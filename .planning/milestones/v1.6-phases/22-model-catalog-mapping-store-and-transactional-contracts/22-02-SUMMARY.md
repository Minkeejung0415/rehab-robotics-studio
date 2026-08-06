---
phase: 22-model-catalog-mapping-store-and-transactional-contracts
plan: "02"
subsystem: backend/model-catalog
tags: [opensim, ros2, model-catalog, sha256, frame-enumeration]

dependency_graph:
  requires: ["22-01"]
  provides: ["/rehab/model/catalog topic", "ModelCatalogNode", "compute_model_hash", "enumerate_compatible_frames"]
  affects: ["22-03-mapping-node", "22-04-mapping-store", "Phase 24 Studio UI"]

tech_stack:
  added: []
  patterns:
    - "Lazy opensim import via importlib.import_module (same as opensim_adapter.py)"
    - "ROS param declare-once pattern from opensim_node.py"
    - "JSON String publish pattern from fleet_bridge_node.py (sort_keys, compact separators)"
    - "SHA-256 via hashlib.sha256(Path.read_bytes()).hexdigest()"

key_files:
  created:
    - backend/rehab_robotics_bridge/model_catalog_node.py
  modified: []

decisions:
  - "enumerate_compatible_frames tries getBodySet() first (universal), then PhysicalOffsetFrame via getComponentsList() as a second pass — if getComponentsList is unavailable, body-only results are returned silently"
  - "Timer polls at 1 Hz but skips publish when opensim_model_path has not changed — avoids redundant JSON serialization and topic chatter"
  - "error_reason is always present (empty string on success) rather than null, matching fleet_bridge_node conventions"
  - "initSystem and setUseVisualizer are absent from the file to prevent the simbody-visualizer fork hazard documented in opensim_adapter.py"

metrics:
  duration_s: 134
  completed_date: "2026-08-05"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 0
---

# Phase 22 Plan 02: ModelCatalogNode SHA-256 and Frame Enumeration Summary

**One-liner:** ROS 2 node that computes SHA-256 of raw .osim bytes and enumerates non-Ground PhysicalFrames, publishing `/rehab/model/catalog` as JSON with error-reason on any failure.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement enumerate_compatible_frames and compute_model_hash | 681101d | backend/rehab_robotics_bridge/model_catalog_node.py |
| 2 | Implement ModelCatalogNode ROS node and main entrypoint | 681101d | backend/rehab_robotics_bridge/model_catalog_node.py |

Both tasks were implemented together in a single commit since the file is a single logical unit.

## What Was Built

`backend/rehab_robotics_bridge/model_catalog_node.py` (296 lines) exports:

- **`compute_model_hash(model_path: str) -> str`** — reads raw bytes, returns `hashlib.sha256(...).hexdigest()`. Raises `FileNotFoundError` for missing paths. No caching.
- **`enumerate_compatible_frames(model_path: str, opensim_module: Any) -> list[dict]`** — read-only enumeration via `getBodySet()` (Pass 1: non-Ground Bodies) and `getComponentsList()` (Pass 2: PhysicalOffsetFrame components). No setters, no system initialization, no visualizer. Returns sorted `[{segment, frame}]`. Raises `ValueError` on model load failure.
- **`ModelCatalogNode(Node)`** — declares `opensim_model_path` ROS param; polls at 1 Hz; calls `_build_and_publish_catalog()` when path changes.
- **`_build_and_publish_catalog(model_path)`** — handles all error cases: empty path, missing file, opensim unavailable, load/enumeration failure. Always publishes JSON with `error_reason`.
- **`main()`** — standard `rclpy.init / spin / destroy_node / try_shutdown` pattern.

Published JSON schema (`/rehab/model/catalog`):
```json
{
  "error_reason": "",
  "frame_list": [{"frame": "femur_r", "segment": "femur_r"}, ...],
  "model_hash": "<64-char hex>",
  "model_path": "/path/to/model.osim",
  "schema_version": "rehab.model_catalog.1"
}
```

## Verification Results

All plan verifications passed:

- `compute_model_hash`: SHA-256 hex matches expected for known content; raises `FileNotFoundError` for nonexistent path — **PASSED**
- AST structure: `ModelCatalogNode`, `main`, `enumerate_compatible_frames`, `compute_model_hash`, `_build_and_publish_catalog` all present — **PASSED**
- Topic `rehab/model/catalog` and schema `rehab.model_catalog.1` in source — **PASSED**
- `setUseVisualizer` absent from source — **PASSED**
- `initSystem` absent from source — **PASSED**
- `error_reason` field present — **PASSED**
- AST parse (`ast.parse`) — **PASSED**

## Threat Model Coverage

| Threat | Disposition | Evidence |
|--------|-------------|---------|
| T-22-02-01 Spoofing / model_hash | Mitigated | SHA-256 computed from raw bytes at read time; path validated before read |
| T-22-02-04 Tampering / model mutation | Mitigated | No setters called; no `setUseVisualizer`; no system initialization |

## Deviations from Plan

None — plan executed exactly as written.

The minor comment text adjustment (replacing "initSystem" in a docstring with "system initialization") was required to pass the plan's own verification assertion (`assert 'initSystem' not in src`), which checks the full source string including comments. This is consistent with the intent: the word must not appear anywhere in the file to avoid confusion with actual API calls.

## Known Stubs

None. The node is fully wired: path parameter read, hash computation, opensim import, frame enumeration, and JSON publish are all implemented end-to-end. Error cases publish meaningful `error_reason` values rather than silent no-ops.

## Self-Check: PASSED

- File `backend/rehab_robotics_bridge/model_catalog_node.py`: FOUND
- Commit `681101d`: FOUND in git log
