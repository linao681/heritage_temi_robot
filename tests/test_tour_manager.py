"""纯导览状态机：用已实现 Mock 后端实际异步运行，不连接实体设备。"""

import asyncio
import itertools
from dataclasses import replace
from pathlib import Path

import pytest

from temi_bridge.mock_backend import MockConfig, MockTemiBackend

ROOT = Path(__file__).resolve().parents[1]


def load_config():
    from heritage_tour_manager.tour_config import TourConfig

    return TourConfig.from_yaml(ROOT / 'config/exhibits.yaml', ROOT / 'config/system.yaml')


async def wait_until(predicate, timeout=3.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        assert asyncio.get_running_loop().time() < deadline, '等待导览状态超时'
        await asyncio.sleep(0.005)


class MockTourRobot:
    def __init__(self, backend):
        self.backend = backend
        self.ids = itertools.count(1)
        self.navigation_calls = []
        self.speech_calls = []
        self.stop_count = 0

    async def navigate(self, location, timeout_sec):
        from heritage_tour_manager.tour_manager import OperationResult
        self.navigation_calls.append(location)
        result = await self.backend.navigate_to(location, timeout_sec, task_id=f'nav-{next(self.ids)}')
        return OperationResult(result.success, result.message)

    async def speak(self, text):
        from heritage_tour_manager.tour_manager import OperationResult
        self.speech_calls.append(text)
        result = await self.backend.speak(text, task_id=f'say-{next(self.ids)}')
        return OperationResult(result.success, result.message)

    async def stop(self):
        from heritage_tour_manager.tour_manager import OperationResult
        self.stop_count += 1
        result = await self.backend.stop()
        return OperationResult(result.success, result.message)


async def setup_rig(**config_overrides):
    from heritage_tour_manager.tour_manager import TourManager

    config = replace(load_config(), navigation_timeout_sec=3.0, consent_timeout_sec=1.0,
                     qa_timeout_sec=1.0, **config_overrides)
    locations = {exhibit.temi_location: (i * 0.3, 0.0) for i, exhibit in enumerate(config.route)}
    backend = MockTemiBackend(MockConfig(locations=locations, speed_mps=2.0, tick_sec=0.01,
                                        navigation_delay_sec=0.01, speech_delay_sec=0.035,
                                        battery_drain_per_meter=0.1))
    await backend.connect()
    driver = MockTourRobot(backend)
    changes = []
    manager = TourManager(driver, config, changes.append)

    def sync():
        snapshot = backend.get_status()
        manager.update_robot_status(connected=snapshot.connected, battery_percentage=snapshot.battery_percentage,
                                    current_location=snapshot.current_location, is_moving=snapshot.is_moving)

    async def pump():
        while True:
            sync()
            await asyncio.sleep(0.01)

    sync()
    monitor = asyncio.create_task(pump())
    return manager, backend, driver, changes, monitor


async def end_rig(manager, monitor):
    await manager.shutdown()
    monitor.cancel()
    await asyncio.gather(monitor, return_exceptions=True)


async def accept(manager):
    assert manager.start()
    await wait_until(lambda: manager.status()['state'] == 'WAITING_CONSENT')
    assert manager.consent(True)


def test_configuration_contains_all_eight_waypoints_and_guide_fields():
    config = load_config()
    assert [e.id for e in config.route] == ['entrance', 'exhibit_01', 'exhibit_02', 'exhibit_03',
                                             'exhibit_04', 'exhibit_05', 'interaction_zone', 'exit']
    assert all(e.name and e.temi_location and e.guide_content and e.guide_level for e in config.route)
    assert config.safe_return_location == config.route[0].temi_location


@pytest.mark.parametrize('pause_source', ['manual', 'team', 'safety'])
def test_automatic_resume_only_accepts_current_safety_pause_and_not_pending_cancel(pause_source):
    async def scenario():
        manager, _, driver, _, monitor = await setup_rig()
        try:
            await accept(manager)
            await wait_until(lambda: manager.state.value == 'NAVIGATING')
            pause = {'manual': manager.pause, 'team': manager.visitor_lost,
                     'safety': lambda: manager.safety_pause('session-a')}[pause_source]
            assert pause()
            await wait_until(lambda: manager.state.value == 'PAUSED' and not manager.is_moving)
            assert not manager.resume_safety('session-b', lambda: True)
            assert not manager.resume_safety('session-a', lambda: False)
            if pause_source == 'safety':
                assert not manager.resume()
                assert manager.resume_safety('session-a', lambda: True)
            assert manager.cancel()
            assert not manager.resume_safety('session-a', lambda: True)
            calls = len(driver.navigation_calls)
            await wait_until(lambda: not manager.running)
            assert len(driver.navigation_calls) == calls
        finally:
            await end_rig(manager, monitor)

    asyncio.run(scenario())


def test_safety_qualification_is_checked_again_at_resume_consumption():
    async def scenario():
        manager, _, driver, _, monitor = await setup_rig()
        try:
            await accept(manager)
            await wait_until(lambda: manager.state.value == 'NAVIGATING')
            assert manager.safety_pause('session-a')
            await wait_until(lambda: manager.state.value == 'PAUSED' and not manager.is_moving)
            checked = asyncio.Event()
            calls = len(driver.navigation_calls)
            checks = 0

            def guard():
                nonlocal checks
                checks += 1
                if checks > 1:
                    checked.set()
                return checks == 1

            assert manager.resume_safety('session-a', guard)
            await checked.wait()
            assert manager.state.value == 'PAUSED'
            assert len(driver.navigation_calls) == calls
        finally:
            await end_rig(manager, monitor)

    asyncio.run(scenario())


def test_cancel_queued_at_resumed_navigation_transition_prevents_goal_submission():
    async def scenario():
        manager, _, driver, _, monitor = await setup_rig()
        try:
            await accept(manager)
            await wait_until(lambda: manager.state.value == 'NAVIGATING')
            assert manager.safety_pause('session-a')
            await wait_until(lambda: manager.state.value == 'PAUSED' and not manager.is_moving)
            goal_count = len(driver.navigation_calls)
            loop = asyncio.get_running_loop()

            def on_change(status):
                if status['state'] == 'NAVIGATING':
                    loop.call_soon(manager.cancel)

            manager.on_change = on_change
            assert manager.resume_safety('session-a', lambda: True)
            await wait_until(lambda: not manager.running)
            assert len(driver.navigation_calls) == goal_count
            assert manager.outcome == 'canceled'
        finally:
            await end_rig(manager, monitor)

    asyncio.run(scenario())


def test_recovery_guard_revoked_at_resumed_transition_keeps_original_pause():
    async def scenario():
        manager, _, driver, _, monitor = await setup_rig()
        try:
            await accept(manager)
            await wait_until(lambda: manager.state.value == 'NAVIGATING')
            assert manager.safety_pause('session-a')
            await wait_until(lambda: manager.state.value == 'PAUSED' and not manager.is_moving)
            goal_count = len(driver.navigation_calls)
            loop = asyncio.get_running_loop()
            qualified = [True]
            revoked = asyncio.Event()

            def revoke():
                qualified[0] = False
                revoked.set()

            def on_change(status):
                if status['state'] == 'NAVIGATING':
                    loop.call_soon(revoke)

            manager.on_change = on_change
            assert manager.resume_safety('session-a', lambda: qualified[0])
            await revoked.wait()
            await wait_until(lambda: manager.state.value == 'PAUSED' or len(driver.navigation_calls) > goal_count)
            assert len(driver.navigation_calls) == goal_count
            assert manager.status()['paused_session_id'] == 'session-a'
            assert manager.status()['pause_source'] == 'safety'
        finally:
            await end_rig(manager, monitor)

    asyncio.run(scenario())


@pytest.mark.parametrize('found', [True, False])
def test_qa_question_speaks_and_then_completes(found):
    async def scenario():
        manager, backend, driver, changes, monitor = await setup_rig()
        text = '潮剧以潮州方言演唱。' if found else '暂未找到可靠资料。'
        async def lookup(question, exhibit, level):
            assert question == '潮剧用什么语言'
            return {'found': found, 'entry_id': 'opera_language' if found else '',
                    'answer': text, 'source': {'url': 'https://example.invalid'} if found else {}}
        manager.qa_lookup = lookup
        try:
            assert not manager.submit_question('潮剧用什么语言')
            await accept(manager)
            await wait_until(lambda: manager.state.value == 'QA')
            assert manager.submit_question('潮剧用什么语言')
            assert not manager.submit_question('第二个问题')
            assert not manager.finish_qa()
            await wait_until(lambda: manager.state.value == 'COMPLETED')
            assert text in driver.speech_calls
            assert manager.status()['qa_result']['found'] is found
            assert manager.status()['qa_result']['spoken']
            assert len(manager.visited) == 8
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario())


