from pathlib import Path
import xml.etree.ElementTree as ET


def test_supports_straddle_center_of_mass():
    robot = ET.parse(Path(__file__).resolve().parents[1] / 'simulation/robot/heritage_robot.urdf')
    supports = [joint.find('origin').get('xyz').split() for joint in robot.findall('joint')
                if 'caster' in joint.get('name')]
    assert min(float(x[0]) for x in supports) < 0
    assert max(float(x[0]) for x in supports) > 0
