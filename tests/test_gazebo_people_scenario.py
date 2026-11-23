import sys
import math
import json
import inspect
from types import SimpleNamespace
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import spawn_people_scenario
from spawn_people_scenario import (ground_truth_path_lengths, scenario_anchor,
                                   scene_positions, trajectory_duration,
                                   trajectory_position, write_truth_record,
                                   PeopleScenario, navigation_heading)
from run_phase25_clean_tour import TourEvidence, validate_dynamic_scenario_evidence
from run_phase25_clean_tour import validate_leaving_recovery_evidence


def test_model_pose_wait_ignores_cache_sample_from_before_move_ack(monkeypatch):
    parameters = inspect.signature(PeopleScenario.wait_for_model_pose).parameters
    assert 'after_monotonic' in parameters

    class FakeScenario:
        _model_states_received_at = 10.0
        _last_pose_confirmation_source = ''
        spin_count = 0

        @staticmethod
        def model_pose(_name):
            return {'x': 1.0, 'y': 2.0, 'yaw': 0.0}

    scenario = FakeScenario()

    def spin_once(node, timeout_sec=0.1):
        node.spin_count += 1
        node._model_states_received_at = 10.1

    monkeypatch.setattr(spawn_people_scenario.rclpy, 'ok', lambda: True)
    monkeypatch.setattr(spawn_people_scenario.rclpy, 'spin_once', spin_once)

    pose = PeopleScenario.wait_for_model_pose(
        scenario, 'visitor', (1.0, 2.0), timeout_sec=0.5,
        tolerance_m=0.02, after_monotonic=10.0)

    assert pose['x'] == pytest.approx(1.0)
    assert scenario.spin_count == 1
    assert scenario._last_pose_confirmation_source == 'gazebo_model_states'


def test_actor_move_uses_ack_time_as_model_state_freshness_boundary(monkeypatch):
    class FakeScenario:
        _set_state = object()
        acknowledged_at = 10.0
        freshness_boundary = None

        def _call(self, _client, _request):
            pass

        def wait_for_model_pose(self, _name, _expected, **kwargs):
            self.freshness_boundary = kwargs.get('after_monotonic')

    monkeypatch.setattr(spawn_people_scenario.time, 'monotonic', lambda: 10.1)
    scenario = FakeScenario()

    PeopleScenario.move(scenario, 'visitor', 1.0, 2.0, 0.0)

    assert scenario.freshness_boundary == 10.1
    assert scenario.freshness_boundary > scenario.acknowledged_at


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
    assert crossing[:2] == (-8.5, -9.5)


def test_people_scenarios_follow_current_robot_heading():
    pose = {'x': 1.0, 'y': 2.0, 'yaw': math.pi / 2}

    single = scene_positions('single', pose)[0]
    near = scene_positions('near', pose)[0]

    assert math.isclose(single[0], 1.0, abs_tol=1e-9)
    assert math.isclose(single[1], 5.0, abs_tol=1e-9)
    assert math.isclose(near[0], 1.0, abs_tol=1e-9)
    assert math.isclose(near[1], 3.05, abs_tol=1e-9)


def test_approaching_scenario_heading_tracks_active_navigation_goal():
    robot = {'x': 1.0, 'y': 2.0, 'yaw': 0.0}
    goal = {'x': 1.0, 'y': 5.0}

    assert navigation_heading(robot, goal) == pytest.approx(math.pi / 2)


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

    assert start[0] == pytest.approx(3.5)
    assert start[1] == pytest.approx(-1.5)
    assert end[0] == pytest.approx(3.5)
    assert end[1] == pytest.approx(1.5)


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


def test_model_pose_rejects_stale_model_states():
    node = object.__new__(PeopleScenario)
    node._model_states = {'phase25_person_01': SimpleNamespace(position=SimpleNamespace(x=1.0, y=2.0),
        orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0))}
    node._model_states_received_at = 0.0

    assert node.model_pose('phase25_person_01') is None


def test_navigation_gate_requires_matching_active_target_and_fresh_motion():
    now = __import__('time').monotonic()
    node = object.__new__(PeopleScenario)
    node._latest_navigation = {'task_id': 'nav-4', 'target': 'zone_4', 'status': 'going'}
    node._navigation_received_at = now
    node._odom_speed_mps = 0.2
    node._odom_received_at = now

    assert node.navigation_snapshot('zone_4', now=now)['task_id'] == 'nav-4'
    assert node.navigation_snapshot('zone_3', now=now) is None
    node._odom_received_at = now - 1.0
    assert node.navigation_snapshot('zone_4', now=now) is None


