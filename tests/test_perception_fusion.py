import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros2_ws/src/visitor_perception'))

from visitor_perception.perception_fusion import PerceptionFusion


def ready_fusion(**kwargs):
    fusion = PerceptionFusion(**kwargs)
    fusion.update_visitor({
        'source': 'camera', 'valid': True, 'stable': True, 'stable_fresh': True,
        'people_count': 3, 'expected_count': 3, 'group_state': 'following',
    }, now=0.0)
    fusion.update_people({
        'source': 'temi_rgbd', 'valid': True, 'person_distance_valid': True,
        'nearest_person_m': 2.8, 'crowd_density_valid': True, 'crowd_density': 0.2,
    }, now=0.0)
    fusion.update_scan([2.0, 1.4, 2.3, float('inf')], -0.3, 0.2, 0.08, 10.0, now=0.0)
    fusion.update_robot({'connected': True, 'frame_id': 'map', 'x': 1.0, 'y': 2.0, 'yaw': 0.0}, now=0.0)
    fusion.update_tour('NAVIGATING', now=0.0)
    fusion.update_navigation('going', 'nav-current', now=0.0)
    fusion.update_safety_stop(False, now=0.0)
    return fusion


def test_fuses_stable_people_depth_lidar_and_current_navigation_session():
    value = ready_fusion().snapshot(now=0.0)

    assert value['valid']
    assert value['source'] == 'temi_sensor_fusion'
    assert value['people_count'] == 3
    assert value['nearest_person_m'] == 2.8
    assert value['obstacle_distance_m'] == 1.4
    assert value['navigation_session_id'] == 'nav-current'
    assert value['navigating']
    assert value['safety_stop_valid'] and not value['safety_stop']
    assert value['sample_timestamp_monotonic_sec'] == 0.0
    assert value['person_observation_state'] == 'PERSON_DISTANCE_VALID'


def test_valid_empty_scene_has_no_person_distance_but_remains_control_valid():
    fusion = ready_fusion(simulation_mode=True)
    fusion.update_visitor({
        'source': 'camera', 'valid': True, 'stable': True, 'stable_fresh': True,
        'people_count': 0, 'expected_count': 0, 'group_state': 'untracked',
    }, now=0.1)
    fusion.update_people({
        'source': 'gazebo_rgbd', 'valid': True, 'observation_state': 'NO_PERSON_OBSERVED',
        'people_count': 0, 'person_distance_valid': False, 'crowd_density_valid': False,
    }, now=0.1)

    value = fusion.snapshot(now=0.1)

    assert value['valid']
    assert value['person_observation_valid']
    assert value['person_observation_state'] == 'NO_PERSON_OBSERVED'
    assert not value['person_distance_valid']
    assert value['nearest_person_m'] is None
    assert value['obstacle_distance_valid']


def test_scene_can_alternate_between_empty_single_person_and_sensor_dropout():
    fusion = ready_fusion(simulation_mode=True)
    empty = {
        'source': 'gazebo_rgbd', 'valid': True, 'observation_state': 'NO_PERSON_OBSERVED',
        'people_count': 0, 'person_distance_valid': False,
    }
    fusion.update_people(empty, now=0.1)
    assert fusion.snapshot(now=0.1)['person_observation_state'] == 'NO_PERSON_OBSERVED'

    fusion.update_people({
        'source': 'gazebo_rgbd', 'valid': True, 'observation_state': 'PERSON_DISTANCE_VALID',
        'people_count': 1, 'person_distance_valid': True, 'nearest_person_m': 1.4,
    }, now=0.2)
    person = fusion.snapshot(now=0.2)
    assert person['person_observation_state'] == 'PERSON_DISTANCE_VALID'
    assert person['nearest_person_m'] == 1.4

    fusion.update_people(empty, now=0.3)
    no_person = fusion.snapshot(now=0.3)
    assert no_person['person_observation_state'] == 'NO_PERSON_OBSERVED'
    assert no_person['nearest_person_m'] is None

    fusion.update_people({
        'source': 'gazebo_rgbd', 'valid': False, 'observation_state': 'SENSOR_INVALID',
        'people_count': 0, 'person_distance_valid': False,
    }, now=0.4)
    failed = fusion.snapshot(now=0.4)
    assert not failed['person_observation_valid']
    assert failed['person_observation_state'] == 'SENSOR_INVALID'


@pytest.mark.parametrize('state', ['PERSON_DISTANCE_UNKNOWN', 'SENSOR_INVALID'])
def test_uncertain_or_failed_person_sensor_never_becomes_empty_scene(state):
    fusion = ready_fusion(simulation_mode=True)
    fusion.update_people({
        'source': 'gazebo_rgbd', 'valid': state != 'SENSOR_INVALID',
        'observation_state': state, 'people_count': 1,
        'person_distance_valid': False, 'crowd_density_valid': False,
    }, now=0.1)

    value = fusion.snapshot(now=0.1)

    assert not value['valid']
    assert not value['person_observation_valid']
    assert value['nearest_person_m'] is None
    assert value['obstacle_distance_valid']


