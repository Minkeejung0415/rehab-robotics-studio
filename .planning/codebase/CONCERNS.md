# Codebase Concerns

**Analysis Date:** 2026-07-13

---

## Tech Debt

**Entire hardware layer is stubbed / mocked:**
- Issue: Every real hardware integration (ROS bridge, Jetson Orin, Red Pitaya TCP, EtherCAT motor driver, OpenSim solver, Python/MATLAB plugins, CSV file I/O) is marked with runtime type `'mock'`, `'ros-later'`, or `'plugin-later'`. None of the actual acquisition, control, or recording pipelines exist.
- Files: `rehab-robotics-studio/src/graph/blockDefinitions.ts` (all `runtime: 'mock'` blocks), `rehab-robotics-studio/src/state/actions.ts` (`deployMock` logs only), `rehab-robotics-studio/src/data/MockDataSource.ts`, `rehab-robotics-studio/src/data/DataSource.ts`
- Impact: The app is purely a UI prototype. No path to production exists until each stub is replaced with a real implementation. The `DataSource` interface is the correct seam, but the `SignalBus` constructor hard-codes `mockDataSource` as the singleton — no runtime swap mechanism exists.
- Fix approach: Implement `RosbridgeDataSource` and `RedPitayaDataSource` conforming to `DataSource.ts`. Make `SignalBus` accept a `DataSource` at construction time (dependency injection) rather than importing `mockDataSource` directly.

**`nextId` / `nextEdgeId` counters are not persisted:**
- Issue: `graphStore.ts` initialises `nextId: 12` and `nextEdgeId: 8` as hard-coded constants that match the 11-node default graph. If a saved project is loaded with more nodes, these counters will produce colliding IDs (e.g. loading a 20-node graph resets counters to 12/8).
- Files: `rehab-robotics-studio/src/state/graphStore.ts` (lines 103–104, 176–179)
- Impact: After a `load()`, the next `addNode` or `addEdge` will silently generate an ID that already exists in the graph, causing duplicate-key React warnings and undefined behaviour in the executor and wire renderer.
- Fix approach: Derive `nextId` / `nextEdgeId` from the loaded document in `graphStore.load()` by scanning `doc.nodes` and `doc.edges` for the highest numeric suffix and incrementing from there.

**`logSeq` is a module-level mutable singleton:**
- Issue: `systemStore.ts` (line 10) uses a bare `let logSeq = 0` outside the Zustand store. This is module-level mutable state that survives store resets and is shared across any hypothetical hot-reloads.
- Files: `rehab-robotics-studio/src/state/systemStore.ts` (line 10)
- Impact: Log IDs will not reset when the store is cleared, which is minor in prototype context but creates a correctness trap if the store is ever torn down and re-created (e.g. in tests or server-side rendering).
- Fix approach: Move `logSeq` inside the Zustand store state, or derive log IDs from `Date.now() + Math.random()` to avoid the counter entirely.

**`RingBuffer` uses `Array.shift()` — O(n) dequeue:**
- Issue: `signalBus.ts` `RingBuffer.push()` appends to an array and calls `Array.shift()` to remove the head (line 16). `shift()` is O(n) because it re-indexes every element.
- Files: `rehab-robotics-studio/src/data/signalBus.ts` (lines 14–17)
- Impact: At 125 Hz with a buffer of 240 samples the impact is negligible on modern hardware, but if the buffer size or tick rate grows (e.g. 4 kHz EMG), this becomes a measurable hot path. Every ingest call re-allocates the internal array via `toArray()` on snapshot as well.
- Fix approach: Replace with a true circular buffer using a fixed-length `Float32Array` and a write-index pointer. This is the standard approach for real-time signal buffers.

**`MiniChart` calls `Math.min(...data)` / `Math.max(...data)` via spread:**
- Issue: `MiniChart.tsx` (lines 29–30) spreads the full 240-element data array into `Math.min` / `Math.max`. This is fine at 240 samples but will hit the JS call-stack argument limit at large buffer sizes.
- Files: `rehab-robotics-studio/src/components/common/MiniChart.tsx` (lines 29–30)
- Fix approach: Use a `for` loop or `Array.prototype.reduce` to compute min/max without spread.

