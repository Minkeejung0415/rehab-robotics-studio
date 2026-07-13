---
phase: 04-runtime-feedback-deploy-polish
plan: 02
subsystem: ui
tags: [Toast, Toolbar, recording, deployMock, portal, RT-02, DEP-01]

requires:
  - phase: 04-runtime-feedback-deploy-polish
    provides: setAllNodeStatuses + runtimeStore badge sync (04-01)
provides:
  - Hand-rolled portal Toast with 2500ms auto-dismiss
  - Toolbar Rec toggle wired to systemStore.setRecording
  - Deploy Mock toast host with locked copy
affects:
  - Phase 4 verification / Playwright QA
  - StatusStrip Recording indicator UX

tech-stack:
  added: []
  patterns:
    - createPortal toast host in Toolbar (single-instance replace via key)
    - Rec pressed chrome via .btn-rec-on matching .btn-estop family

key-files:
  created:
    - src/components/common/Toast.tsx
  modified:
    - src/styles/app.css
    - src/components/chrome/Toolbar.tsx

key-decisions:
  - "Toast hosted in Toolbar with toastKey remount for replace-on-retrigger"
  - "Rec disabled when estopped/fault; On uses btn-rec-on fault chrome"
  - "Browser checkpoint deferred to SUMMARY checklist (autonomous execute)"

patterns-established:
  - "Hand-rolled overlays (ContextMenu, Toast) — no toast libraries"
  - "Locked deploy toast copy separate from deployMock log string"

requirements-completed: [RT-02, DEP-01]

duration: 5min
completed: 2026-07-13
---

# Phase 4 Plan 02: Rec Toggle + Deploy Toast Summary

**Toolbar Rec toggle wired to status-strip Recording plus hand-rolled top-center Deploy Mock toast (2500ms, click-dismiss, single-instance replace)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-13T21:27:45Z
- **Completed:** 2026-07-13T21:30:00Z
- **Tasks:** 3 (2 implemented; 1 browser checkpoint deferred to checklist below)
- **Files modified:** 3

## Accomplishments
- Created portal `Toast` with `role="status"`, `aria-live="polite"`, 2500ms timer, click + Escape dismiss
- Added `.toast` and `.btn-rec-on` LabVIEW chrome to `app.css`
- Inserted Rec between Stop and Validate separator; toggles `setRecording`; Deploy shows locked toast after `deployMock()` log

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Toast component and chrome CSS** - `c1db0e3` (feat)
2. **Task 2: Wire Rec button and Deploy toast in Toolbar** - `d6a88b7` (feat)
3. **Task 3: Browser-verify** - deferred (see checklist; no code commit)

**Plan metadata:** `f66365a` (docs: complete plan)

## Files Created/Modified
- `src/components/common/Toast.tsx` - reusable portal toast
- `src/styles/app.css` - `.toast`, `.btn-rec-on`
- `src/components/chrome/Toolbar.tsx` - Rec + Deploy toast host

## Decisions Made
- Toast host lives in Toolbar with `toastKey` remount so retrigger restarts the timer
- Rec uses same `blocked` gate as Run/Deploy
- Autonomous execute: browser human-verify deferred to SUMMARY checklist (no wait)

## Browser Verification Checklist (deferred)

Prefer `npm run build && npm run preview -- --host 127.0.0.1 --port 4173`:

1. [ ] Run → every block badge shows `running` (green)
2. [ ] Pause → RUNTIME PAUSED; badges still `running`
3. [ ] Run again (resume) → RUNTIME RUNNING; badges `running`
4. [ ] Stop → all badges `idle`
5. [ ] Run then E-STOP → badges `idle`; Reset → badges `idle`
6. [ ] `○ Rec` → `● Rec` and strip Recording On; toggle back Off
7. [ ] E-STOP engaged → Rec, Deploy, Run disabled
8. [ ] Deploy Mock → log `Deploy (mock) — graph would be pushed to Jetson` AND toast `Deploy (mock) started — graph would be pushed to Jetson`
9. [ ] Toast auto-dismiss ~2.5s; click dismisses; second Deploy replaces (no stack)
10. [ ] Phase 1–3 regression: select/delete, wiring, palette drop, context menu

Automated gates for this plan: `npm run typecheck && npm run build` — **PASSED**.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Tracked previously untracked Toolbar.tsx**
- **Found during:** Task 2
- **Issue:** `Toolbar.tsx` was untracked in git despite being the RT-02/DEP-01 integration point
- **Fix:** Committed full Toolbar with Rec + toast wiring
- **Files modified:** `src/components/chrome/Toolbar.tsx`
- **Verification:** typecheck + build green
- **Committed in:** `d6a88b7`

---

**Total deviations:** 1 auto-fixed (missing critical tracking)
**Impact on plan:** Required for feature to ship in repo; no scope creep.

## Issues Encountered
None during Tasks 1–2. Task 3 browser walkthrough deferred per autonomous execute instructions.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- RT-01, RT-02, DEP-01 implemented in code
- Phase 4 ready for human/Playwright browser verification then Phase 5 planning
- Preview via `127.0.0.1:4173` (avoid Vite `dev` when path contains `#`)

## Self-Check: PASSED
- FOUND: `src/components/common/Toast.tsx`
- FOUND: `.toast` / `.btn-rec-on` in `src/styles/app.css`
- FOUND: Rec / setRecording / Toast / deployMock in Toolbar
- FOUND: commit `c1db0e3`
- FOUND: commit `d6a88b7`

---
*Phase: 04-runtime-feedback-deploy-polish*
*Completed: 2026-07-13*
