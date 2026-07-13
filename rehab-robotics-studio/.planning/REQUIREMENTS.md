# Requirements: Rehab Robotics Studio

**Defined:** 2026-07-13
**Core Value:** Every UI element that exists must actually work — the frontend should feel like a complete, interactive application even without a real backend.

## v1 Requirements

Requirements for completing all frontend interactivity. Each maps to roadmap phases.

### Graph Interaction

- [ ] **GRAPH-01**: User can delete a selected block via Delete/Backspace key
- [ ] **GRAPH-02**: User can click a wire to select it (highlighted state), then delete it via Delete/Backspace key
- [ ] **GRAPH-03**: User can drag from an output port to an input port to create a new wire, with a dashed preview line while dragging
- [ ] **GRAPH-04**: User can drag a block from the palette onto the canvas to place it at the drop location

### Context Menu

- [ ] **CTX-01**: User can right-click a block to see a context menu with Delete, Duplicate, and Rename options
- [ ] **CTX-02**: User can right-click a wire to see a context menu with Delete option
- [ ] **CTX-03**: User can right-click canvas background to see a context menu with Select All option

### Block Management

- [ ] **BLK-01**: User can rename a block inline from the properties panel
- [ ] **BLK-02**: User can duplicate a block via context menu, placing the copy offset from the original

### Runtime Feedback

- [ ] **RT-01**: Block status badges update to "running" when execution starts and back to "idle" when stopped
- [ ] **RT-02**: User can toggle recording on/off from a toolbar button, which updates the Recording status strip indicator

### Deploy

- [ ] **DEP-01**: Deploy Mock button shows a brief visual confirmation (toast/banner) in addition to logging

## v2 Requirements

### Advanced Editing

- **EDIT-01**: User can undo/redo actions on the canvas
- **EDIT-02**: User can copy/paste blocks across canvas
- **EDIT-03**: User can multi-select blocks with shift-click or drag-select

### Visual Enhancements

- **VIS-01**: Animated data flow along wires when running
- **VIS-02**: Block grouping / sub-graph nesting

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real hardware backend | Future milestone — this is mock-only completion |
| ROS bridge integration | Requires backend infrastructure |
| Multi-user collaboration | Not needed for single-user tool |
| Custom block scripting execution | Python/MATLAB blocks are mock stubs |
| Mobile responsive layout | Desktop-only LabVIEW-style tool |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| GRAPH-01 | Phase 1 | Pending |
| GRAPH-02 | Phase 1 | Pending |
| GRAPH-03 | Phase 2 | Pending |
| GRAPH-04 | Phase 2 | Pending |
| CTX-01 | Phase 3 | Pending |
| CTX-02 | Phase 3 | Pending |
| CTX-03 | Phase 3 | Pending |
| BLK-01 | Phase 3 | Pending |
| BLK-02 | Phase 3 | Pending |
| RT-01 | Phase 4 | Pending |
| RT-02 | Phase 4 | Pending |
| DEP-01 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0

---
*Requirements defined: 2026-07-13*
*Last updated: 2026-07-13 after initial definition*
