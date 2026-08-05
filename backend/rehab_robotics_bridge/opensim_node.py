"""Dual native-IMU ROS bridge for the optional OpenSim visualizer."""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import json
import math
import threading
import time
from typing import Callable

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile
from sensor_msgs.msg import Imu, JointState
from std_msgs.msg import Float64, String
from std_srvs.srv import Trigger

from .opensim.calibration import (
    DEFAULT_CAPTURE_WINDOW_S,
    DEFAULT_MAX_DISPERSION_DEG,
    CalibrationController,
)
from .opensim.ik_contracts import (
    CALIBRATION_CAPTURE_SERVICE,
    CALIBRATION_CLEAR_SERVICE,
    CALIBRATION_STATUS_TOPIC,
    DIAGNOSTICS_TOPIC,
    IK_STATUS_TOPIC,
    JOINT_STATES_TOPIC,
    VISUALIZER_OPEN_SERVICE,
    may_publish_joint_states,
)
from .opensim.n_sensor_calibration import CalibrationArtifactStore
from .opensim.opensim_orientation_ik import create_orientation_ik_solver
from .opensim.orientation_ik import (
    DEFAULT_JOINT_NAME,
    FakeOrientationIkSolver,
    IkSolution,
    OrientationIkSolver,
    UnavailableOrientationIkSolver,
    ik_status_dict,
)
from .opensim_adapter import (
    VisualizerAdapter,
    create_visualizer_adapter,
    relative_orientation_angle_deg,
    ros_xyzw_to_opensim_rotation,
)


_SCHEMA = "rehab.opensim_live_link.1"
_DIAGNOSTICS_SCHEMA = "rehab.opensim_diagnostics.1"
_ROLES = ("master", "slave")
_IMU_QOS = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=1)


def _parse_name_list(raw: object, *, default: list[str]) -> list[str]:
    if isinstance(raw, (list, tuple)):
        names = [str(item).strip() for item in raw if str(item).strip()]
        return names or list(default)
    text = str(raw or "").strip()
    if not text:
        return list(default)
    if "," in text:
        names = [part.strip() for part in text.split(",") if part.strip()]
        return names or list(default)
    return [text]


def _solver_backend_name(solver: object) -> str:
    if isinstance(solver, FakeOrientationIkSolver):
        return "fake"
    if isinstance(solver, UnavailableOrientationIkSolver):
        return "unavailable"
    return type(solver).__name__


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
    last_xyzw: tuple[float, float, float, float] | None = None
    updates: int = 0
    last_error: str = ""


@dataclass
class _DeviceInput:
    """Per-device state for dynamic N-sensor subscription management (IK-01)."""

    device_id: str          # canonical "esp32:aabbccddeeff"
    frame: str              # OpenSim frame name e.g. "tibia_r_imu"
    subscription_handle: object  # ROS subscription returned by create_subscription
    last_xyzw: tuple[float, float, float, float] | None = None
    last_ts_ns: int | None = None
    post_reconnect_fresh: bool = False
    last_seen_monotonic: float | None = None


