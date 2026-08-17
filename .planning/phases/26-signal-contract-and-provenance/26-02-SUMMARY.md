---
phase: 26-signal-contract-and-provenance
plan: 02
subsystem: signal-contract
tags: [typescript, validation, immutable-data, provenance, calibration]

requires:
  - phase: 26-01
    provides: Python canonical contract and shared D-01 through D-16 fixture
provides:
  - readonly canonical browser signal interfaces distinct from legacy Frame
  - strict unknown-to-canonical parser with stable bounded rejection codes
  - Python-parity measurement validation and calibration-gated magnetometer conversion
affects: [26-04-browser-ingress, signal-viewer, recording-export]

tech-stack:
  added: []
  patterns: [node:test shared fixtures, fail-closed unknown parsing, deep-frozen detached samples]

key-files:
  created:
    - rehab-robotics-studio/src/data/signalContract.ts
    - rehab-robotics-studio/src/data/signalContract.test.ts
  modified:
    - rehab-robotics-studio/src/types/signals.ts
    - rehab-robotics-studio/src/data/measurementContract.ts
    - rehab-robotics-studio/src/data/measurementContract.test.ts

key-decisions:
  - "The browser parser validates both the shared pre-canonical fixture shape and the serialized canonical wire envelope while producing one deeply frozen CanonicalSignalSample."
  - "Canonical wire availability must agree with declared capabilities; unknown codes and capability contradictions reject with bounded contract reasons."
  - "Magnetometer microtesla conversion remains unavailable unless positive sensitivity and strict bounded rehab.mag_calibration.1 provenance both validate."

requirements-completed: [SIG-01, SIG-02, SIG-03, SIG-04, SIG-05]

duration: 8min
completed: 2026-08-17
---

# Phase 26 Plan 02: TypeScript Signal Contract Summary

**Strict, deeply frozen browser signal samples with full-MAC provenance, lossless raw counts, explicit availability, and Python-parity measurement conversions**

## Performance

- **Duration:** 8 min
- **Started:** 2026-08-17T01:28:08Z
- **Completed:** 2026-08-17T01:36:13Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added readonly canonical identity, timing, epoch, capability, raw-channel, SI, quaternion, applied-mapping, availability, and rejection types without changing legacy `Frame` or `ImuData`.
- Mirrored Python calibration validation and deterministic accel, gyro, and magnetometer conversions; sensitivity alone cannot authorize microtesla.
- Implemented ordered unknown-input guards for full-MAC/topic agreement, safe integers, exact int16 channels, explicit capabilities, bounded applied provenance, conversion availability, and quaternion validity.
- Deep-copied and recursively froze accepted samples so later input or store mutation cannot relabel buffered history.
- Loaded the Plan 01 fixture directly in Node tests and covered every D-01 through D-16 decision with exact acceptance and rejection parity.

## Task Commits

1. **Task 1: Define readonly browser contracts and parity tests** - `b742d2c` (test)
2. **Rule 1 fix: Keep parity assertions type-safe** - `add5afe` (fix)
3. **Task 2: Mirror deterministic measurement validation** - `6d2ef68` (feat)
4. **Task 3: Implement the strict canonical parser** - `1c7c337` (feat)

## Decisions Made

- Accepted canonical objects are detached and deeply frozen at the trust boundary, not merely typed readonly at compile time.
- Serialized canonical envelopes are validated for exact units, finite values, allowlisted reasons, and capability agreement; the parser never fabricates acquisition time, SI data, or orientation.
- Existing verbose measurement-config validation remains source compatible, while new calibration and conversion paths return stable `calibration_missing`, `calibration_invalid`, and `raw_field_invalid` results.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected Node assertion overloads exposed by full typecheck**
- **Found during:** Task 2 verification
- **Issue:** The Task 1 RED assertions passed `undefined` as a conditional message, which executed correctly but violated the installed Node type overloads.
- **Fix:** Supplied deterministic string messages while preserving the exact `canonical_parser_unimplemented` RED behavior.
- **Files modified:** `rehab-robotics-studio/src/data/signalContract.test.ts`
- **Verification:** Frontend `tsc --noEmit` passed.
- **Commit:** `add5afe`

**Total deviations:** 1 auto-fixed bug. **Impact:** Type-only correction; no contract behavior changed.

## Issues Encountered

None.

## Known Stubs

None. The temporary `canonical_parser_unimplemented` RED marker was removed by Task 3, and the required scan found no goal-blocking placeholders or empty data paths.

## TDD Gate Compliance

- RED: `b742d2c` established the focused `canonical_parser_unimplemented` failure through the real public parser API.
- GREEN: `6d2ef68` completed deterministic measurement parity and `1c7c337` completed strict canonical parsing.

## Verification

- Focused RED: exit 1 with `canonical_parser_unimplemented` and successful test discovery.
- Python contracts: 19 passed, 123 subtests passed.
- TypeScript contracts: 42 passed across 3 suites.
- Frontend typecheck: passed.
- Diff whitespace check: passed.

## User Setup Required

None - no dependencies or external services were added.

## Next Phase Readiness

- The canonical browser boundary is ready for per-MAC rosbridge routing in Plan 26-04 after Plan 26-03 emits the nested backend envelope.
- Legacy rosbridge `Frame` parsing remains intentionally untouched.

## Self-Check: PASSED

- All five plan-created/modified contract files exist.
- Task commits `b742d2c`, `6d2ef68`, and `1c7c337`, plus deviation commit `add5afe`, exist in repository history.
- No unexpected tracked-file deletions or goal-blocking stubs were found.

---
*Phase: 26-signal-contract-and-provenance*
*Completed: 2026-08-17*
