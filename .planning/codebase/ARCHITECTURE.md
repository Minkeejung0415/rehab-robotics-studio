<!-- refreshed: 2026-07-13 -->
# Architecture

**Analysis Date:** 2026-07-13

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                            App Shell (App.tsx)                               │
│  Toolbar (chrome)    BlockLibrary   GraphCanvas   PropertiesPanel  Dashboard │
│  `src/components/    `components/   `components/  `components/     `components/│
│   chrome/Toolbar`     library/`      canvas/`      properties/`     dashboard/`│
└──────────┬───────────────┬──────────────┬───────────────┬────────────────────┘
           │               │              │               │
           ▼               ▼              ▼               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          State Layer (Zustand stores)                        │
│   runtimeStore.ts        graphStore.ts          systemStore.ts               │
│   (state machine,        (nodes, edges,          (status indicators,         │
│    run/pause/estop)       selection, wiring)      logs)                      │
│                                                                              │
│                    actions.ts (cross-store operations)                       │
└──────────────────────────┬───────────────────────────────────────────────────┘
                           │
           ┌───────────────┼────────────────┐
           ▼               ▼                ▼
┌──────────────┐  ┌────────────────┐  ┌──────────────────────────────────────┐
│  Graph Layer │  │  Data Layer    │  │  Graph Layer (execution)             │
│  blockDefs   │  │  DataSource    │  │  mockExecutor.ts                     │
│  .ts         │  │  (interface)   │  │  (topological eval per frame)        │
│  GraphModel  │  │  MockData      │  │  GraphModel.ts                       │
│  .ts         │  │  Source.ts     │  │  (topo sort, geometry, serialize)    │
│  validation  │  │  (singleton)   │  │  validation.ts                       │
│  .ts         │  └───────┬────────┘  └────────────────┬─────────────────────┘
└──────────────┘          │                            │
                          ▼                            │
                 ┌────────────────────────────────────┘
                 │  signalBus.ts
                 │  (rate decoupler: data rate → ~30 fps RAF loop)
                 │  → useSignals() hook → React UI
                 └────────────────────────────────────────────────
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| App | Shell layout, panel composition | `src/App.tsx` |
| Toolbar | Run/pause/stop/estop controls, save/load/validate | `src/components/chrome/Toolbar.tsx` |
| StatusStrip | Hardware connection indicators (ROS, Jetson, Red Pitaya, Motor, Fault) | `src/components/chrome/StatusStrip.tsx` |
| BlockLibrary | Searchable block palette, add-to-canvas action | `src/components/library/BlockLibrary.tsx` |
| LibraryItem | Single palette entry with add button | `src/components/library/LibraryItem.tsx` |
| GraphCanvas | SVG wire layer + positioned BlockNode divs, drag + click-to-select | `src/components/canvas/GraphCanvas.tsx` |
| BlockNode | Draggable block node, ports, live NodeBody visualisation | `src/components/canvas/BlockNode.tsx` |
| Port | Single typed terminal dot on a node | `src/components/canvas/Port.tsx` |
| Wire | SVG orthogonal wire between two ports | `src/components/canvas/Wire.tsx` |
| PropertiesPanel | Inspector for selected block: params, ports, validation issues | `src/components/properties/PropertiesPanel.tsx` |
| ParamField | Single editable parameter (number/enum/bool/text) | `src/components/properties/ParamField.tsx` |
| Dashboard | Right-panel live data container | `src/components/dashboard/Dashboard.tsx` |
| ForcePanel | Force gauge + chart + tare button | `src/components/dashboard/ForcePanel.tsx` |
| EmgPanel | EMG envelope readout + scrolling chart | `src/components/dashboard/EmgPanel.tsx` |
| MotorPanel | Motor position/velocity/torque/current readouts | `src/components/dashboard/MotorPanel.tsx` |
| LogsPanel | Scrolling system log with level filtering | `src/components/dashboard/LogsPanel.tsx` |
| Gauge | Analog-style arc gauge widget | `src/components/common/Gauge.tsx` |
| MiniChart | Scrolling sparkline chart widget | `src/components/common/MiniChart.tsx` |
| StatusLight | Industrial indicator lamp (ok/warn/fault/idle) | `src/components/common/StatusLight.tsx` |
| graphStore | Zustand store: nodes, edges, selection, wire-dragging, serialize/load | `src/state/graphStore.ts` |
| runtimeStore | Zustand store: state machine (idle/running/paused/estopped/fault) | `src/state/runtimeStore.ts` |
| systemStore | Zustand store: status indicators + log entries (max 300) | `src/state/systemStore.ts` |
| actions | Cross-store operations: validateGraph, saveProject, loadProject, deployMock | `src/state/actions.ts` |
| DataSource | Interface contract for any acquisition source | `src/data/DataSource.ts` |
| MockDataSource | Synthetic frame generator, setInterval-based, 8–40 ms interval | `src/data/MockDataSource.ts` |
| signalBus | Rate decoupler: subscribes to DataSource, runs graph executor, publishes snapshots via rAF at ~30 fps | `src/data/signalBus.ts` |
| blockDefinitions | Registry of all block types (`BLOCK_DEFS`), `defaultParams()`, `CATEGORY_ORDER` | `src/graph/blockDefinitions.ts` |
| GraphModel | Canvas geometry constants, port position math, orthogonal wire routing, topo sort, serialize/deserialize | `src/graph/GraphModel.ts` |
| mockExecutor | Per-frame evaluation of the graph in topological order, returns `ExecResult` | `src/graph/mockExecutor.ts` |
| validation | Pure function `validateGraph()`: type mismatches, missing ports, unsafe motor paths | `src/graph/validation.ts` |
| useSignals | `useSyncExternalStore` hook bridging signalBus to React | `src/hooks/useSignals.ts` |
| tokens | Design token maps: colors, categoryColor, signalColor, statusColor, levelColor | `src/theme/tokens.ts` |

