---
status: clean
phase: 03-context-menu-block-management
reviewer: code-reviewer
reviewed: 2026-07-13
fixed: 2026-07-13
scope:
  - src/state/graphStore.ts
  - src/hooks/useKeyboardDelete.ts
  - src/components/canvas/GraphCanvas.tsx
  - src/components/canvas/BlockNode.tsx
  - src/components/canvas/Wire.tsx
  - src/components/common/ContextMenu.tsx
  - src/components/properties/PropertiesPanel.tsx
  - src/styles/app.css
severity_summary:
  critical: 0
  high: 0
  medium: 0
  low: 0
  info: 2
---

# Phase 3 Code Review — Context Menu + Block Management

## Verdict

**Clean (Low findings fixed).** The implementation faithfully realizes `03-CONTEXT.md`, `03-UI-SPEC.md`, and both execution plans (`03-01-PLAN.md`, `03-02-PLAN.md`). All requirement contracts (CTX-01/02/03, BLK-01/02) are implemented. Low polish items LOW-1–LOW-4 were addressed in a follow-up commit; Info items remain for UAT awareness only.

> Build note: `npm run typecheck` re-run via `subst R:` after Low fixes — green.

---

## Requirement / Spec Conformance

| Item | Spec source | Status | Evidence |
|------|-------------|--------|----------|
| Block menu `Duplicate · Rename · sep · Delete`, exact labels | UI-SPEC copy contract | ✅ | `GraphCanvas.tsx` `contextMenuItems` (block branch), Delete `danger + separatorBefore` |
| Wire menu `Delete` only | UI-SPEC | ✅ | `GraphCanvas.tsx` wire branch |
| Canvas menu `Select All` | UI-SPEC | ✅ | `GraphCanvas.tsx` canvas branch |
| Native OS menu suppressed on handled targets only | Threat T-3-05 | ✅ | `preventDefault` in BlockNode/Wire and canvas handler gated on `currentTarget === target` |
| Select-before-open | CONTEXT | ✅ | `handleBlockContextMenu` → `select`, `handleWireContextMenu` → `selectEdge` |
| Duplicate: type/params/name+` copy`, new id, no wires, offset +40/+40 clamped, auto-select | CONTEXT / BLK-02 | ✅ | `graphStore.duplicateNode` |
| Rename: live per-keystroke, empty-blur revert, focus `#block-name-input` | BLK-01 | ✅ | `PropertiesPanel.tsx` + `focusBlockNameInput` (double rAF) |
| `selectedIds` multi-select + Select All + multi-delete | CONTEXT / CTX-03 | ✅ | `graphStore` + `useKeyboardDelete` |
| Selection mutual exclusion & hygiene (add/remove/wire/load) | Plan 01 must-haves | ✅ | `graphStore` select/selectEdge/selectAll/addNode/startWire/load |
| Menu: fixed portal, `z-index:1000`, min-width 160px, radius 0, 4px viewport clamp, Escape/outside dismiss | UI-SPEC shell | ✅ | `ContextMenu.tsx` + `.context-menu*` CSS |
| CSS chrome (colors, danger `#ec5a5a`/`#3a2020`/`#ffd9d9`, separator, hover, focus bar) | UI-SPEC color/interaction | ✅ | `app.css` lines 684–730 |
| No new npm dependencies | CONTEXT / T-3-SC | ✅ | `tech-stack.added: []`; hand-rolled menu |
| React text escaping for names (no `dangerouslySetInnerHTML`) | Threat T-3-01 | ✅ | `.block-name` and Name input render plain text |

---

## Findings

### LOW-1 — ARIA menu semantics diluted by wrapper `<div>`s — **FIXED**
Was: wrapper `<div>`s inside `role="menu"`. Now: `Fragment` siblings so `menuitem` / `separator` are direct menu children.

### LOW-2 — No keyboard focus/roving inside the menu — **FIXED**
Menu has `tabIndex={-1}` and focuses on mount; ArrowUp/ArrowDown/Home/End move among `menuitem`s. Escape still closes; focus is not trapped.

### LOW-3 — Menu is not dismissed on scroll/resize — **FIXED**
Dismiss effect also listens for `window` `scroll` (capture) and `resize`.

### LOW-4 — `focusBlockNameInput` omitted from `contextMenuItems` deps — **FIXED**
`focusBlockNameInput` wrapped in `useCallback` and included in `contextMenuItems` deps.

### INFO-1 — Duplicate offset collapses at canvas edge (spec-compliant)
When a source block already sits at the clamped max X/Y, `duplicateNode` clamps the `+40/+40` copy back onto the same coordinates, so the copy lands exactly atop the original. This matches the locked "offset then clamp" contract, but the copy can be visually hidden until dragged. Acceptable per CONTEXT; noted for UAT awareness.

- File: `src/state/graphStore.ts` (`duplicateNode` clamp)

### INFO-2 — Task 3 human/browser verification still pending
Per `03-02-SUMMARY.md`, the automated gate passed but the 10-item browser checklist (Task 3, blocking checkpoint) is recorded as *deferred-to-verify*. Recommend running the checklist (or Playwright evidence) before closing the phase, particularly: right-click select-before-open, duplicate offset/naming, empty-blur revert, Select All + Delete, and Phase 1–2 regression (INPUT-focused Backspace must not delete blocks — confirmed correct in code via the `INPUT/TEXTAREA/SELECT` guard).

---

## Things Done Well

- **Selection hygiene is airtight.** `select`/`selectEdge`/`selectAll`/`addNode`/`startWire`/`load`/`removeNode`/`removeNodes` all keep `selectedId` / `selectedIds` / `selectedEdgeId` mutually consistent — exactly the Plan 01 must-have truths.
- **Event isolation is correct.** BlockNode and Wire both `preventDefault + stopPropagation` on `contextmenu`, and the canvas handler only acts on `currentTarget === target`, so the native menu is suppressed only on handled surfaces (Threat T-3-05 satisfied) and nested targets don't bubble into the canvas "Select All" menu.
- **Portal + clamp** correctly avoids the `.graph-canvas { overflow: auto }` clipping trap and uses `useLayoutEffect` so clamping happens pre-paint (no flash).
- **`removeNodes` uses a `Set`** for O(n) batch delete and prunes connected edges in a single `set` — clean and efficient.
- **Rename revert** via `lastNonEmptyRef` synced in an effect keyed on `node.id`/`node.name` handles node-switch and whitespace-only input correctly.
- **No new dependencies**, matching the locked constraint and the STRIDE `T-3-SC` disposition.

---

## Recommendation

Ship the phase. Complete the deferred browser checklist (INFO-2) before marking the milestone done.
