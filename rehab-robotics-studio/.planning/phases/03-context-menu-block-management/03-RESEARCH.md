# Phase 3: Context Menu + Block Management - Research

**Researched:** 2026-07-13
**Domain:** React context menus, Zustand multi-select, block rename/duplicate
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Context Menu Behavior
- Hand-rolled fixed-position menu (no new npm dependencies)
- Close on Escape, outside click, or any menu action
- Position at cursor (clientX/Y), clamped to viewport
- Right-click selects the target first, then opens the menu

#### Rename Flow
- Properties panel name field only (BLK-01); context “Rename” selects the block and focuses that field
- Commit name on every keystroke via store (same pattern as ParamField)
- Revert to previous name on blur if empty
- Context menu “Rename”: select block → ensure properties visible → focus name input

#### Duplicate Behavior
- Copy type, name + `" copy"`, params, ports — new ID; do not copy wires
- Offset +40px X and +40px Y from original
- Auto-select the new copy after duplicate
- Duplicate entry point: context menu only (BLK-02)

#### Select All & Selection Model
- Minimal multi-select: `selectedIds: string[]` for blocks only; Select All fills it; Delete removes all selected; click still single-selects
- All selected blocks show selected styling
- Select All selects blocks only (not wires)
- Empty canvas click clears all; selecting a wire clears block multi-select

### Claude's Discretion
- Menu visual styling (match existing LabVIEW-inspired chrome)
- Exact focus timing for Rename (requestAnimationFrame vs setTimeout)
- How keyboard Delete interacts with `selectedIds` when multiple blocks are selected
- Whether renameNode is a dedicated store method or a general updateNode

### Deferred Ideas (OUT OF SCOPE)
- Full multi-select with marquee / shift-click (EDIT-03 / v2)
- Copy/paste clipboard (EDIT-02 / v2)
- Undo/redo (EDIT-01 / v2)
- Duplicate button in properties panel (not in BLK-02)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CTX-01 | Right-click a block → menu with Delete, Duplicate, Rename | Hand-roll `ContextMenu`; `onContextMenu` on `BlockNode`; reuse `removeNode` / add `duplicateNode`; Rename focuses properties Name field |
| CTX-02 | Right-click a wire → menu with Delete | `onContextMenu` on Wire `<g>`; call `selectEdge` then `removeEdge` |
| CTX-03 | Right-click canvas background → Select All | Background `onContextMenu` on `.graph-canvas` / SVG; store `selectAll` fills `selectedIds` |
| BLK-01 | Rename block from properties panel; canvas label updates | Replace static `<h2>` with controlled Name input; `renameNode` on each keystroke; empty blur reverts |
| BLK-02 | Duplicate via context menu with offset copy | `duplicateNode`: clone instance fields, `name + " copy"`, +40/+40, new id via `nextId`, no edges, auto-select |
</phase_requirements>

## Summary

Phase 3 extends the existing Zustand graph UI with a hand-rolled context menu and light block-management store APIs. Phases 1–2 already deliver selection, keyboard delete, wiring, and palette drop. This phase does **not** add npm packages: menu chrome follows `03-UI-SPEC.md` and existing `app.css` / `tokens.ts`. The main model change is introducing `selectedIds: string[]` alongside `selectedId` so Select All can highlight every block while PropertiesPanel continues to edit a single primary selection.

Duplicate and rename are store-owned graph mutations (same ownership pattern as `addNode` / `updateParam`). Context-menu open/close and cursor clamping are canvas/UI local state. Keyboard Delete must be updated to remove every id in `selectedIds` when multi-select is active — otherwise Select All is useless with Delete/Backspace.

