"""Local ROS visualization bridge with optional interactive tour controls."""
import argparse
import json
import math
import os
import signal

import numpy as np
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.qos import qos_profile_sensor_data
from tf2_ros import Buffer, TransformListener
from std_msgs.msg import String
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import CameraInfo, Image, LaserScan
from temi_interfaces.msg import PerceptionInput
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



def snapshot_payload(value, received_at, now, max_age_sec):
    age = None if received_at is None else now - received_at
    fresh = value is not None and age is not None and 0 <= age <= max_age_sec
    return {'fresh': fresh, 'age_sec': age, 'value': value if fresh else None}


def scan_summary(ranges, *, angle_min, angle_increment, range_min, range_max):
    valid = [(index, float(value)) for index, value in enumerate(ranges)
             if math.isfinite(value) and range_min <= value <= range_max]
    if not valid:
        return {'valid': False, 'minimum_distance_m': None,
                'bearing_rad': None, 'valid_sample_count': 0}
    index, distance = min(valid, key=lambda item: item[1])
    return {'valid': True, 'minimum_distance_m': distance,
            'bearing_rad': angle_min + index * angle_increment,
            'valid_sample_count': len(valid)}


def depth_image_summary(message):
    frame_id = message.header.frame_id
    total = int(message.width) * int(message.height)
    result = {'valid': False, 'frame_id': frame_id, 'valid_pixels': 0,
              'total_pixels': total, 'valid_fraction': 0.0,
              'minimum_m': None, 'median_m': None}
    if message.encoding != '32FC1':
        result['reason'] = 'unsupported_encoding'
        return result
    row_bytes = int(message.width) * 4
    if (message.width <= 0 or message.height <= 0 or message.step < row_bytes or
            len(message.data) < message.step * message.height):
        result['reason'] = 'invalid_step_or_data_length'
        return result
    dtype = np.dtype('>f4' if message.is_bigendian else '<f4')
    raw = bytes(message.data)
    try:
        image = np.ndarray((message.height, message.width), dtype=dtype,
                           buffer=raw, strides=(message.step, 4))
    except (TypeError, ValueError):
        result['reason'] = 'invalid_step_or_data_length'
        return result
    samples = image[np.isfinite(image) & (image > 0)].astype(np.float64, copy=False)
    if not samples.size:
        result['reason'] = 'no_valid_depth_samples'
        return result
    result.update(valid=True, valid_pixels=int(samples.size),
                  valid_fraction=float(samples.size / total),
                  minimum_m=float(samples.min()), median_m=float(np.median(samples)))
    return result


