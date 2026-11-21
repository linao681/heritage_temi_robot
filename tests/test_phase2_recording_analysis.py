import csv
import json
import os
from pathlib import Path
import subprocess
import sys


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