def test_empty_camera_observation_cannot_mask_invalid_laser():
    fusion = ready_fusion(simulation_mode=True)
    fusion.update_visitor({
        'source': 'camera', 'valid': True, 'stable': True, 'stable_fresh': True,
        'people_count': 0, 'expected_count': 0, 'group_state': 'untracked',
    }, now=0.1)
    fusion.update_people({
        'source': 'gazebo_rgbd', 'valid': True, 'observation_state': 'NO_PERSON_OBSERVED',
        'people_count': 0, 'person_distance_valid': False,
    }, now=0.1)
    fusion.update_scan([], -0.2, 0.1, 0.08, 10.0, now=0.1)

    value = fusion.snapshot(now=0.1)

    assert not value['valid']
    assert value['person_observation_valid']
    assert not value['obstacle_distance_valid']
    assert value['obstacle_distance_m'] is None


def test_delayed_clear_person_observation_cannot_replace_newer_person():
    fusion = ready_fusion(simulation_mode=True)
    fusion.update_people({
        'source': 'gazebo_rgbd', 'valid': True, 'person_distance_valid': True,
        'nearest_person_m': 0.8, 'sample_age_sec': 0.01,
    }, now=0.4)
    fusion.update_people({
        'source': 'gazebo_rgbd', 'valid': True, 'person_distance_valid': False,
        'people_count': 0, 'observation_state': 'NO_PERSON_OBSERVED', 'sample_age_sec': 0.3,
    }, now=0.5)
    assert not fusion.snapshot(now=0.5)['person_observation_valid']


def test_late_scan_does_not_make_previous_obstacle_safe():
    fusion = ready_fusion()
    fusion.update_scan([0.3, 0.3], -0.1, 0.2, 0.08, 10.0, now=0.4)
    fusion.update_scan([3.0, 3.0], -0.1, 0.2, 0.08, 10.0, now=0.3)
    assert not fusion.snapshot(now=0.5)['obstacle_distance_valid']


def test_fresh_delivery_of_stale_stop_report_does_not_renew_confirmation():
    fusion = ready_fusion(simulation_mode=True)
    status = dict(source='gazebo_nav2_transport', valid=True, state='STOP_CONFIRMED',
                  navigation_session_id='nav-current', action_terminal=True, linear_speed_mps=0.0,
                  angular_speed_rps=0.0, odom_age_sec=0.01, stopped_duration_sec=0.8,
                  source_stamp=100_000_000_000, source_age_sec=0.01)
    fusion.update_safety_stop_status(status, now=0.2)
    assert fusion.snapshot(now=0.2)['stop_confirmed']
    fusion.update_safety_stop_status(status | {'source_stamp': 99_900_000_000,
                                               'source_age_sec': 0.7}, now=0.3)
    assert not fusion.snapshot(now=0.3)['stop_confirmed']


def test_fused_publication_never_refreshes_old_stop_odom_age():
    fusion = ready_fusion(simulation_mode=True)
    status = dict(source='gazebo_nav2_transport', valid=True, state='STOP_CONFIRMED',
                  navigation_session_id='nav-current', action_terminal=True, linear_speed_mps=0.0,
                  angular_speed_rps=0.0, odom_age_sec=0.35, stopped_duration_sec=0.8,
                  source_stamp=100_000_000_000, source_age_sec=0.04)
    fusion.update_safety_stop_status(status, now=0.2)
    assert fusion.snapshot(now=0.2)['stop_confirmed']
    assert not fusion.snapshot(now=0.32)['stop_confirmed']


def test_sample_timestamp_tracks_oldest_sensor_sample_using_monotonic_age():
    value = ready_fusion().snapshot(now=0.4)

    assert value['sample_age_sec'] == 0.4
    assert value['sample_timestamp_monotonic_sec'] == 0.0


def test_nonheartbeat_visitor_and_navigation_events_do_not_age_motion_inputs():
    fusion = ready_fusion(max_sample_age_sec=0.5)
    fusion.update_people({
        'source': 'temi_rgbd', 'valid': True, 'people_count': 1,
        'person_distance_valid': True, 'nearest_person_m': 0.8,
    }, now=0.5)
    fusion.update_scan([2.0, 1.4, 2.3], -0.3, 0.2, 0.08, 10.0, now=0.5)
    fusion.update_robot({'connected': True, 'frame_id': 'map', 'x': 1.0,
                         'y': 2.0, 'yaw': 0.0}, now=0.5)
    fusion.update_tour('NAVIGATING', now=0.5)
    fusion.update_safety_stop(False, now=0.5)

    value = fusion.snapshot(now=0.6)

    assert not value['valid']
    assert not value['people_valid']
    assert value['person_observation_valid']
    assert value['sample_age_sec'] == pytest.approx(0.1)
    assert value['sample_timestamp_monotonic_sec'] == pytest.approx(0.5)


