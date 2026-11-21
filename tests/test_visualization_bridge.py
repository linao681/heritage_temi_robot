import math
import pytest


def test_ros_to_threejs_position_and_heading():
    from scripts.visualization_bridge import convert_pose
    assert convert_pose(2, 3, 0) == pytest.approx({'x': 2, 'z': -3, 'yaw': math.pi/2})
    assert convert_pose(-1, 4, math.pi/2) == pytest.approx({'x': -1, 'z': -4, 'yaw': math.pi})
