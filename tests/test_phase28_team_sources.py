import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import rclpy
from std_msgs.msg import String

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                        'ros2_ws/src/heritage_tour_manager'))

from heritage_tour_manager.team_observation import (
    observation_requires_pause, simulation_team_controls, validate_team_decision_mode,
)


def team_observation(**changes):
    value = {'source': 'vision_tracker', 'valid': True, 'stamp_ns': 1_000_000_000,
             'sample_age_sec': 0.1, 'observation_state': 'OBSERVED',
             'observed_count': 3, 'expected_count': 3,
             'coverage': 'team_visible'}
    value.update(changes)
    return value


@pytest.mark.parametrize('value,now_ns', [
    (team_observation(source='gazebo_scripted_actors'), 1_100_000_000),
    (team_observation(valid=False), 1_100_000_000),
    (team_observation(stamp_ns=1_000_000_000), 2_100_000_001),
    (team_observation(observation_state='UNKNOWN'), 1_100_000_000),
    (team_observation(coverage='forward_only'), 1_100_000_000),
    (team_observation(observed_count=2), 1_100_000_000),
])
def test_non_visual_or_uncertain_team_observation_requires_pause(value, now_ns):
    assert observation_requires_pause(value, now_ns=now_ns)


def test_fresh_complete_visual_team_is_the_only_clear_observation():
    assert not observation_requires_pause(team_observation(), now_ns=1_100_000_000)


def test_invalid_json_and_nonfinite_age_fail_closed():
    assert observation_requires_pause('{broken', now_ns=1_100_000_000)
    assert observation_requires_pause(team_observation(sample_age_sec=float('nan')),
                                     now_ns=1_100_000_000)


def test_only_explicit_supported_decision_modes_are_accepted():
    assert validate_team_decision_mode('business_script') == 'business_script'
    assert validate_team_decision_mode('vision_conservative') == 'vision_conservative'
    with pytest.raises(ValueError):
        validate_team_decision_mode('auto_use_sim_truth')


def test_scripted_truth_controls_business_mode_only():
    assert simulation_team_controls('business_script')
    assert not simulation_team_controls('vision_conservative')


def test_vision_mode_ignores_scripted_team_status_in_ros_node():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                            'ros2_ws/src/heritage_tour_manager'))
    from heritage_tour_manager.ros_tour_node import HeritageTourNode
    from heritage_tour_manager.tour_config import TourConfig

    root = Path(__file__).resolve().parents[1]
    rclpy.init(args=['--ros-args', '-p', 'team_decision_mode:=vision_conservative'])
    node = HeritageTourNode(TourConfig.from_yaml(root / 'config/exhibits.yaml',
                                                 root / 'config/system.yaml'))
    try:
        message = String()
        message.data = json.dumps({'source': 'gazebo_scripted_actors',
                                   'gathered': True, 'people_count': 3})
        node._on_sim_team(message)
        assert node._sim_team is None
        assert node._team_decision_mode == 'vision_conservative'
        response = node._on_control('visitor_lost', node._manager.visitor_lost,
                                    SimpleNamespace(), SimpleNamespace(success=True, message=''))
        assert response.success is False
    finally:
        node.destroy_node()
        rclpy.shutdown()


def test_scripted_team_model_disables_lost_service_client_in_vision_mode():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
    from gazebo_visitor_team import create_lost_service_client

    class StubNode:
        def __init__(self):
            self.clients = []

        def create_client(self, service_type, name):
            self.clients.append((service_type, name))
            return object()

    vision_node = StubNode()
    assert create_lost_service_client(vision_node, 'vision_conservative') is None
    assert vision_node.clients == []

    business_node = StubNode()
    assert create_lost_service_client(business_node, 'business_script') is not None
    assert business_node.clients[0][1] == 'heritage/tour/visitor_lost'