def transform_summary(*, target_frame, source_frame, translation, rotation,
                      stamp_ns, current_ros_time_ns, max_age_sec=2.0):
    values = tuple(float(value) for value in (*translation, *rotation))
    finite = all(math.isfinite(value) for value in values)
    x, y, z, qx, qy, qz, qw = values
    norm = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
    is_static = int(stamp_ns) == 0
    age = None if is_static else (int(current_ros_time_ns) - int(stamp_ns)) / 1e9
    age_valid = is_static or (age is not None and 0 <= age <= max_age_sec)
    valid = finite and norm > 1e-6 and age_valid
    if valid:
        qx, qy, qz, qw = (component / norm for component in (qx, qy, qz, qw))
        yaw = math.atan2(2 * (qw*qz + qx*qy), 1 - 2 * (qy*qy + qz*qz))
    else:
        yaw = None
    return {'valid': valid, 'target_frame': target_frame, 'source_frame': source_frame,
            'translation_m': {'x': x, 'y': y, 'z': z} if finite else None,
            'yaw_rad': yaw, 'age_sec': age, 'is_static': is_static,
            'reason': '' if valid else 'invalid_or_stale_transform'}


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
    node.track_snapshot = (None, None)
    node.vision_team_snapshot = (None, None)
    node.rgb_info_snapshot = (None, None)
    node.depth_info_snapshot = (None, None)
    node.depth_image_snapshot = (None, None)
    node.scan_snapshot = (None, None)
    node.fused_snapshot = (None, None)
    node.cmd_vel_snapshot = (None, None)
    node.odom_snapshot = (None, None)
    def receive_tracks(message):
        try:
            value = json.loads(message.data)
            if isinstance(value, dict) and isinstance(value.get('tracks'), list):
                node.track_snapshot = (value, time.monotonic())
        except (TypeError, ValueError):
            pass
    def receive_vision_team(message):
        try:
            value = json.loads(message.data)
            if isinstance(value, dict):
                node.vision_team_snapshot = (value, time.monotonic())
        except (TypeError, ValueError):
            pass
    def receive_camera_info(kind):
        def receive(message):
            now = time.monotonic()
            value = {'frame_id': message.header.frame_id, 'width': message.width,
                     'height': message.height, 'fx': message.k[0], 'fy': message.k[4],
                     'valid': bool(message.width > 0 and message.height > 0 and
                                   math.isfinite(message.k[0]) and math.isfinite(message.k[4]) and
                                   message.k[0] > 0 and message.k[4] > 0)}
            if kind == 'rgb': node.rgb_info_snapshot = (value, now)
            else: node.depth_info_snapshot = (value, now)
        return receive
    def receive_depth_image(message):
        node.depth_image_snapshot = (depth_image_summary(message), time.monotonic())

    def receive_scan(message):
        value = scan_summary(message.ranges, angle_min=message.angle_min,
                             angle_increment=message.angle_increment,
                             range_min=message.range_min, range_max=message.range_max)
        value.update({'frame_id': message.header.frame_id,
                      'stamp_ns': message.header.stamp.sec * 1_000_000_000 + message.header.stamp.nanosec})
        node.scan_snapshot = (value, time.monotonic())
    def receive_fused(message):
        value = {'source': message.source, 'valid': bool(message.valid),
                 'sample_age_sec': float(message.sample_age_sec), 'error': message.error,
                 'warning': message.warning, 'people_count': int(message.people_count),
                 'expected_count': int(message.expected_count),
                 'person_observation_state': message.person_observation_state,
                 'person_observation_valid': bool(message.person_observation_valid),
                 'person_distance_valid': bool(message.person_distance_valid),
                 'nearest_person_m': float(message.nearest_person_m) if message.person_distance_valid else None,
                 'crowd_density_valid': bool(message.crowd_density_valid),
                 'crowd_density': float(message.crowd_density) if message.crowd_density_valid else None,
                 'obstacle_distance_valid': bool(message.obstacle_distance_valid),
                 'obstacle_distance_m': float(message.obstacle_distance_m) if message.obstacle_distance_valid else None,
                 'safety_stop': bool(message.safety_stop), 'stop_confirmed': bool(message.stop_confirmed),
                 'stop_confirmed_session_id': message.stop_confirmed_session_id,
                 'navigation_session_id': message.navigation_session_id}
        node.fused_snapshot = (value, time.monotonic())
    def receive_cmd_vel(message):
        linear = math.hypot(message.linear.x, message.linear.y)
        angular = message.angular.z
        if math.isfinite(linear) and math.isfinite(angular):
            node.cmd_vel_snapshot = ({'linear_speed_mps': linear, 'angular_speed_rps': angular},
                                     time.monotonic())
    def receive_odom(message):
        twist = message.twist.twist
        linear = math.hypot(twist.linear.x, twist.linear.y)
        angular = twist.angular.z
        if math.isfinite(linear) and math.isfinite(angular):
            node.odom_snapshot = ({'linear_speed_mps': linear, 'angular_speed_rps': angular},
                                  time.monotonic())

    def receive_speech(message):
        try:
            node.speech_snapshot = (json.loads(message.data), time.monotonic())
        except ValueError:
            pass
    node.create_subscription(String, 'heritage/simulation/speech', receive_speech, 10)
    node.create_subscription(String, 'heritage/visitor/tracks', receive_tracks, 10)
    node.create_subscription(String, 'heritage/visitor/team_observation', receive_vision_team, 10)
    node.create_subscription(CameraInfo, 'depth_camera/camera_info', receive_camera_info('rgb'),
                             qos_profile_sensor_data)
    node.create_subscription(CameraInfo, 'camera/depth/camera_info', receive_camera_info('depth'),
                             qos_profile_sensor_data)
    node.create_subscription(Image, 'camera/depth/image_raw', receive_depth_image,
                             qos_profile_sensor_data)
    node.create_subscription(LaserScan, 'scan', receive_scan, qos_profile_sensor_data)
    node.create_subscription(PerceptionInput, 'heritage/perception/fused', receive_fused, 10)
    node.create_subscription(Twist, 'cmd_vel', receive_cmd_vel, 10)
    node.create_subscription(Odometry, 'odom', receive_odom, 10)
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
            now = time.monotonic()
            data['evidence'] = {
                'tracks': snapshot_payload(*node.track_snapshot, now, 1.0),
                'team_observation': snapshot_payload(*node.vision_team_snapshot, now, 1.0),
                'rgb_camera_info': snapshot_payload(*node.rgb_info_snapshot, now, 2.0),
                'depth_camera_info': snapshot_payload(*node.depth_info_snapshot, now, 2.0),
                'depth_image': snapshot_payload(*node.depth_image_snapshot, now, 1.0),
                'scan': snapshot_payload(*node.scan_snapshot, now, 0.5),
                'fused': snapshot_payload(*node.fused_snapshot, now, 1.0),
                'cmd_vel': snapshot_payload(*node.cmd_vel_snapshot, now, 0.5),
                'odom': snapshot_payload(*node.odom_snapshot, now, 0.5),
                'nav2_limit_readback': {'valid': False, 'value_mps': None,
                                         'reason': '当前 SetNavigationSpeed 接口未提供独立限速回读'},
            }
            try:
                camera_transform = buffer.lookup_transform('base_footprint',
                                                           'depth_camera_optical_frame',
                                                           rclpy.time.Time())
                camera_stamp_ns = (camera_transform.header.stamp.sec * 1_000_000_000 +
                                   camera_transform.header.stamp.nanosec)
                camera_tf = transform_summary(
                    target_frame=camera_transform.header.frame_id,
                    source_frame=camera_transform.child_frame_id,
                    translation=(camera_transform.transform.translation.x,
                                 camera_transform.transform.translation.y,
                                 camera_transform.transform.translation.z),
                    rotation=(camera_transform.transform.rotation.x,
                              camera_transform.transform.rotation.y,
                              camera_transform.transform.rotation.z,
                              camera_transform.transform.rotation.w),
                    stamp_ns=camera_stamp_ns,
                    current_ros_time_ns=int(node.sim_seconds * 1_000_000_000))
                data['evidence']['camera_tf'] = {
                    'fresh': camera_tf['valid'], 'age_sec': camera_tf['age_sec'],
                    'value': camera_tf}
            except Exception:
                data['evidence']['camera_tf'] = {'fresh': False, 'age_sec': None, 'value': None}
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
