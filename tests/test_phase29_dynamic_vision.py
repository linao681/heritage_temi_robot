import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros2_ws/src/visitor_perception'))

from visitor_perception.ros_team_observer import finite_sample_age_sec
from visitor_perception.team_observer import TeamObserver


def test_invalid_detector_age_serializes_as_unknown_without_killing_observer():
    payload = TeamObserver().observe(
        tracks=[], stamp_ns=0, sensor_valid=False, coverage='forward_only',
        expected_count=3, sample_stamp_ns=None)
    payload['sample_age_sec'] = finite_sample_age_sec(float('inf'))

    encoded = json.dumps(payload, allow_nan=False)

    assert 'Infinity' not in encoded
    assert payload['sample_age_sec'] is None
    assert payload['valid'] is False
    assert payload['observation_state'] == 'UNKNOWN'
    assert payload['requires_manual_confirmation'] is True


def test_finite_nonnegative_detector_age_is_preserved():
    assert finite_sample_age_sec(0.125) == 0.125
    assert finite_sample_age_sec(float('nan')) is None
    assert finite_sample_age_sec(-0.1) is None
    assert finite_sample_age_sec(True) is None
