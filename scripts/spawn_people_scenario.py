"""Spawn real Gazebo collision models for phase 2 perception scenarios."""
import argparse
import json
import math
from pathlib import Path
import random
import time

import rclpy
from gazebo_msgs.msg import EntityState, ModelStates
from gazebo_msgs.srv import DeleteEntity, GetEntityState, SetEntityState, SpawnEntity
from geometry_msgs.msg import Pose
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_srvs.srv import Trigger
from temi_interfaces.msg import NavigationStatus, SafetyStopStatus
from phase27_scenario import actor_step, collision_envelopes, swept_gap

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'phase25_person_'
LEGACY_PREFIX = 'phase2_person_'
MAX_PEOPLE = 8


class PeopleScenario(Node):
    def __init__(self):
        super().__init__('phase25_people_scenario')
        self._spawn = self.create_client(SpawnEntity, '/spawn_entity')
        self._delete = self.create_client(DeleteEntity, '/delete_entity')
        self._set_state = self.create_client(SetEntityState, '/gazebo/set_entity_state')
        self._get_entity_state = self.create_client(GetEntityState, '/gazebo/get_entity_state')
        self._model_states = {}
        self._model_states_received_at = 0.0
        self._last_pose_confirmation_source = ''
        self.active_navigation_session_id = ''
        self.safety_stop_requested = False
        self._latest_navigation = {}
        self._navigation_received_at = 0.0
        self._odom_speed_mps = None
        self._odom_received_at = 0.0
        self.latest_safety_stop = None
        self.safety_events = []
        self._last_safety_signature = None
        self._pause_tour = self.create_client(Trigger, 'heritage/tour/pause')
        self.create_subscription(ModelStates, '/gazebo/model_states', self._on_model_states, 10)
        self.create_subscription(NavigationStatus, 'temi/navigation_status',
                                 self._on_navigation_status, 10)
        self.create_subscription(Odometry, 'odom', self._on_odom, 10)
        self.create_subscription(SafetyStopStatus, 'heritage/safety_stop/status',
                                 self._on_safety_stop, 10)

    def _on_safety_stop(self, message):
        session_id = message.navigation_session_id
        if (message.source != 'gazebo_nav2_transport' or not session_id):
            return
        if not hasattr(self, 'safety_events'):
            self.safety_events = []
        if not hasattr(self, '_last_safety_signature'):
            self._last_safety_signature = None
        signature = (message.state, session_id, bool(message.valid))
        self.latest_safety_stop = {
            'state': message.state, 'navigation_session_id': session_id,
            'valid': bool(message.valid), 'received_monotonic_sec': time.monotonic(),
        }
        if signature != self._last_safety_signature:
            self.safety_events.append({
                **self.latest_safety_stop, 'source': message.source,
                'reason': getattr(message, 'reason', ''),
            })
            self.safety_events = self.safety_events[-256:]
            self._last_safety_signature = signature
        if message.state == 'CLEAR':
            if message.valid:
                self.active_navigation_session_id = session_id
                self.safety_stop_requested = False
            return
        if (self.active_navigation_session_id and
                session_id != self.active_navigation_session_id):
            return
        if message.state in ('STOP_REQUESTED', 'STOP_COMMAND_ACCEPTED', 'STOPPING',
                             'STOP_CONFIRMED', 'STOP_FAILED'):
            self.active_navigation_session_id = session_id
            self.safety_stop_requested = True

    def request_business_pause(self, timeout_sec=8.0):
        """Request Tour Manager pause and wait for matching real stop evidence."""
        result = {'service': 'heritage/tour/pause', 'requested': True,
                  'response_received': False, 'stop_confirmed': False}
        if not self._pause_tour.wait_for_service(timeout_sec=2.0):
            result['error'] = 'pause service unavailable'
            return result
        future = self._pause_tour.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=3.0)
        if not future.done() or future.exception():
            result['error'] = 'pause service timed out or failed'
            return result
        response = future.result()
        result.update(response_received=True, accepted=bool(response.success),
                      message=response.message)
        deadline = time.monotonic() + timeout_sec
        while rclpy.ok() and time.monotonic() < deadline:
            stop = self.latest_safety_stop
            odom_age = time.monotonic() - self._odom_received_at
            if (stop and stop['state'] == 'STOP_CONFIRMED' and stop['valid'] and
                    stop['navigation_session_id'] == self.active_navigation_session_id and
                    time.monotonic() - stop['received_monotonic_sec'] <= 0.5 and
                    self._odom_speed_mps is not None and self._odom_speed_mps < 0.02 and
                    0.0 <= odom_age <= 0.5):
                result.update(stop_confirmed=True, stopped_session_id=
                              stop['navigation_session_id'], odom_speed_mps=
                              self._odom_speed_mps, odom_age_sec=odom_age)
                break
            rclpy.spin_once(self, timeout_sec=0.05)
        result['safety_events'] = list(self.safety_events)
        return result

    def _on_navigation_status(self, message):
        self._latest_navigation = {
            'task_id': message.task_id, 'target': getattr(message, 'target', ''),
            'status': message.status,
        }
        self._navigation_received_at = time.monotonic()
        if (message.status in ('start', 'calculating', 'going', 'reposing') and
                message.task_id):
            self.active_navigation_session_id = message.task_id

    def _on_odom(self, message):
        twist = message.twist.twist.linear
        speed = math.hypot(twist.x, twist.y)
        if math.isfinite(speed):
            self._odom_speed_mps = speed
            self._odom_received_at = time.monotonic()

    def navigation_snapshot(self, target, now=None):
        now = time.monotonic() if now is None else now
        navigation_age = now - self._navigation_received_at
        odom_age = now - self._odom_received_at
        if (navigation_age < 0 or navigation_age > 0.5 or
                self._latest_navigation.get('target') != target or
                self._latest_navigation.get('status') not in ('going', 'reposing') or
                not self._latest_navigation.get('task_id') or
                odom_age < 0 or odom_age > 0.5 or
                self._odom_speed_mps is None or self._odom_speed_mps < 0.05):
            return None
        return {**self._latest_navigation, 'odom_speed_mps': self._odom_speed_mps,
                'navigation_age_sec': navigation_age, 'odom_age_sec': odom_age}

    def wait_for_navigation(self, target, timeout_sec=120.0):
        deadline = time.monotonic() + timeout_sec
        while rclpy.ok() and time.monotonic() < deadline:
            snapshot = self.navigation_snapshot(target)
            if snapshot is not None:
                return snapshot
            rclpy.spin_once(self, timeout_sec=0.05)
        raise TimeoutError(f'未在 {timeout_sec:.1f}s 内观察到 {target} 的活动导航 UUID 与新鲜 odom 运动')

    def _on_model_states(self, message):
        self._model_states = dict(zip(message.name, message.pose))
        self._model_states_received_at = time.monotonic()

    def current_pose(self):
        return self.wait_for_model_pose('heritage_robot', timeout_sec=5.0)

    @staticmethod
    def _pose(pose):
        q = pose.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                         1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        return {'x': pose.position.x, 'y': pose.position.y, 'yaw': yaw}

    def model_pose(self, name):
        pose = self._model_states.get(name)
        if pose is None or time.monotonic() - self._model_states_received_at > 0.5:
            return None
        return self._pose(pose)

    def wait_for_model_pose(self, name, expected=None, timeout_sec=5.0, tolerance_m=0.08):
        deadline = time.monotonic() + timeout_sec
        while rclpy.ok() and time.monotonic() < deadline:
            pose = self.model_pose(name)
            if pose is not None and (expected is None or
                                     math.hypot(pose['x'] - expected[0],
                                                pose['y'] - expected[1]) <= tolerance_m):
                self._last_pose_confirmation_source = 'gazebo_model_states'
                return pose
            rclpy.spin_once(self, timeout_sec=0.05)
        service_error = ''
        if self._get_entity_state.wait_for_service(timeout_sec=2.0):
            request = GetEntityState.Request(name=name, reference_frame='world')
            future = self._get_entity_state.call_async(request)
            rclpy.spin_until_future_complete(self, future, timeout_sec=2.0)
            if future.done() and not future.exception() and future.result().success:
                pose = self._pose(future.result().state.pose)
                if (expected is None or math.hypot(pose['x'] - expected[0],
                                                   pose['y'] - expected[1]) <= tolerance_m):
                    self._last_pose_confirmation_source = 'gazebo_get_entity_state'
                    return pose
                service_error = f'get_entity_state pose outside tolerance: {pose}'
            elif future.done() and not future.exception():
                service_error = future.result().status_message
            else:
                service_error = 'get_entity_state timed out or failed'
        else:
            service_error = 'get_entity_state service unavailable'
        raise RuntimeError(f'Gazebo 未确认模型位姿：{name}; /model_states stale/timeout; {service_error}')

    def _call(self, client, request):
        if not client.wait_for_service(timeout_sec=10.0):
            raise RuntimeError('Gazebo service unavailable')
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
        if not future.done() or future.exception():
            raise RuntimeError('Gazebo service call failed')
        response = future.result()
        if not response.success:
            detail = getattr(response, 'status_message', '')
            raise RuntimeError(detail or 'Gazebo entity state service returned success=false')
        return response

    def clear_existing(self):
        if not self._delete.wait_for_service(timeout_sec=10.0):
            raise RuntimeError('Gazebo delete_entity 服务不可用')
        removed = []
        for prefix in (PREFIX, LEGACY_PREFIX):
            for index in range(1, MAX_PEOPLE + 1):
                name = f'{prefix}{index:02d}'
                future = self._delete.call_async(DeleteEntity.Request(name=name))
                rclpy.spin_until_future_complete(self, future, timeout_sec=3.0)
                if (future.done() and not future.exception() and
                        future.result().success):
                    removed.append(name)
        deadline = time.monotonic() + 3.0
        while (rclpy.ok() and time.monotonic() < deadline and
               any(name in self._model_states for name in removed)):
            rclpy.spin_once(self, timeout_sec=0.05)
        remaining = [name for name in removed if name in self._model_states]
        if remaining:
            raise RuntimeError(f'Gazebo 未确认删除旧访客模型：{remaining}')
        return removed

    def spawn(self, name, x, y, yaw):
        sdf = (ROOT / 'simulation/models/person_mannequin/model.sdf').read_text()
        sdf = sdf.replace('name="person_mannequin"', f'name="{name}"', 1)
        materials = ROOT / 'simulation/models/person_mannequin/materials'
        sdf = sdf.replace('__VISITOR_MATERIALS_URI__', (materials / 'scripts').resolve().as_uri())
        sdf = sdf.replace('__VISITOR_TEXTURES_URI__', (materials / 'textures').resolve().as_uri())
        pose = Pose()
        pose.position.x, pose.position.y = x, y
        pose.orientation.z, pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        request = SpawnEntity.Request(name=name, xml=sdf, initial_pose=pose, reference_frame='world')
        self._call(self._spawn, request)
        observed = self.wait_for_model_pose(name, (x, y))
        return {'name': name, 'x': x, 'y': y, 'yaw': yaw,
                'gazebo_readback_x': observed['x'], 'gazebo_readback_y': observed['y'],
                'readback_source': self._last_pose_confirmation_source}

    def move(self, name, x, y, yaw):
        state = EntityState()
        state.name = name
        state.reference_frame = 'world'
        state.pose.position.x, state.pose.position.y = x, y
        state.pose.orientation.z, state.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        self._call(self._set_state, SetEntityState.Request(state=state))
        return self.wait_for_model_pose(name, (x, y), tolerance_m=0.02)


