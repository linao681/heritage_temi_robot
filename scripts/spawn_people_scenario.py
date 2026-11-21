"""Spawn real Gazebo collision models for phase 2 perception scenarios."""
import argparse
import json
import math
from pathlib import Path
import random
import time

import rclpy
from gazebo_msgs.msg import EntityState, ModelStates
from gazebo_msgs.srv import DeleteEntity, SetEntityState, SpawnEntity
from geometry_msgs.msg import Pose
from rclpy.node import Node
from temi_interfaces.msg import NavigationStatus, SafetyStopStatus

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
        self._model_states = {}
        self._model_states_received_at = 0.0
        self.active_navigation_session_id = ''
        self.safety_stop_requested = False
        self.create_subscription(ModelStates, '/gazebo/model_states', self._on_model_states, 10)
        self.create_subscription(NavigationStatus, 'temi/navigation_status',
                                 self._on_navigation_status, 10)
        self.create_subscription(SafetyStopStatus, 'heritage/safety_stop/status',
                                 self._on_safety_stop, 10)

    def _on_safety_stop(self, message):
        session_id = message.navigation_session_id
        if (message.source != 'gazebo_nav2_transport' or not session_id):
            return
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

    def _on_navigation_status(self, message):
        if (message.status in ('start', 'calculating', 'going', 'reposing') and
                message.task_id):
            self.active_navigation_session_id = message.task_id

    def _on_model_states(self, message):
        self._model_states = dict(zip(message.name, message.pose))
        self._model_states_received_at = time.monotonic()

    def current_pose(self):
        deadline = time.monotonic() + 5.0
        while (rclpy.ok() and 'heritage_robot' not in self._model_states and
               time.monotonic() < deadline):
            rclpy.spin_once(self, timeout_sec=0.1)
        if 'heritage_robot' not in self._model_states:
            raise RuntimeError('Gazebo /model_states 中没有 heritage_robot，未生成人员模型')
        return self._pose(self._model_states['heritage_robot'])

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

    def wait_for_model_pose(self, name, expected=None, timeout_sec=2.0):
        deadline = time.monotonic() + timeout_sec
        while rclpy.ok() and time.monotonic() < deadline:
            pose = self.model_pose(name)
            if pose is not None and (expected is None or
                                     math.hypot(pose['x'] - expected[0],
                                                pose['y'] - expected[1]) <= 0.08):
                return pose
            rclpy.spin_once(self, timeout_sec=0.05)
        raise RuntimeError(f'Gazebo /model_states 未确认模型位姿：{name}')

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
        self.wait_for_model_pose(name, (x, y))
        return {'name': name, 'x': x, 'y': y, 'yaw': yaw}

    def move(self, name, x, y, yaw):
        state = EntityState()
        state.name = name
        state.reference_frame = 'world'
        state.pose.position.x, state.pose.position.y = x, y
        state.pose.orientation.z, state.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        self._call(self._set_state, SetEntityState.Request(state=state))
        self.wait_for_model_pose(name)


def _basis(pose):
    forward = (math.cos(pose.get('yaw', 0.0)), math.sin(pose.get('yaw', 0.0)))
    left = (-forward[1], forward[0])
    return forward, left


