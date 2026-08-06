---
phase: 22-model-catalog-mapping-store-and-transactional-contracts
plan: "04"
subsystem: model-catalog
tags: [testing, offline, model-catalog, sha256, opensim]
dependency_graph:
  requires: ["22-02"]
  provides: ["offline test coverage for model_catalog_node"]
  affects: ["backend/test/test_model_catalog_node.py"]
tech_stack:
  added: []
  patterns: [unittest, importlib.util module loader, _StubNode test double, mock opensim module]
key_files:
  created:
    - backend/test/test_model_catalog_node.py
  modified: []
decisions:
  - "Empty-path case tested via direct _build_and_publish_catalog() call because _on_catalog_timer() short-circuits when last path == new path (both ''), which is the correct production behavior."
  - "Mock opensim built as types.SimpleNamespace with a configurable Model class to avoid any real OpenSim dependency."
  - "_make_catalog_node() re-loads the module with _OverrideStubNode patched as rclpy.node.Node base to give each test a fresh isolated node instance."
metrics:
  duration: "~8 minutes"
  completed: "2026-08-05"
  tasks_completed: 2
  files_changed: 1
---

# Phase 22 Plan 04: Model Catalog Node Offline Tests Summary

Offline deterministic test suite for `model_catalog_node.py` — SHA-256 hash contract, frame enumeration with mock OpenSim, and fail-closed publish behavior on every error path.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write tests for compute_model_hash and enumerate_compatible_frames | 976c077 | backend/test/test_model_catalog_node.py |
| 2 | Write tests for ModelCatalogNode catalog publish behavior | 976c077 | backend/test/test_model_catalog_node.py |

## Test Coverage

### ModelCatalogPureFunctionTest (11 tests)

| Test | What it proves |
|------|---------------|
| test_compute_model_hash_correct | SHA-256 of known bytes matches hashlib reference (MODEL-01) |
| test_compute_model_hash_empty_file | sha256(b"") is correct for empty file |
| test_compute_model_hash_missing_path_raises | FileNotFoundError on non-existent path |
| test_hash_changes_on_file_change | Different content produces different hash |
| test_enumerate_compatible_frames_excludes_ground | Ground excluded; femur_r/tibia_r included (MODEL-02) |
| test_enumerate_compatible_frames_empty_model | Ground-only model returns [] |
| test_enumerate_compatible_frames_no_bodies_at_all | Empty body set returns [] |
| test_enumerate_compatible_frames_read_only | setUseVisualizer and initSystem never called (D-03) |
| test_enumerate_compatible_frames_result_is_sorted | Output deterministically sorted by segment |
| test_enumerate_compatible_frames_missing_file_raises | FileNotFoundError for non-existent model path |

### ModelCatalogNodePublishTest (7 tests)

| Test | What it proves |
|------|---------------|
| test_empty_model_path_publishes_no_model_path_error | error_reason=no_model_path, frame_list=[], model_hash="" |
| test_missing_file_publishes_not_found_error | error_reason=model_path_not_found (MODEL-03) |
| test_opensim_unavailable_publishes_bindings_error | error_reason=opensim_bindings_unavailable; hash present before import attempt |
| test_schema_version_in_all_error_outputs | schema_version="rehab.model_catalog.1" in every output |
| test_no_republish_on_same_path | Change detection prevents duplicate publishes (D-02) |
| test_on_catalog_timer_publishes_on_path_change | Timer publishes when path changes |
| test_catalog_published_on_load | __init__ triggers immediate publish on non-empty startup path |

**Total: 17 tests. All pass. No live ROS, no real OpenSim, no hardware.**

## Deviations from Plan

### Auto-corrected Behavior Mismatches

**1. [Rule 1 - Bug] Empty-path test expectation adjusted**
- **Found during:** Task 2
- **Issue:** The plan described `_on_catalog_timer()` as publishing on empty path during `__init__`. In fact the node initialises `_last_model_path=""`, reads `opensim_model_path=""`, finds them equal, and returns without publishing — which is correct production behavior.
- **Fix:** Tests for the empty-path branch now call `_build_and_publish_catalog("")` directly, which tests the branch logic without relying on the timer change-detection path. This accurately verifies MODEL-03 semantics.
- **Files modified:** backend/test/test_model_catalog_node.py

**2. [Rule 1 - Bug] test_catalog_published_on_load uses non-empty path**
- **Found during:** Task 2
- **Issue:** Using `opensim_model_path=""` on startup does not produce a publish because `_last_model_path` also starts as `""`.
- **Fix:** Test now uses a non-empty missing path (`/nonexistent/startup.osim`) which triggers the `""` -> non-empty transition, producing one publish on `__init__`.
- **Files modified:** backend/test/test_model_catalog_node.py

## Verification Results

```
Ran 17 tests in 0.032s
OK
```

Cross-regression with test_fleet_bridge:
```
Ran 52 tests in 0.362s
OK
```

## Known Stubs

None. All tests assert real production logic; no placeholder data.

## Threat Flags

None. Test file adds no new network endpoints, auth paths, or schema changes.

## Self-Check: PASSED

- [x] backend/test/test_model_catalog_node.py exists (562 lines)
- [x] Commit 976c077 exists and verified
- [x] 17 tests pass: 0 failures, 0 errors
- [x] Cross-regression with fleet_bridge: 52 total tests pass
