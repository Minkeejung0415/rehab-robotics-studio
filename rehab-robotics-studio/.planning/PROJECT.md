# Rehab Robotics Studio

## What This Is

A LabVIEW-style visual programming environment for rehabilitation robotics, built with React + TypeScript + Zustand. Users wire together sensor sources, signal processing blocks, biomechanics models, motor controllers, and indicators on a node-graph canvas. Currently operates with mock data only (no real hardware backend).

## Core Value

Every UI element that exists must actually work — the frontend should feel like a complete, interactive application even without a real backend. If you can see it, you can interact with it.

## Requirements

### Validated

- ✓ Block diagram canvas with draggable nodes — existing
- ✓ Wired connections between blocks (visual, static) — existing
- ✓ Block palette with search and add (+/double-click) — existing
- ✓ Properties panel with editable parameters — existing
- ✓ Live dashboard (Force, EMG, Motor/Joint panels) — existing
- ✓ System log with clear button — existing
- ✓ Runtime state machine (Run/Pause/Stop/E-Stop/Reset) — existing
- ✓ Mock data source with graph executor — existing
- ✓ Save/Load project as JSON — existing
- ✓ Graph validation — existing
- ✓ Status strip with system indicators — existing

- Block/wire keyboard deletion and wire selection were validated in Phase 01.

### Active

- [ ] Interactive port-to-port wiring (drag from output to input)
- [ ] Drag-and-drop blocks from palette onto canvas
- [ ] Right-click context menu on blocks and wires
- [ ] Block renaming from properties panel
- [ ] Node status updates during execution (idle → running)
- [ ] Recording toggle (start/stop, status indicator updates)
- [ ] Deploy mock feedback (confirmation or status display)

### Out of Scope

- Real backend/hardware connectivity — future milestone
- ROS bridge integration — future milestone
- Multi-user collaboration — not needed
- Undo/redo — nice-to-have for a later phase

## Context

- React 18.3 + TypeScript + Vite 5 + Zustand 4.5
- Single-page app, no routing
- All data is mock/synthetic — MockDataSource generates frames at up to ~125 Hz
- SignalBus throttles React re-renders to ~30 fps
- Graph executor runs topological sort and evaluates blocks per frame
- Block definitions registry (blockDefinitions.ts) is the source of truth for all block types
- Store methods for all missing interactions already exist (removeNode, removeEdge, startWire, finishWire, cancelWire, setRecording) — they just lack UI triggers

## Constraints

- **No new dependencies**: Use only what's already installed (React, Zustand, Vite)
- **No backend**: Everything runs client-side with mock data
- **Preserve existing architecture**: Don't restructure stores or data flow patterns

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Mock-only frontend completion | User wants interactable UI before wiring backend | — Pending |
| Use existing store methods | removeNode, removeEdge, wiring methods already implemented | validated in Phase 01 for keyboard deletion |
| Default port IDs follow port names | Default graph edges use semantic port IDs, so omitted port IDs must match displayed port names | validated in Phase 01 for default wire rendering |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-13 after Phase 01 completion*
