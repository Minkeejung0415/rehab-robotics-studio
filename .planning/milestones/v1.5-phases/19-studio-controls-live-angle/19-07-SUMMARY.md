---
phase: 19-studio-controls-live-angle
plan: "07"
subsystem: production-qa-and-operations
tags: [playwright, fake-rosbridge, contract-check, regression, runbook]

requires:
  - phase: 19-studio-controls-live-angle
    plans: ["01", "02", "03", "04", "05", "06"]
    provides: Backend Trigger, typed reconnect-safe transport, gated product routing, toolbar health feedback, and nullable angle displays
provides:
  - Fast no-browser/no-preview/no-network Phase 19 contract gate
  - Complete production fake-rosbridge operator-flow E2E
  - Full frontend and backend regression evidence
  - Runnable wireless OpenSim IK operator checklist with an explicit native-window boundary
affects: [phase-19-verification, wireless-operations, opensim-visualizer-smoke]

tech-stack:
  added: []
  patterns:
    - "One contract manifest drives fast source checks and full executed-scenario coverage"
    - "Production WebSocket injection proves malformed and obsolete-session isolation without ROS/OpenSim runtime dependencies"

key-files:
  created: []
  modified:
    - rehab-robotics-studio/scripts/phase19-qa.mjs
    - rehab-robotics-studio/package.json
    - docs/stepesp-wireless-setup.md

key-decisions:
  - "Contract-check mode exits before preview startup or Playwright import and reports machine-readable JSON."
  - "Full QA proves same-button identity across disabled busy state because Chromium does not keep document focus on disabled controls."
  - "Real Simbody native-window appearance remains human_needed when simbody-visualizer is unavailable."

patterns-established:
  - "Every full E2E scenario is marked only after its production assertion passes, then checked against the contract manifest."
  - "Late replies, messages, and close callbacks are injected through the obsolete socket while a current request remains pending."

requirements-completed: [VIS-01, VIS-02, IK-06]

duration: 10min
completed: 2026-07-28
---

# Phase 19 Plan 07: Production QA and Wireless Operations Summary

**A fast self-contract gate and complete production fake-rosbridge flow now prove the visualizer, standing calibration, official live knee angle, stale recovery, and reconnect isolation before operators use the fixed wireless checklist.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-28T21:16:16Z
- **Completed:** 2026-07-28T21:26:33Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments

- Added `--contract-check`, which completes in approximately 1 ms and explicitly reports that no browser, preview, or network was used.
- Extended default production QA through the three typed subscriptions, fixed argument-free visualizer Trigger, pending duplicate suppression, persistent failure/retry, standing calibration, invalid em dash, reordered `Math.PI / 2` to `90.0 deg` on all three displays, 2,001 ms stale clearing, fresh-series recovery, malformed-envelope isolation, and obsolete-session reply/message/close rejection.
- Added `test:phase19` as build plus default QA without changing dependencies or devDependencies.
- Added a copy-paste wireless/OpenSim checklist covering stack start, device/topic confirmation, visualizer request, standing calibration, official angle verification, recovery, and clean shutdown.
- Completed the full frontend and backend regression gate.

## Task Commits

Each task was committed atomically:

1. **Task 1: Complete QA contracts, full regression gate, and operator runbook** - `757bde7` (test)

## Files Created/Modified

- `rehab-robotics-studio/scripts/phase19-qa.mjs` - Fast contract mode, retained toolbar mode, full production fake-rosbridge E2E, bounded cleanup, and machine-readable results.
- `rehab-robotics-studio/package.json` - Adds the dependency-neutral `test:phase19` build/E2E command.
- `docs/stepesp-wireless-setup.md` - Adds the one-page calibrated OpenSim IK operating and recovery checklist.

## Decisions Made

