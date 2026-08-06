---
phase: 19-studio-controls-live-angle
plan: "03"
subsystem: frontend-rosbridge-opensim-integration
tags: [typescript, rosbridge, zustand, opensim, joint-state, session-generation]

requires:
  - phase: 19-studio-controls-live-angle
    plan: "01"
    provides: Fixed backend-owned visualizer Trigger and persistent visualization status
  - phase: 19-studio-controls-live-angle
    plan: "02"
    provides: Fail-closed live knee angle tracker and typed OpenSim snapshots
provides:
  - Distinct validated subscriptions for OpenSim status, IK status, and JointState
  - Fixed 10-second visualizer Trigger facade with retry-safe settlement
  - Generation and socket identity guards for callbacks, replies, disconnects, and timeouts
  - Persistent Zustand snapshots wired through the live knee angle tracker
affects: [19-04, 19-05, studio-toolbar, health-panel, live-angle-display]

tech-stack:
  added: []
  patterns:
    - "Validate untrusted topic payloads at the rosbridge boundary before state mutation"
    - "Bind every asynchronous transport operation to both connection generation and socket identity"
    - "Log state transitions by normalized signature instead of logging data frames"

key-files:
  created: []
  modified:
    - rehab-robotics-studio/src/data/DataSource.ts
    - rehab-robotics-studio/src/data/RosbridgeDataSource.ts
    - rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts
    - rehab-robotics-studio/src/data/appDataSource.ts
    - rehab-robotics-studio/src/state/systemStore.ts

key-decisions:
  - "Status and IK status remain independent String JSON contracts while JointState uses its native sensor message envelope."
  - "Only backend Opening/Open status clears a settled visualizer request failure."
  - "Disconnect settles pending work for its own generation; obsolete callbacks never settle current work."

patterns-established:
  - "OpenSim transport parsers return null on malformed input and copy only validated bounded fields."
  - "The application facade feeds each accepted snapshot through one persistent LiveKneeAngleTracker."

requirements-completed: [VIS-01, VIS-02, IK-06]

duration: 9min
completed: 2026-07-28
---

# Phase 19 Plan 03: Reconnect-Safe OpenSim Transport Summary

**Typed rosbridge routing now drives the fail-closed OpenSim knee tracker and retryable visualizer request state without allowing obsolete sessions or malformed payloads to mutate the current view model.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-28T20:25:30Z
- **Completed:** 2026-07-28T20:34:45Z
- **Tasks:** 1
- **Files modified:** 5

## Accomplishments

- Subscribed independently to `/opensim/status`, `/opensim/ik_status`, and `/opensim/joint_states`, with topic-specific structural validation and bounded reason normalization.
- Added the fixed `/opensim/visualizer/open` Trigger facade with exact 10-second timeout copy, duplicate settlement protection, and retry behavior.
- Bound socket callbacks, service replies, disconnect settlement, and timeout callbacks to both a monotonically increasing generation and the originating WebSocket.
- Wired validated status, IK, and JointState snapshots through `LiveKneeAngleTracker` into distinct Zustand fields with transition-only logs.
- Preserved the complete recorded untracked `DataSource.ts` and `systemStore.ts` baselines while patching them narrowly in place.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add typed rosbridge routing, Trigger facade, and session guards** - `1363f7a` (feat)

## Files Created/Modified

- `rehab-robotics-studio/src/data/DataSource.ts` - Adds the narrow argument-free OpenSim visualizer control interface beside the acquisition contract.
- `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` - Validates three topic contracts, calls the fixed Trigger, and enforces generation/socket guards.
- `rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts` - Proves malformed rejection, distinct routing, timeout/retry, duplicate settlement, disconnect, reconnect, and obsolete callback behavior.
- `rehab-robotics-studio/src/data/appDataSource.ts` - Connects validated snapshots to the tracker/store and exposes the deduplicated application visualizer facade.
- `rehab-robotics-studio/src/state/systemStore.ts` - Persists distinct OpenSim, IK, JointState, live-angle, and request snapshots with deduplicated transition logs.

## Decisions Made

- Used both generation and exact socket identity as the session boundary; neither token alone is relied on.
- Kept visualizer input argument-free and fixed to the backend-owned Trigger service.
- Retained request failure through unrelated/unavailable backend updates and cleared it only when the backend reports `opening` or `open`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved existing calibration response casing**
- **Found during:** Task 1 targeted regression test
- **Issue:** Applying the new display normalization in the shared service helper changed the existing response `capturing` to `Capturing`.
- **Fix:** Added a bounded safe service-message helper that preserves existing casing, while retaining sentence-cased normalization on the new visualizer and OpenSim reason paths.
- **Files modified:** `rehab-robotics-studio/src/data/RosbridgeDataSource.ts`
- **Verification:** Final targeted suite passes 26/26, including the pre-existing calibration Trigger assertions.
- **Committed in:** `1363f7a`

---

**Total deviations:** 1 auto-fixed bug.
**Impact on plan:** Compatibility was restored without changing scope or weakening validation.

## Issues Encountered

- `npm run typecheck` reaches one pre-existing unchanged error in `src/components/dashboard/calibrationStatus.ts:14` (`string | number` is not assignable to `string`). The same out-of-scope error was documented by Plan 19-02; no Plan 19-03 file reports a type error.

## Known Stubs

None.

## Verification

- `npm exec -- tsx --test src/data/RosbridgeDataSource.test.ts`
  - Result: 26 passed, 0 failed.
- `npm run typecheck`
  - Result: Plan 19-03 files pass; command remains blocked only by the pre-existing `calibrationStatus.ts:14` error.
- `git diff --check -- <three tracked task paths>`
  - Result: passed; only existing line-ending conversion warnings were reported.
- Exact-path staging contained only the five planned files, and source commit `1363f7a` deleted no tracked files.
- `.planning/phases/19-studio-controls-live-angle/19-WORKTREE-BASELINE.local.md` remains untracked and unstaged.

## Threat Model

- T-19-05 mitigated with independent structural validators before callback dispatch.
- T-19-07 mitigated with generation plus socket identity on callbacks, replies, disconnects, and timeouts.
- T-19-10 mitigated with early rejection and transition-only logging.
- T-19-11 mitigated with bounded normalized reasons that reject raw objects, JSON, multiline text, and sentinel strings.
- No unplanned security-relevant surface was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for Plan 19-04 to consume persistent store snapshots in the Studio view model.
- The known unrelated `calibrationStatus.ts` typecheck issue remains in its owning scope.

## Self-Check: PASSED

- All five modified key files exist.
- Task commit `1363f7a` exists in git history.
- Targeted verification passes 26/26.
- The preservation baseline remains untracked and unstaged.

---
*Phase: 19-studio-controls-live-angle*
*Completed: 2026-07-28*
