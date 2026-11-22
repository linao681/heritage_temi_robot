"""真实本机 ROS2 三节点联动；所有人数、位置和移动均使用 Mock。"""

import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
from threading import Thread
import time
from types import SimpleNamespace

import pytest
import rclpy
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import Int32, String
from std_srvs.srv import Trigger

from heritage_tour_manager.ros_tour_node import HeritageTourNode
from heritage_tour_manager.tour_config import TourConfig
from temi_bridge.mock_backend import MockConfig, MockTemiBackend
from temi_bridge.ros_gateway import TemiGatewayNode
from visitor_perception.ros_visitor_node import VisitorPerceptionNode
from visitor_perception.visitor_monitor import VisitorConfig


def wait(predicate, timeout=8.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, '等待联动状态超时'
        time.sleep(0.01)


@pytest.fixture
def rig(request, monkeypatch, tmp_path):
    monkeypatch.setenv('ROS_LOCALHOST_ONLY', '1')
    monkeypatch.setenv('ROS_DOMAIN_ID', os.environ.get('HERITAGE_TEST_ROS_DOMAIN_ID', '222'))
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    root = Path(__file__).resolve().parents[1]
    system = root / 'config/system.yaml'
    enabled = getattr(request, 'param', True)
    config = replace(TourConfig.from_yaml(root / 'config/exhibits.yaml', system),
                     visitor_assist_enabled=enabled, visitor_status_timeout_sec=0.7,
                     communication_timeout_sec=1.0, navigation_timeout_sec=5.0,
                     consent_timeout_sec=5.0, qa_timeout_sec=5.0)
    backend = MockTemiBackend(replace(MockConfig.from_yaml(system), speed_mps=1.2,
                                      navigation_delay_sec=0.08, tick_sec=0.025, speech_delay_sec=0.12))
    rclpy.init(args=[])
    gateway = TemiGatewayNode(backend, status_hz=25)
    tour = HeritageTourNode(config)
    visitor = VisitorPerceptionNode(VisitorConfig(stale_timeout_sec=0.75))
    client = rclpy.create_node('visitor_tour_test_client')
    statuses, visitors = [], []
    client.create_subscription(String, 'heritage/tour/status',
                               lambda msg: statuses.append(json.loads(msg.data)), 100)

    def receive_visitor(message):
        try:
            visitors.append(json.loads(message.data))
        except ValueError:
            # 故障注入测试不能让旁路观察者抢先终止 ROS executor。
            pass

    client.create_subscription(String, 'heritage/visitor/status',
                               receive_visitor, 100)
    publisher = client.create_publisher(Int32, 'heritage/visitor/count', 10)
    count = [0]
    pulse = [0]

    def send():
        value = count[0]
        if value == 'jitter':
            pulse[0] += 1
            value = 2 + pulse[0] % 2
        if value is not None:
            publisher.publish(Int32(data=value))

    client.create_timer(0.05, send)
    controls = {name: client.create_client(Trigger, 'heritage/tour/' + name)
                for name in ('start', 'arm_visitor', 'accept', 'refuse', 'resume', 'cancel', 'manual_takeover')}
    executor = MultiThreadedExecutor(num_threads=8)
    for node in (gateway, tour, visitor, client):
        executor.add_node(node)
    thread = Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        wait(lambda: statuses and statuses[-1]['connected'] and visitors and
             visitors[-1].get('stable') and visitors[-1]['people_count'] == 0 and
             (not enabled or statuses[-1].get('visitor_assist', {}).get('can_arm')))
        for name, control in controls.items():
            if name != 'arm_visitor' or enabled:
                assert control.wait_for_service(timeout_sec=3)
        yield SimpleNamespace(backend=backend, gateway=gateway, visitor=visitor, tour=tour,
                              client=client, executor=executor, statuses=statuses, visitors=visitors,
                              count=count, controls=controls)
    finally:
        tour.close()
        gateway.close()
        executor.shutdown(timeout_sec=5.0)
        thread.join(timeout=5.0)
        for node in (client, visitor, tour, gateway):
            node.destroy_node()
        rclpy.try_shutdown()


def call(rig, name, success=True):
    future = rig.controls[name].call_async(Trigger.Request())
    wait(future.done)
    assert future.result().success is success, future.result().message


def state(rig, name, outcome=None):
    wait(lambda: rig.statuses[-1]['state'] == name and
         (outcome is None or rig.statuses[-1]['outcome'] == outcome))


def assist(rig):
    return rig.statuses[-1]['visitor_assist']


def count(rig, value):
    rig.count[0] = value
    if isinstance(value, int):
        wait(lambda: rig.visitors[-1]['stable'] and rig.visitors[-1]['people_count'] == value)


def greet(rig):
    call(rig, 'arm_visitor')
    wait(lambda: assist(rig)['armed'] and assist(rig)['observed_empty'])
    count(rig, 3)
    state(rig, 'WAITING_CONSENT')
    wait(lambda: assist(rig)['can_accept'])


def begin(rig):
    greet(rig)
    call(rig, 'accept')
    wait(lambda: rig.statuses[-1]['state'] == 'NAVIGATING' and
         rig.statuses[-1]['target'] == 'exhibit_01' and rig.backend.get_status().is_moving)


def test_new_arrival_consent_and_dropout_requires_explicit_resume(rig):
    count(rig, 3)
    assert rig.statuses[-1]['state'] == 'IDLE'
    call(rig, 'arm_visitor')
    time.sleep(0.25)
    assert assist(rig)['armed'] and rig.statuses[-1]['state'] == 'IDLE'
    count(rig, 0)
    wait(lambda: assist(rig)['observed_empty'])
    count(rig, 3)
    state(rig, 'WAITING_CONSENT')
    wait(lambda: assist(rig)['can_accept'])
    assert not rig.backend.get_status().is_moving and rig.statuses[-1]['visited'] == []
    count(rig, 2)
    wait(lambda: not assist(rig)['can_accept'])
    call(rig, 'accept', False)
    assert rig.statuses[-1]['state'] == 'WAITING_CONSENT'
    count(rig, 3)
    wait(lambda: assist(rig)['can_accept'])
    call(rig, 'accept')
    wait(lambda: rig.statuses[-1]['target'] == 'exhibit_01' and rig.backend.get_status().is_moving)
    count(rig, 2)
    state(rig, 'PAUSED')
    assert not rig.backend.get_status().is_moving
    assert rig.statuses[-1]['error_count'] == 1
    call(rig, 'resume', False)
    count(rig, 3)
    wait(lambda: assist(rig)['can_resume'])
    time.sleep(0.25)
    assert rig.statuses[-1]['state'] == 'PAUSED' and not rig.backend.get_status().is_moving
    call(rig, 'resume')
    wait(lambda: rig.statuses[-1]['state'] == 'NAVIGATING' and
         rig.statuses[-1]['target'] == 'exhibit_01' and rig.backend.get_status().is_moving)
    call(rig, 'cancel')
    state(rig, 'IDLE', 'canceled')
    wait(lambda: rig.visitors[-1]['expected_count'] == 0 and not assist(rig)['active'])


@pytest.mark.parametrize('failure', ['stale', 'jitter', 'heartbeat', 'malformed', 'expected_mismatch'])
def test_lost_or_unreliable_perception_pauses(rig, failure):
    begin(rig)
    if failure in ('heartbeat', 'malformed'):
        rig.executor.remove_node(rig.visitor)
        if failure == 'malformed':
            bad = rig.client.create_publisher(String, 'heritage/visitor/status', 10)
            wait(lambda: bad.get_subscription_count() >= 1)
            rig.client.create_timer(0.05, lambda: bad.publish(String(data='invalid JSON')))
    elif failure == 'expected_mismatch':
        expected = rig.client.create_publisher(Int32, 'heritage/visitor/expected_count', 10)
        wait(lambda: expected.get_subscription_count() == 1)
        expected.publish(Int32(data=0))
    else:
        count(rig, 'jitter' if failure == 'jitter' else None)
    state(rig, 'PAUSED')
    assert not rig.backend.get_status().is_moving
    call(rig, 'resume', False)
    if failure == 'jitter':
        assert rig.visitors[-1]['valid'] and not rig.visitors[-1]['stable_fresh']
    call(rig, 'manual_takeover')
    state(rig, 'IDLE', 'manual_takeover')


def test_cancel_armed_refusal_and_takeover_never_retrigger(rig):
    call(rig, 'arm_visitor')
    call(rig, 'cancel')
    count(rig, 3)
    time.sleep(0.25)
    assert rig.statuses[-1]['state'] == 'IDLE' and not assist(rig)['armed']
    count(rig, 0)
    greet(rig)
    call(rig, 'refuse')
    state(rig, 'IDLE', 'declined')
    wait(lambda: rig.visitors[-1]['expected_count'] == 0)
    time.sleep(0.25)
    assert not assist(rig)['active'] and rig.statuses[-1]['outcome'] == 'declined'
    count(rig, 0)
    greet(rig)
    call(rig, 'manual_takeover')
    state(rig, 'IDLE', 'manual_takeover')
    wait(lambda: rig.visitors[-1]['expected_count'] == 0)
    time.sleep(0.25)
    assert not assist(rig)['armed'] and rig.statuses[-1]['outcome'] == 'manual_takeover'


def test_low_battery_before_consent_never_starts_motion(rig):
    greet(rig)
    rig.gateway._loop.call_soon_threadsafe(rig.backend.set_battery_percentage, 10.0)
    state(rig, 'ERROR', 'low_battery_before_consent')
    assert not rig.backend.get_status().is_moving and rig.statuses[-1]['visited'] == []
    assert 'NAVIGATING' not in {entry['state'] for entry in rig.statuses[-1]['history']}
    assert 'RETURNING' not in {entry['state'] for entry in rig.statuses[-1]['history']}
    call(rig, 'arm_visitor', False)


def test_low_battery_return_takes_priority_over_visitor_pause(rig):
    begin(rig)
    count(rig, 2)
    state(rig, 'PAUSED')
    rig.gateway._loop.call_soon_threadsafe(rig.backend.set_battery_percentage, 10.0)
    state(rig, 'ERROR', 'low_battery_returned')
    assert rig.statuses[-1]['safe_return_completed']


def test_nonmock_frame_aborts_assisted_tour(rig):
    greet(rig)

    def change_frame():
        rig.backend._state = replace(rig.backend.get_status(), frame_id='temi_sdk_unverified')

    rig.gateway._loop.call_soon_threadsafe(change_frame)
    state(rig, 'ERROR', 'error')
    assert not rig.backend.get_status().is_moving
    wait(lambda: not assist(rig)['active'])
    call(rig, 'arm_visitor', False)


@pytest.mark.parametrize('source', ['robot', 'visitor'])
def test_disconnect_after_arming_requires_new_arm(rig, source):
    call(rig, 'arm_visitor')
    wait(lambda: assist(rig)['armed'])
    if source == 'robot':
        asyncio.run_coroutine_threadsafe(rig.backend.simulate_disconnect(), rig.gateway._loop).result(3)
        wait(lambda: not rig.statuses[-1]['connected'] and not assist(rig)['armed'])
        asyncio.run_coroutine_threadsafe(rig.backend.connect(), rig.gateway._loop).result(3)
    else:
        rig.executor.remove_node(rig.visitor)
        wait(lambda: not assist(rig)['armed'], timeout=2.0)
        rig.executor.add_node(rig.visitor)
    count(rig, 3)
    time.sleep(0.25)
    assert rig.statuses[-1]['state'] == 'IDLE'


@pytest.mark.parametrize('rig', [False], indirect=True)
def test_disabled_assist_preserves_manual_modes(rig):
    assert not rig.controls['arm_visitor'].service_is_ready()
    count(rig, 3)
    time.sleep(0.25)
    assert rig.statuses[-1]['state'] == 'IDLE'
    call(rig, 'start')
    state(rig, 'WAITING_CONSENT')
    call(rig, 'accept')
    wait(lambda: rig.backend.get_status().is_moving)
    call(rig, 'cancel')
    state(rig, 'IDLE', 'canceled')
