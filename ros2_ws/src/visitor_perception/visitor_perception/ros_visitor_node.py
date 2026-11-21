"""感知 ROS2 Topic 适配器，不调用导览或运动控制服务。"""

import json
import time

from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from std_msgs.msg import Int32, String

from .visitor_monitor import VisitorConfig, VisitorMonitor


class VisitorPerceptionNode(Node):
    def __init__(self, config: VisitorConfig):
        super().__init__('visitor_perception')
        self._monitor = VisitorMonitor(config)
        self._status = self.create_publisher(String, 'heritage/visitor/status', 10)
        self._events = self.create_publisher(String, 'heritage/visitor/events', 10)
        count_topic = 'count' if config.count_source == 'mock' else 'vision_count'
        self.create_subscription(Int32, 'heritage/visitor/' + count_topic, self._on_count, 10)
        self.create_subscription(Int32, 'heritage/visitor/expected_count', self._on_expected, 10)
        self.create_timer(min(0.2, config.stale_timeout_sec / 2), self._on_timer,
                          clock=Clock(clock_type=ClockType.STEADY_TIME))

    def _publish(self, events):
        snapshot = self._monitor.snapshot()
        self._status.publish(String(data=json.dumps(snapshot)))
        for event in events:
            self._events.publish(String(data=json.dumps({'event': event, **snapshot})))
            self.get_logger().info(f'游客感知: {event}, {snapshot}')

    def _on_count(self, message):
        now = time.monotonic()
        expired = self._monitor.tick(now)
        if expired:
            self._publish(expired)
        self._publish(self._monitor.observe(message.data, now))

    def _on_expected(self, message):
        self._publish(self._monitor.set_expected_count(message.data, time.monotonic()))

    def _on_timer(self):
        self._publish(self._monitor.tick(time.monotonic()))
