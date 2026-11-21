from setuptools import setup

setup(name='heritage_dashboard', version='0.1.0', packages=['heritage_dashboard'],
      data_files=[('share/ament_index/resource_index/packages',['resource/heritage_dashboard']),('share/heritage_dashboard',['package.xml'])],
      install_requires=['setuptools','PyYAML'],
      entry_points={'console_scripts':['dashboard = heritage_dashboard.main:main']})