**Block node renaming is commented-out / not wired:**
- Issue: `types/blocks.ts` line 74 contains `/** Display name (defaults to the definition name, user-renameable later). */`. The `BlockInstance.name` field exists but no UI or store action allows the user to rename a node.
- Files: `rehab-robotics-studio/src/types/blocks.ts` (line 74), `rehab-robotics-studio/src/state/graphStore.ts`
- Impact: Minor UX gap; each block of the same type is visually indistinguishable by name once multiple instances are placed.

**Canvas is a fixed-size absolute-positioned div with hard-coded dimensions:**
- Issue: `GraphCanvas.tsx` hard-codes `CANVAS_WIDTH = 980` and `CANVAS_HEIGHT = 720`. The SVG wire layer uses these as fixed `width`/`height` attributes. Block dragging is clamped to these limits.
- Files: `rehab-robotics-studio/src/components/canvas/GraphCanvas.tsx` (lines 7–8, 54)
- Impact: On large monitors the canvas is undersized; on smaller screens nodes can overflow outside the visible area with no scroll. There is no pan or zoom support.
- Fix approach: Measure the container with a `ResizeObserver` and update dimensions reactively, or switch to a virtualised canvas approach with pan/zoom transforms.

**Duplicate geometry constants between `GraphModel.ts` and `Wire.tsx`:**
- Issue: Canvas geometry (node width, header height, port row height) is defined twice: once in `rehab-robotics-studio/src/graph/GraphModel.ts` (`NODE_W = 178`, `HEADER_H = 30`, `PORT_ROW_H = 22`) and once in `rehab-robotics-studio/src/components/canvas/Wire.tsx` (`NODE_WIDTH = 220`, `NODE_HEADER_HEIGHT = 34`, `PORT_ROW_HEIGHT = 22`). The values differ (`NODE_W` is 178 in GraphModel but 220 in Wire.tsx).
- Files: `rehab-robotics-studio/src/graph/GraphModel.ts` (lines 6–11), `rehab-robotics-studio/src/components/canvas/Wire.tsx` (lines 4–6)
- Impact: Wire endpoints computed from `GraphModel` geometry will not align with node ports rendered using `Wire.tsx` geometry. The default graph likely has visually misaligned wires relative to port dots. `GraphModel.ts` geometry functions (`inPortPos`, `outPortPos`) appear to be dead code — `GraphCanvas.tsx` and `Wire.tsx` recompute port positions locally.
- Fix approach: Delete the geometry constants in `GraphModel.ts` (or promote them to a single `geometry.ts` module). Import from a single source of truth.

---

## Known Bugs

**Wire endpoint misalignment due to dual geometry constants:**
- Symptoms: Wires drawn by `Wire.tsx` may not connect visually to the port triangles rendered by `Port.tsx` inside `BlockNode.tsx` because `NODE_WIDTH` is 178 in one file and 220 in the other.
- Files: `rehab-robotics-studio/src/components/canvas/Wire.tsx`, `rehab-robotics-studio/src/graph/GraphModel.ts`
- Trigger: Always visible on any graph with edges.
- Workaround: None — purely visual glitch.

**Loading a saved project resets `nextId`/`nextEdgeId` to stale defaults:**
- Symptoms: After `actions.loadProject()`, calling `addNode` produces an ID like `B12` even if the loaded graph already contains a `B12`. The duplicate ID causes the wrong node to be selected, its params may overwrite the wrong entry, and React `key` warnings fire.
- Files: `rehab-robotics-studio/src/state/graphStore.ts` (line 178)
- Trigger: Save a graph with more than 11 nodes, reload the page, load the saved file, then add a new node.
- Workaround: None currently.

**`signalBus` starts its `requestAnimationFrame` loop unconditionally at module load time:**
- Symptoms: Importing `signalBus` in any context (including unit tests or SSR) immediately schedules a RAF loop. In test environments without `requestAnimationFrame`, this silently no-ops; in SSR it would throw.
- Files: `rehab-robotics-studio/src/data/signalBus.ts` (lines 88–92)
- Trigger: Import `signalBus` in a Node.js test runner.
- Workaround: The guard `if (typeof requestAnimationFrame !== 'undefined')` is present but the loop is still attached to `mockDataSource.subscribe` unconditionally.