def test_qa_cancel_while_lookup_pending_never_speaks_late_answer():
    async def scenario():
        manager, backend, driver, changes, monitor = await setup_rig()
        entered = asyncio.Event()
        canceled = asyncio.Event()
        async def lookup(*args):
            entered.set()
            try:
                await asyncio.sleep(10)
            finally:
                canceled.set()
        manager.qa_lookup = lookup
        try:
            await accept(manager)
            await wait_until(lambda: manager.status()['qa_waiting'])
            assert manager.submit_question('潮剧用什么语言')
            await asyncio.wait_for(entered.wait(), 1)
            assert manager.cancel()
            await wait_until(lambda: manager.outcome == 'canceled')
            assert canceled.is_set() and manager.status()['qa_result'] is None
            assert 'exit' not in driver.navigation_calls
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario())


def test_complete_tour_visits_all_locations_in_order_and_records_states():
    async def scenario():
        manager, backend, driver, changes, monitor = await setup_rig()
        try:
            await accept(manager)
            await wait_until(lambda: manager.status()['state'] == 'QA')
            assert manager.finish_qa()
            await wait_until(lambda: manager.status()['state'] == 'COMPLETED')
            report = manager.status()
            assert report['outcome'] == 'completed' and report['error_count'] == 0
            expected = [e.temi_location for e in load_config().route]
            assert report['visited'] == expected and driver.navigation_calls == expected
            states = [entry['state'] for entry in report['history']]
            assert states[0] == 'IDLE' and states[-1] == 'COMPLETED'
            assert all(state in states for state in ('GREETING', 'WAITING_CONSENT', 'PLANNING',
                       'NAVIGATING', 'EXPLAINING', 'QA', 'RETURNING'))
            assert report['elapsed_sec'] > 0 and backend.get_status().current_location == 'exit'
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario())


