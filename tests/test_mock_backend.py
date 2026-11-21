"""Mock 后端行为测试：使用实际 asyncio 延时，不需要 ROS 或 Android。"""

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest


def make_config(**overrides):
    from temi_bridge.mock_backend import MockConfig

    config = MockConfig(
        locations={'entrance': (0.0, 0.0), 'exhibit_01': (1.0, 0.0),
                   'exhibit_02': (1.0, 1.0)},
        speed_mps=4.0, navigation_delay_sec=0.01, tick_sec=0.01,
        speech_delay_sec=0.08, speech_timeout_sec=1.0,
        initial_battery_percentage=90.0, battery_drain_per_meter=2.0,
    )
    return replace(config, **overrides)


def make_backend(**overrides):
    from temi_bridge.mock_backend import MockTemiBackend

    return MockTemiBackend(make_config(**overrides))


async def wait_until(predicate, timeout=1.5):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            pytest.fail('未在超时前观测到预期状态')
        await asyncio.sleep(0.005)


def test_yaml_configuration_has_virtual_destinations_and_no_random_failures():
    from temi_bridge.mock_backend import MockConfig

    config = MockConfig.from_yaml(Path(__file__).resolve().parents[1] / 'config/system.yaml')
    assert config.navigation_failure_probability == 0.0
    assert config.speed_mps > 0
    assert set(config.locations) == {
        'entrance', 'exhibit_01', 'exhibit_02', 'exhibit_03', 'exhibit_04',
        'exhibit_05', 'interaction_zone', 'exit',
    }


@pytest.mark.parametrize('override', [
    {'speed_mps': 0.0}, {'tick_sec': -0.1}, {'navigation_failure_probability': 1.5},
    {'initial_location': 'not_in_map'}, {'speech_timeout_sec': 0.0},
    {'initial_battery_percentage': 120.0},
])
def test_invalid_configuration_is_rejected(override):
    with pytest.raises(ValueError):
        make_config(**override)


def test_connect_disconnect_and_reconnect_preserve_position():
    async def scenario():
        backend = make_backend()
        assert not backend.get_status().connected
        assert (await backend.connect()).success
        snapshot = backend.get_status()
        assert snapshot.connected and snapshot.current_location == 'entrance'
        assert snapshot.connection_epoch == 1
        assert snapshot.frame_id == 'mock_map' and snapshot.battery_percentage == 90.0
        assert (await backend.connect()).success
        assert backend.get_status().connection_epoch == 1
        assert (await backend.navigate_to('exhibit_01', 2.0, task_id='nav_01')).success
        assert (await backend.disconnect()).success
        assert not backend.get_status().connected
        assert (await backend.connect()).success
        assert backend.get_status().connection_epoch == 2
        assert backend.get_status().current_location == 'exhibit_01'
        assert backend.get_status().x == 1.0

    asyncio.run(scenario())


def test_navigation_moves_continuously_and_drains_battery():
    async def scenario():
        backend = make_backend()
        await backend.connect()
        events = []
        navigation = asyncio.create_task(backend.navigate_to(
            'exhibit_01', 2.0, task_id='nav_01', feedback=events.append,
        ))
        await wait_until(lambda: 0.0 < backend.get_status().x < 1.0)
        first = backend.get_status()
        assert first.is_moving and first.navigation_status == 'going'
        assert not navigation.done()
        await wait_until(lambda: first.x < backend.get_status().x < 1.0)
        second = backend.get_status()
        assert second.x > first.x and second.battery_percentage < first.battery_percentage
        result = await navigation
        final = backend.get_status()
        assert result.success and final.x == 1.0 and final.y == 0.0
        assert not final.is_moving and final.current_location == 'exhibit_01'
        assert final.battery_percentage == pytest.approx(88.0)
        assert [event.status for event in events] == ['start', 'calculating', 'going', 'complete']
        assert all(event.task_id == 'nav_01' and event.target == 'exhibit_01' for event in events)

    asyncio.run(scenario())


def test_configured_speed_and_planning_delay_affect_real_elapsed_time():
    async def scenario():
        async def duration(speed):
            backend = make_backend(speed_mps=speed, navigation_delay_sec=0.08)
            await backend.connect()
            loop = asyncio.get_running_loop()
            timestamps = {}

            def observe(event):
                timestamps[event.status] = loop.time()

            assert (await backend.navigate_to('exhibit_01', 3.0, task_id='timed', feedback=observe)).success
            assert timestamps['going'] - timestamps['calculating'] >= 0.075
            movement_elapsed = timestamps['complete'] - timestamps['going']
            assert movement_elapsed >= 1.0 / speed - 0.01
            return movement_elapsed

        fast = await duration(8.0)
        slow = await duration(2.0)
        assert slow > fast + 0.2

    asyncio.run(scenario())


