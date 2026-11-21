"""Local, read-only HTTP bridge from ROS map TF to the existing web scene."""
import argparse
import json
import math
import os
import signal
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from tf2_ros import Buffer, TransformListener
from std_msgs.msg import String
try:
    from .route_status import fresh_status
except ImportError:
    from route_status import fresh_status

ROOT = Path(__file__).resolve().parents[1]


def convert_pose(x, y, yaw):
    return {'x': x, 'z': -y, 'yaw': math.atan2(math.sin(math.pi/2 + yaw),
                                                math.cos(math.pi/2 + yaw))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', choices=['official', 'adaptive'], default='official')
    parser.add_argument('--port', type=int, default=8088)
    parser.add_argument('--domain-id', type=int, default=211)
    args = parser.parse_args()
    if (os.environ.get('ROS_LOCALHOST_ONLY') != '1' or
            os.environ.get('ROS_DOMAIN_ID') != str(args.domain_id) or
            not 0 <= args.domain_id <= 232):
        parser.error('须使用本机 ROS_LOCALHOST_ONLY=1 与匹配的 ROS_DOMAIN_ID')
    from rclpy.signals import SignalHandlerOptions
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = rclpy.create_node('heritage_web_visualization')
    node.route_status, node.route_received = None, 0.0
    node.tour_status, node.tour_received = None, 0.0
    node.speed_control, node.speed_received = None, 0.0
    def receive_route(message):
        try:
            value = json.loads(message.data)
        except (TypeError, ValueError):
            return
        node.route_status, node.route_received = value, time.monotonic()
    node.create_subscription(String, 'heritage/simulation/route_status', receive_route, 10)
    def receive_tour(message):
        try:
            value = json.loads(message.data)
            if not isinstance(value, dict):
                return
            node.tour_status = {key: value.get(key) for key in
                                ('state', 'reason', 'target', 'visited', 'outcome', 'qa_waiting', 'qa_result')}
            node.tour_received = time.monotonic()
        except (TypeError, ValueError):
            pass
    node.create_subscription(String, 'heritage/tour/status', receive_tour, 10)
    def receive_speed(message):
        try:
            value = json.loads(message.data)
            if isinstance(value, dict):
                node.speed_control = value
                node.speed_received = time.monotonic()
        except (TypeError, ValueError):
            pass
    node.create_subscription(String, 'heritage/speed_control/status', receive_speed, 10)
    buffer = Buffer()
    listener = TransformListener(buffer, node, spin_thread=False)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    thread = Thread(target=executor.spin, daemon=True)
    thread.start()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *handler_args, **kwargs):
            super().__init__(*handler_args, directory=str(ROOT / 'visualization/ros_hall'), **kwargs)

        def do_GET(self):
            if self.path != '/api/pose':
                return super().do_GET()
            data = {'connected': False, 'layout': args.layout}
            data['route'] = fresh_status(node.route_status, node.route_received)
            data['tour'] = node.tour_status if time.monotonic()-node.tour_received < 3 else None
            data['speed_control'] = node.speed_control if time.monotonic()-node.speed_received < 3 else None
            try:
                transform = buffer.lookup_transform('map', 'base_footprint', rclpy.time.Time())
                stamp = transform.header.stamp.sec + transform.header.stamp.nanosec * 1e-9
                # TF 使用仿真时钟：读取 /clock，禁止把冻结的仿真误判为实时。
                q = transform.transform.rotation
                yaw = math.atan2(2 * (q.w*q.z + q.x*q.y), 1 - 2 * (q.y*q.y + q.z*q.z))
                age = time.monotonic() - node.last_clock_at
                if age < 2 and abs(node.sim_seconds - stamp) < 2:
                    data.update(connected=True, **convert_pose(transform.transform.translation.x,
                                                               transform.transform.translation.y, yaw))
            except Exception:
                pass
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    from rosgraph_msgs.msg import Clock
    from rclpy.qos import qos_profile_sensor_data
    node.last_clock_at, node.sim_seconds = 0.0, 0.0
    def clock_callback(msg):
        node.sim_seconds = msg.clock.sec + msg.clock.nanosec * 1e-9
        node.last_clock_at = time.monotonic()
    node.create_subscription(Clock, '/clock', clock_callback, qos_profile_sensor_data)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    print(f'只读展示: http://127.0.0.1:{args.port}/', flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        executor.shutdown()
        thread.join(timeout=3)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