def test_visitor_decline_does_not_send_navigation():
    async def scenario():
        manager, _, driver, _, monitor = await setup_rig()
        try:
            assert manager.start()
            await wait_until(lambda: manager.status()['state'] == 'WAITING_CONSENT')
            assert manager.consent(False)
            await wait_until(lambda: manager.status()['outcome'] == 'declined')
            assert manager.status()['state'] == 'IDLE' and not driver.navigation_calls
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario())


@pytest.mark.parametrize('mode', ['pause', 'visitor_lost'])
def test_pause_or_visitor_lost_stops_and_resumes_same_destination(mode):
    async def scenario():
        manager, backend, driver, _, monitor = await setup_rig()
        try:
            await accept(manager)
            await wait_until(lambda: backend.get_status().is_moving)
            target = driver.navigation_calls[-1]
            assert getattr(manager, mode)()
            await wait_until(lambda: manager.status()['state'] == 'PAUSED')
            position = backend.get_status().x
            assert driver.stop_count >= 1 and not backend.get_status().is_moving
            await asyncio.sleep(0.05)
            assert backend.get_status().x == position
            assert manager.resume()
            await wait_until(lambda: driver.navigation_calls.count(target) == 2)
            assert manager.cancel()
            await wait_until(lambda: manager.status()['outcome'] == 'canceled')
            assert not backend.get_status().is_moving
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario())


def test_manual_takeover_stops_and_releases_tour():
    async def scenario():
        manager, backend, driver, _, monitor = await setup_rig()
        try:
            await accept(manager)
            await wait_until(lambda: backend.get_status().is_moving)
            assert manager.manual_takeover()
            await wait_until(lambda: manager.status()['outcome'] == 'manual_takeover')
            assert manager.status()['state'] == 'IDLE' and driver.stop_count >= 1
            assert not backend.get_status().is_moving
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario())


def test_assisted_resume_revoked_before_checkpoint_needs_new_confirmation():
    async def scenario():
        manager, backend, driver, _, monitor = await setup_rig()
        ready = [True]
        try:
            assert manager.start(visitor_guard=lambda: ready[0])
            await wait_until(lambda: manager.state.value == 'WAITING_CONSENT')
            assert manager.consent(True)
            await wait_until(lambda: backend.get_status().is_moving)
            assert manager.visitor_lost()
            await wait_until(lambda: manager.state.value == 'PAUSED' and not manager.is_moving)
            previous = list(driver.navigation_calls)
            assert manager.resume()
            # 同一 loop 内恢复请求刚被接受，感知即失效；队伍稍后恢复也不能重用旧请求。
            ready[0] = False
            await asyncio.sleep(0.08)
            assert manager.state.value == 'PAUSED' and driver.navigation_calls == previous
            ready[0] = True
            await asyncio.sleep(0.08)
            assert manager.state.value == 'PAUSED' and driver.navigation_calls == previous
            assert manager.resume()
            await wait_until(lambda: len(driver.navigation_calls) > len(previous))
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario())


