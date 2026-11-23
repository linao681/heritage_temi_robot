import json
from pathlib import Path
import sys
from threading import Lock
from types import MethodType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros2_ws/src/heritage_tour_manager'))

from heritage_tour_manager.ros_tour_node import HeritageTourNode


def test_same_route_new_uncertainty_reopens_pause_after_reliable_observation():
    class Manager:
        pauses = 0

        def status(self):
            return {'state': 'NAVIGATING', 'route_index': 4}

        def visitor_uncertain(self, session_id=''):
            self.pauses += 1
            self.session_id = session_id
            return True

    manager = Manager()
    node = SimpleNamespace(
        get_clock=lambda: SimpleNamespace(now=lambda: SimpleNamespace(nanoseconds=1_000_000_000)),
        _vision_team=None,
        _vision_team_received=0.0,
        _vision_pause_pending=False,
        _vision_confirmed_route_index=4,
        _vision_expected_count=3,
        _navigation_session_id='nav-vision-1',
        _manager=manager,
        _lock=Lock(),
        _schedule=lambda callback, *args: callback(*args),
    )
    node._pause_for_vision_uncertainty = MethodType(
        HeritageTourNode._pause_for_vision_uncertainty, node)
    node._clear_vision_confirmation = MethodType(
        HeritageTourNode._clear_vision_confirmation, node)
    node._current_navigation_session = MethodType(
        HeritageTourNode._current_navigation_session, node)
    observed = {
        'source': 'vision_tracker', 'valid': True, 'stamp_ns': 1_000_000_000,
        'sample_age_sec': 0.05, 'expected_count': 3, 'observed_count': 3,
        'observation_state': 'OBSERVED', 'coverage': 'team_visible',
    }
    uncertain = {
        **observed, 'observed_count': 1, 'observation_state': 'UNKNOWN',
        'coverage': 'forward_only',
    }

    HeritageTourNode._on_vision_team(node, SimpleNamespace(
        data=json.dumps(observed)))
    HeritageTourNode._on_vision_team(node, SimpleNamespace(
        data=json.dumps(uncertain)))

    assert manager.pauses == 1
    assert manager.session_id == 'nav-vision-1'
    assert node._vision_pause_pending is True
