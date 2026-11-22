"""真实 ROS2 Topic 回环：仅匿名模拟人数，不启动机器人。"""

import json
import os
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from std_msgs.msg import Int32, String


def test_mock_visitor_topics_and_stale_recovery(monkeypatch, tmp_path):
    from visitor_perception.ros_visitor_node import VisitorPerceptionNode
    from visitor_perception.visitor_monitor import VisitorConfig

    monkeypatch.setenv('ROS_LOCALHOST_ONLY', '1')
    monkeypatch.setenv('ROS_DOMAIN_ID', os.environ.get('HERITAGE_TEST_ROS_DOMAIN_ID', '232'))
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    rclpy.init(args=[])
    monitor = VisitorPerceptionNode(VisitorConfig(stale_timeout_sec=1.0))
    client = rclpy.create_node('visitor_integration_client')
    executor = SingleThreadedExecutor()
    executor.add_node(monitor)
    executor.add_node(client)
    counts = client.create_publisher(Int32, 'heritage/visitor/count', 10)
    expected = client.create_publisher(Int32, 'heritage/visitor/expected_count', 10)
    states, events = [], []
    client.create_subscription(String, 'heritage/visitor/status',
                               lambda msg: states.append(json.loads(msg.data)), 30)
    client.create_subscription(String, 'heritage/visitor/events',
                               lambda msg: events.append(json.loads(msg.data)), 30)

    def until(predicate, timeout=5.0):
        deadline = time.monotonic() + timeout
        while not predicate():
            assert time.monotonic() < deadline, (states[-1:], events)
            executor.spin_once(timeout_sec=0.05)

    def observation(value):
        for _ in range(3):
            counts.publish(Int32(data=value))

    def event_names():
        return [event['event'] for event in events]

    try:
        until(lambda: states and counts.get_subscription_count() == 1 and
              expected.get_subscription_count() == 1 and
              client.count_publishers('heritage/visitor/events') == 1)
        assert not states[-1]['valid']
        observation(3)
        until(lambda: event_names() == ['arrival'] and states[-1]['people_count'] == 3)
        expected.publish(Int32(data=3))
        until(lambda: states[-1]['expected_count'] == 3)
        observation(2)
        until(lambda: event_names()[-1] == 'visitor_lost' and states[-1]['group_state'] == 'lost')
        observation(3)
        until(lambda: event_names()[-1] == 'regrouped' and states[-1]['group_state'] == 'following')
        until(lambda: event_names()[-1] == 'data_stale' and not states[-1]['valid'])
        assert states[-1]['people_count'] is None
        observation(3)
        until(lambda: event_names()[-1] == 'data_restored' and states[-1]['valid'])
        expected.publish(Int32(data=0))
        until(lambda: states[-1]['expected_count'] == 0)
        observation(0)
        until(lambda: event_names()[-1] == 'departure' and states[-1]['people_count'] == 0)
        assert event_names() == ['arrival', 'visitor_lost', 'regrouped', 'data_stale',
                                 'data_restored', 'departure']
        assert all(item['source'] == 'mock' for item in states + events)
    finally:
        executor.shutdown()
        client.destroy_node()
        monitor.destroy_node()
        rclpy.try_shutdown()
