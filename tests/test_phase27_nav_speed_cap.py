import importlib.util
import math
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'heritage_navigation_launch', ROOT / 'simulation/navigation.launch.py')
navigation_launch = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = navigation_launch
spec.loader.exec_module(navigation_launch)


def nav_params():
    return {
        'controller_server': {'ros__parameters': {'FollowPath': {
            'max_vel_x': 9.0, 'max_speed_xy': 9.0, 'max_vel_theta': 1.2,
        }}},
        'velocity_smoother': {'ros__parameters': {
            'max_velocity': [9.0, 0.0, 1.2],
        }},
    }


def test_initial_linear_speed_cap_updates_controller_and_smoother_only():
    params = nav_params()

    result = navigation_launch.apply_speed_limit(params, 0.7)

    assert result['controller_server']['ros__parameters']['FollowPath']['max_vel_x'] == 0.7
    assert result['controller_server']['ros__parameters']['FollowPath']['max_speed_xy'] == 0.7
    assert result['controller_server']['ros__parameters']['FollowPath']['max_vel_theta'] == 1.2
    assert result['velocity_smoother']['ros__parameters']['max_velocity'] == [0.7, 0.0, 1.2]


def test_default_speed_cap_remains_point_three_five():
    params = navigation_launch.apply_speed_limit(nav_params(), 0.35)

    assert params['controller_server']['ros__parameters']['FollowPath']['max_vel_x'] == 0.35
    assert params['velocity_smoother']['ros__parameters']['max_velocity'][0] == 0.35


@pytest.mark.parametrize('value', [float('nan'), float('inf'), 0.0, -0.1, 1.5])
def test_speed_cap_rejects_non_finite_or_unsupported_values(value):
    with pytest.raises(ValueError):
        navigation_launch.apply_speed_limit(nav_params(), value)
