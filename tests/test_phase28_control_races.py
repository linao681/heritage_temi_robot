import asyncio
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from action_msgs.msg import GoalStatus

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros2_ws/src/heritage_tour_manager'))
sys.path.insert(0, str(ROOT / 'ros2_ws/src/temi_bridge'))

from heritage_tour_manager.tour_config import TourConfig
from heritage_tour_manager.tour_manager import TourManager, TourState
from heritage_tour_manager.ros_tour_node import HeritageTourNode, _RosTourRobot, OperationResult
from temi_bridge.nav2_transport import arrival_stop_confirmed


def make_manager():
    config = TourConfig.from_yaml(ROOT / 'config/exhibits.yaml', ROOT / 'config/system.yaml')
    manager = TourManager(object(), config)
    manager._task = SimpleNamespace(done=lambda: False)
    return manager


def test_user_cancel_supersedes_pending_safety_pause_and_cannot_be_downgraded():
    manager = make_manager()
    manager.state = TourState.NAVIGATING

    assert manager.safety_pause('nav-old')
    assert manager.cancel()
    assert not manager.safety_pause('nav-old')
    assert manager._control == ('cancel', '用户取消导览')


def test_team_loss_latches_without_downgrading_pending_safety_stop():
    manager = make_manager()
    manager.state = TourState.NAVIGATING

    assert manager.safety_pause('nav-old')
    assert manager.visitor_lost()
    assert manager._control == ('safety_pause', '导航安全停车')
    assert manager.status()['team_recovery_required'] is True
    assert manager.error_count == 1


def test_team_loss_during_safety_pause_waits_for_gather_and_operator_ack():
    manager = make_manager()
    manager.state = TourState.PAUSED
    manager._pause_source = 'safety'
    manager._paused_session_id = 'nav-old'
    manager.connected = True
    manager.is_moving = False
    team_ready = [False]
    manager._visitor_guard = lambda: team_ready[0]

    assert manager.visitor_lost()
    assert manager._control is None
    assert not manager.resume()
    assert not manager.resume_safety('nav-old', lambda: True)

    team_ready[0] = True
    assert manager.resume()
    assert manager.status()['team_resume_confirmed'] is True
    assert not manager._resume_event.is_set()
    assert manager.resume_safety('nav-old', lambda: True)
    assert manager._resume_event.is_set()


def test_manual_pause_supersedes_automatic_safety_pause():
    manager = make_manager()
    manager.state = TourState.NAVIGATING

    assert manager.safety_pause('nav-old')
    assert manager.pause()
    assert manager._control == ('pause', '用户暂停')


def test_duplicate_pause_does_not_enqueue_another_control():
    manager = make_manager()
    manager.state = TourState.PAUSED
    manager._pause_source = 'safety'

    assert manager.pause()
    assert not manager.pause()
    assert manager._control == ('pause', '用户暂停')


def test_safety_resume_requires_stationary_robot_and_is_one_shot():
    manager = make_manager()
    manager.state = TourState.PAUSED
    manager._pause_source = 'safety'
    manager._paused_session_id = 'nav-old'
    manager.connected = True
    manager.is_moving = True

    assert not manager.resume_safety('nav-old', lambda: True)
    manager.is_moving = False
    assert manager.resume_safety('nav-old', lambda: True)
    assert not manager.resume_safety('nav-old', lambda: True)


