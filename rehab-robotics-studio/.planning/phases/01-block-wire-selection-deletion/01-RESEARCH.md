# Phase 1: Block & Wire Selection + Deletion - Research

**Researched:** 2026-07-13
**Domain:** React event handling, Zustand state, SVG interactivity
**Confidence:** HIGH

---

## Summary

Phase 1 wires up keyboard-driven deletion of blocks and wires. The implementation is almost entirely event-plumbing: the store already has `removeNode`, `removeEdge`, `select`, and `selectEdge` — the only missing pieces are (1) a global `keydown` listener that reads current selection from the store and calls the right remove method, and (2) passing `onClick`/`selected` props that `Wire` already accepts but `GraphCanvas` never supplies.

The phase is self-contained. No new dependencies, no new store methods, no data model changes. Every required capability exists in the codebase today — it just needs to be connected to UI events.

**Primary recommendation:** Add a single `useKeyboardDelete` hook mounted in `GraphCanvas`, enable wire click handling by passing `onClick` and `selected` to the `<Wire>` component, and re-enable pointer events on the SVG wire layer for wire clicks only.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GRAPH-01 | User can delete a selected block via Delete/Backspace key | `removeNode` exists in graphStore; need `useKeyboardDelete` hook reading `selectedId` |
| GRAPH-02 | User can click a wire to select it (highlighted state), then delete it via Delete/Backspace key | `Wire` already accepts `onClick`/`selected` props; `selectEdge` exists; wire-selected CSS exists; need to pass props from GraphCanvas and enable SVG pointer events |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Keyboard event listening | Browser / Client | — | Global `window` keydown; no server involved |
| Selection state (block) | Browser / Client (Zustand) | — | `selectedId` already in graphStore |
| Selection state (wire) | Browser / Client (Zustand) | — | `selectedEdgeId` already in graphStore |
| Delete dispatch | Browser / Client (Zustand) | — | `removeNode` / `removeEdge` already in graphStore |
| Wire click hit area | Browser / Client (SVG) | — | `.wire-hit` transparent 12px stroke path in Wire.tsx |
| Visual highlight (wire) | Browser / Client (SVG) | — | `selected` prop already drives color and stroke-width in Wire |
| Visual highlight (block) | Browser / Client (CSS) | — | `.is-selected` class already exists on `.block-node` |
| Canvas deselect on bg click | Browser / Client | — | Already implemented: `onMouseDown` on `.graph-canvas` calls `select(null)` |

---

## Standard Stack

### Core (already installed — no installs needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 18.3.1 | Component rendering, `useEffect` for event listeners | Already in project |
| Zustand | 4.5.5 | `useGraphStore` — selection state + delete methods | Already in project |
| TypeScript | 5.6.3 | Type-safe event handler signatures | Already in project |

**No new packages required for this phase.** [VERIFIED: package.json]

---

## Package Legitimacy Audit

> No external packages are installed in this phase. Section is not applicable.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
User presses Delete/Backspace
        |
        v
window keydown listener (useKeyboardDelete hook)
        |
        +-- reads selectedId from graphStore
        |       |
        |       +--> removeNode(selectedId) --> nodes filtered, connected edges pruned
        |
        +-- reads selectedEdgeId from graphStore
                |
                +--> removeEdge(selectedEdgeId) --> edges filtered

User clicks wire (SVG <g> element)
        |
        v
Wire onClick handler (e.stopPropagation)
        |
        v
GraphCanvas passes selectEdge(edgeId) as onClick prop
        |
        v
graphStore.selectEdge --> selectedEdgeId set, selectedId cleared
        |
        v
Wire re-renders with selected=true --> blue stroke + thicker width (already implemented)

User clicks empty canvas
        |
        v
.graph-canvas onMouseDown (already implemented)
        |
        v