def test_laser_uses_only_front_sector_and_filters_nonfinite_and_out_of_range_values():
    fusion = PerceptionFusion(front_half_angle_rad=0.4, scan_min_valid_samples=2)
    fusion.update_scan([0.2, 2.0, 1.2, 1.1, float('inf'), 0.1],
                       -1.0, 0.4, 0.08, 10.0, now=0.0)

    assert fusion.obstacle_distance_m == 1.1


def test_default_speed_safety_scan_ignores_side_corner_but_keeps_forward_path():
    fusion = PerceptionFusion()
    fusion.update_scan([0.576, 1.154], -math.pi / 3, math.radians(35),
                       0.08, 12.0, now=0.0)

    assert fusion.obstacle_distance_m == pytest.approx(1.154)


def test_clear_positive_infinity_scan_is_a_valid_range_max_bound():
    fusion = PerceptionFusion(scan_min_valid_samples=3)
    fusion.update_scan([float('inf')] * 120, -0.5, 0.01, 0.08, 12.0, now=0.0)

    assert fusion.obstacle_distance_m == 12.0


def test_missing_safety_stop_signal_fails_closed():
    fusion = ready_fusion()
    fusion._safety_stop = None

    value = fusion.snapshot(now=0.0)

    assert not value['valid']
    assert not value['safety_stop_valid']
    assert value['safety_stop']
    assert value['error'] == '安全停车状态未确认'


def test_trusted_safety_status_distinguishes_stop_request_from_physical_confirmation():
    fusion = ready_fusion(simulation_mode=True)
    fusion.update_safety_stop_status({
        'source': 'gazebo_nav2_transport', 'valid': True,
        'state': 'STOP_CONFIRMED', 'navigation_session_id': 'nav-current',
        'action_terminal': True, 'linear_speed_mps': 0.0, 'angular_speed_rps': 0.0,
        'odom_age_sec': 0.02, 'stopped_duration_sec': 0.6,
    }, now=0.1)

    value = fusion.snapshot(now=0.1)

    assert value['safety_stop_valid']
    assert not value['safety_stop']
    assert value['stop_confirmed']
    assert value['stop_confirmed_session_id'] == 'nav-current'


def test_trusted_clear_safety_status_requires_fresh_odometry():
    fusion = ready_fusion(simulation_mode=True)
    fusion.update_safety_stop_status({
        'source': 'gazebo_nav2_transport', 'valid': True, 'state': 'CLEAR',
        'navigation_session_id': 'nav-current', 'odom_age_sec': 0.02,
    }, now=0.1)

    value = fusion.snapshot(now=0.1)

    assert value['safety_stop_valid'] and not value['safety_stop']
    assert not value['stop_confirmed']


def test_gazebo_safety_status_cannot_be_used_as_live_temi_confirmation():
    fusion = ready_fusion()
    fusion.update_safety_stop_status({
        'source': 'gazebo_nav2_transport', 'valid': True, 'state': 'CLEAR',
        'navigation_session_id': 'nav-current', 'odom_age_sec': 0.02,
    }, now=0.1)

    value = fusion.snapshot(now=0.1)

    assert not value['safety_stop_valid']
    assert value['safety_stop']


@pytest.mark.parametrize('state', ['STOP_REQUESTED', 'STOP_COMMAND_ACCEPTED', 'STOPPING', 'STOP_FAILED'])
def test_pending_or_failed_safety_stop_never_counts_as_confirmed(state):
    fusion = ready_fusion(simulation_mode=True)
    fusion.update_safety_stop_status({
        'source': 'gazebo_nav2_transport', 'valid': True, 'state': state,
        'navigation_session_id': 'nav-current', 'action_terminal': False,
        'linear_speed_mps': 0.1, 'angular_speed_rps': 0.0,
        'odom_age_sec': 0.02, 'stopped_duration_sec': 0.0,
    }, now=0.1)

    value = fusion.snapshot(now=0.1)

    assert value['safety_stop_valid']
    assert value['safety_stop']
    assert not value['stop_confirmed']
    assert value['stop_confirmed_session_id'] == ''


