"""Record live ROS2 phase 2 sensing, speed commands and Gazebo feedback to CSV."""
import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from threading import Lock, Thread
import time

import rclpy
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from gazebo_msgs.msg import ModelStates
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String
from temi_interfaces.msg import NavigationStatus, PerceptionInput, PersonDetectionArray

ROOT = Path(__file__).resolve().parents[1]
FIELDS = [
    'time_utc', 'time_monotonic_sec', 'experiment_id', 'navigation_session_id',
    'navigation_task_id', 'navigation_target', 'navigation_status',
    'tour_state', 'speed_controller_state', 'target_speed_mps',
    'cmd_vel_nav_linear_x', 'cmd_vel_linear_x', 'odom_linear_x', 'odom_angular_z',
    'people_count', 'person_observation_state', 'nearest_person_m',
    'obstacle_distance_m', 'vision_inference_age_sec', 'perception_age_sec',
    'fusion_valid', 'perception_error',
    'stop_requested', 'stop_confirmed', 'control_reason',
    'recovery_requested',
    'last_speed_command_status', 'last_speed_command_target_mps',
    'last_speed_command_message', 'last_speed_command_sdk_return_code',
    'last_speed_command_id', 'last_speed_command_navigation_session_id',
    'detection_confidences_json', 'actual_speed_source',
    'gazebo_ground_truth_person_name', 'gazebo_ground_truth_robot_x',
    'gazebo_ground_truth_robot_y', 'gazebo_ground_truth_person_x',
    'gazebo_ground_truth_person_y', 'gazebo_ground_truth_person_count',
    'gazebo_ground_truth_person_fov_count',
    'gazebo_ground_truth_center_distance_m',
    'gazebo_ground_truth_distance_m', 'gazebo_ground_truth_robot_yaw',
    'gazebo_ground_truth_nearest_camera_z_m',
    'gazebo_ground_truth_fov_nearest_camera_z_m',
    'gazebo_ground_truth_sample_age_sec',
]
PERSON_PREFIXES = ('phase25_person_', 'phase2_person_')
ROBOT_RADIUS_M = 0.34
PERSON_HALF_LENGTH_M = 0.14
PERSON_HALF_WIDTH_M = 0.39
CAMERA_FORWARD_OFFSET_M = 0.17
CAMERA_HORIZONTAL_FOV_RAD = math.pi / 3.0
CAMERA_FAR_M = 8.0


def _yaw(pose):
    q = pose.orientation
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def ground_truth_nearest_person(names, poses):
    """Return world-model truth using the base and mannequin collision envelopes."""
    models = dict(zip(names, poses))
    robot = models.get('heritage_robot')
    if robot is None:
        return {}
    robot_x, robot_y = robot.position.x, robot.position.y
    if not all(math.isfinite(value) for value in (robot_x, robot_y)):
        return {}
    robot_yaw = _yaw(robot)
    candidates = [(name, pose) for name, pose in models.items()
                  if name.startswith(PERSON_PREFIXES)]
    result = {
        'gazebo_ground_truth_robot_x': robot_x,
        'gazebo_ground_truth_robot_y': robot_y,
        'gazebo_ground_truth_robot_yaw': robot_yaw,
        'gazebo_ground_truth_person_count': len(candidates),
    }
    nearest = None
    fov_camera_z = []
    for name, person in candidates:
        person_x, person_y = person.position.x, person.position.y
        if not all(math.isfinite(value) for value in (person_x, person_y)):
            continue
        dx, dy = person_x - robot_x, person_y - robot_y
        center_distance = math.hypot(dx, dy)
        relative_robot_bearing = math.atan2(dy, dx) - robot_yaw
        relative_robot_bearing = math.atan2(math.sin(relative_robot_bearing),
                                            math.cos(relative_robot_bearing))
        camera_z = (dx * math.cos(robot_yaw) + dy * math.sin(robot_yaw) -
                    CAMERA_FORWARD_OFFSET_M)
        if (0.2 <= camera_z <= CAMERA_FAR_M and
                abs(relative_robot_bearing) <= CAMERA_HORIZONTAL_FOV_RAD / 2.0):
            fov_camera_z.append(camera_z)
        relative_bearing = math.atan2(dy, dx) - _yaw(person)
        person_support = (
            PERSON_HALF_LENGTH_M * abs(math.cos(relative_bearing)) +
            PERSON_HALF_WIDTH_M * abs(math.sin(relative_bearing)))
        surface_clearance = max(0.0, center_distance - ROBOT_RADIUS_M - person_support)
        candidate = (surface_clearance, name, center_distance, person_x, person_y)
        if nearest is None or candidate[0] < nearest[0]:
            nearest = candidate
    if nearest is None:
        result['gazebo_ground_truth_person_fov_count'] = len(fov_camera_z)
        if fov_camera_z:
            result['gazebo_ground_truth_fov_nearest_camera_z_m'] = min(fov_camera_z)
        return result
    clearance, name, center_distance, person_x, person_y = nearest
    result.update({
        'gazebo_ground_truth_person_name': name,
        'gazebo_ground_truth_person_x': person_x,
        'gazebo_ground_truth_person_y': person_y,
        'gazebo_ground_truth_center_distance_m': center_distance,
        'gazebo_ground_truth_distance_m': clearance,
        'gazebo_ground_truth_person_fov_count': len(fov_camera_z),
        'gazebo_ground_truth_nearest_camera_z_m': (
            (person_x - robot_x) * math.cos(robot_yaw) +
            (person_y - robot_y) * math.sin(robot_yaw) -
            CAMERA_FORWARD_OFFSET_M),
    })
    if fov_camera_z:
        result['gazebo_ground_truth_fov_nearest_camera_z_m'] = min(fov_camera_z)
    return result


