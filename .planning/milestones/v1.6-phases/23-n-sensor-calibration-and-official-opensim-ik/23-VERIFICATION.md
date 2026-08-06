---
phase: 23-n-sensor-calibration-and-official-opensim-ik
verified: 2026-08-05T00:00:00Z
status: gaps_found
score: 3/4 success criteria verified
overrides_applied: 0
gaps:
  - truth: "Official OpenSim orientation IK consumes mapped inputs in deterministic order and exposes mapping_revision, calibration_identity, input_validity, solver_status, and visualizer_provenance"
    status: partial
    reason: "IK-04-G and IK-04-H contract tests (solver_insufficient hard-block in mapping_node.apply_candidate) fail at runtime due to a test stub ordering bug. The production code in mapping_node.py lines 322-338 is substantively correct — verified by direct invocation — but the tests cannot exercise it through pytest because _install_ros_stubs() registers a minimal rehab_robotics_interfaces stub (IdentifyDevice only) at module-import time, and _ensure_mapping_stubs() inside IkFourContractTests silently skips augmentation because the module is already in sys.modules. Net result: 2 of 9 IK-04 tests fail in the test runner."
    artifacts:
      - path: "backend/test/test_opensim_node.py"
        issue: "_ensure_mapping_stubs() (line 2116) checks 'if rehab_robotics_interfaces not in sys.modules' but the module is already registered by _install_ros_stubs() at line 218 with only IdentifyDevice, so ApplyMapping is never added and mapping_node.py fails to import."
    missing:
      - "Extend _install_ros_stubs() or _ensure_mapping_stubs() to also install ApplyMapping, GetMappingState, ResetMapping, SetAssignment into the shared stub so that IK-04-G and IK-04-H can import MappingStore successfully"
---

# Phase 23: N-Sensor Calibration and Official OpenSim IK — Verification Report

**Phase Goal:** N-Sensor Calibration and Official OpenSim IK — opensim_node subscribes to /rehab/mapping/current, manages MAC-keyed subscriptions with full lifecycle, captures calibration artifacts tied to model+revision identity, enforces sync-skew bounds, and gates JointState publication through the official OpenSim orientation IK solver.
**Verified:** 2026-08-05
**Status:** gaps_found — 3/4 success criteria verified; IK-04 has 2 test failures caused by a stub isolation bug in the test harness (not a production code gap).
**Re-verification:** No — initial verification.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Applying or replacing a mapping creates one deterministic ordered N-sensor input set and tears down obsolete MAC-keyed subscriptions, callbacks, and queues without resource growth across repeated remaps. | VERIFIED | `_on_mapping_current()` at opensim_node.py:363 destroys removed subscriptions via `destroy_subscription()` and creates new ones. `_mac_inputs` dict is atomically updated under `self._input_lock`. IK-01-A through IK-01-F all pass (6/6). |
| 2 | Calibration artifacts identify the exact model hash, applied mapping revision, device-to-Frame assignments, and solver profile, and become invalid after any semantic change. | VERIFIED | `CalibrationArtifactStore` in n_sensor_calibration.py provides atomic save/load with schema_version="calib.v1" and strict `is_valid()` checks on model_hash, applied_revision, and device_order set equality. `_check_artifact_validity()` in opensim_node.py:762 is called after every `_on_mapping_current()`. 32/32 tests in test_n_sensor_calibration.py pass. IK-02 node tests (IkTwoNodeTests) all pass (8/8). |
| 3 | Joint states publish only when every required input is valid, fresh, post-reconnect, and within the synchronization-skew bound; degraded inputs suppress new IK output while acquisition and recording continue. | VERIFIED | `_check_sync_skew()` in opensim_node.py:485 uses median-reference algorithm with configurable `sync_skew_ms` (default 50). Gate in `_solve_and_publish_ik_n()` publishes `/rehab/opensim/input_validity` on every cycle and suppresses JointState when `all_valid=False`. IK-03-A through IK-03-H all pass (10/10). `sync_skew_ms` wired in rehab_robotics.launch.py (lines 87, 140). |
| 4 | Official OpenSim orientation IK consumes mapped inputs in deterministic order and exposes mapping_revision, calibration_identity, input_validity, solver_status, and visualizer_provenance. | PARTIAL | IK-04-A through IK-04-F and IK-04-I pass (7/9). `_solve_and_publish_ik_n()` correctly calls `solve_n()` with alphabetically sorted (frame, xyzw) pairs, publishes `/rehab/opensim/joint_states_metadata` with all five required fields, and wires `SOLVER_PROFILE_MIN_SENSORS` in `ik_contracts.py`. `apply_candidate()` in mapping_node.py correctly returns `solver_insufficient` when assigned count < 2. However, IK-04-G and IK-04-H fail in the test runner due to a stub isolation bug (see Gaps). |

