---
phase: 01-block-wire-selection-deletion
plan: 01
subsystem: ui
tags: [react, zustand, svg, keyboard-shortcuts, canvas]

requires: []
provides:
  - "Keyboard deletion for selected graph blocks"
  - "Clickable and highlighted SVG wire selection"
  - "Keyboard deletion for selected graph wires"
  - "Default graph wire rendering restored through semantic port IDs"
affects: [graph-canvas, wiring, block-management, interactive-wiring]

tech-stack:
  added: []
  patterns:
    - "Global keyboard shortcuts use a scoped React hook and Zustand getState() at event time"
    - "SVG wire interaction uses transparent hit paths plus selected/onClick props"

key-files:
  created:
    - src/hooks/useKeyboardDelete.ts
  modified:
    - src/components/canvas/GraphCanvas.tsx
    - src/graph/blockDefinitions.ts

key-decisions:
  - "Mount keyboard deletion in GraphCanvas so the shortcut is scoped to graph interaction."
  - "Use semantic port names as default port IDs so existing default edges render and remain selectable."

patterns-established:
  - "Canvas keyboard shortcuts should guard INPUT, TEXTAREA, and SELECT before mutating graph state."
  - "GraphCanvas should preserve empty-canvas deselection on both the canvas div and the pointer-enabled SVG layer."

requirements-completed:
  - GRAPH-01
  - GRAPH-02

duration: 75 min
completed: 2026-07-13
---

# Phase 01 Plan 01: Block & Wire Selection + Deletion Summary

**Keyboard-driven deletion for selected blocks and SVG wires, with default graph wires restored for interaction**

## Performance

- **Duration:** 75 min
- **Started:** 2026-07-13T17:30:00Z
- **Completed:** 2026-07-13T18:45:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added `useKeyboardDelete`, a React hook that deletes the selected block or selected wire on Delete/Backspace while ignoring form fields.
- Wired `GraphCanvas` to mount the hook, select wires through the existing `selectEdge` store action, highlight selected wires, and preserve empty-canvas deselection.
- Restored default wire rendering by making omitted port IDs default to the displayed port name, matching the existing default edge definitions.
- Verified the behavior in a production preview with Playwright-driven browser actions.

## Task Commits

1. **Task 1: Add keyboard deletion hook** - `e761779` (feat)
2. **Task 2: Mount deletion hook and wire wire selection** - `c97864f` (feat)
3. **Task 2 follow-up: Preserve empty canvas deselection** - `0d1bba9` (fix)
4. **Deviation fix: Restore default wire port matching** - `a398d5c` (fix)

**Plan metadata:** pending in docs commit

## Files Created/Modified

- `src/hooks/useKeyboardDelete.ts` - Global Delete/Backspace handler for selected nodes and edges using `useGraphStore.getState()`.
- `src/components/canvas/GraphCanvas.tsx` - Mounts keyboard deletion, passes `selected`/`onClick` to wires, enables SVG pointer events, and handles SVG background deselection.
- `src/graph/blockDefinitions.ts` - Defaults port IDs to port names so default edge definitions resolve to real ports.

## Decisions Made

- Mounted `useKeyboardDelete()` in `GraphCanvas` because graph deletion should be active only while the canvas is mounted.
- Kept deletion behavior on existing store methods (`removeNode`, `removeEdge`) rather than adding new graph state actions.
- Used semantic port names as default IDs because the existing default graph edges already reference semantic port identifiers.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Restored default graph wire rendering**
- **Found during:** Task 3 (Verify Phase 1 behavior)
- **Issue:** The default graph contained seven edges, but no SVG wires rendered because port builders defaulted IDs to `in`/`out` while default edges referenced semantic IDs like `force`, `imu`, `angles`, and `value`.
- **Fix:** Changed the `out` and `inp` helper defaults in `src/graph/blockDefinitions.ts` so omitted IDs use the port `name`.
- **Files modified:** `src/graph/blockDefinitions.ts`
- **Verification:** `npm run typecheck`, `npm run build`, and Playwright preview acceptance confirmed seven initial wires render and are selectable/deletable.
- **Committed in:** `a398d5c`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Required for GRAPH-02 correctness. The fix restores intended existing default graph behavior and does not add dependencies or new state.

## Issues Encountered

- Vite dev serving was unreliable from the current project path because the root path contains `#`; Vite warned this may not work. Production `npm run build` and `npm run preview` were used for browser verification instead.
- Playwright's bundled browser was not initially installed for the REPL package version. Installed the matching Chromium runtime with `npx playwright@1.57.0 install chromium` to run acceptance checks.

## Verification

- `npm run typecheck` - passed.
- `npm run build` - passed.
- Playwright against `npm run preview -- --host 127.0.0.1 --port 4173` - passed:
  - Initial graph rendered 11 blocks and 7 wires.
  - Clicking block `B1` selected it.
  - Pressing Delete removed `B1` and connected wire `e5`.
  - Clicking wire `e5` selected/highlighted it.
  - Pressing Backspace removed selected wire `e5`.
  - Clicking visible empty canvas cleared selected wire `e2`.
  - Pressing Delete inside a visible properties input did not remove selected block `B4`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 1 graph selection and deletion behavior is ready for Phase 2 interactive wiring and palette drag-drop. Phase 2 should preserve the `selectedEdgeId`/`selectedId` mutual exclusion and the pointer-enabled SVG background deselection behavior.

## Self-Check: PASSED

- PLAN requirements copied into summary frontmatter.
- Key files exist and are committed.
- Automated checks passed.
- Browser acceptance checks passed.
- Deviations documented.

---
*Phase: 01-block-wire-selection-deletion*
*Completed: 2026-07-13*
