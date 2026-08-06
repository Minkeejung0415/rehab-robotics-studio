---
phase: 19-studio-controls-live-angle
plan: "06"
subsystem: frontend-live-angle-rendering
tags: [react, typescript, accessibility, opensim, canvas, fail-closed]

requires:
  - phase: 19-studio-controls-live-angle
    plan: "02"
    provides: Fail-closed live knee angle contract and deterministic freshness tracker
  - phase: 19-studio-controls-live-angle
    plan: "04"
    provides: Nullable official product value with immediate SignalBus history clearing
  - phase: 19-studio-controls-live-angle
    plan: "05"
    provides: Approved toolbar and persistent OpenSim health surfaces
provides:
  - One shared one-decimal nullable product-angle formatter for dashboard and diagram
  - Immediate empty-chart selection with finite-only recovery traces
  - Accessible unavailable copy and approved purple live-angle treatment
  - Responsive no-wrap toolbar behavior and protected diagram readout spacing
affects: [19-07, studio-live-angle, motor-panel, block-node, production-preview]

tech-stack:
  added: []
  patterns:
    - "Format nullable telemetry through one pure fail-closed display contract"
    - "Select chart history only while the current value and every buffered point are finite"

key-files:
  created:
    - rehab-robotics-studio/src/components/dashboard/MotorPanel.tsx
  modified:
    - rehab-robotics-studio/src/components/canvas/BlockNode.tsx
    - rehab-robotics-studio/src/data/liveKneeAngle.ts
    - rehab-robotics-studio/src/data/liveKneeAngle.test.ts
    - rehab-robotics-studio/src/styles/app.css
    - rehab-robotics-studio/src/components/dashboard/calibrationStatus.ts
    - rehab-robotics-studio/src/components/dashboard/HealthPanel.tsx

key-decisions:
  - "Treat only finite nullable SignalBus values as displayable; valid zero formats as 0.0 deg while every closed state formats as an em dash without a unit."
  - "Keep MiniChart unchanged and pass it an explicitly empty series whenever the product gate is closed or buffered data is non-finite."
  - "Expose textual live/unavailable state through data-state and visible copy without making high-frequency numeric updates a live region."

patterns-established:
  - "Dashboard and diagram angle surfaces consume formatLiveKneeAngle instead of calling toFixed independently."
  - "A recovered official value receives only the new finite SignalBus trace, never the pre-closure history."

requirements-completed: [VIS-02, IK-06]

duration: 5min
completed: 2026-07-28
---

# Phase 19 Plan 06: Nullable Live Angle Rendering Summary

**Dashboard and diagram now share a finite-only one-decimal OpenSim knee display, with immediate empty-chart behavior and a fresh purple trace after recovery.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-28T21:08:10Z
- **Completed:** 2026-07-28T21:13:32Z
- **Tasks:** 1
- **Files modified:** 7

## Accomplishments

- Added `formatLiveKneeAngle` so both product readouts distinguish a valid `0.0 deg` from unavailable `—` plus `Waiting for calibrated IK`.
- Added finite-only chart-series selection, preserving SignalBus's synchronous clear and new-series recovery behavior while leaving `MiniChart`'s clear-before-empty implementation untouched.
- Applied the approved 22px monospaced purple live value, 10px wrapped waiting copy, protected node height, and non-wrapping horizontally scrollable toolbar contract.
- Restored the phase-level TypeScript and production build gates with two minimal behavior-preserving return-type corrections.

## Task Commits

Each task and required blocker fix was committed atomically:

1. **Rule 3 blocker: calibration status return type** - `68949f0` (fix)
2. **Rule 3 blocker: HealthPanel display return type** - `e0b55be` (fix)
3. **Task 1: Render and style the shared nullable product angle** - `59c7342` (feat)

## Files Created/Modified

- `rehab-robotics-studio/src/components/dashboard/MotorPanel.tsx` - Uses the shared formatter, visible waiting copy, and gated purple knee trace.
- `rehab-robotics-studio/src/components/canvas/BlockNode.tsx` - Uses the identical display contract and reserves enough angle-body height to avoid port overlap.
- `rehab-robotics-studio/src/data/liveKneeAngle.ts` - Defines the shared finite-only formatter and chart-series selector.
- `rehab-robotics-studio/src/data/liveKneeAngle.test.ts` - Proves one-decimal values, valid zero, unavailable states, immediate clearing, non-finite rejection, and fresh recovery.
- `rehab-robotics-studio/src/styles/app.css` - Adds approved angle typography/color/layout and responsive toolbar rules atop the preserved baseline.
- `rehab-robotics-studio/src/components/dashboard/calibrationStatus.ts` - Narrows the calibration display fallback to its existing string behavior.
- `rehab-robotics-studio/src/components/dashboard/HealthPanel.tsx` - Makes the existing rendered display helper's string return explicit.

