# Phase 3: Context Menu + Block Management - Pattern Map

**Mapped:** 2026-07-13
**Files analyzed:** 8
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/components/common/ContextMenu.tsx` | component | event-driven | `src/components/canvas/GraphCanvas.tsx` (window Escape/mousedown listeners) + `src/components/chrome/Toolbar.tsx` (btn chrome) + `src/components/common/StatusLight.tsx` (common shell) | partial |
| `src/state/graphStore.ts` | store | CRUD | `src/state/graphStore.ts` (`addNode` / `updateParam` / `select` / `removeNode`) | exact |
| `src/hooks/useKeyboardDelete.ts` | hook | event-driven | `src/hooks/useKeyboardDelete.ts` | exact |
| `src/components/canvas/GraphCanvas.tsx` | component | event-driven | `src/components/canvas/GraphCanvas.tsx` (local UI state + background hit-test) | exact |
| `src/components/canvas/BlockNode.tsx` | component | event-driven | `src/components/canvas/BlockNode.tsx` (`button !== 0` + select-on-interaction) | exact |
| `src/components/canvas/Wire.tsx` | component | event-driven | `src/components/canvas/Wire.tsx` (`stopPropagation` + `onClick`) | exact |
| `src/components/properties/PropertiesPanel.tsx` | component | event-driven | `src/components/properties/ParamField.tsx` (controlled input) + `PropertiesPanel.tsx` (header) | exact |
| `src/styles/app.css` | config | — | `src/styles/app.css` (`.btn`, `.param-field`, `.block-node.is-selected`, `.btn-estop`) | exact |

## Pattern Assignments

### `src/components/common/ContextMenu.tsx` (component, event-driven)

**Analog:** `src/components/canvas/GraphCanvas.tsx` (dismiss listeners) + `src/components/chrome/Toolbar.tsx` (button chrome) + `src/components/common/StatusLight.tsx` (common component file shape)

**No existing overlay/portal.** Hand-roll fixed menu; copy window listener lifecycle from GraphCanvas pending-wire effect, button markup from Toolbar, and file placement under `components/common/`.

**Imports pattern** (from `StatusLight.tsx` lines 1–2 + GraphCanvas listener style):
```typescript
import { useEffect, useLayoutEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
```

**Window dismiss / Escape pattern** (GraphCanvas lines 46–62 — copy lifecycle):
```typescript
useEffect(() => {
  if (!pendingWire) return;

  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') cancelWire();
  };

  window.addEventListener('mousemove', updatePointer);
  window.addEventListener('mouseup', cancelPendingWire);
  window.addEventListener('keydown', handleKeyDown);
  return () => {
    window.removeEventListener('mousemove', updatePointer);
    window.removeEventListener('mouseup', cancelPendingWire);
    window.removeEventListener('keydown', handleKeyDown);
  };
}, [cancelWire, pendingWire]);
```

**Adapt for ContextMenu:** `keydown` Escape → `onClose`; `mousedown` (or `pointerdown`) outside `ref.current` → `onClose`; cleanup on unmount. Prefer `createPortal(..., document.body)` because `.graph-canvas` has `overflow: auto` (app.css line 300).

**Button chrome pattern** (Toolbar lines 44–51 + app.css `.btn` / `.btn-estop`):
```tsx
<button className="btn btn-run" onClick={run} disabled={blocked} title="Run / Resume">
  ▶ Run
</button>
```

```css
.btn {
  height: 27px;
  padding: 0 10px;
  font-size: 12px;
}
.btn-estop {
  border-color: #7a3030;
  background: #3a2020;
  color: #ffd9d9;
  font-weight: 700;
}
```

**Core menu pattern** (new — align with RESEARCH sketch + UI-SPEC):
- `role="menu"` / `role="menuitem"`
- `position: fixed; z-index: 1000`
- Clamp with `useLayoutEffect` + `getBoundingClientRect()` (4px pad)
- Items: Duplicate / Rename / sep / Delete (block); Delete (wire); Select All (canvas)
- Destructive Delete: text `#ec5a5a`, hover bg `#3a2020` (match `.btn-estop`)
- Separator: 1px `#23292d`, margin 4px (match `.toolbar-sep` color)