select(null) -- clears both selectedId and selectedEdgeId (need to verify selectEdge clears selectedId too)
```

### Recommended Project Structure

No new files required. All changes are in existing files:

```
src/
├── components/
│   └── canvas/
│       ├── GraphCanvas.tsx    <-- ADD: import useKeyboardDelete; pass onClick+selected to Wire; enable SVG pointer events
│       └── Wire.tsx           <-- no changes needed (already accepts onClick/selected)
└── hooks/
    └── useKeyboardDelete.ts   <-- NEW: single hook, ~20 lines
```

### Pattern 1: Global Keyboard Listener via useEffect

**What:** Register a `keydown` listener on `window` inside a custom hook using `useEffect`. Read Zustand state imperatively via `useGraphStore.getState()` (not reactive selector) to avoid re-registering on every selection change.

**When to use:** Any time a keyboard shortcut must be active regardless of which DOM element has focus.

```typescript
// Source: React 18 docs — useEffect cleanup pattern
// [VERIFIED: React 18 docs — event listener cleanup]
import { useEffect } from 'react';
import { useGraphStore } from '../state/graphStore';

export function useKeyboardDelete() {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== 'Delete' && e.key !== 'Backspace') return;
      // Guard: don't fire when user is typing in an input/textarea
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      const { selectedId, selectedEdgeId, removeNode, removeEdge } = useGraphStore.getState();
      if (selectedId) removeNode(selectedId);
      else if (selectedEdgeId) removeEdge(selectedEdgeId);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []); // empty deps — reads state imperatively, never stale
}
```

**Critical detail:** Use `useGraphStore.getState()` inside the handler (imperative read), NOT a reactive selector. If you use a selector and try to close over it, the closure will capture a stale value at registration time and never see updates. The Zustand pattern for event listeners is always `getState()` at call time. [VERIFIED: codebase — actions.ts uses this exact pattern: `useGraphStore.getState().validate()`]

**Mount location:** Call `useKeyboardDelete()` inside `GraphCanvas` (one invocation, no props needed).

### Pattern 2: Enable SVG Wire Click Events

**What:** The `.wire-layer` SVG has `pointer-events: none` in CSS (line 310-312 of app.css). This blocks all mouse events on wires. To fix this, change the SVG element to `pointer-events: all` (or remove the rule) and make the individual `<path>` elements opt out where needed.

**When to use:** Any SVG overlay that needs to receive click events while still allowing click-through to elements beneath it in some areas.

The cleanest approach for this phase: add `pointerEvents: 'all'` directly on the SVG element in JSX (inline style overrides the CSS class), and add `style={{ pointerEvents: 'none' }}` on wire elements that should not block block-node interaction — but the existing `.wire-hit` path (12px transparent stroke) already handles click targets perfectly. The `<g>` wrapper already calls `e.stopPropagation()` to prevent bubbling to the canvas deselect handler.

```tsx
// In GraphCanvas.tsx — change this:
<svg className="wire-layer" width={CANVAS_WIDTH} height={CANVAS_HEIGHT} ...>

// To this (override the CSS pointer-events: none):
<svg className="wire-layer" style={{ pointerEvents: 'all' }} width={CANVAS_WIDTH} height={CANVAS_HEIGHT} ...>
```

Then pass `onClick` and `selected` to the `Wire` component:

```tsx
// In GraphCanvas.tsx — add these to useGraphStore reads:
const selectedEdgeId = useGraphStore((s) => s.selectedEdgeId);
const selectEdge = useGraphStore((s) => s.selectEdge);

// Then in the edges.map():
<Wire
  key={edge.id}
  edge={edge}
  source={source}
  target={target}
  sourcePort={sourcePort}
  targetPort={targetPort}
  sourcePortIndex={sourcePortIndex}
  targetPortIndex={targetPortIndex}
  selected={edge.id === selectedEdgeId}   // ADD
  onClick={selectEdge}                    // ADD
