import sys
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros2_ws/src/temi_speed_controller'))
from temi_speed_controller.speed_policy import SpeedConfig, SpeedController, SpeedInputs


def step(controller, now, **changes):
    sample = dict(
        now=now, nearest_person_m=3.0, crowd_density=0.2, obstacle_distance_m=2.0,
        group_state='following', navigating=False, explaining=False, navigation_error=False,
        safety_stop=False, position_valid=True, communication_valid=True,
        stop_confirmed=True, stop_confirmed_session_id='original', navigation_session_id='',
        person_distance_timestamp_sec=now, current_speed_mps=0.0, current_speed_valid=True,
    )
    return controller.update(SpeedInputs(**(sample | changes)), now)


@pytest.mark.parametrize('state', ['EXPLAINING', 'QA', 'GREETING', 'WAITING_CONSENT', 'IDLE', 'COMPLETED'])
def test_stationary_sensor_stop_does_not_create_manual_tour_pause(state):
    from temi_speed_controller.speed_controller_node import SpeedControllerNode
    calls = []
    node = SimpleNamespace(_stop_future=None, _tour_state=state,
                           _send_stop_direct=lambda: calls.append('stop'))
    SpeedControllerNode._send_stop(node, SimpleNamespace(state='STOPPING', reason='感知数据无效或过期'))
    assert calls == ['stop']


def waiting():
    controller = SpeedController(SpeedConfig(recovery_hold_sec=0.3, input_timeout_sec=0.2))
    assert step(controller, 1.0, navigation_session_id='original', navigating=True,
                stop_confirmed=False, obstacle_distance_m=0.4).stop_requested
    assert step(controller, 1.01, obstacle_distance_m=0.4).state == 'STOPPED'
    assert step(controller, 1.1).state == 'WAITING'
    assert not step(controller, 1.2).resume_requested
    return controller


@pytest.mark.parametrize('interruption', [
    {'sample_age_sec': 0.21},
    {'person_distance_timestamp_sec': 1.19},
    {'stop_confirmed': False},
    {'stop_confirmed_session_id': 'other'},
    {'current_speed_valid': False},
    {'current_speed_mps': 0.03},
    {'current_angular_speed_rps': 0.07},
    {'obstacle_distance_valid': False, 'nearest_person_m': None,
     'person_distance_valid': False, 'person_observation_state': 'NO_PERSON_OBSERVED'},
])
def test_recovery_interruption_restarts_hold(interruption):
    controller = waiting()
    assert not step(controller, 1.3, **interruption).resume_requested
    assert not step(controller, 1.45).resume_requested
    for now in (1.55, 1.65):
        assert not step(controller, now).resume_requested
    assert step(controller, 1.76).resume_requested


def test_sampling_gap_restarts_hold_even_if_next_sample_is_fresh():
    controller = waiting()
    assert not step(controller, 1.45).resume_requested
    for now in (1.55, 1.65):
        assert not step(controller, now).resume_requested
    assert step(controller, 1.76).resume_requested


def test_monotonic_clock_regression_restarts_hold():
    controller = waiting()
    assert not step(controller, 1.15).resume_requested
    for now in (1.25, 1.35, 1.44):
        assert not step(controller, now).resume_requested
    assert step(controller, 1.56).resume_requested


def test_replayed_navigation_cannot_reopen_retired_uuid():
    controller = SpeedController()
    for index, session in enumerate(('original', 'replacement')):
        assert step(controller, 1.0 + index * 0.1, navigating=True,
                    navigation_session_id=session, stop_confirmed=False).send_speed
    replay = step(controller, 1.2, navigating=True,
                  navigation_session_id='original', stop_confirmed=False)
    assert not replay.send_speed


