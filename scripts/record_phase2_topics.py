"""Record live ROS2 phase 2 sensing, speed commands and Gazebo feedback to CSV."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String
from temi_interfaces.msg import PerceptionInput, PersonDetectionArray

ROOT = Path(__file__).resolve().parents[1]
FIELDS = [
    'time_utc', 'time_monotonic_sec', 'experiment_id', 'navigation_session_id',
    'tour_state', 'speed_controller_state', 'target_speed_mps',
    'cmd_vel_nav_linear_x', 'cmd_vel_linear_x', 'odom_linear_x', 'odom_angular_z',
    'people_count', 'person_observation_state', 'nearest_person_m',
    'obstacle_distance_m', 'vision_inference_age_sec', 'perception_age_sec',
    'fusion_valid', 'perception_error',
    'stop_requested', 'stop_confirmed', 'control_reason',
    'last_speed_command_status', 'last_speed_command_target_mps',
    'detection_confidences_json', 'actual_speed_source',
]


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
        self._rows = 0
        self.create_subscription(String, 'heritage/tour/status', self._tour, 10)
        self.create_subscription(String, 'heritage/speed_control/status', self._speed, 10)
        self.create_subscription(String, 'heritage/speed_control/commands', self._command, 10)
        self.create_subscription(PerceptionInput, 'heritage/perception/fused', self._perception, 10)
        self.create_subscription(PersonDetectionArray, 'heritage/visitor/person_detections/raw',
                                 self._raw_people, 10)
        self.create_subscription(PersonDetectionArray, 'heritage/visitor/person_detections', self._people, 10)
        self.create_subscription(Twist, 'cmd_vel_nav', self._cmd_nav, 10)
        self.create_subscription(Twist, 'cmd_vel', self._cmd, 10)
        self.create_subscription(Odometry, 'odom', self._odom, 10)
        self.create_timer(1.0 / hz, self._record)

    def _set(self, source, values):
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
                'control_reason': value.get('reason', ''),
                'navigation_session_id': value.get('navigation_session_id', ''),
                'actual_speed_source': value.get('actual_speed_source'),
            })
        except (ValueError, TypeError):
            self._set('speed', {'speed_controller_state': 'STATUS_PARSE_ERROR'})

    def _command(self, message):
        try:
            value = json.loads(message.data)
            self._last_command = {
                'last_speed_command_status': value.get('status', ''),
                'last_speed_command_target_mps': value.get('requested_target_speed_mps'),
            }
        except (ValueError, TypeError):
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
        row = {key: self._values.get(key) for key in FIELDS}
        row.update(self._last_command)
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
    try:
        deadline = time.monotonic() + args.duration_sec
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=min(0.1, 1.0 / args.hz))
    finally:
        rows = node._rows
        node.close()
        node.destroy_node()
        rclpy.shutdown()
    print(json.dumps({'output': str(output), 'rows': rows, 'duration_sec': args.duration_sec}))


if __name__ == '__main__':
    main()
