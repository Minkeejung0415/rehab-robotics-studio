---
phase: 03-context-menu-block-management
plan: 02
subsystem: ui
tags: [context-menu, portal, rename, duplicate, properties, labview-chrome]

requires:
  - phase: 03-context-menu-block-management
    provides: selectedIds, selectAll, renameNode, duplicateNode, removeNodes store APIs
provides:
  - Hand-rolled ContextMenu portal with viewport clamp and Escape/outside dismiss
  - Block/wire/canvas context menus with UI-SPEC labels
  - Properties Name field (block-name-input) with live rename and empty-blur revert
affects:
  - Phase 3 verification / UAT browser checklist
  - Future EDIT clipboard/marquee work (deferred)

tech-stack:
  added: []
  patterns:
    - createPortal fixed menu outside overflow:auto canvas
    - Select-before-open on contextmenu targets
    - Controlled Name input → renameNode every keystroke

key-files:
  created:
    - src/components/common/ContextMenu.tsx
  modified:
    - src/styles/app.css
    - src/components/canvas/GraphCanvas.tsx
    - src/components/canvas/BlockNode.tsx
    - src/components/canvas/Wire.tsx
    - src/components/properties/PropertiesPanel.tsx

key-decisions:
  - "Portal to document.body so graph-canvas overflow cannot clip the menu"
  - "Rename uses double requestAnimationFrame to focus #block-name-input after menu close"
  - "Delete menu items use is-danger chrome matching .btn-estop palette"

patterns-established:
  - "ContextMenu: role=menu/menuitem, clamp via useLayoutEffect, dismiss via Escape + outside pointerdown"
  - "Canvas local contextMenu state (not store); items dispatch typed store methods"
  - "Properties Name replaces static h2; lastNonEmptyRef for blur revert"

requirements-completed: [CTX-01, CTX-02, CTX-03, BLK-01, BLK-02]

duration: 12min
completed: 2026-07-13
---

# Phase 3 Plan 02: Context Menu + Block Management UI Summary

**Hand-rolled portal context menus on blocks/wires/canvas plus a live properties Name field deliver CTX-01/02/03 and BLK-01/02 on top of Plan 01 store APIs.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-13T19:04:00Z
- **Completed:** 2026-07-13T19:16:00Z
- **Tasks:** 3 (2 code + 1 checkpoint deferred-to-verify)
- **Files modified:** 6

## Accomplishments

- Added `ContextMenu` with `createPortal`, viewport clamp (4px pad), Escape/outside dismiss, and LabVIEW chrome CSS (no new npm deps)
- Wired block (Duplicate / Rename / Delete), wire (Delete), and canvas (Select All) menus with select-before-open
- Replaced properties static title with controlled `Name` input (`#block-name-input`) committing via `renameNode`; empty blur restores last non-empty name; Rename focuses the field via double rAF

## Task Commits

Each task was committed atomically:

1. **Task 1: Build ContextMenu component and LabVIEW chrome CSS** - `b2fd4a8` (feat)
2. **Task 2: Wire context menus, properties Name field, and Rename focus** - `39d1628` (feat)
3. **Task 3: Browser-verify context menus and block management** - deferred-to-verify (autonomous mode; checklist below)

**Plan metadata:** `2f98fbb` (docs: complete plan)

## Files Created/Modified

- `src/components/common/ContextMenu.tsx` — fixed portal menu shell
- `src/styles/app.css` — `.context-menu*` rules per UI-SPEC
- `src/components/canvas/GraphCanvas.tsx` — menu state, handlers, item dispatch, ContextMenu mount
- `src/components/canvas/BlockNode.tsx` — optional `onContextMenu` with preventDefault/stopPropagation
- `src/components/canvas/Wire.tsx` — optional `onContextMenu` on wire `<g>`
- `src/components/properties/PropertiesPanel.tsx` — editable Name field + empty-blur revert

## Decisions Made

- Portal to `document.body` so `.graph-canvas { overflow: auto }` cannot clip the menu
- Rename focus via double `requestAnimationFrame` after menu close (CONTEXT discretion)
- Destructive Delete uses `is-danger` / `#ec5a5a` matching `.btn-estop` family
- No packages added (T-3-SC)

## Deviations from Plan

None - plan executed exactly as written (Task 3 browser approval deferred per autonomous-mode instructions).

## Task 3 — Pending Human Verification (deferred-to-verify)

Automated gate passed: `npm run typecheck && npm run build` exit 0.

Browser checklist (pending human verification). Prefer:

`npm run build && npm run preview -- --host 127.0.0.1 --port 4173`

Then confirm:

1. Right-click a block → menu shows Duplicate / Rename / separator / Delete; native OS menu does not appear.
2. Duplicate → new block at roughly +40,+40, name ends with ` copy`, no new wires, copy is selected.
3. Rename → properties Name input focused; typing updates canvas `.block-name`; clear Name and blur → previous name restored.
4. Block Delete → block and its wires removed.
5. Right-click a wire → Delete removes only that wire.
6. Right-click empty canvas → Select All; every block shows selected chrome; wires are not selected.
7. Select All then Delete/Backspace → all selected blocks (and their wires) removed.
8. Empty canvas left-click clears multi-select; clicking a wire clears block multi-select.
9. Escape / outside click dismisses an open menu without applying an action.
10. Phase 1–2 regression: port wiring, palette drop, single keyboard delete, INPUT-focused Backspace does not delete blocks.

**Resume signal:** Type `approved` or list any failing checklist items.

## Issues Encountered

None blocking. Shell path apostrophe required `subst R:` + temp `.cmd` wrappers for PowerShell.

## User Setup Required

None - no external service configuration required. Human browser verification of the checklist above remains.

## Next Phase Readiness

- CTX-01/02/03 and BLK-01/02 UI paths are implemented against Plan 01 store contracts
- Phase 3 ROADMAP success criteria ready for verifier after human checklist (or Playwright evidence)

## Self-Check: PASSED

- FOUND: `src/components/common/ContextMenu.tsx`
- FOUND: `src/styles/app.css` (`.context-menu` rules)
- FOUND: `src/components/canvas/GraphCanvas.tsx`
- FOUND: `src/components/canvas/BlockNode.tsx`
- FOUND: `src/components/canvas/Wire.tsx`
- FOUND: `src/components/properties/PropertiesPanel.tsx`
- FOUND: commit `b2fd4a8`
- FOUND: commit `39d1628`
- `npm run typecheck` and `npm run build` exit 0

---
*Phase: 03-context-menu-block-management*
*Completed: 2026-07-13*
