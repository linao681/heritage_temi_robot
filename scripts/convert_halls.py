"""交接布局生成 SDF 与 ROS 占据地图；静态连通性仅为几何预检。"""
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, label
import yaml

ROOT = Path(__file__).resolve().parents[1]


def pixel_to_ros(pixel, plan):
    return ((pixel[0] - plan['center'][0]) * plan['scale'],
            -(pixel[1] - plan['center'][1]) * plan['scale'])


def build_hall(layout, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    name, resolution = layout['id'], 0.05
    width = math.ceil((layout['PLAN_W'] + 2) / resolution)
    height = math.ceil((layout['PLAN_D'] + 2) / resolution)
    origin = [-width * resolution / 2, -height * resolution / 2, 0.0]
    yy, xx = np.mgrid[:height, :width]
    xx = origin[0] + (xx + 0.5) * resolution
    yy = origin[1] + (height - yy - 0.5) * resolution
    occupied = np.zeros((height, width), dtype=bool)
    sdf = ET.Element('sdf', version='1.6')
    world = ET.SubElement(sdf, 'world', name=name)
    ET.SubElement(world, 'gravity').text = '0 0 -9.81'
    floor = ET.SubElement(world, 'include')
    ET.SubElement(floor, 'uri').text = 'model://ground_plane'
    assumptions = []
    for fixture in layout['MAP_FIXTURES']:
        x, y = fixture['x'], -fixture['z']
        angle = fixture.get('angle', 0)
        height_m = fixture.get('height', 1.0)
        if 'height' not in fixture:
            assumptions.append(fixture['id'] + ': height=1m assumed')
        dx, dy = xx - x, yy - y
        local_x = dx * math.cos(angle) + dy * math.sin(angle)
        local_y = -dx * math.sin(angle) + dy * math.cos(angle)
        core = fixture['kind'] == 'core'
        if core:
            occupied |= dx**2 + dy**2 <= fixture['radius']**2
        else:
            occupied |= (abs(local_x) <= fixture['w']/2) & (abs(local_y) <= fixture['d']/2)
        model = ET.SubElement(world, 'model', name=fixture['id'])
        ET.SubElement(model, 'static').text = 'true'
        ET.SubElement(model, 'pose').text = f'{x} {y} {height_m/2} 0 0 {angle}'
        link = ET.SubElement(model, 'link', name='body')
        for tag in ('collision', 'visual'):
            geometry = ET.SubElement(ET.SubElement(link, tag, name=tag), 'geometry')
            if core:
                cylinder = ET.SubElement(geometry, 'cylinder')
                ET.SubElement(cylinder, 'radius').text = str(fixture['radius'])
                ET.SubElement(cylinder, 'length').text = str(height_m)
            else:
                box = ET.SubElement(geometry, 'box')
                ET.SubElement(box, 'size').text = f"{fixture['w']} {fixture['d']} {height_m}"
    ET.indent(sdf)
    ET.ElementTree(sdf).write(directory / f'{name}.world', encoding='utf-8', xml_declaration=True)
    image = Image.fromarray(np.where(occupied, 0, 254).astype('uint8'))
    image.save(directory / f'{name}.pgm')
    image.save(directory / f'{name}.png')
    metadata = dict(image=f'{name}.pgm', resolution=resolution, origin=origin,
                    negate=0, occupied_thresh=0.65, free_thresh=0.196)
    (directory / f'{name}.yaml').write_text(yaml.safe_dump(metadata), encoding='utf-8')
    # 房间先作为禁止进入的实心障碍；高度未知均明确列为假设。
    free = distance_transform_edt(~occupied) * resolution > 0.34
    components, _ = label(free)
    points = {'wait': layout['PLAN_WAIT'],
              **{f"zone_{z['id']}": z['goal'] for z in layout['PLAN_ZONES']},
              **{key: value['pixel'] for key, value in layout['PLAN_PORTALS'].items()}}
    goals = {}
    for key, pixel in points.items():
        x, y = pixel_to_ros(pixel, layout['PLAN'])
        col = int((x-origin[0])/resolution)
        row = height-1-int((y-origin[1])/resolution)
        component = int(components[row, col]) if 0 <= row < height and 0 <= col < width else 0
        goals[key] = dict(x=x, y=y, yaw=0.0, component=component)
    start = goals['wait']['component']
    for goal in goals.values():
        goal['reachable'] = bool(start and goal['component'] == start)
    report = dict(layout=name, source='browser_design_not_survey', resolution=resolution,
                  robot_clearance_radius=0.34, obstacle_count=len(layout['MAP_FIXTURES']),
                  assumptions=assumptions + ['rooms treated as solid exclusion areas',
                                            'goal yaw=0 placeholder, docking orientation not validated',
                                            'glass treated as opaque collision for geometric precheck'],
                  goals=goals)
    (directory / f'{name}_goals.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'simulation/generated')
    args = parser.parse_args()
    layouts = json.loads((ROOT / 'reference/ros2_handoff/environment/layouts.json').read_text())
    reports = [build_hall(layout, args.output) for layout in layouts.values()]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0 if all(g['reachable'] for r in reports for g in r['goals'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