- Used a shared contract manifest so the fast mode checks every required contract and the full mode refuses success until every declared scenario has executed.
- Tested preserved button DOM identity rather than `document.activeElement` while disabled; Chromium moves focus off disabled controls even when React retains the exact same button.
- Kept native-window verification explicitly `human_needed`; automated coverage proves the bounded Trigger and failure/retry behavior but cannot assert that an external Simbody window is visible.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the inherited disabled-button focus assertion**
- **Found during:** Task 1 production fake-rosbridge E2E
- **Issue:** The inherited toolbar-only script required `document.activeElement` to remain a disabled button. Chromium removes focus from disabled controls, so the harness failed before reaching the Phase 19 production flow even though React preserved the same button.
- **Fix:** Asserted stable DOM button identity across busy, failure, and recovery states while retaining disabled/`aria-busy`, duplicate-suppression, settlement, and retry checks.
- **Files modified:** `rehab-robotics-studio/scripts/phase19-qa.mjs`
- **Verification:** Toolbar-only mode and the complete default production E2E both pass.
- **Committed in:** `757bde7`

---

**Total deviations:** 1 auto-fixed bug.
**Impact on plan:** The correction removes a browser-impossible assertion without weakening any Plan 19-07 behavior or accessibility-state check.

## Issues Encountered

- Vite reports the pre-existing repository-path `#` warning and the existing mixed static/dynamic `appDataSource.ts` import warning; both are non-fatal and the production build succeeds.
- Backend discovery skips five runtime-dependent OpenSim/Simbody tests on this Windows host. The remaining 115 backend tests pass, and the native-window check remains documented as `human_needed`.

## Known Stubs

None.

## Verification

- `node --check scripts/phase19-qa.mjs`
  - Result: passed.
- `node scripts/phase19-qa.mjs --contract-check`
  - Result: passed in approximately 1 ms; `browserStarted`, `previewStarted`, and `networkUsed` are all `false`.
- `node scripts/phase19-qa.mjs --toolbar-only`
  - Result: passed the toolbar order, pending/duplicate, persistent failure, retry, and backend recovery scenarios.
- `npm test`
  - Result: 54 passed, 0 failed.
- `npm run typecheck`
  - Result: passed with no TypeScript errors.
- `npm run test:phase19`
  - Result: production build passed and all 10 full fake-rosbridge scenarios passed.
- `$env:PYTHONPATH='backend'; python -m unittest discover -s backend/test -p "test_*.py"`
  - Result: 120 tests run, 115 passed, 5 expected runtime-dependent skips.
- Dependency comparison against `HEAD`
  - Result: `dependencies` and `devDependencies` are unchanged.
- Exact-path preservation
  - Result: task commit contains only the three planned paths; no tracked files were deleted; `19-WORKTREE-BASELINE.local.md` remains untracked and unstaged.

## Threat Model

- T-19-14 is mitigated by production injection of a late old-session service reply, typed messages, and close callback while the current visualizer request and angle remain unchanged.
- T-19-17 is mitigated by fixed PowerShell/ROS commands and an explicit statement that Studio cannot execute browser-supplied shell, WSL, path, or process input.
- T-19-20 is mitigated by the fast manifest contract, nonzero machine-readable failure output, bounded preview/browser cleanup, and full executed-scenario coverage.
- T-19-SC remains accepted: no package dependency changed.
- No unplanned network endpoint, authentication path, file-access boundary, or schema trust surface was introduced.

## User Setup Required

None - no external service configuration is required for automated QA. Real native-window verification follows the runbook when the Simbody runtime is available.

## Next Phase Readiness

- Phase 19 is complete and ready for phase verification/UAT.
- The only manual boundary is the documented WSLg/Simbody native-window appearance and update smoke.

## Self-Check: PASSED

- All three modified key files exist.
- Task commit `757bde7` exists and contains exactly the three planned paths.
- Fast, toolbar-only, full production, frontend, typecheck, build, and backend gates pass.
- No tracked files were deleted.
- The dirty-worktree preservation baseline remains untracked and unstaged.

---
*Phase: 19-studio-controls-live-angle*
*Completed: 2026-07-28*
