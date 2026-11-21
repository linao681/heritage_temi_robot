#!/usr/bin/env python3
"""Exercise Gazebo depth/lidar through fusion and policy with a marked box fixture."""
import argparse
import copy
import json
import os
from pathlib import Path
import threading
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Header, String
from temi_interfaces.msg import NavigationStatus, PerceptionInput, PersonDetection, PersonDetectionArray, RobotStatus
from temi_speed_controller.speed_policy import SpeedController, SpeedInputs
from visitor_perception.ros_depth_association import DepthAssociationNode
from visitor_perception.ros_perception_fusion import PerceptionFusionNode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=20.0)
    parser.add_argument('--output', required=True, help='新文件路径；拒绝覆盖')
    options = parser.parse_args()
    output = Path(options.output)
    if output.exists():
        parser.error('输出文件已存在；拒绝覆盖历史报告')
    if os.environ.get('ROS_LOCALHOST_ONLY') != '1':
        parser.error('必须使用隔离的 ROS Domain（ROS_LOCALHOST_ONLY=1）')

    rclpy.init(args=['--ros-args', '-p', 'simulation_mode:=true'])
    probe = rclpy.create_node('gazebo_perception_pipeline_probe')
    depth = DepthAssociationNode(simulation_mode=True)
    fusion = PerceptionFusionNode(simulation_mode=True)
    executor = SingleThreadedExecutor()
    for node in (probe, depth, fusion):
        executor.add_node(node)
    received = {'depth': None, 'associated': [], 'fused': []}
    probe.create_subscription(Image, 'camera/depth/image_raw',
                              lambda msg: received.update(depth=msg), 5)
    probe.create_subscription(PerceptionInput, 'heritage/perception/fused',
                              received['fused'].append, 10)
    probe.create_subscription(PersonDetectionArray, 'heritage/visitor/person_detections',
                              received['associated'].append, 10)
    visitor_pub = probe.create_publisher(String, 'heritage/visitor/status', 10)
    raw_pub = probe.create_publisher(PersonDetectionArray,
                                     'heritage/visitor/person_detections/raw', 5)
    robot_pub = probe.create_publisher(RobotStatus, 'temi/robot_status', 10)
    nav_pub = probe.create_publisher(NavigationStatus, 'temi/navigation_status', 10)
    tour_pub = probe.create_publisher(String, 'heritage/tour/status', 10)
    safety_pub = probe.create_publisher(Bool, 'heritage/safety_stop', 10)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + options.timeout
        while received['depth'] is None and time.monotonic() < deadline:
            time.sleep(0.05)
        if received['depth'] is None:
            raise RuntimeError('未收到 Gazebo 深度图')
        while not any(message.valid for message in received['fused']) and time.monotonic() < deadline:
            image = received['depth']
            detection = PersonDetection(x_min=0.4, y_min=0.2, x_max=0.6, y_max=0.85,
                                        confidence=0.8, distance_valid=False)
            raw = PersonDetectionArray(header=copy.deepcopy(image.header), source='yolox_rgb',
                sample_age_sec=0.0, valid=True, people_count=1, detections=[detection],
                person_distance_valid=False, crowd_density_valid=True, crowd_density=0.2)
            visitor_pub.publish(String(data=json.dumps({
                'source': 'mock', 'valid': True, 'stable': True, 'stable_fresh': True,
                'people_count': 1, 'expected_count': 1, 'group_state': 'following',
            })))
            raw_pub.publish(raw)
            robot_pub.publish(RobotStatus(header=Header(frame_id='gazebo_map'), connected=True,
                                          x=0.0, y=0.0, yaw=0.0))
            nav_pub.publish(NavigationStatus(task_id='gazebo-fixture-session', status='going'))
            tour_pub.publish(String(data='{"state":"NAVIGATING"}'))
            safety_pub.publish(Bool(data=False))
            time.sleep(0.1)
        fused = next((message for message in reversed(received['fused']) if message.valid), None)
        if fused is None:
            latest = received['fused'][-1].error if received['fused'] else '未收到融合消息'
            sources = received['fused'][-1].data_sources if received['fused'] else []
            assoc = received['associated'][-1] if received['associated'] else None
            raise RuntimeError(f'感知融合未达到有效态：{latest}; sources={sources}; '
                f'modes=({depth._simulation_mode},{fusion._fusion.config.simulation_mode}); '
                f'association={None if assoc is None else (assoc.valid, assoc.source, assoc.error, assoc.person_distance_valid, assoc.crowd_density_valid)}')
        now = time.monotonic()
        decision = SpeedController().update(SpeedInputs(
            now=now - fused.sample_age_sec, nearest_person_m=fused.nearest_person_m,
            crowd_density=fused.crowd_density, obstacle_distance_m=fused.obstacle_distance_m,
            group_state=fused.group_state, navigating=fused.navigating,
            explaining=fused.explaining, navigation_error=fused.navigation_error,
            safety_stop=fused.safety_stop, position_valid=fused.position_valid,
            communication_valid=fused.communication_valid, stop_confirmed=False,
            navigation_session_id=fused.navigation_session_id,
            sample_age_sec=fused.sample_age_sec, source_allowed=True,
            people_valid=fused.people_valid, person_distance_valid=fused.person_distance_valid,
            crowd_density_valid=fused.crowd_density_valid,
            obstacle_distance_valid=fused.obstacle_distance_valid,
            safety_stop_valid=fused.safety_stop_valid,
        ), now=now)
        report = {
            'success': bool(decision.send_speed),
            'data_source': 'Gazebo scan/depth plus explicit synthetic YOLOX-box and calibrated-density fixture',
            'person_detection_is_camera_model_output': False,
            'nearest_person_m': fused.nearest_person_m,
            'obstacle_distance_m': fused.obstacle_distance_m,
            'people_count': fused.people_count,
            'sample_age_sec': fused.sample_age_sec,
            'navigation_session_id': fused.navigation_session_id,
            'controller_state': decision.state,
            'target_speed_mps': decision.target_speed_mps,
            'command_eligible': decision.send_speed,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as file:
            json.dump(report, file, indent=2, ensure_ascii=False, allow_nan=False)
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report['success'] else 1
    finally:
        executor.shutdown()
        thread.join(timeout=2)
        for node in (fusion, depth, probe):
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
