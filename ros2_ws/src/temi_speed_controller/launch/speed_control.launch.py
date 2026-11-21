from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('mock_mode', default_value='false'),
        DeclareLaunchArgument('allow_simulated_sources', default_value='false'),
        Node(package='temi_speed_controller', executable='speed_controller', output='screen',
             parameters=[PathJoinSubstitution([FindPackageShare('temi_speed_controller'), 'config', 'speed_config.yaml']),
                         {'mock_mode': LaunchConfiguration('mock_mode'),
                          'allow_simulated_sources': LaunchConfiguration('allow_simulated_sources')}]),
    ])
