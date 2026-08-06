---
phase: 23-n-sensor-calibration-and-official-opensim-ik
plan: "04"
subsystem: opensim-ik
tags:
  - ik
  - n-sensor
  - metadata
  - solver-sufficiency
  - tdd
dependency_graph:
  requires:
    - 23-01  # _DeviceInput, subscription lifecycle, solve_n() protocol
    - 23-02  # CalibrationArtifactStore, artifact lifecycle
    - 23-03  # _check_sync_skew, _solve_and_publish_ik_n stub, input_validity publisher
  provides:
    - SOLVER_PROFILE_MIN_SENSORS dict in ik_contracts.py
    - solver_insufficient hard-block in mapping_node.apply_candidate()
    - complete _solve_and_publish_ik_n() with solve_n() call
    - /rehab/opensim/joint_states_metadata publisher and payload
    - IK-04-A through IK-04-I contract tests
  affects:
    - opensim_node._solve_and_publish_ik_n
    - mapping_node.MappingStore.apply_candidate
    - ik_contracts module exports
tech_stack:
  added:
    - SOLVER_PROFILE_MIN_SENSORS constant (ik_contracts.py)
    - _publish_n_ik_metadata() helper (opensim_node.py)
    - _n_joint_states_metadata_publisher (opensim_node.__init__)
    - _TrackingFakeIkSolver test double (test_opensim_node.py)
  patterns:
    - TDD RED/GREEN with alphabetical order verification
    - try/except wrapper for solve_n() exception containment (T-23-04-05)
    - explicit None check for xyzw before solver_inputs construction (T-23-04-02)
    - Hard-block before atomic swap (solver_insufficient)
key_files:
  created: []
  modified:
    - backend/rehab_robotics_bridge/opensim/ik_contracts.py
    - backend/rehab_robotics_bridge/mapping_node.py
    - backend/rehab_robotics_bridge/opensim_node.py
    - backend/test/test_opensim_node.py
    - backend/test/test_mapping_node.py
decisions:
  - "SOLVER_PROFILE_MIN_SENSORS defined in ik_contracts.py (authoritative) and mirrored locally in mapping_node.py (_SOLVER_PROFILE_MIN_SENSORS) to avoid circular import"
  - "solver_insufficient hard-block placed BEFORE atomic swap in apply_candidate() so applied_revision is never updated on insufficient sensors"
  - "input_age_s uses min(now - last_seen_monotonic) to be conservative about data age"
  - "source_timestamp_ns uses min(last_ts_ns) across inputs, parallel to pair strategy"
  - "_TrackingFakeIkSolver used as test double to verify inputs ordering without depending on FakeOrientationIkSolver internals"
  - "IK-04-G/H use _ensure_mapping_stubs() helper to install rehab_robotics_interfaces stubs when importing MappingStore within test_opensim_node.py test context"
metrics:
  duration_s: 506
  completed_date: "2026-08-05"
  tasks_completed: 3
  files_modified: 5
---

# Phase 23 Plan 04: N-sensor IK wiring and extended metadata output — Summary

**One-liner:** Complete _solve_and_publish_ik_n() wired to solve_n() with alphabetical input ordering, /rehab/opensim/joint_states_metadata provenance publisher, and SOLVER_PROFILE_MIN_SENSORS hard-block in mapping_node.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| RED | IK-04-A through IK-04-I contract tests (failing) | dc23de7 | test_opensim_node.py |
| GREEN T1 | SOLVER_PROFILE_MIN_SENSORS in ik_contracts + hard-block in mapping_node | 249209c | ik_contracts.py, mapping_node.py |
| GREEN T2 | Complete _solve_and_publish_ik_n() + _publish_n_ik_metadata() | 249209c | opensim_node.py |
| GREEN T3 | IK-04 tests pass + mapping_node regression fixes | 249209c | test_opensim_node.py, test_mapping_node.py |

## Verification Results

- `python -m pytest test/test_opensim_node.py test/test_mapping_node.py -q` → **110 passed, 6 subtests passed**
- `from rehab_robotics_bridge.opensim.ik_contracts import SOLVER_PROFILE_MIN_SENSORS` → `{'lower_body': 2}`
- `grep "joint_states_metadata" backend/rehab_robotics_bridge/opensim_node.py` → found in publisher creation and `_publish_n_ik_metadata()`
- IK-04-A through IK-04-I: all 9 tests pass
- All prior IK-01, IK-02, IK-03 tests pass without regression

## Implementation Details

### SOLVER_PROFILE_MIN_SENSORS (ik_contracts.py)

Added after `CalibrationState` class:
```python
SOLVER_PROFILE_MIN_SENSORS: dict[str, int] = {
    "lower_body": 2,
}
```

### Hard-block in mapping_node.apply_candidate()

Replaced soft warning (`detail = "solver_insufficient: no devices assigned"`) with an early return BEFORE the atomic swap:

