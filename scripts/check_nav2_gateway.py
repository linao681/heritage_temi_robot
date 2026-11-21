"""Explicit local Gazebo adapter acceptance: arrival then stop while moving."""
import json
import os
from pathlib import Path
import time

import rclpy
from rclpy.action import ActionClient
from nav_msgs.msg import Odometry
from temi_interfaces.action import NavigateTo
from temi_interfaces.srv import StopRobot

ROOT = Path(__file__).resolve().parents[1]


def main():
    if os.environ.get('ROS_LOCALHOST_ONLY') != '1' or os.environ.get('ROS_DOMAIN_ID') != '211':
        raise RuntimeError('仅限本机模拟域 211')
    rclpy.init()
    node = rclpy.create_node('gazebo_gateway_acceptance')
    action = ActionClient(node, NavigateTo, 'temi/navigate_to')
    stop = node.create_client(StopRobot, 'temi/stop')
    odom = {'moving': False, 'at': 0}
    def receive(msg):
        odom.update(moving=abs(msg.twist.twist.linear.x)>0.03 or abs(msg.twist.twist.angular.z)>0.08,
                    at=time.monotonic())
    node.create_subscription(Odometry, 'odom', receive, 10)
    report = {'success': False}
    def wait(predicate, timeout):
        deadline = time.monotonic()+timeout
        while not predicate():
            if time.monotonic() > deadline:
                raise TimeoutError('等待网关响应超时')
            rclpy.spin_once(node, timeout_sec=0.05)
    def submit(location):
        future = action.send_goal_async(NavigateTo.Goal(location=location, timeout_sec=120.0))
        wait(future.done, 10)
        goal = future.result()
        if not goal.accepted:
            raise RuntimeError('网关拒绝目标')
        return goal, goal.get_result_async()
    try:
        wait(lambda: action.server_is_ready() and stop.service_is_ready(), 30)
        first, result = submit('zone_1')
        wait(result.done, 120)
        report['arrival'] = bool(result.result().result.success)
        if not report['arrival']:
            raise RuntimeError(result.result().result.message)
        second, pending = submit('zone_2')
        wait(lambda: odom['moving'] and time.monotonic()-odom['at'] < 1, 30)
        response = stop.call_async(StopRobot.Request(stop=True))
        wait(response.done, 20)
        report['stop_confirmed'] = response.result().success
        report['stop_message'] = response.result().message
        wait(pending.done, 20)
        report['interrupted_not_success'] = not pending.result().result.success
        report['stationary'] = not odom['moving'] and time.monotonic()-odom['at'] < 1
        report['success'] = all(report[k] for k in ('arrival', 'stop_confirmed', 'interrupted_not_success', 'stationary'))
    except Exception as error:
        report['error'] = str(error)
    finally:
        path = ROOT/'docs/acceptance/gazebo/nav2_gateway.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False), flush=True)
        action.destroy()
        node.destroy_node()
        rclpy.shutdown()
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
