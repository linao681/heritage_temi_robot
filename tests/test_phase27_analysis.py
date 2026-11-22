import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from analyze_phase27_experiment import analyze_experiment, main


def sample_inputs():
    truth = {
        'movement_started_monotonic_sec': 10.0,
        'movement_ended_monotonic_sec': 16.0,
        'actor_motion': {'target_distance_m': 1.4, 'contact_observed': None},
        'gazebo_model_state_samples': [
            {'time_monotonic_sec': 10.0, 'actor_phase': 'APPROACH', 'x': 2.0, 'y': 0.0,
             'robot_x': 0.0, 'robot_y': 0.0, 'center_distance_m': 2.0,
             'geometry_gap_m': 1.2, 'odom_speed_mps': 0.3},
            {'time_monotonic_sec': 12.0, 'actor_phase': 'APPROACH', 'x': 1.5, 'y': 0.0,
             'robot_x': 0.0, 'robot_y': 0.0, 'center_distance_m': 1.5,
             'geometry_gap_m': 0.7, 'odom_speed_mps': 0.1},
            {'time_monotonic_sec': 13.0, 'actor_phase': 'HOLD_TARGET', 'x': 1.4, 'y': 0.0,
             'robot_x': 0.0, 'robot_y': 0.0, 'center_distance_m': 1.4,
             'geometry_gap_m': 0.6, 'odom_speed_mps': 0.0,
             'safety_state': 'STOP_CONFIRMED', 'navigation_session_id': 'old'},
            {'time_monotonic_sec': 15.0, 'actor_phase': 'LEAVE', 'x': 1.8, 'y': 0.0,
             'robot_x': 0.0, 'robot_y': 0.0, 'center_distance_m': 1.8,
             'geometry_gap_m': 1.0, 'odom_speed_mps': 0.0},
        ],
    }
    report = {
        'stop_status_events': [
            {'time_monotonic_sec': 12.5, 'state': 'STOP_REQUESTED',
             'navigation_session_id': 'old', 'valid': True},
            {'time_monotonic_sec': 13.0, 'state': 'STOP_CONFIRMED',
             'navigation_session_id': 'old', 'valid': True},
            {'time_monotonic_sec': 13.5, 'state': 'STOP_CONFIRMED',
             'navigation_session_id': 'new', 'valid': True},
        ],
        'perception_events': [
            {'time_monotonic_sec': 10.5, 'person_observation_state': 'PERSONS_DETECTED',
             'person_observation_valid': True, 'person_distance_valid': False},
            {'time_monotonic_sec': 11.0, 'person_observation_state': 'PERSON_DISTANCE_VALID',
             'person_observation_valid': True, 'person_distance_valid': True,
             'nearest_person_m': 1.9},
        ],
        'speed_controller_events': [
            {'time_monotonic_sec': 11.5, 'status': {'state': 'SLOW',
             'reason': '接近游客，按距离减速', 'target_speed_mps': 0.2}},
        ],
    }
    csv_rows = [
        {'time_monotonic_sec': str(value), 'current_robot_speed_mps': str(speed),
         'person_distance_valid': 'false', 'nearest_person_m': '',
         'raw_person_observation_state': 'NO_PERSON_OBSERVED'}
        for value, speed in ((8.0, 0.29), (8.5, 0.3), (9.0, 0.31), (9.5, 0.3))
    ]
    return truth, report, csv_rows


def test_analysis_matches_stop_uuid_and_calculates_independent_response():
    truth, report, rows = sample_inputs()

    result = analyze_experiment(truth, report, rows, target_robot_speed_mps=0.3)

    assert result['stop_response']['navigation_session_id'] == 'old'
    assert result['stop_response']['response_sec'] == pytest.approx(0.5)
    assert result['stop_response']['confirmed_distance_m'] == pytest.approx(1.4)
    assert result['stop_response']['minimum_center_distance_m'] == pytest.approx(1.4)


def test_analysis_reports_detection_and_rgbd_events_separately():
    truth, report, rows = sample_inputs()

    result = analyze_experiment(truth, report, rows, target_robot_speed_mps=0.3)

    assert result['first_visual_detection']['time_monotonic_sec'] == 10.5
    assert result['first_rgbd_distance']['nearest_person_m'] == 1.9
    assert result['first_person_slow']['time_monotonic_sec'] == 11.5


