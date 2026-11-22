"""本机 ROS2 验证离线视觉与 Mock 输入隔离、过期及导览拒绝。"""

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
from threading import Thread
import time

import pytest
import rclpy
from rclpy.executors import MultiThreadedExecutor, SingleThreadedExecutor
from std_msgs.msg import Int32, String
from std_srvs.srv import Trigger

from heritage_tour_manager.ros_tour_node import HeritageTourNode
from heritage_tour_manager.tour_config import TourConfig
from temi_bridge.mock_backend import MockConfig, MockTemiBackend
from temi_bridge.ros_gateway import TemiGatewayNode
from visitor_perception.ros_visitor_node import VisitorPerceptionNode
from visitor_perception.visitor_monitor import VisitorConfig


def prepare(monkeypatch, tmp_path):
    monkeypatch.setenv('ROS_LOCALHOST_ONLY', '1')
    monkeypatch.setenv('ROS_DOMAIN_ID', os.environ.get('HERITAGE_TEST_ROS_DOMAIN_ID', '220'))
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))


@pytest.mark.parametrize('source,topic,other', [
    ('mock', 'count', 'vision_count'), ('offline_video', 'vision_count', 'count'),
    ('camera', 'camera_count', 'count'),
])
def test_count_topic_source_isolation_and_staleness(monkeypatch, tmp_path, source, topic, other):
    config = VisitorConfig(count_source=source, stale_timeout_sec=.5)
    prepare(monkeypatch, tmp_path)
    rclpy.init(args=[])
    monitor = VisitorPerceptionNode(config)
    client = rclpy.create_node('vision_isolation_client')
    executor = SingleThreadedExecutor()
    executor.add_node(monitor)
    executor.add_node(client)
    states, events = [], []
    client.create_subscription(String, 'heritage/visitor/status',
                               lambda msg: states.append(json.loads(msg.data)), 30)
    client.create_subscription(String, 'heritage/visitor/events',
                               lambda msg: events.append(json.loads(msg.data)), 30)
    correct = client.create_publisher(Int32, 'heritage/visitor/' + topic, 10)
    wrong = client.create_publisher(Int32, 'heritage/visitor/' + other, 10)

    def until(predicate, timeout=4):
        deadline = time.monotonic() + timeout
        while not predicate():
            assert time.monotonic() < deadline, states[-1:]
            executor.spin_once(timeout_sec=.05)

    try:
        until(lambda: states and correct.get_subscription_count() == 1)
        assert wrong.get_subscription_count() == 0
        assert states[-1]['source'] == source and not states[-1]['valid']
        for _ in range(3):
            wrong.publish(Int32(data=99))
        for _ in range(3):
            correct.publish(Int32(data=3))
        until(lambda: states[-1]['stable'] and states[-1]['people_count'] == 3)
        until(lambda: any(event['event'] == 'arrival' for event in events))
        assert all(event['source'] == source for event in events)
        until(lambda: not states[-1]['valid'] and states[-1]['people_count'] is None)
        until(lambda: any(event['event'] == 'data_stale' for event in events))
        assert not any(event['event'] == 'departure' for event in events)
        assert not any(state['people_count'] == 99 for state in states)
    finally:
        executor.shutdown()
        client.destroy_node()
        monitor.destroy_node()
        rclpy.try_shutdown()


def test_offline_video_cannot_arm_or_move_mock_tour(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    root = Path(__file__).resolve().parents[1]
    config = replace(TourConfig.from_yaml(root / 'config/exhibits.yaml', root / 'config/system.yaml'),
                     visitor_assist_enabled=True, visitor_status_timeout_sec=.8)
    rclpy.init(args=[])
    backend = MockTemiBackend(MockConfig.from_yaml(root / 'config/system.yaml'))
    gateway = TemiGatewayNode(backend)
    tour = HeritageTourNode(config)
    monitor = VisitorPerceptionNode(VisitorConfig(count_source='offline_video'))
    client = rclpy.create_node('offline_tour_boundary_client')
    tour_states, visitor_states = [], []
    client.create_subscription(String, 'heritage/tour/status',
                               lambda msg: tour_states.append(json.loads(msg.data)), 50)
    client.create_subscription(String, 'heritage/visitor/status',
                               lambda msg: visitor_states.append(json.loads(msg.data)), 50)
    publisher = client.create_publisher(Int32, 'heritage/visitor/vision_count', 10)
    count = [0]
    client.create_timer(.05, lambda: publisher.publish(Int32(data=count[0])))
    arm = client.create_client(Trigger, 'heritage/tour/arm_visitor')
    executor = MultiThreadedExecutor(num_threads=8)
    for node in (gateway, tour, monitor, client):
        executor.add_node(node)
    thread = Thread(target=executor.spin, daemon=True)
    thread.start()

    def until(predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while not predicate():
            assert time.monotonic() < deadline, (tour_states[-1:], visitor_states[-1:])
            time.sleep(.01)

    try:
        assert arm.wait_for_service(timeout_sec=4)
        until(lambda: tour_states and tour_states[-1]['connected'] and visitor_states and
              visitor_states[-1]['stable'] and visitor_states[-1]['people_count'] == 0)
        assert visitor_states[-1]['source'] == 'offline_video'
        assert not tour_states[-1]['visitor_assist']['can_arm']
        future = arm.call_async(Trigger.Request())
        until(future.done)
        assert not future.result().success
        count[0] = 3
        until(lambda: visitor_states[-1]['stable'] and visitor_states[-1]['people_count'] == 3)
        time.sleep(.3)
        assert tour_states[-1]['state'] == 'IDLE'
        assert not tour_states[-1]['visitor_assist']['active']
        assert not backend.get_status().is_moving
    finally:
        tour.close()
        gateway.close()
        executor.shutdown(timeout_sec=5)
        thread.join(timeout=5)
        for node in (client, monitor, tour, gateway):
            node.destroy_node()
        rclpy.try_shutdown()


def test_offline_monitor_cli_sigterm_exits_cleanly(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    root = Path(__file__).resolve().parents[1]
    command = root / 'ros2_ws/install/visitor_perception/lib/visitor_perception/visitor_perception'
    config = tmp_path / 'system.yaml'
    config.write_text('visitor_perception:\n  count_source: offline_video\n', encoding='utf-8')
    log = tmp_path / 'monitor.log'
    rclpy.init(args=[])
    node = rclpy.create_node('offline_monitor_cli_client')
    states = []
    node.create_subscription(String, 'heritage/visitor/status',
                             lambda msg: states.append(json.loads(msg.data)), 10)
    with log.open('w') as output:
        process = subprocess.Popen([str(command), '--config', str(config)], stdout=output,
                                   stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 5
            while not states:
                assert process.poll() is None and time.monotonic() < deadline
                rclpy.spin_once(node, timeout_sec=.05)
            process.terminate()
            assert process.wait(timeout=5) == 0, log.read_text()
            assert 'Traceback' not in log.read_text()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
            node.destroy_node()
            rclpy.try_shutdown()
