# Codebase Structure

**Analysis Date:** 2026-07-13

## Directory Layout

```
rehab-robotics-studio/
├── src/
│   ├── main.tsx                    # Browser entry point — React root mount
│   ├── App.tsx                     # Shell layout — 5-panel composition
│   ├── vite-env.d.ts               # Vite ambient types
│   │
│   ├── types/                      # Shared TypeScript contracts (no runtime deps)
│   │   ├── index.ts                # Re-export barrel
│   │   ├── blocks.ts               # BlockDefinition, BlockInstance, EdgeDefinition, GraphDocument
│   │   ├── signals.ts              # Frame, ForceData, EmgData, ImuData, MotorState, SignalType
│   │   └── system.ts               # RuntimeState, LogEntry, SystemStatus, IndicatorLevel
│   │
│   ├── theme/
│   │   └── tokens.ts               # Color constants, categoryColor, signalColor, statusColor maps
│   │
│   ├── styles/
│   │   └── app.css                 # Global CSS — dark lab palette, layout grid, component styles
│   │
│   ├── state/                      # Zustand stores — all mutable application state
│   │   ├── graphStore.ts           # Graph structure: nodes, edges, selection, wire ops, serialize
│   │   ├── runtimeStore.ts         # State machine: idle/running/paused/estopped/fault
│   │   ├── systemStore.ts          # Status indicators + log entries
│   │   └── actions.ts              # Cross-store operations: validate, save, load, deploy
│   │
│   ├── graph/                      # Graph domain logic — no React, no Zustand
│   │   ├── blockDefinitions.ts     # BLOCK_DEFS registry, defaultParams(), CATEGORY_ORDER
│   │   ├── GraphModel.ts           # Geometry constants, port math, topo sort, serialize/deserialize
│   │   ├── mockExecutor.ts         # Per-frame topological evaluation of the graph
│   │   └── validation.ts           # Pure validateGraph() function
│   │
│   ├── data/                       # Hardware abstraction and signal pipeline
│   │   ├── DataSource.ts           # Interface: start/stop/pause/resume/subscribe
│   │   ├── MockDataSource.ts       # Synthetic frame generator singleton (mockDataSource)
│   │   └── signalBus.ts            # Rate decoupler: data-rate ingest → ~30 fps React notifications
│   │
│   ├── hooks/
│   │   └── useSignals.ts           # useSyncExternalStore wrapper for signalBus
│   │
│   └── components/
│       ├── canvas/                 # Graph editor canvas
│       │   ├── GraphCanvas.tsx     # SVG wire layer + positioned block divs, canvas container
│       │   ├── BlockNode.tsx       # Draggable block node with ports and live body visualisation
│       │   ├── Port.tsx            # Typed terminal dot
│       │   └── Wire.tsx            # SVG orthogonal wire + geometry constants (NODE_WIDTH, etc.)
│       │
│       ├── chrome/                 # Application frame UI
│       │   ├── Toolbar.tsx         # Run/pause/stop/estop controls, save/load/validate buttons
│       │   └── StatusStrip.tsx     # Bottom hardware status indicators bar
│       │
│       ├── common/                 # Reusable display widgets
│       │   ├── Gauge.tsx           # Analog arc gauge
│       │   ├── MiniChart.tsx       # Scrolling sparkline (canvas or SVG)
│       │   └── StatusLight.tsx     # Industrial indicator lamp
│       │
│       ├── dashboard/              # Right-panel live data panels
│       │   ├── Dashboard.tsx       # Container: composes 4 panels
│       │   ├── ForcePanel.tsx      # Force gauge + chart + tare
│       │   ├── EmgPanel.tsx        # EMG envelope + chart
│       │   ├── MotorPanel.tsx      # Motor state readouts
│       │   └── LogsPanel.tsx       # Scrolling system log
│       │
│       ├── library/                # Block palette
│       │   ├── BlockLibrary.tsx    # Searchable palette grouped by category
│       │   └── LibraryItem.tsx     # Single palette entry with add button
│       │
│       └── properties/             # Block inspector
│           ├── PropertiesPanel.tsx # Inspector: params, ports, validation issues for selected block
│           └── ParamField.tsx      # Single editable param (number/enum/bool/text input)
│
├── index.html                      # Vite HTML entry — mounts #root
├── package.json                    # Dependencies: react 18, react-dom, zustand; dev: vite, typescript
├── package-lock.json
├── tsconfig.json                   # TypeScript config (browser target)
├── tsconfig.node.json              # TypeScript config (vite.config.ts)
├── vite.config.ts                  # Vite build config with @vitejs/plugin-react
├── dist/                           # Built output (committed snapshot)
│   ├── index.html
│   └── assets/
│       ├── index-BkgxtW75.js
│       └── index-C5aWE0wL.css
│
.planning/
└── codebase/                       # GSD codebase map documents
```

