---
phase: 09-range-correct-measurement-contract
plan: 01
subsystem: backend
tags: [python, unittest, measurement-contract, imu, esp32, ros2, scale-conversion, sensor-config]

# Dependency graph
requires:
  - phase: none
    provides: existing esp32_bridge_node.py, pipeline.py, test_esp32_controls.py
provides:
  - Pure stdlib measurement_contract.py with canonical ICM-20948 range tables, MeasurementConfig, and SI conversion helpers
  - Shared cross-consumer fixture (32 cases: 2 roles x 4 accel x 4 gyro, raw_count=4096)
  - test_measurement_contract.py with MeasurementContractTableTests and PublishFrameAndPipelineTests
  - Nullable confirmed range state in esp32_bridge_node; _publish_frame suppresses when config absent
  - sensor_config embedded in every published raw JSON frame
  - Native sensor_msgs/Imu values derived from confirmed config (not fixed +-2g/+-250dps constants)
  - ConfirmedRangeRetentionTests in test_esp32_controls.py
affects:
  - Phase 09 Plan 02 (TypeScript measurementContract.ts, RosbridgeDataSource.test.ts)
  - Phase 09 Plan 03 (cross-language regression)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Nullable confirmed sensor state: desired ROS param fields separate from None-initialized confirmed fields; publish suppressed until ACK"
    - "One config snapshot per published sample: build MeasurementConfig once at start of _publish_frame, use same object for raw JSON metadata and native Imu SI conversion"
    - "Shared fixture for cross-consumer proof: measurement_contract_cases.json consumed by both Python and (Phase 09-02) TypeScript tests"
    - "object.__new__ stub pattern: instantiate Esp32BridgeNode without ROS init for targeted unit tests"

key-files:
  created:
    - backend/rehab_robotics_bridge/measurement_contract.py
    - backend/test/fixtures/measurement_contract_cases.json
    - backend/test/test_measurement_contract.py
  modified:
    - backend/rehab_robotics_bridge/esp32_bridge_node.py
    - backend/test/test_esp32_controls.py

key-decisions:
  - "Nullable confirmed fields: _confirmed_accel_range_g / _confirmed_gyro_range_dps initialized to None; suppress _publish_frame output until both are set"
  - "Keep dormant ACC_LSB_PER_G / GYR_LSB_PER_DPS / ACC_SCALE / GYR_SCALE module constants for Plan 03 clean-up, not removed here"
  - "Handshake-time range confirmation: new _confirm_range_during_handshake helper sends CFG command directly on handshake writer/reader before streaming begins"
  - "Strict validate_sensor_config uses 1e-9 relative tolerance for range/sensitivity cross-check to handle JSON float round-trip"
  - "config_as_json returns canonical literal table values (not re-derived floats) to guarantee exact round-trip"

requirements-completed:
  - DATA-01
  - DATA-02

# Metrics
duration: 7min
completed: 2026-07-24
---

# Phase 9 Plan 01: Range-Correct Measurement Contract Summary

**Pure stdlib measurement_contract.py with canonical ICM-20948 range tables, strict validator, and SI conversion; nullable confirmed range state in esp32_bridge_node with sensor_config embedded in every published raw JSON frame**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-24T18:43:40Z
- **Completed:** 2026-07-24T18:49:44Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Created `measurement_contract.py` (pure stdlib, no ROS) exporting all 7 required symbols: range tables, frozen `MeasurementConfig` dataclass, `measurement_config()`, `validate_sensor_config()`, `config_as_json()`, `accel_count_to_mps2()`, `gyro_count_to_rad_s()`
- Created 32-case shared fixture `measurement_contract_cases.json` (2 roles x 4 accel x 4 gyro, raw_count=4096) with 15+ decimal place precision for cross-language use
- Refactored `esp32_bridge_node.py`: separate desired vs. nullable confirmed range fields; `_publish_frame` suppresses all output when confirmed config is absent (T-09-03); attaches `sensor_config` dict to every raw JSON frame; uses `accel_count_to_mps2` / `gyro_count_to_rad_s` for native `sensor_msgs/Imu` values
- Added `_confirm_range_during_handshake` async helper that sends CFG commands on the handshake writer/reader before streaming begins
- Added 5 `ConfirmedRangeRetentionTests` + 7 `test_measurement_contract` tests; full backend discovery: 26 tests, zero failures

