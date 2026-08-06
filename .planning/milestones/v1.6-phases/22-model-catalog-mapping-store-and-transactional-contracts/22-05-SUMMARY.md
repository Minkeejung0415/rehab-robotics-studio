---
phase: 22-model-catalog-mapping-store-and-transactional-contracts
plan: "05"
subsystem: backend/mapping
tags: [testing, mapping, offline-tests, MAP-01, MAP-02, MAP-03, MAP-04, MAP-05, MAP-06]

dependency_graph:
  requires: ["22-03"]
  provides: ["offline regression suite for MappingStore and MappingNode"]
  affects: []

tech_stack:
  added: []
  patterns:
    - "_StubNode inheriting from object used as rclpy.node.Node stub (set in sys.modules before module exec)"
    - "importlib.util.spec_from_file_location for isolated module load"
    - "tempfile.TemporaryDirectory for store_path isolation"

key_files:
  created:
    - backend/test/test_mapping_node.py
  modified: []

decisions:
  - "Set rclpy.node.Node = _StubNode via sys.modules[] assignment (not setdefault) before module exec so MappingNode inherits _StubNode in its MRO — avoids object.__init__ TypeError on super().__init__('mapping_node')"
  - "36 tests across 4 test classes covers all MAP-01 through MAP-06 contracts"
  - "test_apply_invalid_frame directly mutates store._data to bypass set_assignment frame validation (which does not validate frames against frame_list at assignment time)"

metrics:
  duration: "12 minutes"
  completed: "2026-08-05T18:39:46Z"
  tasks_completed: 2
  files_created: 1
  files_modified: 0
  tests_run: 36
  tests_passed: 36
  tests_failed: 0
---

# Phase 22 Plan 05: Offline Tests for MappingNode (MAP-01 through MAP-06) Summary

**One-liner:** 36-test offline suite covering all MappingStore and MappingNode contracts — persistence, apply transaction, interlock, reconnect re-attach, and publish-on-change.

## What Was Built

Created `backend/test/test_mapping_node.py` with four test classes:

### MappingStoreTest (22 tests — pure persistence layer, no ROS)
- `test_initial_state_is_empty` — MAP-01: revision==0, applied_revision==0, assignments=={}
- `test_set_assignment_assigned_ok` — MAP-01: assigned state accepted with valid frame
- `test_set_assignment_not_used_ok` — MAP-01: not_used state accepted
- `test_set_assignment_unassigned_ok` — MAP-01: unassigned state accepted
- `test_set_assignment_invalid_state_rejected` — MAP-01: unknown state returns invalid_state
- `test_set_assignment_invalid_device_id_rejected_bare_string` — MAP-01: non-esp32 prefix rejected
- `test_set_assignment_invalid_device_id_rejected_too_short` — MAP-01: < 12 hex chars rejected
- `test_set_assignment_invalid_device_id_rejected_uppercase` — MAP-01: uppercase hex rejected
- `test_set_assignment_invalid_device_id_rejected_wrong_prefix` — MAP-01: wrong prefix rejected
- `test_set_assignment_duplicate_frame_rejected` — MAP-01: duplicate (segment, frame) returns duplicate_frame
- `test_revision_increments_on_each_set_assignment` — MAP-02: monotonic revision counter
- `test_persistence_across_instantiation` — MAP-03: assignments survive MappingStore reload
- `test_backup_on_save` — MAP-03: .bak file present after second save
- `test_corruption_recovery_fresh_start` — MAP-03: both main and .bak corrupt yields fresh revision=0
- `test_reset_clears_assignments` — MAP-03: reset() clears assignments, revision back to 0
- `test_apply_fails_on_revision_mismatch` — MAP-04: wrong expected_revision returns revision_mismatch
- `test_apply_blocked_when_interlock_active` — MAP-04/05: interlock_active=True returns blocked
- `test_apply_fails_incomplete_mapping` — MAP-04: unassigned device returns incomplete
- `test_apply_passes_with_valid_candidate` — MAP-04: success path returns applied, persists applied_revision
- `test_apply_fails_invalid_frame` — MAP-04: frame not in frame_list returns invalid_frame
- `test_apply_preserves_applied_revision_on_failure` — MAP-04: failed apply does not overwrite applied_revision

### MappingNodeApplyTest (7 tests — ROS service handler contracts)
- `test_apply_ok` — MAP-04: _on_apply_mapping returns outcome=applied, applied_revision=1
- `test_apply_revision_mismatch` — MAP-04: wrong revision returns revision_mismatch
- `test_apply_blocked_recording` — MAP-05: recording_active=True returns blocked with 'recording' in detail
- `test_apply_blocked_calibration` — MAP-05: calibration_active=True returns blocked with 'calibration' in detail
- `test_apply_incomplete_unassigned_device` — MAP-04: unassigned device blocks apply
- `test_apply_invalid_frame` — MAP-04: invalid frame returns invalid_frame via node handler
- `test_apply_preserves_applied_revision_on_failure` — MAP-04: node handler preserves applied_revision on failure