def test_stale_safety_status_expires_and_is_treated_as_active_stop():
    fusion = ready_fusion(simulation_mode=True, max_sample_age_sec=0.5)
    fusion.update_safety_stop_status({
        'source': 'gazebo_nav2_transport', 'valid': True, 'state': 'CLEAR',
        'navigation_session_id': 'nav-current', 'odom_age_sec': 0.02,
    }, now=0.1)

    value = fusion.snapshot(now=0.7)

    assert not value['safety_stop_valid']
    assert value['safety_stop']
    assert not value['stop_confirmed']


@pytest.mark.parametrize('changes', [
    {'action_terminal': False}, {'linear_speed_mps': 0.03},
    {'angular_speed_rps': 0.06}, {'odom_age_sec': 0.6},
    {'stopped_duration_sec': 0.49}, {'navigation_session_id': ''},
])
def test_stop_confirmation_requires_terminal_action_and_fresh_stable_odometry(changes):
    fusion = ready_fusion(simulation_mode=True)
    status = {
        'source': 'gazebo_nav2_transport', 'valid': True,
        'state': 'STOP_CONFIRMED', 'navigation_session_id': 'nav-current',
        'action_terminal': True, 'linear_speed_mps': 0.0, 'angular_speed_rps': 0.0,
        'odom_age_sec': 0.02, 'stopped_duration_sec': 0.6,
    }
    status.update(changes)
    fusion.update_safety_stop_status(status, now=0.1)

    value = fusion.snapshot(now=0.1)

    assert not value['stop_confirmed']
    assert value['safety_stop']


def test_offline_video_and_mock_sources_cannot_become_live_control_input():
    fusion = ready_fusion()
    fusion.update_visitor({
        'source': 'offline_video', 'valid': True, 'stable': True, 'stable_fresh': True,
        'people_count': 3, 'expected_count': 3, 'group_state': 'following',
    }, now=0.1)

    value = fusion.snapshot(now=0.1)

    assert not value['valid']
    assert value['source'] == 'temi_sensor_fusion'
    assert '真实摄像头人数数据不可用' in value['error']


def test_lidar_or_depth_stream_timeout_never_means_clear_space_or_far_people():
    fusion = ready_fusion(max_sample_age_sec=0.5)

    value = fusion.snapshot(now=0.6)

    assert not value['valid']
    assert value['obstacle_distance_m'] is None
    assert value['nearest_person_m'] is None
    assert value['sample_age_sec'] > 0.5


def test_invalid_person_distance_and_density_are_rejected():
    fusion = ready_fusion()
    fusion.update_people({
        'source': 'temi_rgbd', 'valid': True, 'person_distance_valid': True,
        'nearest_person_m': float('nan'), 'crowd_density_valid': True, 'crowd_density': 1.2,
    }, now=0.1)

    value = fusion.snapshot(now=0.1)

    assert not value['valid']
    assert value['nearest_person_m'] is None
    assert value['crowd_density'] is None


def test_uncalibrated_crowd_density_is_reported_but_does_not_hide_valid_distance_sensors():
    fusion = ready_fusion()
    fusion.update_people({
        'source': 'temi_rgbd', 'valid': True, 'person_distance_valid': True,
        'nearest_person_m': 2.8, 'crowd_density_valid': False,
    }, now=0.1)

    value = fusion.snapshot(now=0.1)

    assert value['valid']
    assert not value['crowd_density_valid']
    assert value['crowd_density'] is None
    assert '人群密度尚未标定' in value['warning']


def test_stable_count_is_required_and_dropouts_do_not_become_zero_people():
    fusion = ready_fusion()
    fusion.update_visitor({
        'source': 'camera', 'valid': False, 'stable': False, 'stable_fresh': False,
        'people_count': None, 'expected_count': 3, 'group_state': 'unknown',
    }, now=0.1)

    value = fusion.snapshot(now=0.1)

    assert not value['valid']
    assert value['people_count'] is None
    assert value['group_state'] == 'unknown'


def test_terminal_navigation_event_clears_old_session_id():
    fusion = ready_fusion()
    fusion.update_navigation('succeeded', 'nav-current', now=0.1)

    value = fusion.snapshot(now=0.1)

    assert not value['navigating']
    assert value['navigation_session_id'] == ''
    assert value['valid']


def test_expected_navigation_cancellation_is_not_an_active_or_failed_task():
    fusion = ready_fusion()
    fusion.update_navigation('cancelled', 'nav-current', now=0.1)

    value = fusion.snapshot(now=0.1)

    assert not value['navigating']
    assert not value['navigation_error']
    assert value['navigation_session_id'] == ''


def test_rejects_negative_or_nonfinite_laser_ranges_as_sensor_failure():
    fusion = PerceptionFusion(scan_min_valid_samples=1)
    fusion.update_scan([-1.0, float('nan'), float('-inf')], -0.1, 0.1, 0.08, 10.0, now=0.0)

    assert fusion.obstacle_distance_m is None
