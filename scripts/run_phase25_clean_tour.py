#!/usr/bin/env python3
"""Run a camera-gated, explicitly consented five-zone Gazebo tour and record it."""
import argparse
from datetime import datetime, timezone
import json
import math
import signal
from pathlib import Path
import subprocess
import sys
import time

import rclpy
from gazebo_msgs.msg import ModelStates
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger
from temi_interfaces.msg import NavigationStatus, PerceptionInput, SafetyStopStatus
from temi_interfaces.srv import SubmitQuestion
from tf2_ros import Buffer, TransformException, TransformListener

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROUTE = ['wait', 'zone_1', 'zone_2', 'zone_3', 'zone_4', 'zone_5', 'exit']


class TourEvidence(Node):
    def __init__(self):
        super().__init__('phase25_clean_tour_evidence')
        self.visitor = {}
        self.tour = {}
        self.events = []
        self.speed_events = []
        self.perception_events = []
        self._last_tour_signature = None
        self._last_speed_signature = None
        self._last_perception_signature = None
        self._last_stop_signature = None
        self._last_stop_sample_at = 0.0
        self.navigation = []
        self.stops = []
        self.odom = []
        self.gazebo = {}
        self.goals = json.loads((ROOT / 'simulation/generated/official_goals.json').read_text())['goals']
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.create_subscription(String, 'heritage/visitor/status', self._visitor, 10)
        self.create_subscription(String, 'heritage/tour/status', self._tour, 10)
        self.create_subscription(String, 'heritage/speed_control/status', self._speed, 10)
        self.create_subscription(PerceptionInput, 'heritage/perception/fused',
                                 self._perception, 10)
        self.create_subscription(NavigationStatus, 'temi/navigation_status', self._navigation, 50)
        self.create_subscription(SafetyStopStatus, 'heritage/safety_stop/status', self._stop, 20)
        self.create_subscription(Odometry, 'odom', self._odom, 50)
        self.create_subscription(ModelStates, '/gazebo/model_states', self._models, 10)
        self.trigger_clients = {
            name: self.create_client(Trigger, 'heritage/tour/' + name)
            for name in ('start', 'accept', 'cancel')
        }
        self.question = self.create_client(SubmitQuestion, 'heritage/tour/ask')

    def _timestamp(self):
        return time.monotonic()

    def _visitor(self, message):
        try:
            self.visitor = json.loads(message.data)
        except (TypeError, ValueError):
            self.visitor = {}

    def _tour(self, message):
        try:
            current = json.loads(message.data)
        except (TypeError, ValueError):
            return
        signature = tuple(current.get(key) for key in
                          ('state', 'reason', 'outcome', 'route_index', 'target',
                           'qa_waiting', 'connected', 'is_moving', 'current_location')) + (tuple(current.get('visited', [])),
                                             json.dumps(current.get('qa_result'), sort_keys=True))
        if signature != self._last_tour_signature:
            self.events.append({
                'time_monotonic_sec': self._timestamp(), 'kind': 'tour_status',
                'state': current.get('state'), 'reason': current.get('reason'),
                'outcome': current.get('outcome'), 'route_index': current.get('route_index'),
                'target': current.get('target'), 'visited': current.get('visited', []),
                'qa_waiting': current.get('qa_waiting'), 'qa_result': current.get('qa_result'),
                'connected': current.get('connected'),
                'is_moving': current.get('is_moving'),
                'current_location': current.get('current_location'),
            })
            self._last_tour_signature = signature
        self.tour = current

    def _speed(self, message):
        try:
            value = json.loads(message.data)
        except (TypeError, ValueError):
            return
        signature = tuple(value.get(key) for key in (
            'state', 'reason', 'navigation_session_id', 'stop_requested',
            'stop_confirmed', 'resume_requested', 'target_speed_mps', 'command_status'))
        if signature != self._last_speed_signature:
            self.speed_events.append({'time_monotonic_sec': self._timestamp(),
                                      'status': {key: value.get(key) for key in (
                                          'state', 'reason', 'navigation_session_id',
                                          'stop_requested', 'stop_confirmed', 'resume_requested',
                                          'target_speed_mps', 'command_status', 'input_valid')}})
            self._last_speed_signature = signature

    def _perception(self, message):
        signature = (
            bool(message.valid), message.error, int(message.people_count),
            message.person_observation_state, bool(message.person_distance_valid),
            bool(message.person_observation_valid), bool(message.people_valid),
            round(float(message.nearest_person_m), 1) if message.person_distance_valid else None,
            round(float(message.obstacle_distance_m), 1) if message.obstacle_distance_valid else None,
            bool(message.safety_stop), bool(message.stop_confirmed),
            bool(message.navigating), bool(message.explaining), bool(message.navigation_error),
            message.navigation_session_id,
        )
        if signature != self._last_perception_signature:
            self.perception_events.append({
                'time_monotonic_sec': self._timestamp(), 'valid': bool(message.valid),
                'error': message.error, 'people_count': int(message.people_count),
                'people_valid': bool(message.people_valid),
                'sample_age_sec': float(message.sample_age_sec),
                'person_observation_state': message.person_observation_state,
                'person_observation_valid': bool(message.person_observation_valid),
                'person_distance_valid': bool(message.person_distance_valid),
                'nearest_person_m': (float(message.nearest_person_m)
                                     if message.person_distance_valid else None),
                'obstacle_distance_valid': bool(message.obstacle_distance_valid),
                'obstacle_distance_m': (float(message.obstacle_distance_m)
                                        if message.obstacle_distance_valid else None),
                'safety_stop': bool(message.safety_stop),
                'stop_confirmed': bool(message.stop_confirmed),
                'navigating': bool(message.navigating), 'explaining': bool(message.explaining),
                'navigation_error': bool(message.navigation_error),
                'navigation_session_id': message.navigation_session_id,
            })
            self._last_perception_signature = signature

    def _navigation(self, message):
        event = {
            'time_monotonic_sec': self._timestamp(), 'task_id': message.task_id,
            'target': message.target, 'status': message.status,
            'description': message.description,
        }
        target = self.goals.get(message.target)
        if target is not None and message.status == 'complete':
            try:
                pose = self.tf_buffer.lookup_transform(
                    'map', 'base_footprint', rclpy.time.Time()).transform
                event['robot_map_pose'] = {
                    'x': pose.translation.x, 'y': pose.translation.y,
                }
                event['goal_map_pose'] = {'x': target['x'], 'y': target['y']}
                event['position_error_m'] = math.hypot(
                    pose.translation.x - target['x'], pose.translation.y - target['y'])
            except TransformException:
                event['position_error_m'] = None
        self.navigation.append(event)

    def _stop(self, message):
        now = self._timestamp()
        signature = (message.state, message.navigation_session_id)
        if (signature == self._last_stop_signature and message.state == 'CLEAR' or
                now - self._last_stop_sample_at < 0.2 and signature == self._last_stop_signature):
            return
        self.stops.append({
            'time_monotonic_sec': now, 'state': message.state,
            'navigation_session_id': message.navigation_session_id,
            'reason': message.reason, 'valid': bool(message.valid),
            'action_terminal': bool(message.action_terminal),
            'linear_speed_mps': float(message.linear_speed_mps),
            'angular_speed_rps': float(message.angular_speed_rps),
            'odom_age_sec': float(message.odom_age_sec),
            'stopped_duration_sec': float(message.stopped_duration_sec),
        })
        self._last_stop_signature = signature
        self._last_stop_sample_at = now

    def _odom(self, message):
        twist = message.twist.twist
        self.odom.append({
            'time_monotonic_sec': self._timestamp(),
            'linear_mps': math.hypot(twist.linear.x, twist.linear.y),
            'angular_rps': abs(twist.angular.z),
        })

    def _models(self, message):
        models = dict(zip(message.name, message.pose))
        robot = models.get('heritage_robot')
        if robot is not None:
            self.gazebo = {
                'time_monotonic_sec': self._timestamp(),
                'robot_x': robot.position.x, 'robot_y': robot.position.y,
                'person_count': sum(name.startswith(('phase25_person_', 'phase2_person_'))
                                    for name in message.name),
            }

    def stationary_duration_at(self, stamp):
        selected = [sample for sample in self.odom
                    if sample['time_monotonic_sec'] <= stamp]
        if not selected:
            return 0.0
        end = selected[-1]
        if stamp - end['time_monotonic_sec'] > 0.5:
            return 0.0
        if end['linear_mps'] >= 0.02 or end['angular_rps'] >= 0.05:
            return 0.0
        start = end['time_monotonic_sec']
        previous = end
        for sample in reversed(selected[:-1]):
            if (previous['time_monotonic_sec'] - sample['time_monotonic_sec'] > 0.5 or
                    sample['linear_mps'] >= 0.02 or sample['angular_rps'] >= 0.05):
                break
            start = sample['time_monotonic_sec']
            previous = sample
        return max(0.0, end['time_monotonic_sec'] - start)


