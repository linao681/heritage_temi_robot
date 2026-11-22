"""通过真实 ROS2 客户端验证 Gateway 与虚拟机器人的集成。"""

import asyncio
import os
import time
from threading import Event, Thread
from types import SimpleNamespace

import pytest
import rclpy
from action_msgs.msg import GoalStatus
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from temi_interfaces.action import NavigateTo, Speak
from temi_interfaces.msg import NavigationStatus, RobotStatus
from temi_interfaces.srv import StopRobot

from temi_bridge.mock_backend import MockConfig, MockTemiBackend


def wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            pytest.fail('未在超时前收到预期 ROS2 状态')
        time.sleep(0.01)


def wait_result(future, timeout=5.0):
    wait_until(future.done, timeout)
    return future.result()


def test_concurrent_stops_wait_for_the_same_confirmation(rig):
    from concurrent.futures import ThreadPoolExecutor
    original = rig.backend.stop
    entered = Event()
    calls = []
    async def delayed_stop():
        calls.append(1)
        entered.set()
        await asyncio.sleep(.25)
        return await original()
    rig.backend.stop = delayed_stop
    def stop():
        return rig.gateway._stop_robot(StopRobot.Request(stop=True), StopRobot.Response())
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(stop)
        assert entered.wait(2)
        second = pool.submit(stop)
        assert first.result(timeout=5).success
        assert second.result(timeout=5).success
    assert len(calls) == 1


@pytest.fixture
def rig(monkeypatch, tmp_path):
    from temi_bridge.ros_gateway import TemiGatewayNode

    monkeypatch.setenv('ROS_LOCALHOST_ONLY', '1')
    monkeypatch.setenv('ROS_DOMAIN_ID', os.environ.get('HERITAGE_TEST_ROS_DOMAIN_ID', '230'))
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    rclpy.init(args=[])
    backend = MockTemiBackend(MockConfig(
        locations={'entrance': (0.0, 0.0), 'near': (1.0, 0.0), 'far': (10.0, 0.0)},
        speed_mps=3.0, navigation_delay_sec=0.03, tick_sec=0.02,
        speech_delay_sec=1.5, speech_timeout_sec=4.0,
    ))
    gateway = TemiGatewayNode(backend, status_hz=30.0)
    client = rclpy.create_node('gateway_test_client')
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(gateway)
    executor.add_node(client)
    snapshots, events = [], []
    client.create_subscription(RobotStatus, 'temi/robot_status', snapshots.append, 10)
    client.create_subscription(NavigationStatus, 'temi/navigation_status', events.append, 10)
    navigation = ActionClient(client, NavigateTo, 'temi/navigate_to')
    speech = ActionClient(client, Speak, 'temi/speak')
    stop = client.create_client(StopRobot, 'temi/stop')
    thread = Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        assert navigation.wait_for_server(timeout_sec=5.0)
        assert speech.wait_for_server(timeout_sec=5.0)
        assert stop.wait_for_service(timeout_sec=5.0)
        wait_until(lambda: snapshots and snapshots[-1].connected)
        yield SimpleNamespace(backend=backend, gateway=gateway, navigation=navigation,
                              speech=speech, stop=stop, snapshots=snapshots, events=events)
    finally:
        gateway.close()
        executor.shutdown(timeout_sec=5.0)
        thread.join(timeout=5.0)
        navigation.destroy()
        speech.destroy()
        client.destroy_node()
        gateway.destroy_node()
        rclpy.try_shutdown()


def navigate(rig, location='near', timeout_sec=5.0, feedback=None):
    callback = None if feedback is None else lambda msg: feedback.append(msg.feedback.status)
    return wait_result(rig.navigation.send_goal_async(
        NavigateTo.Goal(location=location, timeout_sec=timeout_sec), feedback_callback=callback,
    ))


def speak(rig, text='欢迎来到展厅', feedback=None):
    callback = None if feedback is None else lambda msg: feedback.append(msg.feedback.status)
    return wait_result(rig.speech.send_goal_async(Speak.Goal(text=text), feedback_callback=callback))


def test_navigation_reports_movement_status_events_and_goal_uuid(rig):
    first = rig.snapshots[-1]
    assert first.header.frame_id == 'mock_map' and first.header.stamp.sec > 0
    assert first.current_location == 'entrance' and first.battery_percentage == 100.0
    feedback = []
    goal = navigate(rig, feedback=feedback)
    assert goal.accepted
    result = wait_result(goal.get_result_async())
    assert result.status == GoalStatus.STATUS_SUCCEEDED and result.result.success
    wait_until(lambda: rig.snapshots[-1].current_location == 'near')
    wait_until(lambda: rig.events and rig.events[-1].status == 'complete' and 'complete' in feedback)
    assert any(0.0 < msg.x < 1.0 and msg.is_moving for msg in rig.snapshots)
    assert rig.snapshots[-1].x == 1.0 and not rig.snapshots[-1].is_moving
    assert rig.snapshots[-1].battery_percentage == pytest.approx(99.5)
    assert feedback == ['start', 'calculating', 'going', 'complete']
    assert [msg.status for msg in rig.events] == feedback
    assert all(msg.task_id == bytes(goal.goal_id.uuid).hex() and msg.target == 'near'
               and msg.header.frame_id == 'mock_map' and msg.header.stamp.sec > 0
               and msg.description for msg in rig.events)


