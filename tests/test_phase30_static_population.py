import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from run_phase25_clean_tour import summarize_static_population_evidence


@pytest.mark.parametrize(('scenario', 'count'), [
    ('empty', 0), ('single', 1), ('group', 3),
])
def test_static_population_summary_separates_gazebo_truth_from_perception(scenario, count):
    truth = {
        'status': 'PASS',
        'models_spawned_monotonic_sec': 10.0,
        'commanded_model_poses_world': [{'name': f'person_{i}'} for i in range(count)],
    }
    events = [
        {'time_monotonic_sec': 9.9, 'person_observation_state': 'NO_PERSON_OBSERVED'},
        {'time_monotonic_sec': 10.1, 'person_observation_state': 'PERSON_DISTANCE_VALID'},
        {'time_monotonic_sec': 10.2, 'person_observation_state': 'NO_PERSON_OBSERVED'},
    ]

    result = summarize_static_population_evidence(scenario, truth, events)

    assert result['setup_status'] == 'PASS'
    assert result['gazebo_ground_truth_count'] == count
    assert result['gazebo_model_readback_count'] == count
    assert result['perception_sample_count_after_spawn'] == 2
    assert result['perception_observation_states'] == {
        'PERSON_DISTANCE_VALID': 1, 'NO_PERSON_OBSERVED': 1,
    }


def test_static_population_summary_rejects_a_model_count_mismatch():
    with pytest.raises(AssertionError, match='Gazebo模型回读'):
        summarize_static_population_evidence('group', {
            'status': 'PASS', 'models_spawned_monotonic_sec': 10.0,
            'commanded_model_poses_world': [{'name': 'only_one'}],
        }, [])