class Phase2Recorder(Node):
    def __init__(self, output, experiment_id, hz):
        super().__init__('phase2_topic_recorder')
        self._output = output
        self._experiment_id = experiment_id
        self._file = output.open('w', newline='', encoding='utf-8')
        self._writer = csv.DictWriter(self._file, fieldnames=FIELDS)
        self._writer.writeheader()
        self._values = {}
        self._last_command = {}
        self._ground_truth = {}
        self._ground_truth_received_at = 0.0
        self._mutex = Lock()
        self._rows = 0
        self.create_subscription(String, 'heritage/tour/status', self._tour, 10)
        self.create_subscription(String, 'heritage/speed_control/status', self._speed, 10)
        self.create_subscription(String, 'heritage/speed_control/commands', self._command, 10)
        self.create_subscription(NavigationStatus, 'temi/navigation_status',
                                 self._navigation, 10)
        self.create_subscription(PerceptionInput, 'heritage/perception/fused', self._perception, 10)
        self.create_subscription(PersonDetectionArray, 'heritage/visitor/person_detections/raw',
                                 self._raw_people, 10)
        self.create_subscription(PersonDetectionArray, 'heritage/visitor/person_detections', self._people, 10)
        self.create_subscription(Twist, 'cmd_vel_nav', self._cmd_nav, 10)
        self.create_subscription(Twist, 'cmd_vel', self._cmd, 10)
        self.create_subscription(Odometry, 'odom', self._odom, 10)
        self.create_subscription(ModelStates, '/gazebo/model_states',
                                 self._on_model_states, 10)
        self.create_timer(1.0 / hz, self._record)

    def _set(self, source, values):
        with self._mutex:
            self._values.update(values)
            self._values[source + '_received_at'] = time.monotonic()

    def _tour(self, message):
        try:
            value = json.loads(message.data)
            self._set('tour', {'tour_state': value.get('state', '')})
        except (ValueError, TypeError):
            self._set('tour', {'tour_state': 'STATUS_PARSE_ERROR'})

    def _speed(self, message):
        try:
            value = json.loads(message.data)
            self._set('speed', {
                'speed_controller_state': value.get('state', ''),
                'target_speed_mps': value.get('target_speed_mps'),
                'stop_requested': value.get('stop_requested'),
                'stop_confirmed': value.get('stop_confirmed'),
                'recovery_requested': value.get('resume_requested'),
                'control_reason': value.get('reason', ''),
                'navigation_session_id': value.get('navigation_session_id', ''),
                'actual_speed_source': value.get('actual_speed_source'),
            })
        except (ValueError, TypeError):
            self._set('speed', {'speed_controller_state': 'STATUS_PARSE_ERROR'})

    def _navigation(self, message):
        self._set('navigation', {
            'navigation_task_id': message.task_id,
            'navigation_target': message.target,
            'navigation_status': message.status,
        })

    def _on_model_states(self, message):
        truth = ground_truth_nearest_person(message.name, message.pose)
        with self._mutex:
            self._ground_truth = truth
            self._ground_truth_received_at = time.monotonic()

    def _command(self, message):
        try:
            value = json.loads(message.data)
            command = {
                'last_speed_command_status': value.get('status', ''),
                'last_speed_command_target_mps': value.get('requested_target_speed_mps'),
                'last_speed_command_message': value.get('message', ''),
                'last_speed_command_sdk_return_code': value.get('sdk_return_code'),
                'last_speed_command_id': value.get('command_id', ''),
                'last_speed_command_navigation_session_id': value.get(
                    'navigation_session_id', ''),
            }
            with self._mutex:
                self._last_command = command
        except (ValueError, TypeError):
            with self._mutex:
                self._last_command = {'last_speed_command_status': 'STATUS_PARSE_ERROR'}

    def _perception(self, message):
        self._set('perception', {
            'navigation_session_id': message.navigation_session_id,
            'people_count': message.people_count,
            'person_observation_state': message.person_observation_state,
            'nearest_person_m': message.nearest_person_m if message.person_distance_valid else None,
            'obstacle_distance_m': message.obstacle_distance_m if message.obstacle_distance_valid else None,
            'perception_age_sec': float(message.sample_age_sec),
            'fusion_valid': bool(message.valid),
            'perception_error': message.error,
        })

    def _people(self, message):
        self._set('people', {
            'people_count': message.people_count,
            'person_observation_state': message.observation_state,
            'detection_confidences_json': json.dumps(
                [round(float(item.confidence), 6) for item in message.detections]),
        })

    def _raw_people(self, message):
        self._set('raw_people', {
            'vision_inference_age_sec': float(message.sample_age_sec),
            'detection_confidences_json': json.dumps(
                [round(float(item.confidence), 6) for item in message.detections]),
        })

    def _cmd_nav(self, message):
        self._set('cmd_nav', {'cmd_vel_nav_linear_x': message.linear.x})

    def _cmd(self, message):
        self._set('cmd', {'cmd_vel_linear_x': message.linear.x})

    def _odom(self, message):
        twist = message.twist.twist
        self._set('odom', {'odom_linear_x': twist.linear.x, 'odom_angular_z': twist.angular.z})

    @staticmethod
    def _csv_value(value):
        if value is None:
            return ''
        if isinstance(value, bool):
            return str(value).lower()
        return value

    def _record(self):
        now = time.monotonic()
        with self._mutex:
            values = dict(self._values)
            command = dict(self._last_command)
            truth = dict(self._ground_truth)
            truth_received_at = self._ground_truth_received_at
        row = {key: values.get(key) for key in FIELDS}
        row.update(command)
        truth_age = now - truth_received_at
        row.update(truth if truth_age <= 0.5 else {})
        row['gazebo_ground_truth_sample_age_sec'] = (
            truth_age if truth and truth_age <= 0.5 else None)
        row.update({
            'time_utc': datetime.now(timezone.utc).isoformat(),
            'time_monotonic_sec': f'{now:.6f}',
            'experiment_id': self._experiment_id,
        })
        for key in FIELDS:
            row[key] = self._csv_value(row.get(key))
        self._writer.writerow(row)
        self._file.flush()
        self._rows += 1

    def close(self):
        self._file.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration-sec', type=float, default=60.0)
    parser.add_argument('--hz', type=float, default=10.0)
    parser.add_argument('--experiment-id', default='phase2-live')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 0 < args.duration_sec <= 3600 or not 0 < args.hz <= 50:
        parser.error('duration must be 0..3600 sec and hz must be 0..50')
    stamp = time.strftime('%Y%m%d-%H%M%S')
    output = args.output or ROOT / 'docs/experiments/phase2' / f'run-{stamp}' / 'experiment_data.csv'
    output.parent.mkdir(parents=True, exist_ok=True)
    rclpy.init(args=None)
    node = Phase2Recorder(output, args.experiment_id, args.hz)
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    def spin_executor():
        try:
            executor.spin()
        except ExternalShutdownException:
            pass
    thread = Thread(target=spin_executor, daemon=True)
    thread.start()
    started_monotonic = time.monotonic()
    try:
        deadline = time.monotonic() + args.duration_sec
        while rclpy.ok() and time.monotonic() < deadline:
            time.sleep(min(0.05, 1.0 / args.hz))
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown(timeout_sec=5.0)
        thread.join(timeout=5.0)
        rows = node._rows
        elapsed = time.monotonic() - started_monotonic
        node.close()
        node.destroy_node()
        rclpy.try_shutdown()
    print(json.dumps({'output': str(output), 'rows': rows,
                      'duration_sec': round(elapsed, 3)}))


if __name__ == '__main__':
    main()
