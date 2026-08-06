---
phase: 19-studio-controls-live-angle
plan: "02"
subsystem: frontend-opensim-angle-contract
tags: [typescript, opensim, joint-state, monotonic-time, fail-closed]

requires:
  - phase: 18-realtime-opensim-ik-outputs
    provides: Calibrated `/opensim/joint_states`, IK validity, calibration identity, and source stamps
provides:
  - Explicit frontend IK, JointState, ROS stamp, visualizer-request, and live-angle snapshot types
  - Pure calibrated and identity-matched `knee_angle_r` radians-to-degrees derivation
  - Monotonic 2,000 ms freshness tracker with ordered-stamp watermarking
  - Transition-only notification seam and deterministic gate/timer tests
affects: [19-03, 19-04, 19-05, studio-live-angle, rosbridge]

tech-stack:
  added: []
  patterns:
    - "Fail-closed discriminated snapshot keeps unavailable data distinct from a valid zero"
    - "ROS stamps remain bounded integer pairs and compare lexicographically"
    - "Injected monotonic clock and scheduler make stale transitions deterministic"

key-files:
  created:
    - rehab-robotics-studio/src/data/liveKneeAngle.ts
    - rehab-robotics-studio/src/data/liveKneeAngle.test.ts
  modified:
    - rehab-robotics-studio/src/types/health.ts
    - rehab-robotics-studio/src/types/signals.ts

key-decisions:
  - "Never combine ROS sec/nanosec into a JavaScript nanosecond integer; validate and compare the pair lexicographically."
  - "Only structurally valid JointState samples advance the ordering watermark, preventing malformed future-stamp samples from poisoning recovery."
  - "Calibration closure clears both the cached JointState and accepted-stamp watermark."

patterns-established:
  - "Product angle state is live, waiting, invalid, or stale; only live carries a finite degree value."
  - "Transition callbacks deduplicate the exact state/reason signature while fresh samples replace the stale timer."

requirements-completed: [VIS-02, IK-06]

duration: 6min
completed: 2026-07-28
---

# Phase 19 Plan 02: Fail-Closed Live Angle Contract Summary

**A typed frontend contract now exposes `knee_angle_r` only from calibrated, identity-matched, finite, ordered, and locally fresh OpenSim JointState data.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-28T20:17:20Z
- **Completed:** 2026-07-28T20:23:04Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments

- Added explicit rosbridge-friendly IK status, validated ROS stamp, JointState, visualizer-request, and discriminated live-angle types.
- Added a pure derivation that converts radians once, preserves valid zero, and returns `null` for every closed trust gate.
- Added a tracker that clears state with calibration, rejects reordered samples, replaces stale timers, and emits only state/reason transitions.
- Proved the 1,999/2,001 ms boundary, coordinate reordering, bad stamps, identity mismatch, malformed watermark resistance, stale recovery, and transition coalescing with 14 deterministic tests.

## Task Commits

Each task was committed atomically:

1. **Task 1: Define and prove the fail-closed live-angle contract** - `eb18aec` (feat)

## Files Created/Modified

- `rehab-robotics-studio/src/data/liveKneeAngle.ts` - Pure gate, stamp validation/order helpers, reason normalization, and injected timer tracker.
- `rehab-robotics-studio/src/data/liveKneeAngle.test.ts` - Deterministic gate, timer, recovery, ordering, security, and transition tests.
- `rehab-robotics-studio/src/types/health.ts` - Typed IK, JointState, ROS stamp, visualizer request, and live-angle snapshots.
- `rehab-robotics-studio/src/types/signals.ts` - Separate nullable official OpenSim knee field while retaining the deprecated debug field.

## Decisions Made

- Kept source time as `{sec, nanosec}` throughout the view model so large ROS timestamps never lose integer precision.
- Advanced the ordering watermark only for structurally usable finite knee samples; malformed messages fail closed without locking out later valid data.
- Scheduled expiry for the first millisecond beyond the inclusive 2,000 ms live boundary.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The initial test run exposed two assertion-shape issues: exact floating-point comparison at 60 degrees and a count that conflated distinct invalid reasons. Both assertions were corrected to match the state/reason contract; the final targeted suite passes.
- `npm run typecheck` remains blocked by a pre-existing, unchanged return-type mismatch in `src/components/dashboard/calibrationStatus.ts:14`. It is outside the four-path plan scope and does not affect the targeted contract test.

## Known Stubs

None.

## Verification

- `npm exec -- tsx --test src/data/liveKneeAngle.test.ts`
  - Result: 14 tests passed, 0 failed.
- `git diff --check -- <four exact task paths>`
  - Result: passed; only existing line-ending conversion warnings were reported.
- Exact-path staging contained only the four planned files.
- No tracked files were deleted by task commit `eb18aec`.
- The Phase 19 preservation baseline remains untracked and unstaged.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for Plan 19-03 to parse the three independent rosbridge topics and feed validated snapshots into this contract.
- The unrelated `calibrationStatus.ts` typecheck issue remains for its owning scope; the plan-required targeted verification is green.

## Self-Check: PASSED

- All four key files exist.
- Task commit `eb18aec` exists in git history.
- The committed targeted suite passes 14/14.
- `.planning/phases/19-studio-controls-live-angle/19-WORKTREE-BASELINE.local.md` remains untracked and unstaged.

---
*Phase: 19-studio-controls-live-angle*
*Completed: 2026-07-28*
