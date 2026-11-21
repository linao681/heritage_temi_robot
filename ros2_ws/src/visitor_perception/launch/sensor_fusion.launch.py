"""Launch camera counting, calibrated depth association and fail-closed fusion."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    simulation = LaunchConfiguration('simulation_mode')
    model = LaunchConfiguration('model_path')
    confidence = LaunchConfiguration('confidence')
    image_topic = LaunchConfiguration('image_topic')
    use_sim_time = ParameterValue(simulation, value_type=bool)
    config = PathJoinSubstitution([FindPackageShare('visitor_perception'), 'config', 'camera.yaml'])
    return LaunchDescription([
        DeclareLaunchArgument('simulation_mode', default_value='false'),
        DeclareLaunchArgument('model_path', default_value='assets/vision/object_detection_yolox_2022nov.onnx'),
        DeclareLaunchArgument('confidence', default_value='0.5'),
        DeclareLaunchArgument('image_topic', default_value='depth_camera/image_raw'),
        Node(package='visitor_perception', executable='visitor_perception',
             arguments=['--config', config], output='screen'),
        Node(package='visitor_perception', executable='yolox_person_detector',
             parameters=[{'model_path': model, 'image_topic': image_topic,
                          'confidence': confidence, 'use_sim_time': use_sim_time}], output='screen'),
        Node(package='visitor_perception', executable='depth_association',
             parameters=[{'simulation_mode': simulation,
                          'min_detection_confidence': confidence}], output='screen'),
        Node(package='visitor_perception', executable='perception_fusion',
             parameters=[{'simulation_mode': simulation}], output='screen'),
    ])