**Common component shell** (StatusLight lines 10–21 — props-in, className CSS, no store):
```tsx
export function StatusLight({ label, value, level }: Props) {
  const c = levelColor[level];
  return (
    <div className="status-light">
      ...
    </div>
  );
}
```

---

### `src/state/graphStore.ts` (store, CRUD)

**Analog:** `src/state/graphStore.ts` (self)

**Imports pattern** (lines 1–6):
```typescript
import { create } from 'zustand';
import type { BlockInstance, EdgeDefinition, ParamValue } from '../types/blocks';
import type { SignalType } from '../types/signals';
import { BLOCK_DEFS, defaultParams } from '../graph/blockDefinitions';
import { deserializeGraph, serializeGraph } from '../graph/GraphModel';
import { validateGraph, type ValidationIssue } from '../graph/validation';
```

**Instance factory pattern** (lines 17–27 — reuse for duplicate clone base):
```typescript
function makeNode(id: string, type: string, x: number, y: number): BlockInstance {
  return {
    id,
    type,
    name: BLOCK_DEFS[type]?.name ?? type,
    position: { x, y },
    params: defaultParams(type),
    status: 'idle',
  };
}
```

**Field-update pattern** (lines 110–115 — copy for `renameNode`):
```typescript
updateParam: (nodeId, key, value) =>
  set((s) => ({
    nodes: s.nodes.map((nd) =>
      nd.id === nodeId ? { ...nd, params: { ...nd.params, [key]: value } } : nd,
    ),
  })),
```

**Dedicated rename** (mirror `updateParam` specificity):
```typescript
renameNode: (nodeId, name) =>
  set((s) => ({
    nodes: s.nodes.map((nd) => (nd.id === nodeId ? { ...nd, name } : nd)),
  })),
```

**Insert + auto-select pattern** (lines 122–126 — copy for `duplicateNode` id/`nextId`/select):
```typescript
addNode: (type, x, y) =>
  set((s) => {
    const id = `B${s.nextId}`;
    return { nodes: [...s.nodes, makeNode(id, type, x, y)], nextId: s.nextId + 1, selectedId: id };
  }),
```

**Duplicate core** (extend `addNode`; clamp like GraphCanvas drop lines 103–105):
```typescript
// CANVAS_WIDTH=980, CANVAS_HEIGHT=720, NODE_WIDTH=220 — export or duplicate constants
const copy: BlockInstance = {
  id: `B${s.nextId}`,
  type: src.type,
  name: `${src.name} copy`,
  position: {
    x: Math.max(8, Math.min(980 - 220 - 8, src.position.x + 40)),
    y: Math.max(8, Math.min(720 - 140, src.position.y + 40)),
  },
  params: { ...src.params },
  status: 'idle',
};
// return { nodes: [...s.nodes, copy], nextId: s.nextId + 1, selectedId: id, selectedIds: [id], selectedEdgeId: null }
```

**Selection mutual exclusion** (lines 106–108 — extend with `selectedIds`):
```typescript
select: (id) => set({ selectedId: id, selectedEdgeId: null }),
selectEdge: (id) => set({ selectedEdgeId: id, selectedId: null }),
```

**Phase 3 target:**
```typescript
select: (id) => set({ selectedId: id, selectedIds: id ? [id] : [], selectedEdgeId: null }),
selectEdge: (id) => set({ selectedEdgeId: id, selectedId: null, selectedIds: [] }),
selectAll: () => set((s) => {
  const ids = s.nodes.map((n) => n.id);
  const primary = s.selectedId && ids.includes(s.selectedId) ? s.selectedId : ids[0] ?? null;
  return { selectedIds: ids, selectedId: primary, selectedEdgeId: null };
}),
```

