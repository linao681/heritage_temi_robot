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
                           'qa_waiting')) + (tuple(current.get('visited', [])),
                                             json.dumps(current.get('qa_result'), sort_keys=True))
        if signature != self._last_tour_signature:
            self.events.append({
                'time_monotonic_sec': self._timestamp(), 'kind': 'tour_status',
                'state': current.get('state'), 'reason': current.get('reason'),
                'outcome': current.get('outcome'), 'route_index': current.get('route_index'),
                'target': current.get('target'), 'visited': current.get('visited', []),
                'qa_waiting': current.get('qa_waiting'), 'qa_result': current.get('qa_result'),
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
                'person_observation_state': message.person_observation_state,
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment-id', default='E01')
    parser.add_argument('--timeout-sec', type=float, default=1200.0)
    parser.add_argument('--visitor-timeout-sec', type=float, default=90.0)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--question', default='潮州音乐有哪些类型？')
    parser.add_argument('--exhibit', default='exhibit_05')
    args = parser.parse_args()
    if (not math.isfinite(args.timeout_sec) or args.timeout_sec <= 0 or
            not math.isfinite(args.visitor_timeout_sec) or args.visitor_timeout_sec <= 0):
        parser.error('timeout 参数必须是有限正数')
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
    recorder = subprocess.Popen([
        sys.executable, str(ROOT / 'scripts/record_phase2_topics.py'),
        '--duration-sec', str(min(args.timeout_sec + 60.0, 3600.0)), '--hz', '10',
        '--experiment-id', args.experiment_id, '--output', str(record_file),
    ], cwd=ROOT)
    started_utc = datetime.now(timezone.utc).isoformat()
    result = {'experiment_id': args.experiment_id, 'started_utc': started_utc,
              'domain_id': domain, 'status': 'RUNNING', 'expected_route': EXPECTED_ROUTE,
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
        warmup_end = time.monotonic() + 1.0
        while rclpy.ok() and time.monotonic() < warmup_end:
            rclpy.spin_once(node, timeout_sec=0.05)
        result['telemetry_subscription_warmup_sec'] = 1.0
        result['start_service'] = trigger(node, node.trigger_clients['start'], 'start')
        spin_until(node, lambda: node.tour.get('state') == 'WAITING_CONSENT', 30,
                   '进入等待游客同意状态')
        result['consent_service'] = trigger(node, node.trigger_clients['accept'], 'accept')
        asked = False
        paused_since = None
        deadline = time.monotonic() + args.timeout_sec
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
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
                if time.monotonic() - paused_since > 30.0:
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
        result['status'] = 'PASS'
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
        write_json(out / 'report.json', result)
        write_json(out / 'events.json', {
            'tour': node.events, 'navigation': node.navigation,
            'safety_stop': node.stops, 'speed_control': node.speed_events,
            'perception': node.perception_events,
            'gazebo_robot_last_pose': node.gazebo,
        })
        node.destroy_node()
        rclpy.shutdown()
        if recorder.poll() is None:
            recorder.send_signal(signal.SIGINT)
            try:
                recorder.wait(timeout=10)
            except subprocess.TimeoutExpired:
                recorder.kill()
                recorder.wait()
    print(json.dumps({'status': result['status'], 'report': str(out / 'report.json'),
                      'error': error}, ensure_ascii=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
