"""Launch only the OpenSim quaternion subscriber and optional test publisher."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    arguments = [
        DeclareLaunchArgument(
            "master_imu_topic",
            default_value="/esp32/master/imu",
        ),
        DeclareLaunchArgument(
            "slave_imu_topic",
            default_value="/esp32/slave/imu",
        ),
        DeclareLaunchArgument("master_frame", default_value="femur_r_imu"),
        DeclareLaunchArgument("slave_frame", default_value="tibia_r_imu"),
        DeclareLaunchArgument("model_path", default_value=""),
        DeclareLaunchArgument("stale_timeout_s", default_value="1.0"),
        DeclareLaunchArgument("status_topic", default_value="/opensim/status"),
        DeclareLaunchArgument(
            "joint_angle_topic",
            default_value="/opensim/joint_angle",
        ),
        DeclareLaunchArgument(
            "publish_joint_angle_enabled",
            default_value="false",
        ),
        DeclareLaunchArgument(
            "ik_joint_names",
            default_value="knee_angle_r",
        ),
        DeclareLaunchArgument(
            "ik_coordinate_paths",
            default_value="knee_angle_r",
        ),
        DeclareLaunchArgument(
            "enable_test_publisher",
            default_value="false",
        ),
    ]

    bridge = Node(
        package="rehab_robotics_bridge",
        executable="opensim_bridge",
        name="opensim_bridge",
        output="screen",
        parameters=[{
            "master_imu_topic": LaunchConfiguration("master_imu_topic"),
            "slave_imu_topic": LaunchConfiguration("slave_imu_topic"),
            "master_frame": LaunchConfiguration("master_frame"),
            "slave_frame": LaunchConfiguration("slave_frame"),
            "model_path": LaunchConfiguration("model_path"),
            "stale_timeout_s": LaunchConfiguration("stale_timeout_s"),
            "status_topic": LaunchConfiguration("status_topic"),
            "joint_angle_topic": LaunchConfiguration("joint_angle_topic"),
            "publish_joint_angle_enabled": LaunchConfiguration(
                "publish_joint_angle_enabled"
            ),
            "ik_joint_names": LaunchConfiguration("ik_joint_names"),
            "ik_coordinate_paths": LaunchConfiguration("ik_coordinate_paths"),
        }],
    )
    test_publisher = Node(
        package="rehab_robotics_bridge",
        executable="opensim_test_publisher",
        name="opensim_test_publisher",
        output="screen",
        parameters=[{
            "master_imu_topic": LaunchConfiguration("master_imu_topic"),
            "slave_imu_topic": LaunchConfiguration("slave_imu_topic"),
        }],
        condition=IfCondition(LaunchConfiguration("enable_test_publisher")),
    )

    return LaunchDescription(arguments + [bridge, test_publisher])