**Score:** 3/4 truths fully verified (1 partial)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/rehab_robotics_bridge/opensim/n_sensor_calibration.py` | CalibrationArtifactStore with save/load/is_valid | VERIFIED | 119 lines; compute_artifact_path, save (atomic tmp+replace), load (schema validation), is_valid (model_hash + revision + device_order set) |
| `backend/rehab_robotics_bridge/opensim/ik_contracts.py` | SOLVER_PROFILE_MIN_SENSORS constant, CalibrationState enum | VERIFIED | `SOLVER_PROFILE_MIN_SENSORS = {"lower_body": 2}` at line 48; `CalibrationState` enum at line 39; `may_publish_joint_states()` gate |
| `backend/rehab_robotics_bridge/opensim_node.py` | Extended with N-sensor subscription management, calibration artifact state, sync-skew gate, IK-N solve path | VERIFIED | 1355 lines; `_DeviceInput` dataclass, `_mac_inputs` dict under `_input_lock`, `_on_mapping_current()`, `_on_mac_imu()`, `_on_fleet_registry()`, `_check_sync_skew()`, `_solve_and_publish_ik_n()`, `_on_calibration_capture_n()`, `_check_artifact_validity()` all present and substantive |
| `backend/rehab_robotics_bridge/opensim/opensim_orientation_ik.py` | `solve_n()` method on OpenSimOrientationIkSolver | VERIFIED | `solve_n()` at line 540; `_make_quat_table_n()` at line 497; handles N (frame, wxyz) pairs, rebuilds solver, publishes IkSolution |
| `backend/test/test_n_sensor_calibration.py` | CalibrationArtifactStore contract tests | VERIFIED | 32 tests across 3 classes: CalibrationArtifactStoreBasicTests, IkTwoArtifactTests, CalibrationArtifactStoreExtendedTests — all 32 pass |
| `backend/test/test_opensim_node.py` | IK-01 through IK-04 contract tests | PARTIAL | IkOneContractTests (6), IkTwoNodeTests (8), IkThreeContractTests (10), IkFourContractTests (9) collected; 37/39 pass; 2 fail (IK-04-G, IK-04-H) |
| `backend/launch/rehab_robotics.launch.py` | sync_skew_ms launch argument | VERIFIED | DeclareLaunchArgument at line 87, LaunchConfiguration at line 140 |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `/rehab/mapping/current` | `_on_mapping_current()` | ROS subscription at opensim_node.py:304 | WIRED | `_mapping_subscription` created in `__init__`, callback parses JSON and manages `_mac_inputs` |
| `_on_mapping_current()` | `_mac_inputs` | `destroy_subscription()` + `create_subscription()` under `_input_lock` | WIRED | Lines 387-420; alphabetical order enforced by `sorted()` in `_solve_and_publish_ik_n()` |
| `_on_mac_imu()` | `_solve_and_publish_ik_n()` | Direct call at opensim_node.py:455 outside lock | WIRED | Called after updating `_mac_inputs[device_id]` entry |
| `_check_sync_skew()` | `/rehab/opensim/input_validity` | `_publish_input_validity()` at opensim_node.py:536 | WIRED | Called on every `_solve_and_publish_ik_n()` cycle, even when suppressed |
| `_solve_and_publish_ik_n()` | `_ik_solver.solve_n()` | Line 646, alphabetical inputs at line 617 | WIRED | `solver_inputs` built from `sorted(_mac_inputs.values(), key=lambda e: e.device_id)` |
| `solve_n()` | `JointState` publisher | Lines 670-676 in opensim_node.py | WIRED | Published only when `solution.solution_valid and source_ts is not None` |
| `_publish_n_ik_metadata()` | `/rehab/opensim/joint_states_metadata` | Lines 678-701 | WIRED | Published on all paths (suppressed, calibration_required, error, success); carries mapping_revision, calibration_identity, input_validity_mask, solver_status, visualizer_provenance |
| `CalibrationArtifactStore` | `opensim_node._n_calib_store` | Import at line 34; instantiated at line 320 | WIRED | Used in `_on_calibration_capture_n()` (save) and `_check_artifact_validity()` (is_valid) |
| `SOLVER_PROFILE_MIN_SENSORS` | `apply_candidate()` in mapping_node.py | `_SOLVER_PROFILE_MIN_SENSORS` mirror at lines 29-33, used at line 330 | WIRED | Hard-block returns `solver_insufficient` when `len(assigned_devices) < min_sensors` |
| `/esp/fleet/registry` | `post_reconnect_fresh = False` | `_on_fleet_registry()` at opensim_node.py:457 | WIRED | Clears freshness flag on reconnect events |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `opensim_node._solve_and_publish_ik_n()` | `inputs_snapshot` | `_mac_inputs` populated by `_on_mac_imu()` IMU callbacks | Yes — actual Imu.orientation values from ROS topic | FLOWING |
| `CalibrationArtifactStore.save()` | `artifact` dict | Reference poses captured from `_mac_inputs[did].last_xyzw` at capture time | Yes — actual sensor quaternions | FLOWING |
| `_publish_n_ik_metadata()` | `mapping_revision`, `calibration_identity` | `_n_mapping_revision` from `data["applied_revision"]` in mapping JSON | Yes — populated from /rehab/mapping/current | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| SOLVER_PROFILE_MIN_SENSORS constant correct | `python -c "from rehab_robotics_bridge.opensim.ik_contracts import SOLVER_PROFILE_MIN_SENSORS; assert SOLVER_PROFILE_MIN_SENSORS['lower_body'] == 2; print('ok')"` | ok | PASS |
| CalibrationArtifactStore importable | `python -c "from rehab_robotics_bridge.opensim.n_sensor_calibration import CalibrationArtifactStore; print('ok')"` | ok | PASS |
| apply_candidate returns solver_insufficient (1 device) | Direct Python invocation with full stubs | `{'outcome': 'solver_insufficient', ...}` | PASS |
| apply_candidate returns applied (2 devices) | Direct Python invocation with full stubs | `{'outcome': 'applied', 'applied_revision': 2, ...}` | PASS |
| n_sensor_calibration tests | `python -m pytest test/test_n_sensor_calibration.py -q` | 32 passed | PASS |
| IK-01 through IK-03 contract tests | `python -m pytest test/test_opensim_node.py -k "IkOne or IkTwo or IkThree" -q` | 24 passed | PASS |
| IK-04 contract tests | `python -m pytest test/test_opensim_node.py -k "IkFour" -q` | 7 passed, 2 failed | PARTIAL |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/test/test_opensim_node.py` | 2116-2129 | `_ensure_mapping_stubs()` checks `if "rehab_robotics_interfaces" not in sys.modules` but module already registered at line 218 with only `IdentifyDevice`; `ApplyMapping`, `GetMappingState`, `ResetMapping`, `SetAssignment` never added | BLOCKER | IK-04-G and IK-04-H cannot import `MappingStore` and fail with `ImportError: cannot import name 'ApplyMapping'` |

