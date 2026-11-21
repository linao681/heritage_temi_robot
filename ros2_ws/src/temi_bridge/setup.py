from setuptools import setup

package_name = 'temi_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'PyYAML'],
    extras_require={'websocket': ['websockets==16.1.1']},
    entry_points={'console_scripts': ['temi_gateway = temi_bridge.gateway_main:main']},
    zip_safe=True,
    maintainer='Heritage Temi Project Team',
    maintainer_email='maintainer@heritage-temi.invalid',
    description='Backend contract and communication bridge for the heritage temi robot.',
    license='UNLICENSED',
)
