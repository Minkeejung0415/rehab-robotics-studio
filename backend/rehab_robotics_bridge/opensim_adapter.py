"""OpenSim-independent quaternion conversion and optional visualization adapter.

ROS ``sensor_msgs/Imu.orientation`` supplies quaternion components in ``(x, y,
z, w)`` order.  :func:`ros_xyzw_to_opensim_rotation` is the single conversion
boundary: it rejects unusable values, normalizes finite input, constructs the
scalar-first ``(w, x, y, z)`` semantics used by OpenSim/SimTK, and exposes the
equivalent right-handed active 3x3 rotation matrix consumed by the visualizer
adapter.

This module intentionally performs no sensor calibration, heading correction,
timestamp pairing, inverse kinematics, joint-state solving, or model-pose
mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import math
from pathlib import Path
import shutil
from typing import Any, Mapping, Protocol


_MIN_QUATERNION_NORM = 1e-8


@dataclass(frozen=True)
class OpenSimRotation:
    """Immutable normalized quaternion and equivalent active rotation matrix."""

    scalar_first: tuple[float, float, float, float]
    matrix: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]


def ros_xyzw_to_opensim_rotation(
    x: float,
    y: float,
    z: float,
    w: float,
) -> OpenSimRotation:
    """Validate and convert a ROS ``(x, y, z, w)`` quaternion.

    Raises:
        ValueError: ``quaternion_non_finite`` or ``quaternion_near_zero``.
    """

    components = (float(x), float(y), float(z), float(w))
    if not all(math.isfinite(component) for component in components):
        raise ValueError("quaternion_non_finite")

    scale = max(abs(component) for component in components)
    if scale == 0.0:
        raise ValueError("quaternion_near_zero")

    scaled = tuple(component / scale for component in components)
    norm = math.hypot(*scaled)
    if scale * norm < _MIN_QUATERNION_NORM:
        raise ValueError("quaternion_near_zero")
    normalized = tuple(component / norm for component in scaled)
    if not all(math.isfinite(value) for value in normalized):
        raise ValueError("quaternion_norm_invalid")
    x_n, y_n, z_n, w_n = normalized
    xx, yy, zz = x_n * x_n, y_n * y_n, z_n * z_n
    xy, xz, yz = x_n * y_n, x_n * z_n, y_n * z_n
    wx, wy, wz = w_n * x_n, w_n * y_n, w_n * z_n

    return OpenSimRotation(
        scalar_first=(w_n, x_n, y_n, z_n),
        matrix=(
            (1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)),
            (2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)),
            (2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)),
        ),
    )


def relative_orientation_angle_deg(
    master_xyzw: tuple[float, float, float, float],
    slave_xyzw: tuple[float, float, float, float],
) -> float:
    """Debug/utility: signed relative orientation angle between two ROS quaternions.

    Uses ``q_rel = conj(q_master) * q_slave`` and ``2 * atan2(||xyz||, w)``.
    This is a non-product sensor-relative diagnostic — **not** OpenSim IK and
    must not feed the GUI product knee/angle path. Values are degrees in
    approximately ``(-180, 180]``.
    """

    master = ros_xyzw_to_opensim_rotation(*master_xyzw)
    slave = ros_xyzw_to_opensim_rotation(*slave_xyzw)
    wm, xm, ym, zm = master.scalar_first
    ws, xs, ys, zs = slave.scalar_first
    # q_rel = conj(q_master) * q_slave
    wr = wm * ws + xm * xs + ym * ys + zm * zs
    xr = wm * xs - xm * ws - ym * zs + zm * ys
    yr = wm * ys + xm * zs - ym * ws - zm * xs
    zr = wm * zs - xm * ys + ym * xs - zm * ws
    return math.degrees(2.0 * math.atan2(math.hypot(xr, yr, zr), wr))


class VisualizerAdapter(Protocol):
    """OpenSim-free interface consumed by the ROS subscription layer."""

    def open_visualizer(self) -> tuple[bool, str]:
        """Show the adapter-owned native visualizer without spawning a process."""

    def update_sensor(
        self,
        sensor_id: str,
        frame_name: str,
        rotation: OpenSimRotation,
    ) -> bool:
        """Update only ``sensor_id`` and return whether the update was accepted."""

    def status(self) -> dict[str, object]:
        """Return JSON-safe availability, state, and stable reason fields."""


class UnavailableVisualizerAdapter:
    """Successful no-op adapter used while native visualization is unavailable."""

    def __init__(
        self,
        reason: str,
        frame_mappings: Mapping[str, str] | None = None,
    ) -> None:
        self._reason = reason
        self._frame_mappings = dict(frame_mappings or {})

    def open_visualizer(self) -> tuple[bool, str]:
        """Return the stable capability reason without touching native APIs."""

        return False, self._reason

    def update_sensor(
        self,
        sensor_id: str,
        frame_name: str,
        rotation: OpenSimRotation,
    ) -> bool:
        # The ROS layer already validates role, mapping, and quaternion.  Staying
        # live in non-visual mode is intentional, so native absence is a no-op.
        del sensor_id, frame_name, rotation
        return True

    def status(self) -> dict[str, object]:
        return {
            "available": False,
            "state": "unavailable",
            "reason": self._reason,
        }


class _AdapterInitializationError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class OpenSimVisualizerAdapter:
    """Single-owner OpenSim model and native Simbody visualizer adapter.

    Mapped model frames supply only the displayed triads' ground positions.
    Each ROS message supplies an absolute sensor orientation; model coordinates
    and articulated-body transforms are never mutated.
    """

    _ROLE_COLORS = {
        "master": (0.95, 0.35, 0.20),
        "slave": (0.20, 0.65, 0.95),
    }

    def __init__(
        self,
        model_path: str,
        frame_mappings: Mapping[str, str],
        *,
        opensim_module: Any | None = None,
    ) -> None:
        self._opensim = opensim_module or import_module("opensim")
        self._frame_mappings = dict(frame_mappings)
        self._frames: dict[str, Any] = {}
        self._anchor_positions: dict[str, Any] = {}
        self._decoration_groups: dict[str, Any] = {}
        self._decoration_indices: dict[str, int] = {}
        self._latest_transforms: dict[str, Any] = {}
        self._decoration_generator: Any | None = None
        self._mode = ""
        self._available = False
        self._state_name = "initializing"
        self._reason = ""

        try:
            self._model = self._opensim.Model(model_path)
        except Exception as exc:
            raise _AdapterInitializationError("model_load_failed") from exc

        try:
            self._model.setUseVisualizer(True)
            self._state = self._model.initSystem()
        except Exception as exc:
            raise _AdapterInitializationError(
                "visualizer_initialization_failed",
            ) from exc

        self._resolve_frames()

        try:
            self._model_visualizer = self._model.updVisualizer()
            self._simbody_visualizer = (
                self._model_visualizer.updSimbodyVisualizer()
            )
        except Exception as exc:
            raise _AdapterInitializationError(
                "visualizer_access_failed",
            ) from exc

        # Sampling mode coalesces high-rate IMU updates into a bounded display
        # cadence instead of blocking the ROS callback for every 100 Hz sample.
        visualizer_type = getattr(self._opensim, "SimTKVisualizer", None)
        sampling_mode = getattr(visualizer_type, "Sampling", None)
        set_mode = getattr(self._simbody_visualizer, "setMode", None)
        set_frame_rate = getattr(
            self._simbody_visualizer,
            "setDesiredFrameRate",
            None,
        )
        try:
            if sampling_mode is not None and callable(set_mode):
                set_mode(sampling_mode)
            if callable(set_frame_rate):
                set_frame_rate(30.0)
        except Exception as exc:
            raise _AdapterInitializationError(
                "visualizer_sampling_mode_failed",
            ) from exc

        if self._supports_retained_decorations():
            self._initialize_retained_decorations()
            self._mode = "retained_decorations"
        elif self._supports_decoration_generator():
            self._initialize_decoration_generator()
            self._mode = "decoration_generator"
        else:
            raise _AdapterInitializationError(
                "dynamic_decorations_unsupported_by_bindings",
            )

        self._available = True
        self._state_name = "ready"

    def _resolve_frames(self) -> None:
        frame_type = getattr(self._opensim, "Frame", None)
        safe_down_cast = getattr(frame_type, "safeDownCast", None)
        if not callable(safe_down_cast):
            raise _AdapterInitializationError(
                "frame_api_unsupported_by_bindings",
            )

        for sensor_id, component_path in self._frame_mappings.items():
            try:
                component = self._model.getComponent(component_path)
                frame = safe_down_cast(component)
            except Exception as exc:
                raise _AdapterInitializationError(
                    f"frame_not_found:{sensor_id}:{component_path}",
                ) from exc
            if frame is None or not frame:
                raise _AdapterInitializationError(
                    f"frame_not_found:{sensor_id}:{component_path}",
                )
            try:
                transform = frame.getTransformInGround(self._state)
                anchor_position = transform.p()
            except Exception as exc:
                raise _AdapterInitializationError(
                    f"frame_transform_failed:{sensor_id}:{component_path}",
                ) from exc
            self._frames[sensor_id] = frame
            self._anchor_positions[sensor_id] = anchor_position

    def _supports_retained_decorations(self) -> bool:
        return (
            callable(getattr(self._simbody_visualizer, "addDecoration", None))
            and callable(
                getattr(self._simbody_visualizer, "updDecoration", None),
            )
            and hasattr(self._opensim, "Decorations")
            and hasattr(self._opensim, "DecorativeFrame")
            and hasattr(self._opensim, "DecorativeText")
        )

    def _supports_decoration_generator(self) -> bool:
        return (
            callable(
                getattr(
                    self._simbody_visualizer,
                    "addDecorationGenerator",
                    None,
                ),
            )
            and hasattr(self._opensim, "DecorationGenerator")
        )

    def _make_decorations(self, sensor_id: str) -> Any:
        component_path = self._frame_mappings[sensor_id]
        group = self._opensim.Decorations()
        frame = self._opensim.DecorativeFrame(0.12)
        text = self._opensim.DecorativeText(
            f"{sensor_id}: {component_path}",
        )
        color_values = self._ROLE_COLORS.get(
            sensor_id,
            (0.85, 0.85, 0.85),
        )
        color = self._opensim.Vec3(*color_values)
        if callable(getattr(frame, "setColor", None)):
            frame.setColor(color)
        if callable(getattr(text, "setColor", None)):
            text.setColor(color)
        group.addDecoration(frame)
        group.addDecoration(text)
        return group

    def _initialize_retained_decorations(self) -> None:
        try:
            # OpenSim 4.6 exposes mobilized-body indices returned by frames as
            # ordinary Python integers; it does not export MobilizedBodyIndex.
            ground_index = self._model.getGround().getMobilizedBodyIndex()
            identity_transform = self._opensim.Transform()
            for sensor_id in self._frame_mappings:
                group = self._make_decorations(sensor_id)
                initial_transform = self._opensim.Transform(
                    self._rotation_for_native(
                        ros_xyzw_to_opensim_rotation(0.0, 0.0, 0.0, 1.0),
                    ),
                    self._anchor_positions[sensor_id],
                )
                group.setTransform(initial_transform)
                index = self._simbody_visualizer.addDecoration(
                    ground_index,
                    identity_transform,
                    group,
                )
                self._decoration_groups[sensor_id] = group
                self._decoration_indices[sensor_id] = int(index)
                self._latest_transforms[sensor_id] = initial_transform
        except Exception as exc:
            raise _AdapterInitializationError(
                "dynamic_decorations_unsupported_by_bindings",
            ) from exc

    def _initialize_decoration_generator(self) -> None:
        adapter = self
        opensim_module = self._opensim

        class AdapterDecorationGenerator(opensim_module.DecorationGenerator):
            def __init__(self) -> None:
                super().__init__()

            def generateDecorations(self, state, geometry) -> None:
                del state
                for sensor_id in adapter._frame_mappings:
                    group = adapter._make_decorations(sensor_id)
                    transform = adapter._latest_transforms.get(sensor_id)
                    if transform is not None:
                        group.setTransform(transform)
                    if callable(getattr(geometry, "push_back", None)):
                        geometry.push_back(group)
                    elif callable(getattr(geometry, "append", None)):
                        geometry.append(group)
                    else:
                        raise RuntimeError("unsupported geometry collection")

        try:
            identity = ros_xyzw_to_opensim_rotation(0.0, 0.0, 0.0, 1.0)
            native_identity = self._rotation_for_native(identity)
            for sensor_id in self._frame_mappings:
                self._latest_transforms[sensor_id] = self._opensim.Transform(
                    native_identity,
                    self._anchor_positions[sensor_id],
                )
            self._decoration_generator = AdapterDecorationGenerator()
            self._simbody_visualizer.addDecorationGenerator(
                self._decoration_generator,
            )
        except Exception as exc:
            raise _AdapterInitializationError(
                "dynamic_decorations_unsupported_by_bindings",
            ) from exc

    def _rotation_for_native(self, rotation: OpenSimRotation) -> Any:
        w, x, y, z = rotation.scalar_first
        quaternion = self._opensim.Quaternion(w, x, y, z)
        return self._opensim.Rotation(quaternion)

    def open_visualizer(self) -> tuple[bool, str]:
        """Idempotently show the already-owned native visualizer window."""

        try:
            self._model_visualizer.show(self._state)
        except Exception:
            self._available = False
            self._state_name = "failed"
            self._reason = "visualizer_open_failed"
            return False, self._reason

        self._available = True
        self._state_name = "open"
        self._reason = ""
        return True, "visualizer_open"

    def update_sensor(
        self,
        sensor_id: str,
        frame_name: str,
        rotation: OpenSimRotation,
    ) -> bool:
        expected_frame = self._frame_mappings.get(sensor_id)
        if expected_frame is None:
            raise ValueError("sensor_mapping_unknown")
        if frame_name != expected_frame:
            raise ValueError("frame_mapping_mismatch")
        if not isinstance(rotation, OpenSimRotation):
            raise ValueError("rotation_value_required")

        try:
            transform = self._opensim.Transform(
                self._rotation_for_native(rotation),
                self._anchor_positions[sensor_id],
            )
            self._latest_transforms[sensor_id] = transform
            if self._mode == "retained_decorations":
                decoration = self._simbody_visualizer.updDecoration(
                    self._decoration_indices[sensor_id],
                )
                decoration.setTransform(transform)
            self._model.updVisualizer().show(self._state)
        except Exception:
            self._available = False
            self._state_name = "unavailable"
            self._reason = "visualizer_update_failed"
            return False
        self._available = True
        self._state_name = "ready"
        self._reason = ""
        return True

    def status(self) -> dict[str, object]:
        return {
            "available": self._available,
            "state": self._state_name,
            "reason": self._reason,
            "mode": self._mode,
        }


def create_visualizer_adapter(
    model_path: str,
    frame_mappings: Mapping[str, str],
) -> VisualizerAdapter:
    """Create the native adapter or a stable non-visual fallback.

    Importing this module never imports OpenSim.  The optional binding is loaded
    lazily only after basic model-path validation.
    """

    if not model_path or not str(model_path).strip():
        return UnavailableVisualizerAdapter(
            "model_path_empty",
            frame_mappings,
        )
    if not Path(model_path).is_file():
        return UnavailableVisualizerAdapter(
            "model_path_not_found",
            frame_mappings,
        )

    try:
        opensim_module = import_module("opensim")
    except (ImportError, ModuleNotFoundError):
        return UnavailableVisualizerAdapter(
            "opensim_bindings_unavailable",
            frame_mappings,
        )

    # Simbody may fork while attempting to start its native visualizer. Avoid
    # doing that after rclpy/DDS threads exist when the executable is absent.
    if (
        getattr(opensim_module, "__name__", None) == "opensim"
        and shutil.which("simbody-visualizer") is None
    ):
        return UnavailableVisualizerAdapter(
            "visualizer_initialization_failed",
            frame_mappings,
        )

    try:
        return OpenSimVisualizerAdapter(
            model_path,
            frame_mappings,
            opensim_module=opensim_module,
        )
    except _AdapterInitializationError as exc:
        return UnavailableVisualizerAdapter(exc.reason, frame_mappings)
    except Exception:
        return UnavailableVisualizerAdapter(
            "opensim_adapter_initialization_failed",
            frame_mappings,
        )
