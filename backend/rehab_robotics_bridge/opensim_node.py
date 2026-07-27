"""Dual native-IMU ROS bridge for the optional OpenSim visualizer."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import time
from typing import Callable

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile
from sensor_msgs.msg import Imu
from std_msgs.msg import String

from .opensim_adapter import (
    VisualizerAdapter,
    create_visualizer_adapter,
    ros_xyzw_to_opensim_rotation,
)


_SCHEMA = "rehab.opensim_live_link.1"
_ROLES = ("master", "slave")
_IMU_QOS = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=1)


def _source_timestamp_ns(message: Imu) -> int | None:
    """Return a usable positive ROS source timestamp, if one was supplied."""

    try:
        stamp = message.header.stamp
        seconds = int(stamp.sec)
        nanoseconds = int(stamp.nanosec)
    except (AttributeError, TypeError, ValueError):
        return None
    if seconds < 0 or not 0 <= nanoseconds < 1_000_000_000:
        return None
    timestamp_ns = seconds * 1_000_000_000 + nanoseconds
    return timestamp_ns if timestamp_ns > 0 else None


@dataclass
class _SensorState:
    topic: str
    frame: str
    waiting_since_monotonic: float
    state: str = "waiting"
    last_valid_monotonic: float | None = None
    last_source_timestamp_ns: int | None = None
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
        try:
            configured_timeout = float(values["stale_timeout_s"])
        except (TypeError, ValueError):
            configured_timeout = 1.0
        if not math.isfinite(configured_timeout):
            configured_timeout = 1.0
        self._stale_timeout_s = max(configured_timeout, 0.1)
        waiting_since_monotonic = self._monotonic_clock()
        self._sensor_states = {
            "master": _SensorState(
                topic=str(values["master_imu_topic"]),
                frame=str(values["master_frame"]),
                waiting_since_monotonic=waiting_since_monotonic,
            ),
            "slave": _SensorState(
                topic=str(values["slave_imu_topic"]),
                frame=str(values["slave_frame"]),
                waiting_since_monotonic=waiting_since_monotonic,
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
        self._last_visualization_signature = self._visualization_signature()

        self._status_publisher = self.create_publisher(
            String,
            str(values["status_topic"]),
            10,
        )
        self._master_subscription = self.create_subscription(
            Imu,
            self._sensor_states["master"].topic,
            self._on_master_imu,
            _IMU_QOS,
        )
        self._slave_subscription = self.create_subscription(
            Imu,
            self._sensor_states["slave"].topic,
            self._on_slave_imu,
            _IMU_QOS,
        )
        self._status_timer = self.create_timer(
            min(self._stale_timeout_s / 2.0, 0.5),
            self._on_status_timer,
        )

    def _on_master_imu(self, message: Imu) -> None:
        self._on_imu("master", message)

    def _on_slave_imu(self, message: Imu) -> None:
        self._on_imu("slave", message)

    def _on_imu(self, role: str, message: Imu) -> None:
        sensor = self._sensor_states[role]
        source_timestamp_ns = _source_timestamp_ns(message)
        if (
            source_timestamp_ns is not None
            and sensor.last_source_timestamp_ns is not None
            and source_timestamp_ns <= sensor.last_source_timestamp_ns
        ):
            return
        orientation = message.orientation
        try:
            rotation = ros_xyzw_to_opensim_rotation(
                orientation.x,
                orientation.y,
                orientation.z,
                orientation.w,
            )
        except (TypeError, ValueError) as exc:
            self._set_sensor_state(role, "invalid", str(exc))
            return

        try:
            accepted = self._adapter.update_sensor(
                role,
                sensor.frame,
                rotation,
            )
        except Exception as exc:
            self._set_sensor_state(
                role,
                "mapping_error",
                str(exc) or "adapter_update_failed",
            )
            return

        if not accepted:
            self._set_sensor_state(
                role,
                "mapping_error",
                "adapter_update_failed",
            )
            return

        sensor.last_valid_monotonic = self._monotonic_clock()
        if source_timestamp_ns is not None:
            sensor.last_source_timestamp_ns = source_timestamp_ns
        sensor.updates += 1
        self._set_sensor_state(role, "live", "")

    def _set_sensor_state(
        self,
        role: str,
        state: str,
        error: str,
    ) -> None:
        sensor = self._sensor_states[role]
        if (sensor.state, sensor.last_error) == (state, error):
            return
        previous_state = sensor.state
        sensor.state = state
        sensor.last_error = error
        message = (
            f"OpenSim sensor {role} state {previous_state}->{state}"
            + (f": {error}" if error else "")
        )
        if state == "live":
            self.get_logger().info(message)
        else:
            self.get_logger().warning(message)

    def _visualization_signature(self) -> tuple[bool, str, str]:
        try:
            adapter_status = self._adapter.status()
            return (
                bool(adapter_status.get("available", False)),
                str(adapter_status.get("state", "unavailable")),
                str(adapter_status.get("reason", "")),
            )
        except Exception:
            return (False, "unavailable", "adapter_status_failed")

    def _on_status_timer(self) -> None:
        now = self._monotonic_clock()
        for role in _ROLES:
            sensor = self._sensor_states[role]
            freshness_baseline = (
                sensor.last_valid_monotonic
                if sensor.last_valid_monotonic is not None
                else sensor.waiting_since_monotonic
            )
            if now - freshness_baseline > self._stale_timeout_s:
                self._set_sensor_state(role, "stale", "stale_timeout")

        visualization_signature = self._visualization_signature()
        if visualization_signature != self._last_visualization_signature:
            available, state, reason = visualization_signature
            message = (
                "OpenSim visualization state "
                f"available={available} state={state} reason={reason}"
            )
            if available:
                self.get_logger().info(message)
            else:
                self.get_logger().warning(message)
            self._last_visualization_signature = visualization_signature
        self._publish_status()

    def status_snapshot(self) -> dict[str, object]:
        now = self._monotonic_clock()
        available, adapter_state, adapter_reason = (
            self._visualization_signature()
        )
        visualization = {
            "available": available,
            "state": adapter_state,
            "reason": adapter_reason,
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