## Pattern Overview

**Overall:** LabVIEW-style visual dataflow programming environment — a node-and-wire graph editor backed by a real dataflow executor.

**Key Characteristics:**
- Graph is the primary abstraction: nodes (`BlockInstance`) connected by typed edges (`EdgeDefinition`)
- Data flows in two separate loops: a fast data loop (MockDataSource → signalBus ingest) and a slow render loop (rAF at ~30 fps → React)
- State is split across three Zustand stores by concern domain (graph structure, runtime lifecycle, system status)
- Block types are defined declaratively in a static registry (`BLOCK_DEFS`); adding a new block type requires only a registry entry and an executor `case`
- All hardware integrations are behind an interface (`DataSource`); mock implementations are drop-in replaceable

## Layers

**UI Layer:**
- Purpose: React components that render and capture user interaction
- Location: `src/components/`
- Contains: Canvas, palette, dashboard panels, chrome (toolbar, status strip), common widgets
- Depends on: State layer (Zustand stores), hooks, theme tokens
- Used by: `src/App.tsx` root

**State Layer:**
- Purpose: Zustand stores holding all mutable application state; single source of truth
- Location: `src/state/`
- Contains: `graphStore.ts`, `runtimeStore.ts`, `systemStore.ts`, `actions.ts`
- Depends on: Graph layer (for validation/serialization), Data layer (runtimeStore drives mockDataSource)
- Used by: UI components, signalBus (reads graphStore per frame)

**Graph Layer:**
- Purpose: Block registry, graph topology utilities, static validator, frame executor
- Location: `src/graph/`
- Contains: `blockDefinitions.ts`, `GraphModel.ts`, `mockExecutor.ts`, `validation.ts`
- Depends on: Types layer
- Used by: State layer (graphStore, runtimeStore), signalBus

**Data Layer:**
- Purpose: Hardware abstraction — produces `Frame` objects at the acquisition rate
- Location: `src/data/`
- Contains: `DataSource.ts` (interface), `MockDataSource.ts` (singleton impl), `signalBus.ts` (rate bridge)
- Depends on: Graph layer (mockExecutor), State layer (graphStore read-only)
- Used by: runtimeStore (lifecycle control), useSignals hook (React subscription)

**Types Layer:**
- Purpose: Shared TypeScript contracts with no runtime dependencies
- Location: `src/types/`
- Contains: `blocks.ts`, `signals.ts`, `system.ts`, `index.ts` (re-export barrel)
- Depends on: nothing
- Used by: all other layers

**Theme Layer:**
- Purpose: Design token maps used by components for consistent styling
- Location: `src/theme/tokens.ts`
- Contains: color constants, per-category and per-signal-type color maps
- Depends on: Types (SignalType, Category, etc.)
- Used by: UI components

## Data Flow

### Primary Signal Path (data rate)