def spin_until(node, predicate, timeout_sec, description):
    deadline = time.monotonic() + timeout_sec
    while rclpy.ok() and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
        if predicate():
            return
    raise TimeoutError(f'等待超时：{description}')


def trigger(node, client, name):
    if not client.wait_for_service(timeout_sec=10.0):
        raise RuntimeError(f'服务不可用：heritage/tour/{name}')
    future = client.call_async(Trigger.Request())
    rclpy.spin_until_future_complete(node, future, timeout_sec=12.0)
    if not future.done() or future.exception():
        raise RuntimeError(f'服务调用失败：{name}')
    result = future.result()
    if not result.success:
        raise RuntimeError(f'{name} 未接受：{result.message}')
    return result.message


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def safety_pause_timeout_budget_sec(args):
    if args.dynamic_scenario != 'approaching' or not args.continue_after_robot_stop:
        return min(30.0, args.timeout_sec)
    approach_sec = max(0.0, 4.5 - args.scenario_end_distance_m) / args.person_speed_mps
    leave_sec = args.leave_distance_m / args.person_speed_mps if args.leave_after_hold else 0.0
    actor_sec = approach_sec + args.hold_at_target_sec + leave_sec + args.hold_clear_sec
    return min(args.timeout_sec, max(30.0, actor_sec + 30.0))


