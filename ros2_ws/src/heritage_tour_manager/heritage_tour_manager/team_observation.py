"""Validation rules for letting vision evidence influence team tour state."""
import json
import math


TEAM_DECISION_MODES = {'business_script', 'vision_conservative'}


def validate_team_decision_mode(value):
    if value not in TEAM_DECISION_MODES:
        raise ValueError(f'team_decision_mode must be one of {sorted(TEAM_DECISION_MODES)}')
    return value


def simulation_team_controls(mode):
    return validate_team_decision_mode(mode) == 'business_script'


def observation_requires_pause(value, *, now_ns, max_age_sec=0.5):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return True
    if not isinstance(value, dict):
        return True
    try:
        stamp_ns = value['stamp_ns']
        sample_age = float(value['sample_age_sec'])
        expected = value['expected_count']
        observed = value['observed_count']
    except (KeyError, TypeError, ValueError):
        return True
    if (type(stamp_ns) is not int or stamp_ns <= 0 or type(now_ns) is not int or
            now_ns < stamp_ns or not math.isfinite(sample_age) or
            not 0 <= sample_age <= max_age_sec or
            (now_ns - stamp_ns) / 1e9 > max_age_sec or
            type(expected) is not int or expected < 0 or
            type(observed) is not int or observed < 0):
        return True
    return (value.get('source') != 'vision_tracker' or value.get('valid') is not True or
            value.get('observation_state') != 'OBSERVED' or
            value.get('coverage') != 'team_visible' or observed < expected)
