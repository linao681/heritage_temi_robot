import sys
import math
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from spawn_people_scenario import scene_positions


def test_local_person_model_has_camera_visible_geometry_and_collisions():
    model = ET.parse(ROOT / 'simulation/models/person_mannequin/model.sdf').getroot()

    assert model.find('.//visual[@name="visitor_billboard"]') is not None
    assert len(model.findall('.//collision')) >= 6
    assert model.find('.//static').text == 'true'
    model_text = (ROOT / 'simulation/models/person_mannequin/model.sdf').read_text()
    assert '__VISITOR_MATERIALS_URI__' in model_text
    assert '__VISITOR_TEXTURES_URI__' in model_text
    assert (ROOT / 'simulation/models/person_mannequin/materials/textures/visitor.png').is_file()


def test_official_scenarios_cover_empty_single_group_near_and_crossing():
    wait = {'x': -12.0, 'y': -8.0}

    assert scene_positions('empty', wait) == []
    assert len(scene_positions('single', wait)) == 1
    assert len(scene_positions('group', wait)) == 3
    assert math.isclose(scene_positions('near', wait)[0][0] - wait['x'], 1.05)
    crossing = scene_positions('crossing', wait)[0]
    assert crossing[:2] == (-9.6, -9.2)


def test_people_scenarios_follow_current_robot_heading():
    pose = {'x': 1.0, 'y': 2.0, 'yaw': math.pi / 2}

    single = scene_positions('single', pose)[0]
    near = scene_positions('near', pose)[0]

    assert math.isclose(single[0], 1.0, abs_tol=1e-9)
    assert math.isclose(single[1], 5.0, abs_tol=1e-9)
    assert math.isclose(near[0], 1.0, abs_tol=1e-9)
    assert math.isclose(near[1], 3.05, abs_tol=1e-9)
