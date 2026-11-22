"""ROS Nav2 transport: only for the local Gazebo simulation."""
import asyncio
import math
import time
from threading import Lock

import rclpy
from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from rcl_interfaces.srv import GetParameters, SetParameters
from rclpy.parameter import Parameter
from rclpy.action import ActionClient
from rclpy.node import Node
from temi_interfaces.msg import SafetyStopStatus
from tf2_ros import Buffer, TransformException, TransformListener

_ODOM_FUTURE_STAMP_TOLERANCE_SEC = 0.15


def arrival_stop_confirmed(stable_since, last_sample, now,
                           stationary_window_sec=0.5, freshness_sec=0.5):
    if stable_since is None:
        return False
    values = (stable_since, last_sample, now, stationary_window_sec, freshness_sec)
    if any(not math.isfinite(value) for value in values):
        return False
    return (stable_since <= last_sample <= now and
            now - last_sample <= freshness_sec and
            now - stable_since >= stationary_window_sec)


class Nav2Transport(Node):
    def __init__(self):
        super().__init__('heritage_nav2_transport')
        self.set_parameters([rclpy.parameter.Parameter('use_sim_time', value=True)])
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self._controller_get = self.create_client(GetParameters, 'controller_server/get_parameters')
        self._controller_set = self.create_client(SetParameters, 'controller_server/set_parameters')
        self._smoother_get = self.create_client(GetParameters, 'velocity_smoother/get_parameters')
        self._smoother_set = self.create_client(SetParameters, 'velocity_smoother/set_parameters')
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.create_subscription(Odometry, 'odom', self._odom, 10)
        self._mutex = Lock()
        self._last_odom = 0.0
        self._last_odom_stamp_ns = 0
        self._odom_initial_age = math.inf
        self._linear = self._angular = float('inf')
        self._arrival_stable_since = None
        self._pending = self._goal = self._result = None
        self._abort = False
        self._unsafe = False
        self._stop_lock = asyncio.Lock()
        self._navigation_session_id = ''
        self._stop_session_id = ''
        self._stop_state = 'CLEAR'
        self._stop_reason = '无停车请求'
        self._stop_action_terminal = False
        self._stop_stable_since = None
        self._stop_was_confirmed = False
        self._stop_status = self.create_publisher(
            SafetyStopStatus, 'heritage/safety_stop/status', 10)
        self.create_timer(0.1, self._publish_stop_status)

    def _odom(self, msg):
        with self._mutex:
            now = time.monotonic()
            if self._stop_state == 'STOP_CONFIRMED':
                self._stop_was_confirmed = True
            stamp = msg.header.stamp
            stamp_ns = stamp.sec * 10**9 + stamp.nanosec
            age_ns = self.get_clock().now().nanoseconds - stamp_ns
            if (stamp_ns <= self._last_odom_stamp_ns or
                    not -_ODOM_FUTURE_STAMP_TOLERANCE_SEC * 1e9 <= age_ns <= 500_000_000):
                self._last_odom = 0.0
                self._linear = self._angular = math.inf
                self._arrival_stable_since = self._stop_stable_since = None
                if self._stop_state == 'STOP_CONFIRMED':
                    self._stop_state = 'STOPPING'
                    self._stop_reason = '里程计样本过期或倒序，等待重新静止确认'
                return
            gap = self._odom_age(now) > 0.5
            if gap:
                self._arrival_stable_since = self._stop_stable_since = None
            self._last_odom_stamp_ns = stamp_ns
            self._odom_initial_age = max(0.0, age_ns / 1e9)
            self._last_odom = now
            self._linear = math.hypot(msg.twist.twist.linear.x, msg.twist.twist.linear.y)
            self._angular = abs(msg.twist.twist.angular.z)
            stationary = self._linear < 0.02 and self._angular < 0.05
            if stationary:
                self._arrival_stable_since = self._arrival_stable_since or self._last_odom
            else:
                self._arrival_stable_since = None
            if self._stop_was_confirmed and not stationary:
                self._stop_state = 'STOP_FAILED'
                self._stop_stable_since = None
                self._stop_reason = '停车确认后速度反馈再次显示机器人运动'
                self._unsafe = True
            elif self._stop_state == 'STOPPING':
                if stationary:
                    self._stop_stable_since = self._stop_stable_since or self._last_odom
                else:
                    self._stop_stable_since = None
            elif self._stop_state == 'STOP_CONFIRMED' and gap:
                self._stop_state = 'STOPPING'
                self._stop_reason = '里程计断流，等待重新静止确认'
                self._stop_stable_since = now
            if (self._stop_state == 'STOPPING' and self._stop_action_terminal and
                    arrival_stop_confirmed(self._stop_stable_since, now, now)):
                self._stop_state = 'STOP_CONFIRMED'
                self._stop_was_confirmed = True
                self._stop_reason = 'Nav2 Action 终止且新鲜里程计重新连续静止 0.5 秒'

    def _odom_age(self, now):
        received_age = now - self._last_odom if self._last_odom else math.inf
        stamp_age = (self.get_clock().now().nanoseconds - self._last_odom_stamp_ns) / 1e9
        return (max(received_age + self._odom_initial_age, max(0.0, stamp_age))
                if received_age >= 0 and
                stamp_age >= -_ODOM_FUTURE_STAMP_TOLERANCE_SEC else math.inf)

    def set_navigation_session_id(self, session_id):
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError('导航会话 ID 不能为空')
        with self._mutex:
            if self._unsafe:
                raise RuntimeError('停车故障已锁存，拒绝建立新导航会话')
            if session_id != self._navigation_session_id:
                self._navigation_session_id = session_id
                self._stop_session_id = session_id
                self._stop_state = 'CLEAR'
                self._stop_reason = '当前导航会话未请求停车'
                self._stop_action_terminal = False
                self._stop_stable_since = None
                self._stop_was_confirmed = False

    def _publish_stop_status(self):
        now = time.monotonic()
        with self._mutex:
            age = self._odom_age(now)
            state = self._stop_state
            stable = (now - self._stop_stable_since
                      if self._stop_stable_since is not None else 0.0)
            linear, angular = self._linear, self._angular
            session_id = (self._stop_session_id if state != 'CLEAR'
                          else self._navigation_session_id)
            action_terminal = self._stop_action_terminal
            reason = self._stop_reason
        valid = (state != 'CLEAR' or
                 (age <= 0.5 and self.client.server_is_ready()))
        if state == 'STOP_CONFIRMED':
            valid = (age <= 0.5 and action_terminal and stable >= 0.5 and
                     linear < 0.02 and angular < 0.05)
        message = SafetyStopStatus()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = 'base_footprint'
        message.source = 'gazebo_nav2_transport'
        message.state = state
        message.navigation_session_id = session_id
        message.reason = reason
        message.valid = bool(valid)
        message.action_terminal = bool(action_terminal)
        message.linear_speed_mps = float(linear if math.isfinite(linear) else 0.0)
        message.angular_speed_rps = float(angular if math.isfinite(angular) else 0.0)
        message.odom_age_sec = float(max(0.0, age) if math.isfinite(age) else 1e6)
        message.stopped_duration_sec = float(max(0.0, stable))
        self._stop_status.publish(message)

    def ready(self):
        with self._mutex:
            fresh = self._odom_age(time.monotonic()) <= 0.5
        return bool(not self._unsafe and fresh and self.client.server_is_ready() and
                    self._fresh_transform() is not None)

    def _fresh_transform(self):
        try:
            value = self.buffer.lookup_transform('map', 'base_footprint', rclpy.time.Time())
        except TransformException:
            return None
        stamp = value.header.stamp
        stamp_ns = stamp.sec * 10**9 + stamp.nanosec
        age_ns = self.get_clock().now().nanoseconds - stamp_ns
        return (value if stamp_ns > 0 and
                -_ODOM_FUTURE_STAMP_TOLERANCE_SEC * 1e9 <= age_ns <= 500_000_000
                else None)

    def snapshot(self):
        value = self._fresh_transform()
        if value is None:
            return None
        t = value.transform
        q = t.rotation
        with self._mutex:
            moving = self._linear >= 0.02 or self._angular >= 0.05
        return {'x': t.translation.x, 'y': t.translation.y,
                'yaw': math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z)),
                'moving': moving}

    async def _future(self, future, timeout):
        end = time.monotonic() + timeout
        while not future.done():
            if time.monotonic() >= end:
                raise TimeoutError('Nav2 响应超时')
            await asyncio.sleep(0.02)
        return future.result()

    async def _wait_for_arrival_stop(self, timeout_sec=5.0):
        deadline = time.monotonic() + timeout_sec
        while not self._abort and time.monotonic() < deadline:
            now = time.monotonic()
            with self._mutex:
                confirmed = arrival_stop_confirmed(
                    self._arrival_stable_since, self._last_odom, now) and self._odom_age(now) <= 0.5
            if confirmed:
                return True
            await asyncio.sleep(0.05)
        return False

    async def navigate(self, pose, *, on_active=None):
        if self._unsafe or self._pending is not None:
            return False
        self._abort = False
        request = NavigateToPose.Goal()
        request.pose.header.frame_id = 'map'
        request.pose.header.stamp = self.get_clock().now().to_msg()
        request.pose.pose.position.x = float(pose['x'])
        request.pose.pose.position.y = float(pose['y'])
        request.pose.pose.orientation.z = math.sin(float(pose['yaw']) / 2)
        request.pose.pose.orientation.w = math.cos(float(pose['yaw']) / 2)
        self._pending = self.client.send_goal_async(request)
        try:
            self._goal = await self._future(self._pending, 5)
            if not self._goal.accepted:
                return False
            if on_active is not None:
                on_active()
            self._result = self._goal.get_result_async()
            if self._abort:
                return False
            result = await self._future(self._result, 3600)
            if result.status != GoalStatus.STATUS_SUCCEEDED or self._abort:
                return False
            return await self._wait_for_arrival_stop()
        except TimeoutError:
            self._unsafe = True
            return False
        finally:
            if not self._abort and self._result is not None and self._result.done():
                self._pending = self._goal = self._result = None

    async def set_speed(self, target_speed_mps):
        """调整 Nav2 目标线速度上限；真实 temi SDK 不经过此 Gazebo 专用 transport。"""
        if not math.isfinite(target_speed_mps) or not 0.3 <= target_speed_mps <= 0.8:
            return False
        clients = (self._controller_get, self._controller_set,
                   self._smoother_get, self._smoother_set)
        if not all(client.service_is_ready() for client in clients):
            return False
        controller_response = await self._future(self._controller_get.call_async(
            GetParameters.Request(names=['FollowPath.max_vel_x', 'FollowPath.max_speed_xy'])), 3.0)
        if (len(controller_response.values) != 2 or
                any(not math.isfinite(value.double_value) or value.double_value <= 0
                    for value in controller_response.values)):
            return False
        old_controller = [value.double_value for value in controller_response.values]
        smoother_request = GetParameters.Request(names=['max_velocity'])
        smoother_response = await self._future(self._smoother_get.call_async(smoother_request), 3.0)
        if not smoother_response.values or not smoother_response.values[0].double_array_value:
            return False
        velocities = list(smoother_response.values[0].double_array_value)
        old_smoother = list(velocities)
        velocities[0] = float(target_speed_mps)
        async def write_params(controller, smoother):
            return await asyncio.gather(
                self._future(self._controller_set.call_async(SetParameters.Request(parameters=[
                    Parameter('FollowPath.max_vel_x', value=controller[0]).to_parameter_msg(),
                    Parameter('FollowPath.max_speed_xy', value=controller[1]).to_parameter_msg()])), 3.0),
                self._future(self._smoother_set.call_async(SetParameters.Request(parameters=[
                    Parameter('max_velocity', value=smoother).to_parameter_msg()])), 3.0),
                return_exceptions=True,
            )

        def applied(responses):
            return all(not isinstance(response, BaseException) and len(response.results) == count and
                       all(item.successful for item in response.results)
                       for response, count in zip(responses, (2, 1)))

        async def readback_matches(controller, smoother):
            try:
                verify_controller, verify_smoother = await asyncio.gather(
                    self._future(self._controller_get.call_async(GetParameters.Request(
                        names=['FollowPath.max_vel_x', 'FollowPath.max_speed_xy'])), 3.0),
                    self._future(self._smoother_get.call_async(smoother_request), 3.0),
                )
            except Exception:
                return False
            actual_controller = [value.double_value for value in verify_controller.values]
            actual_smoother = (list(verify_smoother.values[0].double_array_value)
                               if verify_smoother.values else [])
            return (len(actual_controller) == len(controller) and len(actual_smoother) == len(smoother) and
                    all(math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-4)
                        for actual, expected in zip(actual_controller + actual_smoother,
                                                    controller + smoother)))

        requested = [float(target_speed_mps)] * 2
        result = await write_params(requested, velocities)
        if applied(result) and await readback_matches(requested, velocities):
            return True
        restored = await write_params(old_controller, old_smoother)
        if (not applied(restored) or not await readback_matches(old_controller, old_smoother) or
                any(isinstance(item, BaseException) for item in result)):
            self._unsafe = True  # Late writes can outlive a timeout; do not trust subsequent motion.
        return False

    async def stop(self):
        async with self._stop_lock:
            self._abort = True
            with self._mutex:
                if (self._stop_state == 'STOP_CONFIRMED' and self._stop_action_terminal and
                        self._stop_session_id == self._navigation_session_id and
                        self._odom_age(time.monotonic()) <= 0.5 and
                        arrival_stop_confirmed(self._stop_stable_since, self._last_odom, time.monotonic())):
                    return True
                self._stop_session_id = self._navigation_session_id
                self._stop_state = 'STOP_REQUESTED'
                self._stop_reason = 'Nav2 停车请求已提交'
                self._stop_action_terminal = self._pending is None
                self._stop_stable_since = None
            try:
                if self._pending is not None:
                    goal = self._goal or await self._future(self._pending, 5)
                    if goal.accepted:
                        result = self._result or goal.get_result_async()
                        if not result.done():
                            response = await self._future(goal.cancel_goal_async(), 5)
                            if not response.goals_canceling and not result.done():
                                raise RuntimeError('Nav2 未接受取消')
                            with self._mutex:
                                self._stop_state = 'STOP_COMMAND_ACCEPTED'
                                self._stop_reason = 'Nav2 已接受当前目标取消'
                        terminal = await self._future(result, 8)
                        if terminal.status not in (GoalStatus.STATUS_CANCELED,
                                                    GoalStatus.STATUS_SUCCEEDED,
                                                    GoalStatus.STATUS_ABORTED):
                            raise RuntimeError('Nav2 Action 未进入终态')
                    with self._mutex:
                        self._stop_action_terminal = True
                        self._stop_state = 'STOPPING'
                        self._stop_reason = ('Nav2 Action 已终止，等待里程计连续静止确认'
                                             if goal.accepted else 'Nav2 未接受目标；等待里程计连续静止确认')
                else:
                    with self._mutex:
                        self._stop_state = 'STOPPING'
                        self._stop_reason = '没有活动 Nav2 Action，等待里程计连续静止确认'
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    with self._mutex:
                        now = time.monotonic()
                        if (self._odom_age(now) <= 0.5 and
                                arrival_stop_confirmed(self._stop_stable_since, self._last_odom, now)):
                            self._stop_state = 'STOP_CONFIRMED'
                            self._stop_was_confirmed = True
                            self._stop_action_terminal = True
                            self._stop_reason = 'Nav2 Action 终止且新鲜里程计连续静止 0.5 秒'
                            self._pending = self._goal = self._result = None
                            return True
                    await asyncio.sleep(0.05)
                raise TimeoutError('没有足够的新鲜静止里程计')
            except Exception as error:
                with self._mutex:
                    self._stop_state = 'STOP_FAILED'
                    self._stop_reason = f'停车未确认：{error}'
                    self._stop_action_terminal = False
            self._unsafe = True
            return False