def validate_dynamic_scenario_evidence(truth, perception_events, speed_events,
                                       navigation_events):
    start = truth.get('movement_started_monotonic_sec')
    end = truth.get('movement_ended_monotonic_sec')
    if (not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or
            not math.isfinite(start) or not math.isfinite(end) or end < start):
        raise AssertionError('动态场景缺少有效的 Gazebo 人物移动时间窗口')
    path_lengths = truth.get('gazebo_ground_truth_path_length_m_by_person', {})
    moved = {name: distance for name, distance in path_lengths.items()
             if isinstance(distance, (int, float)) and math.isfinite(distance) and
             distance >= 0.05}
    if not moved:
        raise AssertionError('Gazebo 真值未证实人物在实验窗口内移动')

    detections = [event for event in perception_events
                  if start <= event.get('time_monotonic_sec', -1) <= end and
                  event.get('person_distance_valid') is True and
                  event.get('person_observation_valid', True) is True and
                  event.get('person_observation_state', 'PERSON_DISTANCE_VALID') != 'SENSOR_INVALID' and
                  isinstance(event.get('nearest_person_m'), (int, float)) and
                  math.isfinite(event['nearest_person_m'])]
    if not detections:
        raise AssertionError('人物移动窗口内没有有效的人员距离通道观测')

    person_distance_slow_responses = []
    person_distance_stop_responses = []
    laser_obstacle_responses = []
    ambiguous_safety_responses = []
    multi_source_stop_responses = []
    for event in speed_events:
        if not start <= event.get('time_monotonic_sec', -1) <= end:
            continue
        status = event.get('status', {})
        reason = status.get('reason', '')
        if status.get('input_valid') is not True:
            continue
        has_nearby_distance = any(
            abs(event['time_monotonic_sec'] - detection['time_monotonic_sec']) <= 2.0
            for detection in detections)
        if (status.get('state') == 'SLOW' and
                reason == '接近游客，按距离减速' and has_nearby_distance):
            person_distance_slow_responses.append(event)
        elif (status.get('state') in ('STOPPING', 'STOPPED') and
              reason == '人员与障碍物近距离停车'):
            multi_source_stop_responses.append(event)
        elif (status.get('state') in ('STOPPING', 'STOPPED') and
              reason == '近距离人员停车' and has_nearby_distance):
            person_distance_stop_responses.append(event)
        elif (status.get('state') == 'SLOW' and reason == '前方障碍，按距离减速'):
            laser_obstacle_responses.append(event)
        elif (status.get('state') in ('STOPPING', 'STOPPED') and
              reason == '近距离障碍物停车'):
            laser_obstacle_responses.append(event)
        elif (status.get('state') in ('STOPPING', 'STOPPED') and '安全停车条件' in reason):
            ambiguous_safety_responses.append(event)
    navigation_responses = [event for event in navigation_events
                            if start <= event.get('time_monotonic_sec', -1) <= end and
                            event.get('status') == 'reposing']
    if (not person_distance_slow_responses and not person_distance_stop_responses and
            not laser_obstacle_responses and not ambiguous_safety_responses and
            not multi_source_stop_responses and not navigation_responses):
        raise AssertionError('人物移动窗口内没有可归因的限速、停车或 Nav2 避障响应')
    person_distance_responses = (person_distance_slow_responses +
                                 person_distance_stop_responses)
    risk_only = not person_distance_responses and not navigation_responses
    if person_distance_stop_responses and person_distance_slow_responses:
        attribution = 'PERSON_DISTANCE_SLOWING_AND_STOP'
    elif person_distance_stop_responses:
        attribution = 'PERSON_DISTANCE_STOP'
    elif person_distance_slow_responses:
        attribution = 'PERSON_DISTANCE_SLOWING_ONLY'
    elif navigation_responses:
        attribution = 'NAV2_AVOIDANCE'
    elif multi_source_stop_responses:
        attribution = 'PERSON_AND_LIDAR_STOP'
    elif laser_obstacle_responses:
        attribution = 'LIDAR_OBSTACLE_RESPONSE'
    else:
        attribution = 'SAFETY_SOURCE_AMBIGUOUS'
    return {
        'movement_window_monotonic_sec': [start, end],
        'gazebo_moved_models': moved,
        'valid_person_distance_channel_observations': len(detections),
        'valid_aggregate_fusion_observations': sum(
            event.get('valid') is True for event in detections),
        'person_distance_control_responses': len(person_distance_responses),
        'person_distance_slow_responses': len(person_distance_slow_responses),
        'person_distance_stop_responses': len(person_distance_stop_responses),
        'laser_obstacle_control_responses': len(laser_obstacle_responses),
        'ambiguous_safety_stop_responses': len(ambiguous_safety_responses),
        'multi_source_stop_responses': len(multi_source_stop_responses),
        'navigation_avoidance_responses': len(navigation_responses),
        'status': 'PASS_WITH_RISK' if risk_only else 'PASS',
        'response_attribution': attribution,
    }


