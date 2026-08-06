---
phase: 22-model-catalog-mapping-store-and-transactional-contracts
plan: "03"
subsystem: backend/mapping
tags: [mapping, persistence, ros-services, atomic-write, interlock]
dependency_graph:
  requires: ["22-01"]
  provides: ["MappingStore", "MappingNode", "mapping_node.py"]
  affects: ["/rehab/mapping/current", "/rehab/mapping/set_assignment", "/rehab/mapping/apply", "/rehab/mapping/state", "/rehab/mapping/reset"]
tech_stack:
  added: []
  patterns: ["atomic tmp+os.replace write", "threading.Lock service guard", "multi-hash assignment store", "ROS latched QoS publisher"]
key_files:
  created:
    - backend/rehab_robotics_bridge/mapping_node.py
  modified: []
decisions:
  - "MappingStore holds one active model_hash at a time; prior hash assignments archived in hash_assignments dict (D-08)"
  - "Apply interlock checks recording_active and calibration_active before any staging (D-15, T-22-03-05)"
  - "SetAssignment is NOT interlocked — draft edits allowed during active session (D-16)"
  - "Fleet registry reconnect re-attach: device already in assignments keeps state; new device registers as unassigned (D-17)"
  - "Solver sufficiency check is best-effort warning in Apply detail, not a hard block (D-20)"
  - "Latched QoS simulated via KEEP_LAST depth=1 on /rehab/mapping/current publisher"
metrics:
  duration: "~25 minutes"
  completed: "2026-08-05"
  tasks_completed: 2
  files_created: 1
  files_modified: 0
---

# Phase 22 Plan 03: MappingNode — MappingStore + ROS Services + Atomic Persistence Summary

**One-liner:** JSON-persisted device-to-frame assignment state machine with atomic write, backup/corruption recovery, four ROS services, and recording/calibration Apply interlock.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement MappingStore — persistence, atomic write, backup/corruption recovery | abd2b8b | backend/rehab_robotics_bridge/mapping_node.py |
| 2 | Implement MappingNode — ROS services, subscriptions, Apply interlock, reconnect re-attach | abd2b8b | backend/rehab_robotics_bridge/mapping_node.py |

## What Was Built

### MappingStore (pure Python, no ROS dependency)
- **Atomic persistence:** tmp file + `os.replace()` + `.bak` backup before each write
- **Corruption recovery:** `_load()` tries main file, falls back to `.bak`, then starts fresh (revision=0)
- **Multi-hash support:** `set_model_hash()` saves current assignments under old hash in `hash_assignments` dict, loads stored state for new hash
- **set_assignment validation order:**
  1. Device ID format: `esp32:<12hex>` — rejects with `invalid_device_id`
  2. State value: `assigned|not_used|unassigned` — rejects with `invalid_state`
  3. Assigned without model: rejects with `no_model`
  4. Duplicate (segment, frame): rejects with `duplicate_frame`
  5. Store, bump revision, save — returns `("ok", "")`
- **apply_candidate:** validates interlock → revision → model → completeness → duplicate → frame validity → solver sufficiency (warning only); atomic swap of `applied_revision` on success
- **reset(model_hash):** clears assignments and sets revision=0 for target hash

### MappingNode (ROS 2 node)
- **Services:** `/rehab/mapping/set_assignment`, `/rehab/mapping/apply`, `/rehab/mapping/state`, `/rehab/mapping/reset`
- **Publisher:** `/rehab/mapping/current` — String JSON, KEEP_LAST depth=1 (latched equivalent)
- **Subscriptions:**
  - `/rehab/model/catalog` → updates `model_hash` + `frame_list` via `set_model_hash()` + `set_frame_list()`
  - `/esp/fleet/registry` → auto-reattach reconnected devices (D-17); new devices added as `unassigned`
  - `/esp/recording/status` → sets `_recording_active`
  - `/rehab/calibration/status` → sets `_calibration_active`
- **Apply interlock:** checked before any staging; returns `blocked` with `recording_active` or `calibration_active` detail; does not touch store
- **Threading:** `threading.Lock` acquired by all service handlers and subscription callbacks (T-22-03-02)
- **Publish on every mutation:** `_publish_current()` called after every successful state change

## Verification Results

All three verification scripts passed:

```
AST OK
MappingStore: PASSED
MappingNode structure: PASSED
mapping_node.py: ALL CHECKS PASSED
```

## Deviations from Plan

None — plan executed exactly as written.

The two tasks were committed together (single commit `abd2b8b`) because the MappingNode class depends directly on MappingStore in the same file. Both tasks are logically atomic: the file is only complete when both classes are present.

## Known Stubs

None — all fields are wired to live store state or ROS message fields. No placeholder values flow to publishers.

## Threat Surface Scan

No new network endpoints or auth paths introduced beyond what the plan's threat model already covers. All four services are ROS-internal (no rosbridge exposure in this plan). The `GetMappingState` service (T-22-03-06) is accepted as no credentials are stored in mapping state.

## Self-Check

- [x] `backend/rehab_robotics_bridge/mapping_node.py` exists and is 685 lines
- [x] Commit `abd2b8b` exists in git log
- [x] AST parse: PASSED
- [x] MappingStore functional tests: PASSED
- [x] Structure + topic/outcome string checks: PASSED
- [x] Full verification block: ALL CHECKS PASSED

## Self-Check: PASSED
