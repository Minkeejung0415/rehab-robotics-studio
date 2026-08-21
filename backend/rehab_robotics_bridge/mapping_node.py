"""Mapping store and ROS node for device-to-frame assignment management.

Provides four ROS services:
  - /rehab/mapping/set_assignment   (SetAssignment)
  - /rehab/mapping/apply            (ApplyMapping)
  - /rehab/mapping/state            (GetMappingState)
  - /rehab/mapping/reset            (ResetMapping)

Publishes /rehab/mapping/current (String/JSON) on every state change.
Persists state atomically to ~/.ros/rehab_robotics/mapping_store.json.
"""
from __future__ import annotations

import copy
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_STORE_PATH: Path = Path.home() / ".ros" / "rehab_robotics" / "mapping_store.json"

# Mirrors ik_contracts.SOLVER_PROFILE_MIN_SENSORS — kept local to avoid circular
# import between mapping_node and opensim_node (both import from ik_contracts,
# but mapping_node must not import from opensim_node or vice versa at module level).
_SOLVER_PROFILE_MIN_SENSORS: dict[str, int] = {
    "lower_body": 2,
}

_SCHEMA_VERSION = "map.v1"
_VALID_STATES = {"assigned", "not_used", "unassigned"}
_DEVICE_ID_RE = re.compile(r"^esp32:[0-9a-f]{12}$")

MAPPING_CATALOG_TOPIC = "/rehab/model/catalog"
MAPPING_CURRENT_TOPIC = "/rehab/mapping/current"
FLEET_REGISTRY_TOPIC = "/esp/fleet/registry"
RECORDING_STATUS_TOPIC = "/esp/recording/status"
CALIBRATION_STATUS_TOPIC = "/rehab/calibration/status"


# ---------------------------------------------------------------------------
# MappingStore — pure Python, no ROS dependency
# ---------------------------------------------------------------------------