def validate_leaving_recovery_evidence(truth, speed_events, stop_events,
                                       navigation_events, perception_events=()):
    start = truth['movement_started_monotonic_sec']
    end = truth['movement_ended_monotonic_sec']
    person_stop = next((event for event in speed_events
                        if start <= event.get('time_monotonic_sec', -1) <= end and
                        event.get('status', {}).get('state') in ('STOPPING', 'STOPPED') and
                        event.get('status', {}).get('navigation_session_id')), None)
    if person_stop is None:
        raise AssertionError('E06 未记录带导航 UUID 的停车请求')
    stop_time = person_stop['time_monotonic_sec']
    status = person_stop.get('status', {})
    nearby_person = next((event for event in perception_events
                          if abs(event.get('time_monotonic_sec', -1) - stop_time) <= 1.0 and
                          event.get('person_distance_valid') is True and
                          isinstance(event.get('nearest_person_m'), (int, float)) and
                          math.isfinite(event['nearest_person_m']) and
                          0.0 < event['nearest_person_m'] <= 1.6), None)
    direct_person_stop = (status.get('reason') in ('近距离危险停车', '近距离人员停车') and
                          status.get('input_valid') is not False and nearby_person is not None)
    fail_closed_stop = (status.get('input_valid') is False and
                        status.get('reason') == '感知数据无效或过期' and
                        nearby_person is not None)
    if not direct_person_stop and not fail_closed_stop:
        raise AssertionError('E06 停车缺少近距离人员测距证据或停车原因不明确')
    old_session = person_stop['status'].get('navigation_session_id')
    target = next((event.get('target') for event in reversed(navigation_events)
                   if event.get('task_id') == old_session and event.get('target') and
                   event.get('time_monotonic_sec', 0) <= stop_time), None)
    if not target:
        raise AssertionError('E06 无法把停车会话关联到原导航目标')

    confirmed = next((event for event in stop_events
                      if event.get('navigation_session_id') == old_session and
                      event.get('state') == 'STOP_CONFIRMED' and event.get('valid') is True and
                      event.get('time_monotonic_sec', 0) >= stop_time), None)
    if confirmed is None:
        raise AssertionError('E06 缺少同一 UUID 的新鲜停车确认')

    recovery = next((event for event in speed_events
                     if event.get('time_monotonic_sec', 0) > confirmed['time_monotonic_sec'] and
                     (event.get('status', {}).get('state') == 'RECOVERING' or
                      event.get('status', {}).get('resume_requested') is True)), None)
    if recovery is None:
        raise AssertionError('E06 停车确认后没有记录自动恢复请求')
    resumed = next((event for event in navigation_events
                    if event.get('time_monotonic_sec', 0) > recovery['time_monotonic_sec'] and
                    event.get('status') == 'start' and event.get('target') == target and
                    event.get('task_id') and event.get('task_id') != old_session), None)
    if resumed is None:
        raise AssertionError('E06 未以新导航 UUID 恢复原目标')
    cleared = next((event for event in stop_events
                    if event.get('navigation_session_id') in (old_session, resumed['task_id']) and
                    event.get('state') == 'CLEAR' and event.get('valid') is True and
                    event.get('time_monotonic_sec', 0) > confirmed['time_monotonic_sec'] and
                    event.get('time_monotonic_sec', 0) <= resumed['time_monotonic_sec'] + 1.0), None)
    if cleared is None:
        raise AssertionError('E06 恢复窗口内没有观察到有效 CLEAR 状态')
    clear_after_resume = cleared['time_monotonic_sec'] > resumed['time_monotonic_sec']
    return {
        'status': 'PASS_WITH_RISK' if fail_closed_stop else 'PASS',
        'stop_cause': ('FAIL_CLOSED_WITH_NEAR_PERSON_OBSERVATION' if fail_closed_stop
                       else 'PERSON_DISTANCE_THRESHOLD'),
        'near_person_distance_m': nearby_person['nearest_person_m'],
        'stop_session_id': old_session, 'target': target,
        'stop_confirmed_at_monotonic_sec': confirmed['time_monotonic_sec'],
        'safety_cleared_at_monotonic_sec': cleared['time_monotonic_sec'],
        'clear_after_resume': clear_after_resume,
        'recovery_requested_at_monotonic_sec': recovery['time_monotonic_sec'],
        'resumed_session_id': resumed['task_id'],
        'resumed_at_monotonic_sec': resumed['time_monotonic_sec'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment-id', default='E01')
    parser.add_argument('--timeout-sec', type=float, default=1200.0)
    parser.add_argument('--visitor-timeout-sec', type=float, default=90.0)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--question', default='潮州音乐有哪些类型？')
    parser.add_argument('--exhibit', default='exhibit_05')
    parser.add_argument('--dynamic-scenario',
                        choices=('none', 'crossing', 'approaching', 'leaving'), default='none',
                        help='与真实导航路段联动的 Gazebo 动态人物实验')
    parser.add_argument('--scenario-target', default='zone_4')
    parser.add_argument('--person-speed-mps', type=float, default=0.25)
    parser.add_argument('--scenario-end-distance-m', type=float, default=1.4)
    parser.add_argument('--continue-after-robot-stop', action='store_true',
                        help='让人物在机器人安全停车后仍继续独立轨迹')
    parser.add_argument('--hold-at-target-sec', type=float, default=2.0)
    parser.add_argument('--leave-after-hold', action='store_true')
    parser.add_argument('--leave-distance-m', type=float, default=3.9)
    parser.add_argument('--leave-direction', choices=('forward', 'left', 'right'),
                        default='forward')
    parser.add_argument('--hold-clear-sec', type=float, default=1.0)
    parser.add_argument('--retain-scenario-model', action='store_true',
                        help='导览结束前不删除人物；结束时由本轮清理')
    args = parser.parse_args()
    if (not math.isfinite(args.timeout_sec) or args.timeout_sec <= 0 or
            not math.isfinite(args.visitor_timeout_sec) or args.visitor_timeout_sec <= 0 or
            not math.isfinite(args.person_speed_mps) or args.person_speed_mps <= 0 or
            not math.isfinite(args.scenario_end_distance_m) or
            not 0.5 <= args.scenario_end_distance_m <= 4.5 or
            not math.isfinite(args.hold_at_target_sec) or args.hold_at_target_sec < 0 or
            not math.isfinite(args.leave_distance_m) or args.leave_distance_m < 0 or
            not math.isfinite(args.hold_clear_sec) or args.hold_clear_sec < 0):
        parser.error('timeout 参数必须是有限正数')
    if args.continue_after_robot_stop and args.dynamic_scenario != 'approaching':
        parser.error('--continue-after-robot-stop 当前仅支持 approaching 场景')
    if args.leave_after_hold and not args.continue_after_robot_stop:
        parser.error('--leave-after-hold 需要启用 --continue-after-robot-stop')
    if args.continue_after_robot_stop and not args.retain_scenario_model:
        parser.error('持续接近实验必须启用 --retain-scenario-model')
    pause_timeout_sec = safety_pause_timeout_budget_sec(args)
    domain = int(__import__('os').environ.get('ROS_DOMAIN_ID', '-1'))
    if (__import__('os').environ.get('ROS_LOCALHOST_ONLY') != '1' or
            not 0 <= domain <= 232 or domain in (211, 219)):
        parser.error('请使用隔离 ROS 域并设置 ROS_LOCALHOST_ONLY=1')
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    out = args.output_dir or ROOT / 'docs/experiments/phase2_5/clean_tour' / stamp
    out.mkdir(parents=True, exist_ok=False)
    record_file = out / 'experiment_data.csv'
    rclpy.init(args=None)
    node = TourEvidence()
    scenario_process = None
    scenario_log = None
    scenario_truth = out / 'scenario' / 'truth.json'
    recorder = subprocess.Popen([
        sys.executable, str(ROOT / 'scripts/record_phase2_topics.py'),
        '--duration-sec', str(min(args.timeout_sec + 60.0, 3600.0)), '--hz', '10',
        '--experiment-id', args.experiment_id, '--output', str(record_file),
    ], cwd=ROOT)
    started_utc = datetime.now(timezone.utc).isoformat()
    result = {'experiment_id': args.experiment_id, 'started_utc': started_utc,
              'domain_id': domain, 'status': 'RUNNING', 'expected_route': EXPECTED_ROUTE,
              'safety_pause_timeout_budget_sec': pause_timeout_sec,
              'operator_consent': 'test harness called accept after WAITING_CONSENT',
              'speech_mode': 'Mock Speak Action; successful action is not real audio'}
    error = None
    try:
        spin_until(node, lambda: node.visitor.get('source') == 'camera' and
                   node.visitor.get('valid') is True and
                   node.visitor.get('stable') is True and
                   node.visitor.get('stable_fresh') is True and
                   isinstance(node.visitor.get('people_count'), int) and
                   node.visitor['people_count'] >= 1,
                   args.visitor_timeout_sec, '相机稳定检测到至少一位参观者')
        result['visitor_gate'] = dict(node.visitor)
        start_ready_since = [None]

        def manager_ready_to_start():
            ready = (node.tour.get('connected') is True and
                     node.tour.get('is_moving') is False)
            if not ready:
                start_ready_since[0] = None
                return False
            start_ready_since[0] = start_ready_since[0] or time.monotonic()
            return time.monotonic() - start_ready_since[0] >= 0.5

        spin_until(node, manager_ready_to_start, 30,
                   '导览管理器已连接且机器人保持静止')
        result['manager_start_gate'] = {
            'connected': node.tour.get('connected'),
            'is_moving': node.tour.get('is_moving'),
            'current_location': node.tour.get('current_location'),
            'stable_sec': round(time.monotonic() - start_ready_since[0], 3),
        }
        result['start_service'] = trigger(node, node.trigger_clients['start'], 'start')
        spin_until(node, lambda: node.tour.get('state') == 'WAITING_CONSENT', 30,
                   '进入等待游客同意状态')
        if args.dynamic_scenario != 'none':
            scenario_truth.parent.mkdir(parents=True, exist_ok=True)
            scenario_log = (out / 'scenario' / 'scenario.log').open('w', encoding='utf-8')
            scenario_ready = out / 'scenario' / 'ready'
            scenario_command = [
                sys.executable, str(ROOT / 'scripts/spawn_people_scenario.py'),
                '--scenario', args.dynamic_scenario,
                '--wait-for-navigation-target', args.scenario_target,
                '--navigation-timeout-sec', str(args.timeout_sec),
                '--ready-file', str(scenario_ready),
                '--speed-mps', str(args.person_speed_mps), '--start-delay-sec', '0',
                '--target-distance-m', str(args.scenario_end_distance_m),
                '--hold-at-target-sec', str(args.hold_at_target_sec),
                '--leave-distance-m', str(args.leave_distance_m),
                '--leave-direction', args.leave_direction,
                '--hold-clear-sec', str(args.hold_clear_sec),
                '--truth-output', str(scenario_truth),
            ]
            if args.continue_after_robot_stop:
                scenario_command.append('--continue-after-robot-stop')
                if args.leave_after_hold:
                    scenario_command.append('--leave-after-hold')
            else:
                scenario_command.append('--remove-after')
            if args.dynamic_scenario == 'approaching' and not args.continue_after_robot_stop:
                scenario_command.append('--stop-on-safety-stop')
            scenario_process = subprocess.Popen(
                scenario_command, cwd=ROOT, stdout=scenario_log, stderr=subprocess.STDOUT)
            result['dynamic_scenario'] = {
                'scenario': args.dynamic_scenario, 'target': args.scenario_target,
                'person_speed_mps': args.person_speed_mps,
                'end_distance_m': args.scenario_end_distance_m,
                'leave_direction': args.leave_direction,
                'truth_output': str(scenario_truth),
                'trigger': 'child ready before consent; matching navigation UUID/target plus fresh moving odom',
            }
            spin_until(node, lambda: scenario_ready.is_file() or
                       scenario_process.poll() is not None,
                       min(15.0, args.timeout_sec), '动态人物进程已准备好监听导航')
            if scenario_process.poll() is not None:
                log = (out / 'scenario' / 'scenario.log').read_text(encoding='utf-8')
                raise RuntimeError(f'动态人物进程未能准备就绪：{log[-1500:]}')
        result['consent_service'] = trigger(node, node.trigger_clients['accept'], 'accept')
        asked = False
        paused_since = None
        deadline = time.monotonic() + args.timeout_sec
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            if scenario_process is not None and scenario_process.poll() not in (None, 0):
                log = (out / 'scenario' / 'scenario.log').read_text(encoding='utf-8')
                raise RuntimeError(f'动态人物场景失败，退出码 {scenario_process.returncode}: {log[-1500:]}')
            if (not asked and node.tour.get('state') == 'QA' and
                    node.tour.get('qa_waiting') is True):
                if not node.question.wait_for_service(timeout_sec=5.0):
                    raise RuntimeError('heritage/tour/ask 服务不可用')
                request = SubmitQuestion.Request(question=args.question,
                                                 exhibit=args.exhibit, level='basic')
                future = node.question.call_async(request)
                rclpy.spin_until_future_complete(node, future, timeout_sec=8.0)
                if not future.done() or future.exception() or not future.result().accepted:
                    raise RuntimeError('互动区问答服务未接受验收问题')
                result['question'] = {'question': args.question, 'exhibit': args.exhibit,
                                      'accepted': True}
                asked = True
            if node.tour.get('state') == 'COMPLETED':
                break
            if node.tour.get('state') == 'PAUSED':
                paused_since = paused_since or time.monotonic()
                if time.monotonic() - paused_since > pause_timeout_sec:
                    raise RuntimeError(f"安全暂停后未自动恢复：{node.tour.get('reason')}")
            else:
                paused_since = None
            if (node.tour.get('state') == 'ERROR' or
                    (node.tour.get('state') == 'IDLE' and
                     node.tour.get('outcome') not in ('running', 'idle'))):
                raise RuntimeError(f"导览进入异常状态：{node.tour.get('state')} / {node.tour.get('reason')}")
        else:
            raise TimeoutError('完整导览未在总时限内结束')
        final = dict(node.tour)
        if scenario_process is not None:
            try:
                scenario_exit = scenario_process.wait(timeout=30.0)
            except subprocess.TimeoutExpired as exc:
                scenario_process.send_signal(signal.SIGINT)
                scenario_process.wait(timeout=10.0)
                raise TimeoutError('动态人物场景在导览结束后仍未完成') from exc
            if scenario_truth.is_file():
                result['dynamic_scenario']['truth'] = json.loads(scenario_truth.read_text(encoding='utf-8'))
            if scenario_exit != 0 or result['dynamic_scenario'].get('truth', {}).get('status') != 'PASS':
                raise RuntimeError('动态人物模型/位姿回读未得到 PASS 真值记录')
            result['dynamic_scenario']['response_evidence'] = (
                validate_dynamic_scenario_evidence(
                    result['dynamic_scenario']['truth'], node.perception_events,
                    node.speed_events, node.navigation))
            if args.dynamic_scenario == 'leaving' or args.leave_after_hold:
                result['dynamic_scenario']['recovery_evidence'] = (
                    validate_leaving_recovery_evidence(
                        result['dynamic_scenario']['truth'], node.speed_events,
                        node.stops, node.navigation, node.perception_events))
        result.update({'final_status': final, 'actual_route': final.get('visited', []),
                       'qa_result': final.get('qa_result'),
                       'navigation_events': node.navigation,
                       'stop_status_events': node.stops,
                       'speed_controller_events': node.speed_events,
                       'perception_events': node.perception_events,
                       'gazebo_robot_last_pose': node.gazebo,
                       'odom_samples': len(node.odom),
                       'experiment_csv': str(record_file)})
        completed_ids = {}
        for event in node.navigation:
            if event['task_id']:
                task = completed_ids.setdefault(event['task_id'], {
                    'target': event['target'], 'statuses': [],
                    'started_at_monotonic_sec': None,
                    'completed_at_monotonic_sec': None,
                    'position_error_m': None,
                })
                task['statuses'].append(event['status'])
                stamp = event['time_monotonic_sec']
                if event['status'] == 'start' and task['started_at_monotonic_sec'] is None:
                    task['started_at_monotonic_sec'] = stamp
                if event['status'] == 'complete':
                    task['completed_at_monotonic_sec'] = stamp
                    task['position_error_m'] = event.get('position_error_m')
        for task in completed_ids.values():
            started_at = task['started_at_monotonic_sec']
            completed_at = task['completed_at_monotonic_sec']
            task['elapsed_sec'] = (round(completed_at - started_at, 3)
                                   if started_at is not None and completed_at is not None
                                   else None)
        arrival_evidence = []
        for task_id, task in completed_ids.items():
            completes = [event for event in node.navigation
                         if event['task_id'] == task_id and event['status'] == 'complete']
            if completes:
                completed_at = completes[-1]['time_monotonic_sec']
                arrival_evidence.append({
                    'task_id': task_id, 'target': task['target'],
                    'elapsed_sec': completed_ids[task_id]['elapsed_sec'],
                    'position_error_m': completed_ids[task_id]['position_error_m'],
                    'arrival_stop_confirmed_by_nav2_transport_contract': True,
                    'stationary_window_sec_before_complete': round(
                        node.stationary_duration_at(completed_at), 3),
                })
        result['navigation_tasks'] = completed_ids
        result['arrival_stop_evidence'] = arrival_evidence
        qa = final.get('qa_result') or {}
        if final.get('outcome') != 'completed' or final.get('error_count') != 0:
            raise AssertionError('导览终态或 error_count 不符合验收')
        if final.get('visited') != EXPECTED_ROUTE:
            raise AssertionError('实际五区路线与验收顺序不一致')
        if (not asked or qa.get('found') is not True or qa.get('spoken') is not True or
                '广场乐' not in qa.get('answer', '')):
            raise AssertionError('问答未命中知识库或模拟播报 Action 未成功')
        if len([event for event in node.navigation if event['status'] == 'complete']) != len(EXPECTED_ROUTE):
            raise AssertionError('导航成功终态数量与路线站点数量不一致')
        if any(item['target'] != 'wait' and
               item['stationary_window_sec_before_complete'] < 0.45
               for item in arrival_evidence):
            raise AssertionError('存在展区或出口导航完成时未能从里程计观察到停车窗口的站点')
        response_status = (result.get('dynamic_scenario', {}).get('response_evidence', {})
                           .get('status'))
        recovery_status = (result.get('dynamic_scenario', {}).get('recovery_evidence', {})
                           .get('status'))
        result['status'] = ('PASS_WITH_RISK'
                            if 'PASS_WITH_RISK' in (response_status, recovery_status)
                            else 'PASS')
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        result['status'] = 'FAIL'
        result['error'] = error
        try:
            if node.tour.get('state') not in ('IDLE', 'COMPLETED', 'ERROR'):
                trigger(node, node.trigger_clients['cancel'], 'cancel')
        except Exception:
            pass
    finally:
        result.update({
            'ended_utc': datetime.now(timezone.utc).isoformat(),
            'tour_events': node.events, 'navigation_events': node.navigation,
            'stop_status_events': node.stops, 'odom_samples': len(node.odom),
            'speed_controller_events': node.speed_events,
            'perception_events': node.perception_events,
            'gazebo_robot_last_pose': node.gazebo,
        })
        if scenario_process is not None and scenario_process.poll() is None:
            scenario_process.send_signal(signal.SIGINT)
            try:
                scenario_process.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                scenario_process.kill()
                scenario_process.wait(timeout=3.0)
        if scenario_process is not None and args.retain_scenario_model:
            cleanup_output = out / 'scenario' / 'cleanup.json'
            try:
                cleanup = subprocess.run(
                    [sys.executable, str(ROOT / 'scripts/spawn_people_scenario.py'),
                     '--cleanup-only', '--truth-output', str(cleanup_output)],
                    cwd=ROOT, capture_output=True, text=True, timeout=25.0)
                result.setdefault('dynamic_scenario', {})['cleanup'] = {
                    'exit_code': cleanup.returncode,
                    'truth_output': str(cleanup_output),
                    'stdout': cleanup.stdout[-2000:], 'stderr': cleanup.stderr[-2000:],
                }
                if cleanup_output.is_file():
                    result['dynamic_scenario']['cleanup']['truth'] = json.loads(
                        cleanup_output.read_text(encoding='utf-8'))
            except Exception as cleanup_error:
                result.setdefault('dynamic_scenario', {})['cleanup'] = {
                    'error': f'{type(cleanup_error).__name__}: {cleanup_error}',
                    'truth_output': str(cleanup_output),
                }
        if scenario_log is not None:
            scenario_log.close()
        write_json(out / 'report.json', result)
        write_json(out / 'events.json', {
            'tour': node.events, 'navigation': node.navigation,
            'safety_stop': node.stops, 'speed_control': node.speed_events,
            'perception': node.perception_events,
            'gazebo_robot_last_pose': node.gazebo,
        })
        node.destroy_node()
        rclpy.try_shutdown()
        if recorder.poll() is None:
            recorder.send_signal(signal.SIGINT)
            try:
                recorder.wait(timeout=10)
            except subprocess.TimeoutExpired:
                recorder.kill()
                recorder.wait()
    print(json.dumps({'status': result['status'], 'report': str(out / 'report.json'),
                      'error': error}, ensure_ascii=False))
    return 0 if result['status'] in ('PASS', 'PASS_WITH_RISK') else 1


if __name__ == '__main__':
    raise SystemExit(main())
