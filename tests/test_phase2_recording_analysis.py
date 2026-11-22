import csv
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock
from types import SimpleNamespace


def test_phase2_analysis_plots_only_the_recorded_topic_samples(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / 'experiment_data.csv'
    rows = [
        {'time_monotonic_sec': '100.0', 'target_speed_mps': '0.5',
         'cmd_vel_linear_x': '0.48', 'odom_linear_x': '0.41',
         'nearest_person_m': '', 'obstacle_distance_m': '2.1',
         'tour_state': 'NAVIGATING', 'speed_controller_state': 'NORMAL',
         'navigation_session_id': 'session-a', 'stop_requested': 'false',
         'stop_confirmed': 'false'},
        {'time_monotonic_sec': '101.0', 'target_speed_mps': '',
         'cmd_vel_linear_x': '0.0', 'odom_linear_x': '0.0',
         'nearest_person_m': '0.52', 'obstacle_distance_m': '0.48',
         'tour_state': 'PAUSED', 'speed_controller_state': 'STOPPED',
         'navigation_session_id': '', 'stop_requested': 'false',
         'stop_confirmed': 'true'},
    ]
    with source.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    env = os.environ.copy()
    env['MPLCONFIGDIR'] = str(tmp_path / 'mpl-cache')

    subprocess.run([sys.executable, str(root / 'scripts/analyze_phase2_recording.py'), str(source)],
                   check=True, capture_output=True, text=True, env=env)

    assert (tmp_path / 'speed_curve.png').stat().st_size > 100
    assert (tmp_path / 'distance_curve.png').stat().st_size > 100
    transitions = json.loads((tmp_path / 'state_transitions.json').read_text())
    assert any(item['field'] == 'speed_controller_state' and item['to'] == 'STOPPED'
               for item in transitions)


def test_phase2_recorder_keeps_dynamic_stop_and_robot_speed_fields():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    from record_phase2_topics import FIELDS, Phase2Recorder

    recorder = object.__new__(Phase2Recorder)
    recorder._mutex = Lock()
    recorder._values = {}
    recorder._speed(SimpleNamespace(data=json.dumps({
        'dynamic_stop_distance_m': 1.72,
        'approach_speed_mps': 0.31,
        'current_robot_speed_mps': 0.28,
        'current_robot_speed_source': 'odom',
    })))

    assert {'dynamic_stop_distance_m', 'approach_speed_mps',
            'current_robot_speed_mps', 'current_robot_speed_source'} <= set(FIELDS)
    assert recorder._values['dynamic_stop_distance_m'] == 1.72
    assert recorder._values['approach_speed_mps'] == 0.31
    assert recorder._values['current_robot_speed_mps'] == 0.28
    assert recorder._values['current_robot_speed_source'] == 'odom'


def test_phase2_recorder_keeps_person_distance_and_visitor_count_validity_separate():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    from record_phase2_topics import FIELDS, Phase2Recorder

    recorder = object.__new__(Phase2Recorder)
    recorder._mutex = Lock()
    recorder._values = {}
    recorder._perception(SimpleNamespace(
        navigation_session_id='session-a', people_count=0, people_valid=False,
        person_observation_state='PERSON_DISTANCE_VALID',
        person_observation_valid=True, person_distance_valid=True,
        nearest_person_m=1.25, obstacle_distance_valid=True,
        obstacle_distance_m=1.1, sample_age_sec=0.4,
        valid=False, error='stable visitor count invalid',
    ))
    recorder._speed(SimpleNamespace(data=json.dumps({
        'input_valid': True, 'visitor_count_valid': False,
    })))

    assert {'visitor_count', 'visitor_count_valid', 'person_observation_valid',
            'person_distance_valid', 'raw_person_observation_state',
            'speed_input_valid'} <= set(FIELDS)
    assert recorder._values['visitor_count'] == 0
    assert recorder._values['visitor_count_valid'] is False
    assert recorder._values['person_observation_valid'] is True
    assert recorder._values['person_distance_valid'] is True
    assert recorder._values['speed_input_valid'] is True
