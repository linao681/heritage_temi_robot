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
from tf2_ros import Buffer, TransformListener


class Nav2Transport(Node):
    def __init__(self):
        super().__init__('heritage_nav2_transport')
        self.set_parameters([rclpy.parameter.Parameter('use_sim_time', value=True)])
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self._controller_set = self.create_client(SetParameters, 'controller_server/set_parameters')
        self._smoother_get = self.create_client(GetParameters, 'velocity_smoother/get_parameters')
        self._smoother_set = self.create_client(SetParameters, 'velocity_smoother/set_parameters')
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.create_subscription(Odometry, 'odom', self._odom, 10)
        self._mutex = Lock()
        self._last_odom = 0.0
        self._linear = self._angular = float('inf')
        self._pending = self._goal = self._result = None
        self._abort = False
        self._unsafe = False
        self._stop_lock = asyncio.Lock()

    def _odom(self, msg):
        with self._mutex:
            self._last_odom = time.monotonic()
            self._linear = math.hypot(msg.twist.twist.linear.x, msg.twist.twist.linear.y)
            self._angular = abs(msg.twist.twist.angular.z)

    def ready(self):
        with self._mutex:
            fresh = time.monotonic() - self._last_odom < 2
        return bool(not self._unsafe and fresh and self.client.server_is_ready() and
                    self.buffer.can_transform('map', 'base_footprint', rclpy.time.Time()))

    def snapshot(self):
        t = self.buffer.lookup_transform('map', 'base_footprint', rclpy.time.Time()).transform
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

    async def navigate(self, pose):
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
            self._result = self._goal.get_result_async()
            if self._abort:
                return False
            result = await self._future(self._result, 3600)
            return result.status == GoalStatus.STATUS_SUCCEEDED and not self._abort
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
        clients = (self._controller_set, self._smoother_get, self._smoother_set)
        if not all(client.service_is_ready() for client in clients):
            return False
        smoother_request = GetParameters.Request(names=['max_velocity'])
        smoother_response = await self._future(self._smoother_get.call_async(smoother_request), 3.0)
        if not smoother_response.values or not smoother_response.values[0].double_array_value:
            return False
        velocities = list(smoother_response.values[0].double_array_value)
        velocities[0] = float(target_speed_mps)
        controller_params = [
            Parameter('FollowPath.max_vel_x', value=float(target_speed_mps)).to_parameter_msg(),
            Parameter('FollowPath.max_speed_xy', value=float(target_speed_mps)).to_parameter_msg(),
        ]
        controller_result, smoother_result = await asyncio.gather(
            self._future(self._controller_set.call_async(SetParameters.Request(parameters=controller_params)), 3.0),
            self._future(self._smoother_set.call_async(SetParameters.Request(parameters=[
                Parameter('max_velocity', value=velocities).to_parameter_msg()])), 3.0),
        )
        return (all(item.successful for item in controller_result.results) and
                all(item.successful for item in smoother_result.results))

    async def stop(self):
        async with self._stop_lock:
            self._abort = True
            try:
                if self._pending is not None:
                    goal = self._goal or await self._future(self._pending, 5)
                    if goal.accepted:
                        result = self._result or goal.get_result_async()
                        if not result.done():
                            response = await self._future(goal.cancel_goal_async(), 5)
                            if not response.goals_canceling and not result.done():
                                raise RuntimeError('Nav2 未接受取消')
                        await self._future(result, 8)
                stable_since = None
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    with self._mutex:
                        still = (time.monotonic()-self._last_odom < 0.5 and
                                 self._linear < 0.02 and self._angular < 0.05)
                    if still:
                        stable_since = stable_since or time.monotonic()
                        if time.monotonic()-stable_since >= 0.5:
                            self._pending = self._goal = self._result = None
                            return True
                    else:
                        stable_since = None
                    await asyncio.sleep(0.05)
            except (TimeoutError, RuntimeError, Exception):
                pass
            self._unsafe = True
            return False
