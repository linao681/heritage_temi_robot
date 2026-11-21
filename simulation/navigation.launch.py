"""Map localization and Nav2 for the currently running simulated hall."""
import json
from pathlib import Path
import shutil
import tempfile

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

ROOT = Path(__file__).resolve().parent


def setup(context):
    layout = LaunchConfiguration('layout').perform(context)
    if layout not in ('official', 'adaptive'):
        raise ValueError('invalid layout')
    goal = json.loads((ROOT / 'generated' / f'{layout}_goals.json').read_text())['goals']['wait']
    nav = Path(get_package_share_directory('nav2_bringup'))
    params = yaml.safe_load((nav / 'params/nav2_params.yaml').read_text())
    amcl = params['amcl']['ros__parameters']
    amcl.update(base_frame_id='base_footprint', set_initial_pose=True,
                alpha1=0.02, alpha2=0.02, alpha3=0.02, alpha4=0.02, alpha5=0.02,
                initial_pose={'x': goal['x'], 'y': goal['y'], 'z': 0.0, 'yaw': 0.0})
    for costmap in ('local_costmap', 'global_costmap'):
        config = params[costmap][costmap]['ros__parameters']
        config.update(robot_base_frame='base_footprint', robot_radius=0.34)
    controller = params['controller_server']['ros__parameters']['FollowPath']
    controller.update(max_vel_x=0.35, max_speed_xy=0.35)
    params['velocity_smoother']['ros__parameters']['max_velocity'][0] = 0.35
    # launch 的配置文件留在独立临时目录，避免覆盖用户配置。
    folder = Path(tempfile.mkdtemp(prefix='heritage-nav2-'))
    config_path = folder / 'nav2.yaml'
    config_path.write_text(yaml.safe_dump(params))
    # ROS 参数重写链对中文路径存在转义问题，地图也复制到本次 ASCII 临时目录。
    for suffix in ('.pgm', '.yaml'):
        shutil.copy2(ROOT / 'generated' / f'{layout}{suffix}', folder / f'{layout}{suffix}')
    return [IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(nav / 'launch/bringup_launch.py')),
        launch_arguments={'map': str(folder / f'{layout}.yaml'),
                          'params_file': str(config_path), 'use_sim_time': 'true',
                          'autostart': 'true', 'use_composition': 'False'}.items())]


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('layout', default_value='official'),
                              OpaqueFunction(function=setup)])