def test_explicit_navigation_failure_is_one_shot():
    async def scenario():
        backend = make_backend()
        await backend.connect()
        backend.inject_navigation_failure()
        events = []
        result = await backend.navigate_to('exhibit_01', 2.0, task_id='fail', feedback=events.append)
        assert not result.success and events[-1].status == 'abort'
        assert backend.get_status().x == 0.0 and not backend.get_status().is_moving
        assert backend.get_status().error_message
        assert (await backend.navigate_to('exhibit_01', 2.0, task_id='retry')).success

    asyncio.run(scenario())


def test_configured_failure_probability_is_respected():
    async def scenario():
        backend = make_backend(navigation_failure_probability=1.0)
        await backend.connect()
        assert not (await backend.navigate_to('exhibit_01', 2.0, task_id='fail')).success
        assert backend.get_status().navigation_status == 'abort'

    asyncio.run(scenario())


def test_stop_interrupts_navigation_immediately_without_stopping_speech():
    async def scenario():
        backend = make_backend(speed_mps=2.0, speech_delay_sec=0.25)
        await backend.connect()
        events = []
        nav = asyncio.create_task(backend.navigate_to('exhibit_01', 3.0, task_id='nav', feedback=events.append))
        speech = asyncio.create_task(backend.speak('欢迎', task_id='speech'))
        await wait_until(lambda: backend.get_status().x > 0.0)
        assert (await backend.stop()).success
        stopped = backend.get_status()
        assert not stopped.is_moving
        assert not (await nav).success and events[-1].status == 'stopped'
        await asyncio.sleep(0.04)
        assert backend.get_status().x == stopped.x < 1.0
        assert (await speech).success

    asyncio.run(scenario())


def test_timeout_and_cancel_release_navigation():
    async def scenario():
        backend = make_backend(speed_mps=2.0)
        await backend.connect()
        events = []
        result = await backend.navigate_to('exhibit_01', 0.06, task_id='timeout', feedback=events.append)
        assert not result.success and events[-1].status == 'timeout'
        assert not backend.get_status().is_moving and backend.get_status().x < 1.0
        nav = asyncio.create_task(backend.navigate_to('exhibit_01', 2.0, task_id='cancel'))
        await wait_until(lambda: backend.get_status().is_moving)
        nav.cancel()
        with pytest.raises(asyncio.CancelledError):
            await nav
        assert not backend.get_status().is_moving
        assert (await backend.navigate_to('exhibit_01', 2.0, task_id='retry')).success

    asyncio.run(scenario())


def test_network_drop_aborts_tasks_and_reconnect_does_not_replay():
    async def scenario():
        backend = make_backend(speed_mps=2.0, speech_delay_sec=0.5)
        await backend.connect()
        nav_events, speech_events = [], []
        nav = asyncio.create_task(backend.navigate_to('exhibit_01', 2.0, task_id='nav', feedback=nav_events.append))
        speech = asyncio.create_task(backend.speak('测试', task_id='speech', feedback=speech_events.append))
        await wait_until(lambda: backend.get_status().is_moving and bool(speech_events))
        await backend.simulate_disconnect()
        interrupted = backend.get_status()
        assert not interrupted.connected and not interrupted.is_moving
        assert interrupted.navigation_status == 'disconnected'
        assert not (await nav).success and nav_events[-1].status == 'disconnected'
        assert not (await speech).success and speech_events[-1].status == 'error'
        assert not (await backend.stop()).success
        await backend.connect()
        await asyncio.sleep(0.04)
        assert backend.get_status().x == interrupted.x
        assert backend.get_status().navigation_status == 'idle'
        assert (await backend.navigate_to('exhibit_01', 2.0, task_id='retry')).success

    asyncio.run(scenario())


def test_stop_allows_immediate_replacement_without_old_task_overwriting_state():
    async def scenario():
        backend = make_backend(speed_mps=2.0)
        await backend.connect()
        old_events = []
        old_nav = asyncio.create_task(backend.navigate_to(
            'exhibit_01', 3.0, task_id='old', feedback=old_events.append,
        ))
        await wait_until(lambda: backend.get_status().x > 0.0)
        assert (await backend.stop()).success
        # 不先等待旧任务的协程完成：新任务应立即可接受。
        replacement = await backend.navigate_to('exhibit_02', 3.0, task_id='new')
        assert replacement.success
        assert not (await old_nav).success and old_events[-1].status == 'stopped'
        assert backend.get_status().current_location == 'exhibit_02'
        assert backend.get_status().navigation_status == 'complete'

    asyncio.run(scenario())


