import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros2_ws/src/visitor_perception'))
from visitor_perception.depth_association import associate_person_depth


def test_depth_association_uses_calibrated_median_depth_not_box_size():
    depth = np.full((100, 100), 2.0, dtype=np.float32)

    distance = associate_person_depth((0.25, 0.25, 0.75, 0.75), depth,
                                      fx=100, fy=100, cx=49.5, cy=49.5)

    assert distance == pytest.approx(2.0)


def test_invalid_and_out_of_range_depth_returns_unknown():
    depth = np.full((100, 100), np.nan, dtype=np.float32)

    assert associate_person_depth((0.25, 0.25, 0.75, 0.75), depth,
                                  fx=100, fy=100, cx=49.5, cy=49.5) is None
    depth[:] = 20.0
    assert associate_person_depth((0.25, 0.25, 0.75, 0.75), depth,
                                  fx=100, fy=100, cx=49.5, cy=49.5,
                                  max_depth_m=8.0) is None


@pytest.mark.parametrize('bbox', [(-0.1, 0.2, 0.3, 0.8), (0.4, 0.4, 0.4, 0.8),
                                  (0.1, 0.1, 1.2, 0.8)])
def test_invalid_normalized_bbox_is_rejected(bbox):
    with pytest.raises(ValueError):
        associate_person_depth(bbox, np.ones((20, 20), dtype=np.float32),
                               fx=20, fy=20, cx=10, cy=10)


def test_depth_intrinsics_must_be_finite_and_positive():
    with pytest.raises(ValueError):
        associate_person_depth((0.2, 0.2, 0.8, 0.8), np.ones((20, 20), dtype=np.float32),
                               fx=float('nan'), fy=20, cx=10, cy=10)


def test_ros_camera_info_numpy_float64_intrinsics_are_accepted():
    depth = np.full((20, 20), 1.5, dtype=np.float32)

    assert associate_person_depth((np.float32(0.2), np.float32(0.2), np.float32(0.8), np.float32(0.8)),
        depth, fx=np.float64(20), fy=np.float64(20), cx=np.float64(10), cy=np.float64(10)) == pytest.approx(1.5)
