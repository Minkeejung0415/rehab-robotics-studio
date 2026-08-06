---
phase: 19-studio-controls-live-angle
plan: "04"
subsystem: frontend-product-angle-routing
tags: [typescript, zustand, opensim, signal-bus, fail-closed]

requires:
  - phase: 19-studio-controls-live-angle
    plan: "02"
    provides: Fail-closed live knee angle tracker and discriminated snapshot
  - phase: 19-studio-controls-live-angle
    plan: "03"
    provides: Persistent Zustand live-angle state driven by validated rosbridge contracts
provides:
  - Stable default B8 graph block backed only by gated official OpenSim IK
  - Nullable SignalBus knee snapshot with empty and immediately cleared history
  - Recovery series isolation and rejection of custom, cached, or frame-injected values
affects: [19-05, motor-panel, block-node, product-knee-readout]

tech-stack:
  added: []
  patterns:
    - "Overwrite untrusted frame product fields from the independently gated store snapshot"
    - "Clear nullable telemetry and history synchronously whenever its trust gate closes"

key-files:
  created: []
  modified:
    - rehab-robotics-studio/src/state/graphStore.ts
    - rehab-robotics-studio/src/graph/blockDefinitions.ts
    - rehab-robotics-studio/src/graph/mockExecutor.ts
    - rehab-robotics-studio/src/graph/productKneeReadout.test.ts
    - rehab-robotics-studio/src/data/signalBus.ts

key-decisions:
  - "Retain the opensim_ik_waiting type identifier for saved-document compatibility while promoting its behavior and label to official OpenSim IK."
  - "SignalBus accepts a graph knee result only when it is finite and exactly matches the current live official store value."
  - "A closed gate synchronously nulls the snapshot and clears the entire knee series; valid recovery starts from an empty buffer."

patterns-established:
  - "Valid zero is tested by finiteness and gate state, never by truthiness."
  - "DataSource-provided openSimKneeAngleDeg is always overwritten before graph execution."

requirements-completed: [VIS-02, IK-06]

duration: 10min
completed: 2026-07-28
---

# Phase 19 Plan 04: Gated Product IK Routing Summary

**The stable B8 graph path and SignalBus now expose only the independently gated official OpenSim knee angle, with nullable snapshots and gap-safe history clearing.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-28T20:37:04Z
- **Completed:** 2026-07-28T20:47:46Z
- **Tasks:** 1
- **Files modified:** 5

## Accomplishments

- Promoted the saved-document-compatible `opensim_ik_waiting` B8 block to the visible `OpenSim IK` source while preserving its identifier, position, ports, and B9 edge.
- Routed only finite `Frame.openSimKneeAngleDeg` values through B8; deprecated `jointAngleDeg` remains confined to the explicit debug block.
- Subscribed SignalBus to the derived Zustand live-angle snapshot and overwrote any DataSource-supplied product field before graph execution.
- Made `kneeAngle` nullable, initialized knee history empty, preserved valid zero, and synchronously cleared value/history on invalid, unavailable, or stale state.
- Added deterministic coverage for B8-to-display routing, malicious custom/frame values, valid zero/nonzero, immediate stale clearing, and fresh-series recovery.

## Task Commits

Each task was committed atomically:

1. **Task 1: Route the gated IK-06 value through the default graph and SignalBus** - `f89ae44` (feat)

## Files Created/Modified

- `rehab-robotics-studio/src/state/graphStore.ts` - Documents stable B8 type-id compatibility for the promoted product source.
- `rehab-robotics-studio/src/graph/blockDefinitions.ts` - Presents B8 as official OpenSim IK rather than a waiting placeholder.
- `rehab-robotics-studio/src/graph/mockExecutor.ts` - Emits B8 output only from finite `openSimKneeAngleDeg`.
- `rehab-robotics-studio/src/graph/productKneeReadout.test.ts` - Proves official-only graph routing and SignalBus clear/recovery behavior.
- `rehab-robotics-studio/src/data/signalBus.ts` - Adds store-gated injection, nullable snapshots, empty history, immediate clearing, and deterministic test seams.

## Decisions Made

- Kept the historical `opensim_ik_waiting` type string to avoid invalidating serialized graph documents; only its product behavior and user-facing name changed.
- Required executor output to equal the current gated store value before it can enter the product snapshot, preventing custom, mock, cached, or injected alternatives from surfacing.
- Published gate closure immediately instead of waiting for the 30 fps animation-frame throttle.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added a path-safe Vite SSR test junction**
- **Found during:** Task 1 targeted SignalBus integration test
- **Issue:** Vite cannot resolve module URLs from the repository path because it contains `#`.
- **Fix:** The test creates a disposable junction under the OS temp directory with symlink preservation and dependency discovery disabled, then removes it after the assertion.
- **Files modified:** `rehab-robotics-studio/src/graph/productKneeReadout.test.ts`
- **Verification:** Final targeted run passes 19/19.
- **Committed in:** `f89ae44`

---

**Total deviations:** 1 auto-fixed blocking issue.
**Impact on plan:** Test infrastructure only; production behavior and dependency scope are unchanged.

## Issues Encountered

- `npm run typecheck` reaches the known pre-existing `calibrationStatus.ts:14` mismatch and the expected nullable-consumer errors in `BlockNode.tsx:36` and `MotorPanel.tsx:17`. Those two consumers are explicitly owned by dependent Plan 19-05; changing them here would violate the five-path staging contract. No Plan 19-04 source file reports a type error.

## Known Stubs

None.

## Verification

- `npm exec -- tsx --test src/graph/productKneeReadout.test.ts src/data/liveKneeAngle.test.ts`
  - Result: 19 passed, 0 failed.
- `npm run typecheck`
  - Result: Plan 19-04 files pass; the command remains blocked by one pre-existing error and two downstream Plan 19-05 nullable readout updates.
- `git diff --check -- <five exact task paths>`
  - Result: passed; only existing line-ending conversion warnings were reported.
- Exact-path staging contained only the five planned source files.
- Source commit `f89ae44` deleted no tracked files.
- The recorded `signalBus.ts` baseline SHA-256 (`8c6c2d21...f855f8`, 4,054 bytes, 151 lines) matched before editing, and the complete baseline was patched in place.
- `.planning/phases/19-studio-controls-live-angle/19-WORKTREE-BASELINE.local.md` remains untracked and unstaged.

## Threat Model

- T-19-13 mitigated by synchronous snapshot/history clearing on every closed live-angle gate.
- T-19-19 mitigated by nullable state, empty initial knee history, and explicit finite checks that preserve a real zero.
- No custom relative-quaternion, mock IK, cached value, or DataSource-injected product value can enter the default product path.
- No new production network, authentication, file-access, or schema trust boundary was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for Plan 19-05 to render the nullable snapshot in MotorPanel and BlockNode and clear the visual chart.
- The known nullable-consumer typecheck errors are intentionally resolved by that dependent plan.

## Self-Check: PASSED

- All five planned source paths exist.
- Source commit `f89ae44` exists and contains exactly the five planned paths.
- Targeted graph/data verification passes 19/19.
- No tracked files were deleted.
- Preservation evidence remains untracked and unstaged.

---
*Phase: 19-studio-controls-live-angle*
*Completed: 2026-07-28*