def _relative_pose(anchor, forward, left, forward_m, left_m, yaw):
    return (anchor['x'] + forward_m * forward[0] + left_m * left[0],
            anchor['y'] + forward_m * forward[1] + left_m * left[1], yaw)


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
        return [_relative_pose(anchor, forward, left, 2.4, -1.2, yaw + math.pi / 2)]
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
        end = _relative_pose(anchor, forward, left, 2.4, 1.2, start[2])
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
        required=True)
    parser.add_argument('--duration-sec', type=float,
                        help='动态轨迹运行时长；省略时按 --speed-mps 和轨迹长度计算')
    parser.add_argument('--speed-mps', type=float, default=0.3)
    parser.add_argument('--end-distance-m', type=float, default=1.4,
                        help='approaching 场景终点；0.65 m 用于危险距离试验')
    parser.add_argument('--update-hz', type=float, default=5.0)
    parser.add_argument('--start-delay-sec', type=float, default=2.0)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--person-pose', type=float, nargs=3, metavar=('X', 'Y', 'YAW'))
    parser.add_argument('--remove-after', action='store_true')
    parser.add_argument('--stop-on-safety-stop', action='store_true',
                        help='收到实际 Nav2 停车状态后立即冻结人物轨迹')
    parser.add_argument('--truth-output', type=Path)
    args = parser.parse_args()
    if (not math.isfinite(args.speed_mps) or args.speed_mps <= 0 or
            not math.isfinite(args.update_hz) or not 1.0 <= args.update_hz <= 20.0 or
            not math.isfinite(args.start_delay_sec) or args.start_delay_sec < 0 or
            (args.duration_sec is not None and
             (not math.isfinite(args.duration_sec) or args.duration_sec <= 0))):
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
        'started_unix_sec': started, 'duration_sec': 0.0,
        'seed': args.seed, 'speed_mps': args.speed_mps, 'update_hz': args.update_hz,
        'end_distance_m': args.end_distance_m,
        'removed_previous_models': removed, 'commanded_model_poses_world': models,
        'robot_pose_world_at_spawn': robot_pose, 'gazebo_model_state_samples': path,
        'model_asset': 'simulation/models/person_mannequin/model.sdf',
        'ground_truth_note': '轨迹样本来自 Gazebo /model_states 的模型位姿回读；commanded_* 字段是 SetEntityState 输入，不是视觉检测。',
    }
    try:
        removed = node.clear_existing()
        record['removed_previous_models'] = removed
        robot_pose = node.current_pose()
        record['robot_pose_world_at_spawn'] = robot_pose
        positions = scene_positions(
            args.scenario, scenario_anchor(args.scenario, wait, robot_pose), seed=args.seed)
        if args.person_pose is not None and positions:
            positions[0] = tuple(args.person_pose)
        models = [node.spawn(f'{PREFIX}{index + 1:02d}', *pose)
                  for index, pose in enumerate(positions)]
        record['commanded_model_poses_world'] = models
        moving = args.scenario in ('approaching', 'crossing', 'leaving', 'group_straggler')
        natural_duration = max(
            (trajectory_duration(args.scenario, (model['x'], model['y'], model['yaw']),
                                 robot_pose, args.speed_mps, args.end_distance_m)
             for model in models),
            default=0.0)
        duration = (args.duration_sec if args.duration_sec is not None else
                    natural_duration if moving else 5.0)
        deadline = time.monotonic() + args.start_delay_sec
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
        if moving and models:
            start = time.monotonic()
            interval = 1.0 / args.update_hz
            while rclpy.ok():
                if args.stop_on_safety_stop and node.safety_stop_requested:
                    stopped_by_safety = True
                    break
                elapsed = min(time.monotonic() - start, duration)
                progress = min(1.0, elapsed / duration)
                for index, model in enumerate(models):
                    x, y, yaw = trajectory_position(
                        args.scenario, (model['x'], model['y'], model['yaw']),
                        robot_pose, progress, person_index=index,
                        end_distance_m=args.end_distance_m)
                    if progress > 0:
                        node.move(model['name'], x, y, yaw)
                    actual = node.wait_for_model_pose(model['name'])
                    path.append({'elapsed_sec': time.monotonic() - start,
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
            'stopped_by_actual_safety_status': stopped_by_safety,
            'removed_after': removed_after,
        })
        write_truth_record(output, record)
        print(json.dumps(record, ensure_ascii=False))
    except Exception as error:
        record.update({'status': 'FAIL', 'duration_sec': time.monotonic() - started_monotonic,
                       'error': f'{type(error).__name__}: {error}'})
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