def _basis(pose):
    forward = (math.cos(pose.get('yaw', 0.0)), math.sin(pose.get('yaw', 0.0)))
    left = (-forward[1], forward[0])
    return forward, left


def _relative_pose(anchor, forward, left, forward_m, left_m, yaw):
    return (anchor['x'] + forward_m * forward[0] + left_m * left[0],
            anchor['y'] + forward_m * forward[1] + left_m * left[1], yaw)


def navigation_heading(robot_pose, goal_pose):
    dx = goal_pose['x'] - robot_pose['x']
    dy = goal_pose['y'] - robot_pose['y']
    if not all(math.isfinite(value) for value in (dx, dy)):
        raise ValueError('机器人和导航目标坐标必须为有限数值')
    if math.hypot(dx, dy) <= 1e-6:
        return robot_pose['yaw']
    return math.atan2(dy, dx)


def scenario_anchor(scenario, wait, robot_pose):
    return wait if scenario == 'single_static' else robot_pose


def scene_positions(scenario, wait, seed=0):
    x, y = wait['x'], wait['y']
    yaw = wait.get('yaw', 0.0)
    anchor = {'x': x, 'y': y, 'yaw': yaw}
    forward, left = _basis(anchor)
    facing = yaw + math.pi
    if scenario in ('empty', 'clear'):
        return []
    if scenario in ('single', 'single_static'):
        return [_relative_pose(anchor, forward, left, 3.0, 0.0, facing)]
    if scenario in ('group', 'group_static', 'group_straggler'):
        return [_relative_pose(anchor, forward, left, 3.2, offset, facing)
                for offset in (-0.75, 0.0, 0.75)]
    if scenario == 'near':
        return [_relative_pose(anchor, forward, left, 1.05, 0.0, facing)]
    if scenario == 'approaching':
        return [_relative_pose(anchor, forward, left, 4.5, 0.0, facing)]
    if scenario == 'leaving':
        return [_relative_pose(anchor, forward, left, 1.1, 0.0, facing)]
    if scenario == 'crossing':
        return [_relative_pose(anchor, forward, left, 3.5, -1.5, facing)]
    if scenario == 'crowded':
        rng = random.Random(seed)
        offsets = (-1.2, -0.6, 0.0, 0.6, 1.2)
        return [_relative_pose(anchor, forward, left, 3.6,
                               offset + rng.uniform(-0.12, 0.12), facing)
                for offset in offsets]
    return []