No debt markers (TBD, FIXME, XXX) found in any phase-23 production files.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| IK-01 | 23-01-PLAN | Dynamic MAC-keyed subscription lifecycle | SATISFIED | `_on_mapping_current()`, `_DeviceInput`, `_input_lock`, `_mac_inputs`; IK-01-A through IK-01-F pass |
| IK-02 | 23-02-PLAN | Calibration artifact with model_hash, revision, device_order, solver_profile; invalidation on semantic change | SATISFIED | `CalibrationArtifactStore`, `_on_calibration_capture_n()`, `_check_artifact_validity()`; 32 artifact tests pass |
| IK-03 | 23-03-PLAN | Sync-skew enforcement; suppress IK when any device invalid/stale/unfresh | SATISFIED | `_check_sync_skew()`, `_publish_input_validity()`, `sync_skew_ms` param + launch arg; IK-03-A through IK-03-H pass |
| IK-04 | 23-04-PLAN | solve_n() wired with deterministic order; metadata topic with all 5 fields; solver_insufficient hard-block | PARTIAL | IK-04-A through IK-04-F and IK-04-I pass. Production implementation correct (verified by direct invocation). IK-04-G and IK-04-H fail due to test stub ordering bug in test harness |

---

## Gaps Summary

**1 gap blocking full status: test stub ordering bug causes IK-04-G and IK-04-H failures.**

The production code is correct:
- `apply_candidate()` in `mapping_node.py` (lines 322-338) correctly checks `len(assigned_devices) < min_sensors` and returns `{"outcome": "solver_insufficient", ...}`.
- Direct Python invocation with a complete stub confirmed the behavior works as specified.

The test harness is broken:
- `_install_ros_stubs()` registers `rehab_robotics_interfaces.srv` with only `IdentifyDevice` at module import time.
- `_ensure_mapping_stubs()` (IkFourContractTests, line 2116) checks the same condition (`if "rehab_robotics_interfaces" not in sys.modules`) — which is already True at test time — and silently skips installing `ApplyMapping`, `GetMappingState`, `ResetMapping`, `SetAssignment`.
- When the test then tries `from rehab_robotics_bridge.mapping_node import MappingStore`, it fails with `ImportError: cannot import name 'ApplyMapping' from 'rehab_robotics_interfaces.srv'`.

**Fix required:** In `_install_ros_stubs()` (or in `_ensure_mapping_stubs()`), change the else-branch at line 226 to unconditionally add the four mapping service classes to the already-registered stub, not just `IdentifyDevice`. Then IK-04-G and IK-04-H will pass.

This is a WARNING-level test harness defect. The SC-4 behavior is implemented in production code. The gap is in test coverage completeness.

---

_Verified: 2026-08-05T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