def test_speech_waits_for_completion_and_reports_feedback(rig):
    feedback = []
    goal = speak(rig, feedback=feedback)
    assert goal.accepted
    pending = goal.get_result_async()
    wait_until(lambda: 'started' in feedback)
    assert not pending.done()
    result = wait_result(pending)
    assert result.status == GoalStatus.STATUS_SUCCEEDED and result.result.success
    wait_until(lambda: 'complete' in feedback)
    assert feedback == ['started', 'complete']


def test_stop_interrupts_navigation_without_blocking_speech(rig):
    nav = navigate(rig, 'far')
    speech_feedback = []
    speech = speak(rig, feedback=speech_feedback)
    assert nav.accepted and speech.accepted
    nav_result = nav.get_result_async()
    speech_result = speech.get_result_async()
    wait_until(lambda: rig.snapshots[-1].is_moving and 'started' in speech_feedback)
    # 同类重复任务须被拒绝，不占用执行线程导致 STOP 饿死。
    assert not navigate(rig).accepted
    assert not speak(rig).accepted
    false_response = wait_result(rig.stop.call_async(StopRobot.Request(stop=False)))
    assert not false_response.success and rig.snapshots[-1].is_moving
    start = time.monotonic()
    response = wait_result(rig.stop.call_async(StopRobot.Request(stop=True)), timeout=1.0)
    assert response.success and time.monotonic() - start < 1.0
    result = wait_result(nav_result, timeout=1.0)
    assert result.status == GoalStatus.STATUS_ABORTED and not result.result.success
    wait_until(lambda: rig.snapshots[-1].navigation_status == 'stopped')
    stopped = rig.snapshots[-1]
    assert stopped.x < 10.0 and not stopped.is_moving
    assert not speech_result.done()
    assert wait_result(speech_result).status == GoalStatus.STATUS_SUCCEEDED
    assert rig.snapshots[-1].x == stopped.x


def test_stop_prevents_already_accepted_navigation_from_starting_later(rig):
    # 模拟已经接受 Goal、但 ROS 执行线程尚未将导航交给后端的情况。
    delayed = Event()
    release = Event()
    execute = rig.gateway._execute_navigation

    def wait_then_execute(goal):
        delayed.set()
        assert release.wait(timeout=3.0)
        return execute(goal)

    rig.gateway._navigation.register_execute_callback(wait_then_execute)
    try:
        nav = navigate(rig, 'far')
        assert nav.accepted and delayed.wait(timeout=2.0)
        assert wait_result(rig.stop.call_async(StopRobot.Request(stop=True))).success
    finally:
        release.set()
    result = wait_result(nav.get_result_async(), timeout=1.0)
    assert result.status == GoalStatus.STATUS_ABORTED and not result.result.success
    assert rig.backend.get_status().x == 0.0 and not rig.backend.get_status().is_moving


@pytest.mark.parametrize('kind', ['navigation', 'speech'])
def test_reconnect_does_not_execute_a_previously_accepted_goal(rig, kind):
    delayed = Event()
    release = Event()
    execute = (rig.gateway._execute_navigation if kind == 'navigation'
               else rig.gateway._execute_speech)
    server = getattr(rig.gateway, '_' + kind)

    def wait_then_execute(goal):
        delayed.set()
        assert release.wait(timeout=3.0)
        return execute(goal)

    server.register_execute_callback(wait_then_execute)
    old_epoch = rig.backend.get_status().connection_epoch
    try:
        goal = navigate(rig, 'far') if kind == 'navigation' else speak(rig)
        assert goal.accepted and delayed.wait(timeout=2.0)
        asyncio.run_coroutine_threadsafe(rig.backend.simulate_disconnect(), rig.gateway._loop).result(2.0)
        assert asyncio.run_coroutine_threadsafe(rig.backend.connect(), rig.gateway._loop).result(2.0).success
        assert rig.backend.get_status().connection_epoch > old_epoch
    finally:
        release.set()
    result = wait_result(goal.get_result_async())
    assert result.status == GoalStatus.STATUS_ABORTED and not result.result.success
    assert not rig.backend.get_status().is_moving and rig.backend.get_status().x == 0.0
    assert not rig.events
    new_goal = navigate(rig) if kind == 'navigation' else speak(rig)
    assert new_goal.accepted and wait_result(new_goal.get_result_async()).result.success