**Primary recommendation:** Keep graph mutations in `graphStore` (`renameNode`, `duplicateNode`, `selectAll`, multi-aware `select` / `selectEdge` / `removeNode`); mount one shared `ContextMenu` overlay (prefer `createPortal` to `document.body` or a sibling outside `.graph-canvas` because that div has `overflow: auto`); wire `onContextMenu` on BlockNode, Wire, and canvas background with `preventDefault` + select-before-open; replace the properties `<h2>` with a ParamField-style Name input and a ref for Rename focus.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Context menu open/position/dismiss | Browser / Client | — | DOM `contextmenu` + fixed overlay; no server |
| Menu action dispatch | Browser / Client (Zustand) | UI overlay | Actions call store methods then close menu |
| Multi-select state (`selectedIds`) | Browser / Client (Zustand) | — | Graph selection is store-owned (Phases 1–2 pattern) |
| Primary selection (`selectedId`) | Browser / Client (Zustand) | PropertiesPanel | Panel edits one block; keep primary id |
| Rename commit / empty revert | Browser / Client (Zustand + panel) | — | Live store updates; blur validation in panel |
| Duplicate / Select All / Delete | Browser / Client (Zustand) | — | Mutates nodes/edges/selection in one place |
| Block/wire hit targets for right-click | Browser / Client (DOM/SVG) | — | Same surfaces as left-click selection |
| Keyboard multi-delete | Browser / Client (`useKeyboardDelete`) | Zustand | Extend existing window keydown hook |
| Visual selected chrome | Browser / Client (CSS) | — | Reuse `.block-node.is-selected` |

## Standard Stack

### Core (already installed — no installs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 18.3.1 (installed; registry latest 19.x unused) | `onContextMenu`, refs, effects for dismiss | Already in project [VERIFIED: npm ls / package.json] |
| react-dom | 18.3.1 | Optional `createPortal` for menu outside overflow | Already dependency; no new package [CITED: react.dev/reference/react-dom/createPortal] |
| Zustand | 4.5.7 (range ^4.5.5) | Graph + selection mutations | Existing store pattern [VERIFIED: npm ls] |
| TypeScript | 5.9.3 (dev; package pins ^5.6.3) | Typed menu state + store API | Existing [VERIFIED: npm ls] |
| Vite | 5.4.11 | Dev/build | Existing [VERIFIED: package.json] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| — | — | — | None. Hand-roll menu; no Radix/Headless UI. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled menu | `@radix-ui/react-context-menu` / floating-ui | Better a11y/positioning, but CONTEXT forbids new deps |
| `selectedIds` only | Keep single `selectedId` + fake Select All | Cannot show multi highlight or multi Delete |
| Portal to `document.body` | Absolute menu inside `.graph-canvas` | Canvas `overflow: auto` risks clip; portal avoids it |

**Installation:**

```bash
# No new packages — do not run npm install for this phase
```

**Version verification:** `npm ls react zustand typescript` on 2026-07-13 → react@18.3.1, zustand@4.5.7, typescript@5.9.3. Registry latest React is 19.2.7 — stay on project pin.

## Package Legitimacy Audit

> No external packages are installed in this phase. Section is not applicable.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | — | N/A |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Right-click (contextmenu)
        |
        +-- BlockNode -----------> preventDefault
        |       |                  select(nodeId)  [selectedId + selectedIds=[id]]
        |       v                  openMenu({ kind:'block', x,y, targetId })
        |   ContextMenu overlay
        |       |
        |       +-- Duplicate --> duplicateNode(id) --> close
        |       +-- Rename    --> select(id); close; focus Name input (rAF)
        |       +-- Delete    --> removeNode(id) [or multi] --> close
        |
        +-- Wire <g> ------------> preventDefault; stopPropagation
        |       |                  selectEdge(edgeId) [clears selectedIds]
        |       v                  openMenu({ kind:'wire', ... })
        |       +-- Delete --> removeEdge --> close
        |
        +-- Canvas / SVG bg -----> preventDefault (only when target===currentTarget)
                |                  openMenu({ kind:'canvas', ... })
                +-- Select All --> selectAll() --> close