def test_assisted_brief_invalid_update_revokes_pending_resume_even_if_recovered():
    from heritage_tour_manager.visitor_assist import VisitorAssist

    async def scenario():
        manager, backend, driver, _, monitor = await setup_rig()
        expected = []
        assist = VisitorAssist(manager, expected.append, 10.0)

        def snapshot(count, group_count=0, group='untracked'):
            return {'source': 'mock', 'valid': True, 'stable': True, 'stable_fresh': True,
                    'people_count': count, 'expected_count': group_count, 'group_state': group}

        try:
            assist.robot_frame('mock_map')
            assist.observe(snapshot(0))
            assert assist.snapshot()['can_arm']
            assert assist.arm()
            assert not assist.snapshot()['can_arm']
            assist.observe(snapshot(0))
            assist.observe(snapshot(3))
            assert expected == [3]
            assist.observe(snapshot(3, 3, 'following'))
            await wait_until(lambda: manager.state.value == 'WAITING_CONSENT')
            assert manager.consent(True)
            await wait_until(lambda: backend.get_status().is_moving)
            assist.observe(snapshot(2, 3, 'lost'))
            await wait_until(lambda: manager.state.value == 'PAUSED' and not manager.is_moving)
            previous = list(driver.navigation_calls)
            assist.observe(snapshot(3, 3, 'following'))
            assert manager.resume()
            # 两次感知消息在恢复协程得到调度前连续到来，失效必须撤销旧恢复授权。
            assist.observe(snapshot(2, 3, 'lost'))
            assist.observe(snapshot(3, 3, 'following'))
            await asyncio.sleep(0.08)
            assert manager.state.value == 'PAUSED' and driver.navigation_calls == previous
            assert manager.resume()
            await wait_until(lambda: len(driver.navigation_calls) > len(previous))
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario())


def test_camera_group_assist_on_map_frame_requires_manual_resume_after_dropout():
    from heritage_tour_manager.visitor_assist import VisitorAssist

    async def scenario():
        manager, backend, driver, _, monitor = await setup_rig()
        expected = []
        assist = VisitorAssist(manager, expected.append, 10.0)

        def snapshot(count, group_count=0, group='untracked'):
            return {'source': 'camera', 'valid': True, 'stable': True,
                    'stable_fresh': True, 'people_count': count,
                    'expected_count': group_count, 'group_state': group}

        try:
            assist.robot_frame('map')
            assist.observe(snapshot(0))
            assert assist.snapshot()['can_arm']
            assert assist.arm()
            assist.observe(snapshot(0))
            assist.observe(snapshot(3))
            assert expected == [3]
            assist.observe(snapshot(3, 3, 'following'))
            await wait_until(lambda: manager.state.value == 'WAITING_CONSENT')
            assert manager.consent(True)
            await wait_until(lambda: backend.get_status().is_moving)
            assist.observe(snapshot(2, 3, 'lost'))
            await wait_until(lambda: manager.state.value == 'PAUSED' and not manager.is_moving)
            previous = list(driver.navigation_calls)
            assist.observe(snapshot(3, 3, 'following'))
            assert manager.resume()
            await wait_until(lambda: len(driver.navigation_calls) > len(previous))
        finally:
            await end_rig(manager, monitor)

    asyncio.run(scenario())


def test_low_battery_interrupts_and_returns_to_safe_configured_location():
    async def scenario():
        manager, backend, driver, _, monitor = await setup_rig()
        try:
            await accept(manager)
            await wait_until(lambda: backend.get_status().is_moving and backend.get_status().x > 0.0)
            backend.set_battery_percentage(10.0)
            await wait_until(lambda: manager.status()['state'] == 'ERROR', timeout=5.0)
            assert manager.status()['outcome'] == 'low_battery_returned'
            assert driver.navigation_calls[-1] == load_config().safe_return_location
            assert manager.status()['target'] == load_config().safe_return_location
            assert backend.get_status().current_location == 'entrance'
            assert manager.status()['error_count'] >= 1 and not backend.get_status().is_moving
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario())