**`ingest()` calls `useGraphStore.getState()` on every data tick:**
- Symptoms: The `SignalBus.ingest` method reads `useGraphStore.getState()` on every data frame (up to 125×/second). This is a direct store read outside React, which is fine with Zustand, but it means graph topology changes are reflected immediately with no debounce. More critically, if the graph store ever moves to a context-based approach, this will break.
- Files: `rehab-robotics-studio/src/data/signalBus.ts` (line 100)
- Trigger: Structural concern, not a crash; acceptable for prototype.

---

## Security Considerations

**No input sanitisation on `deserializeGraph`:**
- Risk: `GraphModel.ts` `deserializeGraph()` calls `JSON.parse(json)` and casts the result directly to `GraphDocument` with only a minimal shape check (version, nodes, edges arrays). A malicious or malformed JSON file loaded by the user could inject arbitrary `type` strings, deeply nested structures, or non-numeric param values.
- Files: `rehab-robotics-studio/src/graph/GraphModel.ts` (lines 57–63), `rehab-robotics-studio/src/state/actions.ts` (line 47)
- Current mitigation: The `validateGraph` call is not triggered automatically on load; it is an explicit user action.
- Recommendations: Run `validateGraph` immediately after `load()` in `actions.loadProject`. Add a Zod/Valibot schema (or hand-written type guards) to validate node/edge shapes before accepting them into state.

**File path parameter stored in plain state with no sandboxing:**
- Risk: `csv_recorder_mock` block exposes a `path` param (`trial_001.csv`) that will eventually write to the filesystem. The text field accepts arbitrary input with no path traversal validation.
- Files: `rehab-robotics-studio/src/graph/blockDefinitions.ts` (line 272)
- Current mitigation: File IO is not yet implemented ("file IO later").
- Recommendations: When CSV recording is implemented, validate the path against an allowed directory prefix and reject `..` sequences.

**IP address param is unsanitised:**
- Risk: `fake_red_pitaya_stream` block has an `ip` text param (default `192.168.1.50`) with no format validation. When the TCP connection is implemented, this value will be used to open a socket.
- Files: `rehab-robotics-studio/src/graph/blockDefinitions.ts` (line 106)
- Current mitigation: TCP connection not yet implemented.
- Recommendations: Validate against an IP/hostname regex before connecting. Restrict to RFC 1918 private ranges if only local hardware is supported.

---

## Performance Bottlenecks

**`topoSort` runs on every data frame:**
- Problem: `runMockExecutor` (called inside `signalBus.ingest`) calls `topoSort(nodes, edges)` on every tick (up to 125 Hz). `topoSort` rebuilds `indeg` and `adj` Maps from scratch each call.
- Files: `rehab-robotics-studio/src/graph/mockExecutor.ts` (line 111), `rehab-robotics-studio/src/graph/GraphModel.ts` (lines 69–94)
- Cause: No memoisation of the sorted order. The graph topology only changes when the user edits the diagram, which is rare compared to the tick rate.
- Improvement path: Cache the topo-sorted node order in the graph store whenever nodes/edges change. Pass the cached order into the executor. Invalidate cache on any `addNode`, `removeNode`, `addEdge`, `removeEdge`.

**`incomingValue` linear scan inside executor result extraction:**
- Problem: `runMockExecutor` (lines 128–131) calls `edges.find(...)` once per indicator block type to extract the value feeding each indicator. With many edges this is O(n) per indicator type per frame.
- Files: `rehab-robotics-studio/src/graph/mockExecutor.ts` (lines 128–131)
- Cause: No index built over edges for fast lookup by target block ID.
- Improvement path: The already-built `portValues` map contains every output. The executor could tag output values by indicator type during the main sweep rather than scanning edges again.

**`LogsPanel` reverses the logs array on every render:**
- Problem: `LogsPanel.tsx` (line 14) calls `logs.slice().reverse()` inside the render function body. With the 300-entry cap this is a small O(n) allocation on every render triggered by any log update.
- Files: `rehab-robotics-studio/src/components/dashboard/LogsPanel.tsx` (line 14)
- Improvement path: Store logs in newest-first order in `systemStore`, or use CSS `flex-direction: column-reverse` which has zero JS cost.

