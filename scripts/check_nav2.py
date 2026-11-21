"""Execute explicit single-point or five-zone Gazebo navigation checks."""
import argparse
import json
import math
import os
from pathlib import Path
import time

import rclpy
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener

ROOT = Path(__file__).resolve().parents[1]

ZONE_NAMES = ['非遗概览', '传统工艺', '代表作品', '传承故事', '互动体验']


def route_keys(full_tour):
    return [f'zone_{index}' for index in range(1, 6)] + ['exit'] if full_tour else ['zone_1']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--layout', choices=['official', 'adaptive'], default='official')
    parser.add_argument('--full-tour', action='store_true', help='五区顺序导航并前往出口')
    args = parser.parse_args()
    if os.environ.get('ROS_LOCALHOST_ONLY') != '1' or os.environ.get('ROS_DOMAIN_ID') != '211':
        parser.error('This simulation check requires localhost Domain 211')
    rclpy.init()
    node = rclpy.create_node('gazebo_navigation_check')
    node.set_parameters([rclpy.parameter.Parameter('use_sim_time', value=True)])
    buffer = Buffer()
    listener = TransformListener(buffer, node)
    client = ActionClient(node, NavigateToPose, 'navigate_to_pose')
    odometry = {}
    def receive_odom(msg):
        odometry.update(time=time.monotonic(), linear=msg.twist.twist.linear.x,
                        angular=msg.twist.twist.angular.z)
    node.create_subscription(Odometry, 'odom', receive_odom, 10)
    route_status = {}
    publisher = node.create_publisher(String, 'heritage/simulation/route_status', 10)
    def publish_status():
        if route_status:
            publisher.publish(String(data=json.dumps(route_status, ensure_ascii=False)))
    node.create_timer(0.5, publish_status)
    def set_status(state, name='', index=0, error=''):
        route_status.update(state=state, name=name, index=index,
                            total=len(route_keys(args.full_tour)), error=error)
        publish_status()
    goal_handle = None
    def wait(predicate, seconds):
        end = time.monotonic() + seconds
        while not predicate():
            if time.monotonic() > end:
                raise TimeoutError('navigation wait timed out')
            rclpy.spin_once(node, timeout_sec=0.1)
    report = {'success': False, 'layout': args.layout, 'stations': [],
              'requested_route': route_keys(args.full_tour)}
    try:
        wait(lambda: client.server_is_ready() and buffer.can_transform(
            'map', 'base_footprint', rclpy.time.Time()), 45)
        wait(lambda: 'gazebo' in node.get_node_names(), 10)
        goals = json.loads((ROOT / 'simulation/generated' / f'{args.layout}_goals.json').read_text())['goals']
        for index, key in enumerate(report['requested_route'], 1):
            name = ZONE_NAMES[int(key[-1])-1] if key.startswith('zone_') else '出口'
            set_status('NAVIGATING', name, index)
            target = goals[key]
            goal = NavigateToPose.Goal()
            goal.pose.header.frame_id = 'map'
            goal.pose.header.stamp = node.get_clock().now().to_msg()
            goal.pose.pose.position.x = target['x']
            goal.pose.pose.position.y = target['y']
            goal.pose.pose.orientation.z = math.sin(target['yaw']/2)
            goal.pose.pose.orientation.w = math.cos(target['yaw']/2)
            started = time.monotonic()
            future = client.send_goal_async(goal)
            wait(future.done, 10)
            goal_handle = future.result()
            if not goal_handle.accepted:
                raise RuntimeError('goal rejected: ' + key)
            result = goal_handle.get_result_async()
            wait(result.done, 240)
            wait(lambda: time.monotonic()-odometry.get('time', 0) < 1 and
                 abs(odometry['linear']) < 0.02 and abs(odometry['angular']) < 0.05, 10)
            transform = buffer.lookup_transform('map', 'base_footprint', rclpy.time.Time())
            pose = transform.transform.translation
            error = math.hypot(pose.x-target['x'], pose.y-target['y'])
            station = dict(id=key, name=ZONE_NAMES[int(key[-1])-1] if key.startswith('zone_') else '出口',
                           status=result.result().status, position_error_m=error,
                           elapsed_sec=round(time.monotonic()-started, 3),
                           stopped=True, success=result.result().status == 4 and error <= 0.3)
            report['stations'].append(station)
            print(json.dumps(station, ensure_ascii=False), flush=True)
            if not station['success']:
                raise RuntimeError('station failed: ' + key)
            set_status('ARRIVED', name, index)
            # 留给只读界面观察到到站事件，不模拟讲解或播报。
            until = time.monotonic() + 1
            wait(lambda: time.monotonic() >= until, 2)
        set_status('COMPLETED', name, index)
        report.update(success=True, status=4, position_error_m=error,
                      elapsed_sec=round(sum(s['elapsed_sec'] for s in report['stations']), 3))
    except Exception as error:
        report['error'] = str(error)
        set_status('ERROR', error=str(error))
    finally:
        if goal_handle is not None and not report['success']:
            cancel = goal_handle.cancel_goal_async()
            try:
                wait(cancel.done, 5)
            except TimeoutError:
                pass
        directory = ROOT / 'docs/acceptance/gazebo'
        directory.mkdir(parents=True, exist_ok=True)
        filename = f'{args.layout}_full_tour.json' if args.full_tour else f'{args.layout}_navigation.json'
        (directory / filename).write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report))
        # 发送终态后短暂保持心跳，便于展示与订阅端接收。
        end = time.monotonic() + 2
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.1)
        client.destroy()
        node.destroy_node()
        rclpy.shutdown()
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
