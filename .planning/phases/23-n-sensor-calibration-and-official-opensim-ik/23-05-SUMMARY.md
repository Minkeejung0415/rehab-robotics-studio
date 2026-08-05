---
phase: 23-n-sensor-calibration-and-official-opensim-ik
plan: "05"
subsystem: opensim-ik
tags:
  - ik
  - n-sensor
  - launch-wiring
  - test-suite
  - green-gate
dependency_graph:
  requires:
    - 23-01  # _DeviceInput, dynamic MAC subscriptions
    - 23-02  # CalibrationArtifactStore offline tests
    - 23-03  # sync-skew gate, input_validity publisher
    - 23-04  # complete _solve_and_publish_ik_n(), SOLVER_PROFILE_MIN_SENSORS
  provides:
    - sync_skew_ms wired in rehab_robotics.launch.py
    - Complete CalibrationArtifactStoreExtendedTests (8 named tests)
    - Phase 23 green gate: 359 tests pass
  affects:
    - backend/launch/rehab_robotics.launch.py
    - backend/test/test_n_sensor_calibration.py
    - backend/test/test_opensim_node.py (stub isolation fix)
tech_stack:
  added: []
  patterns:
    - DeclareLaunchArgument + LaunchConfiguration wiring for opensim_bridge node
    - Comprehensive offline artifact store testing with named contract methods
    - Test stub completeness: all symbols needed by imported modules included
key_files:
  created: []
  modified:
    - backend/launch/rehab_robotics.launch.py
    - backend/test/test_n_sensor_calibration.py
    - backend/test/test_opensim_node.py
decisions:
  - "sync_skew_ms wired to opensim_bridge executable (the opensim_node entrypoint); default 50 ms matches node's parameter default"
  - "CalibrationArtifactStoreExtendedTests added as third test class with exact method names required by plan must_haves"
  - "std_msgs stub extended with Float32MultiArray + Header (not SetBool setdefault isolation) to fix pytest collection ordering bug"
metrics:
  duration_s: 521
  completed_date: "2026-08-05"
  tasks_completed: 3
  files_modified: 3
---

# Phase 23 Plan 05: Launch wiring and full test suite green gate — Summary

**One-liner:** Wire sync_skew_ms into rehab_robotics.launch.py opensim_bridge node, add 8 named CalibrationArtifactStore contract tests, fix pytest module-ordering stub pollution to achieve 359-test green gate.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Wire sync_skew_ms DeclareLaunchArgument + LaunchConfiguration to opensim_bridge | c39bb98 | launch/rehab_robotics.launch.py |
| 2 | Add CalibrationArtifactStoreExtendedTests (8 named tests, 32 total) | 9acf30c | test/test_n_sensor_calibration.py |
| 3 | Fix std_msgs stub isolation in test_opensim_node.py; full suite green | 753b43a | test/test_opensim_node.py |

## Verification Results

- `python -m pytest backend/test/ -x -q` → **359 passed, 8 skipped, 238 subtests passed**
- `grep "sync_skew_ms" backend/launch/rehab_robotics.launch.py` → 2 matches (DeclareLaunchArgument + LaunchConfiguration)
- `python -c "from rehab_robotics_bridge.opensim.ik_contracts import SOLVER_PROFILE_MIN_SENSORS; assert SOLVER_PROFILE_MIN_SENSORS['lower_body'] == 2; print('ok')"` → ok
- `python -m pytest backend/test/test_n_sensor_calibration.py -v` → **32 passed**
- IK-01 through IK-04 contract tests: IkOneContractTests, IkTwoNodeTests, IkTwoArtifactTests, IkThreeContractTests, IkFourContractTests — all collected and passing

## Implementation Details

### Task 1: sync_skew_ms launch wiring

Added to `generate_launch_description()` args list:
```python
DeclareLaunchArgument(
    'sync_skew_ms',
    default_value='50',
    description='Sync skew tolerance in ms for N-sensor IK gate',
),
```

Added to `opensim` Node parameters dict:
```python
'sync_skew_ms': LaunchConfiguration('sync_skew_ms'),
```