PropertiesPanel Name input
        |
        onChange --> renameNode(id, value)  [live; updates .block-name]
        onBlur   --> if empty, renameNode(id, previousNonEmpty)

Keyboard Delete/Backspace (useKeyboardDelete)
        |
        if selectedIds.length > 0 --> remove all those nodes (batch)
        else if selectedEdgeId --> removeEdge
        (ignore when focus in INPUT/TEXTAREA/SELECT)
```

### Recommended Project Structure

```
src/
├── components/
│   ├── canvas/
│   │   ├── GraphCanvas.tsx      # menu state; bg contextmenu; pass handlers; mount overlay
│   │   ├── BlockNode.tsx        # onContextMenu → select + open block menu
│   │   └── Wire.tsx             # onContextMenu → selectEdge + open wire menu
│   ├── common/
│   │   └── ContextMenu.tsx      # NEW: fixed menu shell, items, clamp, dismiss
│   └── properties/
│       ├── PropertiesPanel.tsx  # Name field + ref/focus API for Rename
│       └── ParamField.tsx       # pattern reference only
├── hooks/
│   └── useKeyboardDelete.ts     # multi-select aware delete
├── state/
│   └── graphStore.ts            # selectedIds, renameNode, duplicateNode, selectAll
└── styles/
    └── app.css                  # .context-menu* rules per UI-SPEC
```

### Pattern 1: Select-before-open context menu

**What:** On `contextmenu`, call `event.preventDefault()`, update selection, then open the custom menu at `clientX`/`clientY`.
**When to use:** Block, wire, and canvas background menus (CTX-01/02/03).

```typescript
// Source: MDN Element: contextmenu event + React onContextMenu
// [CITED: https://developer.mozilla.org/en-US/docs/Web/API/Element/contextmenu_event]
// [CITED: https://react.dev/reference/react-dom/components/common#mouseevent-handler-props]
function onBlockContextMenu(event: React.MouseEvent, nodeId: string) {
  event.preventDefault();
  event.stopPropagation();
  select(nodeId); // also sets selectedIds = [nodeId]
  openMenu({ kind: 'block', x: event.clientX, y: event.clientY, targetId: nodeId });
}
```

### Pattern 2: Dual selection fields (`selectedId` + `selectedIds`)

**What:** Keep `selectedId` as the primary block for PropertiesPanel; keep `selectedIds` as the full multi-select set for chrome + multi-delete.
**When to use:** All selection mutations in Phase 3.

| Action | `selectedId` | `selectedIds` | `selectedEdgeId` |
|--------|--------------|---------------|------------------|
| `select(id)` | `id` | `[id]` | `null` |
| `select(null)` | `null` | `[]` | unchanged→ prefer clear edge too (match today) |
| `selectAll()` | keep current if ∈ nodes, else first node id | all node ids | `null` |
| `selectEdge(id)` | `null` | `[]` | `id` |
| `duplicateNode` | new id | `[newId]` | `null` |
| Empty canvas mousedown | `null` | `[]` | `null` |

**Recommendation (discretion):** `select(null)` should clear **both** block multi-select and edge selection (today’s `select(null)` already clears edge). `selectAll` should set `selectedId` to the previous primary if still present, else `nodes[0]?.id ?? null`, so the properties panel stays useful after Select All. [ASSUMED]

### Pattern 3: Viewport clamp for fixed menu

**What:** After measuring menu size (or using estimated min size), clamp `left`/`top` so the panel stays ≥4px inset from `window.innerWidth/innerHeight`.
**When to use:** Every open; re-clamp optional on resize while open.

```typescript
// Source: MDN CSS position:fixed — viewport-relative containing block
// [CITED: https://developer.mozilla.org/en-US/docs/Web/CSS/position#fixed]
function clampMenuPosition(x: number, y: number, width: number, height: number) {
  const pad = 4;
  const left = Math.min(Math.max(pad, x), window.innerWidth - width - pad);
  const top = Math.min(Math.max(pad, y), window.innerHeight - height - pad);
  return { left, top };
}
```

### Pattern 4: Rename focus after menu close

**What:** Close menu first, then focus the Name input on the next frame so the focus isn’t stolen by dismiss handlers.
**When to use:** Context “Rename” only.

**Recommendation (discretion):** Prefer double `requestAnimationFrame` (or `queueMicrotask` + one rAF) after setting selection; `setTimeout(..., 0)` is acceptable fallback. Expose `nameInputRef` from PropertiesPanel via callback ref prop or a tiny module-level/imperative handle — simplest is a `data-testid`/`id="block-name-input"` + `document.getElementById` after select, or lift a `focusNameRequest` counter in local App/canvas state that PropertiesPanel observes. Prefer **ref callback / shared request token in GraphCanvas→Properties via store flag** `pendingFocusName: boolean` cleared after focus — keeps App.tsx thin. [ASSUMED]

### Pattern 5: Duplicate without wires

**What:** Clone `type`, `name + " copy"`, shallow-copied `params`, `status: 'idle'` (or copy status — prefer `'idle'`), new `id` from `nextId`, position `+40,+40` clamped to canvas bounds used by `moveNode`/`addNode`. Do **not** copy edges. Ports live on `BlockDefinition`, not `BlockInstance` — “copy ports” means keep same `type` so ports come from the def.

```typescript
// Pattern aligned with existing makeNode / addNode in graphStore.ts
duplicateNode: (nodeId) =>
  set((s) => {
    const src = s.nodes.find((n) => n.id === nodeId);
    if (!src) return s;
    const id = `B${s.nextId}`;
    const x = Math.max(8, Math.min(980 - 220 - 8, src.position.x + 40));
    const y = Math.max(8, Math.min(720 - 140, src.position.y + 40));
    const copy: BlockInstance = {
      id,
      type: src.type,
      name: `${src.name} copy`,
      position: { x, y },
      params: { ...src.params },
      status: 'idle',
    };
    return {
      nodes: [...s.nodes, copy],
      nextId: s.nextId + 1,
      selectedId: id,
      selectedIds: [id],
      selectedEdgeId: null,
    };
  }),
