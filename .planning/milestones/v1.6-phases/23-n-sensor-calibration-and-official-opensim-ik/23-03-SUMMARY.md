---
phase: 23-n-sensor-calibration-and-official-opensim-ik
plan: 03
subsystem: opensim-bridge
tags: [tdd, ik, sync-skew, n-sensor, ros, python]
dependency_graph:
  requires: [23-01, 23-02]
  provides: [sync-skew-gate, input-validity-publisher, solve-and-publish-ik-n-stub]
  affects: [backend/rehab_robotics_bridge/opensim_node.py]
tech_stack:
  added: []
  patterns:
    - median-reference sync-skew algorithm (D-07)
    - per-device validity publishing every IK cycle regardless of gate result (D-08)
    - post_reconnect_fresh gate independent of skew (D-09)
key_files:
  created: []
  modified:
    - backend/rehab_robotics_bridge/opensim_node.py
    - backend/test/test_opensim_node.py
decisions:
  - "IK-03 test for 100ms skew uses 200ms device gap so each device is 100ms from the median (not 100ms from each other)"
  - "_solve_and_publish_ik_n stubbed to log at debug level after gate passes; full solver wired in Plan 23-04"
  - "_Logger stub in tests extended with debug() method for compatibility with node debug logging"
metrics:
  duration: "~20 minutes"
  completed: 2026-08-05
  tasks: 2
  files_modified: 2
---

# Phase 23 Plan 03: Sync-Skew Gate and Reconnect Freshness Summary

Implemented the IK-03 sync-skew gate and reconnect-freshness guard for N-sensor IK, with per-device validity publishing on every IK cycle.

## What Was Built

### sync_skew_ms Parameter
- Added `"sync_skew_ms": 50` to `parameter_defaults` in `OpenSimBridgeNode.__init__`
- Read after `declare_parameter` loop with safe int cast: `self._sync_skew_ms = max(1, int(values["sync_skew_ms"]))`
- Configurable at launch; defaults to 50ms as specified by D-07

### _check_sync_skew(inputs)
Median-reference algorithm per D-07:
- Empty inputs → `{all_valid: False, device_validities: {}}`
- All None timestamps → all `{valid: False, skew_ms: None}`
- Otherwise: computes median of available timestamps, then for each device:
  - `skew_ms = abs(last_ts_ns - reference_ts) / 1e6`
  - `within_skew = skew_ms <= sync_skew_ms`
  - `valid = within_skew AND post_reconnect_fresh`
- `all_valid = all(v["valid"] for v in device_validities.values())`
- Pure computation — takes no locks, caller supplies snapshot

### _n_input_validity_publisher
Created for `/rehab/opensim/input_validity` (String, depth=10) in `__init__`.

### _publish_input_validity(validity)
Publishes JSON with schema `rehab.n_input_validity.1` on every call, even when IK is suppressed.

### _solve_and_publish_ik_n()
Gate sequence:
1. Snapshot `_mac_inputs` alphabetically under lock (D-03)
2. Return early if snapshot is empty
3. Call `_check_sync_skew(inputs_snapshot)`
4. Call `_publish_input_validity(validity)` — always, even if suppressing
5. Return if `not validity["all_valid"]` (acquisition path unaffected)
6. Return if `_n_calib_artifact is None` (calibration required)
7. Debug log stub for Plan 23-04 solver wire-up

### _on_mac_imu Wiring
Added `self._solve_and_publish_ik_n()` call at the end of `_on_mac_imu`, **outside** the `_input_lock`, so every new IMU frame triggers N-sensor IK evaluation.

The existing single-sensor `_solve_and_publish_ik()` path (called from `_on_imu()`) is untouched.

## Test Coverage

IkThreeContractTests (12 tests added, all passing):

| Test | Description |
|------|-------------|
| IK-03-A | Same timestamp, both fresh → all_valid=True |
| IK-03-B | 200ms device gap → both 100ms from median → exceeds 50ms limit → all_valid=False |
| IK-03-C | fresh=False on one device → valid=False even with same timestamp |
| IK-03-D | last_ts_ns=None → valid=False, skew_ms=None |
| IK-03-E | Skewed input suppresses joint_states, publishes input_validity |
| IK-03-F | All valid + calib present → gate passes, no crash |
| IK-03-G | sync_skew_ms=200 allows 50ms-from-median skew to pass |
| IK-03-H | Existing _solve_and_publish_ik() unaffected |
| edge | Empty inputs → all_valid=False, device_validities={} |
| edge | Publisher created on correct topic |
| edge | sync_skew_ms defaults to 50 |
| edge | All None timestamps → all_valid=False, all skew_ms=None |

Total test suite: 65 tests passed (53 pre-existing + 12 new), 0 regressions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] IK-03-B test used incorrect timestamp gap**
- **Found during:** Task 3 (GREEN verification)
- **Issue:** Test used 100ms device gap (each device 50ms from median), which equals the 50ms threshold exactly; `<=` makes 50ms pass, so test expected failure but got all_valid=True
- **Fix:** Changed device gap to 200ms so each device is 100ms from the median, clearly exceeding the 50ms limit
- **Files modified:** backend/test/test_opensim_node.py
- **Commit:** 5926bff (same GREEN commit)

**2. [Rule 2 - Missing stub method] _Logger stub missing debug()**
- **Found during:** Task 2 (GREEN verification)
- **Issue:** `_solve_and_publish_ik_n` calls `self.get_logger().debug(...)` for the stub log; `_Logger` in tests had no `debug()` method
- **Fix:** Added `debug()` method to `_Logger` stub in test file
- **Files modified:** backend/test/test_opensim_node.py
- **Commit:** 5926bff

## Threat Surface Scan

No new network endpoints or trust boundaries introduced. `/rehab/opensim/input_validity` publishes on the internal ROS bus only — already accounted for in T-23-03-04 (accepted: internal bus, device_ids already published on fleet registry).

The T-23-03-01 mitigation (stale device timestamp detection via median skew) is implemented and verified by IK-03-B and IK-03-D.
The T-23-03-02 mitigation (post_reconnect_fresh=False guards the case where all devices are frozen at the same timestamp) is implemented and verified by IK-03-C.

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| Solver call in `_solve_and_publish_ik_n` | opensim_node.py | after calib gate | Plan 23-04 wires actual N-sensor IK solver call |

The stub emits a debug log and returns cleanly; the N-sensor IK path is intentionally incomplete until Plan 23-04.

## Self-Check: PASSED

- `backend/rehab_robotics_bridge/opensim_node.py` — exists, contains `_check_sync_skew`, `_publish_input_validity`, `_solve_and_publish_ik_n`, `sync_skew_ms` parameter
- `backend/test/test_opensim_node.py` — exists, contains `IkThreeContractTests`
- Commits `d1f9066` (RED) and `5926bff` (GREEN) verified in git log
- 65 tests pass, 0 regressions