class MappingStore:
    """Persistent mapping state: device_id -> {segment, frame, state}.

    Atomic write via tmp file + os.replace(). Corruption recovery from .bak.
    Supports multiple model hashes via internal hash_assignments table.
    """

    def __init__(self, store_path: Path = DEFAULT_STORE_PATH) -> None:
        self._path = Path(store_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # In-memory frame_list from catalog (not persisted)
        self._frame_list: list[dict[str, str]] = []
        self._data: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # Internal load / save
    # ------------------------------------------------------------------

    def _fresh_data(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "model_hash": "",
            "revision": 0,
            "assignments": {},
            "applied_revision": 0,
            # Immutable snapshot used by the runtime/3D solver.  Editable
            # assignments are deliberately separate so a saved-but-not-applied
            # UI selection can never move a body segment early.
            "applied_assignments": {},
            "backup_revision": 0,
            "hash_assignments": {},
        }

    def _parse_file(self, path: Path) -> dict[str, Any] | None:
        """Return parsed JSON dict if valid map.v1, else None."""
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None
            if data.get("schema_version") != _SCHEMA_VERSION:
                return None
            return data
        except Exception:
            return None

    def _load(self) -> None:
        data = self._parse_file(self._path)
        if data is None:
            bak = self._path.with_suffix(".bak")
            data = self._parse_file(bak)
        if data is None:
            self._data = self._fresh_data()
        else:
            self._data = data
            # Ensure all expected keys exist (forward compatibility)
            for key, default in self._fresh_data().items():
                if key not in self._data:
                    self._data[key] = default

    def _save(self) -> None:
        """Atomic write: backup existing, then write via tmp + os.replace."""
        serialised = json.dumps(self._data, sort_keys=True, indent=2)
        tmp = self._path.with_suffix(".tmp")
        # Backup current main file before overwriting
        if self._path.exists():
            bak = self._path.with_suffix(".bak")
            try:
                import shutil
                shutil.copy2(str(self._path), str(bak))
            except Exception:
                pass
        tmp.write_text(serialised, encoding="utf-8")
        tmp.replace(self._path)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def revision(self) -> int:
        return int(self._data.get("revision", 0))

    @property
    def applied_revision(self) -> int:
        return int(self._data.get("applied_revision", 0))

    @property
    def model_hash(self) -> str:
        return str(self._data.get("model_hash", ""))

    @property
    def assignments(self) -> dict[str, dict[str, str]]:
        return self._data.get("assignments", {})

    @property
    def frame_list(self) -> list[dict[str, str]]:
        return self._frame_list

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def set_frame_list(self, frame_list: list[dict[str, str]]) -> None:
        """Update in-memory frame list from model catalog. Not persisted."""
        self._frame_list = list(frame_list)

    def set_model_hash(self, new_hash: str) -> None:
        """Switch to a different model hash.

        Saves current assignments under the old hash, then loads stored
        assignments for new_hash (or starts fresh). Does NOT call _save();
        that happens at the next set_assignment or apply call.
        """
        current_hash = self._data.get("model_hash", "")
        if new_hash == current_hash:
            return

        # Persist current assignments under old hash
        hash_assignments: dict[str, Any] = self._data.get("hash_assignments", {})
        if current_hash:
            hash_assignments[current_hash] = {
                "assignments": copy.deepcopy(self._data.get("assignments", {})),
                "revision": self._data.get("revision", 0),
                "applied_revision": self._data.get("applied_revision", 0),
                "applied_assignments": copy.deepcopy(
                    self._data.get("applied_assignments", {})
                ),
            }

        # Load stored state for new_hash, or start fresh
        stored = hash_assignments.get(new_hash, {})
        self._data["model_hash"] = new_hash
        self._data["assignments"] = copy.deepcopy(stored.get("assignments", {}))
        self._data["revision"] = stored.get("revision", 0)
        self._data["applied_revision"] = stored.get("applied_revision", 0)
        self._data["applied_assignments"] = copy.deepcopy(
            stored.get("applied_assignments", {})
        )
        self._data["hash_assignments"] = hash_assignments
        # Note: _save() not called here — deferred to next mutation

    def set_assignment(
        self,
        device_id: str,
        segment: str,
        frame: str,
        state: str,
    ) -> tuple[str, str]:
        """Assign a device to a segment/frame.

        Returns (outcome, detail).
        Outcomes: "ok", "invalid_device_id", "invalid_state", "no_model", "duplicate_frame".
        """
        # Rule 1: validate device_id format
        if not _DEVICE_ID_RE.match(device_id):
            return ("invalid_device_id", "device_id must be esp32:<12hex>")

        # Rule 2: validate state value
        if state not in _VALID_STATES:
            return ("invalid_state", "state must be assigned|not_used|unassigned")

        # Rule 3: assigned state requires a loaded model
        if state == "assigned" and not self._data.get("model_hash", ""):
            return ("no_model", "no model loaded")

        # Rule 4: check duplicate (segment, frame) among other devices
        if state == "assigned":
            for other_id, entry in self._data["assignments"].items():
                if other_id == device_id:
                    continue
                if (
                    entry.get("state") == "assigned"
                    and entry.get("segment") == segment
                    and entry.get("frame") == frame
                ):
                    return (
                        "duplicate_frame",
                        f"frame {frame} on segment {segment} already assigned to {other_id}",
                    )

        # Store assignment
        self._data["assignments"][device_id] = {
            "segment": segment,
            "frame": frame,
            "state": state,
        }
        self._data["revision"] = self._data.get("revision", 0) + 1
        self._save()
        return ("ok", "")

    def apply_candidate(
        self,
        expected_revision: int,
        frame_list: list[dict[str, str]],
        interlock_active: bool = False,
        interlock_reason: str = "",
    ) -> dict[str, Any]:
        """Validate and atomically apply the current draft mapping.

        Returns dict with keys: outcome, applied_revision, detail.
        Outcomes: "applied", "blocked", "revision_mismatch", "model_changed",
                  "incomplete", "duplicate_frame", "invalid_frame".
        """
        # Interlock check FIRST (D-15: before any staging/reads)
        if interlock_active:
            return {
                "outcome": "blocked",
                "applied_revision": self.applied_revision,
                "detail": interlock_reason or "interlock_active",
            }

        # Revision mismatch (D-14: before staging)
        if self._data.get("revision", 0) != expected_revision:
            return {
                "outcome": "revision_mismatch",
                "applied_revision": self.applied_revision,
                "detail": (
                    f"stored_revision={self._data.get('revision',0)} "
                    f"expected={expected_revision}"
                ),
            }

        # Model hash check
        if not self._data.get("model_hash", ""):
            return {
                "outcome": "model_changed",
                "applied_revision": self.applied_revision,
                "detail": "no_model_loaded",
            }

        assignments = self._data.get("assignments", {})

        # Completeness: all devices must have assigned or not_used
        incomplete_ids = [
            did for did, entry in assignments.items()
            if entry.get("state") == "unassigned"
        ]
        if incomplete_ids:
            return {
                "outcome": "incomplete",
                "applied_revision": self.applied_revision,
                "detail": f"unassigned_devices={','.join(sorted(incomplete_ids))}",
            }

        # Duplicate frame check among assigned devices
        seen_frames: dict[tuple[str, str], str] = {}
        for did, entry in assignments.items():
            if entry.get("state") != "assigned":
                continue
            key = (entry.get("segment", ""), entry.get("frame", ""))
            if key in seen_frames:
                return {
                    "outcome": "duplicate_frame",
                    "applied_revision": self.applied_revision,
                    "detail": (
                        f"frame {key[1]} on segment {key[0]} assigned to both "
                        f"{seen_frames[key]} and {did}"
                    ),
                }
            seen_frames[key] = did

        # Frame validity check against provided frame_list
        valid_frames: set[tuple[str, str]] = {
            (f.get("segment", ""), f.get("frame", ""))
            for f in frame_list
        }
        for did, entry in assignments.items():
            if entry.get("state") != "assigned":
                continue
            key = (entry.get("segment", ""), entry.get("frame", ""))
            if key not in valid_frames:
                return {
                    "outcome": "invalid_frame",
                    "applied_revision": self.applied_revision,
                    "detail": (
                        f"frame {key[1]} on segment {key[0]} not in current frame_list"
                    ),
                }

        # Solver sufficiency hard-block (D-12, IK-04): upgraded from soft warning.
        # Returns solver_insufficient BEFORE atomic swap when assigned device count
        # is below the minimum for the current solver profile.
        assigned_devices = [
            did for did, entry in assignments.items()
            if entry.get("state") == "assigned"
        ]
        solver_profile = self._data.get("solver_profile", "lower_body")
        min_sensors = _SOLVER_PROFILE_MIN_SENSORS.get(solver_profile, 2)
        if len(assigned_devices) < min_sensors:
            return {
                "outcome": "solver_insufficient",
                "applied_revision": self.applied_revision,
                "detail": (
                    f"need_{min_sensors}_assigned_got_{len(assigned_devices)}"
                ),
            }

        # Atomic swap: persist the exact assignment snapshot the runtime must
        # consume.  `revision` alone cannot prove which mapping was applied:
        # a later editable save may have the same displayed revision in a
        # delayed browser update while the solver must retain the old mapping.
        self._data["applied_revision"] = self._data.get("revision", 0)
        self._data["applied_assignments"] = copy.deepcopy(assignments)
        self._save()

        return {
            "outcome": "applied",
            "applied_revision": self.applied_revision,
            "detail": "",
        }

    def reset(self, model_hash: str) -> str:
        """Reset assignments for the given model_hash.

        If model_hash differs from current, switches to it and clears.
        If model_hash matches current, clears draft assignments.
        """
        target_hash = model_hash or self._data.get("model_hash", "")
        if target_hash != self._data.get("model_hash", ""):
            # Switching hash — save current state first
            current_hash = self._data.get("model_hash", "")
            hash_assignments: dict[str, Any] = self._data.get("hash_assignments", {})
            if current_hash:
                hash_assignments[current_hash] = {
                    "assignments": copy.deepcopy(self._data.get("assignments", {})),
                    "revision": self._data.get("revision", 0),
                    "applied_revision": self._data.get("applied_revision", 0),
                    "applied_assignments": copy.deepcopy(
                        self._data.get("applied_assignments", {})
                    ),
                }
            self._data["hash_assignments"] = hash_assignments
            self._data["model_hash"] = target_hash

        self._data["assignments"] = {}
        self._data["revision"] = 0
        self._data["applied_revision"] = 0
        self._data["applied_assignments"] = {}
        self._save()
        return "ok"

    def get_state_dict(self) -> dict[str, Any]:
        """Return the full in-memory state for JSON serialisation."""
        return {
            "schema_version": self._data.get("schema_version", _SCHEMA_VERSION),
            "model_hash": self._data.get("model_hash", ""),
            "revision": self._data.get("revision", 0),
            "assignments": copy.deepcopy(self._data.get("assignments", {})),
            "applied_revision": self._data.get("applied_revision", 0),
            # The browser consumes one atomic current-state contract. Keep the
            # applied snapshot alongside the editable draft so it can never
            # relabel a 3D/IK runtime mapping with an unsaved selection.
            "applied_assignments": copy.deepcopy(
                self._data.get("applied_assignments", {})
            ),
            "backup_revision": self._data.get("backup_revision", 0),
        }


# ---------------------------------------------------------------------------
# ROS 2 imports (after MappingStore — no ROS dep in store)
# ---------------------------------------------------------------------------

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
from rehab_robotics_interfaces.srv import (
    ApplyMapping,
    GetMappingState,
    ResetMapping,
    SetAssignment,
)

_MAPPING_CURRENT_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    reliability=ReliabilityPolicy.RELIABLE,
)