```

Canvas constants `980` / `720` / `NODE_WIDTH` already live in GraphCanvas — either import shared constants or clamp inside the UI before calling a lower-level store insert. Prefer store duplicate with the same clamp numbers exported from Wire/GraphCanvas to avoid drift. [ASSUMED]

### Anti-Patterns to Avoid

- **Installing a menu library:** Violates locked “no new npm dependencies.”
- **Opening menu without `preventDefault`:** Native browser menu appears (MDN).
- **Leaving menu inside `.graph-canvas` without portal/sibling:** `overflow: auto` can clip the overlay.
- **Copying edges on duplicate:** Explicitly out of scope / locked “do not copy wires.”
- **Shift-click / marquee multi-select:** Deferred EDIT-03.
- **Treating Select All as selecting wires:** Locked blocks-only.
- **Silent `selectedIds` drift:** Forgetting to clear `selectedIds` in `selectEdge`, empty click, `startWire`, `load`, `removeNode`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Graph id allocation | Custom uuid scheme | Existing `nextId` / `B${n}` | Consistency with `addNode` |
| Param editing UX for name | New form library | ParamField-style controlled `<input>` | Already established |
| Wire/block delete semantics | Separate delete paths | `removeNode` / `removeEdge` | Connected edges already pruned |
| Keyboard shortcut infrastructure | New hotkey lib | Extend `useKeyboardDelete` | Phase 1 pattern + INPUT guard |
| Viewport positioning math beyond clamp | Floating-ui | Simple clamp with measured size | Locked no deps; menu is tiny |

**Key insight:** Complexity is selection-state hygiene (`selectedId` ↔ `selectedIds` ↔ `selectedEdgeId`), not the menu widget itself.

## Common Pitfalls

### Pitfall 1: Native browser menu still appears
**What goes wrong:** Custom menu and OS menu both show, or only OS menu.
**Why it happens:** Missing `event.preventDefault()` on `contextmenu`.
**How to avoid:** Always preventDefault on block/wire/canvas handlers; stopPropagation on nested targets so canvas doesn’t also open.
**Warning signs:** OS menu flashes on right-click during QA.

### Pitfall 2: Wrong menu from event bubbling
**What goes wrong:** Right-click wire opens canvas Select All, or block opens canvas menu.
**Why it happens:** SVG/`div` events bubble; background handler doesn’t check `target === currentTarget`.
**How to avoid:** Wire/Block `stopPropagation`; background only when empty target (same pattern as Phase 1 deselect).
**Warning signs:** Select All appears when right-clicking a wire.

### Pitfall 3: Select All + Delete only removes one block
**What goes wrong:** Multi highlight works; Delete removes `selectedId` only.
**Why it happens:** `useKeyboardDelete` still reads only `selectedId`.
**How to avoid:** Delete all of `selectedIds` (batch `set` preferred); also update context Delete for blocks to remove primary or all selected if multi. UI-SPEC: keyboard Delete with multi-select removes all selected.
**Warning signs:** After Select All + Delete, most blocks remain.

### Pitfall 4: `selectedIds` not cleared with wire select / empty click
**What goes wrong:** Blocks stay highlighted while a wire is selected.
**Why it happens:** `selectEdge` only nulls `selectedId` today.
**How to avoid:** Extend `selectEdge` / empty `select(null)` / `startWire` / `load` to clear `selectedIds`.
**Warning signs:** Blue outlines remain on blocks after wire click.

### Pitfall 5: Rename focus races menu dismiss
**What goes wrong:** Name input never focuses, or focus returns to body.
**Why it happens:** Outside-click/Escape listeners or menu unmount steal focus in the same tick.
**How to avoid:** Close menu → then rAF focus; register outside dismiss on `pointerdown` with capture and ignore clicks inside the menu.
**Warning signs:** Rename leaves menu closed but caret not in Name field.

### Pitfall 6: Empty name stuck on canvas
**What goes wrong:** Block title becomes blank string.
**Why it happens:** Live keystroke commit without blur revert.
**How to avoid:** Keep last non-empty name in a ref; on blur if `trim()===''`, `renameNode` back.
**Warning signs:** Empty `.block-name` after clearing the field and tabbing away.

### Pitfall 7: Duplicate off-canvas / ID collision
**What goes wrong:** Copy placed outside visible canvas or reuses id.
**Why it happens:** No clamp; not incrementing `nextId`.
**How to avoid:** Reuse `addNode` id scheme; clamp like GraphCanvas move/drop.
**Warning signs:** Copy invisible until scroll; React key warnings.

### Pitfall 8: Firefox Shift+right-click
**What goes wrong:** Custom menu never opens (native menu only).
**Why it happens:** Firefox quirk — Shift+right-click skips `contextmenu` (MDN).
**How to avoid:** Document as known platform quirk; do not block on it for acceptance.
**Warning signs:** Only reproduces with Shift held in Firefox.

## Code Examples

### ContextMenu shell (dismiss + clamp)

```tsx
// Source patterns: MDN contextmenu preventDefault; MDN position:fixed
// [CITED: https://developer.mozilla.org/en-US/docs/Web/API/Element/contextmenu_event]
// [CITED: https://developer.mozilla.org/en-US/docs/Web/CSS/position#fixed]
import { useEffect, useLayoutEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

type MenuItem = { id: string; label: string; danger?: boolean; onSelect: () => void; separatorBefore?: boolean };

export function ContextMenu(props: {
  x: number;
  y: number;
  items: MenuItem[];
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    const pad = 4;
    el.style.left = `${Math.min(Math.max(pad, props.x), window.innerWidth - width - pad)}px`;
    el.style.top = `${Math.min(Math.max(pad, props.y), window.innerHeight - height - pad)}px`;
  }, [props.x, props.y, props.items]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') props.onClose();
    };
    const onPointer = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) props.onClose();
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('mousedown', onPointer);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('mousedown', onPointer);
    };
  }, [props.onClose]);

  return createPortal(
    <div ref={ref} className="context-menu" role="menu" style={{ position: 'fixed', zIndex: 1000 }}>
      {props.items.map((item) => (
        <div key={item.id}>
          {item.separatorBefore && <div className="context-menu-sep" />}
          <button
            type="button"
            role="menuitem"
            className={`context-menu-item${item.danger ? ' is-danger' : ''}`}
            onClick={() => {
              item.onSelect();
              props.onClose();
            }}
          >
            {item.label}
          </button>
        </div>
      ))}
    </div>,
    document.body,
  );
}
```

### Store selection helpers (sketch)

```typescript
// Align with existing graphStore select/selectEdge mutual exclusion
select: (id) =>
  set({
    selectedId: id,
    selectedIds: id ? [id] : [],
    selectedEdgeId: null,
  }),

