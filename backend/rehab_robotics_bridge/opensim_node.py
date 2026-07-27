"""Dual native-IMU ROS bridge for the optional OpenSim visualizer."""
from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Callable

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import String

from .opensim_adapter import (
    VisualizerAdapter,
    create_visualizer_adapter,
    ros_xyzw_to_opensim_rotation,
)


_SCHEMA = "rehab.opensim_live_link.1"
_ROLES = ("master", "slave")


@dataclass
class _SensorState:
    topic: str
    frame: str
    state: str = "waiting"
    last_valid_monotonic: float | None = None
    updates: int = 0
    last_error: str = ""


class OpenSimBridgeNode(Node):
    """Forward each valid IMU orientation independently to one adapter role."""

    def __init__(
        self,
        *,
        adapter: VisualizerAdapter | None = None,
        adapter_factory: Callable[
            [str, dict[str, str]],
            VisualizerAdapter,
        ] = create_visualizer_adapter,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__("opensim_bridge")
        self._monotonic_clock = monotonic_clock

        parameter_defaults = {
            "master_imu_topic": "/esp32/master/imu",
            "slave_imu_topic": "/esp32/slave/imu",
            "master_frame": "femur_r_imu",
            "slave_frame": "tibia_r_imu",
            "model_path": "",
            "stale_timeout_s": 1.0,
            "status_topic": "/opensim/status",
        }
        values = {
            name: self.declare_parameter(name, default).value
            for name, default in parameter_defaults.items()
        }
        self._model_path = str(values["model_path"])
        self._stale_timeout_s = max(float(values["stale_timeout_s"]), 0.001)
        self._sensor_states = {
            "master": _SensorState(
                topic=str(values["master_imu_topic"]),
                frame=str(values["master_frame"]),
            ),
            "slave": _SensorState(
                topic=str(values["slave_imu_topic"]),
                frame=str(values["slave_frame"]),
            ),
        }
        frame_mappings = {
            role: sensor.frame
            for role, sensor in self._sensor_states.items()
        }
        self._adapter = (
            adapter
            if adapter is not None
            else adapter_factory(self._model_path, frame_mappings)
        )

        self._status_publisher = self.create_publisher(
            String,
            str(values["status_topic"]),
            10,
        )
        self._master_subscription = self.create_subscription(
            Imu,
            self._sensor_states["master"].topic,
            self._on_master_imu,
            10,
        )
        self._slave_subscription = self.create_subscription(
            Imu,
            self._sensor_states["slave"].topic,
            self._on_slave_imu,
            10,
        )

    def _on_master_imu(self, message: Imu) -> None:
        self._on_imu("master", message)

    def _on_slave_imu(self, message: Imu) -> None:
        self._on_imu("slave", message)

    def _on_imu(self, role: str, message: Imu) -> None:
        sensor = self._sensor_states[role]
        orientation = message.orientation
        try:
            rotation = ros_xyzw_to_opensim_rotation(
                orientation.x,
                orientation.y,
                orientation.z,
                orientation.w,
            )
        except (TypeError, ValueError) as exc:
            sensor.state = "invalid"
            sensor.last_error = str(exc)
            self._publish_status()
            return

        try:
            accepted = self._adapter.update_sensor(
                role,
                sensor.frame,
                rotation,
            )
        except (RuntimeError, TypeError, ValueError) as exc:
            sensor.state = "mapping_error"
            sensor.last_error = str(exc) or "adapter_update_failed"
            self._publish_status()
            return

        if not accepted:
            sensor.state = "mapping_error"
            sensor.last_error = "adapter_update_failed"
            self._publish_status()
            return

        sensor.last_valid_monotonic = self._monotonic_clock()
        sensor.updates += 1
        sensor.state = "live"
        sensor.last_error = ""
        self._publish_status()

    def status_snapshot(self) -> dict[str, object]:
        now = self._monotonic_clock()
        adapter_status = self._adapter.status()
        visualization = {
            "available": bool(adapter_status.get("available", False)),
            "state": str(adapter_status.get("state", "unavailable")),
            "reason": str(adapter_status.get("reason", "")),
            "model_path": self._model_path,
        }
        sensors = {}
        for role in _ROLES:
            sensor = self._sensor_states[role]
            age_s = (
                None
                if sensor.last_valid_monotonic is None
                else round(max(0.0, now - sensor.last_valid_monotonic), 3)
            )
            sensors[role] = {
                "topic": sensor.topic,
                "frame": sensor.frame,
                "state": sensor.state,
                "age_s": age_s,
                "updates": sensor.updates,
                "last_error": sensor.last_error,
            }
        return {
            "schema": _SCHEMA,
            "visualization": visualization,
            "sensors": sensors,
        }

    def _publish_status(self) -> None:
        message = String()
        message.data = json.dumps(
            self.status_snapshot(),
            sort_keys=True,
            separators=(",", ":"),
        )
        self._status_publisher.publish(message)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = OpenSimBridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
