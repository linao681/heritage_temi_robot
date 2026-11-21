import sys
import math
import json
from types import SimpleNamespace
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from spawn_people_scenario import (ground_truth_path_lengths, scenario_anchor,
                                   scene_positions, trajectory_duration,
                                   trajectory_position, write_truth_record,
                                   PeopleScenario)


def test_local_person_model_has_camera_visible_geometry_and_collisions():
    model = ET.parse(ROOT / 'simulation/models/person_mannequin/model.sdf').getroot()

    assert model.find('.//visual[@name="visitor_billboard"]') is not None
    assert len(model.findall('.//collision')) >= 6
    assert model.find('.//static').text == 'true'
    assert model.find('.//link[@name="body"]/gravity').text == 'false'
    assert model.find('.//link[@name="body"]/kinematic') is None
    model_text = (ROOT / 'simulation/models/person_mannequin/model.sdf').read_text()
    assert '__VISITOR_MATERIALS_URI__' in model_text
    assert '__VISITOR_TEXTURES_URI__' in model_text
    assert (ROOT / 'simulation/models/person_mannequin/materials/textures/visitor.png').is_file()


def test_gazebo_worlds_publish_read_only_model_state_truth():
    for layout in ('official', 'adaptive'):
        world = ET.parse(ROOT / f'simulation/generated/{layout}.world').getroot()
        plugin = world.find('.//world/plugin[@name="gazebo_ros_state"]')

        assert plugin is not None
        assert plugin.attrib['filename'] == 'libgazebo_ros_state.so'
        assert plugin.find('ros/namespace').text == '/gazebo'
        assert float(plugin.find('update_rate').text) >= 10.0


def test_official_scenarios_cover_empty_single_group_near_and_crossing():
    wait = {'x': -12.0, 'y': -8.0}

    assert scene_positions('empty', wait) == []
    assert len(scene_positions('single', wait)) == 1
    assert len(scene_positions('group', wait)) == 3
    assert math.isclose(scene_positions('near', wait)[0][0] - wait['x'], 1.05)
    crossing = scene_positions('crossing', wait)[0]
    assert crossing[:2] == (-9.6, -9.2)


def test_people_scenarios_follow_current_robot_heading():
    pose = {'x': 1.0, 'y': 2.0, 'yaw': math.pi / 2}

    single = scene_positions('single', pose)[0]
    near = scene_positions('near', pose)[0]

    assert math.isclose(single[0], 1.0, abs_tol=1e-9)
    assert math.isclose(single[1], 5.0, abs_tol=1e-9)
    assert math.isclose(near[0], 1.0, abs_tol=1e-9)
    assert math.isclose(near[1], 3.05, abs_tol=1e-9)


def test_dynamic_people_scenarios_anchor_on_live_robot_while_gate_stays_at_wait():
    wait = {'x': -12.0, 'y': -8.0, 'yaw': 0.0}
    robot = {'x': 3.0, 'y': 4.0, 'yaw': math.pi / 2}

    assert scenario_anchor('approaching', wait, robot) == robot
    assert scenario_anchor('crossing', wait, robot) == robot
    assert scenario_anchor('leaving', wait, robot) == robot
    assert scenario_anchor('group_straggler', wait, robot) == robot
    assert scenario_anchor('single_static', wait, robot) == wait
    assert scenario_anchor('group_static', wait, robot) == robot


def test_approaching_trajectory_moves_from_four_and_half_metres_to_safe_hold_distance():
    robot = {'x': 0.0, 'y': 0.0, 'yaw': 0.0}
    start = scene_positions('approaching', robot, seed=17)[0]

    beginning = trajectory_position('approaching', start, robot, 0.0, person_index=0)
    halfway = trajectory_position('approaching', start, robot, 0.5, person_index=0)
    end = trajectory_position('approaching', start, robot, 1.0, person_index=0)

    assert math.hypot(beginning[0], beginning[1]) == pytest.approx(4.5)
    assert math.hypot(halfway[0], halfway[1]) == pytest.approx(2.95)
    assert math.hypot(end[0], end[1]) == pytest.approx(1.4)
    assert trajectory_duration('approaching', start, robot, speed_mps=0.25) == pytest.approx(12.4)


def test_approaching_trajectory_can_stop_at_the_configured_hazard_distance():
    robot = {'x': 0.0, 'y': 0.0, 'yaw': 0.0}
    start = scene_positions('approaching', robot)[0]

    end = trajectory_position('approaching', start, robot, 1.0, end_distance_m=0.65)

    assert math.hypot(end[0], end[1]) == pytest.approx(0.65)