def test_speed_condition_uses_two_second_preinterference_odom_window():
    truth, report, rows = sample_inputs()

    result = analyze_experiment(truth, report, rows, target_robot_speed_mps=0.3)

    assert result['speed_condition']['sample_count'] == 4
    assert result['speed_condition']['median_mps'] == pytest.approx(0.3)
    assert result['speed_condition']['met'] is True


def test_stop_without_matching_confirmed_uuid_is_not_given_a_response_time():
    truth, report, rows = sample_inputs()
    report['stop_status_events'] = [
        {'time_monotonic_sec': 12.5, 'state': 'STOP_REQUESTED',
         'navigation_session_id': 'old', 'valid': True},
        {'time_monotonic_sec': 13.0, 'state': 'STOP_CONFIRMED',
         'navigation_session_id': 'new', 'valid': True},
    ]

    result = analyze_experiment(truth, report, rows, target_robot_speed_mps=0.3)

    assert result['stop_response']['response_sec'] is None
    assert result['stop_response']['failure_reason'] == 'matching stop confirmation not observed'


def test_repeated_csv_rows_do_not_manufacture_new_clear_samples():
    truth, report, rows = sample_inputs()
    repeated = dict(rows[-1], time_monotonic_sec='10.0', nearest_person_m='4.5',
                    person_distance_valid='true')
    rows.extend([dict(repeated), dict(repeated)])

    result = analyze_experiment(truth, report, rows, target_robot_speed_mps=0.3)

    assert result['unique_observation_timestamps'] == len({
        float(row['time_monotonic_sec']) for row in rows})
    assert result['contact_observed'] is None


def test_analysis_cli_writes_valid_json_report(tmp_path):
    truth, report, rows = sample_inputs()
    truth['status'] = 'PASS'
    truth_path = tmp_path / 'truth.json'
    report_path = tmp_path / 'report.json'
    csv_path = tmp_path / 'topics.csv'
    output_dir = tmp_path / 'analysis'
    truth_path.write_text(json.dumps(truth), encoding='utf-8')
    report_path.write_text(json.dumps(report), encoding='utf-8')
    csv_path.write_text(
        'time_monotonic_sec,current_robot_speed_mps\n' +
        ''.join(f"{row['time_monotonic_sec']},{row['current_robot_speed_mps']}\n"
                for row in rows), encoding='utf-8')

    assert main([
        '--truth', str(truth_path), '--report', str(report_path), '--csv', str(csv_path),
        '--target-robot-speed-mps', '0.3', '--output-dir', str(output_dir),
    ]) == 0

    saved = json.loads((output_dir / 'analysis.json').read_text(encoding='utf-8'))
    assert saved['stop_response']['response_sec'] == pytest.approx(0.5)


def test_analysis_matches_speed_controller_stop_request_inside_actor_window():
    truth, report, rows = sample_inputs()
    report['perception_events'].insert(0, {
        'time_monotonic_sec': 9.5, 'person_observation_state': 'PERSONS_DETECTED',
        'person_observation_valid': True, 'person_distance_valid': True,
        'nearest_person_m': 4.0,
    })
    report['stop_status_events'] = [
        event for event in report['stop_status_events'] if event['state'] != 'STOP_REQUESTED'
    ]
    report['speed_controller_events'] = [
        {'time_monotonic_sec': 9.0, 'status': {
            'stop_requested': True, 'navigation_session_id': 'old'}},
        {'time_monotonic_sec': 12.5, 'status': {
            'stop_requested': True, 'navigation_session_id': 'old'}},
    ]

    result = analyze_experiment(truth, report, rows, target_robot_speed_mps=0.3)

    assert result['first_visual_detection']['time_monotonic_sec'] == 10.5
    assert result['first_rgbd_distance']['time_monotonic_sec'] == 11.0
    assert result['stop_request']['time_monotonic_sec'] == 12.5
    assert result['stop_response']['response_sec'] == pytest.approx(0.5)
    assert result['stop_response']['request_distance_m'] == pytest.approx(1.5)
