"""ROS2 输入适配器；上游必须提供真实或明确标记的模拟感知数据。"""
import json
import math
import time
import uuid

from rclpy.clock import Clock, ClockType
from rclpy.parameter import Parameter
from rclpy.node import Node
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from std_srvs.srv import Trigger
from temi_interfaces.msg import NavigationStatus, PerceptionInput
from temi_interfaces.srv import SetNavigationSpeed, StopRobot

from .speed_policy import SpeedConfig, SpeedController, SpeedInputs, perception_source_allowed

_ODOM_FUTURE_STAMP_TOLERANCE_SEC = 0.15


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
        if self._allow_simulated_sources and not self._mock_mode:
            self.set_parameters([Parameter('use_sim_time', value=True)])
        self._group = self.default_callback_group
        self._speed_client = self.create_client(SetNavigationSpeed, 'temi/set_navigation_speed', callback_group=self._group)
        self._stop_client = self.create_client(StopRobot, 'temi/stop', callback_group=self._group)
        self._pause_client = self.create_client(Trigger, 'heritage/tour/pause', callback_group=self._group)
        self._safety_pause_client = self.create_client(Trigger, 'heritage/tour/pause_safety')
        self._team_pause_client = self.create_client(Trigger, 'heritage/tour/visitor_lost')
        self._resume_client = self.create_client(Trigger, 'heritage/tour/resume_safety')
        self.create_service(Trigger, 'heritage/speed_control/reset_error', self._reset_error, callback_group=self._group)
        self._tour_state = ''
        self._tour_status = {}
        self._tour_received_at = -math.inf
        self._last_navigation_session_id = ''
        self._latest_navigation_session_id = ''
        self._latest_navigation_target = ''
        self.create_subscription(String, 'heritage/tour/status', self._on_tour_status, 10)
        self.create_subscription(NavigationStatus, 'temi/navigation_status',
                                 self._on_navigation_status, 20,
                                 callback_group=self._group)
        self._input = None
        self._stop_confirmed = False
        self._stop_future = None
        self._speed_future = None
        self._resume_future = None
        self._resume_future_decision_id = None
        self._resume_requested_at = None
        self._recovery = None
        self._simulated_speed = 0.0
        self._odom_speed_mps = None
        self._odom_angular_rps = None
        self._odom_received_at = None
        self._odom_stamp_ns = 0
        self._odom_source_age_at_receive = math.inf
        self._last_tick = time.monotonic()
        self._status = self.create_publisher(String, 'heritage/speed_control/status', 10)
        self._commands = self.create_publisher(String, 'heritage/speed_control/commands', 10)
        self.create_subscription(String, 'heritage/speed_control/input', self._on_input, 10)
        self.create_subscription(PerceptionInput, 'heritage/perception/fused', self._on_fused_input, 10)
        self.create_subscription(Odometry, 'odom', self._on_odom, 10)
        self.create_timer(0.1, self._tick, callback_group=self._group,
                          clock=Clock(clock_type=ClockType.STEADY_TIME))

    def _on_odom(self, message):
        now = time.monotonic()
        stamp = message.header.stamp
        stamp_ns = stamp.sec * 10**9 + stamp.nanosec
        age_ns = self.get_clock().now().nanoseconds - stamp_ns
        linear = message.twist.twist.linear
        speed = math.hypot(linear.x, linear.y)
        angular = abs(message.twist.twist.angular.z)
        fresh = (stamp_ns > self._odom_stamp_ns and
                 -_ODOM_FUTURE_STAMP_TOLERANCE_SEC * 1e9 <= age_ns <= 500_000_000 and
                 math.isfinite(speed) and math.isfinite(angular))
        if (not fresh or speed >= 0.02 or angular >= 0.05 or
                self._odom_received_at is not None and self._odom_age(now) > 0.5):
            self._policy.interrupt_recovery()
        if fresh:
            self._odom_stamp_ns = stamp_ns
            self._odom_source_age_at_receive = max(0.0, age_ns / 1e9)
            self._odom_speed_mps = speed
            self._odom_angular_rps = angular
            self._odom_received_at = now
        else:
            self._odom_received_at = None

    def _odom_age(self, now):
        if self._odom_received_at is None:
            return math.inf
        receipt_age = now - self._odom_received_at
        source_age = (self.get_clock().now().nanoseconds - self._odom_stamp_ns) / 1e9
        return (max(receipt_age + self._odom_source_age_at_receive, max(0.0, source_age))
                if receipt_age >= 0 and
                source_age >= -_ODOM_FUTURE_STAMP_TOLERANCE_SEC else math.inf)

    def _reset_error(self, _request, response):
        self._policy.reset_error()
        self._recovery = None
        self._resume_requested_at = None
        response.success = True
        response.message = '速度控制错误已人工复位；检查故障原因后再继续导览'
        return response

    def _on_tour_status(self, message):
        try:
            value = json.loads(message.data)
            if isinstance(value, dict) and isinstance(value.get('state'), str):
                self._tour_state = value['state']
                self._tour_status = value
                self._tour_received_at = time.monotonic()
        except (ValueError, TypeError):
            pass

    def _on_navigation_status(self, message):
        if message.status in ('start', 'calculating', 'going', 'reposing'):
            self._latest_navigation_session_id = message.task_id
            self._latest_navigation_target = message.target
        elif message.task_id == self._latest_navigation_session_id:
            self._latest_navigation_session_id = ''
            self._latest_navigation_target = ''

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
        now = time.monotonic()
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
        if not message.navigating:
            config = self._policy.config
            previous_stamp = self._input.get('person_distance_timestamp_sec') if self._input else None
            clear_person = (message.person_observation_valid and (
                message.person_observation_state == 'NO_PERSON_OBSERVED' or
                message.person_distance_valid and math.isfinite(message.nearest_person_m) and
                message.nearest_person_m > self._policy.recovery_person_minimum_m))
            clear_laser = (message.obstacle_distance_valid and math.isfinite(message.obstacle_distance_m) and
                           message.obstacle_distance_m > config.stop_obstacle_distance_m +
                           config.clear_distance_hysteresis_m)
            if (not message.valid or not source_allowed or not self._stop_confirmed or message.safety_stop or
                    not message.position_valid or not message.communication_valid or message.navigation_error or
                    message.explaining or message.group_state == 'lost' or
                    not clear_person or not clear_laser or
                    not 0 <= message.sample_age_sec <= config.input_timeout_sec or
                    not 0 <= now - message.sample_timestamp_monotonic_sec <= config.input_timeout_sec or
                    previous_stamp is not None and message.sample_timestamp_monotonic_sec < previous_stamp):
                self._policy.interrupt_recovery()
        self._input = {
            'source': source, 'source_allowed': source_allowed,
            'perception_valid': bool(message.valid),
            'sample_age_sec': float(message.sample_age_sec), 'received_at': now,
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

    def _send_stop(self, decision):
        if self._stop_future is not None and not self._stop_future.done():
            return
        if decision.reason == '游客掉队等待':
            pause = self._team_pause_client
        elif decision.state != 'ERROR' and self._tour_state in ('NAVIGATING', 'RETURNING'):
            pause = self._safety_pause_client
        elif (self._tour_state == 'PAUSED' or decision.state != 'ERROR' and
              self._tour_state in ('EXPLAINING', 'QA', 'GREETING', 'WAITING_CONSENT', 'IDLE', 'COMPLETED')):
            pause = None
        else:
            pause = self._pause_client
        if pause is not None and pause.service_is_ready():
            self._stop_future = pause.call_async(Trigger.Request())
            self._stop_future.add_done_callback(self._on_pause_result)
            return
        self._send_stop_direct()

    def _send_stop_direct(self):
        if not self._stop_client.service_is_ready():
            self._policy.report_stop_result(False)
            return
        self._stop_future = self._stop_client.call_async(StopRobot.Request(stop=True))
        self._stop_future.add_done_callback(self._on_stop_result)

    def _on_pause_result(self, future):
        try:
            accepted = bool(future.result().success)
        except Exception:
            accepted = False
        if not accepted and future is self._stop_future:
            self._send_stop_direct()

    def _on_resume_result(self, future, decision_id=None):
        if future is not self._resume_future:
            return
        self._resume_future = None
        self._resume_future_decision_id = None
        if self._recovery is None or self._recovery['decision_id'] != decision_id:
            return
        try:
            accepted = bool(future.result().success)
        except Exception:
            accepted = False
        self._recovery['service_result'] = 'accepted' if accepted else 'rejected'
        if not accepted:
            self._policy.reject_resume(self._recovery['stopped_session_id'])
            self._resume_requested_at = None

    def _maybe_send_resume(self, now):
        proposal = self._recovery
        if (proposal is None or self._resume_future is not None or
                proposal['request_sent_at'] is not None or
                not self._tour_allows_recovery(proposal['stopped_session_id'], now) or
                self._tour_status.get('recovery_ack_id') != proposal['decision_id'] or
                not self._resume_client.service_is_ready()):
            return
        proposal['request_sent_at'] = self._resume_requested_at = now
        decision_id = proposal['decision_id']
        self._resume_future_decision_id = decision_id
        self._resume_future = self._resume_client.call_async(Trigger.Request())
        self._resume_future.add_done_callback(lambda future: self._on_resume_result(future, decision_id))

    def _tour_allows_recovery(self, session_id, now):
        return (bool(session_id) and 0 <= now - self._tour_received_at <= 0.5 and
                self._tour_status.get('state') == 'PAUSED' and
                self._tour_status.get('pause_source') == 'safety' and
                self._tour_status.get('paused_session_id') == session_id)

    def _on_stop_result(self, future):
        try:
            response = future.result()
            if not response.success:
                self.get_logger().error(f'停车接口拒绝: {response.message}')
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
            if outcome['status'] != 'complete':
                self.get_logger().error('调速接口未完成: '+json.dumps(outcome, ensure_ascii=False))
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
        odom_age = self._odom_age(now)
        odom_valid = 0 <= odom_age <= 0.5
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
            current_speed_valid=odom_valid,
            current_angular_speed_rps=self._odom_angular_rps if odom_valid else math.inf,
            auto_resume_permitted=(raw.get('perception_valid', False) and
                self._tour_allows_recovery(raw.get('stop_confirmed_session_id', ''), now)))
        decision = self._policy.update(inputs, now)
        if decision.stop_requested:
            self._stop_confirmed = False
            self._send_stop(decision)
        outcome = 'not_sent'
        if decision.send_speed:
            outcome = self._set_speed(decision)
        if decision.resume_requested:
            self._recovery = {
                'decision_id': uuid.uuid4().hex, 'stopped_session_id': decision.stopped_session_id,
                'original_target': self._tour_status.get('target'),
                'clear_since': decision.recovery_clear_since,
                'hold_sec': self._policy.config.recovery_hold_sec,
                'request_sent_at': None, 'service_result': None, 'new_session_id': None,
                'manual_latched': False, 'error_latched': False,
            }
        eligible = (self._recovery is not None and decision.state == 'RECOVERING' and
                    decision.recovery_clear_since is not None and not decision.navigation_session_id and
                    self._recovery['stopped_session_id'] == decision.stopped_session_id and
                    (self._resume_future is None or
                     self._resume_future_decision_id == self._recovery['decision_id']))
        if eligible:
            sample_age = inputs.sample_age_sec + age
            self._recovery.update(
                evidence_sample_id=inputs.person_distance_timestamp_sec, sample_age_sec=sample_age,
                odom_age_sec=odom_age, position_age_sec=sample_age,
                evidence_at=now, input_timeout_sec=self._policy.config.input_timeout_sec,
                minimum_person_distance_m=max(self._policy.config.stop_person_distance_m,
                    decision.dynamic_stop_distance_m) + self._policy.config.clear_distance_hysteresis_m,
                minimum_laser_distance_m=self._policy.config.stop_obstacle_distance_m +
                    self._policy.config.clear_distance_hysteresis_m)
            self._maybe_send_resume(now)
        elif self._recovery and self._resume_requested_at is not None:
            if self._latest_navigation_session_id and (
                    self._latest_navigation_session_id != self._recovery['stopped_session_id'] and
                    self._latest_navigation_target == self._recovery['original_target'] and
                    self._recovery['service_result'] == 'accepted'):
                self._recovery['new_session_id'] = self._latest_navigation_session_id
                self._resume_requested_at = None
        if self._resume_requested_at is not None and now - self._resume_requested_at > 15.0:
            self._policy.reject_resume(self._recovery['stopped_session_id'])
            self._recovery['service_result'] = 'timeout'
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
            'recovery_eligible': eligible, 'recovery': self._recovery,
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
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.signals import SignalHandlerOptions
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = SpeedControllerNode()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()
