---
phase: 26-signal-contract-and-provenance
plan: 01
subsystem: signal-contract
tags: [python, imu, provenance, calibration, immutable-data]

requires:
  - phase: 25-hardware-remap-acceptance
    provides: full-MAC fleet identity and authoritative applied mapping snapshots
provides:
  - immutable rehab.signal_sample.1 Python source of truth
  - cross-language SIG-01 through SIG-05 fixture with D-01 through D-16 traceability
  - deterministic accel, gyro, and calibration-gated magnetometer SI conversions
affects: [26-02-typescript-contract, 26-03-backend-ingestion, signal-viewer, recording-export]

tech-stack:
  added: []
  patterns: [fail-closed bounded reason codes, deeply frozen sample snapshots, calibration-gated SI]

key-files:
  created:
    - backend/rehab_robotics_bridge/signal_contract.py
    - backend/test/fixtures/signal_contract_cases.json
    - backend/test/test_signal_contract.py
  modified:
    - backend/rehab_robotics_bridge/measurement_contract.py
    - backend/test/test_measurement_contract.py

key-decisions:
  - "Canonical integers are bounded to the cross-language safe range, labels to 64 characters, and hashes to 128 characters."
  - "Quaternion storage preserves received component order and values; availability requires finite norm in [0.5, 1.5] with the existing 1e-8 near-zero guard."
  - "Magnetometer conversion uses bounded xyz calibration provenance, hard-iron subtraction, and a 3x3 soft-iron matrix before exposing µT."

patterns-established:
  - "Required envelope failures raise stable ValueError codes; channel failures remain explicit unavailable states."
  - "Canonical samples deep-copy and recursively freeze nested values, while as_dict returns detached JSON-compatible data."

requirements-completed: [SIG-01, SIG-02, SIG-03, SIG-04, SIG-05]

duration: 7min
completed: 2026-08-17
---

# Phase 26 Plan 01: Signal Contract and Provenance Summary

**Immutable full-MAC signal samples with bounded provenance, lossless int16 counts, honest timing, and calibration-gated SI/quaternion availability**

## Performance

- **Duration:** 7 min
- **Started:** 2026-08-17T01:18:01Z
- **Completed:** 2026-08-17T01:25:02Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Locked a language-neutral fixture covering SIG-01 through SIG-05 and all sixteen Phase 26 decisions with exact rejection and availability codes.
- Built a ROS-independent canonical validator that enforces full-MAC/topic agreement, honest timing origins, bounded epochs, exact int16 raw values, and applied-only mapping snapshots.
- Kept quaternion capability absence distinct from transient invalidity and preserved valid input without normalization or identity fallback.
- Extended the measurement contract so accel/gyro SI requires valid range metadata and magnetometer µT requires both sensitivity and validated calibration provenance.

## Task Commits

Each task was committed atomically:

1. **Task 1: Lock the canonical fixture and rejection taxonomy** - `40f053a` (test)
2. **Task 2: Implement immutable canonical validation** - `db671b2` (feat)
3. **Task 3: Extend deterministic SI conversion and magnetometer provenance** - `603a848` (feat)

## Files Created/Modified

- `backend/rehab_robotics_bridge/signal_contract.py` - Pure immutable builder, bounded envelope validation, and explicit SI/quaternion availability.
- `backend/test/fixtures/signal_contract_cases.json` - Shared acceptance, rejection, provenance, conversion, and decision-trace fixture.
- `backend/test/test_signal_contract.py` - Table-driven identity, timing, raw, applied mapping, quaternion, immutability, and SI tests.
- `backend/rehab_robotics_bridge/measurement_contract.py` - Immutable calibration provenance and deterministic magnetometer conversion.
- `backend/test/test_measurement_contract.py` - Backward-compatibility, calibration rejection, serialization, and conversion coverage.

## Decisions Made

- Used JavaScript's safe integer ceiling for cross-language sequence/time/epoch bounds so the Python and later TypeScript contracts cannot disagree through numeric precision.
- Preserved quaternion components exactly and applied a broad unit-quaternion acceptance band rather than normalizing received measurements.
- Selected an explicit `xyz` calibration representation with hard-iron vector and soft-iron 3x3 matrix; malformed, unbounded, or non-finite provenance yields `calibration_invalid`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None. The required stub scan found no TODO/FIXME/placeholder paths or empty values flowing into canonical output.

## TDD Gate Compliance

- RED: `40f053a` established the exact `canonical_validation_unimplemented` focused failure.
- GREEN: `db671b2` implemented canonical validation and `603a848` completed the measurement conversion behavior.

## Verification

- Focused RED: expected exit 1 with `canonical_validation_unimplemented`.
- Plan suite: 19 passed, 123 subtests passed.
- Phase 26 quick backend subset: 77 passed, 123 subtests passed.
- Full backend: 415 passed, 8 skipped, 271 subtests passed.
- Full frontend: 73 passed.
- TypeScript typecheck: passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The shared fixture and canonical Python behavior are ready for TypeScript parity in Plan 26-02.
- No blockers or new threat surfaces were identified; all new validation occurs at trust boundaries already registered in the plan threat model.

## Self-Check: PASSED

- All five created/modified contract files exist.
- Task commits `40f053a`, `db671b2`, and `603a848` exist in repository history.
- No goal-blocking stubs or unexpected tracked-file deletions were found.

---
*Phase: 26-signal-contract-and-provenance*
*Completed: 2026-08-17*
