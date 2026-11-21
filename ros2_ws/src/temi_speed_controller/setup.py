from setuptools import setup

package_name = 'temi_speed_controller'

setup(name=package_name, version='0.1.0', packages=[package_name],
      data_files=[('share/ament_index/resource_index/packages', ['resource/' + package_name]),
                  ('share/' + package_name, ['package.xml']),
                  ('share/' + package_name + '/config', ['config/speed_config.yaml']),
                  ('share/' + package_name + '/launch', ['launch/speed_control.launch.py'])],
      install_requires=['setuptools'], zip_safe=True,
      entry_points={'console_scripts': ['speed_controller = temi_speed_controller.speed_controller_node:main']})
