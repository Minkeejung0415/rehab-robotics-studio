---
phase: 23-n-sensor-calibration-and-official-opensim-ik
plan: "01"
subsystem: opensim-ik
tags: [tdd, ik, opensim, subscriptions, dataclass]
dependency_graph:
  requires: []
  provides:
    - solve_n() on OpenSimOrientationIkSolver / FakeOrientationIkSolver / UnavailableOrientationIkSolver / OrientationIkSolver Protocol
    - _DeviceInput dataclass in opensim_node
    - _mac_inputs dict + _input_lock in OpenSimBridgeNode
    - _on_mapping_current / _on_mac_imu / _on_fleet_registry callbacks
    - IK-01 contract tests (A-F)
  affects:
    - backend/rehab_robotics_bridge/opensim/orientation_ik.py
    - backend/rehab_robotics_bridge/opensim/opensim_orientation_ik.py
    - backend/rehab_robotics_bridge/opensim_node.py
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN cycle for both solve_n() and IK-01 subscription lifecycle
    - threading.Lock for _mac_inputs mutation safety
    - Dynamic ROS subscription management via create_subscription/destroy_subscription
key_files:
  created:
    - backend/test/test_opensim_orientation_ik_n.py
  modified:
    - backend/rehab_robotics_bridge/opensim/orientation_ik.py
    - backend/rehab_robotics_bridge/opensim/opensim_orientation_ik.py
    - backend/rehab_robotics_bridge/opensim_node.py
    - backend/test/test_opensim_node.py
decisions:
  - solve_n() accepts calibration as optional keyword (default None) for FakeOrientationIkSolver path
  - _on_mapping_current logs warning and returns on malformed JSON without touching _mac_inputs
  - post_reconnect_fresh set True only on first frame (last_xyzw was None); subsequent frames do not re-set
  - _on_fleet_registry handles both reconnected_devices list and devices[].event=reconnect formats
  - Existing subscription assertions in tests migrated to topic-name style to tolerate new infra subs
metrics:
  duration: ~25 minutes
  completed: "2026-08-05"
  tasks_completed: 3
  files_modified: 4
  files_created: 1
---

# Phase 23 Plan 01: N-Sensor Subscription Lifecycle and solve_n() Summary

solve_n() added to all IK solver classes and dynamic MAC-keyed subscription management wired into OpenSimBridgeNode with atomic lock-protected _mac_inputs dict and IK-01 contract tests.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| Task 1 RED | solve_n() failing tests (test_opensim_orientation_ik_n.py) | 74b3e00 |
| Task 1 GREEN | solve_n() on all three solver classes and Protocol | b0b90b1 |
| Task 2+3 RED | IK-01 contract tests + destroy_subscription + topic-name assertions | b07da99 |
| Task 2+3 GREEN | _DeviceInput, _mac_inputs, _input_lock, _on_mapping_current, _on_mac_imu, _on_fleet_registry | f5d292b |

## What Was Built

### solve_n() (Task 1)

Added `solve_n(inputs, source_timestamp_ns, input_age_s, joint_names, calibration=None)` to:

- **OrientationIkSolver Protocol** — new method signature added to Protocol class
- **UnavailableOrientationIkSolver.solve_n()** — returns `IkSolution(solution_valid=False, reason=self._reason)` regardless of inputs
- **FakeOrientationIkSolver.solve_n()** — returns `calibration_required` if calibration is None, `missing_source_timestamp` if source_timestamp_ns is None, computes angle using first two inputs via apply_mounting_offsets, returns valid solution otherwise
- **OpenSimOrientationIkSolver.solve_n()** — returns `no_inputs` on empty inputs, `missing_source_timestamp` on None timestamp, builds N-column TimeSeriesTableQuaternion via `_make_quat_table_n()`, rebuilds OrientationsReference+solver per frame (non-buffered path), reads coordinates and visualization pose, returns full IkSolution

`_make_quat_table_n()` uses the same `updElt(0, column)` loop pattern as `_make_quat_table()` with the same fallback paths for older SWIG bindings.

### _DeviceInput + Dynamic Subscriptions (Task 2)

Added to `opensim_node.py`:

