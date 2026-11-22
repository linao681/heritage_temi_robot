"""ROS2 输入适配器；上游必须提供真实或明确标记的模拟感知数据。"""
import json
import math
import time

from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from std_srvs.srv import Trigger
from temi_interfaces.msg import NavigationStatus, PerceptionInput
from temi_interfaces.srv import SetNavigationSpeed, StopRobot

from .speed_policy import SpeedConfig, SpeedController, SpeedInputs, perception_source_allowed


class SpeedControllerNode(Node):
    def __init__(self):
        super().__init__('temi_speed_controller')
        defaults = SpeedConfig()
        for name, value in vars(defaults).items():
            self.declare_parameter(name, value)
        self.declare_parameter('mock_mode', False)
        self.declare_parameter('allow_simulated_sources', False)
        self._policy = SpeedController(SpeedConfig(**{
            name: self.get_parameter(name).value for name in vars(defaults)}))
        self._mock_mode = self.get_parameter('mock_mode').value
        self._allow_simulated_sources = self.get_parameter('allow_simulated_sources').value
        self._group = ReentrantCallbackGroup()
        self._speed_client = self.create_client(SetNavigationSpeed, 'temi/set_navigation_speed', callback_group=self._group)
        self._stop_client = self.create_client(StopRobot, 'temi/stop', callback_group=self._group)
        self._pause_client = self.create_client(Trigger, 'heritage/tour/pause', callback_group=self._group)
        self._resume_client = self.create_client(Trigger, 'heritage/tour/resume', callback_group=self._group)
        self.create_service(Trigger, 'heritage/speed_control/reset_error', self._reset_error, callback_group=self._group)
        self._tour_state = ''
        self._last_navigation_session_id = ''
        self._latest_navigation_session_id = ''
        self.create_subscription(String, 'heritage/tour/status', self._on_tour_status, 10)
        self.create_subscription(NavigationStatus, 'temi/navigation_status',
                                 self._on_navigation_status, 20,
                                 callback_group=self._group)
        self._input = None
        self._stop_confirmed = False
        self._stop_future = None
        self._speed_future = None
        self._resume_future = None
        self._resume_requested_at = None
        self._simulated_speed = 0.0
        self._odom_speed_mps = None
        self._odom_received_at = None
        self._last_tick = time.monotonic()
        self._status = self.create_publisher(String, 'heritage/speed_control/status', 10)
        self._commands = self.create_publisher(String, 'heritage/speed_control/commands', 10)
        self.create_subscription(String, 'heritage/speed_control/input', self._on_input, 10)
        self.create_subscription(PerceptionInput, 'heritage/perception/fused', self._on_fused_input, 10)
        self.create_subscription(Odometry, 'odom', self._on_odom, 10)
        self.create_timer(0.1, self._tick, callback_group=self._group)

    def _on_odom(self, message):
        linear = message.twist.twist.linear
        speed = math.hypot(linear.x, linear.y)
        if math.isfinite(speed):
            self._odom_speed_mps = speed
            self._odom_received_at = time.monotonic()

    def _reset_error(self, _request, response):
        self._policy.reset_error()
        response.success = True
        response.message = '速度控制错误已人工复位；检查故障原因后再继续导览'
        return response

    def _on_tour_status(self, message):
        try:
            value = json.loads(message.data)
            if isinstance(value, dict) and isinstance(value.get('state'), str):
                self._tour_state = value['state']
        except (ValueError, TypeError):
            pass

    def _on_navigation_status(self, message):
        if message.status in ('start', 'calculating', 'going', 'reposing'):
            self._latest_navigation_session_id = message.task_id
        elif message.task_id == self._latest_navigation_session_id:
            self._latest_navigation_session_id = ''

    def _on_input(self, message):
        try:
            value = json.loads(message.data)
            if not isinstance(value, dict):
                return
            required_bool = ('navigating', 'explaining', 'navigation_error', 'safety_stop',
                             'position_valid', 'communication_valid')
            if any(type(value.get(key)) is not bool for key in required_bool):
                return
            for key in ('nearest_person_m', 'crowd_density', 'obstacle_distance_m', 'sample_age_sec',
                        'person_distance_timestamp_sec'):
                item = value.get(key)
                if item is not None and (type(item) not in (int, float) or not math.isfinite(item)):
                    return
            if not isinstance(value.get('group_state'), str) or not isinstance(value.get('navigation_session_id'), str):
                return
            if type(value.get('sample_age_sec')) not in (int, float) or value['sample_age_sec'] < 0:
                return
            source = value.get('source', '')
            if not isinstance(source, str):
                return
            value['source_allowed'] = perception_source_allowed(
                source, mock_mode=self._mock_mode,
                allow_simulated_sources=self._allow_simulated_sources)
            for key in ('people_valid', 'person_distance_valid', 'crowd_density_valid',
                        'obstacle_distance_valid', 'safety_stop_valid'):
                if key in value and type(value[key]) is not bool:
                    return
                value.setdefault(key, value['source_allowed'])
            value.setdefault('people_valid', value['source_allowed'])
            value['received_at'] = time.monotonic()
            self._input = value
        except (TypeError, ValueError, OverflowError):
            return

    def _on_fused_input(self, message):
        session_id = message.navigation_session_id
        if session_id and session_id != self._last_navigation_session_id:
            self._last_navigation_session_id = session_id
        confirmed_session_id = message.stop_confirmed_session_id
        self._stop_confirmed = bool(message.stop_confirmed and message.safety_stop_valid and
                                    confirmed_session_id and
                                    confirmed_session_id == self._last_navigation_session_id)
        source = message.source
        source_allowed = perception_source_allowed(
            source, mock_mode=self._mock_mode,
            allow_simulated_sources=self._allow_simulated_sources)
        self._input = {
            'source': source, 'source_allowed': source_allowed,
            'sample_age_sec': float(message.sample_age_sec), 'received_at': time.monotonic(),
            'person_distance_timestamp_sec': float(message.sample_timestamp_monotonic_sec),
            'nearest_person_m': float(message.nearest_person_m) if message.person_distance_valid else None,
            'crowd_density': float(message.crowd_density) if message.crowd_density_valid else None,
            'obstacle_distance_m': float(message.obstacle_distance_m) if message.obstacle_distance_valid else None,
            'people_valid': bool(message.people_valid),
            'person_observation_state': message.person_observation_state,
            'person_observation_valid': bool(message.person_observation_valid),
            'person_distance_valid': bool(message.person_distance_valid),
            'crowd_density_valid': bool(message.crowd_density_valid),
            'obstacle_distance_valid': bool(message.obstacle_distance_valid),
            'safety_stop_valid': bool(message.safety_stop_valid),
            'group_state': message.group_state, 'navigating': bool(message.navigating),
            'explaining': bool(message.explaining), 'navigation_error': bool(message.navigation_error),
            'safety_stop': bool(message.safety_stop), 'position_valid': bool(message.position_valid),
            'communication_valid': bool(message.communication_valid),
            'navigation_session_id': session_id,
            'stop_confirmed_session_id': confirmed_session_id, 'manual_stop': False,
        }

    def _send_stop(self):
        if self._stop_future is not None and not self._stop_future.done():
            return
        if self._pause_client.service_is_ready():
            self._stop_future = self._pause_client.call_async(Trigger.Request())
            self._stop_future.add_done_callback(self._on_pause_result)
            return
        if not self._stop_client.service_is_ready():
            self._policy.report_stop_result(False)
            return
        self._stop_future = self._stop_client.call_async(StopRobot.Request(stop=True))
        self._stop_future.add_done_callback(self._on_stop_result)

    def _on_pause_result(self, future):
        try:
            response = future.result()
            if not response.success:
                self._policy.report_stop_result(False)
        except Exception:
            self._policy.report_stop_result(False)

    def _on_resume_result(self, future):
        try:
            if not future.result().success:
                self._policy.report_stop_result(False)
                self._resume_requested_at = None
        except Exception:
            self._policy.report_stop_result(False)
            self._resume_requested_at = None

    def _on_stop_result(self, future):
        try:
            response = future.result()
            if not response.success:
                self._stop_confirmed = False
                self._policy.report_stop_result(False)
        except Exception:
            self._stop_confirmed = False
            self._policy.report_stop_result(False)

    def _set_speed(self, decision):
        if self._speed_future is not None and not self._speed_future.done():
            return 'previous_command_pending'
        if not self._speed_client.service_is_ready():
            self.get_logger().error('调速服务未就绪；当前导航目标速度未确认')
            self._policy.report_speed_result(False)
            return 'service_unavailable'
        request = SetNavigationSpeed.Request(command_id=decision.command_id,
                                             navigation_session_id=decision.navigation_session_id,
                                             target_speed_mps=float(decision.target_speed_mps),
                                             control_reason=decision.reason)
        future = self._speed_future = self._speed_client.call_async(request)
        def completed(done):
            try:
                result = done.result()
                outcome = {'command_id': decision.command_id, 'status': 'complete' if result.success else 'error',
                           'requested_target_speed_mps': decision.target_speed_mps,
                           'sdk_return_code': result.sdk_return_code, 'message': result.message,
                           'navigation_session_id': decision.navigation_session_id}
            except Exception as error:
                outcome = {'command_id': decision.command_id, 'status': 'error',
                           'requested_target_speed_mps': decision.target_speed_mps,
                           'sdk_return_code': None, 'message': str(error),
                           'navigation_session_id': decision.navigation_session_id}
            self._commands.publish(String(data=json.dumps(outcome, ensure_ascii=False)))
            self._policy.report_speed_result(
                outcome['status'] == 'complete',
                navigation_session_id=decision.navigation_session_id,
                current_navigation_session_id=self._latest_navigation_session_id,
                recovery_command=decision.state == 'RECOVERING')
        future.add_done_callback(completed)
        return 'sent_pending_confirmation'

    def _tick(self):
        now = time.monotonic()
        raw = self._input or {}
        age = now - raw.get('received_at', -math.inf)
        odom_age = now - self._odom_received_at if self._odom_received_at is not None else math.inf
        odom_valid = odom_age <= 0.5
        person_observation_valid = raw.get('person_observation_valid')
        if type(person_observation_valid) is not bool:
            person_observation_valid = (raw.get('person_distance_valid') is True or
                                        raw.get('person_observation_state') == 'NO_PERSON_OBSERVED')
        inputs = SpeedInputs(
            now=raw.get('received_at', -math.inf),
            nearest_person_m=raw.get('nearest_person_m'), crowd_density=raw.get('crowd_density'),
            obstacle_distance_m=raw.get('obstacle_distance_m'), group_state=raw.get('group_state', 'unknown'),
            navigating=raw.get('navigating', False), explaining=raw.get('explaining', False),
            navigation_error=raw.get('navigation_error', False), safety_stop=raw.get('safety_stop', False),
            position_valid=raw.get('position_valid', False), communication_valid=raw.get('communication_valid', False),
            stop_confirmed=bool(self._stop_confirmed and age <= 0.5),
            stop_confirmed_session_id=raw.get('stop_confirmed_session_id', ''),
            navigation_session_id=raw.get('navigation_session_id', ''),
            manual_stop=raw.get('manual_stop', False), sample_age_sec=raw.get('sample_age_sec', math.inf),
            source_allowed=raw.get('source_allowed', False),
            people_valid=person_observation_valid,
            person_distance_valid=raw.get('person_distance_valid', False),
            crowd_density_valid=raw.get('crowd_density_valid', False),
            obstacle_distance_valid=raw.get('obstacle_distance_valid', False),
            safety_stop_valid=raw.get('safety_stop_valid', False),
            person_observation_state=raw.get('person_observation_state', 'PERSON_DISTANCE_VALID'),
            person_distance_timestamp_sec=raw.get('person_distance_timestamp_sec'),
            current_speed_mps=self._odom_speed_mps if odom_valid else None,
            current_speed_valid=odom_valid)
        decision = self._policy.update(inputs, now)
        if self._tour_state == 'NAVIGATING':
            self._resume_requested_at = None
        if decision.stop_requested:
            self._stop_confirmed = False
            self._send_stop()
        outcome = 'not_sent'
        if decision.send_speed:
            outcome = self._set_speed(decision)
        if decision.resume_requested:
            if self._resume_client.service_is_ready():
                self._resume_requested_at = now
                self._resume_future = self._resume_client.call_async(Trigger.Request())
                self._resume_future.add_done_callback(self._on_resume_result)
            else:
                self._policy.report_stop_result(False)
        if (self._resume_requested_at is not None and self._tour_state != 'NAVIGATING' and
                now - self._resume_requested_at > 15.0):
            self._policy.report_stop_result(False)
            self._resume_requested_at = None
        dt = max(0.0, now - self._last_tick)
        self._last_tick = now
        if self._mock_mode:
            target = decision.target_speed_mps or 0.0
            delta = min(0.2 * dt, max(-0.5 * dt, target - self._simulated_speed))
            self._simulated_speed = max(0.0, self._simulated_speed + delta)
        else:
            self._simulated_speed = None
        message = {
            'state': decision.state, 'target_speed_mps': decision.target_speed_mps,
            'tour_state': self._tour_state, 'resume_requested': decision.resume_requested,
            'simulated_actual_speed_mps': self._simulated_speed,
            'actual_speed_source': 'simulation' if self._mock_mode else None,
            'stop_requested': decision.stop_requested, 'stop_confirmed': self._stop_confirmed,
            'reason': decision.reason, 'navigation_session_id': decision.navigation_session_id,
            'command_status': outcome, 'input_age_sec': age,
            'dynamic_stop_distance_m': decision.dynamic_stop_distance_m,
            'approach_speed_mps': decision.approach_speed_mps,
            'current_robot_speed_mps': self._odom_speed_mps if odom_valid else None,
            'current_robot_speed_source': 'odom' if odom_valid else 'configured_default_estimate',
            'input_source': raw.get('source', ''),
            'input_valid': bool(raw.get('source_allowed', False) and person_observation_valid and
                                raw.get('obstacle_distance_valid', False) and raw.get('safety_stop_valid', False)),
            'visitor_count_valid': bool(raw.get('people_valid', False)),
            'crowd_density_valid': bool(raw.get('crowd_density_valid', False)),
            'nearest_person_m': raw.get('nearest_person_m'), 'crowd_density': raw.get('crowd_density'),
            'obstacle_distance_m': raw.get('obstacle_distance_m'), 'group_state': raw.get('group_state', 'unknown')}
        self._status.publish(String(data=json.dumps(message, ensure_ascii=False)))
        if decision.state == 'ERROR':
            self.get_logger().error(f'速度控制 ERROR: {decision.reason}')
        elif decision.stop_requested:
            self.get_logger().warning(f'请求导航停止: {decision.reason}')


def main(args=None):
    import rclpy
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.signals import SignalHandlerOptions
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = SpeedControllerNode()
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()