def test_stale_resume_future_cannot_change_new_session():
    pytest.importorskip('rclpy')
    from temi_speed_controller.speed_controller_node import SpeedControllerNode

    node = SpeedControllerNode.__new__(SpeedControllerNode)
    node._policy = SpeedController()
    node._recovery = {'decision_id': 'new-decision', 'service_result': None,
                      'stopped_session_id': 'new-session'}
    node._resume_requested_at = 2.0
    node._resume_future = Future()
    old = Future()
    old.set_result(SimpleNamespace(success=False))

    node._on_resume_result(old)

    assert node._policy.state == 'IDLE'
    assert node._resume_requested_at == 2.0
    assert node._recovery['service_result'] is None


def test_only_acknowledged_recovery_can_send_one_trigger():
    pytest.importorskip('rclpy')
    from temi_speed_controller.speed_controller_node import SpeedControllerNode

    node = SpeedControllerNode.__new__(SpeedControllerNode)
    node._resume_future = None
    node._resume_requested_at = None
    node._recovery = {'decision_id': 'decision', 'request_sent_at': None,
                      'stopped_session_id': 'session'}
    calls = []

    def call_async(request):
        calls.append(request)
        return Future()

    node._resume_client = SimpleNamespace(service_is_ready=lambda: True, call_async=call_async)
    node._tour_status = {'recovery_ack_id': 'old', 'paused_session_id': 'session',
                         'pause_source': 'safety', 'state': 'PAUSED'}
    node._tour_received_at = 10.0
    node._maybe_send_resume(10.0)
    assert not calls
    node._tour_status['recovery_ack_id'] = 'decision'
    node._maybe_send_resume(10.1)
    node._maybe_send_resume(10.2)
    assert len(calls) == 1


@pytest.mark.parametrize('hazard', [
    {'valid': False},
    {'nearest_person_m': 0.5},
    {'obstacle_distance_m': 0.3},
    {'stop_confirmed_session_id': 'other'},
    {'sample_timestamp_monotonic_sec': 1.05},
    {'sample_age_sec': 0.3},
])
def test_transient_invalid_fused_sample_between_ticks_breaks_the_hold(hazard, monkeypatch):
    pytest.importorskip('rclpy')
    from temi_interfaces.msg import PerceptionInput
    from temi_speed_controller.speed_controller_node import SpeedControllerNode

    node = SpeedControllerNode.__new__(SpeedControllerNode)
    node._policy = waiting()
    assert not step(node._policy, 1.25).resume_requested
    node._last_navigation_session_id = 'original'
    node._mock_mode = False
    node._allow_simulated_sources = True
    node._input = None
    import temi_speed_controller.speed_controller_node as adapter
    monkeypatch.setattr(adapter.time, 'monotonic', lambda: 1.3)
    clear = dict(source='gazebo_sensor_fusion', valid=True,
                 sample_timestamp_monotonic_sec=1.25, sample_age_sec=0.02,
                 person_observation_valid=True, person_distance_valid=True,
                 nearest_person_m=3.0, person_observation_state='PERSON_DISTANCE_VALID',
                 obstacle_distance_valid=True, obstacle_distance_m=2.0,
                 safety_stop_valid=True, stop_confirmed=True, stop_confirmed_session_id='original',
                 position_valid=True, communication_valid=True, group_state='following')
    node._on_fused_input(PerceptionInput(**clear))
    node._on_fused_input(PerceptionInput(**(clear | hazard)))
    node._on_fused_input(PerceptionInput(**clear))

    assert not step(node._policy, 1.43).resume_requested


