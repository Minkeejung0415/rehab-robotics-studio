"""
Launch file: Rehab Robotics full stack.

Starts:
  - imu_aggregator_node  (reads nodes.yaml → spawns per-ESP32 bridge nodes)
  - rosbridge_websocket  (port 9090, GUI connects here)

Usage:
  ros2 launch rehab_robotics_bridge rehab_robotics.launch.py
  ros2 launch rehab_robotics_bridge rehab_robotics.launch.py config_file:=/path/to/nodes.yaml
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('rehab_robotics_bridge')
    default_config = os.path.join(pkg_share, 'config', 'nodes.yaml')

    config_arg = DeclareLaunchArgument(
        'config_file',
        default_value=default_config,
        description='Path to nodes.yaml ESP32 node configuration',
    )

    aggregator = Node(
        package='rehab_robotics_bridge',
        executable='imu_aggregator_node',
        name='imu_aggregator',
        parameters=[{'config_file': LaunchConfiguration('config_file')}],
        output='screen',
    )

    rosbridge = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        parameters=[{
            'port': 9090,
            'address': '0.0.0.0',
            'retry_startup_delay': 5.0,
        }],
        output='screen',
    )

    return LaunchDescription([
        config_arg,
        aggregator,
        rosbridge,
    ])
