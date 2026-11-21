from setuptools import setup

package_name = 'heritage_tour_manager'

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
    description='Fixed-route cultural heritage robot tour manager.',
    license='UNLICENSED',
    entry_points={'console_scripts': ['tour_manager = heritage_tour_manager.main:main']},
)