### MappingNodeReconnectTest (2 tests — fleet registry reconnect)
- `test_reconnect_reattach_stays_assigned` — MAP-06: device in mapping stays assigned after fleet update
- `test_new_device_from_fleet_registry_gets_unassigned` — MAP-06: new device registered as unassigned

### MappingNodePublishTest (5 tests — publish and status parsing)
- `test_publish_on_set_assignment` — MAP-04: set_assignment triggers publish to /rehab/mapping/current
- `test_get_mapping_state_returns_valid_json` — MAP-04: GetMappingState returns valid JSON with schema fields
- `test_recording_status_sets_interlock` — MAP-05: 'active' field parsed correctly
- `test_calibration_status_sets_interlock` — MAP-05: 'active' field parsed correctly
- `test_recording_status_state_field_sets_interlock` — MAP-05: 'state=recording' activates interlock
- `test_calibration_status_state_field_sets_interlock` — MAP-05: 'state=capturing' activates interlock

## Contract Coverage

| Contract | MAP-ID | Tests Covering |
|----------|--------|----------------|
| Valid assignment states (assigned/not_used/unassigned) | MAP-01 | test_set_assignment_*_ok |
| duplicate_frame rejection | MAP-01 | test_set_assignment_duplicate_frame_rejected |
| invalid_device_id rejection (format) | MAP-01 | test_set_assignment_invalid_device_id_* (4 tests) |
| invalid_state rejection | MAP-01 | test_set_assignment_invalid_state_rejected |
| Revision monotonically increments | MAP-02 | test_revision_increments_on_each_set_assignment |
| Atomic write + corruption recovery | MAP-03 | test_persistence_*, test_backup_on_save, test_corruption_recovery_* |
| Reset clears assignments | MAP-03 | test_reset_clears_assignments |
| Apply revision_mismatch | MAP-04 | test_apply_fails_on_revision_mismatch, test_apply_revision_mismatch |
| Apply incomplete | MAP-04 | test_apply_fails_incomplete_mapping, test_apply_incomplete_unassigned_device |
| Apply invalid_frame | MAP-04 | test_apply_fails_invalid_frame, test_apply_invalid_frame |
| Apply success + applied_revision persisted | MAP-04 | test_apply_passes_with_valid_candidate, test_apply_ok |
| applied_revision preserved on failure | MAP-04 | test_apply_preserves_applied_revision_on_failure (both classes) |
| Publish on every set_assignment | MAP-04 | test_publish_on_set_assignment |
| GetMappingState returns JSON | MAP-04 | test_get_mapping_state_returns_valid_json |
| Apply blocked during recording | MAP-05 | test_apply_blocked_recording, test_apply_blocked_when_interlock_active |
| Apply blocked during calibration | MAP-05 | test_apply_blocked_calibration |
| Recording/calibration status parsing | MAP-05 | test_recording/calibration_status_* (4 tests) |
| Reconnect re-attach: assigned stays assigned | MAP-06 | test_reconnect_reattach_stays_assigned |
| New device from fleet gets unassigned | MAP-06 | test_new_device_from_fleet_registry_gets_unassigned |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _StubNode must be registered as rclpy.node.Node before module exec**

- **Found during:** Task 1 (first test run)
- **Issue:** `_install_ros_stubs()` used `sys.modules.setdefault("rclpy.node", ...)` with `rclpy.node.Node = type('Node', (), {})`. The plain `Node` stub has no `__init__` accepting a `name` argument. When `MappingNode.__init__` calls `super().__init__("mapping_node")`, Python routes to `object.__init__` which rejects the positional arg with `TypeError: object.__init__() takes exactly one argument`.
- **Fix:** Defined `_StubNode` class (with `def __init__(self, name: str)`) before the stub installation function. Changed `_install_ros_stubs()` to use `sys.modules["rclpy.node"].Node = _StubNode` via direct assignment (not `setdefault`) so `MappingNode` inherits `_StubNode` at class-definition time when the module is exec'd. This matches the pattern in `test_opensim_node.py`.
- **Files modified:** `backend/test/test_mapping_node.py`
- **Commit:** 2fb65fc (included in same commit)

None of the other plan elements required deviation.

## Test Run Results

```
Ran 36 tests in 0.214s
OK
```

All 36 tests pass. 0 failures. 0 errors.

## Self-Check: PASSED

- [x] `backend/test/test_mapping_node.py` exists (703 lines, 36 tests)
- [x] All 36 tests pass: `python -m unittest backend.test.test_mapping_node -v` → OK
- [x] Commit 2fb65fc exists with test file
- [x] MAP-01 through MAP-06 all covered (see contract table)
- [x] No live ROS, hardware, or OpenSim required
- [x] File is >200 lines (703 lines — well above minimum)
