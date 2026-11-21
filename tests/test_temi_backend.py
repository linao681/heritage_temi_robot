"""TemiBackend 共享契约的验收测试，不依赖实体机器人。"""

import inspect
from dataclasses import FrozenInstanceError

import pytest


def test_backend_requires_all_six_operations():
    from temi_bridge.backend import TemiBackend

    assert TemiBackend.__abstractmethods__ == {
        'connect', 'disconnect', 'navigate_to', 'stop', 'speak', 'get_status',
    }
    with pytest.raises(TypeError):
        TemiBackend()


def test_commands_are_async_but_snapshot_is_nonblocking():
    from temi_bridge.backend import TemiBackend

    for name in ('connect', 'disconnect', 'navigate_to', 'stop', 'speak'):
        assert inspect.iscoroutinefunction(getattr(TemiBackend, name))
    assert not inspect.iscoroutinefunction(TemiBackend.get_status)


def test_navigation_and_speech_have_command_id_and_feedback():
    from temi_bridge.backend import TemiBackend

    for name, positional in (
        ('navigate_to', ['self', 'location', 'timeout_sec']),
        ('speak', ['self', 'text']),
    ):
        parameters = inspect.signature(getattr(TemiBackend, name)).parameters
        assert list(parameters) == [*positional, 'task_id', 'feedback']
        assert parameters['task_id'].kind == inspect.Parameter.KEYWORD_ONLY
        assert parameters['task_id'].default is inspect.Parameter.empty
        assert parameters['feedback'].kind == inspect.Parameter.KEYWORD_ONLY
        assert parameters['feedback'].default is None


def test_disconnected_snapshot_is_safe_and_immutable():
    from temi_bridge.backend import RobotSnapshot

    status = RobotSnapshot()
    assert not status.connected
    assert status.battery_percentage == -1.0
    assert not status.is_moving
    assert status.navigation_status == 'disconnected'
    assert status.frame_id == ''
    with pytest.raises(FrozenInstanceError):
        status.connected = True


def test_snapshot_fields_match_ros_status_contract():
    from temi_bridge.backend import RobotSnapshot

    status = RobotSnapshot(
        connected=True, battery_percentage=83.5, x=1.0, y=2.0, yaw=0.5,
        navigation_status='going', current_location='entrance', is_moving=True,
        error_message='', frame_id='mock_map',
    )
    assert (status.x, status.y, status.yaw) == (1.0, 2.0, 0.5)
    assert status.battery_percentage == 83.5
    assert status.current_location == 'entrance' and status.frame_id == 'mock_map'
    assert status.connected and status.is_moving


def test_feedback_correlates_with_command_id():
    from temi_bridge.backend import NavigationFeedback, SpeechFeedback, TaskResult

    nav = NavigationFeedback('nav_001', 'exhibit_01', 'going', '导航中')
    speech = SpeechFeedback('speech_001', 'started')
    result = TaskResult(success=False, message='任务已取消')
    assert (nav.task_id, nav.target, nav.status, nav.description) == (
        'nav_001', 'exhibit_01', 'going', '导航中',
    )
    assert (speech.task_id, speech.status) == ('speech_001', 'started')
    assert not result.success and result.message == '任务已取消'
