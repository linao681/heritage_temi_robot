import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros2_ws/src/visitor_perception'))
sys.path.insert(0, str(ROOT / 'ros2_ws/src/temi_speed_controller'))


def test_visitor_depth_lidar_and_navigation_reach_speed_policy(monkeypatch, tmp_path):
    monkeypatch.setenv('ROS_LOCALHOST_ONLY', '1')
    monkeypatch.setenv('ROS_DOMAIN_ID', '230')
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))

    import rclpy
    from rclpy.executors import SingleThreadedExecutor
    from sensor_msgs.msg import LaserScan
    from std_msgs.msg import Bool, Header, String
    from temi_interfaces.msg import NavigationStatus, PerceptionInput, PersonDetectionArray, RobotStatus
    from temi_speed_controller.speed_policy import SpeedController, SpeedInputs
    from visitor_perception.ros_perception_fusion import PerceptionFusionNode

    rclpy.init(args=[])
    probe = rclpy.create_node('perception_fusion_test_probe')
    fusion = PerceptionFusionNode()
    executor = SingleThreadedExecutor()
    executor.add_node(probe)
    executor.add_node(fusion)
    received = []
    probe.create_subscription(PerceptionInput, 'heritage/perception/fused', received.append, 10)
    visitor_pub = probe.create_publisher(String, 'heritage/visitor/status', 10)
    people_pub = probe.create_publisher(PersonDetectionArray, 'heritage/visitor/person_detections', 10)
    scan_pub = probe.create_publisher(LaserScan, 'scan', 10)
    robot_pub = probe.create_publisher(RobotStatus, 'temi/robot_status', 10)
    nav_pub = probe.create_publisher(NavigationStatus, 'temi/navigation_status', 10)
    tour_pub = probe.create_publisher(String, 'heritage/tour/status', 10)
    safety_pub = probe.create_publisher(Bool, 'heritage/safety_stop', 10)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5.0
        while not any(value.valid for value in received) and time.monotonic() < deadline:
            visitor_pub.publish(String(data=json.dumps({
                'source': 'camera', 'valid': True, 'stable': True, 'stable_fresh': True,
                'people_count': 3, 'expected_count': 3, 'group_state': 'following',
            })))
            people_pub.publish(PersonDetectionArray(source='temi_rgbd', valid=True,
                people_count=3, person_distance_valid=True, nearest_person_m=1.3,
                crowd_density_valid=True, crowd_density=0.2))
            scan_pub.publish(LaserScan(angle_min=-0.2, angle_increment=0.2,
                range_min=0.08, range_max=10.0, ranges=[3.0, 2.2, 3.0]))
            robot_pub.publish(RobotStatus(header=Header(frame_id='map'),
                connected=True, x=1.0, y=2.0, yaw=0.0))
            nav_pub.publish(NavigationStatus(task_id='nav-live', status='going'))
            tour_pub.publish(String(data='{"state":"NAVIGATING"}'))
            safety_pub.publish(Bool(data=False))
            time.sleep(0.05)
        assert received, '未收到融合感知状态'
        fused = next((value for value in reversed(received) if value.valid), None)
        assert fused is not None, f'{received[-1].error}; latest_scan={fusion._fusion._scan_at}, distance={fusion._fusion.obstacle_distance_m}'
        assert fused.people_count == 3
        assert fused.nearest_person_m == pytest.approx(1.3)
        assert fused.obstacle_distance_m == pytest.approx(2.2)
        assert fused.navigation_session_id == 'nav-live'
        now = time.monotonic()
        decision = SpeedController().update(SpeedInputs(
            now=now - fused.sample_age_sec, nearest_person_m=fused.nearest_person_m,
            crowd_density=fused.crowd_density, obstacle_distance_m=fused.obstacle_distance_m,
            group_state=fused.group_state, navigating=fused.navigating,
            explaining=fused.explaining, navigation_error=fused.navigation_error,
            safety_stop=fused.safety_stop, position_valid=fused.position_valid,
            communication_valid=fused.communication_valid, stop_confirmed=False,
            navigation_session_id=fused.navigation_session_id,
            sample_age_sec=fused.sample_age_sec, source_allowed=fused.source == 'temi_sensor_fusion',
            people_valid=fused.people_valid, person_distance_valid=fused.person_distance_valid,
            crowd_density_valid=fused.crowd_density_valid,
            obstacle_distance_valid=fused.obstacle_distance_valid,
            safety_stop_valid=fused.safety_stop_valid,
        ), now=now)
        assert decision.state == 'SLOW'
        assert decision.navigation_session_id == 'nav-live'
    finally:
        executor.shutdown()
        thread.join(timeout=2)
        fusion.destroy_node()
        probe.destroy_node()
        rclpy.shutdown()