def test_action_cancel_ack_alone_does_not_settle_old_goal():
    async def scenario():
        loop = asyncio.get_running_loop()
        acceptance = loop.create_future()
        cancel_ack = loop.create_future()
        cancel_sent = asyncio.Event()
        result_waiting = asyncio.Event()

        class HeldResult:
            value = None

            def done(self):
                if cancel_ack.done() and self.value is None:
                    result_waiting.set()
                return self.value is not None

            def result(self):
                return self.value

            def set_result(self, value):
                self.value = value

        action_result = HeldResult()

        class Goal:
            accepted = True

            def get_result_async(self):
                return action_result

            def cancel_goal_async(self):
                cancel_sent.set()
                return cancel_ack

        acceptance.set_result(Goal())
        robot = _RosTourRobot.__new__(_RosTourRobot)
        robot._config = SimpleNamespace(communication_timeout_sec=0.2)
        robot._node = SimpleNamespace(get_logger=lambda: SimpleNamespace(error=lambda *_: None))

        task = asyncio.create_task(robot._settle_goal(acceptance, None, None))
        await cancel_sent.wait()
        cancel_ack.set_result(SimpleNamespace(goals_canceling=[object()]))
        await result_waiting.wait()
        assert not task.done()
        action_result.set_result(SimpleNamespace(status=GoalStatus.STATUS_CANCELED))
        assert await task

    asyncio.run(scenario())


@pytest.mark.parametrize('last_sample, now', [(10.0, 10.6), (10.4, 10.3)])
def test_stale_or_future_odom_cannot_confirm_a_stop(last_sample, now):
    assert not arrival_stop_confirmed(stable_since=9.0, last_sample=last_sample, now=now)


def test_recovery_is_rejected_if_tour_target_changed_since_stop():
    node = HeritageTourNode.__new__(HeritageTourNode)
    node._speed_recovery = ({'decision_id': 'decision', 'stopped_session_id': 'nav-old',
                             'original_target': 'zone_2', 'manual_latched': False,
                             'error_latched': False}, 10.0)
    node._fused = (object(), 10.0, True)
    status = {'state': 'PAUSED', 'pause_source': 'safety', 'connected': True,
              'is_moving': False, 'paused_session_id': 'nav-old', 'target': 'zone_3'}

    assert node._recovery_ack(status) == ''


def test_repeated_team_recovery_reuses_the_same_exhibit_without_skipping_route():
    async def scenario():
        changes = asyncio.Queue()
        nav_started = asyncio.Queue()

        class Robot:
            def __init__(self):
                self.manager = None
                self.stop_count = 0

            async def speak(self, text):
                return OperationResult(True, 'Mock播报完成')

            async def navigate(self, location, timeout_sec):
                release = asyncio.Event()
                await nav_started.put((location, release))
                self.manager.update_robot_status(connected=True, battery_percentage=100.0,
                                                 current_location='entrance', is_moving=True)
                await release.wait()
                return OperationResult(True, 'Mock到达')

            async def stop(self):
                self.stop_count += 1
                self.manager.update_robot_status(connected=True, battery_percentage=100.0,
                                                 current_location='entrance', is_moving=False)
                return OperationResult(True, 'Mock停车已确认')

        async def wait_state(expected, **matches):
            while True:
                status = await changes.get()
                if status['state'] == expected and all(status.get(key) == value
                                                       for key, value in matches.items()):
                    return status

        robot = Robot()
        config = TourConfig.from_yaml(ROOT / 'config/exhibits.yaml', ROOT / 'config/system.yaml')
        manager = TourManager(robot, config, lambda status: changes.put_nowait(status))
        robot.manager = manager
        manager.update_robot_status(connected=True, battery_percentage=100.0,
                                    current_location='entrance', is_moving=False)
        assert manager.start()
        await wait_state('WAITING_CONSENT')
        assert manager.consent(True)

        first_target, _ = await nav_started.get()
        for _ in range(2):
            assert manager.visitor_lost()
            paused = await wait_state('PAUSED', team_resume_confirmed=False)
            assert paused['route_index'] == 0
            assert paused['target'] == first_target
            assert manager.resume()
            next_target, _ = await nav_started.get()
            assert next_target == first_target

        assert manager.route_index == 0
        assert manager.target == first_target
        assert manager.cancel()
        await manager._task
        assert manager.outcome == 'canceled'
        assert robot.stop_count == 3

    asyncio.run(scenario())