1. `mockDataSource.tick()` fires every 8–40 ms, generates a `Frame` (`src/data/MockDataSource.ts`)
2. `signalBus.ingest(frame)` receives the frame — reads current graph from `useGraphStore.getState()` (`src/data/signalBus.ts:99`)
3. `runMockExecutor(nodes, edges, frame, mem)` topologically sorts the graph and evaluates each block, producing scalar port values (`src/graph/mockExecutor.ts:105`)
4. `signalBus` updates ring buffers (240 samples each for force, EMG, knee) and `this.latest` snapshot
5. `signalBus.loop` (rAF) checks `dirty` flag; if >33 ms since last notify, publishes `this.snapshot` and calls all React listeners

### React Render Path (~30 fps)

1. `useSignals()` hook uses `useSyncExternalStore` subscribed to `signalBus` (`src/hooks/useSignals.ts`)
2. Dashboard panels (`ForcePanel`, `EmgPanel`, `MotorPanel`) and `BlockNode.NodeBody` re-render with new `SignalSnapshot`
3. `Gauge`, `MiniChart`, `StatusLight` render the values

### User Graph Editing Path

1. User clicks `+` in `BlockLibrary` → `graphStore.addNode(type, x, y)` (`src/components/library/BlockLibrary.tsx:13`)
2. User drags a `Port` to start a wire → `graphStore.startWire()`, then drops on a target port → `graphStore.finishWire()` (`src/state/graphStore.ts:153`)
3. `graphStore.validate()` runs `validateGraph(nodes, edges)` (pure function, returns `ValidationIssue[]`) (`src/graph/validation.ts`)
4. On next `signalBus.ingest()`, the updated graph is picked up automatically since `signalBus` reads `useGraphStore.getState()` live

### Runtime State Machine

```
idle → running → paused → running
                        ↘ idle
     → running → estopped → idle (reset only)
     → running → fault    → idle (reset only)
     any       → estopped | fault
```
- Implemented in `src/state/runtimeStore.ts` with explicit `TRANSITIONS` table
- `run()` calls `mockDataSource.start(sampleRate)` — wires runtime control to the data layer
- `estop()` calls `mockDataSource.stop()` and flags the motor indicator as 'fault'

**State Management:**
- Three Zustand stores: `graphStore` (graph structure), `runtimeStore` (lifecycle), `systemStore` (indicators + logs)
- Components subscribe with selector functions: `useGraphStore((s) => s.nodes)` — fine-grained, avoids full re-renders
- Cross-store operations live in `src/state/actions.ts` to keep stores focused
- `signalBus` reads graphStore via `useGraphStore.getState()` (non-reactive read inside the data loop — intentional)

## Key Abstractions

**BlockDefinition:**
- Purpose: Declarative description of a block type (ports, params, category, runtime safety)
- Examples: `src/graph/blockDefinitions.ts` — `BLOCK_DEFS['low_pass_filter']`, `BLOCK_DEFS['fake_load_cell']`
- Pattern: Static registry object keyed by block type string; `BlockInstance` is the per-canvas-placement runtime

**DataSource Interface:**
- Purpose: Swappable hardware abstraction — any source implementing `start/stop/pause/resume/subscribe` can replace the mock
- Examples: `src/data/DataSource.ts` (interface), `src/data/MockDataSource.ts` (impl)
- Pattern: Interface + singleton export; `signalBus` subscribes at construction time; `runtimeStore` calls lifecycle methods

**SignalBus:**
- Purpose: Decouples high-frequency data acquisition from React's render cycle
- Examples: `src/data/signalBus.ts`
- Pattern: Singleton class; ingest runs at data rate; RAF loop throttles React notifications to ~30 fps; `useSyncExternalStore` compatible

**SignalSnapshot:**
- Purpose: Immutable point-in-time data bundle React reads each render; includes both scalar values and ring-buffer series arrays
- Examples: `src/data/signalBus.ts:24`
- Pattern: Plain object replaced atomically each RAF tick; old reference held by components between ticks

**GraphDocument:**
- Purpose: Serializable graph format (`{ version, nodes, edges }`) for save/load
- Examples: `src/types/blocks.ts:93`, `src/graph/GraphModel.ts:52`
- Pattern: JSON serialized by `serializeGraph()`, deserialized by `deserializeGraph()` with version check

## Entry Points

**Browser Entry:**
- Location: `src/main.tsx`
- Triggers: Vite serves `index.html` which loads `src/main.tsx`
- Responsibilities: Creates React root, renders `<App />` inside `StrictMode`, imports global CSS

**App Shell:**
- Location: `src/App.tsx`
- Triggers: Rendered by `main.tsx`
- Responsibilities: Composes the 5-panel layout (Toolbar, BlockLibrary, GraphCanvas, PropertiesPanel, Dashboard, StatusStrip)

