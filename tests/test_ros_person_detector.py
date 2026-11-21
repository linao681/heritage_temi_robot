import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros2_ws/src/visitor_perception'))

from visitor_perception.ros_person_detector import image_sample_age_sec


def test_sample_age_includes_time_in_sensor_queue_and_model_inference():
    image_stamp_ns = 2_057_949_000_000
    ros_now_ns = 2_059_256_000_000

    age = image_sample_age_sec(image_stamp_ns, ros_now_ns, 0.17)

    assert age == pytest.approx(1.477)
    assert age > 0.5


def test_sample_age_counts_inference_when_ros_clock_precedes_image_stamp():
    age = image_sample_age_sec(2_057_949_000_000, 2_057_900_000_000, 0.17)

    assert age == pytest.approx(0.17)


def test_sample_age_rejects_missing_timestamp_or_nonfinite_inference():
    assert image_sample_age_sec(0, 2_057_949_000_000, 0.17) == float('inf')
    assert image_sample_age_sec(2_057_949_000_000, 2_057_949_000_000, float('nan')) == float('inf')
