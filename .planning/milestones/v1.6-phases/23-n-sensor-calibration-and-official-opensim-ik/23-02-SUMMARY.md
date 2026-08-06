---
phase: 23-n-sensor-calibration-and-official-opensim-ik
plan: "02"
subsystem: opensim-ik
tags: [tdd, ik, calibration, artifact, atomic-write]
dependency_graph:
  requires:
    - _DeviceInput dataclass in opensim_node (Plan 23-01)
    - _mac_inputs dict + _input_lock (Plan 23-01)
    - _on_mapping_current / _on_mac_imu callbacks (Plan 23-01)
  provides:
    - CalibrationArtifactStore in n_sensor_calibration.py
    - _n_calib_artifact, _n_calib_state in OpenSimBridgeNode
    - /rehab/calibration/capture Trigger service
    - /rehab/calibration/status publisher (rehab.n_calibration_status.1)
    - _check_artifact_validity invalidation on mapping change
    - IK-02 contract tests (A-I)
  affects:
    - backend/rehab_robotics_bridge/opensim/n_sensor_calibration.py
    - backend/rehab_robotics_bridge/opensim_node.py
    - backend/test/test_n_sensor_calibration.py
    - backend/test/test_opensim_node.py
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN cycle for pure-Python store and ROS node integration
    - Atomic write via Path.replace (tmp + rename)
    - threading.Lock snapshot of _mac_inputs before reads (T-23-02-03)
    - Schema-validated load (returns None for wrong version/corrupt JSON)
    - Set-based device-order comparison in is_valid()
    - timezone-aware datetime.now(UTC) for calibrated_at_iso8601
key_files:
  created:
    - backend/rehab_robotics_bridge/opensim/n_sensor_calibration.py
    - backend/test/test_n_sensor_calibration.py
  modified:
    - backend/rehab_robotics_bridge/opensim_node.py
    - backend/test/test_opensim_node.py
decisions:
  - Atomic write uses Path.replace (not os.replace) — identical semantics, more Pythonic
  - calibrated_at_iso8601 uses datetime.now(timezone.utc) instead of deprecated utcnow()
  - _mac_inputs snapshot taken under _input_lock before IMU presence check (TOCTOU protection)
  - is_valid() uses set comparison — order-independent and handles duplicates
  - _n_model_hash extracted from mapping JSON model_hash field (empty string if absent)
  - _publish_n_calibration_status called on every timer tick and on state transitions
metrics:
  duration: ~20 minutes
  completed: "2026-08-05"
  tasks_completed: 3
  files_modified: 2
  files_created: 2
---

# Phase 23 Plan 02: CalibrationArtifactStore + capture service + N-sensor calib status Summary

CalibrationArtifactStore (pure Python, no ROS) with atomic save/load/is_valid wired into OpenSimBridgeNode as the N-sensor calibration capture service with status publishing and D-05 invalidation on mapping change.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| Task 1 RED | CalibrationArtifactStore failing tests (test_n_sensor_calibration.py) | dd81b00 |
| Task 1 GREEN | n_sensor_calibration.py with compute_artifact_path/save/load/is_valid | 6861c32 |
| Task 2+3 RED | IK-02 node integration tests (IkTwoNodeTests) | 6b6ba0f |
| Task 2+3 GREEN | Wire CalibrationArtifactStore into OpenSimBridgeNode | 6d3d478 |

## What Was Built

### CalibrationArtifactStore (Task 1)

Created `backend/rehab_robotics_bridge/opensim/n_sensor_calibration.py`:

- **`compute_artifact_path(model_hash, applied_revision)`**: Returns `~/.ros/rehab_robotics/calibration_{hash8}_rev{N}.json` where `hash8 = model_hash[:8]`.
- **`save(artifact_path, data)`**: Atomic write via `tmp.write_text() + tmp.replace(artifact_path)`. Creates parent directories. No `.tmp` left behind.
- **`load(artifact_path)`**: Returns `dict` if file exists and `schema_version == "calib.v1"`. Returns `None` for: missing file, corrupt JSON, wrong schema_version, non-dict JSON.
- **`is_valid(artifact, model_hash, revision, device_order)`**: Returns `True` only when all three identity fields match. Device comparison is set-based (order-independent).
- `__all__ = ["CalibrationArtifactStore"]`

### Node Wiring (Task 2)

Added to `opensim_node.py`:

- `import datetime` and `from .opensim.n_sensor_calibration import CalibrationArtifactStore`
- `__init__`: `_n_calib_artifact = None`, `_n_calib_state = "uncalibrated"`, `_n_calib_store`, `_n_model_hash = ""`
- `__init__`: `/rehab/calibration/capture` Trigger service and `/rehab/calibration/status` publisher
- **`_on_calibration_capture_n`**: Snapshots `_mac_inputs` under `_input_lock` (T-23-02-03), returns JSON outcomes: `no_mapping` (empty inputs), `missing_inputs` (any device has `last_xyzw=None`), `captured` (success with `artifact_path`). Builds `calib.v1` artifact with sorted `device_order` and `{qw,qx,qy,qz}` reference pose.
- **`_check_artifact_validity`**: Called from `_on_mapping_current` after every update. Invalidates artifact (sets state to `uncalibrated`, clears artifact) when `is_valid()` returns `False`.
- **`_publish_n_calibration_status`**: Publishes `{"schema":"rehab.n_calibration_status.1","state":...,"revision":...,"model_hash":...}` plus `"schema_version":"calib.v1"` when calibrated.
- `_on_mapping_current`: Now also extracts `model_hash` from JSON and calls `_check_artifact_validity()`.
- `_on_status_timer`: Now calls `_publish_n_calibration_status()` on each tick.

### IK-02 Contract Tests (Task 3)

In `test_n_sensor_calibration.py`:
- `CalibrationArtifactStoreBasicTests`: 15 tests covering path computation, save+load, atomic write, all `load()` error cases, all `is_valid()` branches.
- `IkTwoArtifactTests`: IK-02-A (round-trip), IK-02-B (model_hash mismatch), IK-02-C (revision mismatch), IK-02-D (device set change), IK-02-E (corrupt/wrong schema/missing), IK-02-I (hash8+revision in filename).

In `test_opensim_node.py` (added `IkTwoNodeTests`):
- IK-02-F: Capture with all inputs sets `_n_calib_state="calibrated"`
- IK-02-G: Remap with changed devices invalidates artifact
- IK-02-H: Remap with same devices preserves valid artifact
- Plus: initial state, service/publisher existence, no_mapping outcome, missing_inputs outcome, artifact schema validation, reference_pose qw/qx/qy/qz format, status JSON schema.

## Test Results

```
test/test_n_sensor_calibration.py    24 passed
test/test_opensim_node.py            53 passed (41 original + 12 IK-02)
test/test_opensim_orientation_ik_n.py  10 passed, 2 skipped (OpenSim not installed)
test/test_opensim_orientation_ik_opensim.py  3 passed, 3 skipped
Total: 90 passed, 5 skipped
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed deprecated datetime.utcnow() usage**
- **Found during:** Task 2 GREEN — Python 3.12 emits DeprecationWarning for `datetime.datetime.utcnow()`
- **Issue:** The plan spec used `datetime.datetime.utcnow().isoformat() + "Z"` which is deprecated in Python 3.12
- **Fix:** Used `datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")` — produces identical output format, no deprecation warning
- **Files modified:** `backend/rehab_robotics_bridge/opensim_node.py`

**2. [Rule 2 - Auto-add] Used Path.replace() instead of os.replace()**
- The plan spec listed `os.replace(str(tmp), str(path))` for the atomic write. Used `tmp.replace(artifact_path)` (Path method) instead — identical semantics, more Pythonic, avoids string conversion.

## Known Stubs

None. All fields in captured artifacts are populated from live IMU data or mapping metadata.

## Threat Flags

No new trust boundaries beyond the plan's threat model. All four mitigations implemented:
- T-23-02-03: `_mac_inputs` snapshotted under `_input_lock` before reads
- T-23-02-04: `load()` returns `None` for invalid JSON or wrong `schema_version`

## Self-Check: PASSED

Files exist:
- `backend/rehab_robotics_bridge/opensim/n_sensor_calibration.py` FOUND
- `backend/test/test_n_sensor_calibration.py` FOUND
- `backend/rehab_robotics_bridge/opensim_node.py` FOUND (contains _n_calib_state, _on_calibration_capture_n)
- `backend/test/test_opensim_node.py` FOUND (contains IkTwoNodeTests)

Commits exist:
- dd81b00 test(23-02/red): IK-02 calibration artifact contract tests (failing)
- 6861c32 feat(23-02/green): CalibrationArtifactStore — atomic save/load/is_valid
- 6b6ba0f test(23-02/red): IK-02 node integration tests (failing)
- 6d3d478 feat(23-02/green): CalibrationArtifactStore + capture service + N-sensor calib status
