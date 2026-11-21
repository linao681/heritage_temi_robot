#!/usr/bin/env python3
"""向速度策略发布明确标记的模拟感知场景；不代表真实游客检测。"""
import argparse
import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from temi_interfaces.msg import NavigationStatus, RobotStatus


SCENARIOS = {
    'open': (4.0, 0.05, 4.0, 'following'),
    'crowd': (1.8, 0.8, 2.5, 'following'),
    'obstacle': (1.8, 0.1, 1.0, 'following'),
    'danger': (0.4, 0.1, 0.4, 'following'),
    'lost': (3.0, 0.1, 3.0, 'lost'),
    'clear': (4.0, 0.05, 4.0, 'following'),
}


class ScenarioPublisher(Node):
    def __init__(self):
        super().__init__('mock_speed_scenarios')
        self.publisher = self.create_publisher(String, 'heritage/speed_control/input', 10)
        self.navigation_session_id = ''
        self.navigating = False
        self.explaining = False
        self.position_valid = False
        self.communication_valid = False
        self.create_subscription(NavigationStatus, 'temi/navigation_status', self._on_navigation, 10)
        self.create_subscription(RobotStatus, 'temi/robot_status', self._on_robot, 10)
        self.create_subscription(String, 'heritage/tour/status', self._on_tour, 10)

    def _on_navigation(self, message):
        self.navigation_session_id = message.task_id if message.status in ('start', 'calculating', 'going', 'reposing') else self.navigation_session_id
        self.navigating = message.status in ('start', 'calculating', 'going', 'reposing')

    def _on_robot(self, message):
        self.communication_valid = message.connected
        self.position_valid = message.connected and bool(message.header.frame_id)

    def _on_tour(self, message):
        try:
            self.explaining = json.loads(message.data).get('state') == 'EXPLAINING'
        except (TypeError, ValueError):
            pass

    def publish(self, name):
        person, density, obstacle, group = SCENARIOS[name]
        message = {'source': 'simulation', 'sample_age_sec': 0.0, 'nearest_person_m': person, 'crowd_density': density,
                   'obstacle_distance_m': obstacle, 'group_state': group,
                   'navigating': self.navigating, 'explaining': self.explaining,
                   'navigation_error': False, 'safety_stop': False,
                   'position_valid': self.position_valid, 'communication_valid': self.communication_valid,
                   'navigation_session_id': self.navigation_session_id}
        self.publisher.publish(String(data=json.dumps(message)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=(*SCENARIOS, 'cycle'), default='cycle')
    parser.add_argument('--seconds-per-stage', type=float, default=5.0)
    args = parser.parse_args()
    if args.seconds_per_stage <= 0:
        parser.error('--seconds-per-stage must be positive')
    rclpy.init()
    node = ScenarioPublisher()
    sequence = list(SCENARIOS) if args.scenario == 'cycle' else [args.scenario]
    try:
        print('正在发布明确标记的模拟感知数据，不是真实游客/障碍物检测。', flush=True)
        while rclpy.ok():
            for name in sequence:
                print(f'模拟场景: {name}', flush=True)
                deadline = time.monotonic() + args.seconds_per_stage
                while rclpy.ok() and time.monotonic() < deadline:
                    rclpy.spin_once(node, timeout_sec=0.05)
                    node.publish(name)
                    time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
