import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image
import pytest
import yaml
from scipy.ndimage import distance_transform_edt, label

from scripts.convert_halls import build_hall
from scripts.run_phase27_experiment import (
    build_clean_tour_command, build_system_start_command,
)
from scripts.check_nav2 import validate_domain_configuration


ROOT = Path(__file__).resolve().parents[1]
LAYOUTS = json.loads(
    (ROOT / 'reference/ros2_handoff/environment/layouts.json').read_text())


@pytest.mark.parametrize('layout', ['official', 'adaptive'])
def test_generated_ros_map_matches_layout_source_and_is_connected(layout, tmp_path):
    report = build_hall(LAYOUTS[layout], tmp_path)
    generated = ROOT / 'simulation/generated'
    for suffix in ('.world', '.yaml', '.pgm', '_goals.json'):
        source_bytes = (tmp_path / f'{layout}{suffix}').read_bytes()
        generated_bytes = (generated / f'{layout}{suffix}').read_bytes()
        if suffix == '.world':
            assert source_bytes.rstrip(b'\n') == generated_bytes.rstrip(b'\n')
        else:
            assert source_bytes == generated_bytes

    metadata = yaml.safe_load((generated / f'{layout}.yaml').read_text())
    image = np.asarray(Image.open(generated / metadata['image']))
    resolution = metadata['resolution']
    goals = report['goals']
    free = image > 100
    safe = distance_transform_edt(free) * resolution > report['robot_clearance_radius']
    components, _ = label(safe)
    start_component = None
    for key, goal in goals.items():
        col = int((goal['x'] - metadata['origin'][0]) / resolution)
        row = image.shape[0] - 1 - int((goal['y'] - metadata['origin'][1]) / resolution)
        assert 0 <= row < image.shape[0] and 0 <= col < image.shape[1]
        assert safe[row, col]
        assert int(components[row, col]) == goal['component']
        assert goal['reachable'] is True
        if key == 'wait':
            start_component = int(components[row, col])
        else:
            assert int(components[row, col]) == start_component


@pytest.mark.parametrize('layout', ['official', 'adaptive'])
def test_browser_and_nav2_goal_coordinates_share_the_same_transform(layout):
    script = """
const fs = require('node:fs');
const vm = require('node:vm');
const context = {};
vm.createContext(context);
const source = fs.readFileSync('visualization/ros_hall/layout.js', 'utf8') +
  '\\nglobalThis.__MAP_CONFIGS = MAP_CONFIGS;';
vm.runInContext(source, context);
process.stdout.write(JSON.stringify(context.__MAP_CONFIGS));
"""
    browser_maps = json.loads(subprocess.run(
        ['node', '-e', script], cwd=ROOT, check=True,
        capture_output=True, text=True).stdout)
    browser = browser_maps[layout]
    ros_goals = json.loads(
        (ROOT / f'simulation/generated/{layout}_goals.json').read_text())['goals']
    plan = browser['PLAN']
    for zone in browser['PLAN_ZONES']:
        pixel_x, pixel_y = zone['goal']
        ros_x = (pixel_x - plan['center'][0]) * plan['scale']
        ros_y = -(pixel_y - plan['center'][1]) * plan['scale']
        target = ros_goals[f"zone_{zone['id']}"]
        assert target['x'] == pytest.approx(ros_x, abs=1e-8)
        assert target['y'] == pytest.approx(ros_y, abs=1e-8)


def test_adaptive_layout_is_forwarded_to_system_and_tour(tmp_path):
    experiment = {
        'id': 'T07-ADAPTIVE', 'layout': 'adaptive',
        'robot_speed_mps': 0.3, 'camera_height_m': 0.55,
        'camera_pitch_down_deg': 0.0,
        'timeouts': {'tour_sec': 600.0, 'visitor_sec': 90.0},
    }
    system = build_system_start_command(
        ROOT, experiment, domain_id=214, gazebo_port=11400, web_port=8125)
    tour = build_clean_tour_command(
        ROOT, ROOT / '.venv/bin/python', experiment, tmp_path / 'tour')

    assert system[-1] == 'adaptive'
    assert tour[tour.index('--layout') + 1] == 'adaptive'


def test_nav2_check_requires_an_explicit_matching_isolated_domain():
    assert validate_domain_configuration(
        {'ROS_LOCALHOST_ONLY': '1', 'ROS_DOMAIN_ID': '214'}, 214) == 214
    for env, domain_id in [
        ({'ROS_DOMAIN_ID': '214'}, 214),
        ({'ROS_LOCALHOST_ONLY': '1', 'ROS_DOMAIN_ID': '211'}, 214),
        ({'ROS_LOCALHOST_ONLY': '1', 'ROS_DOMAIN_ID': '214'}, 300),
    ]:
        with pytest.raises(ValueError):
            validate_domain_configuration(env, domain_id)
