import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros2_ws/src/temi_speed_controller'))
from temi_speed_controller.speed_policy import (SpeedConfig, SpeedController, SpeedInputs,
    perception_source_allowed)


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


def test_valid_empty_person_observation_allows_safe_cruise_without_fake_distance():
    decision = SpeedController().update(sample(
        nearest_person_m=None, person_distance_valid=False,
        person_observation_state='NO_PERSON_OBSERVED', crowd_density=None,
        crowd_density_valid=False, obstacle_distance_valid=True), now=0.0)

    assert decision.state == 'SLOW'
    assert decision.target_speed_mps == 0.5
    assert decision.send_speed
    assert not decision.stop_requested


def test_invalid_visitor_count_does_not_discard_valid_person_distance():
    decision = SpeedController().update(sample(
        nearest_person_m=0.5, people_valid=False, person_distance_valid=True,
        person_observation_state='PERSON_DISTANCE_VALID'), now=0.0)

    assert decision.state == 'STOPPING'
    assert decision.reason == '近距离人员停车'
    assert decision.stop_requested


def test_close_laser_obstacle_is_not_mislabeled_as_a_person_stop():
    decision = SpeedController().update(sample(
        nearest_person_m=None, person_distance_valid=False,
        person_observation_state='NO_PERSON_OBSERVED', obstacle_distance_m=0.08), now=0.0)

    assert decision.state == 'STOPPING'
    assert decision.reason == '近距离障碍物停车'
    assert decision.stop_requested


def test_person_and_laser_stop_sources_are_both_reported_when_both_trigger():
    decision = SpeedController().update(sample(
        nearest_person_m=0.5, person_distance_valid=True,
        person_observation_state='PERSON_DISTANCE_VALID', obstacle_distance_m=0.4), now=0.0)

    assert decision.state == 'STOPPING'
    assert decision.reason == '人员与障碍物近距离停车'
    assert decision.stop_requested


def test_valid_no_person_observation_is_not_a_sensor_fault_when_count_is_unknown():
    decision = SpeedController().update(sample(
        nearest_person_m=None, people_valid=False, person_distance_valid=False,
        person_observation_state='NO_PERSON_OBSERVED', crowd_density=None,
        crowd_density_valid=False), now=0.0)

    assert decision.state == 'SLOW'
    assert not decision.stop_requested


def test_invalid_person_observation_still_fails_closed_when_count_is_unknown():
    decision = SpeedController().update(sample(
        nearest_person_m=None, people_valid=False, person_distance_valid=False,
        person_observation_state='SENSOR_INVALID'), now=0.0)

    assert decision.state == 'STOPPING'
    assert decision.reason == '感知数据无效或过期'
    assert decision.stop_requested


def test_person_proximity_reduces_speed_when_crowd_density_is_uncalibrated():
    far = SpeedController().update(sample(
        nearest_person_m=3.2, crowd_density=None, crowd_density_valid=False), now=0.0)
    near = SpeedController().update(sample(
        nearest_person_m=1.8, crowd_density=None, crowd_density_valid=False), now=0.0)

    assert far.target_speed_mps == 0.5
    assert near.target_speed_mps < far.target_speed_mps
    assert near.state == 'SLOW'


def test_conservative_stop_floor_triggers_before_observed_near_field_dropout():
    controller = SpeedController(SpeedConfig(
        stop_person_distance_m=1.3, person_stop_margin_m=0.2))
    decision = controller.update(sample(
        nearest_person_m=1.2, person_distance_valid=True,
        person_observation_state='PERSON_DISTANCE_VALID'), now=0.0)

    assert decision.stop_requested
    assert decision.reason == '近距离人员停车'


def test_python_defaults_match_conservative_ros_person_stop_parameters():
    config = SpeedConfig()

    assert config.stop_person_distance_m == 1.3
    assert config.person_stop_margin_m == 0.9


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
    stopped = controller.update(sample(now=0.1, obstacle_distance_m=0.4, stop_confirmed=True,
                                       stop_confirmed_session_id='active'), now=0.1)
    assert stopped.state == 'STOPPED'
    waiting = controller.update(sample(now=0.2, obstacle_distance_m=0.4, stop_confirmed=True,
                                       stop_confirmed_session_id='active'), now=0.2)
    assert waiting.state == 'STOPPED'