---

## Fragile Areas

**`signalBus` constructor couples three modules at import time:**
- Files: `rehab-robotics-studio/src/data/signalBus.ts` (lines 87–92)
- Why fragile: The `SignalBus` constructor immediately calls `mockDataSource.subscribe(...)` and starts the RAF loop. This means importing `signalBus` anywhere in the module graph has global side effects (a live timer and an active listener). Circular import risk: `signalBus` imports `mockDataSource` and `useGraphStore`; `useGraphStore` imports nothing from `signalBus`, but any future cross-dependency could create a circular init.
- Safe modification: Do not add imports of `signalBus` into files that are already imported by `signalBus`. Extract the `start()` call to an explicit `signalBus.init()` method called in `main.tsx`.
- Test coverage: Zero — no tests exist.

**Graph execution result is hard-coded to three indicator types:**
- Files: `rehab-robotics-studio/src/graph/mockExecutor.ts` (lines 133–140)
- Why fragile: `runMockExecutor` only surfaces `force`, `emg`, and `knee` values by scanning for specific block types (`force_gauge`, `emg_chart`, `joint_angle_display`). Adding a new indicator block type requires modifying `mockExecutor`, `signalBus`, and `SignalSnapshot` in lockstep.
- Safe modification: Replace the hard-coded extraction with a generic map of `blockType → outputChannel` driven by block definitions, so new indicator types require only a new `blockDefinitions` entry.

**Canvas node drag uses raw `window.addEventListener`:**
- Files: `rehab-robotics-studio/src/components/canvas/BlockNode.tsx` (lines 57–66)
- Why fragile: Drag handling attaches `mousemove`/`mouseup` to `window` on `mousedown`. If the component unmounts mid-drag (e.g. node deleted while dragging), the listeners are never cleaned up, causing a stale closure reference to the unmounted component.
- Safe modification: Store a cleanup ref and remove listeners in a `useEffect` cleanup, or use the Pointer Events API with `element.setPointerCapture()`.

**`BlockNode` `NodeBody` always calls `useSignals()` regardless of `kind`:**
- Files: `rehab-robotics-studio/src/components/canvas/BlockNode.tsx` (lines 18–38)
- Why fragile: `useSignals()` subscribes every `NodeBody` render to the signal snapshot, meaning every block node on the canvas re-renders at ~30 fps even when the node has no live body (`kind === undefined`). With many blocks on the canvas this causes unnecessary React reconciliation work.
- Safe modification: Call `useSignals()` only inside the conditional branches that need it, or split `NodeBody` into separate components per kind.

---

## Scaling Limits

**Canvas has no pan/zoom — hard cap at ~3–4 blocks per column:**
- Current capacity: `CANVAS_WIDTH = 980px`, `CANVAS_HEIGHT = 720px`. Nodes are ~220px wide, so roughly 4 columns fit.
- Limit: A realistic pipeline (source → pre-process → controller → safety gate → motor command → recorder) with multiple signal chains exceeds canvas area immediately.
- Scaling path: Add SVG `transform` pan/zoom via mouse wheel + drag on the canvas background. The wire SVG layer and node div layer must be kept in sync (shared CSS `transform`).

**Block library search scans all definitions on every keystroke:**
- Current capacity: ~15 block definitions — negligible.
- Limit: When the library grows to hundreds of real blocks (ROS topic adapters, biomechanics models), the `useMemo` filter over `Object.values(BLOCK_DEFS)` will become noticeable.
- Scaling path: Pre-build a search index (e.g. with `fuse.js`) at startup rather than filtering the full set on every query change.

---

## Dependencies at Risk

