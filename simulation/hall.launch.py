"""Run an isolated Gazebo hall with the approximate robot."""
import json
import math
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

ROOT = Path(__file__).resolve().parent


def configure_camera(description, height_m, pitch_down_deg):
    try:
        height = float(height_m)
        pitch_down = float(pitch_down_deg)
    except (TypeError, ValueError) as error:
        raise ValueError('camera pose must contain finite numbers') from error
    if (not math.isfinite(height) or not 0.3 <= height <= 1.2 or
            not math.isfinite(pitch_down) or not 0.0 <= pitch_down <= 30.0):
        raise ValueError('camera height or downward pitch is outside supported bounds')
    root = ET.fromstring(description)
    base_joint = next((joint for joint in root.findall('joint')
                       if joint.find('parent') is not None and
                       joint.find('child') is not None and
                       joint.find('parent').attrib.get('link') == 'base_footprint' and
                       joint.find('child').attrib.get('link') == 'base_link'), None)
    camera_joint = next((joint for joint in root.findall('joint')
                         if joint.attrib.get('name') == 'depth_camera_fixed'), None)
    optical_joint = next((joint for joint in root.findall('joint')
                          if joint.attrib.get('name') == 'depth_camera_optical_fixed'), None)
    if base_joint is None or camera_joint is None or optical_joint is None:
        raise ValueError('URDF camera or base joint is missing')
    base_origin = base_joint.find('origin')
    camera_origin = camera_joint.find('origin')
    optical_origin = optical_joint.find('origin')
    if base_origin is None or camera_origin is None or optical_origin is None:
        raise ValueError('URDF camera or base origin is missing')
    base_xyz = list(map(float, base_origin.attrib.get('xyz', '0 0 0').split()))
    camera_xyz = list(map(float, camera_origin.attrib.get('xyz', '0 0 0').split()))
    camera_xyz[2] = height - base_xyz[2]
    camera_origin.set('xyz', ' '.join(format(value, '.12g') for value in camera_xyz))
    rpy = list(map(float, optical_origin.attrib.get('rpy', '0 0 0').split()))
    # In the URDF's optical-frame convention, subtracting the downward pitch
    # from the first RPY component rotates the optical +Z axis toward base -Z.
    rpy[0] -= math.radians(pitch_down)
    optical_origin.set('rpy', ' '.join(format(value, '.16g') for value in rpy))
    return ET.tostring(root, encoding='unicode')


def optical_axis_in_base(description):
    root = ET.fromstring(description)
    joint = next((item for item in root.findall('joint')
                  if item.attrib.get('name') == 'depth_camera_optical_fixed'), None)
    if joint is None or joint.find('origin') is None:
        raise ValueError('URDF optical camera joint is missing')
    roll, pitch, yaw = map(float, joint.find('origin').attrib.get('rpy', '0 0 0').split())
    cos_roll, sin_roll = math.cos(roll), math.sin(roll)
    cos_pitch, sin_pitch = math.cos(pitch), math.sin(pitch)
    cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)
    return (
        cos_yaw * sin_pitch * cos_roll + sin_yaw * sin_roll,
        sin_yaw * sin_pitch * cos_roll - cos_yaw * sin_roll,
        cos_pitch * cos_roll,
    )


def setup(context):
    layout = LaunchConfiguration('layout').perform(context)
    if layout not in ('official', 'adaptive'):
        raise ValueError('layout must be official or adaptive')
    camera_height = float(LaunchConfiguration('camera_height_m').perform(context))
    camera_pitch = float(LaunchConfiguration('camera_pitch_down_deg').perform(context))
    goal = json.loads((ROOT / 'generated' / f'{layout}_goals.json').read_text())['goals']['wait']
    urdf_template = (ROOT / 'robot/heritage_robot.urdf').read_text()
    description = configure_camera(urdf_template, camera_height, camera_pitch)
    urdf_dir = Path(tempfile.mkdtemp(prefix='heritage-camera-'))
    urdf_path = urdf_dir / 'heritage_robot.urdf'
    urdf_path.write_text(description, encoding='utf-8')
    print(f'Gazebo and robot_state_publisher share generated URDF: {urdf_path}')
    gazebo = Path(get_package_share_directory('gazebo_ros'))
    return [
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(gazebo / 'launch/gazebo.launch.py')),
                                 launch_arguments={'world': str(ROOT / 'generated' / f'{layout}.world'),
                                                   'gui': LaunchConfiguration('gui')}.items()),
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             parameters=[{'robot_description': description, 'use_sim_time': True}]),
        Node(package='gazebo_ros', executable='spawn_entity.py',
             arguments=['-entity', 'heritage_robot', '-topic', 'robot_description',
                        '-x', str(goal['x']), '-y', str(goal['y']), '-z', '0.02'],
             output='screen'),
    ]


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('layout', default_value='official'),
                              DeclareLaunchArgument('gui', default_value='false'),
                              DeclareLaunchArgument('camera_height_m', default_value='0.55'),
                              DeclareLaunchArgument('camera_pitch_down_deg', default_value='0.0'),
                              OpaqueFunction(function=setup)])
