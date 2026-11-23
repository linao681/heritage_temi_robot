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
from rcl_interfaces.msg import ParameterType
from rcl_interfaces.srv import GetParameters
from rclpy.duration import Duration
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.time import Time
from gazebo_msgs.msg import ModelStates
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String
from temi_interfaces.msg import NavigationStatus, PerceptionInput, PersonDetectionArray
from tf2_ros import Buffer, TransformException, TransformListener

ROOT = Path(__file__).resolve().parents[1]
FIELDS = [
    'time_utc', 'received_wall_utc', 'time_monotonic_sec', 'received_monotonic_ns',
    'ros_stamp_ns', 'ros_time_valid', 'experiment_id', 'navigation_session_id',
    'robot_pose_map_x_m', 'robot_pose_map_y_m', 'robot_pose_map_yaw_rad',
    'robot_pose_map_frame_id', 'robot_pose_map_stamp_ns',
    'robot_pose_map_age_sec', 'robot_pose_map_valid',
    'speed_limit_controller_max_vel_x_mps', 'speed_limit_controller_max_speed_xy_mps',
    'speed_limit_smoother_max_velocity_x_mps', 'speed_limit_sample_age_sec',
    'speed_limit_valid',
    'navigation_task_id', 'navigation_target', 'navigation_status',
    'tour_state', 'speed_controller_state', 'target_speed_mps',
    'dynamic_stop_distance_m', 'approach_speed_mps',
    'current_robot_speed_mps', 'current_robot_speed_source',
    'cmd_vel_nav_linear_x', 'cmd_vel_linear_x', 'odom_linear_x', 'odom_angular_z',
    'cmd_vel_nav_sample_age_sec', 'cmd_vel_nav_sample_valid',
    'cmd_vel_sample_age_sec', 'cmd_vel_sample_valid',
    'odom_header_stamp_ns', 'odom_message_age_sec',
    'odom_sample_age_sec', 'odom_sample_valid',
    'people_count', 'raw_person_observation_state', 'visitor_count',
    'visitor_count_valid', 'person_observation_state',
    'person_observation_valid', 'person_distance_valid', 'speed_input_valid',
    'nearest_person_m',
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
SPEED_LIMIT_MAX_AGE_SEC = 1.5
TOPIC_SAMPLE_MAX_AGE_SEC = 0.2


def topic_sample_metadata(received_at, now, *values):
    if (not isinstance(received_at, (int, float)) or
            not isinstance(now, (int, float)) or
            not math.isfinite(received_at) or not math.isfinite(now)):
        return None, False
    age = now - received_at
    valid_values = all(isinstance(value, (int, float)) and math.isfinite(value)
                       for value in values)
    valid = (0.0 <= age <= TOPIC_SAMPLE_MAX_AGE_SEC and bool(values) and valid_values)
    return round(age, 6), valid


def odom_sample_metadata(received_at, wall_now, header_stamp_ns, ros_now_ns, *values):
    received_age, received_valid = topic_sample_metadata(
        received_at, wall_now, *values)
    if (not isinstance(header_stamp_ns, int) or not isinstance(ros_now_ns, int) or
            header_stamp_ns <= 0 or ros_now_ns <= 0):
        return received_age, None, False
    source_age = (ros_now_ns - header_stamp_ns) / 1_000_000_000
    source_valid = 0.0 <= source_age <= TOPIC_SAMPLE_MAX_AGE_SEC
    return received_age, round(source_age, 6), received_valid and source_valid


def normalize_nav2_speed_limits(controller_values, smoother_values, sample_age_sec):
    age_valid = (
        isinstance(sample_age_sec, (int, float)) and math.isfinite(sample_age_sec) and
        0.0 <= sample_age_sec <= SPEED_LIMIT_MAX_AGE_SEC)
    controller_valid = (
        isinstance(controller_values, (tuple, list)) and len(controller_values) == 2 and
        all(isinstance(value, (int, float)) and math.isfinite(value) and value > 0
            for value in controller_values))
    smoother_valid = (
        isinstance(smoother_values, (tuple, list)) and len(smoother_values) >= 1 and
        isinstance(smoother_values[0], (int, float)) and
        math.isfinite(smoother_values[0]) and smoother_values[0] > 0)
    valid = age_valid and controller_valid and smoother_valid
    return {
        'speed_limit_controller_max_vel_x_mps': (
            float(controller_values[0]) if valid else None),
        'speed_limit_controller_max_speed_xy_mps': (
            float(controller_values[1]) if valid else None),
        'speed_limit_smoother_max_velocity_x_mps': (
            float(smoother_values[0]) if valid else None),
        'speed_limit_sample_age_sec': (
            float(sample_age_sec) if isinstance(sample_age_sec, (int, float)) and
            math.isfinite(sample_age_sec) and sample_age_sec >= 0 else None),
        'speed_limit_valid': bool(valid),
    }
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
        self._speed_limit_snapshot = normalize_nav2_speed_limits(None, None, None)
        self._speed_limit_received_at = 0.0
        self._speed_limit_request_started = 0.0
        self._speed_limit_request_sequence = 0
        self._speed_limit_request_inflight = False
        self._speed_limit_responses = {}
        self._controller_parameters = self.create_client(
            GetParameters, 'controller_server/get_parameters')
        self._smoother_parameters = self.create_client(
            GetParameters, 'velocity_smoother/get_parameters')
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
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
        self.create_timer(1.0, self._request_nav2_speed_limits)

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
                'dynamic_stop_distance_m': value.get('dynamic_stop_distance_m'),
                'approach_speed_mps': value.get('approach_speed_mps'),
                'current_robot_speed_mps': value.get('current_robot_speed_mps'),
                'current_robot_speed_source': value.get('current_robot_speed_source'),
                'speed_input_valid': value.get('input_valid'),
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
            'visitor_count': message.people_count,
            'visitor_count_valid': bool(message.people_valid),
            'person_observation_state': message.person_observation_state,
            'person_observation_valid': bool(message.person_observation_valid),
            'person_distance_valid': bool(message.person_distance_valid),
            'nearest_person_m': message.nearest_person_m if message.person_distance_valid else None,
            'obstacle_distance_m': message.obstacle_distance_m if message.obstacle_distance_valid else None,
            'perception_age_sec': float(message.sample_age_sec),
            'fusion_valid': bool(message.valid),
            'perception_error': message.error,
        })

    def _people(self, message):
        self._set('people', {
            'people_count': message.people_count,
            'raw_person_observation_state': message.observation_state,
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
        stamp = message.header.stamp.sec * 1_000_000_000 + message.header.stamp.nanosec
        self._set('odom', {'odom_linear_x': twist.linear.x, 'odom_angular_z': twist.angular.z,
                           'odom_header_stamp_ns': stamp})

    @staticmethod
    def _csv_value(value):
        if value is None:
            return ''
        if isinstance(value, bool):
            return str(value).lower()
        return value

    @staticmethod
    def _parameter_values(response, kind):
        values = getattr(response, 'values', None)
        if not isinstance(values, (list, tuple)):
            return None
        if kind == 'controller':
            if len(values) != 2 or any(
                    item.type != ParameterType.PARAMETER_DOUBLE for item in values):
                return None
            return tuple(float(item.double_value) for item in values)
        if kind == 'smoother':
            if len(values) != 1 or values[0].type != ParameterType.PARAMETER_DOUBLE_ARRAY:
                return None
            return tuple(float(item) for item in values[0].double_array_value)
        return None

    def _request_nav2_speed_limits(self):
        now = time.monotonic()
        with self._mutex:
            if self._speed_limit_request_inflight:
                if now - self._speed_limit_request_started <= 2.0:
                    return
                self._speed_limit_request_sequence += 1
                self._speed_limit_request_inflight = False
                self._speed_limit_snapshot = normalize_nav2_speed_limits(
                    None, None, now - self._speed_limit_received_at
                    if self._speed_limit_received_at else None)
            if (not self._controller_parameters.service_is_ready() or
                    not self._smoother_parameters.service_is_ready()):
                return
            self._speed_limit_request_sequence += 1
            sequence = self._speed_limit_request_sequence
            self._speed_limit_request_started = now
            self._speed_limit_request_inflight = True
            self._speed_limit_responses = {}
        try:
            controller_future = self._controller_parameters.call_async(
                GetParameters.Request(names=['FollowPath.max_vel_x', 'FollowPath.max_speed_xy']))
            smoother_future = self._smoother_parameters.call_async(
                GetParameters.Request(names=['max_velocity']))
            controller_future.add_done_callback(
                lambda future: self._collect_nav2_speed_limits(sequence, 'controller', future))
            smoother_future.add_done_callback(
                lambda future: self._collect_nav2_speed_limits(sequence, 'smoother', future))
        except Exception:
            self._collect_nav2_speed_limits(sequence, 'controller', None)
            self._collect_nav2_speed_limits(sequence, 'smoother', None)

    def _collect_nav2_speed_limits(self, sequence, kind, future):
        try:
            response = future.result() if future is not None else None
            parsed = self._parameter_values(response, kind) if response is not None else None
        except Exception:
            parsed = None
        now = time.monotonic()
        with self._mutex:
            if (sequence != self._speed_limit_request_sequence or
                    not self._speed_limit_request_inflight):
                return
            self._speed_limit_responses[kind] = parsed
            if len(self._speed_limit_responses) < 2:
                return
            self._speed_limit_snapshot = normalize_nav2_speed_limits(
                self._speed_limit_responses.get('controller'),
                self._speed_limit_responses.get('smoother'),
                now - self._speed_limit_request_started)
            self._speed_limit_received_at = now
            self._speed_limit_request_inflight = False

    def _map_pose_snapshot(self, ros_now_ns):
        try:
            transform = self._tf_buffer.lookup_transform(
                'map', 'base_link', Time(), timeout=Duration(seconds=0.0))
        except TransformException:
            return {
                'robot_pose_map_x_m': None, 'robot_pose_map_y_m': None,
                'robot_pose_map_yaw_rad': None, 'robot_pose_map_frame_id': 'map',
                'robot_pose_map_stamp_ns': None, 'robot_pose_map_age_sec': None,
                'robot_pose_map_valid': False,
            }
        translation = transform.transform.translation
        rotation = transform.transform.rotation
        values = (translation.x, translation.y, rotation.x, rotation.y, rotation.z, rotation.w)
        if not all(math.isfinite(value) for value in values):
            return {
                'robot_pose_map_x_m': None, 'robot_pose_map_y_m': None,
                'robot_pose_map_yaw_rad': None, 'robot_pose_map_frame_id': 'map',
                'robot_pose_map_stamp_ns': None, 'robot_pose_map_age_sec': None,
                'robot_pose_map_valid': False,
            }
        stamp = transform.header.stamp.sec * 1_000_000_000 + transform.header.stamp.nanosec
        age_sec = (ros_now_ns - stamp) / 1_000_000_000 if ros_now_ns > 0 and stamp > 0 else None
        valid = (transform.header.frame_id == 'map' and age_sec is not None and
                 0.0 <= age_sec <= 0.5)
        if not valid:
            return {
                'robot_pose_map_x_m': None, 'robot_pose_map_y_m': None,
                'robot_pose_map_yaw_rad': None,
                'robot_pose_map_frame_id': transform.header.frame_id,
                'robot_pose_map_stamp_ns': stamp, 'robot_pose_map_age_sec': age_sec,
                'robot_pose_map_valid': False,
            }
        yaw = math.atan2(
            2.0 * (rotation.w * rotation.z + rotation.x * rotation.y),
            1.0 - 2.0 * (rotation.y * rotation.y + rotation.z * rotation.z))
        return {
            'robot_pose_map_x_m': float(translation.x),
            'robot_pose_map_y_m': float(translation.y),
            'robot_pose_map_yaw_rad': float(yaw),
            'robot_pose_map_frame_id': transform.header.frame_id,
            'robot_pose_map_stamp_ns': stamp,
            'robot_pose_map_age_sec': age_sec,
            'robot_pose_map_valid': True,
        }

    def _record(self):
        now = time.monotonic()
        ros_stamp_ns = self.get_clock().now().nanoseconds
        with self._mutex:
            values = dict(self._values)
            command = dict(self._last_command)
            truth = dict(self._ground_truth)
            truth_received_at = self._ground_truth_received_at
            limits = dict(self._speed_limit_snapshot)
            limits_received_at = self._speed_limit_received_at
        limit_age = now - limits_received_at if limits_received_at else None
        limits = normalize_nav2_speed_limits(
            (limits.get('speed_limit_controller_max_vel_x_mps'),
             limits.get('speed_limit_controller_max_speed_xy_mps')),
            (limits.get('speed_limit_smoother_max_velocity_x_mps'),),
            limit_age)
        row = {key: values.get(key) for key in FIELDS}
        sample_specs = (
            ('cmd_nav', 'cmd_vel_nav_sample_age_sec', 'cmd_vel_nav_sample_valid',
             ('cmd_vel_nav_linear_x',)),
            ('cmd', 'cmd_vel_sample_age_sec', 'cmd_vel_sample_valid',
             ('cmd_vel_linear_x',)),
        )
        for source, age_field, valid_field, numeric_fields in sample_specs:
            age, sample_valid = topic_sample_metadata(
                values.get(source + '_received_at'), now,
                *(values.get(field) for field in numeric_fields))
            row[age_field] = age
            row[valid_field] = sample_valid
        odom_received_age, odom_message_age, odom_valid = odom_sample_metadata(
            values.get('odom_received_at'), now, values.get('odom_header_stamp_ns'),
            ros_stamp_ns, values.get('odom_linear_x'), values.get('odom_angular_z'))
        row['odom_sample_age_sec'] = odom_received_age
        row['odom_message_age_sec'] = odom_message_age
        row['odom_sample_valid'] = odom_valid
        row.update(limits)
        row.update(self._map_pose_snapshot(ros_stamp_ns))
        row.update(command)
        truth_age = now - truth_received_at
        row.update(truth if truth_age <= 0.5 else {})
        row['gazebo_ground_truth_sample_age_sec'] = (
            truth_age if truth and truth_age <= 0.5 else None)
        wall_utc = datetime.now(timezone.utc).isoformat()
        row.update({
            'time_utc': wall_utc,
            'received_wall_utc': wall_utc,
            'time_monotonic_sec': f'{now:.6f}',
            'received_monotonic_ns': int(now * 1_000_000_000),
            'ros_stamp_ns': ros_stamp_ns,
            'ros_time_valid': ros_stamp_ns > 0,
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