**SignalBus Constructor:**
- Location: `src/data/signalBus.ts:87`
- Triggers: Module import (singleton instantiated at module load time)
- Responsibilities: Subscribes to `mockDataSource`, starts the rAF loop — data pipeline is live before any user interaction

## Architectural Constraints

- **Threading:** Single-threaded browser event loop. The data acquisition loop runs via `setInterval`; render loop via `requestAnimationFrame`. No Web Workers.
- **Global state:** Three module-level Zustand store singletons (`useGraphStore`, `useRuntimeStore`, `useSystemStore`). `mockDataSource` and `signalBus` are also module-level singletons (`src/data/MockDataSource.ts:118`, `src/data/signalBus.ts:151`).
- **signalBus reads graphStore imperatively:** `signalBus.ingest()` calls `useGraphStore.getState()` on every frame — this is a deliberate non-reactive read inside the hot path to avoid subscription overhead.
- **Circular import risk:** `signalBus` imports `graphStore` (state) and `mockExecutor` (graph). `runtimeStore` imports `mockDataSource` (data) and `systemStore` (state). These are intentional but must not form a cycle through `graphStore` importing `signalBus`.
- **ExecMemory is mutable in the hot path:** `signalBus` holds `this.mem: ExecMemory` across frames; `mockExecutor` mutates it for filter state. Do not reset this between frames unless intentional (e.g., graph reload).
- **Canvas size is fixed:** `GraphCanvas` hardcodes `CANVAS_WIDTH = 980`, `CANVAS_HEIGHT = 720` (`src/components/canvas/GraphCanvas.tsx:7-8`). Node positions are clamped to these bounds.

## Anti-Patterns

### Bypassing Zustand Actions for Cross-Store Operations

**What happens:** Calling `useSystemStore.getState().addLog()` directly inside `graphStore` mutations rather than using `actions.ts`
**Why it's wrong:** `actions.ts` exists specifically to coordinate cross-store operations; bypassing it scatters cross-cutting logic and makes the log contract implicit
**Do this instead:** Route all operations that span more than one store through `src/state/actions.ts`

### Adding Block Types Without Executor Cases

**What happens:** Adding an entry to `BLOCK_DEFS` in `src/graph/blockDefinitions.ts` without adding a matching `case` in `evalBlock()` in `src/graph/mockExecutor.ts`
**Why it's wrong:** The `default` branch of `evalBlock()` returns `{}` (empty outputs) — the block silently produces nothing and downstream blocks receive 0
**Do this instead:** Always add a `case node.type:` in `src/graph/mockExecutor.ts:43` alongside any new registry entry

### Reading signalBus Snapshot Outside useSignals

**What happens:** Calling `signalBus.getSnapshot()` directly in a component instead of `useSignals()`
**Why it's wrong:** Direct calls bypass `useSyncExternalStore` and will not trigger re-renders when the snapshot updates; the component will display a stale snapshot
**Do this instead:** Always use `useSignals()` from `src/hooks/useSignals.ts` in React components

## Error Handling

**Strategy:** Errors surface through the system log (`systemStore.addLog`) rather than exceptions or UI toasts.

**Patterns:**
- `actions.loadProject()` wraps `graphStore.load()` in try/catch and logs `ERROR` on failure (`src/state/actions.ts:44`)
- `runtimeStore` transitions that violate the state machine log `WARN` and return early without throwing (`src/state/runtimeStore.ts:57`)
- `validateGraph()` is a pure function returning `ValidationIssue[]` — callers decide how to surface issues
- Safety violations are logged at `SAFETY` level (separate from `ERROR`) — used for E-Stop and unsafe motor paths

## Cross-Cutting Concerns

**Logging:** `useSystemStore.getState().addLog(level, message)` — levels: `INFO | WARN | ERROR | SAFETY`. Log capped at 300 entries (`src/state/systemStore.ts:43`). Timestamp format: `HH:MM:SS.mmm`.
**Validation:** Pure function in `src/graph/validation.ts`. Called on demand (Toolbar "Validate Graph" button) and on load. Results stored in `graphStore.validationIssues`.
**Authentication:** Not applicable — local browser app, no auth layer.
**Theming:** All colors centralized in `src/theme/tokens.ts`. Components import named token maps (`categoryColor`, `signalColor`, `statusColor`, `levelColor`) rather than hardcoding hex values.

---

*Architecture analysis: 2026-07-13*
