"""Reference-pose mounting-offset calibration (Phase 17).

OpenSense-style offsets for a fixed known pose (standing, knees extended):
when the model IMU frames are treated as identity at the reference pose,
the sensor-to-model mounting rotation for each IMU is approximately the
mean measured sensor orientation over a stable capture window:

    R_mount ≈ R_sensor_mean   (identity reference model frames)

Quaternions are averaged with antipode-aware sign flips so that samples
near ±q accumulate on the same hemisphere. Angular dispersion is
``2 * acos(|dot(q, mean)|)`` in degrees. This module has no ROS or
OpenSim solver imports.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import uuid
from typing import Sequence

from rehab_robotics_bridge.opensim.ik_contracts import (
    CalibrationState,
    may_publish_joint_states,
)
from rehab_robotics_bridge.opensim_adapter import ros_xyzw_to_opensim_rotation

DEFAULT_CAPTURE_WINDOW_S = 1.5
DEFAULT_MIN_SAMPLES = 10
DEFAULT_MAX_DISPERSION_DEG = 8.0
KNOWN_POSE = "standing_knees_extended"

_IDENTITY_XYZW = (0.0, 0.0, 0.0, 1.0)


@dataclass(frozen=True)
class CalibrationArtifact:
    """In-memory mounting offsets from an accepted stable capture window."""

    calibration_id: str
    known_pose: str
    master_xyzw: tuple[float, float, float, float]
    slave_xyzw: tuple[float, float, float, float]
    captured_at_monotonic: float
    sample_count: int
    window_s: float
    mean_dispersion_deg: float


def _normalize_xyzw(
    xyzw: Sequence[float],
) -> tuple[float, float, float, float]:
    """Validate/normalize via the shared ROS→OpenSim quaternion boundary."""

    rotation = ros_xyzw_to_opensim_rotation(
        float(xyzw[0]),
        float(xyzw[1]),
        float(xyzw[2]),
        float(xyzw[3]),
    )
    w, x, y, z = rotation.scalar_first
    return (x, y, z, w)


def _dot(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3]


def _scale(
    q: tuple[float, float, float, float],
    s: float,
) -> tuple[float, float, float, float]:
    return (q[0] * s, q[1] * s, q[2] * s, q[3] * s)


def _add(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2], a[3] + b[3])


def _unit(
    q: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    norm = math.hypot(q[0], q[1], q[2], q[3])
    if norm < 1e-12:
        raise ValueError("quaternion_near_zero")
    return (q[0] / norm, q[1] / norm, q[2] / norm, q[3] / norm)


def _angular_deviation_deg(
    sample: tuple[float, float, float, float],
    mean: tuple[float, float, float, float],
) -> float:
    """Smallest angle between two unit quaternions (degrees)."""

    d = abs(_dot(sample, mean))
    d = min(1.0, max(0.0, d))
    return math.degrees(2.0 * math.acos(d))


def _antipode_aligned(
    sample: tuple[float, float, float, float],
    reference: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    if _dot(sample, reference) < 0.0:
        return _scale(sample, -1.0)
    return sample


class CalibrationController:
    """Multi-sample stable-window mounting-offset capture with hard publish gate."""

    def __init__(
        self,
        *,
        window_s: float = DEFAULT_CAPTURE_WINDOW_S,
        min_samples: int = DEFAULT_MIN_SAMPLES,
        max_dispersion_deg: float = DEFAULT_MAX_DISPERSION_DEG,
    ) -> None:
        self._window_s = float(window_s)
        self._min_samples = max(1, int(min_samples))
        self._max_dispersion_deg = float(max_dispersion_deg)
        self._state = CalibrationState.UNCALIBRATED
        self._reason = ""
        self._last_capture_error = ""
        self._artifact: CalibrationArtifact | None = None
        self._samples: list[
            tuple[float, tuple[float, float, float, float], tuple[float, float, float, float]]
        ] = []
        self._capture_started_monotonic: float | None = None
        # Running means for dispersion (antipode-aware accumulators).
        self._sum_master = _IDENTITY_XYZW
        self._sum_slave = _IDENTITY_XYZW
        self._count = 0

    @property
    def state(self) -> CalibrationState:
        return self._state

    @property
    def artifact(self) -> CalibrationArtifact | None:
        return self._artifact

    def begin_capture(self) -> tuple[bool, str]:
        if self._state == CalibrationState.CAPTURING:
            return False, "capture already in progress"
        self._reset_capture_buffers()
        self._state = CalibrationState.CAPTURING
        self._reason = "capturing standing knees-extended pose"
        self._last_capture_error = ""
        return True, "capturing"

    def clear(self) -> None:
        self._artifact = None
        self._reset_capture_buffers()
        self._state = CalibrationState.UNCALIBRATED
        self._reason = ""
        self._last_capture_error = ""

    def feed_pair(
        self,
        master_xyzw: Sequence[float],
        slave_xyzw: Sequence[float],
        *,
        monotonic_time: float,
    ) -> CalibrationState:
        if self._state != CalibrationState.CAPTURING:
            return self._state

        try:
            master = _normalize_xyzw(master_xyzw)
            slave = _normalize_xyzw(slave_xyzw)
        except (TypeError, ValueError, IndexError) as exc:
            return self._abort_capture(f"invalid quaternion: {exc}")

        if self._capture_started_monotonic is None:
            self._capture_started_monotonic = float(monotonic_time)

        if self._count == 0:
            aligned_master = master
            aligned_slave = slave
            self._sum_master = master
            self._sum_slave = slave
            self._count = 1
        else:
            mean_master = _unit(self._sum_master)
            mean_slave = _unit(self._sum_slave)
            aligned_master = _antipode_aligned(master, mean_master)
            aligned_slave = _antipode_aligned(slave, mean_slave)
            master_dev = _angular_deviation_deg(aligned_master, mean_master)
            slave_dev = _angular_deviation_deg(aligned_slave, mean_slave)
            if (
                master_dev > self._max_dispersion_deg
                or slave_dev > self._max_dispersion_deg
            ):
                return self._abort_capture(
                    "stability/dispersion exceeded during capture window "
                    f"(master={master_dev:.1f}deg slave={slave_dev:.1f}deg "
                    f"max={self._max_dispersion_deg:.1f}deg)"
                )
            self._sum_master = _add(self._sum_master, aligned_master)
            self._sum_slave = _add(self._sum_slave, aligned_slave)
            self._count += 1

        self._samples.append((float(monotonic_time), aligned_master, aligned_slave))
        elapsed = float(monotonic_time) - float(self._capture_started_monotonic)
        if self._count >= self._min_samples and elapsed >= self._window_s:
            return self._finalize_capture(elapsed)

        return self._state

    def status_dict(self) -> dict[str, object]:
        artifact = self._artifact
        elapsed = 0.0
        if self._capture_started_monotonic is not None and self._samples:
            elapsed = max(0.0, self._samples[-1][0] - self._capture_started_monotonic)
        reason = self._reason
        if self._last_capture_error and self._state == CalibrationState.CALIBRATED:
            reason = self._last_capture_error
        return {
            "state": self._state.value,
            "reason": reason,
            "known_pose": KNOWN_POSE,
            "sample_count": self._count if self._state == CalibrationState.CAPTURING else (
                artifact.sample_count if artifact is not None else 0
            ),
            "window_s": round(elapsed, 3) if self._state == CalibrationState.CAPTURING else (
                artifact.window_s if artifact is not None else 0.0
            ),
            "calibration_id": artifact.calibration_id if artifact is not None else None,
            "has_offsets": artifact is not None,
            "may_publish_joint_states": may_publish_joint_states(self._state),
        }

    def _reset_capture_buffers(self) -> None:
        self._samples = []
        self._capture_started_monotonic = None
        self._sum_master = _IDENTITY_XYZW
        self._sum_slave = _IDENTITY_XYZW
        self._count = 0

    def _abort_capture(self, reason: str) -> CalibrationState:
        self._last_capture_error = reason
        prior = self._artifact
        self._reset_capture_buffers()
        if prior is not None:
            # Transactional: keep prior CALIBRATED artifact on failed re-capture.
            self._state = CalibrationState.CALIBRATED
            self._reason = ""
            return self._state
        self._state = CalibrationState.FAILED
        self._reason = reason
        return self._state

    def _finalize_capture(self, elapsed: float) -> CalibrationState:
        mean_master = _unit(self._sum_master)
        mean_slave = _unit(self._sum_slave)
        dispersions: list[float] = []
        for _, master, slave in self._samples:
            dispersions.append(_angular_deviation_deg(master, mean_master))
            dispersions.append(_angular_deviation_deg(slave, mean_slave))
        mean_dispersion = (
            sum(dispersions) / len(dispersions) if dispersions else 0.0
        )
        self._artifact = CalibrationArtifact(
            calibration_id=uuid.uuid4().hex,
            known_pose=KNOWN_POSE,
            master_xyzw=mean_master,
            slave_xyzw=mean_slave,
            captured_at_monotonic=self._samples[-1][0],
            sample_count=self._count,
            window_s=float(elapsed),
            mean_dispersion_deg=float(mean_dispersion),
        )
        self._reset_capture_buffers()
        self._state = CalibrationState.CALIBRATED
        self._reason = ""
        self._last_capture_error = ""
        return self._state


__all__ = [
    "CalibrationArtifact",
    "CalibrationController",
    "DEFAULT_CAPTURE_WINDOW_S",
    "DEFAULT_MAX_DISPERSION_DEG",
    "DEFAULT_MIN_SAMPLES",
    "KNOWN_POSE",
]
