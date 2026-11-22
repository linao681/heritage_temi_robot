import importlib.util
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'heritage_hall_launch', ROOT / 'simulation/hall.launch.py')
hall_launch = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hall_launch
spec.loader.exec_module(hall_launch)


def test_camera_variant_updates_the_shared_urdf_description():
    urdf = (ROOT / 'simulation/robot/heritage_robot.urdf').read_text()

    description = hall_launch.configure_camera(urdf, height_m=0.70,
                                               pitch_down_deg=10.0)

    root = ET.fromstring(description)
    camera_joint = next(joint for joint in root.findall('joint')
                        if joint.attrib['name'] == 'depth_camera_fixed')
    optical_joint = next(joint for joint in root.findall('joint')
                         if joint.attrib['name'] == 'depth_camera_optical_fixed')
    camera_xyz = list(map(float, camera_joint.find('origin').attrib['xyz'].split()))
    optical_rpy = list(map(float, optical_joint.find('origin').attrib['rpy'].split()))
    assert camera_xyz == pytest.approx((0.17, 0.0, 0.6))
    assert optical_rpy == pytest.approx((-math.pi / 2 - math.radians(10), 0.0, -math.pi / 2), abs=1e-6)


def test_camera_optical_axis_pitch_is_verified_from_generated_tf_rotation():
    urdf = (ROOT / 'simulation/robot/heritage_robot.urdf').read_text()
    description = hall_launch.configure_camera(urdf, height_m=0.55,
                                               pitch_down_deg=10.0)
    axis = hall_launch.optical_axis_in_base(description)

    assert axis[0] == pytest.approx(math.cos(math.radians(10.0)), abs=1e-6)
    assert axis[1] == pytest.approx(0.0, abs=1e-6)
    assert axis[2] == pytest.approx(-math.sin(math.radians(10.0)), abs=1e-6)


def test_default_camera_variant_preserves_height_and_forward_axis():
    urdf = (ROOT / 'simulation/robot/heritage_robot.urdf').read_text()

    description = hall_launch.configure_camera(urdf, height_m=0.55,
                                               pitch_down_deg=0.0)
    axis = hall_launch.optical_axis_in_base(description)

    assert 'xyz="0.17 0 0.45"' in description
    assert axis == pytest.approx((1.0, 0.0, 0.0), abs=1e-6)


@pytest.mark.parametrize('height,pitch', [
    (float('nan'), 0.0), (0.0, 0.0), (0.55, float('inf')), (0.55, 91.0),
])
def test_camera_variant_rejects_unsupported_pose(height, pitch):
    urdf = (ROOT / 'simulation/robot/heritage_robot.urdf').read_text()

    with pytest.raises(ValueError):
        hall_launch.configure_camera(urdf, height_m=height, pitch_down_deg=pitch)
