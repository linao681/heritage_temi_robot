from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('simulation_mode', default_value='false'),
        Node(package='visitor_perception', executable='perception_fusion', output='screen',
             parameters=[{'simulation_mode': LaunchConfiguration('simulation_mode')}]),
    ])
