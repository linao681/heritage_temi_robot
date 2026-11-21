import math
import sys
from pathlib import Path

from geometry_msgs.msg import Pose
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from record_phase2_topics import ground_truth_nearest_person


def pose(x, y, yaw):
    value = Pose()
    value.position.x = x
    value.position.y = y
    value.orientation.z = math.sin(yaw / 2)
    value.orientation.w = math.cos(yaw / 2)
    return value


def test_ground_truth_uses_gazebo_model_centers_and_collision_envelope():
    result = ground_truth_nearest_person(
        ['heritage_robot', 'phase25_person_01'],
        [pose(0.0, 0.0, 0.0), pose(2.0, 0.0, math.pi)])

    assert result['gazebo_ground_truth_person_name'] == 'phase25_person_01'
    assert result['gazebo_ground_truth_center_distance_m'] == 2.0
    assert result['gazebo_ground_truth_distance_m'] == pytest.approx(1.52)
    assert result['gazebo_ground_truth_robot_x'] == 0.0
    assert result['gazebo_ground_truth_person_x'] == 2.0


def test_ground_truth_accounts_for_wider_person_side_profile():
    result = ground_truth_nearest_person(
        ['heritage_robot', 'phase2_person_01'],
        [pose(0.0, 0.0, 0.0), pose(2.0, 0.0, math.pi / 2)])

    assert result['gazebo_ground_truth_distance_m'] == pytest.approx(1.27)


def test_ground_truth_marks_only_person_centers_inside_camera_horizontal_fov():
    result = ground_truth_nearest_person(
        ['heritage_robot', 'phase25_person_01', 'phase25_person_02'],
        [pose(0.0, 0.0, 0.0), pose(2.0, 0.0, math.pi),
         pose(-2.0, 0.0, 0.0)])

    assert result['gazebo_ground_truth_person_fov_count'] == 1
    assert result['gazebo_ground_truth_robot_yaw'] == pytest.approx(0.0)
    assert result['gazebo_ground_truth_fov_nearest_camera_z_m'] == pytest.approx(1.83)


def test_missing_robot_or_person_returns_empty_truth_instead_of_fake_distance():
    assert ground_truth_nearest_person(['phase25_person_01'], [pose(1.0, 0.0, 0.0)]) == {}
    result = ground_truth_nearest_person(['heritage_robot'], [pose(0.0, 0.0, 0.0)])
    assert result['gazebo_ground_truth_person_count'] == 0
    assert result['gazebo_ground_truth_robot_x'] == 0.0
    assert 'gazebo_ground_truth_center_distance_m' not in result