def test_move_waits_for_gazebo_readback_at_the_requested_pose(monkeypatch):
    node = object.__new__(PeopleScenario)
    observed = []
    node._call = lambda _client, request: observed.append(request.state.pose.position.x)
    node._set_state = object()
    node.wait_for_model_pose = lambda name, expected=None, **kwargs: observed.append(
        (name, expected, kwargs.get('tolerance_m')))

    node.move('phase25_person_01', 1.2, -0.4, 0.0)

    assert observed[0] == pytest.approx(1.2)
    assert observed[1] == ('phase25_person_01', (1.2, -0.4), 0.02)


def test_dynamic_scenario_evidence_requires_real_motion_detection_and_response():
    truth = {
        'movement_started_monotonic_sec': 10.0,
        'movement_ended_monotonic_sec': 12.0,
        'gazebo_ground_truth_path_length_m_by_person': {'phase25_person_01': 0.8},
    }
    perception = [{
        'time_monotonic_sec': 10.8, 'valid': True, 'people_count': 1,
        'person_distance_valid': True, 'nearest_person_m': 1.7,
    }]
    speed = [{
        'time_monotonic_sec': 11.0,
        'status': {'state': 'SLOW', 'reason': '接近游客，按距离减速',
                   'input_valid': True},
    }]

    evidence = validate_dynamic_scenario_evidence(truth, perception, speed, [])

    assert evidence['gazebo_moved_models'] == {'phase25_person_01': 0.8}
    assert evidence['valid_person_distance_channel_observations'] == 1
    assert evidence['valid_aggregate_fusion_observations'] == 1
    assert evidence['person_distance_control_responses'] == 1
    assert evidence['person_distance_slow_responses'] == 1
    assert evidence['person_distance_stop_responses'] == 0
    assert evidence['status'] == 'PASS'


def test_close_laser_stop_is_not_attributed_to_person_distance():
    truth = {
        'movement_started_monotonic_sec': 10.0,
        'movement_ended_monotonic_sec': 12.0,
        'gazebo_ground_truth_path_length_m_by_person': {'phase25_person_01': 0.8},
    }
    perception = [{
        'time_monotonic_sec': 10.8, 'valid': True, 'people_count': 1,
        'person_distance_valid': True, 'nearest_person_m': 1.7,
    }]
    speed = [{
        'time_monotonic_sec': 11.0,
        'status': {'state': 'STOPPING', 'reason': '近距离障碍物停车',
                   'input_valid': True},
    }]

    evidence = validate_dynamic_scenario_evidence(truth, perception, speed, [])

    assert evidence['person_distance_control_responses'] == 0
    assert evidence['person_distance_stop_responses'] == 0
    assert evidence['laser_obstacle_control_responses'] == 1
    assert evidence['status'] == 'PASS_WITH_RISK'


def test_person_distance_stop_is_recorded_separately_from_slowing():
    truth = {
        'movement_started_monotonic_sec': 10.0,
        'movement_ended_monotonic_sec': 12.0,
        'gazebo_ground_truth_path_length_m_by_person': {'phase25_person_01': 0.8},
    }
    perception = [{
        'time_monotonic_sec': 10.8, 'valid': True, 'people_count': 1,
        'person_distance_valid': True, 'nearest_person_m': 0.5,
    }]
    speed = [{
        'time_monotonic_sec': 11.0,
        'status': {'state': 'STOPPING', 'reason': '近距离人员停车',
                   'input_valid': True},
    }]

    evidence = validate_dynamic_scenario_evidence(truth, perception, speed, [])

    assert evidence['person_distance_control_responses'] == 1
    assert evidence['person_distance_slow_responses'] == 0
    assert evidence['person_distance_stop_responses'] == 1


def test_dynamic_scenario_evidence_keeps_distance_channel_when_group_count_is_invalid():
    truth = {
        'movement_started_monotonic_sec': 10.0,
        'movement_ended_monotonic_sec': 12.0,
        'gazebo_ground_truth_path_length_m_by_person': {'phase25_person_01': 0.8},
    }
    perception = [{
        'time_monotonic_sec': 10.8, 'valid': False, 'people_count': 0,
        'person_observation_state': 'PERSON_DISTANCE_VALID',
        'person_observation_valid': True, 'person_distance_valid': True,
        'nearest_person_m': 1.7, 'sample_age_sec': 0.3,
    }]
    speed = [{
        'time_monotonic_sec': 11.0,
        'status': {'state': 'SLOW', 'reason': '前方障碍，按距离减速',
                   'input_valid': True},
    }]

    evidence = validate_dynamic_scenario_evidence(truth, perception, speed, [])

    assert evidence['valid_person_distance_channel_observations'] == 1
    assert evidence['valid_aggregate_fusion_observations'] == 0
    assert evidence['status'] == 'PASS_WITH_RISK'


