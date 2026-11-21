"""ROS2 adapter for the fail-closed multi-source perception fusion."""
import json
import time

from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
from temi_interfaces.msg import (NavigationStatus, PerceptionInput, PersonDetectionArray,
                                 RobotStatus, SafetyStopStatus)

from .perception_fusion import PerceptionFusion


class PerceptionFusionNode(Node):
    def __init__(self, simulation_mode=False):
        super().__init__('heritage_perception_fusion')
        self.declare_parameter('max_sample_age_sec', 1.0)
        self.declare_parameter('front_half_angle_rad', 1.0471975512)
        self.declare_parameter('scan_min_valid_samples', 1)
        self.declare_parameter('simulation_mode', simulation_mode)
        self._fusion = PerceptionFusion(
            max_sample_age_sec=self.get_parameter('max_sample_age_sec').value,
            front_half_angle_rad=self.get_parameter('front_half_angle_rad').value,
            scan_min_valid_samples=self.get_parameter('scan_min_valid_samples').value,
            simulation_mode=self.get_parameter('simulation_mode').value,
        )
        self._publisher = self.create_publisher(PerceptionInput, 'heritage/perception/fused', 10)
        self.create_subscription(String, 'heritage/visitor/status', self._visitor, 10)
        self.create_subscription(PersonDetectionArray, 'heritage/visitor/person_detections', self._people, 10)
        self.create_subscription(LaserScan, 'scan', self._scan, 10)
        self.create_subscription(RobotStatus, 'temi/robot_status', self._robot, 10)
        self.create_subscription(NavigationStatus, 'temi/navigation_status', self._navigation, 10)
        self.create_subscription(String, 'heritage/tour/status', self._tour, 10)
        self.create_subscription(SafetyStopStatus, 'heritage/safety_stop/status',
                                 self._safety_stop_status, 10)
        self.create_timer(0.1, self._publish)

    def _visitor(self, message):
        try:
            value = json.loads(message.data)
            self._fusion.update_visitor(value, time.monotonic())
        except (TypeError, ValueError):
            self._fusion.update_visitor({}, time.monotonic())

    def _people(self, message):
        self._fusion.update_people({
            'source': message.source, 'valid': message.valid,
            'observation_state': message.observation_state,
            'people_count': message.people_count,
            'sample_age_sec': message.sample_age_sec,
            'person_distance_valid': message.person_distance_valid,
            'nearest_person_m': message.nearest_person_m,
            'crowd_density_valid': message.crowd_density_valid,
            'crowd_density': message.crowd_density,
        }, time.monotonic())

    def _scan(self, message):
        self._fusion.update_scan(message.ranges, message.angle_min, message.angle_increment,
                                 message.range_min, message.range_max, time.monotonic())

    def _robot(self, message):
        self._fusion.update_robot({
            'connected': message.connected, 'frame_id': message.header.frame_id,
            'x': message.x, 'y': message.y, 'yaw': message.yaw,
            'error_message': message.error_message,
        }, time.monotonic())

    def _navigation(self, message):
        self._fusion.update_navigation(message.status, message.task_id, time.monotonic())

    def _tour(self, message):
        try:
            value = json.loads(message.data)
            state = value.get('state') if isinstance(value, dict) else None
            self._fusion.update_tour(state, time.monotonic())
        except (TypeError, ValueError):
            self._fusion.update_tour('', time.monotonic())

    def _safety_stop_status(self, message):
        self._fusion.update_safety_stop_status({
            'source': message.source, 'valid': message.valid, 'state': message.state,
            'navigation_session_id': message.navigation_session_id,
            'action_terminal': message.action_terminal,
            'linear_speed_mps': message.linear_speed_mps,
            'angular_speed_rps': message.angular_speed_rps,
            'odom_age_sec': message.odom_age_sec,
            'stopped_duration_sec': message.stopped_duration_sec,
        }, time.monotonic())

    def _publish(self):
        value = self._fusion.snapshot(time.monotonic())
        message = PerceptionInput()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = 'base_link'
        message.source = value['source']
        message.data_sources = value['data_sources']
        message.sample_timestamp_monotonic_sec = float(value['sample_timestamp_monotonic_sec'])
        message.sample_age_sec = float(value['sample_age_sec'])
        message.valid = value['valid']
        message.error = value['error']
        message.warning = value['warning']
        message.people_count = value['people_count'] or 0
        message.expected_count = value['expected_count'] or 0
        message.group_state = value['group_state']
        message.people_valid = value['people_valid']
        message.person_observation_state = value['person_observation_state']
        message.person_observation_valid = value['person_observation_valid']
        message.person_distance_valid = value['person_distance_valid']
        message.nearest_person_m = value['nearest_person_m'] or 0.0
        message.crowd_density_valid = value['crowd_density_valid']
        message.crowd_density = value['crowd_density'] or 0.0
        message.obstacle_distance_valid = value['obstacle_distance_valid']
        message.obstacle_distance_m = value['obstacle_distance_m'] or 0.0
        message.position_valid = value['position_valid']
        message.communication_valid = value['communication_valid']
        message.safety_stop_valid = value['safety_stop_valid']
        message.safety_stop = value['safety_stop']
        message.stop_confirmed = value['stop_confirmed']
        message.stop_confirmed_session_id = value['stop_confirmed_session_id']
        message.navigating = value['navigating']
        message.explaining = value['explaining']
        message.navigation_error = value['navigation_error']
        message.navigation_session_id = value['navigation_session_id']
        self._publisher.publish(message)


def main(args=None):
    import rclpy
    rclpy.init(args=args)
    node = PerceptionFusionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