**Delete + edge prune** (lines 128–139 — reuse; extend selection clear for `selectedIds`; prefer `removeNodes(ids[])` for multi-delete):
```typescript
removeNode: (nodeId) =>
  set((s) => ({
    nodes: s.nodes.filter((nd) => nd.id !== nodeId),
    edges: s.edges.filter((e) => e.sourceBlockId !== nodeId && e.targetBlockId !== nodeId),
    selectedId: s.selectedId === nodeId ? null : s.selectedId,
  })),
```

**Also clear `selectedIds` in:** `startWire` (line 153–154), `load` (line 176–178), `select(null)`, `selectEdge`, `removeNode` / `removeNodes`.

**Validation:** silent no-ops when source missing (`if (!src) return s`) — same style as `addEdge` alreadyConnected guard (lines 143–147).

---

### `src/hooks/useKeyboardDelete.ts` (hook, event-driven)

**Analog:** `src/hooks/useKeyboardDelete.ts` (self)

**Imports + window keydown pattern** (lines 1–27 — extend selection branch only):
```typescript
import { useEffect } from 'react';
import { useGraphStore } from '../state/graphStore';

export function useKeyboardDelete(): void {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key !== 'Delete' && event.key !== 'Backspace') return;

      const tag = (event.target as HTMLElement | null)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      const { selectedId, selectedEdgeId, removeNode, removeEdge } = useGraphStore.getState();
      if (selectedId) {
        event.preventDefault();
        removeNode(selectedId);
        return;
      }

      if (selectedEdgeId) {
        event.preventDefault();
        removeEdge(selectedEdgeId);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
}
```

**Phase 3 core change** — prefer `selectedIds` first (INPUT guard stays — rename field must not delete on Backspace):
```typescript
const { selectedIds, selectedEdgeId, removeNodes, removeEdge } = useGraphStore.getState();
if (selectedIds.length > 0) {
  event.preventDefault();
  removeNodes(selectedIds); // batch preferred over forEach(removeNode)
  return;
}
if (selectedEdgeId) { ... }
```

---

### `src/components/canvas/GraphCanvas.tsx` (component, event-driven)

**Analog:** `src/components/canvas/GraphCanvas.tsx` (self)

**Imports pattern** (lines 1–10):
```typescript
import { useEffect, useMemo, useRef, useState, type DragEvent, type MouseEvent } from 'react';
import { useKeyboardDelete } from '../../hooks/useKeyboardDelete';
import { useGraphStore } from '../../state/graphStore';
import { NODE_WIDTH, PendingWireOverlay, portTop, Wire } from './Wire';
import { BlockNode } from './BlockNode';
```

**Local UI state pattern** (lines 16–18 — menu state belongs here, not store):
```typescript
const canvasRef = useRef<HTMLDivElement>(null);
const [pointer, setPointer] = useState({ x: 0, y: 0 });
const [isPaletteDragOver, setIsPaletteDragOver] = useState(false);
```

**Add:** `const [contextMenu, setContextMenu] = useState<null | { kind; x; y; targetId? }>(null)`

**Background hit-test** (lines 115, 128 — copy for canvas `onContextMenu`):
```tsx
onMouseDown={(event) => event.currentTarget === event.target && select(null)}
// SVG:
onMouseDown={(event) => event.currentTarget === event.target && select(null)}
```

**Canvas clamp constants** (lines 12–13, 103–105, 171 — export/share with `duplicateNode`):
```typescript
const CANVAS_WIDTH = 980;
const CANVAS_HEIGHT = 720;
const x = Math.max(8, Math.min(CANVAS_WIDTH - NODE_WIDTH - 8, point.x));
const y = Math.max(8, Math.min(CANVAS_HEIGHT - 140, point.y));
```

**Selected chrome wiring** (lines 165–174 — multi-select):
```tsx
selected={node.id === selectedId}
```
**Phase 3:** `selected={selectedIds.includes(node.id)}` (subscribe `selectedIds` from store).