The `opensim_bridge` executable is the `opensim_node` entrypoint. The node's `__init__` already reads `sync_skew_ms` and applies `max(1, int(value))` clamping (satisfying T-23-05-02 mitigation from threat model).

### Task 2: CalibrationArtifactStoreExtendedTests

Added 8 named test methods to `CalibrationArtifactStoreExtendedTests` class:

| Method | Tests |
|--------|-------|
| `test_corruption_recovery` | Corrupt JSON → None; is_valid(None) → False |
| `test_wrong_schema_version` | calib.v2 → load() returns None |
| `test_empty_device_order_invalid` | Vacuously valid when both empty; False when mismatch |
| `test_artifact_path_uses_hash_prefix` | First 8 chars in filename; short hash handled |
| `test_save_creates_parent_dirs` | Deeply nested missing dirs created on save() |
| `test_atomic_write_no_tmp_residue` | No .tmp left behind; final file contains valid JSON |
| `test_load_missing_file` | No exception on missing path; returns None |
| `test_is_valid_all_match` | True when model_hash, revision, device_order all match |

### Task 3: Stub isolation fix (Rule 1 auto-fix)

**Root cause:** pytest imports ALL test modules during collection phase before running any tests. `test_opensim_node.py` calls `_install_ros_stubs()` at module level using direct `sys.modules[key] = value` assignment (not `setdefault`), overwriting the more complete `std_msgs.msg` stub that `test_esp32_controls.py` had installed. When `test_identify_completes_while_unrelated_fleet_session_is_reconnecting` later called `_load_fleet_module()` → `fleet_bridge_node.py` → `from rehab_robotics_bridge.esp32_bridge_node import ...`, the package import found the incomplete stub missing `Float32MultiArray`, `Header`, and `SetBool`.

**Fix:** Extended `_install_ros_stubs()` in `test_opensim_node.py` to include:
- `std_msgs.msg.Float32MultiArray` (stub class, constructable)
- `std_msgs.msg.Header` (stub class, constructable)
- `std_srvs.srv.SetBool` (stub class)
- `rehab_robotics_interfaces.srv.IdentifyDevice` (conditional: installed if not already in sys.modules, or patched onto existing if absent)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pytest module-ordering stub pollution causing test_esp32_controls test failure**
- **Found during:** Task 3 — `python -m pytest backend/test/ -x -q` stopped at `test_identify_completes_while_unrelated_fleet_session_is_reconnecting` with `ImportError: cannot import name 'Float32MultiArray' from 'std_msgs.msg'`
- **Issue:** `test_opensim_node.py`'s module-level `_install_ros_stubs()` overwrites `sys.modules["std_msgs.msg"]` (and `std_srvs.srv`) with incomplete stubs lacking `Float32MultiArray`, `Header`, `SetBool`, and `IdentifyDevice`. When `fleet_bridge_node.py` is imported via the package system during the failing test, it reaches `esp32_bridge_node.py` which requires these symbols.
- **Root cause mechanism:** pytest collection phase imports all test modules; `test_opensim_node.py` alphabetically comes between `test_fleet_bridge.py` (which uses `setdefault`) and the `test_identify_completes` test execution; the overwrite happened because test_opensim_node used plain assignment not setdefault.
- **Fix:** Added missing stub symbols to `_install_ros_stubs()` in test_opensim_node.py
- **Files modified:** backend/test/test_opensim_node.py
- **Commit:** 753b43a

## Known Stubs

None. All Phase 23 feature implementations are complete. No placeholder data or TODO markers in produced files.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Launch file only adds a parameter pass-through (operator-controlled, bounds-enforced in node per T-23-05-02).

## Self-Check: PASSED

- `backend/launch/rehab_robotics.launch.py` — FOUND: sync_skew_ms (DeclareLaunchArgument at line 87, LaunchConfiguration at line 140)
- `backend/test/test_n_sensor_calibration.py` — FOUND: test_corruption_recovery, 32 tests pass
- `backend/test/test_opensim_node.py` — FOUND: Float32MultiArray, Header, SetBool in stub
- Commit c39bb98 — FOUND in git log
- Commit 9acf30c — FOUND in git log
- Commit 753b43a — FOUND in git log
- Full suite: 359 passed, 8 skipped — CONFIRMED
