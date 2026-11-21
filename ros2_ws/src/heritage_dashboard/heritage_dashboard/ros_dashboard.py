"""ROS2 只读订阅与显式 Mock 导览服务客户端。"""

import json
import time

from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger
from temi_interfaces.msg import RobotStatus, NavigationStatus

from .model import DashboardModel


class DashboardNode(Node):
    def __init__(self, controls=False):
        super().__init__('heritage_dashboard')
        self.model = DashboardModel(controls=controls)
        self.pending = None
        self.control_message = '只读模式' if not controls else 'Mock 人工操作已启用'
        self.create_subscription(RobotStatus, 'temi/robot_status', self._robot, 10)
        self.create_subscription(NavigationStatus, 'temi/navigation_status', self._navigation, 10)
        for key, topic in (('tour','heritage/tour/status'), ('visitor','heritage/visitor/status')):
            self.create_subscription(String, topic, lambda msg, key=key: self._json(key,msg), 10)
        self._control_clients = {name: self.create_client(Trigger, 'heritage/tour/' + name)
                        for name in ('pause','resume','cancel','manual_takeover')} if controls else {}

    def _robot(self, msg):
        self.model.update('robot', {key: getattr(msg, key) for key in ('connected','is_moving','battery_percentage','x','y','current_location','error_message','navigation_status')} | {'frame_id': msg.header.frame_id}, time.monotonic())

    def _navigation(self, msg):
        self.model.update('navigation', {key: getattr(msg,key) for key in ('target','status','description','task_id')}, time.monotonic())

    def _json(self, key, msg):
        try:
            data = json.loads(msg.data)
        except (ValueError, TypeError):
            data = None
        self.model.update(key, data, time.monotonic())

    def request(self, name):
        now = time.monotonic()
        if self.pending is not None or name not in self.model.commands(now):
            self.control_message = '拒绝：当前状态不允许操作'
            return False
        client = self._control_clients[name]
        if not client.service_is_ready():
            self.control_message = '导览服务未就绪'
            return False
        self.pending = (name, client.call_async(Trigger.Request()), now + 3.0)
        self.control_message = f'{name}：等待服务确认'
        return True

    def poll_control(self):
        if self.pending is None:
            return
        name, future, deadline = self.pending
        if future.done():
            try:
                response = future.result()
                self.control_message = f'{name}：{"已接受，等待真实状态确认" if response.success else "已拒绝"} · {response.message}'
            except Exception:
                self.control_message = f'{name}：结果未知，请核对状态'
            self.pending = None
        elif time.monotonic() >= deadline:
            future.cancel()
            self.pending = None
            self.control_message = f'{name}：确认超时，结果未知（不自动重试）'