## Task Commits

Each task was committed atomically:

1. **Task 1: Create measurement_contract.py and shared fixture** - `be53192` (feat)
2. **Task 2: Integrate contract into esp32_bridge_node and pipeline** - `bc7d027` (feat)
3. **Task 3: Confirmed-range retention cases in test_esp32_controls** - `2633d23` (feat)

**Plan metadata:** (this SUMMARY commit)

## Files Created/Modified

- `backend/rehab_robotics_bridge/measurement_contract.py` - Pure stdlib canonical ICM-20948 range tables, frozen MeasurementConfig, strict validator, SI conversion helpers
- `backend/test/fixtures/measurement_contract_cases.json` - 32 deterministic cases for Python and TypeScript cross-consumer proof
- `backend/test/test_measurement_contract.py` - MeasurementContractTableTests (09-01-01) + PublishFrameAndPipelineTests (09-01-02), 7 tests
- `backend/rehab_robotics_bridge/esp32_bridge_node.py` - Nullable confirmed fields, handshake CFG confirmation, sensor_config in raw_json, config-derived SI conversion
- `backend/test/test_esp32_controls.py` - Added sys.path fix for measurement_contract import, added ConfirmedRangeRetentionTests (5 tests), 12 total

## Decisions Made

- Nullable confirmed state is the correct design: `_confirmed_accel_range_g = None` until firmware ACK prevents misleading physical publication during connection setup
- The module-level fixed-scale constants (`ACC_LSB_PER_G`, `ACC_SCALE`, etc.) are kept dormant in esp32_bridge_node.py for now — Plan 03 will remove them cleanly
- `_confirm_range_during_handshake` avoids the shared `_record_command_lock` (not available during handshake) by operating directly on the handshake writer/reader
- `validate_sensor_config` uses `math.isclose(rel_tol=1e-9)` for range/sensitivity consistency to handle JSON float encoding without over-tightening

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added sys.path insertion to _load_bridge_module() in test_esp32_controls.py**
- **Found during:** Task 2 (verifying pre-existing tests after esp32_bridge_node.py added the measurement_contract import)
- **Issue:** `_load_bridge_module()` uses `importlib.util.spec_from_file_location` which loads the bridge module in isolation, without the PYTHONPATH=backend that the test runner sets. When `esp32_bridge_node.py` started importing `from rehab_robotics_bridge.measurement_contract import ...`, the module could not resolve `rehab_robotics_bridge` as a package during `exec_module`, causing an `ImportError`.
- **Fix:** Added `sys.path.insert(0, str(Path(__file__).parents[1]))` at the top of `_load_bridge_module()` to ensure backend/ is importable before the bridge module is exec'd.
- **Files modified:** `backend/test/test_esp32_controls.py`
- **Verification:** All 7 pre-existing Esp32ControlContractTests passed after the fix.
- **Committed in:** `bc7d027` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking import error)
**Impact on plan:** Single necessary fix to maintain testability after the new measurement_contract import was added to esp32_bridge_node.py. No scope creep.

## Issues Encountered

None - all tasks completed in the planned sequence. The sys.path fix was caught immediately during Task 2 acceptance verification.

## User Setup Required

None - no external service configuration required. All changes are pure Python stdlib with no new dependencies.

## Next Phase Readiness

- Backend contract seam complete: `measurement_contract.py` is ready to be consumed by the TypeScript `measurementContract.ts` module (Phase 09 Plan 02)
- The shared JSON fixture `backend/test/fixtures/measurement_contract_cases.json` is available for the TypeScript test suite
- `esp32_bridge_node.py` emits `sensor_config` on every published frame when confirmed ranges are established
- Full backend test suite green (26 tests) before moving to Plan 02
- Plan 02 blockers: none; Plan 01 artifacts are all committed and verified

---
*Phase: 09-range-correct-measurement-contract*
*Completed: 2026-07-24*
