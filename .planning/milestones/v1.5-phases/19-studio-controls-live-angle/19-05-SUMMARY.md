---
phase: 19-studio-controls-live-angle
plan: "05"
subsystem: studio-visualizer-chrome
tags: [react, typescript, accessibility, rosbridge, playwright, health-panel]

requires:
  - phase: 19-studio-controls-live-angle
    plan: "01"
    provides: Backend-owned visualizer Trigger and persistent visualization status
  - phase: 19-studio-controls-live-angle
    plan: "03"
    provides: Narrow visualizer facade and persistent typed OpenSim store snapshots
provides:
  - Exact Calibrate, Clear cal, Open visualizer, Save toolbar sequence
  - One-request visualizer busy controller with focus-safe retry settlement
  - Assertive transient failure alert backed by persistent HealthPanel truth
  - Separate calibration, IK, input-age, angle-freshness, model, and visualizer rows
  - Fast component tests and a deterministic production toolbar DOM QA mode
affects: [19-06, 19-07, studio-toolbar, health-panel, production-preview]

tech-stack:
  added: []
  patterns:
    - "Ref-backed controller guards an async toolbar request before React can rerender"
    - "Transient alert feedback mirrors a persistent typed HealthPanel state"
    - "Production browser QA injects rosbridge at the WebSocket boundary"

key-files:
  created:
    - rehab-robotics-studio/src/components/chrome/Toolbar.test.ts
    - rehab-robotics-studio/scripts/phase19-qa.mjs
  modified:
    - rehab-robotics-studio/src/components/chrome/Toolbar.tsx
    - rehab-robotics-studio/src/components/common/Toast.tsx
    - rehab-robotics-studio/src/components/dashboard/HealthPanel.tsx
    - rehab-robotics-studio/src/components/dashboard/HealthPanel.test.ts

key-decisions:
  - "Use a synchronous ref-backed pending guard in addition to disabled state so same-tick pointer or keyboard duplicates cannot create another request."
  - "Let backend Opening/Open outrank a retained request failure while unrelated unavailable status leaves the failure visible."
  - "Keep preview QA deterministic by replacing WebSocket before the production bundle initializes."

patterns-established:
  - "Visualizer failure emits one store transition/log and one alert; repeated persistence writes are signature-deduplicated."
  - "HealthPanel formatting normalizes reason codes before rendering and never exposes raw payload objects."

requirements-completed: [VIS-01, VIS-02]

duration: 16min
completed: 2026-07-28
---

# Phase 19 Plan 05: Toolbar and Persistent Health Feedback Summary

**A guarded `Open visualizer` toolbar action now drives normalized alert/log feedback and persistent, independently formatted OpenSim health truth, with fast controller tests and deterministic production DOM coverage.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-07-28T20:50:01Z
- **Completed:** 2026-07-28T21:05:36Z
- **Tasks:** 1
- **Files modified:** 6

## Accomplishments

- Inserted `Open visualizer` exactly after `Clear cal` and before `Save`, preserving the same button element across `Opening…`, success, failure, and retry.
- Added a synchronous in-flight guard, disabled/`aria-busy` feedback, normalized fixed-copy failure alert, and retry settlement through only `openOpenSimVisualizer`.
- Expanded OpenSim HealthPanel truth into ordered calibration, IK validity, input age, calibration identity, gated knee freshness, model, and persistent visualizer rows.
- Added 10 fast tests covering order, pending state, duplicate suppression, success/failure settlement, retry, reason containment, persistent failure, and backend recovery.
- Added `phase19-qa.mjs --toolbar-only` with fake-rosbridge service-frame, focus, alert, persistence, retry, and backend replacement assertions.

## Task Commits

Each task was committed atomically:

1. **Task 1: Integrate and prove Toolbar plus persistent HealthPanel behavior** - `7414fea` (feat)

## Files Created/Modified

