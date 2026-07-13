# Phase 2: Interactive Wiring + Palette Drag-Drop - Research

**Researched:** 2026-07-13
**Domain:** React mouse and native drag-drop events, SVG canvas overlays, Zustand graph actions
**Confidence:** HIGH

## Summary

Phase 2 is UI event plumbing over existing graph state. `graphStore` already exposes `startWire`, `finishWire`, and `cancelWire`; `Wire.tsx` already exports `PendingWireOverlay`; and `BlockLibrary` already owns the available block definitions and calls `addNode`. The missing work is to expose output/input port events, track the canvas-relative pointer position for the preview, cancel safely on Escape/background release, and carry a palette block type through native drag-and-drop.

**Primary recommendation:** Keep graph lifecycle rules in `graphStore`; add interaction callbacks to `Port` and `BlockNode`; let `GraphCanvas` coordinate preview geometry, target compatibility, cancellation, and canvas drop placement. Extend the existing library item rather than introducing a second palette component.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GRAPH-03 | Drag output port to compatible input port with dashed preview and cancellation | `startWire`, `finishWire`, `cancelWire`, `pendingWire`, and `PendingWireOverlay` exist but are not mounted or triggered |
| GRAPH-04 | Drag palette block onto canvas at drop location | `addNode(type, x, y)` already accepts coordinates; `LibraryItem` can publish `def.type` through `dataTransfer` |
</phase_requirements>

## Implementation Map

| Capability | Owner | Existing support | Required work |
|------------|-------|------------------|---------------|
| Wire lifecycle | `graphStore` | `startWire`, `finishWire`, `cancelWire`, duplicate target guard | Invoke existing actions from UI events |
| Preview rendering | `GraphCanvas` + `PendingWireOverlay` | SVG component receives source and target coordinates | Track pointer canvas coordinates and render only while `pendingWire` exists |
| Port hit targets | `Port` / `BlockNode` | Semantic port IDs and signal types from block definitions | Surface output start and input finish callbacks without starting node drag |
| Compatibility | `GraphCanvas` | `pendingWire.signalType`, input port signal type | Only finish on matching signal type; otherwise cancel on mouseup |
| Escape cancellation | Canvas interaction hook/effect | `cancelWire` store action | Listen while a wire is pending and remove listener on cleanup |
| Palette transfer | `LibraryItem` / `BlockLibrary` | `def.type`, existing `addNode` and system logger | Set a custom `dataTransfer` type, allow graph-canvas drops, and translate client position to bounded canvas coordinates |

## Existing Patterns To Preserve

- `GraphCanvas` owns canvas-specific selection, bounds, and interaction coordination.
- `BlockNode` currently handles node movement through window-level mousemove/mouseup listeners; port event handlers must stop propagation so a terminal drag does not also move the node.
- Canvas dimensions are fixed at `980 x 720`; node positions are clamped through existing `NODE_WIDTH` and height bounds.
- `select(null)` and `selectEdge(null)` preserve mutual exclusion of node/wire selection. Starting a wire already clears both in `startWire`.
- Default port IDs are semantic port names. Use `PortDefinition.id`, not the display name, in wire store calls.
- The workspace is desktop-only and adds no dependencies.

## Interaction Contract

1. Pointer down on an output terminal starts a pending wire at that terminal's canvas coordinates.
2. Pointer movement updates the dashed preview endpoint in canvas coordinates.
3. Pointer release on a compatible input terminal calls `finishWire`; store clears the pending wire and creates an edge unless that input is already connected.
4. Pointer release on the canvas or Escape calls `cancelWire`; no edge is added.
5. A palette item sets its type in `dataTransfer`; a graph-canvas drop prevents the browser default, converts the drop point relative to the canvas element, and calls `addNode` with bounded coordinates.
6. Existing plus-button and double-click palette placement remain intact.

## Pitfalls

- Do not use viewport client coordinates directly for graph state; subtract the graph canvas bounding rectangle (and account for scroll offsets if the canvas remains scrollable).
- Do not use a target port's display label as the port ID; edges resolve against semantic `PortDefinition.id` values.
- Do not let terminal `mousedown` bubble into `BlockNode.startDrag`; it would move the source node while wiring.
- Do not finish into mismatched signal types or an output port. The preview may remain neutral; only compatible inputs may call `finishWire`.
- Do not leave a pending wire after background mouseup, dragend, or Escape.
- Do not replace the current palette's click/double-click affordances while adding draggable behavior.

## Validation Strategy

No test framework is installed and the project forbids new dependencies. Use `npm run typecheck` after each implementation task, `npm run build` at phase completion, and production-preview browser checks for drag gestures.

| Requirement | Automated check | Browser acceptance |
|-------------|-----------------|-------------------|
| GRAPH-03 | `npm run typecheck` | Preview follows cursor; compatible drop creates one edge; empty drop and Escape cancel; duplicate target connection is not added |
| GRAPH-04 | `npm run typecheck` | Drag a palette item onto the visible canvas and confirm a new selected node appears at the drop location; existing plus/double-click still work |

## Sources

- `src/state/graphStore.ts` - pending wire state, lifecycle actions, add-node coordinates, and existing target-port guard.
- `src/components/canvas/GraphCanvas.tsx` - canvas dimensions, SVG layout, selection behavior, and node bounds.
- `src/components/canvas/Wire.tsx` - port geometry helpers and unused `PendingWireOverlay`.
- `src/components/canvas/BlockNode.tsx` and `src/components/canvas/Port.tsx` - node drag handling and terminal rendering.
- `src/components/library/BlockLibrary.tsx` and `src/components/library/LibraryItem.tsx` - palette grouping and current add behavior.
- `src/graph/blockDefinitions.ts` and `src/types/blocks.ts` - canonical port IDs, directions, and signal types.
- `.planning/phases/01-block-wire-selection-deletion/01-01-SUMMARY.md` - Phase 1 selection/deselection behavior that must remain intact.

