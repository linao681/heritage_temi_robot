"""Start Gazebo-only adapter for an already running local simulation."""
import argparse
import json
import os
from pathlib import Path
import signal
from threading import Event, Thread
import time

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.signals import SignalHandlerOptions
from temi_bridge.nav2_backend import Nav2Backend
from temi_bridge.nav2_transport import Nav2Transport
from temi_bridge.ros_gateway import TemiGatewayNode

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--layout', choices=['official', 'adaptive'], default='official')
    args = parser.parse_args()
    if os.environ.get('ROS_LOCALHOST_ONLY') != '1' or os.environ.get('ROS_DOMAIN_ID') != '211':
        parser.error('仅允许本机隔离的仿真域 211')
    goals = json.loads((ROOT / 'simulation/generated' / f'{args.layout}_goals.json').read_text())['goals']
    waypoints = {}
    if args.layout == 'official':
        layout = json.loads((ROOT / 'reference/ros2_handoff/environment/layouts.json').read_text())['official']
        plan = layout['PLAN']
        # 原始交接布局的第四至第五区参考动线，非访客展区停靠点。
        pixels = [layout['PLAN_APPROACH'][4][2], layout['PLAN_APPROACH'][4][3]]
        waypoints[('zone_4', 'zone_5')] = [
            {'x': (p[0]-plan['center'][0])*plan['scale'],
             'y': -(p[1]-plan['center'][1])*plan['scale'], 'yaw': 0.0} for p in pixels]
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    rclpy.init(args=[], signal_handler_options=SignalHandlerOptions.NO)
    transport = Nav2Transport()
    executor = MultiThreadedExecutor(num_threads=6)
    executor.add_node(transport)
    thread = Thread(target=executor.spin, daemon=True)
    thread.start()
    gateway = None
    try:
        deadline = time.monotonic() + 45
        while not transport.ready() and not stop.wait(0.1):
            if time.monotonic() > deadline:
                raise RuntimeError('等待仿真 Nav2 和定位超时')
        if stop.is_set():
            return 1
        if 'temi_gateway' in transport.get_node_names():
            raise RuntimeError('已有 temi_gateway，禁止重复启动')
        gateway = TemiGatewayNode(Nav2Backend(transport, goals, waypoints))
        executor.add_node(gateway)
        print('Gazebo Nav2 网关就绪（播报为无音频模拟）', flush=True)
        while not stop.wait(0.2):
            if not thread.is_alive():
                raise RuntimeError('ROS executor 已退出')
    finally:
        if gateway:
            gateway.close()
        executor.shutdown(timeout_sec=10)
        thread.join(timeout=10)
        if gateway:
            gateway.destroy_node()
        transport.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