selectEdge: (id) =>
  set({
    selectedEdgeId: id,
    selectedId: null,
    selectedIds: [],
  }),

selectAll: () =>
  set((s) => {
    const ids = s.nodes.map((n) => n.id);
    const primary =
      s.selectedId && ids.includes(s.selectedId) ? s.selectedId : ids[0] ?? null;
    return { selectedIds: ids, selectedId: primary, selectedEdgeId: null };
  }),

renameNode: (nodeId, name) =>
  set((s) => ({
    nodes: s.nodes.map((nd) => (nd.id === nodeId ? { ...nd, name } : nd)),
  })),
```

**Discretion recommendation:** Use dedicated `renameNode` (not a generic `updateNode`) — mirrors `updateParam` specificity and keeps call sites clear. [ASSUMED]

### Keyboard multi-delete

```typescript
// Extend Phase 1 hook pattern — imperative getState()
const { selectedIds, selectedEdgeId, removeNode, removeEdge } = useGraphStore.getState();
if (selectedIds.length > 0) {
  event.preventDefault();
  // Prefer one store action removeNodes(selectedIds) to avoid stale intermediate state
  selectedIds.forEach((id) => removeNode(id)); // OK if removeNode is rewritten to batch, or add removeNodes
  return;
}
```

**Better:** add `removeNodes(ids: string[])` that filters nodes/edges once and clears selection fields. [ASSUMED]

### Menu item copy (exact — UI-SPEC)

| Target | Items |
|--------|-------|
| Block | `Duplicate` · `Rename` · separator · `Delete` |
| Wire | `Delete` |
| Canvas | `Select All` |

Duplicate display name: `` `${originalName} copy` `` (single space + literal `copy`).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single `selectedId` only | `selectedId` + `selectedIds` | Phase 3 | Enables Select All without full EDIT-03 |
| Static properties `<h2>` name | Controlled Name input | Phase 3 | BLK-01 live rename |
| OS context menu only | Hand-rolled fixed menu | Phase 3 | CTX-01/02/03 |
| Menu libraries (Radix etc.) | No new deps | Locked | Match Phases 1–2 |

**Deprecated/outdated:**
- Assuming Phase 3 needs floating-ui / Radix — locked out by CONTEXT.
- Treating “ports” as instance fields — ports remain on `BlockDefinition` via `type`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Keep both `selectedId` and `selectedIds`; Select All sets primary to previous-or-first | Pattern 2 | Properties panel empty after Select All if primary left null |
| A2 | Dedicated `renameNode` preferred over generic `updateNode` | Discretion | Naming only — low risk |
| A3 | Rename focus via rAF + store flag or `#block-name-input` | Pattern 4 | Focus may need one extra tick on slow machines |
| A4 | Duplicate resets `status` to `'idle'` | Pattern 5 | If user expected copied status, badge differs |
| A5 | Portal to `document.body` preferred over in-canvas absolute | Stack / Structure | Sibling mount also OK if outside overflow container |
| A6 | Batch `removeNodes` preferred for multi-delete | Pitfall 3 | Looping `removeNode` can work if each reads fresh state |

