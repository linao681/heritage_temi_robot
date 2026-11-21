from setuptools import setup

package_name = 'visitor_perception'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'PyYAML'],
    zip_safe=True,
    maintainer='Heritage Temi Project Team',
    maintainer_email='maintainer@heritage-temi.invalid',
    description='Anonymous visitor count monitor and offline video detector.',
    license='UNLICENSED',
    entry_points={'console_scripts': ['visitor_perception = visitor_perception.main:main',
                                    'offline_video_count = visitor_perception.video_main:main']},
)