def test_crossing_trajectory_changes_lateral_position_while_holding_forward_range():
    robot = {'x': 0.0, 'y': 0.0, 'yaw': 0.0}
    start = scene_positions('crossing', robot)[0]

    end = trajectory_position('crossing', start, robot, 1.0, person_index=0)

    assert start[0] == pytest.approx(2.4)
    assert start[1] == pytest.approx(-1.2)
    assert end[0] == pytest.approx(2.4)
    assert end[1] == pytest.approx(1.2)


def test_leaving_trajectory_increases_separation_from_the_robot():
    robot = {'x': 0.0, 'y': 0.0, 'yaw': 0.0}
    start = scene_positions('leaving', robot)[0]
    end = trajectory_position('leaving', start, robot, 1.0, person_index=0)

    assert math.hypot(start[0], start[1]) == pytest.approx(1.1)
    assert math.hypot(end[0], end[1]) == pytest.approx(5.0)


def test_group_straggler_moves_only_one_anonymous_person():
    robot = {'x': 0.0, 'y': 0.0, 'yaw': 0.0}
    starts = scene_positions('group_straggler', robot, seed=8)

    assert len(starts) == 3
    for index in (0, 1):
        assert trajectory_position('group_straggler', starts[index], robot, 1.0,
                                   person_index=index) == starts[index]
    straggler_end = trajectory_position('group_straggler', starts[2], robot, 1.0,
                                        person_index=2)
    assert straggler_end[0] == pytest.approx(-1.5)


def test_crowded_scene_seed_is_repeatable_and_changes_layout():
    robot = {'x': 0.0, 'y': 0.0, 'yaw': 0.0}

    first = scene_positions('crowded', robot, seed=123)
    replay = scene_positions('crowded', robot, seed=123)
    other = scene_positions('crowded', robot, seed=124)

    assert len(first) == 5
    assert replay == first
    assert other != first


def test_scenario_writer_preserves_failed_experiment_status_and_error(tmp_path):
    output = tmp_path / 'failed' / 'truth.json'
    record = {'status': 'FAIL', 'scenario': 'crossing',
              'error': 'RuntimeError: model pose readback timed out'}

    write_truth_record(output, record)

    persisted = json.loads(output.read_text())
    assert persisted['status'] == 'FAIL'
    assert persisted['error'] == record['error']


def test_dynamic_trajectory_length_uses_gazebo_readback_not_commanded_poses():
    samples = [
        {'name': 'phase25_person_01', 'x': 0.0, 'y': 0.0,
         'commanded_x': 99.0, 'commanded_y': 99.0},
        {'name': 'phase25_person_01', 'x': 0.2, 'y': 0.0,
         'commanded_x': 98.0, 'commanded_y': 99.0},
        {'name': 'phase25_person_01', 'x': 0.2, 'y': 0.3,
         'commanded_x': 97.0, 'commanded_y': 99.0},
    ]

    assert ground_truth_path_lengths(samples) == {'phase25_person_01': pytest.approx(0.5)}


def test_safety_stop_after_navigation_terminal_still_matches_last_session():
    node = object.__new__(PeopleScenario)
    node.active_navigation_session_id = ''
    node.safety_stop_requested = False

    node._on_navigation_status(SimpleNamespace(status='going', task_id='session-1'))
    node._on_navigation_status(SimpleNamespace(status='aborted', task_id='session-1'))
    node._on_safety_stop(SimpleNamespace(
        source='gazebo_nav2_transport', valid=True, state='STOPPING',
        navigation_session_id='session-1'))

    assert node.safety_stop_requested is True

    node._on_navigation_status(SimpleNamespace(status='going', task_id='session-2'))
    node.safety_stop_requested = False
    node._on_safety_stop(SimpleNamespace(
        source='gazebo_nav2_transport', valid=True, state='STOPPING',
        navigation_session_id='session-1'))

    assert node.safety_stop_requested is False


def test_scenario_started_mid_navigation_learns_session_from_clear_status():
    node = object.__new__(PeopleScenario)
    node.active_navigation_session_id = ''
    node.safety_stop_requested = False

    node._on_safety_stop(SimpleNamespace(
        source='gazebo_nav2_transport', valid=True, state='CLEAR',
        navigation_session_id='session-1'))
    node._on_navigation_status(SimpleNamespace(status='aborted', task_id='session-1'))
    node._on_safety_stop(SimpleNamespace(
        source='gazebo_nav2_transport', valid=True, state='STOPPING',
        navigation_session_id='session-1'))

    assert node.safety_stop_requested is True