@pytest.mark.parametrize('hazard', [
    {'nearest_person_m': 0.5},
    {'obstacle_distance_m': 0.3},
    {'stop_confirmed_session_id': 'wrong'},
])
def test_tour_cannot_forget_transient_hazard_after_recovery_proposal(hazard, monkeypatch):
    pytest.importorskip('rclpy')
    from temi_interfaces.msg import PerceptionInput
    from heritage_tour_manager import ros_tour_node as adapter

    node = adapter.HeritageTourNode.__new__(adapter.HeritageTourNode)
    monkeypatch.setattr(adapter.time, 'monotonic', lambda: 10.1)
    status = dict(state='PAUSED', pause_source='safety', connected=True, is_moving=False,
                  paused_session_id='old', target='zone')
    node._manager = SimpleNamespace(status=lambda: status)
    node._fused = None
    node._last_telemetry = 10.0
    node._recovery_interrupted_at = -float('inf')
    evidence = dict(decision_id='decision', stopped_session_id='old', original_target='zone',
                    manual_latched=False, error_latched=False, clear_since=7.9, hold_sec=2.0,
                    evidence_at=10.0, evidence_sample_id=9.9, sample_age_sec=0.1, odom_age_sec=0.01,
                    position_age_sec=0.1, input_timeout_sec=1.0,
                    minimum_person_distance_m=1.4, minimum_laser_distance_m=0.65)
    node._update_recovery(evidence, 10.0)
    clear = dict(valid=True, sample_timestamp_monotonic_sec=9.9, sample_age_sec=0.1,
                 person_observation_valid=True, person_distance_valid=True, nearest_person_m=3.0,
                 obstacle_distance_valid=True, obstacle_distance_m=2.0,
                 position_valid=True, communication_valid=True, safety_stop_valid=True, safety_stop=False,
                 stop_confirmed=True, stop_confirmed_session_id='old', group_state='following')
    node._update_fused(PerceptionInput(**clear), 10.0)
    assert node._recovery_ack(status) == 'decision'
    node._update_fused(PerceptionInput(**(clear | hazard)), 10.05)
    node._update_fused(PerceptionInput(**clear), 10.06)
    assert node._recovery_ack(status) == ''


def test_speed_adapter_odom_age_keeps_source_delay_after_receipt(monkeypatch):
    pytest.importorskip('rclpy')
    from nav_msgs.msg import Odometry
    from temi_speed_controller import speed_controller_node as adapter

    node = adapter.SpeedControllerNode.__new__(adapter.SpeedControllerNode)
    node._policy = waiting()
    node._odom_stamp_ns = 0
    node._odom_received_at = None
    monkeypatch.setattr(adapter.time, 'monotonic', lambda: 1.3)
    stamp = [100_000_000_000]
    monkeypatch.setattr(adapter.SpeedControllerNode, 'get_clock',
                        lambda _: SimpleNamespace(now=lambda: SimpleNamespace(nanoseconds=stamp[0])))
    msg = Odometry()
    msg.header.stamp.sec = 99
    msg.header.stamp.nanosec = 600_000_000
    node._on_odom(msg)
    assert node._odom_age(1.3) == pytest.approx(0.4)
    stamp[0] += 200_000_000
    assert node._odom_age(1.5) > 0.5


def test_ros_action_rechecks_navigation_guard_after_waiting_for_server(monkeypatch):
    import asyncio
    pytest.importorskip('rclpy')
    from heritage_tour_manager import ros_tour_node as adapter

    async def scenario():
        robot = adapter._RosTourRobot.__new__(adapter._RosTourRobot)
        robot._config = SimpleNamespace(communication_timeout_sec=1.0)
        robot._cleanup = {}
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []
        permitted = [True]

        async def ready(*_):
            entered.set()
            await release.wait()

        def send(request):
            calls.append(request)
            result = Future()
            result.set_result(SimpleNamespace(accepted=False))
            return result

        monkeypatch.setattr(adapter, '_wait_ready', ready)
        class Client(SimpleNamespace):
            __hash__ = object.__hash__

        robot._navigation = Client(server_is_ready=lambda: True, send_goal_async=send)
        robot.navigation_send_guard = lambda: permitted[0]
        task = asyncio.create_task(robot._action(robot._navigation, object(), 1.0))
        await asyncio.wait_for(entered.wait(), 2.0)
        permitted[0] = False
        release.set()
        result = await task
        assert not calls
        assert not result.success
        assert not result.submitted

    asyncio.run(scenario())