def test_dynamic_threshold_shrinking_during_braking_cannot_skip_stop_confirmation():
    controller = SpeedController(SpeedConfig(recovery_hold_sec=0.1))
    pending = controller.update(sample(nearest_person_m=0.5), now=0.0)
    clear_but_unconfirmed = controller.update(sample(now=0.2, nearest_person_m=2.0,
        current_speed_mps=0.1, current_speed_valid=True), now=0.2)

    assert pending.stop_requested
    assert clear_but_unconfirmed.state == 'STOPPING'
    assert not clear_but_unconfirmed.send_speed
    assert not clear_but_unconfirmed.resume_requested


def test_stop_confirmation_from_old_navigation_session_is_ignored():
    controller = SpeedController()
    controller.update(sample(navigation_session_id='new-session', obstacle_distance_m=0.4), now=0)

    decision = controller.update(sample(now=0.1, navigation_session_id='new-session',
        obstacle_distance_m=0.4, stop_confirmed=True,
        stop_confirmed_session_id='old-session'), now=0.1)

    assert decision.state == 'STOPPING'
    assert not decision.send_speed


def test_current_navigation_session_stop_confirmation_is_accepted():
    controller = SpeedController()
    controller.update(sample(navigation_session_id='current-session', obstacle_distance_m=0.4), now=0)

    decision = controller.update(sample(now=0.1, navigation_session_id='current-session',
        obstacle_distance_m=0.4, stop_confirmed=True,
        stop_confirmed_session_id='current-session'), now=0.1)

    assert decision.state == 'STOPPED'


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


def test_untrusted_simulation_source_fails_closed_in_live_mode():
    decision = SpeedController().update(sample(source_allowed=False), now=0)

    assert decision.state == 'STOPPING'
    assert decision.target_speed_mps is None
    assert decision.stop_requested


def test_unconfirmed_safety_stop_signal_fails_closed():
    decision = SpeedController().update(sample(safety_stop_valid=False), now=0)

    assert decision.state == 'STOPPING'
    assert decision.target_speed_mps is None
    assert decision.stop_requested


def test_unknown_crowd_density_uses_conservative_default_without_claiming_a_measurement():
    decision = SpeedController().update(
        sample(crowd_density=None, crowd_density_valid=False), now=0)

    assert decision.state == 'SLOW'
    assert decision.target_speed_mps == 0.5
    assert not decision.stop_requested


def test_offline_video_source_is_never_an_allowed_motion_input():
    assert not perception_source_allowed('offline_video', mock_mode=True,
                                         allow_simulated_sources=True)
    assert not perception_source_allowed('mock', mock_mode=False,
                                         allow_simulated_sources=False)
    assert perception_source_allowed('mock', mock_mode=True,
                                     allow_simulated_sources=False)
    assert perception_source_allowed('temi_sensor_fusion', mock_mode=False,
                                     allow_simulated_sources=False)


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


def test_idle_startup_does_not_latch_before_navigation_and_sensors_are_ready():
    decision = SpeedController().update(sample(
        navigating=False, navigation_session_id='', communication_valid=False,
        position_valid=False, safety_stop=True, safety_stop_valid=False,
        sample_age_sec=float('inf')), now=0)

    assert decision.state == 'IDLE'
    assert decision.target_speed_mps is None
    assert not decision.stop_requested


def test_old_navigation_session_cannot_be_reused():
    controller = SpeedController()
    first = controller.update(sample(navigation_session_id='old'), now=0)
    assert first.navigation_session_id == 'old'
    changed = controller.update(sample(now=0.1, navigation_session_id='new'), now=0.1)
    assert changed.navigation_session_id == 'new'
    assert changed.send_speed


def test_failed_speed_result_from_finished_session_does_not_poison_new_navigation():
    controller = SpeedController()
    stale = controller.update(sample(navigation_session_id='instant-wait'), now=0.0)
    current = controller.update(sample(now=0.1, navigation_session_id='zone-1'), now=0.1)

    assert stale.send_speed and current.send_speed
    controller.report_speed_result(False, navigation_session_id='instant-wait')

    assert controller.state != 'ERROR'
    retry = controller.update(sample(now=0.2, navigation_session_id='zone-1'), now=0.2)
    assert retry.send_speed
    assert retry.navigation_session_id == 'zone-1'