def test_dynamic_scenario_evidence_rejects_missing_robot_response():
    truth = {
        'movement_started_monotonic_sec': 10.0,
        'movement_ended_monotonic_sec': 12.0,
        'gazebo_ground_truth_path_length_m_by_person': {'phase25_person_01': 0.8},
    }
    perception = [{
        'time_monotonic_sec': 10.8, 'valid': True, 'people_count': 1,
        'person_distance_valid': True, 'nearest_person_m': 1.7,
    }]

    speed = [{
        'time_monotonic_sec': 11.0, 'status': {
            'state': 'STOPPING', 'reason': '感知数据无效或过期',
            'stop_requested': True, 'input_valid': False},
    }]
    with pytest.raises(AssertionError, match='没有可归因的限速、停车或 Nav2 避障响应'):
        validate_dynamic_scenario_evidence(truth, perception, speed, [])


def test_dynamic_scenario_evidence_rejects_missing_fused_distance():
    truth = {
        'movement_started_monotonic_sec': 10.0,
        'movement_ended_monotonic_sec': 12.0,
        'gazebo_ground_truth_path_length_m_by_person': {'phase25_person_01': 0.8},
    }
    speed = [{
        'time_monotonic_sec': 11.0,
        'status': {'state': 'SLOW', 'reason': '接近游客，按距离减速',
                   'input_valid': True},
    }]

    with pytest.raises(AssertionError, match='没有有效的人员距离通道观测'):
        validate_dynamic_scenario_evidence(truth, [], speed, [])


def test_dynamic_scenario_evidence_downgrades_unattributed_lidar_response():
    truth = {
        'movement_started_monotonic_sec': 10.0,
        'movement_ended_monotonic_sec': 12.0,
        'gazebo_ground_truth_path_length_m_by_person': {'phase25_person_01': 0.8},
    }
    perception = [{
        'time_monotonic_sec': 10.8, 'valid': True, 'people_count': 1,
        'person_distance_valid': True, 'nearest_person_m': 1.7,
    }]
    speed = [{
        'time_monotonic_sec': 11.0,
        'status': {'state': 'SLOW', 'reason': '前方障碍，按距离减速',
                   'input_valid': True},
    }]

    evidence = validate_dynamic_scenario_evidence(truth, perception, speed, [])

    assert evidence['status'] == 'PASS_WITH_RISK'
    assert evidence['response_attribution'] == 'LIDAR_OBSTACLE_RESPONSE'
    assert evidence['laser_obstacle_control_responses'] == 1


def test_tour_evidence_records_independent_person_and_visitor_validity():
    evidence = object.__new__(TourEvidence)
    evidence._timestamp = lambda: 10.8
    evidence._last_perception_signature = None
    evidence.perception_events = []
    message = SimpleNamespace(
        valid=False, error='stable visitor count invalid', people_count=0,
        people_valid=False, sample_age_sec=0.3,
        person_observation_state='PERSON_DISTANCE_VALID',
        person_observation_valid=True, person_distance_valid=True,
        nearest_person_m=1.7, obstacle_distance_valid=True,
        obstacle_distance_m=1.1, safety_stop=False, stop_confirmed=False,
        navigating=True, explaining=False, navigation_error=False,
        navigation_session_id='session-a',
    )

    TourEvidence._perception(evidence, message)

    event = evidence.perception_events[0]
    assert event['valid'] is False
    assert event['people_valid'] is False
    assert event['person_observation_valid'] is True
    assert event['person_distance_valid'] is True
    assert event['nearest_person_m'] == 1.7


def test_leaving_scenario_requires_confirmed_clear_and_new_navigation_uuid():
    truth = {'movement_started_monotonic_sec': 10.0,
             'movement_ended_monotonic_sec': 20.0}
    speed = [
        {'time_monotonic_sec': 10.2, 'status': {
            'state': 'STOPPING', 'reason': '近距离危险停车',
            'navigation_session_id': 'old-session'}},
        {'time_monotonic_sec': 11.8, 'status': {
            'state': 'RECOVERING', 'resume_requested': True}},
    ]
    stops = [
        {'time_monotonic_sec': 10.6, 'state': 'STOP_CONFIRMED',
         'navigation_session_id': 'old-session', 'valid': True},
        {'time_monotonic_sec': 11.5, 'state': 'CLEAR',
         'navigation_session_id': 'old-session', 'valid': True},
    ]
    navigation = [
        {'time_monotonic_sec': 9.9, 'task_id': 'old-session',
         'target': 'zone_4', 'status': 'going'},
        {'time_monotonic_sec': 12.0, 'task_id': 'new-session',
         'target': 'zone_4', 'status': 'start'},
    ]
    perception = [
        {'time_monotonic_sec': 10.3, 'valid': True, 'people_count': 1,
         'person_distance_valid': True, 'nearest_person_m': 0.8},
    ]

    evidence = validate_leaving_recovery_evidence(
        truth, speed, stops, navigation, perception)

    assert evidence['target'] == 'zone_4'
    assert evidence['resumed_session_id'] == 'new-session'
    assert evidence['status'] == 'PASS'