**Mount ContextMenu** near return root (sibling of `.graph-canvas` or portal from child) when `contextMenu` non-null; pass items by `kind`.

---

### `src/components/canvas/BlockNode.tsx` (component, event-driven)

**Analog:** `src/components/canvas/BlockNode.tsx` (self)

**Imports pattern** (lines 1–9):
```typescript
import type { MouseEvent } from 'react';
import type { BlockInstance, PortDefinition } from '../../types/blocks';
import { getDef } from '../../graph/blockDefinitions';
import { Port } from './Port';
import { NODE_HEADER_HEIGHT, NODE_WIDTH, PORT_ROW_HEIGHT, portTop } from './Wire';
```

**Left-click only drag** (lines 52–54 — already ignores right-click; keep):
```typescript
const startDrag = (event: MouseEvent<HTMLDivElement>) => {
  if (event.button !== 0) return;
  onSelect(node.id);
  ...
};
```

**Select-before-action** (lines 54, 78 — copy for context menu):
```tsx
onMouseDown={startDrag}
onClick={() => onSelect(node.id)}
```

**Add prop + handler:**
```typescript
onContextMenu?: (nodeId: string, event: MouseEvent) => void;
// on root div:
onContextMenu={(event) => {
  event.preventDefault();
  event.stopPropagation();
  onContextMenu?.(node.id, event);
}}
```

**Display name** (line 82 — already live from store; rename updates this):
```tsx
<div className="block-name">{node.name}</div>
```

---

### `src/components/canvas/Wire.tsx` (component, event-driven)

**Analog:** `src/components/canvas/Wire.tsx` (self)

**Stop-propagation + select pattern** (lines 34–38 — extend with `onContextMenu`):
```tsx
<g
  className={`wire${selected ? ' wire-selected' : ''}`}
  data-edge-id={edge.id}
  onClick={(e) => { e.stopPropagation(); onClick?.(edge.id); }}
>
```

**Phase 3:**
```tsx
onContextMenu={(e) => {
  e.preventDefault();
  e.stopPropagation();
  onContextMenu?.(edge.id, e);
}}
```

Add optional `onContextMenu?: (edgeId: string, event: React.MouseEvent) => void` to Props (mirror `onClick`).

---

### `src/components/properties/PropertiesPanel.tsx` (component, event-driven)

**Analog:** `src/components/properties/ParamField.tsx` (controlled text) + `PropertiesPanel.tsx` (header/`h2`)

**Store subscription pattern** (PropertiesPanel lines 7–11):
```typescript
const selectedId = useGraphStore((s) => s.selectedId);
const node = useGraphStore((s) => s.nodes.find((item) => item.id === s.selectedId));
const updateParam = useGraphStore((s) => s.updateParam);
```

**Replace static name** (line 21):
```tsx
<h2>{node.name}</h2>
```

**Controlled text field pattern** (ParamField lines 56–61):
```tsx
<label className="param-field" htmlFor={id}>
  <span>{spec.label}</span>
  <input id={id} type="text" value={String(value)} onChange={(event) => onChange(event.target.value)} />
</label>
```

**Phase 3 Name field:**
```tsx
<label className="param-field" htmlFor="block-name-input">
  <span>Name</span>
  <input
    id="block-name-input"
    ref={nameInputRef}
    type="text"
    value={node.name}
    onChange={(e) => renameNode(node.id, e.target.value)}
    onBlur={() => {
      if (node.name.trim() === '') renameNode(node.id, lastNonEmptyRef.current);
    }}
  />
</label>
```

Keep `lastNonEmptyRef` updated when `node.name.trim()` is non-empty (on change / when selection changes). Focus from context Rename via `id="block-name-input"` + rAF `document.getElementById(...).focus()`, or store `pendingFocusName` flag cleared after focus.

**Param onChange → store** (lines 60–64 — same live-commit style):
```tsx
onChange={(value) => updateParam(node.id, param.key, value)}
```

---

### `src/styles/app.css` (config)

**Analog:** `src/styles/app.css` (self)