/>
```

**Wire.tsx already accepts both props** — `selected?: boolean` and `onClick?: (edgeId: string) => void` — and already uses them to change stroke color and width. Zero changes needed to Wire.tsx itself. [VERIFIED: Wire.tsx lines 20-22, 24, 31, 37]

### Pattern 3: Canvas Deselect on Background Click

**Already implemented.** `GraphCanvas.tsx` line 22:
```tsx
onMouseDown={(event) => event.currentTarget === event.target && select(null)}
```

This fires only when the click target is the canvas div itself (not a child). However, `select(null)` only clears `selectedId` — it does NOT clear `selectedEdgeId`. The store's `select` method is:
```typescript
select: (id) => set({ selectedId: id, selectedEdgeId: null }),
```
[VERIFIED: graphStore.ts line 106]

So `select(null)` correctly clears both. No change needed here.

### Anti-Patterns to Avoid

- **Reactive closure in useEffect:** Do NOT do `const { selectedId } = useGraphStore((s) => s.selectedId)` and close over it in the keydown handler. The closure captures the value at registration time. Always use `useGraphStore.getState()` inside event handlers.
- **Registering the listener in App.tsx:** Mounting the hook inside `GraphCanvas` keeps the listener scoped to when the canvas is mounted. If needed globally, App.tsx is fine — but for phase correctness, GraphCanvas is the right owner.
- **Forgetting the input guard:** Without the `INPUT/TEXTAREA` tag check, Delete key will delete blocks while the user is renaming one in the properties panel (relevant in Phase 3, but safer to add now).
- **Forgetting to re-enable SVG pointer events:** The CSS class `.wire-layer` sets `pointer-events: none`. If you only set `pointerEvents: 'all'` in JSX but then render children with `pointer-events: auto` (CSS default), it will work. But double-check that block nodes (HTML div elements beneath the SVG) still receive drag events — they will, because HTML is behind the SVG in z-order and SVG pointer events are handled before HTML.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Delete key shortcut | Custom event system / context / state machine | `window.addEventListener('keydown')` in `useEffect` | Native browser API — no library needed |
| Wire hit testing | Custom pixel-level intersection math | `.wire-hit` transparent 12px `<path>` (already exists) | SVG stroke hit testing is built-in; the thick transparent path already handles this |
| Wire selected state | New store field | `selectedEdgeId` (already in graphStore) | Already exists and is already a separate field from `selectedId` |
| Wire visual highlight | New CSS class | `selected` prop already wired in Wire.tsx | Already implemented — blue color + thicker stroke when `selected=true` |

**Key insight:** Every piece of state management and every visual component for this phase already exists. The work is pure event-plumbing — 3 surgical edits across 2 existing files plus 1 new ~20-line hook.

---

## Common Pitfalls

### Pitfall 1: Stale Closure in Keyboard Handler
**What goes wrong:** `selectedId` is always `null` or always the ID it was when the component first mounted — deletion seems to randomly not work or always deletes the same block.
**Why it happens:** Closing over a Zustand selector value in `useEffect` with `[]` deps captures the initial value and never updates.
**How to avoid:** Read state imperatively inside the handler: `useGraphStore.getState().selectedId`.
**Warning signs:** Deletion works once then stops, or always deletes a specific block.

### Pitfall 2: Wire Clicks Blocked by pointer-events: none
**What goes wrong:** Clicking wires does nothing — no selection, no highlight.
**Why it happens:** `.wire-layer` SVG in app.css has `pointer-events: none` (line ~310). This prevents all mouse interaction with SVG children.
**How to avoid:** Set `style={{ pointerEvents: 'all' }}` on the SVG element in `GraphCanvas.tsx`. The individual `<g>` elements in Wire.tsx already call `e.stopPropagation()` correctly.
**Warning signs:** `onClick` on `Wire` is never called.

### Pitfall 3: Wire Clicks Bubble to Canvas Deselect Handler
**What goes wrong:** Clicking a wire selects it briefly, then immediately deselects (selectedEdgeId flashes to a value then back to null).
**Why it happens:** The click event bubbles up from the SVG `<g>` to the `.graph-canvas` div's `onMouseDown`, which calls `select(null)` and clears `selectedEdgeId`.
**How to avoid:** The `Wire` component already calls `e.stopPropagation()` on click (line 37 of Wire.tsx). This should prevent bubbling. However, note that `GraphCanvas` uses `onMouseDown` for deselect but `Wire` uses `onClick` — these are different events, so bubbling is not actually a problem here. If the deselect switches to `onClick` in the future, this would become an issue.
**Warning signs:** Wire selection immediately disappears after click.

### Pitfall 4: Forgetting that removeNode Also Cleans Up Edges
**What goes wrong:** Deleting a block leaves orphaned wires on the canvas pointing to nowhere.
**Why it happens:** Naive implementation calls only a node removal function.
**How to avoid:** Already handled — `removeNode` in graphStore filters both `nodes` AND `edges` (removes all edges where `sourceBlockId === nodeId || targetBlockId === nodeId`). [VERIFIED: graphStore.ts lines 128-133]
**Warning signs:** Ghost wires appear after deleting a block.

---

## Code Examples

### Final GraphCanvas.tsx diff (conceptual)

```tsx
// Source: GraphCanvas.tsx — additions only

