#!/usr/bin/env python3
"""Calculate a pinhole camera's geometric floor/head coverage from the Gazebo URDF."""
import argparse
import math
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
URDF = ROOT / 'simulation/robot/heritage_robot.urdf'
PERSON_HEIGHT_M = 1.7  # Explicit analysis assumption, not a measured visitor model.


def _xyz(value):
    values = [float(item) for item in (value or '0 0 0').split()]
    return values if len(values) == 3 else [0.0, 0.0, 0.0]


def camera_geometry(path=URDF):
    root = ET.parse(path).getroot()
    joints = {}
    for joint in root.findall('joint'):
        parent = joint.find('parent').attrib['link']
        child = joint.find('child').attrib['link']
        origin = joint.find('origin')
        xyz = _xyz(origin.attrib.get('xyz') if origin is not None else None)
        rpy = _xyz(origin.attrib.get('rpy') if origin is not None else None)
        joints[child] = (parent, xyz, rpy)
    height = 0.0
    pitch = 0.0
    link = 'depth_camera_link'
    while link in joints:
        parent, xyz, rpy = joints[link]
        height += xyz[2]
        pitch += rpy[1]
        link = parent
    sensor = next(item for item in root.findall('.//sensor')
                  if item.attrib.get('name') == 'depth_camera')
    camera = sensor.find('camera')
    fov = float(camera.findtext('horizontal_fov'))
    width = int(camera.findtext('image/width'))
    image_height = int(camera.findtext('image/height'))
    vertical_fov = 2 * math.atan(image_height / width * math.tan(fov / 2))
    return height, pitch, fov, vertical_fov, width, image_height


def coverage(height, vertical_fov, downward_pitch):
    half = vertical_fov / 2
    lower_ray = half + downward_pitch
    upper_ray = half - downward_pitch
    floor_distance = height / math.tan(lower_ray) if lower_ray > 0 else math.inf
    head_height = max(0.0, PERSON_HEIGHT_M - height)
    head_distance = (head_height / math.tan(upper_ray)
                     if upper_ray > 0 else math.inf)
    return floor_distance, head_distance


def _ray(x, y, angle, dx, scale, color, label):
    end_y = y + math.tan(angle) * dx * scale
    return (f'<line x1="{x}" y1="{y}" x2="{x + dx * scale:.1f}" '
            f'y2="{end_y:.1f}" stroke="{color}" stroke-width="3"/>'
            f'<text x="{x + dx * scale - 8:.1f}" y="{end_y - 8:.1f}" '
            f'fill="{color}" font-size="13">{label}</text>')


def render_svg(height, hfov, vfov, output):
    half_h = hfov / 2
    half_v = vfov / 2
    variants = [
        ('当前：0°俯仰', height, 0.0, '#805a34'),
        ('候选B：下俯5°', height, math.radians(5), '#187b8c'),
        ('候选C：相机高度0.45m', 0.45, 0.0, '#a25e83'),
    ]
    top = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="620" viewBox="0 0 1100 620">',
           '<rect width="100%" height="100%" fill="#fbfaf6"/>',
           '<text x="36" y="38" font-size="22" font-weight="700" fill="#263b40">Gazebo 相机几何覆盖（俯视与侧视）</text>',
           '<text x="36" y="64" font-size="13" fill="#52666a">固定焦距针孔近似；人员身高假设 1.7 m，图示不代表检测性能</text>',
           '<text x="55" y="108" font-size="17" font-weight="700">俯视：水平视场 ±30°</text>',
           '<text x="580" y="108" font-size="17" font-weight="700">侧视：垂直视场与近地面盲区</text>']
    # Top view: a 5 m horizontal sector.
    ox, oy, scale, length = 90, 300, 72, 5.0
    right_x = ox + length * scale
    half_width = math.tan(half_h) * length * scale
    top.extend([
        f'<path d="M {ox} {oy} L {right_x:.1f} {oy-half_width:.1f} L {right_x:.1f} {oy+half_width:.1f} Z" fill="#dfece8" stroke="#187b8c" stroke-width="2"/>',
        f'<circle cx="{ox}" cy="{oy}" r="13" fill="#6a482e"/>',
        f'<line x1="{ox}" y1="{oy}" x2="{right_x:.1f}" y2="{oy}" stroke="#455b5d" stroke-dasharray="7 6"/>',
        '<text x="80" y="330" font-size="12">相机</text>',
        '<text x="230" y="276" font-size="13" fill="#52666a">1 m处半宽约 0.58 m；侧向超过 ±30° 不在视场内</text>',
    ])
    # Side view: rays from each mounting/pitch variant.
    ground_y, cam_x, side_scale = 470, 625, 78
    top.append(f'<line x1="560" y1="{ground_y}" x2="1065" y2="{ground_y}" stroke="#788681" stroke-width="2"/>')
    for label, cam_height, pitch, color in variants:
        cam_y = ground_y - cam_height * side_scale
        lower = half_v + pitch
        upper = half_v - pitch
        top.append(f'<circle cx="{cam_x}" cy="{cam_y:.1f}" r="5" fill="{color}"/>')
        top.append(_ray(cam_x, cam_y, lower, 3.0, side_scale, color, label))
        top.append(_ray(cam_x, cam_y, -upper, 3.0, side_scale, color, '上边界'))
        floor_d, head_d = coverage(cam_height, vfov, pitch)
        marker = cam_x + floor_d * side_scale
        top.append(f'<line x1="{marker:.1f}" y1="{ground_y-9}" x2="{marker:.1f}" y2="{ground_y+9}" stroke="{color}" stroke-width="3"/>')
        top.append(f'<text x="{marker-20:.1f}" y="{ground_y+28}" fill="{color}" font-size="12">{floor_d:.2f}m</text>')
        top.append(f'<text x="580" y="{cam_y-9:.1f}" fill="{color}" font-size="12">{label}</text>')
    top.append('<text x="575" y="590" font-size="12" fill="#52666a">竖线标记相机下边界首次照到地面的距离；相机本体遮挡未建模</text>')
    top.append('</svg>')
    output.write_text('\n'.join(top), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--urdf', type=Path, default=URDF)
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'docs/phase2_6_overnight/camera_coverage.svg')
    args = parser.parse_args()
    height, pitch, hfov, vfov, width, image_height = camera_geometry(args.urdf)
    half_h, half_v = hfov / 2, vfov / 2
    print(f'RGB/depth pinhole geometry: {width}x{image_height}, '
          f'horizontal_fov_deg={math.degrees(hfov):.2f}, '
          f'vertical_fov_deg={math.degrees(vfov):.2f}')
    for label, mount_height, tilt in (
            ('current', height, pitch), ('candidate_down_5_deg', height, pitch + math.radians(5)),
            ('candidate_height_0.45m', 0.45, pitch)):
        floor_distance, head_distance = coverage(mount_height, vfov, tilt)
        print(f'{label}: camera_height_m={mount_height:.3f}, '
              f'down_tilt_deg={math.degrees(tilt):.2f}, '
              f'ground_first_visible_m={floor_distance:.3f}, '
              f'1.7m_head_visible_from_m={head_distance:.3f}')
    print(f'horizontal_half_width_at_1m_m={math.tan(half_h):.3f}; '
          f'vertical_half_angle_deg={math.degrees(half_v):.2f}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    render_svg(height, hfov, vfov, args.output)
    print(f'SVG: {args.output}')


if __name__ == '__main__':
    main()
