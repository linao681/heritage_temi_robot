import pytest

from rcl_interfaces.msg import ParameterType

from scripts.record_phase2_topics import (
    FIELDS, Phase2Recorder, normalize_nav2_speed_limits, odom_sample_metadata,
    topic_sample_metadata,
)


@pytest.mark.parametrize(
    'controller,smoother,age,expected_valid',
    [
        ((0.6, 0.6), (0.45, 0.2, 0.2), 0.1, True),
        ((float('inf'), 0.6), (0.45,), 0.1, False),
        ((0.6, -0.1), (0.45,), 0.1, False),
        ((0.6, 0.6), (), 0.1, False),
    ],
)
def test_speed_limit_snapshot_requires_finite_positive_values(
        controller, smoother, age, expected_valid):
    result = normalize_nav2_speed_limits(controller, smoother, age)

    assert result['speed_limit_valid'] is expected_valid
    if not result['speed_limit_valid']:
        assert result['speed_limit_controller_max_vel_x_mps'] is None
        assert result['speed_limit_controller_max_speed_xy_mps'] is None
        assert result['speed_limit_smoother_max_velocity_x_mps'] is None


def test_speed_limit_snapshot_marks_expired_readback_invalid():
    result = normalize_nav2_speed_limits((0.6, 0.6), (0.5,), 2.0)

    assert result['speed_limit_valid'] is False
    assert result['speed_limit_sample_age_sec'] == 2.0
    assert result['speed_limit_smoother_max_velocity_x_mps'] is None


def test_nav2_parameter_reply_types_are_decoded_separately():
    from types import SimpleNamespace

    controller = SimpleNamespace(values=[
        SimpleNamespace(type=ParameterType.PARAMETER_DOUBLE, double_value=0.6),
        SimpleNamespace(type=ParameterType.PARAMETER_DOUBLE, double_value=0.55),
    ])
    smoother = SimpleNamespace(values=[
        SimpleNamespace(type=ParameterType.PARAMETER_DOUBLE_ARRAY,
                        double_array_value=[0.5, 0.2, 0.2])
    ])

    assert Phase2Recorder._parameter_values(controller, 'controller') == (0.6, 0.55)
    assert Phase2Recorder._parameter_values(smoother, 'smoother') == (0.5, 0.2, 0.2)


@pytest.mark.parametrize(
    'received_at,now,values,expected_age,expected_valid',
    [
        (10.0, 10.1, (0.3,), 0.1, True),
        (9.0, 10.0, (0.3,), 1.0, False),
        (None, 10.0, (0.3,), None, False),
        (9.9, 10.0, (float('nan'),), 0.1, False),
    ],
)
def test_topic_sample_metadata_keeps_age_and_requires_fresh_finite_values(
        received_at, now, values, expected_age, expected_valid):
    age, valid = topic_sample_metadata(received_at, now, *values)

    assert age == expected_age
    assert valid is expected_valid


@pytest.mark.parametrize(
    'received_at,wall_now,stamp_ns,ros_now_ns,expected_valid',
    [
        (10.0, 10.1, 1_000_000_000, 1_100_000_000, True),
        (10.0, 10.1, 1_000_000_000, 2_000_000_000, False),
        (10.0, 10.1, 2_000_000_000, 1_000_000_000, False),
        (10.0, 10.1, 0, 1_100_000_000, False),
        (10.0, 10.4, 1_000_000_000, 1_100_000_000, False),
    ],
)
def test_odom_sample_requires_fresh_receive_and_ros_header_times(
        received_at, wall_now, stamp_ns, ros_now_ns, expected_valid):
    received_age, source_age, valid = odom_sample_metadata(
        received_at, wall_now, stamp_ns, ros_now_ns, 0.3, 0.0)

    assert received_age is not None
    assert valid is expected_valid
    if stamp_ns == 0:
        assert source_age is None
    else:
        assert source_age == pytest.approx((ros_now_ns - stamp_ns) / 1_000_000_000)


def test_recording_schema_has_clock_map_pose_and_readback_fields():
    assert {
        'ros_stamp_ns', 'received_monotonic_ns', 'received_wall_utc',
        'robot_pose_map_x_m', 'robot_pose_map_y_m', 'robot_pose_map_yaw_rad',
        'robot_pose_map_frame_id', 'robot_pose_map_stamp_ns',
        'robot_pose_map_age_sec', 'robot_pose_map_valid',
        'speed_limit_controller_max_vel_x_mps',
        'speed_limit_controller_max_speed_xy_mps',
        'speed_limit_smoother_max_velocity_x_mps',
        'speed_limit_sample_age_sec', 'speed_limit_valid',
        'cmd_vel_nav_sample_age_sec', 'cmd_vel_nav_sample_valid',
        'cmd_vel_sample_age_sec', 'cmd_vel_sample_valid',
        'odom_header_stamp_ns', 'odom_message_age_sec',
        'odom_sample_age_sec', 'odom_sample_valid',
    }.issubset(FIELDS)


def _recorder_with_transform(transform=None, error=None):
    from tf2_ros import TransformException

    recorder = Phase2Recorder.__new__(Phase2Recorder)

    class BufferStub:
        def lookup_transform(self, *_args, **_kwargs):
            if error:
                raise TransformException(error)
            return transform

    recorder._tf_buffer = BufferStub()
    return recorder


def _transform(frame_id, stamp_ns, x=1.0, y=2.0):
    from types import SimpleNamespace

    seconds, nanoseconds = divmod(stamp_ns, 1_000_000_000)
    return SimpleNamespace(
        header=SimpleNamespace(
            frame_id=frame_id,
            stamp=SimpleNamespace(sec=seconds, nanosec=nanoseconds)),
        transform=SimpleNamespace(
            translation=SimpleNamespace(x=x, y=y),
            rotation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0)))


def test_map_pose_accepts_only_fresh_map_transform():
    recorder = _recorder_with_transform(_transform('map', 1_500_000_000))

    result = recorder._map_pose_snapshot(2_000_000_000)

    assert result['robot_pose_map_valid'] is True
    assert result['robot_pose_map_x_m'] == 1.0
    assert result['robot_pose_map_y_m'] == 2.0
    assert result['robot_pose_map_yaw_rad'] == 0.0
    assert result['robot_pose_map_age_sec'] == 0.5


@pytest.mark.parametrize(
    'transform,now_ns',
    [
        (_transform('map', 1_000_000_000), 2_000_000_000),
        (_transform('map', 3_000_000_000), 2_000_000_000),
        (_transform('odom', 1_900_000_000), 2_000_000_000),
        (_transform('map', 1_900_000_000, x=float('nan')), 2_000_000_000),
    ],
)
def test_map_pose_rejects_stale_future_wrong_frame_and_nonfinite(transform, now_ns):
    result = _recorder_with_transform(transform)._map_pose_snapshot(now_ns)

    assert result['robot_pose_map_valid'] is False
    assert result['robot_pose_map_x_m'] is None


def test_map_pose_marks_missing_transform_invalid():
    from tf2_ros import TransformException

    result = _recorder_with_transform(error='missing transform')._map_pose_snapshot(
        2_000_000_000)

    assert result['robot_pose_map_valid'] is False
    assert result['robot_pose_map_age_sec'] is None