_MAPPING_CURRENT_TOPIC = "/rehab/mapping/current"
_FLEET_REGISTRY_TOPIC = "/esp/fleet/registry"


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
        calibration_controller: CalibrationController | None = None,
        ik_solver: OrientationIkSolver | None = None,
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
            "joint_angle_topic": "/opensim/joint_angle",
            "publish_joint_angle_enabled": False,
            "calibration_window_s": DEFAULT_CAPTURE_WINDOW_S,
            "calibration_max_dispersion_deg": DEFAULT_MAX_DISPERSION_DEG,
            "ik_joint_names": DEFAULT_JOINT_NAME,
            "ik_coordinate_paths": DEFAULT_JOINT_NAME,
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
        self._frame_mappings = frame_mappings
        self._adapter_factory = (
            None
            if adapter is not None
            else adapter_factory
        )
        self._next_visualizer_recovery_monotonic = 0.0
        self._adapter = (
            adapter
            if adapter is not None
            else adapter_factory(self._model_path, frame_mappings)
        )
        self._visualizer_request_status: tuple[bool, str, str] | None = None
        self._last_visualization_signature: tuple[bool, str, str] | None = None

        if calibration_controller is not None:
            self._calibration = calibration_controller
        else:
            try:
                window_s = float(values["calibration_window_s"])
            except (TypeError, ValueError):
                window_s = DEFAULT_CAPTURE_WINDOW_S
            try:
                max_dispersion = float(values["calibration_max_dispersion_deg"])
            except (TypeError, ValueError):
                max_dispersion = DEFAULT_MAX_DISPERSION_DEG
            self._calibration = CalibrationController(
                window_s=window_s,
                max_dispersion_deg=max_dispersion,
            )
        self._last_calibration_signature: tuple[str, str, object] | None = None
        self._ik_joint_names = _parse_name_list(
            values["ik_joint_names"],
            default=[DEFAULT_JOINT_NAME],
        )
        self._ik_coordinate_paths = _parse_name_list(
            values["ik_coordinate_paths"],
            default=list(self._ik_joint_names),
        )
        if ik_solver is not None:
            self._ik_solver = ik_solver
        else:
            self._ik_solver = create_orientation_ik_solver(
                model_path=self._model_path,
                master_frame=self._sensor_states["master"].frame,
                slave_frame=self._sensor_states["slave"].frame,
                coordinate_paths=self._ik_coordinate_paths,
            )
        self._ik_backend = _solver_backend_name(self._ik_solver)
        self._ik_solution: dict[str, object] | None = None
        self._last_ik_solution: IkSolution | None = None

        self._status_publisher = self.create_publisher(
            String,
            str(values["status_topic"]),
            10,
        )
        self._calibration_status_publisher = self.create_publisher(
            String,
            CALIBRATION_STATUS_TOPIC,
            10,
        )
        self._ik_status_publisher = self.create_publisher(
            String,
            IK_STATUS_TOPIC,
            10,
        )
        self._diagnostics_publisher = self.create_publisher(
            String,
            DIAGNOSTICS_TOPIC,
            10,
        )
        self._joint_states_publisher = self.create_publisher(
            JointState,
            JOINT_STATES_TOPIC,
            10,
        )
        raw_flag = values["publish_joint_angle_enabled"]
        if isinstance(raw_flag, str):
            self._publish_joint_angle_enabled = raw_flag.strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
        else:
            self._publish_joint_angle_enabled = bool(raw_flag)
        self._joint_angle_publisher = None
        self._last_joint_angle_deg: float | None = None
        self._joint_angle_baseline_deg: float | None = None
        if self._publish_joint_angle_enabled:
            self._joint_angle_publisher = self.create_publisher(
                Float64,
                str(values["joint_angle_topic"]),
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

        # N-sensor dynamic subscription management (IK-01)
        self._input_lock = threading.Lock()
        self._mac_inputs: dict[str, _DeviceInput] = {}
        self._n_mapping_revision: int = 0
        self._mapping_subscription = self.create_subscription(
            String,
            _MAPPING_CURRENT_TOPIC,
            self._on_mapping_current,
            _IMU_QOS,
        )
        self._fleet_registry_subscription = self.create_subscription(
            String,
            _FLEET_REGISTRY_TOPIC,
            self._on_fleet_registry,
            _IMU_QOS,
        )

        # N-sensor calibration artifact state (IK-02)
        self._n_calib_artifact: dict | None = None
        self._n_calib_state: str = "uncalibrated"
        self._n_calib_store = CalibrationArtifactStore()
        self._n_model_hash: str = ""   # populated from mapping JSON when available
        self._n_capture_service = self.create_service(
            Trigger,
            "/rehab/calibration/capture",
            self._on_calibration_capture_n,
        )
        self._n_calibration_status_publisher = self.create_publisher(
            String,
            "/rehab/calibration/status",
            10,
        )

        self._capture_service = self.create_service(
            Trigger,
            CALIBRATION_CAPTURE_SERVICE,
            self._on_calibration_capture,
        )
        self._clear_service = self.create_service(
            Trigger,
            CALIBRATION_CLEAR_SERVICE,
            self._on_calibration_clear,
        )
        self._visualizer_open_service = self.create_service(
            Trigger,
            VISUALIZER_OPEN_SERVICE,
            self._on_visualizer_open,
        )
        self._status_timer = self.create_timer(
            min(self._stale_timeout_s / 2.0, 0.5),
            self._on_status_timer,
        )

    def _on_mapping_current(self, message: String) -> None:
        """Handle /rehab/mapping/current: create/destroy MAC-keyed subscriptions."""
        try:
            data = json.loads(message.data)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            self.get_logger().warning(
                f"N-sensor mapping: malformed JSON ignored: {exc}"
            )
            return

        assigned_list = data.get("assigned", [])
        if not isinstance(assigned_list, list):
            self.get_logger().warning(
                "N-sensor mapping: 'assigned' field is not a list; ignored"
            )
            return

        with self._input_lock:
            new_device_ids = {
                entry["device_id"]
                for entry in assigned_list
                if isinstance(entry, dict) and "device_id" in entry
            }
            # Destroy subscriptions for removed devices
            for device_id in list(self._mac_inputs):
                if device_id not in new_device_ids:
                    try:
                        self.destroy_subscription(
                            self._mac_inputs[device_id].subscription_handle
                        )
                    except Exception:
                        pass
                    del self._mac_inputs[device_id]
            # Create subscriptions for new devices
            for entry in assigned_list:
                if not isinstance(entry, dict):
                    continue
                device_id = entry.get("device_id", "")
                if not device_id:
                    continue
                frame = entry.get("frame", "")
                if device_id not in self._mac_inputs:
                    mac_hex = device_id.replace("esp32:", "")
                    topic = f"/esp/raw/mac_{mac_hex}"
                    sub = self.create_subscription(
                        Imu,
                        topic,
                        lambda msg, did=device_id: self._on_mac_imu(did, msg),
                        _IMU_QOS,
                    )
                    self._mac_inputs[device_id] = _DeviceInput(
                        device_id=device_id,
                        frame=frame,
                        subscription_handle=sub,
                    )
                else:
                    # Update frame if it changed
                    self._mac_inputs[device_id].frame = frame

            self._n_mapping_revision = int(data.get("applied_revision", 0))
            self._n_model_hash = str(data.get("model_hash", ""))

        self.get_logger().info(
            f"N-sensor mapping update: {len(self._mac_inputs)} devices"
        )
        self._check_artifact_validity()

    def _on_mac_imu(self, device_id: str, message: Imu) -> None:
        """Handle a MAC-addressed IMU frame for a dynamically subscribed device."""
        source_ts = _source_timestamp_ns(message)
        now = self._monotonic_clock()
        with self._input_lock:
            entry = self._mac_inputs.get(device_id)
            if entry is None:
                return
            orientation = message.orientation
            try:
                xyzw = (
                    float(orientation.x),
                    float(orientation.y),
                    float(orientation.z),
                    float(orientation.w),
                )
            except (TypeError, AttributeError):
                return
            first_frame = entry.last_xyzw is None
            entry.last_xyzw = xyzw
            entry.last_ts_ns = source_ts
            entry.last_seen_monotonic = now
            if first_frame:
                entry.post_reconnect_fresh = True

    def _on_fleet_registry(self, message: String) -> None:
        """Handle /esp/fleet/registry reconnect events; clears post_reconnect_fresh."""
        try:
            data = json.loads(message.data)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            self.get_logger().warning(
                f"N-sensor fleet registry: malformed JSON ignored: {exc}"
            )
            return

        reconnected: list[str] = []
        if "reconnected_devices" in data:
            val = data["reconnected_devices"]
            if isinstance(val, list):
                reconnected = [str(d) for d in val]
        elif "devices" in data and isinstance(data["devices"], list):
            for device_entry in data["devices"]:
                if isinstance(device_entry, dict):
                    if device_entry.get("event") == "reconnect":
                        did = device_entry.get("device_id", "")
                        if did:
                            reconnected.append(str(did))

        with self._input_lock:
            for device_id in reconnected:
                if device_id in self._mac_inputs:
                    self._mac_inputs[device_id].post_reconnect_fresh = False

    def _on_calibration_capture_n(
        self,
        _request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        """Handle /rehab/calibration/capture: snapshot inputs and write artifact.

        Implements T-23-02-03 mitigation: _mac_inputs is snapshotted under lock
        before any reads to prevent TOCTOU race with concurrent remap callbacks.
        """
        with self._input_lock:
            inputs = dict(self._mac_inputs)   # snapshot under lock
        if not inputs:
            response.success = False
            response.message = json.dumps({"outcome": "no_mapping", "artifact_path": None})
            return response
        missing = [did for did, entry in inputs.items() if entry.last_xyzw is None]
        if missing:
            response.success = False
            response.message = json.dumps({"outcome": "missing_inputs", "artifact_path": None})
            return response
        # Build artifact (D-03: alphabetical device_order)
        device_order = sorted(inputs.keys())
        frame_assignments = {
            did: {"segment": "", "frame": inputs[did].frame}
            for did in device_order
        }
        reference_pose = {}
        for did in device_order:
            xyzw = inputs[did].last_xyzw
            reference_pose[did] = {
                "qw": xyzw[3],
                "qx": xyzw[0],
                "qy": xyzw[1],
                "qz": xyzw[2],
            }
        artifact = {
            "schema_version": "calib.v1",
            "model_hash": self._n_model_hash,
            "applied_revision": self._n_mapping_revision,
            "device_order": device_order,
            "frame_assignments": frame_assignments,
            "solver_profile": "lower_body",
            "calibrated_at_iso8601": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            "reference_pose": reference_pose,
        }
        artifact_path = self._n_calib_store.compute_artifact_path(
            self._n_model_hash, self._n_mapping_revision
        )
        self._n_calib_store.save(artifact_path, artifact)
        self._n_calib_artifact = artifact
        self._n_calib_state = "calibrated"
        self._publish_n_calibration_status()
        response.success = True
        response.message = json.dumps(
            {"outcome": "captured", "artifact_path": str(artifact_path)}
        )
        return response

    def _check_artifact_validity(self) -> None:
        """Invalidate calibration artifact if mapping identity has changed (D-05).

        Called after every _on_mapping_current update.
        """
        if self._n_calib_artifact is None:
            return
        with self._input_lock:
            current_device_order = sorted(self._mac_inputs.keys())
        valid = self._n_calib_store.is_valid(
            self._n_calib_artifact,
            self._n_model_hash,
            self._n_mapping_revision,
            current_device_order,
        )
        if not valid:
            self._n_calib_artifact = None
            self._n_calib_state = "uncalibrated"
            self._publish_n_calibration_status()
            self.get_logger().info(
                "N-sensor calibration invalidated by mapping change"
            )

    def _publish_n_calibration_status(self) -> None:
        """Publish N-sensor calibration status to /rehab/calibration/status."""
        payload: dict[str, object] = {
            "schema": "rehab.n_calibration_status.1",
            "state": self._n_calib_state,
            "revision": self._n_mapping_revision,
            "model_hash": self._n_model_hash,
        }
        if self._n_calib_artifact is not None:
            payload["schema_version"] = "calib.v1"
        message = String()
        message.data = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        self._n_calibration_status_publisher.publish(message)

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

        if not accepted and self._recover_visualizer_adapter():
            try:
                self._adapter.update_sensor(
                    role,
                    sensor.frame,
                    rotation,
                )
            except Exception:
                pass

        # A native window failure is orthogonal to acquisition and IK. The
        # adapter records its own unavailable status; a validated IMU sample
        # must still refresh sensor freshness and feed calibration/IK.
        sensor.last_valid_monotonic = self._monotonic_clock()
        if source_timestamp_ns is not None:
            sensor.last_source_timestamp_ns = source_timestamp_ns
        sensor.last_xyzw = (
            float(orientation.x),
            float(orientation.y),
            float(orientation.z),
            float(orientation.w),
        )
        sensor.updates += 1
        self._set_sensor_state(role, "live", "")
        self._feed_calibration_if_capturing()
        self._publish_joint_angle_if_ready()
        self._solve_and_publish_ik()

    def _sensors_ready_for_capture(self) -> tuple[bool, str]:
        for role in _ROLES:
            sensor = self._sensor_states[role]
            if sensor.last_xyzw is None:
                return False, f"missing_{role}_orientation"
            if sensor.state != "live":
                return False, f"{role}_not_live"
        return True, ""

    def _on_calibration_capture(
        self,
        _request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        ready, reason = self._sensors_ready_for_capture()
        if not ready:
            response.success = False
            response.message = reason
            return response
        ok, message = self._calibration.begin_capture()
        response.success = ok
        response.message = message
        self._publish_calibration_status(force=True)
        return response

    def _on_calibration_clear(
        self,
        _request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        self._calibration.clear()
        self._ik_solution = None
        self._last_ik_solution = None
        try:
            self._ik_solver.reset()
        except Exception:
            pass
        response.success = True
        response.message = "cleared"
        self._publish_calibration_status(force=True)
        self._publish_ik_status()
        return response

    def _on_visualizer_open(
        self,
        _request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        """Delegate one bounded, argument-free open request to the adapter."""

        del _request
        adapter_available, _, _ = self._adapter_visualization_signature()
        self._set_visualizer_request_status(
            adapter_available,
            "opening",
            "",
        )
        try:
            result = self._adapter.open_visualizer()
            if not isinstance(result, tuple) or len(result) != 2:
                raise ValueError("visualizer_open_result_invalid")
            success = bool(result[0])
            message = str(result[1] or "")
        except Exception:
            success = False
            message = "visualizer_open_failed"

        if not success and self._recover_visualizer_adapter():
            try:
                result = self._adapter.open_visualizer()
                if not isinstance(result, tuple) or len(result) != 2:
                    raise ValueError("visualizer_open_result_invalid")
                success = bool(result[0])
                message = str(result[1] or "")
            except Exception:
                success = False
                message = "visualizer_open_failed"

        if success:
            message = message or "visualizer_open"
            self._set_visualizer_request_status(True, "open", "")
        else:
            adapter_status = self._adapter_visualization_signature()
            state = (
                "unavailable"
                if adapter_status[1] == "unavailable"
                else "failed"
            )
            reason = message or adapter_status[2] or "visualizer_open_failed"
            self._set_visualizer_request_status(False, state, reason)

        response.success = success
        response.message = message
        return response

    def _feed_calibration_if_capturing(self) -> None:
        master = self._sensor_states["master"]
        slave = self._sensor_states["slave"]
        if master.last_xyzw is None or slave.last_xyzw is None:
            return
        prior = self._calibration.state
        self._calibration.feed_pair(
            master.last_xyzw,
            slave.last_xyzw,
            monotonic_time=self._monotonic_clock(),
        )
        if self._calibration.state != prior:
            self._publish_calibration_status(force=True)

    def _pair_source_timestamp_ns(self) -> int | None:
        master_ts = self._sensor_states["master"].last_source_timestamp_ns
        slave_ts = self._sensor_states["slave"].last_source_timestamp_ns
        if master_ts is None or slave_ts is None:
            return None
        return min(int(master_ts), int(slave_ts))

    def _pair_input_age_s(self) -> float | None:
        now = self._monotonic_clock()
        ages: list[float] = []
        for role in _ROLES:
            last = self._sensor_states[role].last_valid_monotonic
            if last is None:
                return None
            ages.append(max(0.0, now - last))
        return min(ages) if ages else None

    def _solve_and_publish_ik(self) -> None:
        master = self._sensor_states["master"]
        slave = self._sensor_states["slave"]
        if master.last_xyzw is None or slave.last_xyzw is None:
            return
        if master.state != "live" or slave.state != "live":
            return

        source_timestamp_ns = self._pair_source_timestamp_ns()
        solution = self._ik_solver.solve(
            master_xyzw=master.last_xyzw,
            slave_xyzw=slave.last_xyzw,
            calibration=self._calibration.artifact,
            source_timestamp_ns=source_timestamp_ns,
            input_age_s=self._pair_input_age_s(),
            joint_names=self._ik_joint_names,
        )
        self._last_ik_solution = solution
        if (
            solution.solution_valid
            and may_publish_joint_states(self._calibration.state)
            and solution.source_timestamp_ns is not None
        ):
            pose_names = (
                list(solution.visualization_coordinate_names)
                or list(solution.joint_names)
            )
            pose_positions = (
                list(solution.visualization_positions_rad)
                or list(solution.positions_rad)
            )
            try:
                pose_accepted = self._adapter.update_pose(
                    pose_names,
                    pose_positions,
                )
                if not pose_accepted and self._recover_visualizer_adapter():
                    self._adapter.update_pose(
                        pose_names,
                        pose_positions,
                    )
            except Exception:
                # Visualization remains orthogonal to acquisition and product
                # JointState publication.  The adapter owns its failure state.
                pass
            self._ik_solution = {
                "name": list(solution.joint_names),
                "position": list(solution.positions_rad),
                "source_timestamp_ns": int(solution.source_timestamp_ns),
                "solution_valid": True,
            }
        else:
            self._ik_solution = None
        self._publish_ik_status()
        self._maybe_publish_joint_states()

    def _maybe_publish_joint_states(self) -> None:
        """Publish JointState only when CALIBRATED and solution_valid (D-18-05)."""

        if not may_publish_joint_states(self._calibration.state):
            return
        if self._ik_solution is None:
            return
        if not bool(self._ik_solution.get("solution_valid")):
            return
        names = self._ik_solution.get("name")
        positions = self._ik_solution.get("position")
        stamp_ns = self._ik_solution.get("source_timestamp_ns")
        if not isinstance(names, list) or not isinstance(positions, list):
            return
        if not isinstance(stamp_ns, int) or stamp_ns <= 0:
            return
        message = JointState()
        message.name = [str(name) for name in names]
        message.position = [float(value) for value in positions]
        message.header.stamp.sec = stamp_ns // 1_000_000_000
        message.header.stamp.nanosec = stamp_ns % 1_000_000_000
        self._joint_states_publisher.publish(message)

    def _publish_joint_angle_if_ready(self) -> None:
        if not self._publish_joint_angle_enabled or self._joint_angle_publisher is None:
            return
        master = self._sensor_states["master"]
        slave = self._sensor_states["slave"]
        if master.last_xyzw is None or slave.last_xyzw is None:
            return
        if master.state != "live" or slave.state != "live":
            return
        try:
            absolute = relative_orientation_angle_deg(
                master.last_xyzw,
                slave.last_xyzw,
            )
        except (TypeError, ValueError):
            return
        if self._joint_angle_baseline_deg is None:
            self._joint_angle_baseline_deg = absolute
        angle_deg = absolute - self._joint_angle_baseline_deg
        self._last_joint_angle_deg = angle_deg
        message = Float64()
        message.data = float(angle_deg)
        self._joint_angle_publisher.publish(message)

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

    def _adapter_visualization_signature(self) -> tuple[bool, str, str]:
        try:
            adapter_status = self._adapter.status()
            return (
                bool(adapter_status.get("available", False)),
                str(adapter_status.get("state", "unavailable")),
                str(adapter_status.get("reason", "")),
            )
        except Exception:
            return (False, "unavailable", "adapter_status_failed")

    def _recover_visualizer_adapter(self) -> bool:
        """Recreate only a crashed native visualizer, with bounded retries."""

        if self._adapter_factory is None:
            return False
        _, _, reason = self._adapter_visualization_signature()
        if reason not in (
            "visualizer_open_failed",
            "visualizer_update_failed",
            "visualizer_pose_update_failed",
        ):
            return False
        now = self._monotonic_clock()
        if now < self._next_visualizer_recovery_monotonic:
            return False
        self._next_visualizer_recovery_monotonic = now + 1.0
        try:
            replacement = self._adapter_factory(
                self._model_path,
                self._frame_mappings,
            )
        except Exception:
            return False
        self._adapter = replacement
        self._visualizer_request_status = None
        available, _, _ = self._adapter_visualization_signature()
        return available

    def _visualization_signature(self) -> tuple[bool, str, str]:
        adapter_signature = self._adapter_visualization_signature()
        request_signature = self._visualizer_request_status
        if request_signature is None:
            return adapter_signature
        if request_signature[1] in ("opening", "failed", "unavailable"):
            return request_signature
        if adapter_signature[1] in ("failed", "unavailable"):
            return adapter_signature
        return request_signature

    def _record_visualization_transition(
        self,
        signature: tuple[bool, str, str],
    ) -> None:
        if signature == self._last_visualization_signature:
            return
        available, state, reason = signature
        message = (
            "OpenSim visualization state "
            f"available={available} state={state} reason={reason}"
        )
        if state in ("opening", "open"):
            self.get_logger().info(message)
        else:
            self.get_logger().warning(message)
        self._last_visualization_signature = signature

    def _set_visualizer_request_status(
        self,
        available: bool,
        state: str,
        reason: str,
    ) -> None:
        self._visualizer_request_status = (
            bool(available),
            str(state),
            str(reason),
        )
        self._record_visualization_transition(
            self._visualizer_request_status,
        )
        self._publish_status()

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

        self._record_visualization_transition(
            self._visualization_signature(),
        )
        self._publish_status()
        self._publish_calibration_status()
        self._publish_ik_status()
        self._publish_diagnostics()
        self._publish_n_calibration_status()

    def _ik_status_payload(self) -> dict[str, object]:
        if self._last_ik_solution is not None:
            return ik_status_dict(
                self._last_ik_solution,
                backend=self._ik_backend,
            )
        return {
            "schema": "rehab.opensim_ik_status.1",
            "solution_valid": False,
            "reason": "no_solution_yet",
            "calibration_id": (
                self._calibration.artifact.calibration_id
                if self._calibration.artifact is not None
                else None
            ),
            "orientation_residual_rms": None,
            "orientation_residual_max": None,
            "input_age_s": None,
            "solve_duration_s": None,
            "backend": self._ik_backend,
            "joint_names": list(self._ik_joint_names),
            "source_timestamp_ns": None,
            "positions_rad": [],
        }

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
            "calibration": self._calibration.status_dict(),
            "ik": self._ik_status_payload(),
            "joint_angle_deg": (
                self._last_joint_angle_deg
                if self._publish_joint_angle_enabled
                else None
            ),
        }

    def _publish_status(self) -> None:
        message = String()
        message.data = json.dumps(
            self.status_snapshot(),
            sort_keys=True,
            separators=(",", ":"),
        )
        self._status_publisher.publish(message)

    def _publish_calibration_status(self, *, force: bool = False) -> None:
        payload = self._calibration.status_dict()
        signature = (
            str(payload.get("state", "")),
            str(payload.get("reason", "")),
            payload.get("calibration_id"),
        )
        if not force and signature == self._last_calibration_signature:
            return
        self._last_calibration_signature = signature
        message = String()
        message.data = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        self._calibration_status_publisher.publish(message)

    def _publish_ik_status(self) -> None:
        message = String()
        message.data = json.dumps(
            self._ik_status_payload(),
            sort_keys=True,
            separators=(",", ":"),
        )
        self._ik_status_publisher.publish(message)

    def _publish_diagnostics(self) -> None:
        ik = self._ik_status_payload()
        level = "OK" if ik.get("solution_valid") else "WARN"
        if not may_publish_joint_states(self._calibration.state):
            level = "WARN"
        payload = {
            "schema": _DIAGNOSTICS_SCHEMA,
            "level": level,
            "solution_valid": ik.get("solution_valid"),
            "reason": ik.get("reason"),
            "calibration_id": ik.get("calibration_id"),
            "calibration_state": self._calibration.state.value,
            "orientation_residual_rms": ik.get("orientation_residual_rms"),
            "input_age_s": ik.get("input_age_s"),
            "backend": ik.get("backend"),
        }
        message = String()
        message.data = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        self._diagnostics_publisher.publish(message)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = OpenSimBridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
