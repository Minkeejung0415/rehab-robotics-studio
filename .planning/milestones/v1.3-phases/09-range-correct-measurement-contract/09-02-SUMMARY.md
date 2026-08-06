---
phase: 09-range-correct-measurement-contract
plan: 02
subsystem: data
tags: [typescript, node-test, measurement-contract, imu, esp32, rosbridge, scale-conversion, sensor-config, service-fix]

# Dependency graph
requires:
  - phase: 09-01
    provides: measurement_contract.py, shared JSON fixture (32 cases), sensor_config in every published raw frame
provides:
  - Pure TS measurement contract seam (measurementContract.ts) with SensorConfig type, ACCEL_LSB_PER_G, GYRO_LSB_PER_DPS, validateSensorConfig, accelCountToMps2, gyroCountToRad_s
  - Shared-fixture tests (09-02-01): 32 cases pass to 1e-9 tolerance, 10 rejection partitions all return ok=false
  - RosbridgeDataSource.ts: validate-before-cache, one-warn-per-connection latch, cache/latch reset on new start(), corrected service names, coordinated master+slave range changes
  - RosbridgeDataSource.test.ts: 6 warning/cache/emission tests + 4 service-ACK tests
  - package.json test script extended to src/data/*.test.ts
affects:
  - Phase 09 Plan 03 (cross-language regression: Python backend vs TypeScript frontend)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ValidateResult<T> discriminated union: { ok: true; value: T } | { ok: false; reason: string } — never-throw contract for unsafe network input"
    - "Validate-before-cache: sensor_config validated per-frame before masterFrame/slaveFrame updated; invalid frames silently dropped"
    - "One-warn-per-connection latch: _warnedScale boolean resets only in start() before new WebSocket"
    - "pre-converted Frame pair math: frameFromPair accepts Frame objects, not RawEspMessage; frameFromRaw now requires SensorConfig"
    - "Dual-service range coordination: accel_range_g/gyro_range_dps call both /esp_bridge_master and /esp_bridge_slave in parallel"

key-files:
  created:
    - rehab-robotics-studio/src/data/measurementContract.ts
    - rehab-robotics-studio/src/data/measurementContract.test.ts
    - rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts
  modified:
    - rehab-robotics-studio/src/data/RosbridgeDataSource.ts
    - rehab-robotics-studio/package.json

key-decisions:
  - "frameFromPair signature changed to accept pre-converted Frame objects — enforces validate-before-convert ordering at the type level"
  - "masterFrame/slaveFrame replace masterRaw/slaveRaw: only valid frames reach the pair cache"
  - "callBothRangeServices calls master and slave in parallel (Promise.all) to minimize latency; sequential would add round-trip time per range change"
  - "Compensating master restore on slave failure: logs warning rather than attempting exact restore because prior confirmed value not tracked in this plan — deferred to Plan 03 if needed"
  - "Test fixture path is ../../../backend/... (3 levels up from src/data/) not ../../../../ as specified in plan; the plan's level count was off by one"

requirements-completed:
  - DATA-01
  - DATA-02

# Metrics
duration: 6min
completed: 2026-07-24
---

# Phase 9 Plan 02: Range-Correct Measurement Contract (TypeScript) Summary

**Pure TS measurementContract.ts seam with strict discriminated-union validator, per-config SI conversion, and RosbridgeDataSource validate-before-cache with corrected /esp_bridge_master and /esp_bridge_slave service names**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-24T18:52:41Z
- **Completed:** 2026-07-24T18:58:18Z
- **Tasks:** 2 (09-02-01 and combined 09-02-02/09-02-03)
- **Files modified:** 5

## Accomplishments

- Created `measurementContract.ts`: pure TS module with SensorConfig type, range tables matching Python exactly, validateSensorConfig (never throws, returns ValidateResult), accelCountToMps2, gyroCountToRad_s
- All 32 shared-fixture cases verified to 1e-9 tolerance; all 10 rejection partitions return ok=false
- Rewrote `RosbridgeDataSource.ts`: validate sensor_config before caching masterFrame/slaveFrame; _warnedScale latch fires at most once per connection; reset on start(); corrected service name to /esp_bridge_master/set_parameters; accel_range_g and gyro_range_dps call both master and slave services
- Added `RosbridgeDataSource.test.ts`: 10 tests covering all warning/cache/emission behaviors and service-name/ACK coordination
- Extended `package.json` test script to include `src/data/*.test.ts`
- Full suite: 17 tests across 5 suites, zero failures; `npm run typecheck` zero errors

## Task Commits

Each task was committed atomically:

1. **Task 1 (09-02-01): Create measurementContract.ts and shared-fixture tests** - `b914628` (feat)
2. **Task 2 (09-02-02, 09-02-03): Integrate contract into RosbridgeDataSource and add tests** - `f937d2d` (feat)

**Plan metadata:** (this SUMMARY commit)

## Files Created/Modified

- `rehab-robotics-studio/src/data/measurementContract.ts` - Pure TS canonical ICM-20948 range tables, ValidateResult discriminated union, strict validator (never throws), SI conversion helpers
- `rehab-robotics-studio/src/data/measurementContract.test.ts` - 3 tests: 32 shared-fixture cases to 1e-9, canonical accept, 10 rejection partitions
- `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` - Removed fixed scales; validate-before-cache; _warnedScale latch; onWarnScaleMissing callback; frameFromRaw(config) / frameFromPair(Frame,Frame); corrected service names; dual-service range coordination
- `rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts` - 10 tests: 6 warning/cache/emission + 4 service-name/ACK
- `rehab-robotics-studio/package.json` - Extended test script to include src/data/*.test.ts

## Decisions Made

- Changed `frameFromPair` to accept pre-converted `Frame` objects instead of `RawEspMessage` — this enforces validate-before-convert at the type level; the old signature would have required re-deriving frames from raw messages after validation had already occurred
- Used `ValidateResult<T>` discriminated union (never-throw contract) to match the DATA-02 requirement that untrusted network input never propagates exceptions to callers
- `callBothRangeServices` runs master and slave calls in `Promise.all` for minimum latency; partial failure logs a warning instead of attempting exact value restore (prior confirmed value not tracked)
- Fixture path in plan was incorrect: plan said 4 levels (`../../../../`) but from `src/data/` only 3 levels (`../../../`) reach the project root; corrected automatically (Rule 1 deviation)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixture path depth was off by one level**
- **Found during:** Task 1 (09-02-01) first test run
- **Issue:** The plan specified `'../../../../backend/test/fixtures/...'` (4 levels up from `src/data/`) but that resolves to `Documents/backend/...` not the project root. The project root is 3 levels up from `src/data/`.
- **Fix:** Changed path to `'../../../backend/test/fixtures/measurement_contract_cases.json'`
- **Files modified:** `rehab-robotics-studio/src/data/measurementContract.test.ts`
- **Verification:** `npm exec -- tsx --test src/data/measurementContract.test.ts` — all 3 tests pass
- **Committed in:** `b914628` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 path bug)
**Impact on plan:** Single necessary correction to the fixture path depth. No scope creep.

## Issues Encountered

None - all tests passed after the fixture path fix. TypeScript typecheck clean.

## User Setup Required

None - no external service configuration required. All changes are pure TypeScript with no new npm dependencies.

## Next Phase Readiness

- TypeScript measurement contract complete: `measurementContract.ts` ready for Phase 09-03 cross-language regression
- The shared fixture `backend/test/fixtures/measurement_contract_cases.json` is now consumed by both Python (09-01) and TypeScript (09-02) test suites
- `RosbridgeDataSource.ts` correctly targets `/esp_bridge_master/set_parameters` and `/esp_bridge_slave/set_parameters`
- Full test suite green (17 tests across 5 suites) before moving to Plan 03
- Plan 03 can close out the regression and verify backend/frontend SI values agree on identical raw counts

## Self-Check

- [x] `rehab-robotics-studio/src/data/measurementContract.ts` exists on disk
- [x] `rehab-robotics-studio/src/data/measurementContract.test.ts` exists on disk
- [x] `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` modified
- [x] `rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts` exists on disk
- [x] `rehab-robotics-studio/package.json` test script updated
- [x] Commit `b914628` (Task 1) exists in git log
- [x] Commit `f937d2d` (Task 2) exists in git log
- [x] `npm test` — 17 pass, 0 fail
- [x] `npm run typecheck` — zero errors

## Self-Check: PASSED

---
*Phase: 09-range-correct-measurement-contract*
*Completed: 2026-07-24*