## Directory Purposes

**`src/types/`:**
- Purpose: Pure TypeScript type definitions — the shared contract between all layers
- Contains: Interfaces and type aliases for blocks, signals, and system state
- Key files: `blocks.ts` (graph schema), `signals.ts` (wire payload types), `system.ts` (runtime/log types)
- Note: Always import from `../types` (barrel) or a specific sub-file; never from another layer

**`src/state/`:**
- Purpose: All mutable application state, managed by Zustand
- Contains: Three store files and one actions coordinator
- Key files: `graphStore.ts` (primary graph state), `runtimeStore.ts` (state machine), `actions.ts` (cross-store)

**`src/graph/`:**
- Purpose: Graph domain logic — pure functions and data structures with no UI or state dependencies
- Contains: Block registry, geometry math, topological sort, frame executor, static validator
- Key files: `blockDefinitions.ts` (add new block types here), `mockExecutor.ts` (add execution behavior here)

**`src/data/`:**
- Purpose: Hardware abstraction layer — isolates data production from all consumers
- Contains: The `DataSource` interface contract, mock implementation, and the React-bridging signal bus
- Key files: `DataSource.ts` (swap point for real hardware), `signalBus.ts` (rate throttle, single subscriber)

**`src/components/canvas/`:**
- Purpose: The visual graph editor — nodes, wires, port connection UI
- Key files: `GraphCanvas.tsx` (root of canvas), `Wire.tsx` (geometry constants exported for use by BlockNode and Port)

**`src/components/chrome/`:**
- Purpose: Application-level UI frame (toolbar, status bar) — not graph-domain-specific

**`src/components/common/`:**
- Purpose: Reusable display primitives shared between canvas nodes and dashboard panels
- Note: `Gauge` and `MiniChart` are used both inside `BlockNode.NodeBody` and in `Dashboard` panels

**`src/components/dashboard/`:**
- Purpose: Live data monitoring panels on the right side of the UI

**`src/components/library/`:**
- Purpose: Palette for discovering and adding block types to the canvas

**`src/components/properties/`:**
- Purpose: Inspector for a selected block — edits `graphStore` params live

**`src/theme/`:**
- Purpose: All visual design tokens; single source of truth for colors
- Key file: `tokens.ts` — import named maps (`categoryColor`, `signalColor`) rather than raw hex strings

**`src/styles/`:**
- Purpose: Global CSS for layout, component classes, dark lab palette

## Key File Locations

**Entry Points:**
- `src/main.tsx`: Browser entry, React root mount
- `src/App.tsx`: Shell layout with panel composition
- `rehab-robotics-studio/index.html`: HTML shell

**Block Registry:**
- `src/graph/blockDefinitions.ts`: Add new block types here; every entry needs a `BLOCK_DEFS` object and `CATEGORY_ORDER` placement

**Executor:**
- `src/graph/mockExecutor.ts`: Add `case 'new_block_type':` here to implement block behavior

**Hardware Swap Point:**
- `src/data/DataSource.ts`: Interface to implement for real hardware
- `src/data/signalBus.ts`: Line 88 — `mockDataSource.subscribe(...)` is where a real source is wired in