**No linting, no testing framework:**
- Risk: The project has zero test files and no ESLint/Biome configuration. TypeScript strict mode is enabled but `noUnusedLocals` and `noUnusedParameters` are both `false`, meaning dead code accumulates silently.
- Files: `rehab-robotics-studio/tsconfig.json` (lines 17–18), `rehab-robotics-studio/package.json`
- Impact: Any regression in the mock executor or store logic is undetectable until manual UI testing. The safety-critical state machine (`runtimeStore`) has no unit tests.
- Migration plan: Add Vitest (compatible with Vite) and write unit tests for `validateGraph`, `topoSort`, `runMockExecutor`, and the `runtimeStore` state transitions.

**Single `mockDataSource` singleton — not replaceable at runtime:**
- Risk: `mockDataSource` is a module-level singleton (`MockDataSource.ts` line 118) imported directly by `signalBus.ts`. There is no mechanism to swap it for a real hardware source without a code change.
- Files: `rehab-robotics-studio/src/data/MockDataSource.ts` (line 118), `rehab-robotics-studio/src/data/signalBus.ts` (line 88)
- Impact: When transitioning from prototype to hardware, the singleton must be replaced, requiring refactoring of `SignalBus`.
- Migration plan: Pass the `DataSource` into `SignalBus` as a constructor argument. Export a factory function in `main.tsx` that selects the source based on a build flag or URL param.

---

## Missing Critical Features

**No real-time safety enforcement during execution:**
- Problem: The `safety_gate` block exists in the block library and clips values in the mock executor, but the clip value is used only to compute a `portValues` entry — it never triggers an actual system fault, e-stop, or motor disable in the `runtimeStore`.
- Blocks: `rehab-robotics-studio/src/graph/blockDefinitions.ts` (`safety_gate`), `rehab-robotics-studio/src/graph/mockExecutor.ts` (line 85), `rehab-robotics-studio/src/state/runtimeStore.ts`

**No undo/redo for graph edits:**
- Problem: Graph edits (add node, delete node, move node, add edge) are irreversible. There is no history stack. A misclick that deletes a wired block destroys all its connections permanently.
- Files: `rehab-robotics-studio/src/state/graphStore.ts`

**Port interaction (wire drawing) not connected to the Port component:**
- Problem: `Port.tsx` renders port terminals visually but has no `onClick`/`onMouseDown` handlers. `graphStore` has `startWire`/`finishWire`/`cancelWire` actions (lines 153–165), but no UI component calls them. The pending-wire feature is implemented in the store but not wired to the canvas interaction layer.
- Files: `rehab-robotics-studio/src/components/canvas/Port.tsx`, `rehab-robotics-studio/src/state/graphStore.ts` (lines 153–165)

**`deployMock` is a no-op log stub:**
- Problem: The Deploy button in the toolbar calls `actions.deployMock()` which only adds an INFO log. No graph serialisation, SSH, ROS param server push, or Jetson communication exists.
- Files: `rehab-robotics-studio/src/state/actions.ts` (lines 54–57)

---

## Test Coverage Gaps

**State machine transitions (runtimeStore) — untested:**
- What's not tested: The `idle → running → paused → estopped → idle` state machine, including the `can()` guard function and invalid-transition rejection.
- Files: `rehab-robotics-studio/src/state/runtimeStore.ts`
- Risk: A broken transition guard could allow the UI to run the motor in an e-stopped state.
- Priority: High

**Graph validation logic — untested:**
- What's not tested: `validateGraph` edge cases: edges to missing blocks, type mismatches, safety gate violations, disconnected required inputs.
- Files: `rehab-robotics-studio/src/graph/validation.ts`
- Risk: Silent false-positives or false-negatives in the safety check (`safeForMotorControl` propagation).
- Priority: High

**Topological sort with cycles — untested:**
- What's not tested: `topoSort` cycle detection (falls back to declaration order with no user-visible warning).
- Files: `rehab-robotics-studio/src/graph/GraphModel.ts` (line 91)
- Risk: A cyclic graph runs without error in mock mode but will silently produce incorrect values (executor reads stale `portValues` for the cycle).
- Priority: Medium

**Graph serialisation round-trip — untested:**
- What's not tested: `serializeGraph` → `deserializeGraph` identity, version field enforcement, handling of unknown block types after a definition is removed.
- Files: `rehab-robotics-studio/src/graph/GraphModel.ts` (lines 52–63)
- Priority: Medium

---

*Concerns audit: 2026-07-13*
