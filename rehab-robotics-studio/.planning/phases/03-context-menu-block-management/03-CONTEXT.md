# Phase 3: Context Menu + Block Management - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can manage blocks and wires through right-click context menus and the properties panel: Delete / Duplicate / Rename on blocks, Delete on wires, Select All on canvas background, rename via properties name field, and duplicate with an offset copy. No undo/redo, copy/paste clipboard, or full marquee multi-select (deferred to v2).

</domain>

<decisions>
## Implementation Decisions

### Context Menu Behavior
- Hand-rolled fixed-position menu (no new npm dependencies)
- Close on Escape, outside click, or any menu action
- Position at cursor (clientX/Y), clamped to viewport
- Right-click selects the target first, then opens the menu

### Rename Flow
- Properties panel name field only (BLK-01); context “Rename” selects the block and focuses that field
- Commit name on every keystroke via store (same pattern as ParamField)
- Revert to previous name on blur if empty
- Context menu “Rename”: select block → ensure properties visible → focus name input

### Duplicate Behavior
- Copy type, name + `" copy"`, params, ports — new ID; do not copy wires
- Offset +40px X and +40px Y from original
- Auto-select the new copy after duplicate
- Duplicate entry point: context menu only (BLK-02)

### Select All & Selection Model
- Minimal multi-select: `selectedIds: string[]` for blocks only; Select All fills it; Delete removes all selected; click still single-selects
- All selected blocks show selected styling
- Select All selects blocks only (not wires)
- Empty canvas click clears all; selecting a wire clears block multi-select

### Claude's Discretion
- Menu visual styling (match existing LabVIEW-inspired chrome)
- Exact focus timing for Rename (requestAnimationFrame vs setTimeout)
- How keyboard Delete interacts with `selectedIds` when multiple blocks are selected
- Whether renameNode is a dedicated store method or a general updateNode

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/state/graphStore.ts` — `removeNode`, `removeEdge`, `addNode`, `select`, `selectEdge`, `updateParam`
- `src/hooks/useKeyboardDelete.ts` — window keydown pattern; ignores INPUT/TEXTAREA/SELECT
- `src/components/properties/ParamField.tsx` — inline controlled input pattern for rename field
- `src/components/canvas/GraphCanvas.tsx` — canvas pointer geometry, deselect on background click
- `src/components/canvas/BlockNode.tsx` — already ignores non-left-click for drag (`button !== 0`)
- `src/components/canvas/Wire.tsx` — `onClick` / `selected` already threaded

### Established Patterns
- Zustand store owns graph lifecycle; canvas owns pointer geometry
- Single-select today (`selectedId` + `selectedEdgeId`); Phase 3 extends to `selectedIds` for blocks
- No new dependencies — hand-roll UI chrome
- Keyboard delete already calls `removeNode` / `removeEdge` — context Delete reuses same methods

### Integration Points
- Hook `onContextMenu` on BlockNode root, Wire `<g>`, GraphCanvas background
- PropertiesPanel: replace static `<h2>` name with editable input
- New store methods: `renameNode` (or update), `duplicateNode`, `selectAll`, multi-select aware `select` / clear
- Mount a shared ContextMenu overlay (fixed position) from App or GraphCanvas

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond ROADMAP success criteria and the accepted grey-area decisions above.

</specifics>

<deferred>
## Deferred Ideas

- Full multi-select with marquee / shift-click (EDIT-03 / v2)
- Copy/paste clipboard (EDIT-02 / v2)
- Undo/redo (EDIT-01 / v2)
- Duplicate button in properties panel (not in BLK-02)

</deferred>
