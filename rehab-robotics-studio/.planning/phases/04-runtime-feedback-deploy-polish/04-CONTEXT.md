# Phase 4: Runtime Feedback + Deploy Polish - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Users receive live visual feedback during Run/Stop, recording, and Deploy Mock: all block status badges flip to running/idle with runtime; a toolbar Rec button toggles the status-strip Recording indicator; Deploy Mock shows a brief hand-rolled toast in addition to the existing log entry. No real hardware deploy, animated wire flow, or per-block progress percentages.

</domain>

<decisions>
## Implementation Decisions

### Run/Stop Block Status Badges
- On Run, every block on the canvas gets status `"running"`
- On Pause, badges stay `"running"` (RUNTIME pill shows paused)
- On Stop / E-STOP / Reset, all badges return to `"idle"`
- Update badges synchronously via a graphStore bulk setter called from runtime actions

### Recording Toggle + Deploy Toast
- Toolbar Rec button after Stop (before Validate); label toggles `● Rec` / `○ Rec`
- Disable Rec when estopped/faulted (same as Run/Deploy)
- Hand-rolled top-center toast via portal (~2.5s auto-dismiss), plus existing deploy log
- Toast copy: `Deploy (mock) started — graph would be pushed to Jetson`

### Feedback Polish & Edge Cases
- Single toast at a time — replace previous if still visible
- Auto-dismiss ~2.5s; also click-to-dismiss
- Rec button shows pressed/active chrome when recording On (align with strip red fault-level light)
- Out of scope: real deploy, animated wire flow, per-block progress %

### Claude's Discretion
- Exact graphStore API name (`setAllNodeStatuses` vs `setNodesStatus`)
- Toast component file location (common/ vs chrome/)
- Whether run() from paused path re-asserts running badges
- CSS token choices within LabVIEW chrome (no new deps)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/state/runtimeStore.ts` — run/pause/stop/estop/reset (never touches node.status today)
- `src/state/systemStore.ts` — `setRecording(on)` already updates status strip Recording light
- `src/state/actions.ts` — `deployMock()` logs only
- `src/components/chrome/Toolbar.tsx` — Run/Pause/Stop/Validate/Deploy/Save/Load
- `src/components/chrome/StatusStrip.tsx` — Recording indicator already rendered
- `src/components/canvas/BlockNode.tsx` — `.status-badge` renders `node.status` with statusColor
- Phase 3 `ContextMenu` portal pattern for toast overlay

### Established Patterns
- No new npm dependencies — hand-roll toast like ContextMenu
- Zustand store split: runtime / system / graph; cross-store via getState() or actions
- LabVIEW dark chrome via existing `.btn` / tokens

### Integration Points
- Wire runtimeStore run/stop/estop/reset → graphStore bulk status
- Toolbar: Rec button → setRecording; Deploy → toast + existing log
- Mount toast host in App or Toolbar

</code_context>

<specifics>
## Specific Ideas

Toast message exactly: `Deploy (mock) started — graph would be pushed to Jetson`

</specifics>

<deferred>
## Deferred Ideas

- Real Jetson deploy / hardware push
- Animated data flow on wires (VIS-01)
- Per-block progress or warning/error simulation during run
- Tabbed workspace layout (Phase 5)

</deferred>