- `rehab-robotics-studio/src/components/chrome/Toolbar.tsx` - Adds the ordered, focus-stable visualizer action and guarded retry flow.
- `rehab-robotics-studio/src/components/chrome/Toolbar.test.ts` - Exercises the fast pure request controller.
- `rehab-robotics-studio/src/components/common/Toast.tsx` - Adds assertive error-alert semantics and the pure visualizer request seam.
- `rehab-robotics-studio/src/components/dashboard/HealthPanel.tsx` - Formats and renders independent OpenSim health facts with persistent visualizer replacement rules.
- `rehab-robotics-studio/src/components/dashboard/HealthPanel.test.ts` - Directly proves normalized health formatting and persistent/recovery state.
- `rehab-robotics-studio/scripts/phase19-qa.mjs` - Defines toolbar-only production DOM verification with an injected fake rosbridge.

## Decisions Made

- Kept the Toolbar button mounted and used a ref-owned request guard because React state alone does not protect against multiple activations before rerender.
- Reused the existing store transition deduplication: the facade owns failure persistence/logging, while Toolbar mirrors the same signature only to contain unexpected rejected promises.
- Made HealthPanel recovery fail closed: only backend `opening` or `open` replaces a retained request failure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Kept component tests independent of Vite `import.meta.env`**
- **Found during:** Task 1 fast verification
- **Issue:** Importing component modules through eager application-source dependencies caused Node's test runtime to fail before tests ran because `import.meta.env` is Vite-owned.
- **Fix:** Kept the Toolbar request controller in the already-planned Toast module and made HealthPanel's reconnect dependency lazy, so pure formatter/controller imports do not initialize the live data source.
- **Files modified:** `Toast.tsx`, `HealthPanel.tsx`, `Toolbar.test.ts`, `HealthPanel.test.ts`
- **Verification:** Targeted Node test command passes 10/10.
- **Committed in:** `7414fea`

---

**Total deviations:** 1 auto-fixed blocking issue.
**Impact on plan:** The change is limited to testability and preserves the same runtime action boundaries.

## Issues Encountered

- The exact `npm run build` gate is blocked before Vite by dependency-owned TypeScript errors in `BlockNode.tsx:36`, `MotorPanel.tsx:17`, and the previously documented `calibrationStatus.ts:14`; none of the six Plan 05 files reports a type error.
- A direct production Vite bundle succeeds (162 modules). The toolbar-only browser script then reaches an environment/dependency gate before Toolbar renders: the Plan 06 readouts call `toFixed` on the new nullable knee angle. The script reports the exact production exception and is ready to rerun after Plan 19-06 fixes those readouts; Plan 19-07 should run the full command.

## Known Stubs

None.

## Verification

- `npm exec -- tsx --test src/components/dashboard/HealthPanel.test.ts src/components/chrome/Toolbar.test.ts`
  - Result: 10 passed, 0 failed.
- `npm run typecheck`
  - Result: all Plan 05 files typecheck; blocked only by the three dependency-owned errors listed above.
- `npm run build`
  - Result: same isolated pre-Vite TypeScript blockers.
- `node node_modules/vite/bin/vite.js build --outDir <temporary-production-dir> --emptyOutDir`
  - Result: passed; 162 modules transformed and production assets emitted outside the dirty `dist`.
- `node scripts/phase19-qa.mjs --toolbar-only`
  - Result: QA mode launches and reports the upstream nullable-readout production exception before Toolbar mount; no Plan 05 assertion failure was reached.
- `node --check scripts/phase19-qa.mjs`
  - Result: passed.
- `git diff --check` across all six planned paths
  - Result: passed.

## Threat Model

- T-19-12 mitigated by the ref-backed pending guard and duplicate-attempt tests.
- T-19-15 mitigated by bounded reason normalization and React text rendering.
- T-19-18 mitigated by typed persistent failure precedence and backend Opening/Open replacement tests.
- Browser product code exposes no process, shell, WSL, path, or raw payload execution surface.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 19-06 can now make nullable angle readouts production-safe.
- After Plan 19-06, rerun `npm run build; node scripts/phase19-qa.mjs --toolbar-only`; Plan 19-07 owns the full production-preview gate.

## Self-Check: PASSED

- All six planned source/test/QA files exist.
- Task commit `7414fea` exists and contains exactly those six paths with no deletions.
- Fast verification passes 10/10.
- `.planning/phases/19-studio-controls-live-angle/19-WORKTREE-BASELINE.local.md` remains untracked and unstaged.
- The production DOM blocker is isolated to future-plan dependency files and documented with the exact rerun command.

---
*Phase: 19-studio-controls-live-angle*
*Completed: 2026-07-28*