```python
assigned_devices = [did for did, entry in assignments.items() if entry.get("state") == "assigned"]
solver_profile = self._data.get("solver_profile", "lower_body")
min_sensors = _SOLVER_PROFILE_MIN_SENSORS.get(solver_profile, 2)
if len(assigned_devices) < min_sensors:
    return {"outcome": "solver_insufficient", "applied_revision": self.applied_revision,
            "detail": f"need_{min_sensors}_assigned_got_{len(assigned_devices)}"}
```

### _solve_and_publish_ik_n() completion (opensim_node.py)

Full implementation added after the sync-skew gate:
1. Builds `input_validity_mask` in alphabetical device_id order
2. Computes `calibration_identity` (artifact filename) and `visualizer_provenance` ("{hash8}_rev{N}")
3. On gate failure: publishes metadata with `solver_status="suppressed"` or `"calibration_required"`
4. Checks all `last_xyzw` not None (T-23-04-02)
5. Computes `source_ts = min(last_ts_ns)` and `input_age_s = min(now - last_seen_monotonic)`
6. Calls `self._ik_solver.solve_n(inputs=solver_inputs, ...)` wrapped in try/except (T-23-04-05)
7. Publishes metadata on every path
8. Publishes JointState on JOINT_STATES_TOPIC when `solution_valid=True`

### /rehab/opensim/joint_states_metadata payload

```json
{
  "schema": "rehab.n_ik_metadata.1",
  "mapping_revision": 5,
  "calibration_identity": "calibration_deadbeef_rev5.json",
  "input_validity_mask": [true, true],
  "solver_status": "ok",
  "visualizer_provenance": "deadbeef_rev5"
}
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed NameError: `detail` variable removed when upgrading soft warning to hard-block**
- **Found during:** GREEN phase — `test_apply_ok` raised `NameError: name 'detail' is not defined`
- **Issue:** The original `apply_candidate()` returned `"detail": detail` at the end, but the replacement block removed the `detail = ""` assignment while keeping the return statement referencing it.
- **Fix:** Changed `"detail": detail` to `"detail": ""` in the final return statement.
- **Files modified:** backend/rehab_robotics_bridge/mapping_node.py
- **Commit:** 249209c

**2. [Rule 1 - Bug] Updated 4 test_mapping_node.py tests that used 1 assigned device with `outcome="applied"`**
- **Found during:** GREEN phase — 4 existing tests used 1 device and expected `applied`, which now returns `solver_insufficient` per the new hard-block
- **Tests affected:** `MappingStoreTest::test_apply_passes_with_valid_candidate`, `MappingStoreTest::test_apply_preserves_applied_revision_on_failure`, `MappingNodeApplyTest::test_apply_ok`, `MappingNodeApplyTest::test_apply_preserves_applied_revision_on_failure`, plus cascading revision number updates in 2 further tests
- **Fix:** Added DEVICE_B as second assigned device in test setup; updated revision numbers accordingly (1→2, 2→3 etc.)
- **Files modified:** backend/test/test_mapping_node.py
- **Commit:** 249209c

**3. [Rule 3 - Blocking] Added `_ensure_mapping_stubs()` helper in IkFourContractTests for IK-04-G/H**
- **Found during:** GREEN phase — IK-04-G/H imported `MappingStore` from `mapping_node` which requires `rehab_robotics_interfaces` stubs not installed by `_install_ros_stubs()` in test_opensim_node.py
- **Fix:** Added `_ensure_mapping_stubs()` method that installs the interfaces stub on demand before importing MappingStore; only installs if not already in sys.modules
- **Files modified:** backend/test/test_opensim_node.py
- **Commit:** 249209c

## Known Stubs

None. `_solve_and_publish_ik_n()` is fully implemented. The "Plan 23-04 will wire..." comment has been replaced with the complete implementation.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced beyond what the plan's threat model covers.

| Flag | File | Description |
|------|------|-------------|
| T-23-04-02 (mitigated) | opensim_node.py | Explicit None check for xyzw before building solver_inputs |
| T-23-04-05 (mitigated) | opensim_node.py | solve_n exceptions caught; publish solve_error status without crashing node |

## TDD Gate Compliance

- RED gate (test commit): dc23de7 — `test(23-04/red): IK-04 metadata and solver_insufficient contract tests (failing)`
- GREEN gate (feat commit): 249209c — `feat(23-04/green): complete _solve_and_publish_ik_n() + SOLVER_PROFILE_MIN_SENSORS hard-block`
- REFACTOR gate: Not needed — implementation clean on first pass.

## Self-Check: PASSED

- `backend/rehab_robotics_bridge/opensim/ik_contracts.py` — FOUND: SOLVER_PROFILE_MIN_SENSORS
- `backend/rehab_robotics_bridge/mapping_node.py` — FOUND: solver_insufficient hard-block
- `backend/rehab_robotics_bridge/opensim_node.py` — FOUND: _solve_and_publish_ik_n(), _publish_n_ik_metadata(), joint_states_metadata publisher
- `backend/test/test_opensim_node.py` — FOUND: IkFourContractTests, _TrackingFakeIkSolver
- Commits dc23de7 and 249209c — FOUND in git log
