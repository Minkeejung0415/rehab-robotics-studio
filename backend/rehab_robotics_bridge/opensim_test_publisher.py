"""Opt-in deterministic native IMU publisher for OpenSim live-link checks."""
from __future__ import annotations

import math
from types import SimpleNamespace

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu


_MASTER_FRAME_ID = "opensim_test_master"
_SLAVE_FRAME_ID = "opensim_test_slave"


def _imu_message(
    *,
    frame_id: str,
    x: float,
    y: float,
    z: float,
    w: float,
) -> Imu:
    message = Imu()
    if not hasattr(message, "header"):
        message.header = SimpleNamespace(stamp=None, frame_id="")
    message.header.frame_id = frame_id
    message.orientation.x = x
    message.orientation.y = y
    message.orientation.z = z
    message.orientation.w = w
    return message


def known_orientations() -> dict[str, Imu]:
    """Build fresh master-identity and slave-positive-90Z ROS IMU messages."""

    half_angle = math.sqrt(0.5)
    return {
        "master": _imu_message(
            frame_id=_MASTER_FRAME_ID,
            x=0.0,
            y=0.0,
            z=0.0,
            w=1.0,
        ),
        "slave": _imu_message(
            frame_id=_SLAVE_FRAME_ID,
            x=0.0,
            y=0.0,
            z=half_angle,
            w=half_angle,
        ),
    }


class OpenSimTestPublisher(Node):
    """Publish deterministic orientations to the bridge's two native inputs."""

    def __init__(self) -> None:
        super().__init__("opensim_test_publisher")
        master_topic = str(
            self.declare_parameter(
                "master_imu_topic",
                "/esp32/master/imu",
            ).value
        )
        slave_topic = str(
            self.declare_parameter(
                "slave_imu_topic",
                "/esp32/slave/imu",
            ).value
        )
        configured_rate = self.declare_parameter(
            "publish_rate_hz",
            1.0,
        ).value
        try:
            publish_rate_hz = float(configured_rate)
        except (TypeError, ValueError):
            publish_rate_hz = 1.0
        if not math.isfinite(publish_rate_hz) or publish_rate_hz <= 0.0:
            publish_rate_hz = 1.0

        self._master_publisher = self.create_publisher(Imu, master_topic, 10)
        self._slave_publisher = self.create_publisher(Imu, slave_topic, 10)
        self._timer = self.create_timer(
            1.0 / publish_rate_hz,
            self._publish_orientations,
        )

    def _publish_orientations(self) -> None:
        messages = known_orientations()
        stamp = self.get_clock().now().to_msg()
        messages["master"].header.stamp = stamp
        messages["slave"].header.stamp = stamp
        self._master_publisher.publish(messages["master"])
        self._slave_publisher.publish(messages["slave"])


def main(args=None) -> None:
    rclpy.init(args=args)
    node = OpenSimTestPublisher()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