@pytest.mark.parametrize('during_stop', ['lower_priority', 'manual_takeover'])
def test_checkpoint_keeps_priority_until_stop_confirmation(during_stop):
    from heritage_tour_manager.tour_manager import OperationResult, TourManager, TourState, _LowBattery, _TourEnd

    async def scenario():
        class Robot:
            async def stop(self):
                await asyncio.sleep(0)
                if during_stop == 'lower_priority':
                    manager.visitor_lost()
                    manager.update_robot_status(connected=True, battery_percentage=10.0,
                                                current_location='entrance', is_moving=False)
                else:
                    manager.manual_takeover()
                return OperationResult(True, '停车已确认')

        manager = TourManager(Robot(), load_config())
        manager._task = asyncio.create_task(asyncio.Event().wait())
        manager.state = TourState.NAVIGATING
        manager.update_robot_status(connected=True, battery_percentage=10.0,
                                    current_location='entrance', is_moving=True)
        try:
            if during_stop == 'lower_priority':
                with pytest.raises(_LowBattery):
                    await manager._checkpoint()
                assert manager._control is None  # 不残留掉队暂停或重复低电量命令
                assert manager.error_count == 0
            else:
                with pytest.raises(_TourEnd) as result:
                    await manager._checkpoint()
                assert result.value.outcome == 'manual_takeover'
        finally:
            manager._task.cancel()
            await asyncio.gather(manager._task, return_exceptions=True)

    asyncio.run(scenario())


def test_disconnect_or_navigation_failure_ends_in_error_not_success():
    async def scenario(disconnect):
        manager, backend, _, _, monitor = await setup_rig()
        try:
            if not disconnect:
                backend.inject_navigation_failure()
            await accept(manager)
            if disconnect:
                await wait_until(lambda: backend.get_status().is_moving)
                await backend.simulate_disconnect()
            await wait_until(lambda: manager.status()['state'] == 'ERROR')
            assert manager.status()['outcome'] == 'error' and manager.status()['error_count'] >= 1
            assert not backend.get_status().is_moving
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario(False))
    asyncio.run(scenario(True))


def test_consent_timeout_declines_and_qa_timeout_continues_route():
    async def scenario():
        manager, _, _, _, monitor = await setup_rig()
        try:
            assert manager.start()
            await wait_until(lambda: manager.status()['outcome'] == 'consent_timeout')
            assert manager.status()['state'] == 'IDLE'
            await accept(manager)
            await wait_until(lambda: manager.status()['state'] == 'QA')
            await wait_until(lambda: manager.status()['state'] == 'COMPLETED', timeout=3.0)
            assert manager.status()['outcome'] == 'completed'
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario())


def test_unconfirmed_motion_stop_enters_error_instead_of_paused():
    from heritage_tour_manager.tour_manager import OperationResult

    async def scenario():
        manager, backend, driver, _, monitor = await setup_rig()
        try:
            await accept(manager)
            await wait_until(lambda: backend.get_status().is_moving)

            async def uncertain_stop():
                return OperationResult(False, '未确认停车')

            driver.stop = uncertain_stop
            assert manager.pause()
            await wait_until(lambda: manager.status()['state'] == 'ERROR')
            assert not manager.resume() and '停车未确认' in manager.status()['reason']
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario())


def test_unconfirmed_action_cancellation_cannot_claim_idle():
    async def scenario():
        manager, _, driver, _, monitor = await setup_rig()
        started = asyncio.Event()

        async def uncertain_speech(_text):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                raise RuntimeError('旧 Action 未确认终止')

        driver.speak = uncertain_speech
        try:
            assert manager.start()
            await started.wait()
            assert manager.cancel()
            await wait_until(lambda: manager.status()['state'] == 'ERROR')
            assert '未确认' in manager.status()['reason']
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario())


def test_completed_failed_action_racing_cancel_still_requires_stop_confirmation():
    from heritage_tour_manager.tour_manager import OperationResult

    async def scenario():
        manager, _, driver, _, monitor = await setup_rig()

        async def failed_navigation(_location, _timeout):
            manager.cancel()
            return OperationResult(False, '旧 ROS Action 未确认终止')

        driver.navigate = failed_navigation
        try:
            await accept(manager)
            await wait_until(lambda: manager.status()['state'] == 'ERROR', timeout=1.0)
            assert driver.stop_count >= 1 and '未确认' in manager.status()['reason']
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario())


def test_navigation_exception_attempts_stop_and_reports_error():
    async def scenario():
        manager, _, driver, _, monitor = await setup_rig()

        async def broken_navigation(_location, _timeout):
            raise RuntimeError('通信异常')

        driver.navigate = broken_navigation
        try:
            await accept(manager)
            await wait_until(lambda: manager.status()['state'] == 'ERROR')
            assert driver.stop_count >= 1 and '通信异常' in manager.status()['reason']
        finally:
            await end_rig(manager, monitor)
    asyncio.run(scenario())