# ---------------------------------------------------------------------------
# MappingNode — ROS 2 node
# ---------------------------------------------------------------------------

class MappingNode(Node):
    """Authoritative mapping state machine exposing four ROS services.

    Services:
      /rehab/mapping/set_assignment — SetAssignment
      /rehab/mapping/apply          — ApplyMapping
      /rehab/mapping/state          — GetMappingState
      /rehab/mapping/reset          — ResetMapping

    Publications:
      /rehab/mapping/current        — String (JSON), latched QoS depth=1

    Subscriptions:
      /rehab/model/catalog          — String (JSON): frame_list + model_hash
      /esp/fleet/registry           — String (JSON): fleet device events
      /esp/recording/status         — String (JSON): recording interlock
      /rehab/calibration/status     — String (JSON): calibration interlock
    """

    def __init__(self) -> None:
        super().__init__("mapping_node")

        # Parameter: override store path (empty = default)
        store_path_param = self.declare_parameter("store_path", "").value
        store_path = (
            Path(store_path_param) if store_path_param else DEFAULT_STORE_PATH
        )

        self._store = MappingStore(store_path)
        self._recording_active: bool = False
        self._calibration_active: bool = False
        self._lock = threading.Lock()

        # Retained state lets a GUI that starts after ROS immediately render the
        # saved assignments instead of waiting for the next mapping mutation.
        self._current_publisher = self.create_publisher(
            String,
            MAPPING_CURRENT_TOPIC,
            _MAPPING_CURRENT_QOS,
        )

        # Subscriptions
        self._catalog_sub = self.create_subscription(
            String,
            MAPPING_CATALOG_TOPIC,
            self._on_catalog,
            10,
        )
        self._fleet_sub = self.create_subscription(
            String,
            FLEET_REGISTRY_TOPIC,
            self._on_fleet_registry,
            10,
        )
        self._recording_sub = self.create_subscription(
            String,
            RECORDING_STATUS_TOPIC,
            self._on_recording_status,
            10,
        )
        self._calibration_sub = self.create_subscription(
            String,
            CALIBRATION_STATUS_TOPIC,
            self._on_calibration_status,
            10,
        )

        # Services
        self._set_assignment_srv = self.create_service(
            SetAssignment,
            "/rehab/mapping/set_assignment",
            self._on_set_assignment,
        )
        self._apply_srv = self.create_service(
            ApplyMapping,
            "/rehab/mapping/apply",
            self._on_apply_mapping,
        )
        self._state_srv = self.create_service(
            GetMappingState,
            "/rehab/mapping/state",
            self._on_get_mapping_state,
        )
        self._reset_srv = self.create_service(
            ResetMapping,
            "/rehab/mapping/reset",
            self._on_reset_mapping,
        )

        # Publish initial state
        self._publish_current()
        # rosbridge creates volatile subscriptions for browser clients. Replaying
        # the compact state makes a newly opened GUI deterministic even when it
        # joined after the retained ROS publication.
        self._state_timer = self.create_timer(1.0, self._publish_current)
        self.get_logger().info(
            f"MappingNode started — store={store_path} "
            f"model_hash={self._store.model_hash!r} "
            f"revision={self._store.revision}"
        )

    # ------------------------------------------------------------------
    # Subscription callbacks
    # ------------------------------------------------------------------

    def _on_catalog(self, msg: String) -> None:
        """Handle /rehab/model/catalog — update model_hash and frame_list."""
        try:
            data = json.loads(msg.data)
        except Exception:
            self.get_logger().warning("mapping_node: failed to parse catalog JSON")
            return
        model_hash = str(data.get("model_hash", ""))
        frame_list = data.get("frame_list", [])
        if not isinstance(frame_list, list):
            frame_list = []
        with self._lock:
            self._store.set_model_hash(model_hash)
            self._store.set_frame_list(frame_list)
            self._publish_current()

    def _on_fleet_registry(self, msg: String) -> None:
        """Handle /esp/fleet/registry — auto-reattach reconnected devices (D-17)."""
        try:
            data = json.loads(msg.data)
        except Exception:
            self.get_logger().warning("mapping_node: failed to parse fleet_registry JSON")
            return

        devices = data.get("devices", [])
        if not isinstance(devices, list):
            return

        changed = False
        with self._lock:
            for device in devices:
                if not isinstance(device, dict):
                    continue
                # Accept devices that are connected (various field names)
                route_state = device.get("route_state") or device.get("route", "")
                is_connected = route_state == "connected"
                if not is_connected:
                    continue

                device_id = device.get("device_id", "")
                if not device_id:
                    continue

                assignments = self._store.assignments
                if device_id in assignments:
                    # D-17: device already in mapping — state stays (auto-reattach if assigned)
                    pass
                else:
                    # New device: register as unassigned (draft only, do not persist here)
                    assignments[device_id] = {
                        "segment": "",
                        "frame": "",
                        "state": "unassigned",
                    }
                    changed = True

            if changed:
                self._publish_current()

    def _on_recording_status(self, msg: String) -> None:
        """Track recording interlock state."""
        try:
            data = json.loads(msg.data)
            active = bool(data.get("active", False))
            if not active:
                # Also check state field
                state_field = str(data.get("state", ""))
                active = state_field in {"recording", "active"}
            self._recording_active = active
        except Exception:
            self._recording_active = False

    def _on_calibration_status(self, msg: String) -> None:
        """Track calibration interlock state."""
        try:
            data = json.loads(msg.data)
            active = bool(data.get("active", False))
            if not active:
                state_field = str(data.get("state", ""))
                active = state_field in {"capturing", "active"}
            self._calibration_active = active
        except Exception:
            self._calibration_active = False

    # ------------------------------------------------------------------
    # Service handlers
    # ------------------------------------------------------------------

    def _on_set_assignment(
        self,
        request: SetAssignment.Request,
        response: SetAssignment.Response,
    ) -> SetAssignment.Response:
        """SetAssignment — not blocked during recording/calibration (D-16)."""
        with self._lock:
            outcome, detail = self._store.set_assignment(
                request.device_id,
                request.segment,
                request.frame,
                request.state,
            )
            response.outcome = outcome
            response.detail = detail
            self._publish_current()
        return response

    def _on_apply_mapping(
        self,
        request: ApplyMapping.Request,
        response: ApplyMapping.Response,
    ) -> ApplyMapping.Response:
        """ApplyMapping — blocked during recording or calibration (D-15)."""
        with self._lock:
            # Build interlock state
            interlock_active = self._recording_active or self._calibration_active
            if self._recording_active:
                interlock_reason = "recording_active"
            elif self._calibration_active:
                interlock_reason = "calibration_active"
            else:
                interlock_reason = ""

            result = self._store.apply_candidate(
                expected_revision=int(request.expected_revision),
                frame_list=self._store.frame_list,
                interlock_active=interlock_active,
                interlock_reason=interlock_reason,
            )

            response.outcome = result["outcome"]
            response.applied_revision = int(result["applied_revision"])
            response.detail = str(result.get("detail", ""))

            if result["outcome"] == "applied":
                self._publish_current()

        return response

    def _on_get_mapping_state(
        self,
        request: GetMappingState.Request,
        response: GetMappingState.Response,
    ) -> GetMappingState.Response:
        """GetMappingState — return full state as JSON string."""
        with self._lock:
            state_dict = self._store.get_state_dict()
        response.state_json = json.dumps(state_dict, sort_keys=True, separators=(",", ":"))
        return response

    def _on_reset_mapping(
        self,
        request: ResetMapping.Request,
        response: ResetMapping.Response,
    ) -> ResetMapping.Response:
        """ResetMapping — clear assignments for the given model_hash."""
        with self._lock:
            outcome = self._store.reset(request.model_hash)
            response.outcome = outcome
            self._publish_current()
        return response

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_current(self) -> None:
        """Publish /rehab/mapping/current with full state JSON."""
        state_dict = self._store.get_state_dict()
        state_dict["schema"] = "rehab.mapping_current.1"
        msg = String()
        msg.data = json.dumps(state_dict, sort_keys=True, separators=(",", ":"))
        self._current_publisher.publish(msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(args=None) -> None:
    rclpy.init(args=args)
    node = MappingNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
