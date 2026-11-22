"""Local ROS visualization bridge with optional interactive tour controls."""
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
from gazebo_msgs.msg import ModelStates
try:
    from .route_status import fresh_status
except ImportError:
    from route_status import fresh_status

ROOT = Path(__file__).resolve().parents[1]
INTERACTION_ACTIONS = ('start', 'arm_visitor', 'accept', 'refuse', 'pause', 'resume', 'cancel', 'manual_takeover', 'finish_qa', 'straggle', 'gather')


def interaction_request(payload):
    if not isinstance(payload, dict) or payload.get('action') not in (*INTERACTION_ACTIONS, 'ask'):
        raise ValueError('未知交互操作')
    action = payload['action']
    if action != 'ask':
        return action, None
    question = payload.get('question')
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 500:
        raise ValueError('请输入 1–500 字的问题')
    return action, question.strip()


def convert_pose(x, y, yaw):
    return {'x': x, 'z': -y, 'yaw': math.atan2(math.sin(math.pi/2 + yaw),
                                                math.cos(math.pi/2 + yaw))}


def visitor_poses(names, poses):
    result = []
    for name, pose in zip(names, poses):
        if not name.startswith(('phase25_person_', 'phase2_person_')):
            continue
        q = pose.orientation
        yaw = math.atan2(2 * (q.w*q.z + q.x*q.y), 1 - 2 * (q.y*q.y + q.z*q.z))
        result.append({'id': name, **convert_pose(pose.position.x, pose.position.y, yaw)})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', choices=['official', 'adaptive'], default='official')
    parser.add_argument('--port', type=int, default=8088)
    parser.add_argument('--domain-id', type=int, default=211)
    parser.add_argument('--interactive', action='store_true')
    args = parser.parse_args()
    if (os.environ.get('ROS_LOCALHOST_ONLY') != '1' or
            os.environ.get('ROS_DOMAIN_ID') != str(args.domain_id) or
            not 0 <= args.domain_id <= 232):
        parser.error('须使用本机 ROS_LOCALHOST_ONLY=1 与匹配的 ROS_DOMAIN_ID')
    from rclpy.signals import SignalHandlerOptions
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = rclpy.create_node('heritage_web_visualization')
    if args.interactive:
        from std_srvs.srv import Trigger
        from temi_interfaces.srv import SubmitQuestion
        from threading import Lock
        control_lock = Lock()
        controls = {action: node.create_client(Trigger, ('heritage/simulation/team/' if action in ('straggle', 'gather') else 'heritage/tour/') + action)
                    for action in INTERACTION_ACTIONS}
        question_client = node.create_client(SubmitQuestion, 'heritage/tour/ask')
    node.route_status, node.route_received = None, 0.0
    node.tour_status, node.tour_received = None, 0.0
    node.speed_control, node.speed_received = None, 0.0
    node.visitor_snapshot = ([], 0.0)
    node.team_snapshot = (None, 0.0)
    node.speech_snapshot = (None, 0.0)
    def receive_speech(message):
        try:
            node.speech_snapshot = (json.loads(message.data), time.monotonic())
        except ValueError:
            pass
    node.create_subscription(String, 'heritage/simulation/speech', receive_speech, 10)
    def receive_team(message):
        try:
            value = json.loads(message.data)
            if isinstance(value, dict):
                node.team_snapshot = (value, time.monotonic())
        except ValueError:
            pass
    node.create_subscription(String, 'heritage/simulation/team_status', receive_team, 10)
    def receive_models(message):
        node.visitor_snapshot = (visitor_poses(message.name, message.pose), time.monotonic())
    node.create_subscription(ModelStates, '/gazebo/model_states', receive_models, 10)
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
                                ('state', 'reason', 'target', 'visited', 'outcome', 'qa_waiting', 'qa_result', 'visitor_assist', 'connected', 'is_moving')}
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

        def send_json(self, status, data):
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            origin = f'http://127.0.0.1:{args.port}'
            if (not args.interactive or self.path != '/api/interact' or
                    self.headers.get('Origin') != origin or self.headers.get('Host') != f'127.0.0.1:{args.port}' or
                    self.headers.get('Content-Type', '').split(';')[0] != 'application/json'):
                return self.send_json(403, {'success': False, 'message': '交互模式未启用或请求来源无效'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8192:
                    raise ValueError('请求大小异常')
                action, question = interaction_request(json.loads(self.rfile.read(length)))
            except (ValueError, TypeError):
                return self.send_json(400, {'success': False, 'message': '交互请求无效'})
            if not control_lock.acquire(blocking=False):
                return self.send_json(409, {'success': False, 'message': '正在等待上一条指令'})
            try:
                team, received = node.team_snapshot
                if action == 'resume' and team is not None and (time.monotonic()-received > 1 or not team.get('gathered')):
                    return self.send_json(409, {'success': False, 'message': '游客尚未集合或队伍状态过期'})
                client = question_client if action == 'ask' else controls[action]
                if not client.service_is_ready():
                    return self.send_json(503, {'success': False, 'message': '导览服务未就绪'})
                request = (SubmitQuestion.Request(question=question, exhibit='exhibit_05', level='basic')
                           if action == 'ask' else Trigger.Request())
                future = client.call_async(request)
                deadline = time.monotonic() + 8
                while not future.done() and time.monotonic() < deadline:
                    time.sleep(.05)
                if not future.done():
                    future.cancel()
                    return self.send_json(504, {'success': False, 'message': '确认超时，请查看当前导览状态'})
                result = future.result()
                return self.send_json(200, {'success': result.accepted if action == 'ask' else result.success,
                                            'message': result.message})
            except Exception:
                return self.send_json(503, {'success': False, 'message': '导览服务异常，请查看当前状态'})
            finally:
                control_lock.release()

        def do_GET(self):
            if self.path != '/api/pose':
                return super().do_GET()
            data = {'connected': False, 'layout': args.layout, 'interactive': args.interactive}
            data['route'] = fresh_status(node.route_status, node.route_received)
            data['tour'] = node.tour_status if time.monotonic()-node.tour_received < 3 else None
            data['speed_control'] = node.speed_control if time.monotonic()-node.speed_received < 3 else None
            visitors, received = node.visitor_snapshot
            data['visitors'] = visitors if time.monotonic()-received < 2 else None
            team, team_received = node.team_snapshot
            data['team'] = team if time.monotonic()-team_received < 1 else None
            speech, speech_received = node.speech_snapshot
            data['speech'] = speech if time.monotonic()-speech_received < 12 else None
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
    print(f'{"交互展示" if args.interactive else "只读展示"}: http://127.0.0.1:{args.port}/', flush=True)
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
