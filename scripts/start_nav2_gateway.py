"""Start Gazebo-only adapter for an already running local simulation."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
from threading import Event, Thread
import time

import rclpy
from std_msgs.msg import String
from rclpy.executors import MultiThreadedExecutor
from rclpy.signals import SignalHandlerOptions
from temi_bridge.nav2_backend import Nav2Backend
from temi_bridge.nav2_transport import Nav2Transport
from temi_bridge.ros_gateway import TemiGatewayNode

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--layout', choices=['official', 'adaptive'], default='official')
    parser.add_argument('--presentation', action='store_true')
    parser.add_argument('--domain-id', type=int,
                        default=int(os.environ.get('ROS_DOMAIN_ID', '211')))
    args = parser.parse_args()
    if (os.environ.get('ROS_LOCALHOST_ONLY') != '1' or
            not 0 <= args.domain_id <= 232 or
            os.environ.get('ROS_DOMAIN_ID') != str(args.domain_id)):
        parser.error('需设置匹配的 ROS_DOMAIN_ID（0–232）并启用 ROS_LOCALHOST_ONLY=1')
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
        # Costmap lifecycle configuration can exceed 45s on a resource-limited host.
        # This only extends readiness waiting; no navigation action is sent until ready.
        deadline = time.monotonic() + 120
        while not transport.ready() and not stop.wait(0.1):
            if time.monotonic() > deadline:
                raise RuntimeError('等待仿真 Nav2 和定位超时')
        if stop.is_set():
            return 1
        if 'temi_gateway' in transport.get_node_names():
            raise RuntimeError('已有 temi_gateway，禁止重复启动')
        backend = Nav2Backend(transport, goals, waypoints)
        if args.presentation:
            speech = transport.create_publisher(String, 'heritage/simulation/speech', 10)
            original_speak = backend.speak
            async def presentation_speak(text, *, task_id, feedback=None):
                speech.publish(String(data=json.dumps({'text': text, 'task_id': task_id, 'mode': 'simulated_speech'})))
                await asyncio.sleep(min(10.0, max(4.0, len(text)/5)))
                return await original_speak(text, task_id=task_id, feedback=feedback)
            backend.speak = presentation_speak
        gateway = TemiGatewayNode(backend)
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
