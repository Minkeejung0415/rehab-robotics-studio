"""Calibration artifact store for N-sensor IK (IK-02).

Pure Python — no ROS dependency. Handles atomic file writes,
schema-validated loads, and artifact validity checks tied to
model_hash, applied_revision, and device assignment identity.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

__all__ = ["CalibrationArtifactStore"]

_SCHEMA_VERSION = "calib.v1"


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
