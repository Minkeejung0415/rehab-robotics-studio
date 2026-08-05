"""
Launch file: Rehab Robotics full stack.

Starts:
  - fleet_bridge_node (preferred wireless/N-route path) OR dual esp32_bridge_node (legacy)
  - rosbridge_websocket  (port 9090, GUI connects here)

Usage:
  ros2 launch rehab_robotics_bridge rehab_robotics.launch.py
  ros2 launch rehab_robotics_bridge rehab_robotics.launch.py use_fleet_bridge:=true routes_json:='[...]'
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _fleet_bridge(context, *args, **kwargs):
    enabled = LaunchConfiguration('use_fleet_bridge').perform(context).lower()
    if enabled not in ('true', '1', 'yes'):
        return []
    return [Node(
        package='rehab_robotics_bridge',
        executable='fleet_bridge_node',
        name='esp_fleet_bridge',
        output='screen',
        parameters=[{
            'routes_json': LaunchConfiguration('routes_json').perform(context),
            'alias_master_device_id': LaunchConfiguration(
                'alias_master_device_id'
            ).perform(context),
            'alias_slave_device_id': LaunchConfiguration(
                'alias_slave_device_id'
            ).perform(context),
            'registry_period_s': float(
                LaunchConfiguration('registry_period_s').perform(context) or '0.5'
            ),
        }],
    )]


def generate_launch_description():
    args = [
        DeclareLaunchArgument('master_host', default_value='192.168.4.1'),
        DeclareLaunchArgument('master_port', default_value='5000'),
        DeclareLaunchArgument('master_transport', default_value='tcp'),
        DeclareLaunchArgument('master_udp_port', default_value='55001'),
        DeclareLaunchArgument('master_segment', default_value='femur_r_imu'),
        DeclareLaunchArgument('slave_host', default_value='192.168.4.2'),
        DeclareLaunchArgument('slave_port', default_value='5000'),
        DeclareLaunchArgument('slave_transport', default_value='tcp'),
        DeclareLaunchArgument('slave_udp_port', default_value='55002'),
        DeclareLaunchArgument('slave_segment', default_value='tibia_r_imu'),
        DeclareLaunchArgument('filter_window', default_value='3'),
        DeclareLaunchArgument('master_imu_topic', default_value='/esp32/master/imu'),
        DeclareLaunchArgument('slave_imu_topic', default_value='/esp32/slave/imu'),
        DeclareLaunchArgument('master_frame', default_value='femur_r_imu'),
        DeclareLaunchArgument('slave_frame', default_value='tibia_r_imu'),
        DeclareLaunchArgument('model_path', default_value=''),
        DeclareLaunchArgument('stale_timeout_s', default_value='1.0'),
        DeclareLaunchArgument('status_topic', default_value='/opensim/status'),
        DeclareLaunchArgument('joint_angle_topic', default_value='/opensim/joint_angle'),
        DeclareLaunchArgument('publish_joint_angle_enabled', default_value='false'),
        DeclareLaunchArgument('enable_opensim_bridge', default_value='true'),
        DeclareLaunchArgument('enable_opensim_test_publisher', default_value='false'),
        DeclareLaunchArgument('enable_recorder', default_value='true'),
        DeclareLaunchArgument('enable_rosbridge', default_value='true'),
        DeclareLaunchArgument('enable_processing_observer', default_value='true'),
        DeclareLaunchArgument(
            'use_fleet_bridge',
            default_value='false',
            description='When true, start one fleet_bridge_node instead of dual esp32_bridge_node',
        ),
        DeclareLaunchArgument(
            'routes_json',
            default_value='[]',
            description='Fleet route table JSON (host/port/expected_device_id/role)',
        ),
        DeclareLaunchArgument('alias_master_device_id', default_value=''),
        DeclareLaunchArgument('alias_slave_device_id', default_value=''),
        DeclareLaunchArgument('registry_period_s', default_value='0.5'),
        DeclareLaunchArgument('enable_model_catalog', default_value='true', description='Start model_catalog_node'),
        DeclareLaunchArgument('enable_mapping_node', default_value='true', description='Start mapping_node'),
        DeclareLaunchArgument('mapping_store_path', default_value='', description='Path to mapping_store.json (empty = use default ~/.ros/rehab_robotics/mapping_store.json)'),
    ]

    def bridge(role, host, tcp_port, transport, udp_port, segment):
        return Node(
            package='rehab_robotics_bridge',
            executable='esp32_bridge_node',
            name=f'esp_bridge_{role}',
            output='screen',
            parameters=[{
                'node_id': role,
                'host': LaunchConfiguration(host),
                'port': LaunchConfiguration(tcp_port),
                'udp_port': LaunchConfiguration(udp_port),
                'transport': LaunchConfiguration(transport),
                'body_segment': LaunchConfiguration(segment),
                'publish_native_topics': True,
            }],
            condition=UnlessCondition(LaunchConfiguration('use_fleet_bridge')),
        )

    def filter_node(role):
        return Node(package='rehab_robotics_bridge', executable='esp_filter', name=f'esp_filter_{role}', output='screen', parameters=[{
            'raw_topic': f'/esp/raw/{role}', 'filtered_topic': f'/esp/filtered/{role}',
            'window': LaunchConfiguration('filter_window'),
        }])

    rosbridge = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        parameters=[{
            'port': 9090,
            'address': '0.0.0.0',
            'retry_startup_delay': 5.0,
        }],
        condition=IfCondition(LaunchConfiguration('enable_rosbridge')),
        output='screen',
    )

    opensim = Node(package='rehab_robotics_bridge', executable='opensim_bridge', name='opensim_bridge', output='screen', parameters=[{
        'master_imu_topic': LaunchConfiguration('master_imu_topic'),
        'slave_imu_topic': LaunchConfiguration('slave_imu_topic'),
        'master_frame': LaunchConfiguration('master_frame'),
        'slave_frame': LaunchConfiguration('slave_frame'),
        'model_path': LaunchConfiguration('model_path'),
        'stale_timeout_s': LaunchConfiguration('stale_timeout_s'),
        'status_topic': LaunchConfiguration('status_topic'),
        'joint_angle_topic': LaunchConfiguration('joint_angle_topic'),
        'publish_joint_angle_enabled': LaunchConfiguration('publish_joint_angle_enabled'),
    }], condition=IfCondition(LaunchConfiguration('enable_opensim_bridge')))
    opensim_test_publisher = Node(
        package='rehab_robotics_bridge', executable='opensim_test_publisher',
        name='opensim_test_publisher', output='screen', parameters=[{
            'master_imu_topic': LaunchConfiguration('master_imu_topic'),
            'slave_imu_topic': LaunchConfiguration('slave_imu_topic'),
        }],
        condition=IfCondition(LaunchConfiguration('enable_opensim_test_publisher')),
    )
    recorder = Node(package='rehab_robotics_bridge', executable='esp_record', name='esp_record', output='screen',
        condition=IfCondition(LaunchConfiguration('enable_recorder')))
    status = Node(package='rehab_robotics_bridge', executable='esp_status', name='esp_status', output='screen')
    processing_observer = Node(
        package='rehab_robotics_bridge', executable='processing_block_observer',
        name='processing_block_observer', output='screen',
        condition=IfCondition(LaunchConfiguration('enable_processing_observer')),
    )
    model_catalog = Node(
        package='rehab_robotics_bridge',
        executable='model_catalog_node',
        name='model_catalog_node',
        output='screen',
        parameters=[{'opensim_model_path': LaunchConfiguration('model_path')}],
        condition=IfCondition(LaunchConfiguration('enable_model_catalog')),
    )
    mapping = Node(
        package='rehab_robotics_bridge',
        executable='mapping_node',
        name='mapping_node',
        output='screen',
        parameters=[{'store_path': LaunchConfiguration('mapping_store_path')}],
        condition=IfCondition(LaunchConfiguration('enable_mapping_node')),
    )
    return LaunchDescription(args + [
        OpaqueFunction(function=_fleet_bridge),
        bridge('master', 'master_host', 'master_port', 'master_transport', 'master_udp_port', 'master_segment'),
        bridge('slave', 'slave_host', 'slave_port', 'slave_transport', 'slave_udp_port', 'slave_segment'),
        filter_node('master'),
        filter_node('slave'), opensim, opensim_test_publisher, recorder, status,
        processing_observer, rosbridge, model_catalog, mapping,
    ])
