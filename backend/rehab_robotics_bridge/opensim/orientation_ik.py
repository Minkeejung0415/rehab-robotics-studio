"""Orientation IK solver seam (Phase 18) — Fake + Unavailable, ROS-free.

Product joint angles come only from an ``OrientationIkSolver`` implementation.
This module never imports or calls the debug relative-quaternion angle helper.

Mounting-offset correction (OpenSense-style, D-18-07)
------------------------------------------------------
Treat ``CalibrationArtifact`` master/slave quaternions as sensor orientations
at the identity model pose (standing, knees extended). Corrected sensor
orientation before IK is:

    q_corrected = q_sensor ⊗ conjugate(q_mount)

where ⊗ is Hamilton product and quaternions are ROS ``(x, y, z, w)``.

Fake flexion axis
-----------------
``FakeOrientationIkSolver`` approximates the right-knee flexion coordinate by
the signed rotation of the offset-corrected relative orientation
``q_rel = conj(q_master_corr) * q_slave_corr`` about the fixed body +X axis.
Positive rotation about +X maps to positive ``knee_angle_r`` (radians). This
is a deterministic test double — not the product OpenSim InverseKinematics
solver.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import time
from typing import Protocol, Sequence

from rehab_robotics_bridge.opensim.calibration import CalibrationArtifact
from rehab_robotics_bridge.opensim_adapter import ros_xyzw_to_opensim_rotation

IK_STATUS_SCHEMA = "rehab.opensim_ik_status.1"
DEFAULT_JOINT_NAME = "knee_angle_r"

# Fake flexion axis in body frame (unit vector).
_FLEXION_AXIS = (1.0, 0.0, 0.0)


@dataclass(frozen=True)
class IkSolution:
    """Result of one Orientation IK solve attempt."""

    solution_valid: bool
    reason: str
    joint_names: list[str]
    positions_rad: list[float]
    source_timestamp_ns: int | None
    orientation_residual_rms: float | None
    orientation_residual_max: float | None
    calibration_id: str | None
    input_age_s: float | None
    solve_duration_s: float | None
    visualization_coordinate_names: list[str] = field(default_factory=list)
    visualization_positions_rad: list[float] = field(default_factory=list)


class OrientationIkSolver(Protocol):
    """Protocol for product Orientation IK backends (Fake / OpenSim / Unavailable)."""

    def reset(self) -> None:
        """Clear assemble/track state after calibration clear or change."""

    def solve(
        self,
        *,
        master_xyzw: Sequence[float],
        slave_xyzw: Sequence[float],
        calibration: CalibrationArtifact | None,
        source_timestamp_ns: int | None,
        input_age_s: float | None,
        joint_names: Sequence[str],
    ) -> IkSolution:
        """Solve for joint coordinates; never fabricate wall-time stamps."""

    def solve_n(
        self,
        inputs: list[tuple[str, Sequence[float]]],
        source_timestamp_ns: int | None,
        input_age_s: float | None,
        joint_names: Sequence[str],
        calibration: CalibrationArtifact | None = None,
    ) -> IkSolution:
        """Solve for N-sensor input list; never fabricate wall-time stamps."""


def ik_status_dict(solution: IkSolution, *, backend: str) -> dict[str, object]:
    """Build rosbridge-friendly JSON payload for ``/opensim/ik_status``."""

    return {
        "schema": IK_STATUS_SCHEMA,
        "solution_valid": bool(solution.solution_valid),
        "reason": str(solution.reason),
        "calibration_id": solution.calibration_id,
        "orientation_residual_rms": solution.orientation_residual_rms,
        "orientation_residual_max": solution.orientation_residual_max,
        "input_age_s": solution.input_age_s,
        "solve_duration_s": solution.solve_duration_s,
        "backend": backend,
        "joint_names": list(solution.joint_names),
        "source_timestamp_ns": solution.source_timestamp_ns,
        "positions_rad": list(solution.positions_rad),
    }


def _normalize_xyzw(
    xyzw: Sequence[float],
) -> tuple[float, float, float, float]:
    rotation = ros_xyzw_to_opensim_rotation(
        float(xyzw[0]),
        float(xyzw[1]),
        float(xyzw[2]),
        float(xyzw[3]),
    )
    w, x, y, z = rotation.scalar_first
    return (x, y, z, w)


def _conj(q: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    return (-q[0], -q[1], -q[2], q[3])


def _mul(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Hamilton product for ROS xyzw quaternions."""

    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def apply_mounting_offsets(
    master_xyzw: Sequence[float],
    slave_xyzw: Sequence[float],
    artifact: CalibrationArtifact,
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    """Apply OpenSense-style mount correction: q ⊗ conjugate(q_mount)."""

    master = _normalize_xyzw(master_xyzw)
    slave = _normalize_xyzw(slave_xyzw)
    mount_m = _normalize_xyzw(artifact.master_xyzw)
    mount_s = _normalize_xyzw(artifact.slave_xyzw)
    return (
        _mul(master, _conj(mount_m)),
        _mul(slave, _conj(mount_s)),
    )


def _relative_xyzw(
    master: tuple[float, float, float, float],
    slave: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    return _mul(_conj(master), slave)


def _signed_angle_about_axis(
    q_rel: tuple[float, float, float, float],
    axis: tuple[float, float, float],
) -> float:
    """Project relative quaternion onto axis → signed angle (radians)."""

    qx, qy, qz, qw = q_rel
    # Ensure shortest hemisphere.
    if qw < 0.0:
        qx, qy, qz, qw = -qx, -qy, -qz, -qw
    # Vector part projected onto axis.
    v_dot = qx * axis[0] + qy * axis[1] + qz * axis[2]
    # Signed angle 2*atan2(|v_axis|, w) with sign of projection.
    angle = 2.0 * math.atan2(abs(v_dot), qw)
    if v_dot < 0.0:
        angle = -angle
    return angle


class UnavailableOrientationIkSolver:
    """Fail-closed solver when OpenSim orientation IK APIs are missing."""

    def __init__(self, reason: str) -> None:
        self._reason = str(reason) or "opensim_ik_api_unavailable"

    def reset(self) -> None:
        return

    def solve(
        self,
        *,
        master_xyzw: Sequence[float],
        slave_xyzw: Sequence[float],
        calibration: CalibrationArtifact | None,
        source_timestamp_ns: int | None,
        input_age_s: float | None,
        joint_names: Sequence[str],
    ) -> IkSolution:
        del master_xyzw, slave_xyzw, calibration, joint_names
        return IkSolution(
            solution_valid=False,
            reason=self._reason,
            joint_names=[],
            positions_rad=[],
            source_timestamp_ns=source_timestamp_ns,
            orientation_residual_rms=None,
            orientation_residual_max=None,
            calibration_id=None,
            input_age_s=input_age_s,
            solve_duration_s=0.0,
        )

    def solve_n(
        self,
        inputs: list[tuple[str, Sequence[float]]],
        source_timestamp_ns: int | None,
        input_age_s: float | None,
        joint_names: Sequence[str],
        calibration: CalibrationArtifact | None = None,
    ) -> IkSolution:
        del inputs, calibration, joint_names
        return IkSolution(
            solution_valid=False,
            reason=self._reason,
            joint_names=[],
            positions_rad=[],
            source_timestamp_ns=source_timestamp_ns,
            orientation_residual_rms=None,
            orientation_residual_max=None,
            calibration_id=None,
            input_age_s=input_age_s,
            solve_duration_s=0.0,
        )


class FakeOrientationIkSolver:
    """Deterministic test double: relative orientation about +X → knee_angle_r."""

    def __init__(self) -> None:
        self._assembled = False

    def reset(self) -> None:
        self._assembled = False

    def solve(
        self,
        *,
        master_xyzw: Sequence[float],
        slave_xyzw: Sequence[float],
        calibration: CalibrationArtifact | None,
        source_timestamp_ns: int | None,
        input_age_s: float | None,
        joint_names: Sequence[str],
    ) -> IkSolution:
        started = time.perf_counter()
        names = [str(name) for name in joint_names] or [DEFAULT_JOINT_NAME]

        if calibration is None:
            return IkSolution(
                solution_valid=False,
                reason="calibration_required",
                joint_names=names,
                positions_rad=[],
                source_timestamp_ns=source_timestamp_ns,
                orientation_residual_rms=None,
                orientation_residual_max=None,
                calibration_id=None,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
            )

        if source_timestamp_ns is None:
            return IkSolution(
                solution_valid=False,
                reason="missing_source_timestamp",
                joint_names=names,
                positions_rad=[],
                source_timestamp_ns=None,
                orientation_residual_rms=None,
                orientation_residual_max=None,
                calibration_id=calibration.calibration_id,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
            )

        try:
            master_corr, slave_corr = apply_mounting_offsets(
                master_xyzw,
                slave_xyzw,
                calibration,
            )
            q_rel = _relative_xyzw(master_corr, slave_corr)
            angle = _signed_angle_about_axis(q_rel, _FLEXION_AXIS)
        except (TypeError, ValueError, IndexError) as exc:
            return IkSolution(
                solution_valid=False,
                reason=f"invalid_orientation:{exc}",
                joint_names=names,
                positions_rad=[],
                source_timestamp_ns=source_timestamp_ns,
                orientation_residual_rms=None,
                orientation_residual_max=None,
                calibration_id=calibration.calibration_id,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
            )

        self._assembled = True
        positions = [float(angle) for _ in names]
        return IkSolution(
            solution_valid=True,
            reason="ok",
            joint_names=names,
            positions_rad=positions,
            source_timestamp_ns=int(source_timestamp_ns),
            orientation_residual_rms=0.0,
            orientation_residual_max=0.0,
            calibration_id=calibration.calibration_id,
            input_age_s=input_age_s,
            solve_duration_s=time.perf_counter() - started,
        )

    def solve_n(
        self,
        inputs: list[tuple[str, Sequence[float]]],
        source_timestamp_ns: int | None,
        input_age_s: float | None,
        joint_names: Sequence[str],
        calibration: CalibrationArtifact | None = None,
    ) -> IkSolution:
        """Deterministic test double for N-sensor solve: delegates to solve() using first two frames."""
        started = time.perf_counter()
        names = [str(name) for name in joint_names] or [DEFAULT_JOINT_NAME]

        if calibration is None:
            return IkSolution(
                solution_valid=False,
                reason="calibration_required",
                joint_names=names,
                positions_rad=[],
                source_timestamp_ns=source_timestamp_ns,
                orientation_residual_rms=None,
                orientation_residual_max=None,
                calibration_id=None,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
            )

        if source_timestamp_ns is None:
            return IkSolution(
                solution_valid=False,
                reason="missing_source_timestamp",
                joint_names=names,
                positions_rad=[],
                source_timestamp_ns=None,
                orientation_residual_rms=None,
                orientation_residual_max=None,
                calibration_id=calibration.calibration_id,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
            )

        identity = (0.0, 0.0, 0.0, 1.0)
        master_xyzw = inputs[0][1] if len(inputs) >= 1 else identity
        slave_xyzw = inputs[1][1] if len(inputs) >= 2 else identity

        try:
            master_corr, slave_corr = apply_mounting_offsets(
                master_xyzw,
                slave_xyzw,
                calibration,
            )
            q_rel = _relative_xyzw(master_corr, slave_corr)
            angle = _signed_angle_about_axis(q_rel, _FLEXION_AXIS)
        except (TypeError, ValueError, IndexError) as exc:
            return IkSolution(
                solution_valid=False,
                reason=f"invalid_orientation:{exc}",
                joint_names=names,
                positions_rad=[],
                source_timestamp_ns=source_timestamp_ns,
                orientation_residual_rms=None,
                orientation_residual_max=None,
                calibration_id=calibration.calibration_id,
                input_age_s=input_age_s,
                solve_duration_s=time.perf_counter() - started,
            )

        self._assembled = True
        positions = [float(angle) for _ in names]
        return IkSolution(
            solution_valid=True,
            reason="ok",
            joint_names=names,
            positions_rad=positions,
            source_timestamp_ns=int(source_timestamp_ns),
            orientation_residual_rms=0.0,
            orientation_residual_max=0.0,
            calibration_id=calibration.calibration_id,
            input_age_s=input_age_s,
            solve_duration_s=time.perf_counter() - started,
        )


__all__ = [
    "DEFAULT_JOINT_NAME",
    "IK_STATUS_SCHEMA",
    "FakeOrientationIkSolver",
    "IkSolution",
    "OrientationIkSolver",
    "UnavailableOrientationIkSolver",
    "apply_mounting_offsets",
    "ik_status_dict",
]
