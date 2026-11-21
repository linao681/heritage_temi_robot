import sys
from pathlib import Path

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


def test_sample_timestamp_tracks_oldest_sensor_sample_using_monotonic_age():
    value = ready_fusion().snapshot(now=0.4)

    assert value['sample_age_sec'] == 0.4
    assert value['sample_timestamp_monotonic_sec'] == 0.0


def test_laser_uses_only_front_sector_and_filters_nonfinite_and_out_of_range_values():
    fusion = PerceptionFusion(front_half_angle_rad=0.4, scan_min_valid_samples=2)
    fusion.update_scan([0.2, 2.0, 1.2, 1.1, float('inf'), 0.1],
                       -1.0, 0.4, 0.08, 10.0, now=0.0)

    assert fusion.obstacle_distance_m == 1.1


def test_missing_safety_stop_signal_fails_closed():
    fusion = ready_fusion()
    fusion._safety_stop = None

    value = fusion.snapshot(now=0.0)

    assert not value['valid']
    assert not value['safety_stop_valid']
    assert value['safety_stop']
    assert value['error'] == '安全停车状态未确认'


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

    assert value['navigating']
    assert value['navigation_session_id'] == ''
    assert not value['valid']


def test_rejects_negative_or_nonfinite_laser_ranges_as_sensor_failure():
    fusion = PerceptionFusion(scan_min_valid_samples=1)
    fusion.update_scan([-1.0, float('nan'), float('inf')], -0.1, 0.1, 0.08, 10.0, now=0.0)

    assert fusion.obstacle_distance_m is None
