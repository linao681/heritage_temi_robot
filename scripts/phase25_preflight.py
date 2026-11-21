#!/usr/bin/env python3
"""Isolated Phase 2.5 ROS readiness checks; this node issues no motion commands."""
import argparse
from collections import OrderedDict
import json
import math
import os
import time

import rclpy
from gazebo_msgs.msg import ModelStates
from gazebo_msgs.srv import DeleteEntity, GetEntityState, SetEntityState, SpawnEntity
from geometry_msgs.msg import PoseWithCovarianceStamped
from lifecycle_msgs.srv import GetState
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, Image, LaserScan
from std_msgs.msg import String
from std_srvs.srv import Trigger
from temi_interfaces.action import NavigateTo, Speak
from temi_interfaces.msg import PerceptionInput, RobotStatus
from temi_interfaces.srv import AskHeritage
from tf2_ros import Buffer, TransformException, TransformListener


LIFECYCLE_NODES = (
    'map_server', 'amcl', 'planner_server', 'controller_server',
    'smoother_server', 'behavior_server', 'bt_navigator',
    'waypoint_follower', 'velocity_smoother',
)


def _json_default(value):
    if hasattr(value, 'item'):
        return value.item()
    raise TypeError(f'not JSON serializable: {type(value).__name__}')


class Phase25Readiness(Node):
    def __init__(self):
        super().__init__('phase25_readiness')
        self.received = {}
        self.values = {}
        self.stationary_since = None
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self, spin_thread=False)
        self.service_clients = {
            'tour_start_service': self.create_client(Trigger, 'heritage/tour/start'),
            'speed_reset_service': self.create_client(Trigger, 'heritage/speed_control/reset_error'),
            'knowledge_service': self.create_client(AskHeritage, 'heritage/knowledge/ask'),
            'gazebo_spawn_service': self.create_client(SpawnEntity, '/spawn_entity'),
            'gazebo_delete_service': self.create_client(DeleteEntity, '/delete_entity'),
            'gazebo_set_state_service': self.create_client(SetEntityState, '/gazebo/set_entity_state'),
            'gazebo_get_state_service': self.create_client(GetEntityState, '/gazebo/get_entity_state'),
        }
        self.navigation = ActionClient(self, NavigateTo, 'temi/navigate_to')
        self.speech = ActionClient(self, Speak, 'temi/speak')
        self.lifecycle = {
            name: self.create_client(GetState, f'/{name}/get_state')
            for name in LIFECYCLE_NODES
        }
        map_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                             durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(Clock, '/clock', self._on_clock, qos_profile_sensor_data)
        self.create_subscription(OccupancyGrid, 'map', self._map, map_qos)
        localization_qos = QoSProfile(
            depth=1, reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(PoseWithCovarianceStamped, 'amcl_pose',
                                 self._localization, localization_qos)
        self.create_subscription(Odometry, 'odom', self._odom, 20)
        self.create_subscription(LaserScan, 'scan', self._scan, qos_profile_sensor_data)
        self.create_subscription(Image, 'depth_camera/image_raw', self._image('rgb'), qos_profile_sensor_data)
        self.create_subscription(Image, 'camera/depth/image_raw', self._image('depth'), qos_profile_sensor_data)
        self.create_subscription(CameraInfo, 'depth_camera/camera_info',
                                 self._camera_info('rgb_info'), qos_profile_sensor_data)
        self.create_subscription(CameraInfo, 'camera/depth/camera_info',
                                 self._camera_info('depth_info'), qos_profile_sensor_data)
        self.create_subscription(ModelStates, '/gazebo/model_states', self._models, 10)
        self.create_subscription(PerceptionInput, 'heritage/perception/fused', self._fused, 10)
        self.create_subscription(String, 'heritage/visitor/status', self._visitor, 10)
        self.create_subscription(RobotStatus, 'temi/robot_status', self._robot, 10)
        self.create_subscription(String, 'heritage/tour/status', self._tour, 10)
        self.create_subscription(String, 'heritage/speed_control/status', self._speed, 10)

    def _mark(self, key, value=None):
        self.received[key] = time.monotonic()
        if value is not None:
            self.values[key] = value

    def _on_clock(self, message):
        self._mark('clock', message.clock.sec + message.clock.nanosec * 1e-9)

    def _map(self, message):
        self._mark('map', {'width': message.info.width, 'height': message.info.height})

    def _localization(self, message):
        self._mark('localization', {
            'x': message.pose.pose.position.x,
            'y': message.pose.pose.position.y,
        })

    def _odom(self, message):
        now = time.monotonic()
        twist = message.twist.twist
        linear = math.hypot(twist.linear.x, twist.linear.y)
        angular = abs(twist.angular.z)
        if linear < 0.02 and angular < 0.05:
            self.stationary_since = self.stationary_since or now
        else:
            self.stationary_since = None
        self._mark('odom', {'linear': linear, 'angular': angular})

    def _scan(self, message):
        valid = [value for value in message.ranges
                 if math.isfinite(value) and message.range_min <= value <= message.range_max]
        self._mark('scan', {'samples': len(message.ranges), 'finite_valid': len(valid),
                            'range_max': message.range_max})

    def _image(self, name):
        def receive(message):
            self._mark(name, {'width': message.width, 'height': message.height,
                              'encoding': message.encoding, 'has_data': bool(message.data)})
        return receive

    def _camera_info(self, name):
        def receive(message):
            self._mark(name, {'width': message.width, 'height': message.height,
                              'fx': message.k[0], 'fy': message.k[4]})
        return receive

    def _models(self, message):
        self._mark('gazebo_models', list(message.name))

    def _fused(self, message):
        self._mark('fused', {'valid': bool(message.valid),
                             'sample_age_sec': float(message.sample_age_sec),
                             'source': message.source,
                             'people_valid': bool(message.people_valid),
                             'obstacle_distance_valid': bool(message.obstacle_distance_valid),
                             'safety_stop_valid': bool(message.safety_stop_valid)})

    def _visitor(self, message):
        try:
            value = json.loads(message.data)
        except (ValueError, TypeError):
            value = {}
        self._mark('visitor', value)

    def _robot(self, message):
        self._mark('robot', {'connected': bool(message.connected),
                             'is_moving': bool(message.is_moving),
                             'frame_id': message.header.frame_id})

    def _tour(self, message):
        try:
            value = json.loads(message.data)
        except (ValueError, TypeError):
            value = {}
        self._mark('tour', value)

    def _speed(self, message):
        try:
            value = json.loads(message.data)
        except (ValueError, TypeError):
            value = {}
        self._mark('speed', value)

    def basic_checks(self):
        now = time.monotonic()
        fresh = lambda key, max_age=1.0: now - self.received.get(key, -math.inf) <= max_age
        odom = self.values.get('odom', {})
        visitor = self.values.get('visitor', {})
        fused = self.values.get('fused', {})
        robot = self.values.get('robot', {})
        tour = self.values.get('tour', {})
        speed = self.values.get('speed', {})
        checks = OrderedDict()
        checks['simulation_clock'] = fresh('clock', 1.0)
        checks['map_loaded'] = bool(self.values.get('map', {}).get('width', 0))
        checks['localization_fresh'] = self.localized_in_map()
        checks['odom_fresh'] = fresh('odom', 0.5)
        checks['robot_stationary'] = bool(self.stationary_since is not None and
                                          now - self.stationary_since >= 0.5 and
                                          odom.get('linear', math.inf) < 0.02 and
                                          odom.get('angular', math.inf) < 0.05)
        checks['laser_fresh'] = fresh('scan', 0.5) and self.values.get('scan', {}).get('samples', 0) > 0
        for key in ('rgb', 'depth'):
            value = self.values.get(key, {})
            checks[key + '_fresh'] = fresh(key, 1.0) and value.get('has_data', False)
        for key in ('rgb_info', 'depth_info'):
            value = self.values.get(key, {})
            checks[key + '_valid'] = (fresh(key, 2.0) and value.get('width', 0) > 0 and
                                      value.get('height', 0) > 0 and value.get('fx', 0) > 0 and
                                      value.get('fy', 0) > 0)
        checks['gazebo_robot_present'] = 'heritage_robot' in self.values.get('gazebo_models', [])
        checks['perception_fused_valid'] = (fresh('fused', 1.0) and fused.get('valid') is True and
                                             fused.get('sample_age_sec', math.inf) <= 1.0 and
                                             fused.get('people_valid') is True and
                                             fused.get('obstacle_distance_valid') is True and
                                             fused.get('safety_stop_valid') is True)
        checks['camera_count_stable'] = (
            fresh('visitor', 1.0) and visitor.get('source') == 'camera' and
            visitor.get('valid') is True and visitor.get('stable') is True and
            visitor.get('stable_fresh') is True)
        checks['robot_connected'] = fresh('robot', 1.0) and robot.get('connected') is True
        checks['tour_idle'] = fresh('tour', 1.0) and tour.get('state') == 'IDLE'
        checks['speed_controller_ready'] = (fresh('speed', 1.0) and
                                              speed.get('state') != 'ERROR' and
                                              speed.get('input_valid') is True)
        for name, client in self.service_clients.items():
            checks[name] = client.service_is_ready()
        checks['navigate_action_ready'] = self.navigation.server_is_ready()
        checks['speak_action_ready'] = self.speech.server_is_ready()
        return checks

    def lifecycle_checks(self):
        checks = OrderedDict()
        for name, client in self.lifecycle.items():
            if not client.service_is_ready():
                checks['lifecycle_' + name] = False
                continue
            future = client.call_async(GetState.Request())
            rclpy.spin_until_future_complete(self, future, timeout_sec=1.5)
            checks['lifecycle_' + name] = (
                future.done() and not future.exception() and
                future.result().current_state.label == 'active')
        return checks

    def localized_in_map(self):
        try:
            transform = self.tf_buffer.lookup_transform(
                'map', 'base_footprint', rclpy.time.Time())
        except TransformException:
            return False
        translation = transform.transform.translation
        stamp = transform.header.stamp.sec + transform.header.stamp.nanosec * 1e-9
        sim_time = self.values.get('clock', -math.inf)
        values = (translation.x, translation.y, translation.z, stamp, sim_time)
        age = abs(sim_time - stamp)
        self.values['localization_tf_age_sec'] = age
        return all(math.isfinite(value) for value in values) and age <= 1.5


def check_empty_domain(node, timeout_sec=1.0):
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    peers = [(name, namespace) for name, namespace in node.get_node_names_and_namespaces()
             if name != node.get_name()]
    return peers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout-sec', type=float, default=150.0)
    parser.add_argument('--check-domain-empty', action='store_true')
    args = parser.parse_args()
    domain = os.environ.get('ROS_DOMAIN_ID')
    if (os.environ.get('ROS_LOCALHOST_ONLY') != '1' or not domain or
            not domain.isdecimal() or not 0 <= int(domain) <= 232):
        parser.error('必须显式设置 ROS_LOCALHOST_ONLY=1 和 ROS_DOMAIN_ID=0..232')
    if not math.isfinite(args.timeout_sec) or args.timeout_sec <= 0:
        parser.error('--timeout-sec 必须为有限正数')
    rclpy.init(args=None)
    node = Phase25Readiness()
    try:
        if args.check_domain_empty:
            peers = check_empty_domain(node)
            print(json.dumps({'domain_id': int(domain), 'other_nodes': peers,
                              'empty': not peers}, ensure_ascii=False))
            return 0 if not peers else 1
        deadline = time.monotonic() + args.timeout_sec
        checks = OrderedDict()
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            checks = node.basic_checks()
            if all(checks.values()):
                lifecycle = node.lifecycle_checks()
                checks.update(lifecycle)
                if all(checks.values()):
                    print(json.dumps({'domain_id': int(domain), 'ready': True,
                                      'checks': checks, 'values': node.values},
                                     ensure_ascii=False, default=_json_default))
                    return 0
        checks = node.basic_checks()
        print(json.dumps({'domain_id': int(domain), 'ready': False,
                          'checks': checks, 'values': node.values,
                          'missing': [name for name, ok in checks.items() if not ok]},
                         ensure_ascii=False, default=_json_default))
        return 1
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