**Selected block chrome** (lines 352–355 — reuse for multi-select; no new class):
```css
.block-node.is-selected {
  border-color: #4a90d6;
  outline: 1px solid #4a90d6;
}
```

**Input chrome** (lines 176–185 — Name field):
```css
.param-field input,
.param-field select {
  width: 100%;
  min-width: 0;
  border: 1px solid #30383d;
  background: #111416;
  color: #dfe6ea;
  padding: 6px 7px;
}
```

**Overflow warning** (lines 298–300 — why portal):
```css
.graph-canvas {
  position: relative;
  overflow: auto;
  ...
}
```

**New rules to add** (UI-SPEC — mirror `.btn` / `.btn-estop` / `.toolbar-sep`):
```css
.context-menu {
  position: fixed;
  z-index: 1000;
  min-width: 160px;
  padding: 4px;
  border: 1px solid #30383d;
  border-radius: 0;
  background: #1a1f23;
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.25);
}
.context-menu-item {
  display: block;
  width: 100%;
  height: 28px;
  padding: 0 10px;
  border: none;
  background: transparent;
  color: #dfe6ea;
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}
.context-menu-item:hover { background: #1c2226; }
.context-menu-item.is-danger { color: #ec5a5a; }
.context-menu-item.is-danger:hover { background: #3a2020; color: #ffd9d9; }
.context-menu-sep {
  height: 1px;
  margin: 4px 0;
  background: #23292d;
}
```

## Shared Patterns

### Zustand store ownership
**Source:** `src/state/graphStore.ts`
**Apply to:** `renameNode`, `duplicateNode`, `selectAll`, `selectedIds`, `removeNodes`
- Graph mutations live in Zustand; canvas owns pointer geometry and menu open/close UI state
- Imperative reads via `useGraphStore.getState()` in window handlers (keyboard delete pattern)

### Select-before-open / preventDefault
**Source:** BlockNode drag select + GraphCanvas drop `preventDefault`
**Apply to:** Block / Wire / canvas `onContextMenu`
```typescript
event.preventDefault();
event.stopPropagation();
select(targetId); // or selectEdge
openMenu({ kind, x: event.clientX, y: event.clientY, targetId });
```

### Background target === currentTarget
**Source:** `GraphCanvas.tsx` lines 115, 128
**Apply to:** Canvas background context menu and empty deselect — avoid opening Select All when bubbling from Wire/Block

### Window listener lifecycle
**Source:** `GraphCanvas.tsx` lines 46–62; `useKeyboardDelete.ts` lines 25–26
**Apply to:** ContextMenu Escape + outside click; always pair add/remove in effect cleanup

### Controlled live inputs
**Source:** `ParamField.tsx` text/number `onChange` → store
**Apply to:** Properties Name field → `renameNode` every keystroke; blur empty revert via ref

### ID allocation
**Source:** `graphStore.ts` `addNode` (`B${nextId}`)
**Apply to:** `duplicateNode` — never invent UUIDs

### No new dependencies
**Source:** CONTEXT / RESEARCH lock
**Apply to:** All Phase 3 files — hand-roll menu; no Radix/floating-ui/hotkey libs

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| *(portal overlay)* | — | — | No `createPortal` usage in repo yet — use RESEARCH ContextMenu sketch; closest lifecycle analog is GraphCanvas window listeners |
| *(multi-select)* | — | — | `selectedIds` is new — extend existing `select`/`selectEdge` mutual exclusion |

*(Both are covered by partial analogs above; planner should not invent new architecture.)*

## Metadata

**Analog search scope:** `rehab-robotics-studio/src/**/*.{ts,tsx,css}` (canvas, properties, common, hooks, state, styles, chrome)
**Files scanned:** ~25 project source files (excluding node_modules)
**Strong analogs used:** 5 (`graphStore`, `useKeyboardDelete`, `GraphCanvas`, `ParamField`/`PropertiesPanel`, `BlockNode`/`Wire`)
**Pattern extraction date:** 2026-07-13
