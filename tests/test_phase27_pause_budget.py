from types import SimpleNamespace

from scripts.run_phase25_clean_tour import (
    safety_pause_timeout_budget_sec,
    validate_leaving_recovery_evidence,
)


def test_approaching_recovery_budget_covers_actor_path_and_buffer():
    args = SimpleNamespace(
        dynamic_scenario='approaching', continue_after_robot_stop=True,
        scenario_end_distance_m=3.5, person_speed_mps=0.1,
        hold_at_target_sec=2.0, leave_after_hold=True,
        leave_distance_m=3.1, hold_clear_sec=1.0, timeout_sec=900.0,
    )

    assert safety_pause_timeout_budget_sec(args) == 74.0


def test_recovery_budget_never_exceeds_tour_timeout():
    args = SimpleNamespace(
        dynamic_scenario='approaching', continue_after_robot_stop=True,
        scenario_end_distance_m=3.5, person_speed_mps=0.1,
        hold_at_target_sec=2.0, leave_after_hold=True,
        leave_distance_m=3.1, hold_clear_sec=1.0, timeout_sec=60.0,
    )

    assert safety_pause_timeout_budget_sec(args) == 60.0


def test_other_scenarios_keep_the_short_pause_timeout():
    args = SimpleNamespace(
        dynamic_scenario='none', continue_after_robot_stop=False,
        timeout_sec=20.0,
    )

    assert safety_pause_timeout_budget_sec(args) == 20.0


def test_recovery_evidence_accepts_near_person_stop_and_clear_after_new_uuid():
    truth = {'movement_started_monotonic_sec': 10.0,
             'movement_ended_monotonic_sec': 20.0}
    speed_events = [
        {'time_monotonic_sec': 12.0, 'status': {
            'state': 'STOPPING', 'reason': '近距离人员停车',
            'navigation_session_id': 'old', 'input_valid': True}},
        {'time_monotonic_sec': 13.0, 'status': {
            'state': 'RECOVERING', 'reason': '安全条件恢复；请求导览状态机重新导航',
            'resume_requested': True}},
    ]
    stop_events = [
        {'time_monotonic_sec': 12.6, 'state': 'STOP_CONFIRMED',
         'navigation_session_id': 'old', 'valid': True},
        {'time_monotonic_sec': 13.8, 'state': 'CLEAR',
         'navigation_session_id': 'new', 'valid': True},
    ]
    navigation_events = [
        {'time_monotonic_sec': 11.0, 'task_id': 'old', 'target': 'zone_1',
         'status': 'going'},
        {'time_monotonic_sec': 13.5, 'task_id': 'new', 'target': 'zone_1',
         'status': 'start'},
    ]
    perception_events = [
        {'time_monotonic_sec': 12.0, 'person_distance_valid': True,
         'nearest_person_m': 1.4},
    ]

    result = validate_leaving_recovery_evidence(
        truth, speed_events, stop_events, navigation_events, perception_events)

    assert result['status'] == 'PASS'
    assert result['clear_after_resume'] is True
    assert result['stop_session_id'] == 'old'
    assert result['resumed_session_id'] == 'new'
