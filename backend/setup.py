from setuptools import find_packages, setup

package_name = 'rehab_robotics_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/rehab_robotics.launch.py']),
        ('share/' + package_name + '/config', ['config/nodes.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Rehab Robotics',
    maintainer_email='you@example.com',
    description='ESP32 IMU → ROS2 bridge for Rehab Robotics Studio',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'esp32_bridge_node = rehab_robotics_bridge.esp32_bridge_node:main',
            'imu_aggregator_node = rehab_robotics_bridge.imu_aggregator_node:main',
        ],
    },
)