**Stores:**
- `src/state/graphStore.ts`: Graph nodes/edges/selection
- `src/state/runtimeStore.ts`: Run/pause/estop lifecycle
- `src/state/systemStore.ts`: Status indicators and system log

**Shared Types:**
- `src/types/blocks.ts`: Block and graph schema
- `src/types/signals.ts`: Signal payload types and `Frame`
- `src/types/system.ts`: Runtime state machine types and log types

**Styles and Tokens:**
- `src/theme/tokens.ts`: Color maps by category, signal type, status
- `src/styles/app.css`: All CSS rules

## Naming Conventions

**Files:**
- Components: PascalCase matching the exported component name — `BlockNode.tsx`, `ForcePanel.tsx`
- Non-component modules: camelCase — `graphStore.ts`, `signalBus.ts`, `blockDefinitions.ts`
- Type files: camelCase — `blocks.ts`, `signals.ts`, `system.ts`

**Directories:**
- Feature groupings use lowercase: `canvas/`, `chrome/`, `dashboard/`, `library/`, `properties/`, `common/`
- Domain modules use lowercase: `state/`, `graph/`, `data/`, `hooks/`, `theme/`, `types/`, `styles/`

**Exports:**
- One named export per component file matching the filename: `export function BlockNode(...)` in `BlockNode.tsx`
- Store hooks: `useGraphStore`, `useRuntimeStore`, `useSystemStore`
- Singletons: `mockDataSource` (from `MockDataSource.ts`), `signalBus` (from `signalBus.ts`)
- Block registry: `BLOCK_DEFS` (all caps, Record), `CATEGORY_ORDER` (all caps, array)

**Types:**
- Interfaces: PascalCase — `BlockDefinition`, `BlockInstance`, `PortDefinition`
- Type aliases: PascalCase — `SignalType`, `RuntimeState`, `BlockStatus`, `Category`
- Zustand store interfaces: PascalCase matching store — `GraphStore`, `RuntimeStore`, `SystemStore`

## Where to Add New Code

**New Block Type:**
1. Add `BlockDefinition` entry to `BLOCK_DEFS` in `src/graph/blockDefinitions.ts`
2. Add to `CATEGORY_ORDER` in `src/graph/blockDefinitions.ts` (or use an existing category)
3. Add `case 'new_type':` in `evalBlock()` in `src/graph/mockExecutor.ts`
4. If the block has a live visualisation, add `bodyKind` to the definition and handle in `BlockNode.NodeBody` in `src/components/canvas/BlockNode.tsx`

**New Signal Type:**
1. Add to the `SignalType` union in `src/types/signals.ts`
2. Add color entry to `signalColor` in `src/theme/tokens.ts`
3. Add data interface if needed in `src/types/signals.ts`
4. Add to `Frame` if the source emits it in `src/types/signals.ts`

**New Dashboard Panel:**
1. Create `src/components/dashboard/NewPanel.tsx`
2. Import and render in `src/components/dashboard/Dashboard.tsx`
3. Read data via `useSignals()` from `src/hooks/useSignals.ts`

**New Reusable Widget:**
- Implementation: `src/components/common/NewWidget.tsx`

**New Cross-Store Action:**
- Add to `actions` object in `src/state/actions.ts`

**New Store (if needed):**
- Add `src/state/newStore.ts` following the Zustand pattern in existing stores

**Real Hardware Data Source:**
1. Implement `DataSource` interface from `src/data/DataSource.ts`
2. Replace the `mockDataSource.subscribe(...)` call in `src/data/signalBus.ts:88`
3. Wire lifecycle calls in `src/state/runtimeStore.ts` (currently calls `mockDataSource.start/pause/resume/stop`)

## Special Directories

**`dist/`:**
- Purpose: Vite production build output — committed snapshot of the built app
- Generated: Yes (via `npm run build`)
- Committed: Yes (this repo has a committed dist snapshot)

**`.planning/codebase/`:**
- Purpose: GSD codebase map documents (this file and ARCHITECTURE.md)
- Generated: Yes (by GSD map-codebase command)
- Committed: Yes

**`node_modules/`:**
- Purpose: NPM dependencies
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-07-13*
