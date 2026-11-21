import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from scripts.convert_halls import build_hall, pixel_to_ros

ROOT = Path(__file__).resolve().parents[1]
LAYOUTS = json.loads((ROOT / 'reference/ros2_handoff/environment/layouts.json').read_text())


def test_coordinate_conversion():
    plan = {'center': [100, 200], 'scale': 0.05}
    assert pixel_to_ros([120, 180], plan) == pytest.approx((1, 1))


@pytest.mark.parametrize('name', ['official', 'adaptive'])
def test_world_and_map_use_same_obstacles(name, tmp_path):
    report = build_hall(LAYOUTS[name], tmp_path)
    world = ET.parse(tmp_path / f'{name}.world')
    models = world.findall('.//model')
    ids = {model.attrib['name'] for model in models}
    assert {item['id'] for item in LAYOUTS[name]['MAP_FIXTURES']} <= ids
    assert report['resolution'] == 0.05
    assert len(report['goals']) == 8
    assert report['source'] == 'browser_design_not_survey'
    assert (tmp_path / f'{name}.pgm').read_bytes().startswith(b'P5')
    assert report['goals']['wait']['reachable']
    assert all(goal['reachable'] for goal in report['goals'].values())