## Open Questions

1. **Primary selection after Select All**
   - What we know: UI-SPEC allows `selectedId` or first of `selectedIds` for Name edits.
   - What's unclear: Whether Select All should force a primary or leave `selectedId` null until click.
   - Recommendation: Keep/set primary (Assumption A1) so properties stay populated.

2. **Context Delete with multi-select already active**
   - What we know: Right-click selects target first (single-select), so block menu Delete typically deletes one.
   - What's unclear: If future UX opens menu without collapsing multi-select.
   - Recommendation: After select-before-open, Delete removes the menu target (single). Keyboard Delete remains the multi path.

3. **UI-SPEC checker still pending**
   - What we know: `03-UI-SPEC.md` is draft; checker sign-off unchecked.
   - What's unclear: Whether spacing exceptions change during check.
   - Recommendation: Planner treat UI-SPEC as source of truth unless checker amends it.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | typecheck/build | ✓ | v24.18.0 | — |
| npm | scripts | ✓ | 11.16.0 | — |
| React/Zustand (installed) | app | ✓ | 18.3.1 / 4.5.7 | — |
| Browser (manual QA) | contextmenu gestures | ✓ (dev machine) | — | Playwright/Chromium as in Phase 1–2 |
| Test runner (Vitest/Jest) | automated unit tests | ✗ | — | `npm run typecheck` + `npm run build` + browser checks |
| Knowledge graph | cross-doc query | ✗ | — | Codebase grep only |