## Decisions Made

- Kept formatting at the final UI boundary so every readout has identical precision, units, unavailable copy, and non-finite rejection.
- Reused the already-proven nullable SignalBus instead of subscribing readout components directly to high-rate transport state.
- Preserved the untracked `MiniChart.tsx` byte-for-byte because its existing canvas clear occurs before the empty-series early return.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Corrected the documented calibration status return type**
- **Found during:** Task 1 typecheck verification
- **Issue:** `calibrationStatus.ts:14` inferred `string | number` for a contract that promises `string`.
- **Fix:** Narrowed its fallback parameter to the string value already used by the helper.
- **Files modified:** `rehab-robotics-studio/src/components/dashboard/calibrationStatus.ts`
- **Verification:** HealthPanel formatter tests pass, `npm run typecheck` passes, and the production build passes.
- **Committed in:** `68949f0`

**2. [Rule 3 - Blocking] Corrected the dependent HealthPanel display return type**
- **Found during:** Task 1 typecheck verification
- **Issue:** Plan 19-05's local display helper exposed the same inferred `string | number` mismatch at two string view-model fields.
- **Fix:** Explicitly stringified the fallback just as JSX already did during rendering, without changing visible output.
- **Files modified:** `rehab-robotics-studio/src/components/dashboard/HealthPanel.tsx`
- **Verification:** Six HealthPanel/calibration tests pass, `npm run typecheck` passes, and the production build passes.
- **Committed in:** `e0b55be`

---

**Total deviations:** 2 auto-fixed blocking issues (Rule 3).
**Impact on plan:** Both changes are minimal type corrections required to make the mandated phase build green; no UI behavior or architecture changed.

## Issues Encountered

- Vite continues to warn that the repository path contains `#` and that `appDataSource.ts` has both static and dynamic importers. Both are pre-existing non-fatal warnings; the production build completes successfully.

## Known Stubs

None.

## Verification

- `npm exec -- tsx --test src/data/liveKneeAngle.test.ts`
  - Result: 16 passed, 0 failed.
- `npm exec -- tsx --test src/data/liveKneeAngle.test.ts src/graph/productKneeReadout.test.ts`
  - Result: 21 passed, 0 failed, including synchronous clear and new-series recovery.
- `npm exec -- tsx --test src/data/liveKneeAngle.test.ts src/components/dashboard/HealthPanel.test.ts`
  - Result: 22 passed, 0 failed.
- `npm run typecheck`
  - Result: passed with no TypeScript errors.
- `npm run build`
  - Result: passed; Vite transformed 163 modules and emitted the production bundle.
- Source acceptance checks confirm both components import `formatLiveKneeAngle`, neither has an unconditional knee `toFixed`, and neither reads custom/mock fields or untrusted markup.
- The feature commit contains exactly the five planned paths. The two blocker commits each contain only their explicitly authorized path.
- The recorded `MotorPanel.tsx` and `MiniChart.tsx` hashes matched before editing; `MiniChart.tsx` remains unchanged at SHA-256 `ed905aac...05d13e`.
- The complete pre-existing `app.css` baseline remained intact beneath additive Phase 19 rules.

## Threat Model

- T-19-13 is mitigated by finite-only formatting and an explicit empty series whenever the gate closes or buffered data is invalid.
- T-19-19 is mitigated by a dedicated valid-zero test proving `0` renders as `0.0 deg` while null/non-finite values render `—` without a degree unit.
- No package, registry component, network endpoint, authentication path, file-access pattern, or schema trust boundary was added.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 19-07 can run the full production-preview and wireless operator verification with the phase-level frontend build now green.
- Native OpenSim/Simbody visualizer smoke remains environment-dependent as already tracked for Phase 19 verification.

## Self-Check: PASSED

- All seven created/modified source paths exist.
- Commits `68949f0`, `e0b55be`, and `59c7342` exist and contain no tracked-file deletions.
- Targeted tests, TypeScript typecheck, and production build all pass.
- `.planning/phases/19-studio-controls-live-angle/19-WORKTREE-BASELINE.local.md` remains untracked and unstaged.
- `rehab-robotics-studio/src/components/common/MiniChart.tsx` remains unchanged and untracked.

---
*Phase: 19-studio-controls-live-angle*
*Completed: 2026-07-28*