def test_feedback_publication_error_does_not_interrupt_navigation(rig, monkeypatch):
    original = rig.gateway._navigation_status.publish
    attempted = Event()

    def fail_going(message):
        if message.status == 'going':
            attempted.set()
            raise RuntimeError('模拟 ROS 反馈发布失败')
        return original(message)

    monkeypatch.setattr(rig.gateway._navigation_status, 'publish', fail_going)
    feedback = []
    goal = navigate(rig, feedback=feedback)
    result = wait_result(goal.get_result_async())
    assert attempted.is_set()
    assert result.status == GoalStatus.STATUS_SUCCEEDED and result.result.success
    wait_until(lambda: 'complete' in feedback and rig.snapshots[-1].current_location == 'near')
    assert 'going' in feedback
    assert not rig.snapshots[-1].is_moving and rig.snapshots[-1].x == 1.0


def test_duplicate_stop_service_waits_for_active_stop_confirmation(rig, monkeypatch):
    started = Event()
    release = asyncio.Event()
    original_stop = rig.backend.stop

    async def delayed_stop():
        started.set()
        await release.wait()
        return await original_stop()

    monkeypatch.setattr(rig.backend, 'stop', delayed_stop)
    nav = navigate(rig, 'far')
    speech = speak(rig)
    wait_until(lambda: rig.snapshots[-1].is_moving)
    first = rig.stop.call_async(StopRobot.Request(stop=True))
    try:
        assert started.wait(timeout=2.0)
        second = rig.stop.call_async(StopRobot.Request(stop=True))
        time.sleep(.15)
        assert not second.done() and not first.done()
    finally:
        rig.gateway._loop.call_soon_threadsafe(release.set)
    assert wait_result(first).success
    assert wait_result(second).success
    assert wait_result(nav.get_result_async()).status == GoalStatus.STATUS_ABORTED
    assert wait_result(speech.get_result_async()).status == GoalStatus.STATUS_SUCCEEDED


def test_navigation_and_speech_cancel_then_accept_new_goals(rig):
    nav = navigate(rig, 'far')
    speech = speak(rig)
    wait_until(lambda: rig.snapshots[-1].is_moving)
    assert wait_result(nav.cancel_goal_async()).goals_canceling
    assert wait_result(speech.cancel_goal_async()).goals_canceling
    for goal in (nav, speech):
        result = wait_result(goal.get_result_async())
        assert result.status == GoalStatus.STATUS_CANCELED and not result.result.success
    wait_until(lambda: not rig.snapshots[-1].is_moving)
    next_nav = navigate(rig, 'entrance')
    assert next_nav.accepted and wait_result(next_nav.get_result_async()).result.success
    next_speech = speak(rig)
    assert next_speech.accepted and wait_result(next_speech.get_result_async()).result.success


def test_invalid_goals_timeout_and_navigation_failure_release_slot(rig):
    assert not navigate(rig, '').accepted
    assert not navigate(rig, timeout_sec=-1.0).accepted
    assert not navigate(rig, timeout_sec=float('nan')).accepted
    assert not speak(rig, '   ').accepted
    for location, timeout in (('unknown', 2.0), ('far', 0.1)):
        goal = navigate(rig, location, timeout)
        result = wait_result(goal.get_result_async())
        assert result.status == GoalStatus.STATUS_ABORTED and not result.result.success
    rig.gateway._loop.call_soon_threadsafe(rig.backend.inject_navigation_failure)
    goal = navigate(rig)
    result = wait_result(goal.get_result_async())
    assert result.status == GoalStatus.STATUS_ABORTED and not result.result.success
    wait_until(lambda: rig.events[-1].status == 'abort')
    goal = navigate(rig)
    assert goal.accepted and wait_result(goal.get_result_async()).result.success


def test_disconnect_aborts_active_goals_and_stop_does_not_claim_success(rig):
    nav = navigate(rig, 'far')
    speech = speak(rig)
    wait_until(lambda: rig.snapshots[-1].is_moving)
    asyncio.run_coroutine_threadsafe(rig.backend.simulate_disconnect(), rig.gateway._loop).result(2.0)
    for goal in (nav, speech):
        result = wait_result(goal.get_result_async())
        assert result.status == GoalStatus.STATUS_ABORTED and not result.result.success
    wait_until(lambda: not rig.snapshots[-1].connected)
    assert rig.snapshots[-1].navigation_status == 'disconnected'
    assert not rig.snapshots[-1].is_moving and rig.snapshots[-1].error_message
    assert not wait_result(rig.stop.call_async(StopRobot.Request(stop=True))).success
    assert not navigate(rig).accepted
    assert not speak(rig).accepted


def test_close_disconnects_stops_loop_and_is_idempotent(rig):
    nav = navigate(rig, 'far')
    wait_until(lambda: rig.snapshots[-1].is_moving)
    rig.gateway.close()
    rig.gateway.close()
    assert not rig.backend.get_status().connected
    assert not rig.gateway._loop.is_running()
    result = wait_result(nav.get_result_async())
    assert result.status == GoalStatus.STATUS_ABORTED and not result.result.success
