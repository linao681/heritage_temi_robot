"""使用真实 ROS2 Service、Action、Topic 验证 Mock 导览闭环。"""

import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
from threading import Event, Thread
import time
from types import SimpleNamespace

import pytest
import rclpy
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import String
from std_srvs.srv import Trigger
from temi_interfaces.action import NavigateTo, Speak

from temi_bridge.mock_backend import MockConfig, MockTemiBackend
from temi_bridge.ros_gateway import TemiGatewayNode


def wait_until(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            pytest.fail('未在超时前收到预期导览状态')
        time.sleep(0.01)


def wait_result(future, timeout=5.0):
    wait_until(future.done, timeout)
    return future.result()


@pytest.fixture
def rig(monkeypatch, tmp_path):
    from heritage_tour_manager.ros_tour_node import HeritageTourNode
    from heritage_tour_manager.tour_config import TourConfig

    monkeypatch.setenv('ROS_LOCALHOST_ONLY', '1')
    monkeypatch.setenv('ROS_DOMAIN_ID', os.environ.get('HERITAGE_TEST_ROS_DOMAIN_ID', '227'))
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    root = Path(__file__).resolve().parents[1]
    system = root / 'config/system.yaml'
    config = replace(
        TourConfig.from_yaml(root / 'config/exhibits.yaml', system),
        navigation_timeout_sec=3.0, speech_timeout_sec=2.0,
        communication_timeout_sec=1.0, consent_timeout_sec=5.0, qa_timeout_sec=5.0,
    )
    backend = MockTemiBackend(replace(
        MockConfig.from_yaml(system), speed_mps=6.0,
        navigation_delay_sec=0.04, tick_sec=0.015, speech_delay_sec=0.08,
    ))
    rclpy.init(args=[])
    gateway = TemiGatewayNode(backend, status_hz=40.0)
    tour = HeritageTourNode(config)
    client = rclpy.create_node('tour_integration_client')
    statuses = []
    client.create_subscription(String, 'heritage/tour/status',
                               lambda msg: statuses.append(json.loads(msg.data)), 100)
    controls = {
        command: client.create_client(Trigger, 'heritage/tour/' + command)
        for command in ('start', 'accept', 'refuse', 'pause', 'resume', 'cancel',
                        'visitor_lost', 'manual_takeover', 'finish_qa')
    }
    navigation = ActionClient(client, NavigateTo, 'temi/navigate_to')
    speech = ActionClient(client, Speak, 'temi/speak')
    executor = MultiThreadedExecutor(num_threads=8)
    for node in (gateway, tour, client):
        executor.add_node(node)
    thread = Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        assert all(service.wait_for_service(timeout_sec=5.0) for service in controls.values())
        wait_until(lambda: statuses and statuses[-1]['connected'])
        yield SimpleNamespace(backend=backend, gateway=gateway, tour=tour, config=config,
                              statuses=statuses, controls=controls, navigation=navigation, client=client,
                              speech=speech)
    finally:
        tour.close()
        tour.close()
        gateway.close()
        executor.shutdown(timeout_sec=5.0)
        thread.join(timeout=5.0)
        navigation.destroy()
        speech.destroy()
        client.destroy_node()
        tour.destroy_node()
        gateway.destroy_node()
        rclpy.try_shutdown()


def call(rig, command):
    result = wait_result(rig.controls[command].call_async(Trigger.Request()))
    assert result.success, result.message


def wait_state(rig, state, outcome=None):
    wait_until(lambda: rig.statuses[-1]['state'] == state and
               (outcome is None or rig.statuses[-1]['outcome'] == outcome))


def begin(rig):
    call(rig, 'start')
    wait_state(rig, 'WAITING_CONSENT')
    call(rig, 'accept')


def test_complete_configured_route_and_qa_through_ros_services(rig):
    begin(rig)
    wait_state(rig, 'QA')
    expected = [exhibit.temi_location for exhibit in rig.config.route]
    assert rig.statuses[-1]['visited'] == expected[:-1]
    call(rig, 'finish_qa')
    wait_state(rig, 'COMPLETED', 'completed')
    final = rig.statuses[-1]
    assert final['visited'] == expected
    assert len(final['visited']) == 8
    assert final['route_index'] == len(expected) - 1
    assert final['error_count'] == 0
    assert rig.backend.get_status().current_location == expected[-1]
    assert not rig.backend.get_status().is_moving
    assert {'WAITING_CONSENT', 'QA', 'COMPLETED'} <= {
        status['state'] for status in rig.statuses
    }


@pytest.mark.parametrize('question,found', [('潮剧用什么语言', True), ('明天的天气', False)])
def test_knowledge_service_to_tour_speech_and_exit(rig, question, found):
    import subprocess
    import signal
    from temi_interfaces.srv import AskHeritage, SubmitQuestion
    root = Path(__file__).resolve().parents[1]
    process = subprocess.Popen([str(root/'ros2_ws/install/heritage_knowledge/lib/heritage_knowledge/knowledge_node'),
                                '--config', str(root/'config/knowledge.yaml')])
    try:
        knowledge = rig.client.create_client(AskHeritage, 'heritage/knowledge/ask')
        assert knowledge.wait_for_service(timeout_sec=5)
        submit = rig.client.create_client(SubmitQuestion, 'heritage/tour/ask')
        assert submit.wait_for_service(timeout_sec=5)
        assert not wait_result(submit.call_async(SubmitQuestion.Request(question=question))).accepted
        begin(rig)
        wait_until(lambda: rig.statuses[-1].get('qa_waiting'))
        assert not wait_result(submit.call_async(SubmitQuestion.Request(question=' '))).accepted
        assert wait_result(submit.call_async(SubmitQuestion.Request(question=question))).accepted
        assert not wait_result(submit.call_async(SubmitQuestion.Request(question='重复提问'))).accepted
        wait_state(rig, 'COMPLETED', 'completed')
        result = rig.statuses[-1]['qa_result']
        assert result['found'] is found and result['spoken']
        assert bool(result['source']) is found
        assert len(rig.statuses[-1]['visited']) == 8
        if found:
            assert result['entry_id'] == 'opera_language'
    finally:
        process.send_signal(signal.SIGINT)
        process.wait(timeout=5)


def test_qa_service_unavailable_falls_back_and_continues(rig):
    from temi_interfaces.srv import SubmitQuestion
    submit = rig.client.create_client(SubmitQuestion, 'heritage/tour/ask')
    assert submit.wait_for_service(timeout_sec=5)
    begin(rig)
    wait_until(lambda: rig.statuses[-1].get('qa_waiting'))
    assert wait_result(submit.call_async(SubmitQuestion.Request(question='潮剧用什么语言'))).accepted
    wait_state(rig, 'COMPLETED', 'completed')
    result = rig.statuses[-1]['qa_result']
    assert not result['found'] and result['spoken'] and '暂不可用' in result['answer']


def test_dashboard_real_ros_telemetry_and_manual_takeover(rig):
    from heritage_dashboard.ros_dashboard import DashboardNode
    monitor = DashboardNode(controls=True)
    def until(predicate, timeout=5):
        deadline=time.monotonic()+timeout
        while not predicate():
            assert time.monotonic()<deadline, monitor.control_message
            rclpy.spin_once(monitor,timeout_sec=.02)
            monitor.poll_control()
    try:
        until(lambda: monitor.model.snapshot(time.monotonic())['robot'] is not None and
              monitor.model.snapshot(time.monotonic())['tour'] is not None)
        assert not monitor.request('pause')
        begin(rig)
        until(lambda: 'pause' in monitor.model.commands(time.monotonic()) and monitor.model.snapshot(time.monotonic())['tour']['state']=='NAVIGATING')
        assert monitor.request('pause')
        until(lambda: monitor.pending is None and 'resume' in monitor.model.commands(time.monotonic()))
        assert not rig.backend.get_status().is_moving
        assert monitor.request('resume')
        until(lambda: monitor.pending is None and monitor.model.snapshot(time.monotonic())['tour']['state'] != 'PAUSED')
        assert monitor.request('manual_takeover')
        until(lambda: monitor.pending is None and (monitor.model.snapshot(time.monotonic())['tour'] or {}).get('outcome')=='manual_takeover')
        assert not rig.backend.get_status().is_moving
        assert not monitor.model.commands(time.monotonic())
    finally:
        monitor.destroy_node()


@pytest.mark.parametrize('pause_command', ['pause', 'visitor_lost'])
def test_pause_resume_and_cancel_stop_real_navigation(rig, pause_command):
    begin(rig)
    wait_until(lambda: rig.backend.get_status().is_moving)
    call(rig, pause_command)
    wait_state(rig, 'PAUSED')
    wait_until(lambda: not rig.backend.get_status().is_moving)
    paused = rig.backend.get_status()
    visited = rig.statuses[-1]['visited']
    time.sleep(0.15)
    assert rig.backend.get_status().x == paused.x
    assert rig.backend.get_status().y == paused.y
    assert rig.statuses[-1]['visited'] == visited
    assert rig.statuses[-1]['error_count'] == (1 if pause_command == 'visitor_lost' else 0)
    call(rig, 'resume')
    wait_until(lambda: rig.backend.get_status().is_moving)
    call(rig, 'cancel')
    wait_state(rig, 'IDLE', 'canceled')
    wait_until(lambda: not rig.backend.get_status().is_moving)
    # 下一条真实 Action 能被接受，说明旧任务已经释放其导航槽位。
    goal = wait_result(rig.navigation.send_goal_async(
        NavigateTo.Goal(location='entrance', timeout_sec=3.0)))
    assert goal.accepted
    assert wait_result(goal.get_result_async()).result.success


def test_cancel_during_goal_acceptance_cleans_up_pending_goal(rig):
    requested, release = Event(), Event()
    previous = rig.gateway._navigation_goal

    def delay_acceptance(request):
        requested.set()
        assert release.wait(timeout=2.0)
        return previous(request)

    rig.gateway._navigation.register_goal_callback(delay_acceptance)
    try:
        begin(rig)
        assert requested.wait(timeout=3.0)
        call(rig, 'cancel')
        release.set()
        wait_state(rig, 'IDLE', 'canceled')
        rig.gateway._navigation.register_goal_callback(previous)
        goal = wait_result(rig.navigation.send_goal_async(
            NavigateTo.Goal(location='exhibit_02', timeout_sec=3.0)))
        assert goal.accepted
        assert wait_result(goal.get_result_async()).result.success
    finally:
        release.set()
        rig.gateway._navigation.register_goal_callback(previous)


def test_speech_result_timeout_cancels_old_action_before_new_speech(rig):
    original = rig.backend.config
    rig.backend.config = replace(original, speech_delay_sec=5.0)
    call(rig, 'start')
    wait_state(rig, 'ERROR', 'error')
    rig.backend.config = original
    goal = wait_result(rig.speech.send_goal_async(Speak.Goal(text='新任务')))
    assert goal.accepted
    assert wait_result(goal.get_result_async()).result.success


def test_close_cancels_active_navigation(rig):
    begin(rig)
    wait_until(lambda: rig.backend.get_status().is_moving)
    rig.tour.close()
    rig.tour.close()
    assert not rig.backend.get_status().is_moving
    assert not rig.tour._thread.is_alive()


def test_unknown_ros_result_is_not_terminal_confirmation():
    import asyncio
    from concurrent.futures import Future
    from action_msgs.msg import GoalStatus
    from heritage_tour_manager.ros_tour_node import _RosTourRobot

    async def scenario():
        robot = _RosTourRobot.__new__(_RosTourRobot)
        result = Future()
        result.set_result(SimpleNamespace(status=GoalStatus.STATUS_UNKNOWN))
        assert not await robot._settle_goal(None, SimpleNamespace(accepted=True), result)

    asyncio.run(scenario())


def test_low_battery_via_ros_status_stops_tour_and_returns_to_entrance(rig):
    begin(rig)
    wait_until(lambda: rig.backend.get_status().is_moving and rig.backend.get_status().x > 0.0)
    rig.gateway._loop.call_soon_threadsafe(rig.backend.set_battery_percentage, 10.0)
    wait_state(rig, 'ERROR', 'low_battery_returned')
    final = rig.statuses[-1]
    assert final['safe_return_completed'] and final['target'] == rig.config.safe_return_location
    assert final['error_count'] >= 1 and rig.backend.get_status().current_location == 'entrance'
    assert not rig.backend.get_status().is_moving


def test_ros_disconnect_reconnect_does_not_resume_old_tour(rig):
    begin(rig)
    wait_until(lambda: rig.backend.get_status().is_moving)
    asyncio.run_coroutine_threadsafe(rig.backend.simulate_disconnect(), rig.gateway._loop).result(2.0)
    wait_state(rig, 'ERROR', 'error')
    wait_until(lambda: not rig.statuses[-1]['connected'])
    interrupted = rig.backend.get_status()
    assert asyncio.run_coroutine_threadsafe(rig.backend.connect(), rig.gateway._loop).result(2.0).success
    wait_until(lambda: rig.statuses[-1]['connected'])
    time.sleep(0.15)
    assert rig.statuses[-1]['state'] == 'ERROR'
    assert rig.backend.get_status().x == interrupted.x and not rig.backend.get_status().is_moving
    # 仅人工重新开始才能建立新任务，旧导览没有自动重放。
    begin(rig)
    call(rig, 'cancel')
    wait_state(rig, 'IDLE', 'canceled')


def test_refusal_then_manual_takeover_via_ros_services(rig):
    call(rig, 'start')
    wait_state(rig, 'WAITING_CONSENT')
    call(rig, 'refuse')
    wait_state(rig, 'IDLE', 'declined')
    assert rig.statuses[-1]['visited'] == [] and not rig.backend.get_status().is_moving
    begin(rig)
    wait_until(lambda: rig.backend.get_status().is_moving)
    call(rig, 'manual_takeover')
    wait_state(rig, 'IDLE', 'manual_takeover')
    assert not rig.backend.get_status().is_moving


def test_navigation_fault_propagates_via_ros_action_to_tour_error(rig):
    rig.gateway._loop.call_soon_threadsafe(rig.backend.inject_navigation_failure)
    begin(rig)
    wait_state(rig, 'ERROR', 'error')
    assert rig.statuses[-1]['error_count'] >= 1
    assert rig.statuses[-1]['visited'] == [] and not rig.backend.get_status().is_moving
