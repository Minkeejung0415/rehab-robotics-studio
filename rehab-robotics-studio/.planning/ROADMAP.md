# Roadmap: Rehab Robotics Studio

## Overview

The frontend exists and renders correctly, but most interactions are decorative. This roadmap wires up every non-functional UI element — from keyboard-driven block deletion through interactive wiring to runtime status feedback — so the application feels complete and usable without any backend. Four phases, each delivering a coherent and independently verifiable set of interactions, working from the lowest-friction fixes (keyboard shortcuts) up to the highest-fidelity feedback (runtime badges and deploy toast).

## Phases

This roadmap now has five phases; Phase 5 adds a tabbed workspace layout after the existing interaction and runtime work.

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Block & Wire Selection + Deletion** - Keyboard Delete/Backspace removes selected blocks and wires from the canvas (completed 2026-07-13)
- [x] **Phase 2: Interactive Wiring + Palette Drag-Drop** - Users can draw new wires by dragging port-to-port and place blocks by dragging from the palette (completed 2026-07-13)
- [x] **Phase 3: Context Menu + Block Management** - Right-click menus on blocks, wires, and canvas; inline rename and duplicate from properties panel (completed 2026-07-13)
- [x] **Phase 4: Runtime Feedback + Deploy Polish** - Block status badges reflect execution state; recording toggle and deploy confirmation work end-to-end (completed 2026-07-13)
- [x] **Phase 5: Tabbed Workspace Layout** - LabVIEW-style tab bar switches between Block Diagram (graph editor) and Front Panel (live dashboard) views (completed 2026-07-13)

## Phase Details

### Phase 1: Block & Wire Selection + Deletion

**Goal**: Users can remove blocks and wires from the canvas using the keyboard
**Depends on**: Nothing (first phase)
**Requirements**: GRAPH-01, GRAPH-02
**Success Criteria** (what must be TRUE):

  1. User can click a block on the canvas, press Delete or Backspace, and the block disappears along with all its connected wires
  2. User can click a wire and it visually highlights to indicate selection
  3. User can press Delete or Backspace after selecting a wire and the wire is removed from the canvas
  4. Clicking empty canvas space deselects any selected block or wire

**Plans**: TBD
**UI hint**: yes

### Phase 2: Interactive Wiring + Palette Drag-Drop

**Goal**: Users can build and extend the node graph interactively by drawing wires and placing blocks
**Depends on**: Phase 1
**Requirements**: GRAPH-03, GRAPH-04
**Success Criteria** (what must be TRUE):

  1. User can click and drag from an output port and a dashed preview line follows the cursor
  2. Releasing the drag over a compatible input port creates a permanent wire between the two ports
  3. Pressing Escape or releasing the drag over empty canvas cancels the wire preview without creating a connection
  4. User can drag a block type from the palette sidebar and drop it onto the canvas; the block appears at the cursor drop position

**Plans**: TBD
**UI hint**: yes

### Phase 3: Context Menu + Block Management

**Goal**: Users can manage blocks and wires through right-click menus and the properties panel
**Depends on**: Phase 2
**Requirements**: CTX-01, CTX-02, CTX-03, BLK-01, BLK-02
**Success Criteria** (what must be TRUE):

  1. Right-clicking a block shows a context menu with Delete, Duplicate, and Rename options, each of which executes correctly
  2. Right-clicking a wire shows a context menu with a Delete option that removes the wire
  3. Right-clicking the canvas background shows a context menu with Select All that selects every block on the canvas
  4. User can edit the block name field in the properties panel and the block's label on the canvas updates to match
  5. Selecting Duplicate from a block's context menu creates an offset copy of that block on the canvas

**Plans**: 2 plans
Plans:
**Wave 1**

- [x] 03-01-PLAN.md — Store multi-select, rename, duplicate, batch remove + keyboard multi-delete

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02-PLAN.md — Context menu UI, properties Name field, canvas/block/wire wiring

**UI hint**: yes

### Phase 4: Runtime Feedback + Deploy Polish

**Goal**: Users receive live visual feedback during execution, recording, and deployment actions
**Depends on**: Phase 3
**Requirements**: RT-01, RT-02, DEP-01
**Success Criteria** (what must be TRUE):

  1. When the user clicks Run, every block on the canvas shows a "running" status badge; when the user clicks Stop, badges return to "idle"
  2. A recording button is visible in the toolbar; clicking it toggles the Recording indicator in the status strip between active and inactive states
  3. Clicking the Deploy Mock button shows a brief toast or banner confirmation that the deploy action was triggered, in addition to the existing log entry

**Plans**: 2 plans
Plans:
**Wave 1**

- [x] 04-01-PLAN.md — graphStore setAllNodeStatuses + runtimeStore badge sync (RT-01)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 04-02-PLAN.md — Rec toolbar toggle + Deploy Mock portal toast (RT-02, DEP-01)

**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Block & Wire Selection + Deletion | 1/1 | Complete   | 2026-07-13 |
| 2. Interactive Wiring + Palette Drag-Drop | 1/1 | Complete    | 2026-07-13 |
| 3. Context Menu + Block Management | 2/2 | Complete   | 2026-07-13 |
| 4. Runtime Feedback + Deploy Polish | 2/2 | Complete   | 2026-07-13 |
| 5. Tabbed Workspace Layout | 1/1 | Complete | 2026-07-13 |

### Phase 5: Tabbed Workspace Layout

**Goal:** Add a LabVIEW-style tab bar to switch between Block Diagram (graph editor) and Front Panel (live dashboard)
**Requirements**: TAB-01, TAB-02, TAB-03, TAB-04, TAB-05
**Depends on:** Phase 4
**Plans:** 1 plan

Plans:

- [x] 05-01-PLAN.md — Tab strip + App.tsx conditional workspace rendering + CSS