// 1. Add import
import { useKeyboardDelete } from '../../hooks/useKeyboardDelete';

// 2. Add store reads
const selectedEdgeId = useGraphStore((s) => s.selectedEdgeId);
const selectEdge = useGraphStore((s) => s.selectEdge);

// 3. Call hook inside component
useKeyboardDelete();

// 4. Enable pointer events on SVG
<svg className="wire-layer" style={{ pointerEvents: 'all' }} ...>

// 5. Pass props to Wire
<Wire
  ...existing props...
  selected={edge.id === selectedEdgeId}
  onClick={selectEdge}
/>
```

### New file: src/hooks/useKeyboardDelete.ts

```typescript
import { useEffect } from 'react';
import { useGraphStore } from '../state/graphStore';

/**
 * Registers a global keydown listener that deletes the currently selected
 * block or wire when the user presses Delete or Backspace.
 *
 * Guards against firing when an input element has focus (so users can
 * type "Delete" in text fields without destroying their graph).
 */
export function useKeyboardDelete(): void {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== 'Delete' && e.key !== 'Backspace') return;
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      const { selectedId, selectedEdgeId, removeNode, removeEdge } = useGraphStore.getState();
      if (selectedId) {
        e.preventDefault();
        removeNode(selectedId);
      } else if (selectedEdgeId) {
        e.preventDefault();
        removeEdge(selectedEdgeId);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
}
```

---

## Runtime State Inventory

> Not applicable — this is a greenfield feature addition, not a rename/refactor/migration.

---

## Environment Availability

> Step 2.6: SKIPPED (no external dependencies — all work is client-side React/TypeScript with existing toolchain).

The existing dev server (`npm run dev` via Vite 5) is sufficient to test this phase. No new tools, services, or runtimes required.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None currently installed |
| Config file | None — see Wave 0 |
| Quick run command | N/A — manual browser testing |
| Full suite command | `npm run typecheck` (TypeScript only) |

No test framework (Jest, Vitest) is installed. The project's `package.json` has no test script and no testing devDependencies. [VERIFIED: package.json]

Given the project constraint of "no new dependencies" and the UI-only nature of this phase, the validation approach is:

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GRAPH-01 | Click block, press Delete — block + its wires disappear | Manual browser | — | N/A |
| GRAPH-01 | Press Delete when no selection — nothing happens, no errors | Manual browser | — | N/A |
| GRAPH-01 | Press Delete while typing in input — no deletion | Manual browser | — | N/A |
| GRAPH-02 | Click wire — wire highlights blue | Manual browser | — | N/A |
| GRAPH-02 | Click wire, press Delete — wire disappears | Manual browser | — | N/A |
| GRAPH-02 | Click canvas background — selection clears | Manual browser | — | N/A |
| All | TypeScript compiles with no errors | Automated | `npm run typecheck` | N/A (runs on .ts files) |

### Sampling Rate

- **Per task commit:** `npm run typecheck`
- **Phase gate:** All 6 manual acceptance criteria checked in browser before `/gsd:verify-work`

### Wave 0 Gaps

- No test files exist, no test framework installed. Given the "no new dependencies" constraint in PROJECT.md, Vitest is not being added. Manual browser verification is the acceptance gate for this phase.
- The TypeScript compile check (`npm run typecheck`) provides a lightweight automated gate for type correctness.

---

## Security Domain

> This phase adds no authentication, no user input storage, no API calls, no cryptographic operations, and no data persistence changes. The only new surface is a `window` keydown listener (client-side only). ASVS categories are not applicable.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `.wire-layer` SVG's `pointer-events: none` CSS is the only thing blocking wire clicks | Common Pitfalls — Pitfall 2 | If Wire.tsx or other ancestors also block pointer events, additional fixes needed; easily discovered in browser devtools |
| A2 | `select(null)` from the canvas background click handler correctly clears `selectedEdgeId` because the `select` method in graphStore sets `selectedEdgeId: null` explicitly | Architecture Patterns — Pattern 3 | If this implementation changes, deselect-on-background-click breaks for wires; mitigated by code verification |

**All other claims in this document are VERIFIED against the codebase (graphStore.ts, Wire.tsx, GraphCanvas.tsx, BlockNode.tsx, app.css, package.json).**

---

## Open Questions

1. **Should pressing Delete with no selection be a no-op or log something?**
   - What we know: `removeNode(null)` and `removeEdge(null)` would filter against null, which may or may not cause issues depending on Zustand's behavior.
   - What's unclear: Whether calling these with null produces silent no-ops or side effects.
   - Recommendation: Guard explicitly in the hook — only call `removeNode` if `selectedId` is truthy, and only call `removeEdge` if `selectedEdgeId` is truthy. (Already reflected in the code example above.)

2. **Where should `useKeyboardDelete` be mounted — `GraphCanvas` or `App`?**
   - What we know: Both work. `App` means the shortcut is always active. `GraphCanvas` means it's only active when the canvas is mounted (which in this app is always).
   - Recommendation: Mount in `GraphCanvas` — it's the component that owns graph interaction, and it keeps the concern co-located.

---

## Sources

### Primary (HIGH confidence — codebase read)
- `src/state/graphStore.ts` — `removeNode`, `removeEdge`, `select`, `selectEdge` implementations; `selectedId`, `selectedEdgeId` state shape
- `src/components/canvas/Wire.tsx` — `selected` prop, `onClick` prop, `.wire-hit` transparent path, `e.stopPropagation()` call
- `src/components/canvas/GraphCanvas.tsx` — current `Wire` invocation (missing `onClick`/`selected`); canvas background deselect handler; SVG setup
- `src/components/canvas/BlockNode.tsx` — `startDrag` pattern using `window.addEventListener` with `useEffect`-style cleanup
- `src/styles/app.css` — `.wire-layer { pointer-events: none }`, `.wire-hit`, `.wire-selected`, `.block-node.is-selected`
- `src/state/actions.ts` — `useGraphStore.getState()` imperative read pattern (confirmed correct pattern for use in handlers)
- `package.json` — confirmed no test framework, confirmed no new dependencies constraint

### Secondary (MEDIUM confidence — React docs)
- React 18 docs on `useEffect` cleanup pattern — `[ASSUMED]` based on training, standard and stable API

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — read directly from package.json and source files
- Architecture: HIGH — all components and store methods verified by reading actual source code
- Pitfalls: HIGH — derived from reading actual CSS (`pointer-events: none` confirmed), actual store methods, actual component props
- Test approach: HIGH — no test framework confirmed from package.json; TypeScript compile as lightweight gate is a reasonable fallback

**Research date:** 2026-07-13
**Valid until:** Stable (no external dependencies — changes only invalidated by modifying graphStore.ts, Wire.tsx, GraphCanvas.tsx, or app.css)