def test_leaving_scenario_accepts_fail_closed_stop_with_near_person_and_recovery_evidence():
    truth = {'movement_started_monotonic_sec': 10.0,
             'movement_ended_monotonic_sec': 20.0}
    speed = [
        {'time_monotonic_sec': 10.2, 'status': {
            'state': 'STOPPING', 'reason': '感知数据无效或过期',
            'input_valid': False, 'navigation_session_id': 'old-session'}},
        {'time_monotonic_sec': 11.8, 'status': {
            'state': 'RECOVERING', 'resume_requested': True}},
    ]
    stops = [
        {'time_monotonic_sec': 10.6, 'state': 'STOP_CONFIRMED',
         'navigation_session_id': 'old-session', 'valid': True},
        {'time_monotonic_sec': 12.1, 'state': 'CLEAR',
         'navigation_session_id': 'new-session', 'valid': True},
    ]
    navigation = [
        {'time_monotonic_sec': 9.9, 'task_id': 'old-session',
         'target': 'zone_4', 'status': 'going'},
        {'time_monotonic_sec': 12.0, 'task_id': 'new-session',
         'target': 'zone_4', 'status': 'start'},
    ]
    perception = [
        {'time_monotonic_sec': 10.25, 'valid': False, 'people_count': 0,
         'person_distance_valid': True, 'nearest_person_m': 0.86},
    ]

    evidence = validate_leaving_recovery_evidence(
        truth, speed, stops, navigation, perception)

    assert evidence['status'] == 'PASS_WITH_RISK'
    assert evidence['stop_cause'] == 'FAIL_CLOSED_WITH_NEAR_PERSON_OBSERVATION'
    assert evidence['clear_after_resume'] is True
    assert evidence['resumed_session_id'] == 'new-session'


def test_leaving_scenario_rejects_fail_closed_stop_without_near_person_measurement():
    truth = {'movement_started_monotonic_sec': 10.0,
             'movement_ended_monotonic_sec': 20.0}
    speed = [
        {'time_monotonic_sec': 10.2, 'status': {
            'state': 'STOPPING', 'reason': '感知数据无效或过期',
            'input_valid': False, 'navigation_session_id': 'old-session'}},
        {'time_monotonic_sec': 11.8, 'status': {
            'state': 'RECOVERING', 'resume_requested': True}},
    ]
    stops = [
        {'time_monotonic_sec': 10.6, 'state': 'STOP_CONFIRMED',
         'navigation_session_id': 'old-session', 'valid': True},
        {'time_monotonic_sec': 11.5, 'state': 'CLEAR',
         'navigation_session_id': 'old-session', 'valid': True},
    ]
    navigation = [
        {'time_monotonic_sec': 9.9, 'task_id': 'old-session',
         'target': 'zone_4', 'status': 'going'},
        {'time_monotonic_sec': 12.0, 'task_id': 'new-session',
         'target': 'zone_4', 'status': 'start'},
    ]

    with pytest.raises(AssertionError, match='近距离人员测距证据'):
        validate_leaving_recovery_evidence(truth, speed, stops, navigation, [])


def test_leaving_scenario_rejects_reuse_of_old_navigation_uuid():
    truth = {'movement_started_monotonic_sec': 10.0,
             'movement_ended_monotonic_sec': 20.0}
    speed = [
        {'time_monotonic_sec': 10.2, 'status': {
            'state': 'STOPPING', 'reason': '近距离危险停车',
            'navigation_session_id': 'old-session'}},
        {'time_monotonic_sec': 11.8, 'status': {'state': 'RECOVERING'}},
    ]
    stops = [
        {'time_monotonic_sec': 10.6, 'state': 'STOP_CONFIRMED',
         'navigation_session_id': 'old-session', 'valid': True},
        {'time_monotonic_sec': 11.5, 'state': 'CLEAR',
         'navigation_session_id': 'old-session', 'valid': True},
    ]
    navigation = [
        {'time_monotonic_sec': 9.9, 'task_id': 'old-session',
         'target': 'zone_4', 'status': 'going'},
        {'time_monotonic_sec': 12.0, 'task_id': 'old-session',
         'target': 'zone_4', 'status': 'start'},
    ]
    perception = [
        {'time_monotonic_sec': 10.3, 'valid': True, 'people_count': 1,
         'person_distance_valid': True, 'nearest_person_m': 0.8},
    ]

    with pytest.raises(AssertionError, match='新导航 UUID'):
        validate_leaving_recovery_evidence(
            truth, speed, stops, navigation, perception)