- `threading` import
- `_DeviceInput` dataclass with all D-02 fields: `device_id`, `frame`, `subscription_handle`, `last_xyzw`, `last_ts_ns`, `post_reconnect_fresh`, `last_seen_monotonic`
- `_MAPPING_CURRENT_TOPIC = "/rehab/mapping/current"` and `_FLEET_REGISTRY_TOPIC = "/esp/fleet/registry"` constants
- `OpenSimBridgeNode.__init__`: `_input_lock`, `_mac_inputs`, `_n_mapping_revision`, subscriptions to both topics
- `_on_mapping_current()`: parses JSON, destroys subscriptions for removed devices under lock, creates new subscriptions to `/esp/raw/mac_<12hex>` using closure pattern for device_id capture
- `_on_mac_imu()`: updates `last_xyzw`, `last_ts_ns`, `last_seen_monotonic` under lock; sets `post_reconnect_fresh=True` on first frame only
- `_on_fleet_registry()`: clears `post_reconnect_fresh` for reconnected devices; handles both JSON formats

### IK-01 Contract Tests (Task 3)

Added to `test_opensim_node.py`:

- `_StubNode.destroy_subscription()` removes subscription from list
- Updated `test_locked_defaults_create_exactly_two_native_imu_subscriptions` to use topic-name assertions instead of bare `len == 2`
- Updated `test_parameter_overrides_control_topics_frames_model_timeout_and_status` to use `assertIn` instead of equality on full topic list
- `IkOneContractTests` class with 6 tests:
  - **IK-01-A**: 2 assigned devices → 2 `/esp/raw/mac_*` subscriptions
  - **IK-01-B**: remap removes old subscription, creates new subscription
  - **IK-01-C**: `_mac_inputs` dict has exactly new device_ids after remap
  - **IK-01-D**: `_on_mac_imu` sets `last_xyzw` and `post_reconnect_fresh=True` on first call only
  - **IK-01-E**: `_on_fleet_registry` sets `post_reconnect_fresh=False` for reconnected device
  - **IK-01-F**: malformed JSON in `_on_mapping_current` logs warning, does not raise, leaves `_mac_inputs` untouched

## Test Results

```
test/test_opensim_node.py           41 passed (35 original + 6 IK-01)
test/test_opensim_orientation_ik_n.py  10 passed, 2 skipped (OpenSim not installed)
test/test_opensim_orientation_ik_opensim.py  3 passed, 3 skipped
```

## Deviations from Plan

### Auto-fixed Issues

None. Plan executed exactly as written.

### Notes

- `FakeOrientationIkSolver.solve_n()` accepts `calibration` as a keyword argument (default None) rather than having it always injected from outside. This matches the pattern in `solve()` and allows tests to call `solve_n(..., calibration=artifact)` cleanly.
- The OpenSim-binding tests in `test_opensim_orientation_ik_n.py` are correctly skipped on this machine (OpenSim not installed in Python 3.12 environment); they will run in the WSL ROS environment.

## Known Stubs

None. No stubs were introduced.

## Threat Flags

No new trust boundaries beyond what is documented in the plan's threat model. `_on_mapping_current` and `_on_fleet_registry` are defensively wrapped per T-23-01-01 and T-23-01-04.

## Self-Check: PASSED

Files exist:
- `backend/test/test_opensim_orientation_ik_n.py` FOUND
- `backend/rehab_robotics_bridge/opensim/orientation_ik.py` FOUND (contains solve_n)
- `backend/rehab_robotics_bridge/opensim/opensim_orientation_ik.py` FOUND (contains solve_n)
- `backend/rehab_robotics_bridge/opensim_node.py` FOUND (contains _DeviceInput, _mac_inputs, _on_mapping_current)
- `backend/test/test_opensim_node.py` FOUND (contains IK-01 tests)

Commits exist:
- 74b3e00 test(23-01/red): IK-01 solve_n() contract tests
- b0b90b1 feat(23-01/green): solve_n() on all IK solver classes
- b07da99 test(23-01/red): IK-01 contract tests for dynamic MAC subscriptions
- f5d292b feat(23-01/green): _DeviceInput dataclass + dynamic MAC subscriptions
