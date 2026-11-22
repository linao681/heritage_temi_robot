import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from phase27_scenario import actor_step, collision_envelopes, swept_gap


def actor_config(**overrides):
    config = {
        'speed_mps': 0.25,
        'start_distance_m': 4.5,
        'target_distance_m': 0.6,
        'hold_at_target_sec': 2.0,
        'leave_after_hold': True,
        'leave_distance_m': 2.0,
        'hold_clear_sec': 1.0,
    }
    config.update(overrides)
    return config


def test_actor_keeps_approaching_and_holds_after_robot_stop_confirmation():
    config = actor_config()
    anchor = (0.0, 0.0, 0.0)

    before_stop = actor_step(config, 10.0, anchor)
    after_stop = actor_step(config, 12.0, anchor)

    assert before_stop['phase'] == 'APPROACH'
    assert after_stop['phase'] == 'APPROACH'
    assert after_stop['pose'][0] < before_stop['pose'][0]


def test_actor_uses_fixed_anchor_then_holds_and_really_leaves():
    config = actor_config()
    anchor = (3.0, 4.0, math.pi / 2)
    approach_duration = (4.5 - 0.6) / 0.25

    target = actor_step(config, approach_duration + 0.5, anchor)
    leave = actor_step(config, approach_duration + 2.0 + 1.0, anchor)
    clear = actor_step(config, approach_duration + 2.0 + 9.0, anchor)

    assert target['phase'] == 'HOLD_TARGET'
    assert target['pose'][0] == pytest.approx(3.0)
    assert target['pose'][1] == pytest.approx(4.6)
    assert leave['phase'] == 'LEAVE'
    assert leave['pose'][1] > target['pose'][1]
    assert clear['phase'] == 'HOLD_CLEAR'
    assert clear['finished'] is True
    assert clear['pose'][1] == pytest.approx(6.6)


def test_actor_can_leave_laterally_and_hold_in_the_clear_area():
    config = actor_config(speed_mps=0.1, target_distance_m=3.5,
                          leave_distance_m=3.1, leave_direction='left')
    anchor = (0.0, 0.0, 0.0)

    leaving = actor_step(config, 13.0, anchor)
    clear = actor_step(config, 44.5, anchor)

    assert leaving['phase'] == 'LEAVE'
    assert leaving['pose'][0] == pytest.approx(3.5)
    assert leaving['pose'][1] == pytest.approx(0.1)
    assert clear['phase'] == 'HOLD_CLEAR'
    assert clear['finished'] is True
    assert clear['pose'][:2] == pytest.approx((3.5, 3.1))


def test_actor_rejects_non_finite_and_unsafe_configuration():
    with pytest.raises(ValueError):
        actor_step(actor_config(speed_mps=float('nan')), 0.0, (0.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        actor_step(actor_config(target_distance_m=-0.1), 0.0, (0.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        actor_step(actor_config(), float('inf'), (0.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        actor_step(actor_config(leave_direction='diagonal'), 13.0, (0.0, 0.0, 0.0))


def test_swept_geometry_stops_before_circle_envelopes_overlap():
    gap = swept_gap(
        (1.0, 0.0, 0.0), (0.7, 0.0, 0.0), (0.0, 0.0, 0.0),
        {'robot_radius_m': 0.3, 'actor_radius_m': 0.4, 'margin_m': 0.1},
    )

    assert gap == pytest.approx(-0.1)


def test_swept_geometry_uses_both_robot_poses_for_relative_motion():
    gap = swept_gap(
        (1.0, 0.0, 0.0), (1.0, 0.0, 0.0),
        {'previous': (0.0, 0.0, 0.0), 'current': (0.5, 0.0, 0.0)},
        {'robot_radius_m': 0.2, 'actor_radius_m': 0.2, 'margin_m': 0.0},
    )

    assert gap == pytest.approx(0.1)


def test_collision_envelopes_are_derived_from_real_urdf_and_sdf_collisions():
    robot_radius, actor_radius, source = collision_envelopes(
        ROOT / 'simulation/robot/heritage_robot.urdf',
        ROOT / 'simulation/models/person_mannequin/model.sdf',
    )

    assert robot_radius >= math.hypot(0.225, 0.175)
    assert actor_radius >= 0.39
    assert source['robot'].endswith('simulation/robot/heritage_robot.urdf')
    assert source['actor'].endswith('simulation/models/person_mannequin/model.sdf')


def test_actor_collision_geometry_contains_no_unbounded_shapes():
    model = ET.parse(ROOT / 'simulation/models/person_mannequin/model.sdf').getroot()

    assert model.findall('.//collision')