**Missing dependencies with no fallback:**
- None for implementation (code/config only).

**Missing dependencies with fallback:**
- Unit test framework → use typecheck/build + manual/browser acceptance (same as Phases 1–2).

Step 2.6 external services: SKIPPED beyond Node/npm (no DB/API).

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | none installed (no Vitest/Jest/Playwright in package.json) |
| Config file | none — see Wave 0 |
| Quick run command | `npm run typecheck` |
| Full suite command | `npm run typecheck && npm run build` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CTX-01 | Block right-click menu; Duplicate/Rename/Delete work | manual / browser | `npm run typecheck` (compile only) | ❌ Wave 0 |
| CTX-02 | Wire right-click Delete | manual / browser | `npm run typecheck` | ❌ Wave 0 |
| CTX-03 | Canvas Select All selects all blocks | manual / browser | `npm run typecheck` | ❌ Wave 0 |
| BLK-01 | Properties Name edits update canvas label; empty blur reverts | manual / browser | `npm run typecheck` | ❌ Wave 0 |
| BLK-02 | Duplicate offsets +40,+40, name suffix, no wires | manual / browser | `npm run typecheck` | ❌ Wave 0 |
| GRAPH-01/02 regression | Keyboard delete still works; multi-delete after Select All | manual / browser | `npm run typecheck` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `npm run typecheck`
- **Per wave merge:** `npm run typecheck && npm run build`
- **Phase gate:** Full suite green + browser checklist before `/gsd:verify-work`

### Browser acceptance checklist (phase gate)

1. Right-click block → Duplicate / Rename / separator / Delete; native OS menu suppressed.
2. Duplicate → new block at +40,+40, name ends with ` copy`, no new wires, copy selected.
3. Rename menu item → properties Name focused; typing updates `.block-name`; clear + blur restores previous.
4. Right-click wire → Delete removes wire only.
5. Right-click empty canvas → Select All; all blocks `.is-selected`; wires not selected.
6. Empty canvas left-click clears multi-select; wire click clears block multi-select.
7. After Select All, Delete/Backspace removes all selected blocks (and their wires).
8. Phase 1–2: port wiring, palette drop, single delete still work.