def test_stale_speed_failure_after_current_session_confirmation_does_not_retrigger_command():
    controller = SpeedController()
    old = controller.update(sample(navigation_session_id='instant-wait'), now=0.0)
    current = controller.update(sample(now=0.1, navigation_session_id='zone-1'), now=0.1)
    controller.report_speed_result(True, navigation_session_id='zone-1')

    controller.report_speed_result(False, navigation_session_id='instant-wait')
    next_decision = controller.update(sample(now=0.2, navigation_session_id='zone-1'), now=0.2)

    assert controller.state != 'ERROR'
    assert not next_decision.send_speed
    assert old.navigation_session_id != current.navigation_session_id


def test_speed_failure_is_stale_when_nav_status_advanced_before_policy_tick():
    controller = SpeedController()
    old = controller.update(sample(navigation_session_id='instant-wait'), now=0.0)

    controller.report_speed_result(
        False, navigation_session_id=old.navigation_session_id,
        current_navigation_session_id='zone-1')
    next_decision = controller.update(sample(now=0.1, navigation_session_id='zone-1'), now=0.1)

    assert controller.state != 'ERROR'
    assert next_decision.send_speed
    assert next_decision.navigation_session_id == 'zone-1'


def test_failed_speed_result_for_current_navigation_session_latches_error():
    controller = SpeedController()
    decision = controller.update(sample(navigation_session_id='zone-1'), now=0.0)

    controller.report_speed_result(
        False, navigation_session_id=decision.navigation_session_id,
        current_navigation_session_id='zone-1')

    assert controller.state == 'ERROR'


def test_waiting_for_confirmed_stop_can_resume_only_after_stable_clear_period():
    controller = SpeedController(SpeedConfig(recovery_hold_sec=1.0))
    controller.update(sample(obstacle_distance_m=0.4), now=0)
    waiting = controller.update(sample(now=0.1, obstacle_distance_m=0.4, stop_confirmed=True,
                                      stop_confirmed_session_id='active',
                                      navigating=False), now=0.1)
    assert waiting.state == 'STOPPED'
    clearing = controller.update(sample(now=0.2, stop_confirmed=True,
                                       stop_confirmed_session_id='active', navigating=False,
                                       obstacle_distance_m=0.75), now=0.2)
    assert clearing.state == 'WAITING' and not clearing.resume_requested
    resumed = controller.update(sample(now=1.3, stop_confirmed=True,
                                      stop_confirmed_session_id='active', navigating=False,
                                      obstacle_distance_m=0.75), now=1.3)
    assert resumed.state == 'RECOVERING'
    assert resumed.resume_requested
    new_goal = controller.update(sample(now=1.4, navigation_session_id='new-goal'), now=1.4)
    assert new_goal.state == 'RECOVERING'
    assert new_goal.target_speed_mps == 0.3
    assert new_goal.send_speed
    controller.report_speed_result(True, navigation_session_id='old-goal',
                                   recovery_command=True)
    assert controller.state == 'RECOVERING'
    controller.report_speed_result(True, navigation_session_id='new-goal',
                                   recovery_command=True)
    accelerating = controller.update(sample(now=1.5, navigation_session_id='new-goal'), now=1.5)
    assert accelerating.state != 'RECOVERING'
    assert accelerating.target_speed_mps > 0.3


def test_stable_obstacle_clearance_above_stop_plus_hysteresis_can_resume():
    controller = SpeedController(SpeedConfig(recovery_hold_sec=1.0))
    controller.update(sample(obstacle_distance_m=0.4), now=0.0)
    controller.update(sample(now=0.1, obstacle_distance_m=0.4, stop_confirmed=True,
                             stop_confirmed_session_id='active', navigating=False), now=0.1)

    controller.update(sample(now=0.2, obstacle_distance_m=0.662, stop_confirmed=True,
                             stop_confirmed_session_id='active', navigating=False), now=0.2)
    recovered = controller.update(sample(now=1.3, obstacle_distance_m=0.662,
                                          stop_confirmed=True,
                                          stop_confirmed_session_id='active',
                                          navigating=False), now=1.3)

    assert recovered.state == 'RECOVERING'
    assert recovered.resume_requested


def test_obstacle_below_stop_plus_hysteresis_remains_waiting():
    controller = SpeedController(SpeedConfig(recovery_hold_sec=1.0))
    controller.update(sample(obstacle_distance_m=0.4), now=0.0)
    controller.update(sample(now=0.1, obstacle_distance_m=0.4, stop_confirmed=True,
                             stop_confirmed_session_id='active', navigating=False), now=0.1)

    controller.update(sample(now=0.2, obstacle_distance_m=0.64, stop_confirmed=True,
                             stop_confirmed_session_id='active', navigating=False), now=0.2)
    waiting = controller.update(sample(now=1.3, obstacle_distance_m=0.64,
                                       stop_confirmed=True,
                                       stop_confirmed_session_id='active',
                                       navigating=False), now=1.3)

    assert waiting.state == 'WAITING'
    assert not waiting.resume_requested


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