def trajectory_position(scenario, start, robot_pose, progress, person_index=0,
                        end_distance_m=1.4):
    """Interpolate the commanded world pose; this is not a sensor detection."""
    if not math.isfinite(progress):
        raise ValueError('progress 必须为有限数值')
    progress = min(1.0, max(0.0, progress))
    if scenario == 'group_straggler' and person_index != 2:
        return start
    anchor = {'x': robot_pose['x'], 'y': robot_pose['y'],
              'yaw': robot_pose.get('yaw', 0.0)}
    forward, left = _basis(anchor)
    if scenario == 'approaching':
        end = _relative_pose(anchor, forward, left, end_distance_m, 0.0, start[2])
    elif scenario == 'crossing':
        end = _relative_pose(anchor, forward, left, 3.5, 1.5, start[2])
    elif scenario == 'leaving':
        end = _relative_pose(anchor, forward, left, 5.0, 0.0, start[2])
    elif scenario == 'group_straggler':
        end = _relative_pose(anchor, forward, left, -1.5, 0.75, start[2])
    else:
        return start
    return tuple(start[index] + (end[index] - start[index]) * progress for index in range(3))


def trajectory_duration(scenario, start, robot_pose, speed_mps, end_distance_m=1.4):
    if not math.isfinite(speed_mps) or speed_mps <= 0:
        raise ValueError('speed_mps 必须为有限正数')
    end = trajectory_position(scenario, start, robot_pose, 1.0,
                              person_index=2 if scenario == 'group_straggler' else 0,
                              end_distance_m=end_distance_m)
    return math.hypot(end[0] - start[0], end[1] - start[1]) / speed_mps


