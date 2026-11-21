import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros2_ws/src/temi_speed_controller'))
from temi_speed_controller.speed_policy import SpeedConfig, SpeedController, SpeedInputs


def sample(**changes):
    values = dict(now=0.0, nearest_person_m=3.2, crowd_density=0.1,
                  obstacle_distance_m=3.0, group_state='following', navigating=True,
                  explaining=False, navigation_error=False, safety_stop=False,
                  position_valid=True, communication_valid=True, stop_confirmed=False,
                  navigation_session_id='active', sample_age_sec=0.0)
    values.update(changes)
    return SpeedInputs(**values)


def test_open_area_uses_configured_open_speed():
    decision = SpeedController().update(sample(), now=0.0)
    assert decision.target_speed_mps == 0.7
    assert decision.state == 'NORMAL'


def test_crowd_and_person_proximity_only_reduce_speed():
    controller = SpeedController()
    open_speed = controller.update(sample(), now=0).target_speed_mps
    slow = controller.update(sample(now=0.1, crowd_density=0.8, nearest_person_m=1.8), now=0.1)
    assert slow.target_speed_mps <= open_speed
    assert slow.state == 'SLOW'


def test_lost_group_waits_for_configured_duration_then_requests_stop():
    controller = SpeedController(SpeedConfig(lost_group_stop_sec=1.0))
    first = controller.update(sample(group_state='lost'), now=0)
    assert not first.stop_requested
    decision = controller.update(sample(now=1.1, group_state='lost'), now=1.1)
    assert decision.stop_requested
    assert decision.state == 'STOPPING'


def test_stop_confirmation_is_required_before_waiting_state():
    controller = SpeedController()
    pending = controller.update(sample(obstacle_distance_m=0.4), now=0)
    assert pending.state == 'STOPPING'
    assert pending.stop_requested
    stopped = controller.update(sample(now=0.1, obstacle_distance_m=0.4, stop_confirmed=True), now=0.1)
    assert stopped.state == 'STOPPED'
    waiting = controller.update(sample(now=0.2, obstacle_distance_m=0.4, stop_confirmed=True), now=0.2)
    assert waiting.state == 'STOPPED'


def test_stale_or_invalid_perception_fails_closed():
    controller = SpeedController(SpeedConfig(input_timeout_sec=0.5))
    stale = controller.update(sample(now=0.0), now=1.0)
    assert stale.target_speed_mps is None
    assert stale.stop_requested
    assert stale.state == 'STOPPING'


def test_explaining_never_requests_positive_speed():
    decision = SpeedController().update(sample(explaining=True), now=0)
    assert decision.target_speed_mps is None
    assert decision.stop_requested


def test_speed_commands_are_rate_limited_and_not_sent_for_tiny_changes():
    controller = SpeedController(SpeedConfig(command_interval_sec=0.5, min_speed_delta_mps=0.05))
    first = controller.update(sample(navigation_session_id='session'), now=0)
    assert first.send_speed
    too_soon = controller.update(sample(now=0.1, crowd_density=0.8, navigation_session_id='session'), now=0.1)
    assert not too_soon.send_speed
    later = controller.update(sample(now=0.6, crowd_density=0.8, navigation_session_id='session'), now=0.6)
    assert later.send_speed


def test_error_is_latched_until_explicit_reset():
    controller = SpeedController()
    failed = controller.update(sample(communication_valid=False), now=0)
    assert failed.state == 'ERROR'
    recovered_input = sample(now=1.0, navigation_session_id='session')
    assert controller.update(recovered_input, now=1.0).state == 'ERROR'
    controller.reset_error()
    assert controller.update(recovered_input, now=1.1).state == 'NORMAL'


def test_old_navigation_session_cannot_be_reused():
    controller = SpeedController()
    first = controller.update(sample(navigation_session_id='old'), now=0)
    assert first.navigation_session_id == 'old'
    changed = controller.update(sample(now=0.1, navigation_session_id='new'), now=0.1)
    assert changed.navigation_session_id == 'new'
    assert changed.send_speed


def test_waiting_for_confirmed_stop_can_resume_only_after_stable_clear_period():
    controller = SpeedController(SpeedConfig(recovery_hold_sec=1.0))
    controller.update(sample(obstacle_distance_m=0.4), now=0)
    waiting = controller.update(sample(now=0.1, obstacle_distance_m=0.4, stop_confirmed=True,
                                      navigating=False), now=0.1)
    assert waiting.state == 'STOPPED'
    clearing = controller.update(sample(now=0.2, stop_confirmed=True, navigating=False), now=0.2)
    assert clearing.state == 'WAITING' and not clearing.resume_requested
    resumed = controller.update(sample(now=1.3, stop_confirmed=True, navigating=False), now=1.3)
    assert resumed.state == 'RECOVERING'
    assert resumed.resume_requested
    new_goal = controller.update(sample(now=1.4, navigation_session_id='new-goal'), now=1.4)
    assert new_goal.state == 'RECOVERING'
    assert new_goal.target_speed_mps == 0.3


def test_obstacle_distance_moves_through_slow_and_stop_zones():
    controller = SpeedController()
    normal = controller.update(sample(), now=0)
    slow = controller.update(sample(now=0.6, obstacle_distance_m=1.0), now=0.6)
    stop = controller.update(sample(now=1.2, obstacle_distance_m=0.5), now=1.2)
    assert slow.target_speed_mps < normal.target_speed_mps
    assert stop.stop_requested and stop.target_speed_mps is None


def test_talking_and_safety_stop_request_pause_without_speed_zero():
    for fields in ({'explaining': True}, {'safety_stop': True}):
        decision = SpeedController().update(sample(**fields), now=0)
        assert decision.stop_requested
        assert decision.target_speed_mps is None


def test_invalid_or_stale_measurements_never_select_open_area_speed():
    for values in ({'nearest_person_m': None}, {'obstacle_distance_m': None},
                   {'crowd_density': None}, {'crowd_density': float('nan')}):
        decision = SpeedController().update(sample(**values), now=0)
        assert decision.target_speed_mps is None
        assert decision.stop_requested


def test_sdk_rejection_latches_error_until_operator_reset():
    controller = SpeedController()
    controller.report_speed_result(False)
    assert controller.update(sample(), now=0).state == 'ERROR'
    controller.reset_error()
    assert controller.update(sample(), now=0.1).state == 'NORMAL'


def test_communication_or_sdk_failure_requests_stop_once_then_latches_error():
    controller = SpeedController()
    failed = controller.update(sample(communication_valid=False), now=0)
    assert failed.state == 'ERROR'
    assert failed.stop_requested
    repeated = controller.update(sample(now=0.1, communication_valid=False), now=0.1)
    assert repeated.state == 'ERROR'
    assert not repeated.stop_requested


def test_active_navigation_without_session_id_fails_closed():
    decision = SpeedController().update(sample(navigation_session_id=''), now=0)
    assert decision.state == 'ERROR'
    assert decision.stop_requested
    assert decision.target_speed_mps is None


def test_stale_sensor_measurement_fails_closed_even_if_its_topic_is_refreshed():
    decision = SpeedController(SpeedConfig(input_timeout_sec=0.5)).update(
        sample(sample_age_sec=0.7), now=0.0)
    assert decision.state == 'STOPPING'
    assert decision.stop_requested
