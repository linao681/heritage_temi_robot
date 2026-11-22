import math

import pytest


def test_snapshot_payload_drops_stale_values_and_preserves_age():
    from scripts.visualization_bridge import snapshot_payload

    fresh = snapshot_payload({'value': 3}, received_at=9.5, now=10.0, max_age_sec=1.0)
    assert fresh == {'fresh': True, 'age_sec': 0.5, 'value': {'value': 3}}

    stale = snapshot_payload({'value': 3}, received_at=8.0, now=10.0, max_age_sec=1.0)
    assert stale == {'fresh': False, 'age_sec': 2.0, 'value': None}


def test_scan_summary_uses_only_finite_in_range_samples():
    from scripts.visualization_bridge import scan_summary

    result = scan_summary([math.inf, 2.0, 0.1, 0.7, math.nan],
                          angle_min=-1.0, angle_increment=0.1,
                          range_min=0.2, range_max=4.0)
    assert result == {'valid': True, 'minimum_distance_m': 0.7,
                      'bearing_rad': pytest.approx(-0.7), 'valid_sample_count': 2}


def test_scan_summary_marks_empty_valid_set_invalid():
    from scripts.visualization_bridge import scan_summary

    assert scan_summary([math.nan, 0.1, 5.0], angle_min=0.0,
                        angle_increment=0.1, range_min=0.2,
                        range_max=4.0) == {
                            'valid': False, 'minimum_distance_m': None,
                            'bearing_rad': None, 'valid_sample_count': 0}


def test_depth_image_summary_reports_finite_positive_samples():
    import struct
    from sensor_msgs.msg import Image
    from scripts.visualization_bridge import depth_image_summary

    image = Image()
    image.header.frame_id = 'depth_camera_optical_frame'
    image.height, image.width = 2, 2
    image.encoding, image.is_bigendian, image.step = '32FC1', 0, 8
    image.data = list(struct.pack('<ffff', 1.0, math.nan, 0.0, 3.0))

    summary = depth_image_summary(image)

    assert summary['valid'] is True
    assert summary['frame_id'] == 'depth_camera_optical_frame'
    assert summary['valid_pixels'] == 2
    assert summary['total_pixels'] == 4
    assert summary['valid_fraction'] == 0.5
    assert summary['minimum_m'] == 1.0
    assert summary['median_m'] == 2.0


def test_depth_image_summary_rejects_inconsistent_layout():
    from sensor_msgs.msg import Image
    from scripts.visualization_bridge import depth_image_summary

    image = Image()
    image.height, image.width = 2, 2
    image.encoding, image.step = '32FC1', 4
    image.data = [0] * 16

    assert depth_image_summary(image) == {
        'valid': False, 'frame_id': '', 'valid_pixels': 0,
        'total_pixels': 4, 'valid_fraction': 0.0, 'minimum_m': None,
        'median_m': None, 'reason': 'invalid_step_or_data_length'}


def test_transform_summary_reports_static_and_stale_transforms():
    from scripts.visualization_bridge import transform_summary

    static = transform_summary(
        target_frame='base_footprint', source_frame='depth_camera_optical_frame',
        translation=(0.1, 0.0, 0.8), rotation=(0.0, 0.0, 0.0, 1.0),
        stamp_ns=0, current_ros_time_ns=10_000_000_000)
    stale = transform_summary(
        target_frame='base_footprint', source_frame='depth_camera_optical_frame',
        translation=(0.1, 0.0, 0.8), rotation=(0.0, 0.0, 0.0, 1.0),
        stamp_ns=1_000_000_000, current_ros_time_ns=5_000_000_000)

    assert static['valid'] and static['is_static'] and static['age_sec'] is None
    assert static['target_frame'] == 'base_footprint'
    assert static['source_frame'] == 'depth_camera_optical_frame'
    assert static['translation_m'] == {'x': 0.1, 'y': 0.0, 'z': 0.8}
    assert stale['valid'] is False and stale['is_static'] is False
    assert stale['age_sec'] == 4.0