def test_immediate_reconnect_accepts_new_tasks_and_ignores_old_completions():
    async def scenario():
        backend = make_backend(speed_mps=2.0, speech_delay_sec=0.2)
        await backend.connect()
        old_nav = asyncio.create_task(backend.navigate_to('exhibit_01', 3.0, task_id='old_nav'))
        old_speech = asyncio.create_task(backend.speak('旧任务', task_id='old_speech'))
        await wait_until(lambda: backend.get_status().is_moving)
        await backend.simulate_disconnect()
        await backend.connect()
        new_nav, new_speech = await asyncio.gather(
            backend.navigate_to('exhibit_02', 3.0, task_id='new_nav'),
            backend.speak('新任务', task_id='new_speech'),
        )
        assert new_nav.success and new_speech.success
        assert not (await old_nav).success and not (await old_speech).success
        assert backend.get_status().connected and backend.get_status().current_location == 'exhibit_02'

    asyncio.run(scenario())


def test_cancel_concurrent_with_disconnect_propagates_to_both_tasks():
    async def scenario():
        backend = make_backend(navigation_delay_sec=1.0, speech_delay_sec=1.0)
        await backend.connect()
        nav_events, speech_events = [], []
        nav = asyncio.create_task(backend.navigate_to('exhibit_01', 3.0, task_id='nav', feedback=nav_events.append))
        speech = asyncio.create_task(backend.speak('播报', task_id='speech', feedback=speech_events.append))
        await wait_until(lambda: len(nav_events) >= 2 and bool(speech_events))
        await backend.simulate_disconnect()
        # Event 等待完成与显式取消同时发生时，也不能吞掉取消信号。
        await asyncio.sleep(0)
        assert nav.cancel() and speech.cancel()
        for task in (nav, speech):
            with pytest.raises(asyncio.CancelledError):
                await task
        assert not backend.get_status().is_moving and not backend.get_status().connected
        assert (await backend.connect()).success

    asyncio.run(scenario())


def test_speech_has_correlated_feedback_timeout_and_cancellation():
    async def scenario():
        backend = make_backend()
        await backend.connect()
        events = []
        assert (await backend.speak('欢迎', task_id='say', feedback=events.append)).success
        assert [(event.task_id, event.status) for event in events] == [('say', 'started'), ('say', 'complete')]
        slow = make_backend(speech_delay_sec=0.5, speech_timeout_sec=0.02)
        await slow.connect()
        events = []
        assert not (await slow.speak('测试', task_id='timeout', feedback=events.append)).success
        assert events[-1].status == 'error'
        events.clear()
        task = asyncio.create_task(backend.speak('取消', task_id='cancel', feedback=events.append))
        await wait_until(lambda: bool(events))
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert events[-1].status == 'canceled'
        assert (await backend.speak('恢复', task_id='retry')).success

    asyncio.run(scenario())


def test_low_battery_and_invalid_or_conflicting_commands():
    async def scenario():
        backend = make_backend(speed_mps=2.0, speech_delay_sec=0.2)
        assert not (await backend.navigate_to('exhibit_01', 1.0, task_id='offline')).success
        assert not (await backend.speak('不能播报', task_id='offline')).success
        await backend.connect()
        backend.set_battery_percentage(12.0)
        assert backend.get_status().battery_percentage == 12.0
        with pytest.raises(ValueError):
            backend.set_battery_percentage(-5.0)
        for location, timeout, task_id in [('missing', 1.0, 'a'), ('exhibit_01', 0.0, 'b'),
                                            ('exhibit_01', 1.0, '')]:
            assert not (await backend.navigate_to(location, timeout, task_id=task_id)).success
        assert not (await backend.speak(' ', task_id='empty')).success
        nav = asyncio.create_task(backend.navigate_to('exhibit_01', 2.0, task_id='active_nav'))
        await wait_until(lambda: backend.get_status().is_moving)
        assert not (await backend.navigate_to('exhibit_02', 2.0, task_id='conflict')).success
        speech = asyncio.create_task(backend.speak('开始', task_id='active_speech'))
        await asyncio.sleep(0.02)
        assert not (await backend.speak('重复', task_id='conflict')).success
        await backend.stop()
        await nav
        await speech

    asyncio.run(scenario())


def test_mock_dynamic_speed_only_applies_to_active_navigation_session():
    async def scenario():
        backend = make_backend(speed_mps=0.35)
        await backend.connect()
        navigation = asyncio.create_task(backend.navigate_to('exhibit_01', 3.0, task_id='nav_current'))
        await wait_until(lambda: backend.get_status().navigation_status == 'going')
        applied = await backend.set_navigation_speed(0.3, command_id='speed_current',
            navigation_session_id='nav_current', control_reason='crowd')
        stale = await backend.set_navigation_speed(0.8, command_id='speed_old',
            navigation_session_id='nav_old', control_reason='open')
        assert applied.success
        assert not stale.success
        await backend.stop()
        await navigation

    asyncio.run(scenario())