def test_dynamic_stopping_distance_increases_with_speed_and_latency():
    slow = SpeedController(SpeedConfig(
        perception_control_latency_sec=0.2, person_stop_margin_m=0.2)).update(
            sample(nearest_person_m=1.0, person_distance_valid=True,
                   current_speed_mps=0.2, current_speed_valid=True), now=0.0)
    fast = SpeedController(SpeedConfig(
        perception_control_latency_sec=0.6, person_stop_margin_m=0.5)).update(
            sample(nearest_person_m=1.0, person_distance_valid=True,
                   current_speed_mps=0.6, current_speed_valid=True), now=0.0)

    assert fast.stop_requested
    assert fast.dynamic_stop_distance_m > slow.dynamic_stop_distance_m


def test_approaching_person_trend_raises_stop_distance_using_new_samples_only():
    controller = SpeedController(SpeedConfig(
        perception_control_latency_sec=0.4, person_stop_margin_m=0.9,
        person_slow_buffer_m=1.5, max_person_approach_speed_mps=1.0))
    first = controller.update(sample(nearest_person_m=2.0, person_distance_valid=True,
        person_distance_timestamp_sec=0.0, current_speed_mps=0.3, current_speed_valid=True), now=0.0)
    second = controller.update(sample(now=0.1, nearest_person_m=1.9,
        person_distance_valid=True, person_distance_timestamp_sec=0.1,
        current_speed_mps=0.3, current_speed_valid=True), now=0.1)
    repeated = controller.update(sample(now=0.2, nearest_person_m=1.9,
        person_distance_valid=True, person_distance_timestamp_sec=0.1,
        current_speed_mps=0.3, current_speed_valid=True), now=0.2)
    near = controller.update(sample(now=0.3, nearest_person_m=1.8,
        person_distance_valid=True, person_distance_timestamp_sec=0.2,
        current_speed_mps=0.3, current_speed_valid=True), now=0.3)

    assert first.dynamic_stop_distance_m < second.dynamic_stop_distance_m
    assert repeated.approach_speed_mps == second.approach_speed_mps
    assert near.stop_requested
    assert near.state == 'STOPPING'
    assert near.reason == '近距离人员停车'


def test_invalid_or_empty_person_observation_clears_approach_history():
    controller = SpeedController()
    controller.update(sample(now=1.0, nearest_person_m=2.0, person_distance_valid=True,
        person_distance_timestamp_sec=1.0), now=1.0)
    approaching = controller.update(sample(now=1.1, nearest_person_m=1.8,
        person_distance_valid=True, person_distance_timestamp_sec=1.1), now=1.1)
    empty = controller.update(sample(now=1.2, nearest_person_m=None,
        person_distance_valid=False, person_observation_state='NO_PERSON_OBSERVED',
        people_valid=True, person_distance_timestamp_sec=1.2), now=1.2)

    assert approaching.approach_speed_mps > 0
    assert empty.approach_speed_mps == 0


def test_regressed_person_timestamp_clears_approach_estimate():
    controller = SpeedController()
    controller.update(sample(now=1.0, nearest_person_m=2.0, person_distance_valid=True,
        person_distance_timestamp_sec=1.0), now=1.0)
    approaching = controller.update(sample(now=1.1, nearest_person_m=1.8,
        person_distance_valid=True, person_distance_timestamp_sec=1.1), now=1.1)
    regressed = controller.update(sample(now=1.2, nearest_person_m=1.9,
        person_distance_valid=True, person_distance_timestamp_sec=1.05), now=1.2)

    assert approaching.approach_speed_mps > 0
    assert regressed.approach_speed_mps == 0


def test_dynamic_stop_configuration_rejects_invalid_latency_margin_and_speed():
    import pytest

    for values in ({'perception_control_latency_sec': 0},
                   {'person_stop_margin_m': -0.1},
                   {'max_person_approach_speed_mps': float('inf')},
                   {'person_slow_buffer_m': 0}):
        with pytest.raises(ValueError):
            SpeedConfig(**values)
