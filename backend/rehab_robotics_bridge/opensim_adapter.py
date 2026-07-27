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
import math


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

    norm = math.sqrt(sum(component * component for component in components))
    if norm < _MIN_QUATERNION_NORM:
        raise ValueError("quaternion_near_zero")

    x_n, y_n, z_n, w_n = (
        component / norm for component in components
    )
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