def write_truth_record(output, record):
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')


def ground_truth_path_lengths(samples):
    previous = {}
    lengths = {}
    for sample in samples:
        name = sample['name']
        point = (sample['x'], sample['y'])
        if name in previous:
            lengths[name] = lengths.get(name, 0.0) + math.hypot(
                point[0] - previous[name][0], point[1] - previous[name][1])
        previous[name] = point
    return lengths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', choices=('official', 'adaptive'), default='official')
    parser.add_argument('--scenario', choices=(
        'empty', 'single', 'single_static', 'group', 'group_static', 'near',
        'approaching', 'crossing', 'leaving', 'group_straggler', 'crowded', 'clear'),
        default='empty')
    parser.add_argument('--cleanup-only', action='store_true',
                        help='仅清理本项目固定前缀的人形模型并退出')
    parser.add_argument('--duration-sec', type=float,
                        help='动态轨迹运行时长；省略时按 --speed-mps 和轨迹长度计算')
    parser.add_argument('--speed-mps', type=float, default=0.3)
    parser.add_argument('--end-distance-m', type=float, default=1.4,
                        help='approaching 场景终点；0.65 m 用于危险距离试验')
    parser.add_argument('--target-distance-m', type=float,
                        help='阶段2.7人物终点中心距；仅以接近开始时机器人位置为锚点')
    parser.add_argument('--continue-after-robot-stop', action='store_true',
                        help='机器人停车事件不冻结人物运动；仅供阶段2.7受控实验')
    parser.add_argument('--hold-at-target-sec', type=float, default=2.0)
    parser.add_argument('--leave-after-hold', action='store_true')
    parser.add_argument('--leave-distance-m', type=float, default=3.9,
                        help='从接近终点向外离开的距离；默认回到初始可通行点')
    parser.add_argument('--leave-direction', choices=('forward', 'left', 'right'),
                        default='forward', help='离开时沿路线前方或横向空闲方向移动')
    parser.add_argument('--hold-clear-sec', type=float, default=1.0)
    parser.add_argument('--geometry-margin-m', type=float, default=0.10)
    parser.add_argument('--update-hz', type=float, default=5.0)
    parser.add_argument('--start-delay-sec', type=float, default=2.0)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--person-pose', type=float, nargs=3, metavar=('X', 'Y', 'YAW'))
    parser.add_argument('--wait-for-navigation-target',
                        help='等待指定目标的活动导航 UUID 和新鲜 odom 运动后再注入')
    parser.add_argument('--navigation-timeout-sec', type=float, default=120.0)
    parser.add_argument('--ready-file', type=Path,
                        help='清理完已有模型并准备监听导航后写入的就绪标记')
    parser.add_argument('--remove-after', action='store_true')
    parser.add_argument('--stop-on-safety-stop', action='store_true',
                        help='收到实际 Nav2 停车状态后立即冻结人物轨迹')
    parser.add_argument('--truth-output', type=Path)
    args = parser.parse_args()
    if args.target_distance_m is not None:
        args.end_distance_m = args.target_distance_m
    if args.cleanup_only and args.scenario != 'empty':
        parser.error('--cleanup-only 不能与动态场景同时使用')
    if args.leave_after_hold and not args.continue_after_robot_stop:
        parser.error('--leave-after-hold 需要显式启用 --continue-after-robot-stop')
    if args.continue_after_robot_stop and args.stop_on_safety_stop:
        parser.error('--continue-after-robot-stop 与 --stop-on-safety-stop 互斥')
    if (not math.isfinite(args.speed_mps) or args.speed_mps <= 0 or
            not math.isfinite(args.update_hz) or not 1.0 <= args.update_hz <= 20.0 or
            not math.isfinite(args.start_delay_sec) or args.start_delay_sec < 0 or
            (args.duration_sec is not None and
             (not math.isfinite(args.duration_sec) or args.duration_sec <= 0)) or
            not math.isfinite(args.navigation_timeout_sec) or args.navigation_timeout_sec <= 0 or
            not math.isfinite(args.hold_at_target_sec) or args.hold_at_target_sec < 0 or
            not math.isfinite(args.leave_distance_m) or args.leave_distance_m < 0 or
            not math.isfinite(args.hold_clear_sec) or args.hold_clear_sec < 0 or
            not math.isfinite(args.geometry_margin_m) or args.geometry_margin_m < 0):
        parser.error('speed、update-hz、start-delay 和 duration 参数无效')
    if (not math.isfinite(args.end_distance_m) or
            not 0.5 <= args.end_distance_m <= 4.5):
        parser.error('end-distance-m 必须处于 0.5–4.5 m')

    goals = json.loads((ROOT / 'simulation/generated' / f'{args.layout}_goals.json').read_text())['goals']
    wait = goals['wait']
    rclpy.init(args=None)
    node = PeopleScenario()
    timestamp = time.strftime('%Y%m%d-%H%M%S')
    output = args.truth_output or (ROOT / 'docs/experiments/phase2_5/dynamic_people' /
                                   args.scenario / timestamp / 'truth.json')
    started = time.time()
    started_monotonic = time.monotonic()
    removed = []
    robot_pose = None
    models = []
    path = []
    stopped_by_safety = False
    record = {
        'status': 'FAIL', 'scenario': args.scenario, 'layout': args.layout,
        'source': 'gazebo_model_states_and_set_entity_state',
        'started_unix_sec': started, 'started_monotonic_sec': started_monotonic,
        'movement_started_monotonic_sec': None,
        'movement_ended_monotonic_sec': None,
        'duration_sec': 0.0,
        'seed': args.seed, 'speed_mps': args.speed_mps, 'update_hz': args.update_hz,
        'end_distance_m': args.end_distance_m,
        'actor_motion': {
            'continue_after_robot_stop': bool(args.continue_after_robot_stop),
            'stop_at_target': True, 'movement_speed_mps': args.speed_mps,
            'target_distance_m': args.end_distance_m,
            'hold_at_target_sec': args.hold_at_target_sec,
            'leave_after_hold': bool(args.leave_after_hold),
            'leave_distance_m': args.leave_distance_m,
            'leave_direction': args.leave_direction,
            'hold_clear_sec': args.hold_clear_sec,
            'pause_on_collision': True,
            'motion_phase_events': ([{'phase': 'WAIT_NAV',
                                      'time_monotonic_sec': started_monotonic}]
                                    if args.wait_for_navigation_target else []),
            'contact_observed': None,
        },
        'removed_previous_models': removed, 'commanded_model_poses_world': models,
        'robot_pose_world_at_spawn': robot_pose, 'gazebo_model_state_samples': path,
        'model_asset': 'simulation/models/person_mannequin/model.sdf',
        'ground_truth_note': '轨迹样本来自 Gazebo /model_states 的模型位姿回读；commanded_* 字段是 SetEntityState 输入，不是视觉检测。',
    }
    try:
        removed = node.clear_existing()
        record['removed_previous_models'] = removed
        if args.cleanup_only:
            record.update({'status': 'PASS', 'cleanup_only': True,
                           'removed_after': removed,
                           'duration_sec': time.monotonic() - started_monotonic,
                           'ended_monotonic_sec': time.monotonic()})
            write_truth_record(output, record)
            print(json.dumps(record, ensure_ascii=False))
            return
        if args.ready_file:
            args.ready_file.parent.mkdir(parents=True, exist_ok=True)
            args.ready_file.write_text('ready\n', encoding='utf-8')
        if args.wait_for_navigation_target:
            record['navigation_trigger'] = node.wait_for_navigation(
                args.wait_for_navigation_target, args.navigation_timeout_sec)
        robot_pose = node.current_pose()
        record['robot_pose_world_at_spawn'] = robot_pose
        scenario_robot_pose = robot_pose
        if args.scenario == 'approaching' and args.wait_for_navigation_target:
            goals = json.loads((ROOT / 'simulation/generated/official_goals.json').read_text())['goals']
            target_goal = goals.get(args.wait_for_navigation_target)
            if target_goal is not None:
                scenario_robot_pose = dict(robot_pose)
                scenario_robot_pose['yaw'] = navigation_heading(robot_pose, target_goal)
                record['trajectory_heading_rad'] = scenario_robot_pose['yaw']
                record['trajectory_heading_source'] = 'active_navigation_goal_bearing'
        phase27_motion = (args.scenario == 'approaching' and
                          args.continue_after_robot_stop)
        if phase27_motion:
            robot_radius, actor_radius, envelope_source = collision_envelopes(
                ROOT / 'simulation/robot/heritage_robot.urdf',
                ROOT / 'simulation/models/person_mannequin/model.sdf')
            record['geometry_envelope'] = {
                'robot_radius_m': robot_radius, 'actor_radius_m': actor_radius,
                'margin_m': args.geometry_margin_m, 'source': envelope_source,
                'assumption': 'conservative planar circumscribed circles from URDF/SDF collision shapes; contact sensing unavailable',
            }
        else:
            robot_radius = actor_radius = None
        positions = scene_positions(
            args.scenario, scenario_anchor(args.scenario, wait, scenario_robot_pose),
            seed=args.seed)
        if args.person_pose is not None and positions:
            positions[0] = tuple(args.person_pose)
        models = [node.spawn(f'{PREFIX}{index + 1:02d}', *pose)
                  for index, pose in enumerate(positions)]
        record['commanded_model_poses_world'] = models
        moving = args.scenario in ('approaching', 'crossing', 'leaving', 'group_straggler')
        natural_duration = max(
            (trajectory_duration(args.scenario, (model['x'], model['y'], model['yaw']),
                                 scenario_robot_pose, args.speed_mps, args.end_distance_m)
             for model in models),
            default=0.0)
        duration = (args.duration_sec if args.duration_sec is not None else
                    natural_duration if moving else 5.0)
        if phase27_motion and args.duration_sec is None:
            start_distance = math.hypot(positions[0][0] - scenario_robot_pose['x'],
                                        positions[0][1] - scenario_robot_pose['y'])
            duration = ((start_distance - args.end_distance_m) / args.speed_mps +
                        args.hold_at_target_sec +
                        (args.leave_distance_m / args.speed_mps
                         if args.leave_after_hold else 0.0) +
                        args.hold_clear_sec)
            if duration <= 0.0:
                raise ValueError('阶段2.7人物运动时长必须为正数')
        deadline = time.monotonic() + args.start_delay_sec
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
        if moving and models:
            start = time.monotonic()
            record['movement_started_monotonic_sec'] = start
            interval = 1.0 / args.update_hz
            if phase27_motion:
                model = models[0]
                anchor = (scenario_robot_pose['x'], scenario_robot_pose['y'],
                          scenario_robot_pose.get('yaw', 0.0))
                actor_config = {
                    'speed_mps': args.speed_mps,
                    'start_distance_m': math.hypot(model['x'] - anchor[0],
                                                   model['y'] - anchor[1]),
                    'target_distance_m': args.end_distance_m,
                    'hold_at_target_sec': args.hold_at_target_sec,
                    'leave_after_hold': args.leave_after_hold,
                    'leave_distance_m': args.leave_distance_m,
                    'leave_direction': args.leave_direction,
                    'hold_clear_sec': args.hold_clear_sec,
                }
                record['actor_motion']['start_anchor_world'] = list(anchor)
                record['actor_motion']['start_distance_m'] = actor_config['start_distance_m']
                record['actor_motion'].setdefault('motion_phase_events', [])
                record['actor_motion']['minimum_center_distance_m_by_phase'] = {}
                record['actor_motion']['minimum_geometry_gap_m_by_phase'] = {}
                record['actor_motion']['robot_stop_confirmed_distance_m'] = None
                record['actor_motion']['minimum_center_distance_after_stop_m'] = None
                record['actor_motion']['safety_stop_events'] = node.safety_events
                record['actor_motion']['geometry_risk'] = None
                previous_actor = node.wait_for_model_pose(model['name'])
                previous_robot = node.current_pose()
                current_phase = None
                complete = False
                while rclpy.ok():
                    elapsed = time.monotonic() - start
                    if elapsed > duration + interval:
                        record['actor_motion']['timeout'] = True
                        break
                    step = actor_step(actor_config, elapsed, anchor)
                    robot_now = node.current_pose()
                    commanded = step['pose']
                    geometry_gap = swept_gap(
                        (previous_actor['x'], previous_actor['y'], previous_actor['yaw']),
                        commanded,
                        {'previous': previous_robot, 'current': robot_now},
                        {'robot_radius_m': robot_radius,
                         'actor_radius_m': actor_radius,
                         'margin_m': args.geometry_margin_m})
                    if step['phase'] != current_phase:
                        current_phase = step['phase']
                        record['actor_motion']['motion_phase_events'].append({
                            'phase': current_phase,
                            'time_monotonic_sec': time.monotonic(),
                            'robot_stop_requested': node.safety_stop_requested,
                        })
                    if geometry_gap <= 0.0:
                        pause = node.request_business_pause()
                        record['actor_motion']['geometry_risk'] = {
                            'kind': 'predicted_geometry_risk',
                            'time_monotonic_sec': time.monotonic(),
                            'phase': current_phase,
                            'predicted_gap_m': geometry_gap,
                            'previous_verified_actor_pose': previous_actor,
                            'not_executed_actor_pose': list(commanded),
                            'robot_previous_pose': previous_robot,
                            'robot_current_pose': robot_now,
                            'business_pause': pause,
                            'contact_observed': None,
                        }
                        record['actor_motion']['motion_phase_events'].append({
                            'phase': 'ABORTED', 'time_monotonic_sec': time.monotonic(),
                            'reason': 'PREDICTED_GEOMETRY_RISK',
                        })
                        record['abort_reason'] = 'PREDICTED_GEOMETRY_RISK'
                        record['actor_motion']['contact_observed'] = None
                        break

                    if math.hypot(commanded[0] - previous_actor['x'],
                                  commanded[1] - previous_actor['y']) > 1e-4:
                        actual = node.move(model['name'], *commanded)
                    else:
                        actual = node.wait_for_model_pose(model['name'])
                    robot_after = node.current_pose()
                    observed_gap = swept_gap(
                        (previous_actor['x'], previous_actor['y'], previous_actor['yaw']),
                        (actual['x'], actual['y'], actual['yaw']),
                        {'previous': previous_robot, 'current': robot_after},
                        {'robot_radius_m': robot_radius,
                         'actor_radius_m': actor_radius,
                         'margin_m': args.geometry_margin_m})
                    center_distance = math.hypot(actual['x'] - robot_after['x'],
                                                 actual['y'] - robot_after['y'])
                    sample_time = time.monotonic()
                    stop = node.latest_safety_stop or {}
                    stop_age = (sample_time - stop.get('received_monotonic_sec')
                                if stop.get('received_monotonic_sec') is not None else math.inf)
                    matching_fresh_stop = (
                        stop.get('state') == 'STOP_CONFIRMED' and
                        stop.get('valid') is True and
                        stop.get('navigation_session_id') == node.active_navigation_session_id and
                        0.0 <= stop_age <= 0.5)
                    sample = {
                        'elapsed_sec': sample_time - start,
                        'time_monotonic_sec': sample_time,
                        'name': model['name'], 'x': actual['x'], 'y': actual['y'],
                        'yaw': actual['yaw'], 'commanded_x': commanded[0],
                        'commanded_y': commanded[1], 'actor_phase': current_phase,
                        'robot_x': robot_after['x'], 'robot_y': robot_after['y'],
                        'center_distance_m': center_distance,
                        'geometry_gap_m': observed_gap,
                        'geometry_risk_gap_m': observed_gap,
                        'odom_speed_mps': node._odom_speed_mps,
                        'odom_age_sec': (sample_time - node._odom_received_at
                                         if node._odom_received_at else None),
                        'safety_state': stop.get('state'),
                        'navigation_session_id': stop.get('navigation_session_id'),
                        'safety_sample_age_sec': (stop_age if math.isfinite(stop_age) else None),
                    }
                    path.append(sample)
                    record['gazebo_model_state_samples'] = path
                    center_minima = record['actor_motion']['minimum_center_distance_m_by_phase']
                    gap_minima = record['actor_motion']['minimum_geometry_gap_m_by_phase']
                    center_minima[current_phase] = min(
                        center_minima.get(current_phase, math.inf), center_distance)
                    gap_minima[current_phase] = min(
                        gap_minima.get(current_phase, math.inf), observed_gap)
                    if (matching_fresh_stop and
                            record['actor_motion']['robot_stop_confirmed_distance_m'] is None):
                        record['actor_motion']['robot_stop_confirmed_distance_m'] = center_distance
                    if node.safety_stop_requested and matching_fresh_stop:
                        prior = record['actor_motion']['minimum_center_distance_after_stop_m']
                        record['actor_motion']['minimum_center_distance_after_stop_m'] = (
                            center_distance if prior is None else min(prior, center_distance))
                    if observed_gap <= 0.0:
                        pause = node.request_business_pause()
                        record['actor_motion']['geometry_risk'] = {
                            'kind': 'observed_geometry_overlap',
                            'time_monotonic_sec': sample_time,
                            'phase': current_phase, 'observed_gap_m': observed_gap,
                            'robot_pose': robot_after, 'actor_pose': actual,
                            'business_pause': pause, 'contact_observed': None,
                        }
                        record['actor_motion']['motion_phase_events'].append({
                            'phase': 'ABORTED', 'time_monotonic_sec': sample_time,
                            'reason': 'OBSERVED_GEOMETRY_OVERLAP',
                        })
                        record['abort_reason'] = 'OBSERVED_GEOMETRY_OVERLAP'
                        record['actor_motion']['contact_observed'] = None
                        break
                    previous_actor, previous_robot = actual, robot_after
                    if step['finished']:
                        complete = True
                        record['actor_motion']['finished_phase'] = current_phase
                        break
                    time.sleep(interval)
                record['actor_motion']['completed'] = complete
                record['actor_motion']['actor_retained_at_end'] = True
                if record.get('abort_reason'):
                    raise RuntimeError(record['abort_reason'])
                if not complete:
                    raise TimeoutError('人物阶段未能在配置时限内完成')
                stopped_by_safety = node.safety_stop_requested
            else:
                while rclpy.ok():
                    if args.stop_on_safety_stop and node.safety_stop_requested:
                        stopped_by_safety = True
                        break
                    elapsed = min(time.monotonic() - start, duration)
                    progress = min(1.0, elapsed / duration)
                    for index, model in enumerate(models):
                        x, y, yaw = trajectory_position(
                            args.scenario, (model['x'], model['y'], model['yaw']),
                            scenario_robot_pose, progress, person_index=index,
                            end_distance_m=args.end_distance_m)
                        if progress > 0:
                            node.move(model['name'], x, y, yaw)
                        actual = node.wait_for_model_pose(model['name'])
                        sampled_at = time.monotonic()
                        path.append({'elapsed_sec': sampled_at - start,
                                     'time_monotonic_sec': sampled_at,
                                     'name': model['name'], 'x': actual['x'],
                                     'y': actual['y'], 'yaw': actual['yaw'],
                                     'commanded_x': x, 'commanded_y': y})
                        record['gazebo_model_state_samples'] = path
                    if progress >= 1.0:
                        break
                    if args.stop_on_safety_stop and node.safety_stop_requested:
                        stopped_by_safety = True
                        break
                    time.sleep(interval)
            record['movement_ended_monotonic_sec'] = time.monotonic()
        elif duration > 0:
            end = time.monotonic() + duration
            while rclpy.ok() and time.monotonic() < end:
                for model in models:
                    actual = node.wait_for_model_pose(model['name'])
                    path.append({'elapsed_sec': time.monotonic() - started_monotonic,
                                 'name': model['name'], 'x': actual['x'],
                                 'y': actual['y'], 'yaw': actual['yaw'],
                                 'commanded_x': model['x'], 'commanded_y': model['y']})
                    record['gazebo_model_state_samples'] = path
                time.sleep(min(1.0 / args.update_hz, max(0.0, end - time.monotonic())))
        if moving and models:
            path_lengths = ground_truth_path_lengths(path)
            record['gazebo_ground_truth_path_length_m_by_person'] = path_lengths
            moving_models = [model['name'] for index, model in enumerate(models)
                             if args.scenario != 'group_straggler' or index == 2]
            if any(path_lengths.get(name, 0.0) < 0.05 for name in moving_models):
                raise RuntimeError('Gazebo 真值位姿未确认到动态人物实际移动')
        removed_after = node.clear_existing() if args.remove_after else []
        record.update({
            'status': 'PASS', 'duration_sec': time.monotonic() - started_monotonic,
            'ended_monotonic_sec': time.monotonic(),
            'stopped_by_actual_safety_status': stopped_by_safety,
            'removed_after': removed_after,
        })
        write_truth_record(output, record)
        print(json.dumps(record, ensure_ascii=False))
    except Exception as error:
        record.update({'status': 'FAIL', 'duration_sec': time.monotonic() - started_monotonic,
                       'ended_monotonic_sec': time.monotonic(),
                       'error': f'{type(error).__name__}: {error}'})
        if record.get('abort_reason'):
            record['failed_cleanup_removed'] = []
            record['actor_retained_for_risk_review'] = True
        else:
            try:
                record['failed_cleanup_removed'] = node.clear_existing()
            except Exception as cleanup_error:
                record['failed_cleanup_error'] = f'{type(cleanup_error).__name__}: {cleanup_error}'
        write_truth_record(output, record)
        print(json.dumps(record, ensure_ascii=False))
        raise
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
