"""Run an isolated Gazebo hall with the approximate robot."""
import json
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

ROOT = Path(__file__).resolve().parent


def setup(context):
    layout = LaunchConfiguration('layout').perform(context)
    if layout not in ('official', 'adaptive'):
        raise ValueError('layout must be official or adaptive')
    goal = json.loads((ROOT / 'generated' / f'{layout}_goals.json').read_text())['goals']['wait']
    description = (ROOT / 'robot/heritage_robot.urdf').read_text()
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
                              OpaqueFunction(function=setup)])
