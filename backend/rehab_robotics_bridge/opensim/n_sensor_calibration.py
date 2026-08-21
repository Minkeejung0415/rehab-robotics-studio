"""Calibration artifact store for N-sensor IK (IK-02).

Pure Python — no ROS dependency. Handles atomic file writes,
schema-validated loads, and artifact validity checks tied to
model_hash, applied_revision, and device assignment identity.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

__all__ = ["CalibrationArtifactStore", "apply_reference_pose_offsets"]

_SCHEMA_VERSION = "calib.v1"


def _unit_xyzw(values: object) -> tuple[float, float, float, float]:
    """Validate and normalize one persisted ROS quaternion."""

    if not isinstance(values, (list, tuple)) or len(values) != 4:
        raise ValueError("calibration_reference_quaternion_invalid")
    x, y, z, w = (float(value) for value in values)
    norm = math.hypot(x, y, z, w)
    if not math.isfinite(norm) or norm < 1e-12:
        raise ValueError("calibration_reference_quaternion_invalid")
    return (x / norm, y / norm, z / norm, w / norm)


def _multiply_xyzw(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Hamilton product for ROS-order quaternions."""

    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return (
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    )


def apply_reference_pose_offsets(
    inputs: list[tuple[str, object]],
    artifact: dict,
) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Express mapped IMU orientations relative to their captured pose.

    At capture q_current == q_reference, so the corrected orientation is the
    identity quaternion.  This is the N-sensor equivalent of the legacy
    OpenSense mounting-offset correction and makes the standing capture pose
    neutral for the model solver.
    """

    if not isinstance(artifact, dict):
        raise ValueError("calibration_artifact_invalid")
    references = artifact.get("reference_pose")
    assignments = artifact.get("frame_assignments")
    if not isinstance(references, dict) or not isinstance(assignments, dict):
        raise ValueError("calibration_reference_missing")

    reference_by_frame: dict[str, tuple[float, float, float, float]] = {}
    for device_id, assignment in assignments.items():
        if not isinstance(device_id, str) or not isinstance(assignment, dict):
            continue
        frame = assignment.get("frame")
        reference = references.get(device_id)
        if not isinstance(frame, str) or not isinstance(reference, dict):
            continue
        try:
            reference_by_frame[frame] = _unit_xyzw((
                reference.get("qx"), reference.get("qy"),
                reference.get("qz"), reference.get("qw"),
            ))
        except (TypeError, ValueError):
            raise ValueError("calibration_reference_quaternion_invalid") from None

    corrected: list[tuple[str, tuple[float, float, float, float]]] = []
    for frame, raw in inputs:
        current = _unit_xyzw(raw)
        reference = reference_by_frame.get(str(frame))
        if reference is None:
            raise ValueError(f"calibration_reference_missing:{frame}")
        rx, ry, rz, rw = reference
        corrected.append((str(frame), _multiply_xyzw(current, (-rx, -ry, -rz, rw))))
    return corrected


class CalibrationArtifactStore:
    """Stateless utility class for calibration artifact file operations.

    All methods are instance methods for testability/injection but carry
    no state — a single shared instance is sufficient in production.
    """

    # ------------------------------------------------------------------
    # Path computation
    # ------------------------------------------------------------------

    def compute_artifact_path(self, model_hash: str, applied_revision: int) -> Path:
        """Return the canonical filesystem path for a calibration artifact.

        File pattern: ~/.ros/rehab_robotics/calibration_{hash8}_rev{N}.json
        where hash8 = first 8 characters of model_hash.
        """
        base = Path.home() / ".ros" / "rehab_robotics"
        hash8 = str(model_hash)[:8]
        filename = f"calibration_{hash8}_rev{applied_revision}.json"
        return base / filename

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, artifact_path: Path, data: dict) -> None:
        """Atomically write *data* as JSON to *artifact_path*.

        Uses the tmp-then-os.replace pattern to prevent partial-write
        corruption (T-23-02-04 mitigation).

        Args:
            artifact_path: Destination file path.
            data: Dict to serialise as JSON (sort_keys=True, indent=2).
        """
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        serialised = json.dumps(data, sort_keys=True, indent=2)
        tmp = artifact_path.with_suffix(".tmp")
        tmp.write_text(serialised, encoding="utf-8")
        tmp.replace(artifact_path)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load(self, artifact_path: Path) -> dict | None:
        """Load and validate a calibration artifact from disk.

        Returns the artifact dict if the file exists and has
        schema_version == 'calib.v1'. Returns None for:
        - missing file
        - corrupt / non-JSON content
        - wrong schema_version
        - non-dict JSON value

        This implements the T-23-02-04 tamper-resistance: an attacker
        who modifies the file on disk will produce a schema mismatch or
        corrupt JSON, keeping calibration state as 'uncalibrated'.
        """
        try:
            text = artifact_path.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, dict):
                return None
            if data.get("schema_version") != _SCHEMA_VERSION:
                return None
            return data
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Validity check
    # ------------------------------------------------------------------

    def is_valid(
        self,
        artifact: dict | None,
        current_model_hash: str,
        current_applied_revision: int,
        current_device_order: list[str],
    ) -> bool:
        """Return True only if artifact matches the current mapping identity.

        Invalidation triggers (D-05):
        - artifact is None
        - artifact["model_hash"] != current_model_hash
        - artifact["applied_revision"] != current_applied_revision
        - set(artifact["device_order"]) != set(current_device_order)

        Device-order comparison is order-independent (set equality).
        """
        if artifact is None:
            return False
        if artifact.get("model_hash") != current_model_hash:
            return False
        if int(artifact.get("applied_revision", -1)) != current_applied_revision:
            return False
        stored_devices = set(artifact.get("device_order", []))
        current_devices = set(current_device_order)
        return stored_devices == current_devices