### Wave 0 Gaps

- [ ] No unit test framework — **do not add** (phase forbids new deps; match Phases 1–2). Treat Wave 0 as documenting manual/browser gates only.
- [ ] Optional later (out of phase): Vitest for `duplicateNode` / `selectAll` pure store tests — only if a future phase allows installing a runner.
- [ ] Framework install: **none** — if none detected, rely on `typecheck` + `build` + browser checklist above.

*(Existing test infrastructure does not cover phase requirements; Wave 0 = accept typecheck/build + manual browser verification as the Nyquist sampling commands.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | N/A — no auth |
| V3 Session Management | no | N/A |
| V4 Access Control | no | Single-user desktop mock UI |
| V5 Input Validation | yes | Rename: controlled string; empty blur revert; React text escaping for display |
| V6 Cryptography | no | N/A |
| V7 Error Handling | partial | Silent revert OK per UI-SPEC; optional exact error copy if shown |
| V8 Data Protection | no | In-memory graph only |
| V14 Config | no | No secrets |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| HTML injection via block name | Tampering | React escapes text nodes; don’t use `dangerouslySetInnerHTML` |
| Accidental mass delete | Elevation of privilege (UX) | No confirm modal (parity with keyboard delete); out of scope undo |
| Native menu bypass / unexpected clipboard | Information disclosure | `preventDefault` on handled targets only — don’t disable context menu app-wide |
| Prototype pollution via params clone | Tampering | Shallow `{ ...params }` of known ParamValue primitives only |

## Sources

### Primary (HIGH confidence)

- Codebase: `src/state/graphStore.ts`, `GraphCanvas.tsx`, `BlockNode.tsx`, `Wire.tsx`, `PropertiesPanel.tsx`, `ParamField.tsx`, `useKeyboardDelete.ts`, `types/blocks.ts`, `styles/app.css`, `theme/tokens.ts`
- `.planning/phases/03-context-menu-block-management/03-CONTEXT.md` — locked decisions
- `.planning/phases/03-context-menu-block-management/03-UI-SPEC.md` — visual/interaction contract
- `.planning/REQUIREMENTS.md` — CTX-01/02/03, BLK-01/02
- Prior: `01-RESEARCH.md`, `01-01-SUMMARY.md`, `02-RESEARCH.md`, `02-01-SUMMARY.md`
- [CITED: https://developer.mozilla.org/en-US/docs/Web/API/Element/contextmenu_event] — preventDefault, Firefox Shift quirk
- [CITED: https://react.dev/reference/react-dom/components/common#mouseevent-handler-props] — `onContextMenu`
- [CITED: https://react.dev/reference/react-dom/createPortal] — portal for overlays
- [CITED: https://developer.mozilla.org/en-US/docs/Web/CSS/position#fixed] — fixed = viewport positioning
- [VERIFIED: package.json / npm ls] — React 18.3.1, Zustand 4.5.7, no test runner

### Secondary (MEDIUM confidence)

- Community hand-rolled React context menu patterns (Pluralsight guide) — used only to corroborate preventDefault + client coordinates; implementation follows CONTEXT/UI-SPEC not that guide’s global document listener

### Tertiary (LOW confidence)

- None material

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; versions verified via npm ls
- Architecture: HIGH — maps cleanly onto existing store/canvas split; selection dual-field design recommended with explicit assumptions
- Pitfalls: HIGH — derived from existing event patterns + MDN contextmenu behavior

**Research date:** 2026-07-13
**Valid until:** 2026-08-12 (30 days — stable React/DOM APIs; project-local patterns dominate)
