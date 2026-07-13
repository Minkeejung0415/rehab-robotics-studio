# Coding Conventions

**Analysis Date:** 2026-07-13

## Naming Patterns

**Files:**
- React components: PascalCase `.tsx` (e.g., `BlockNode.tsx`, `PropertiesPanel.tsx`, `ForcePanel.tsx`)
- Non-component TypeScript modules: camelCase `.ts` (e.g., `graphStore.ts`, `signalBus.ts`, `blockDefinitions.ts`)
- Type-only files: camelCase `.ts` in `src/types/` (e.g., `blocks.ts`, `signals.ts`, `system.ts`)
- Hook files: camelCase with `use` prefix `.ts` (e.g., `useSignals.ts`)
- Data/class files: PascalCase `.ts` when containing a class (e.g., `MockDataSource.ts`, `DataSource.ts`)

**Functions and Variables:**
- Exported functions: PascalCase for React components (`BlockNode`, `GraphCanvas`, `PropertiesPanel`)
- Exported functions: camelCase for non-component utilities (`getDef`, `defaultParams`, `topoSort`, `validateGraph`)
- Local helpers: camelCase (`makeNode`, `edge`, `can`, `timestamp`)
- Constants: SCREAMING_SNAKE_CASE for module-level statics (`BLOCK_DEFS`, `DEFAULT_NODES`, `NODE_WIDTH`, `TRANSITIONS`, `CATEGORY_ORDER`)
- Private class members: camelCase with no prefix (uses TypeScript `private` keyword)

**Types and Interfaces:**
- Interfaces: PascalCase (`BlockInstance`, `EdgeDefinition`, `GraphStore`, `SignalSnapshot`)
- Type aliases: PascalCase (`RuntimeState`, `SignalType`, `LogLevel`, `Category`, `ParamValue`)
- Local inline `interface Props {}` pattern for React component props — always named `Props`, declared in the same file as the component

**Block type identifiers:**
- snake_case strings (e.g., `'fake_load_cell'`, `'emg_envelope'`, `'joint_angle_display'`)
- These are domain constants, not TypeScript identifiers

## Code Style

**Formatting:**
- No Prettier or ESLint config files present — formatting is by convention only
- Consistent 2-space indentation throughout all `.ts` and `.tsx` files
- Single quotes for imports; double quotes in JSX string attributes
- Trailing commas in multi-line arrays and objects
- Semicolons always present

**TypeScript:**
- `strict: true` in `tsconfig.json`
- `noFallthroughCasesInSwitch: true` enforced
- `isolatedModules: true` (Vite requirement)
- `import type` used consistently for type-only imports: `import type { BlockInstance } from '../types/blocks'`
- Non-null assertion `!` used sparingly, only where value is logically guaranteed (e.g., `queue.shift()!`, `byId.get(id)!`)
- Nullish coalescing `??` preferred over `||` for defaults when 0/false are valid values

**JSX:**
- `react-jsx` transform — no `import React` needed in component files
- Self-closing tags used when no children: `<span />`
- Inline styles via `style={{ ... }}` object literals for dynamic theming (color, position)
- `className` string concatenation using template literals: `className={\`block-node${selected ? ' is-selected' : ''}\`}`
- `key` prop always set to a stable, meaningful id (port id, block id, edge id, param key) — not index

## Import Organization

**Order (observed pattern):**
1. React / external packages (`react`, `zustand`)
2. Internal types (`import type { ... } from '../types/...'`)
3. Internal state/stores (`../../state/graphStore`)
4. Internal graph logic (`../../graph/blockDefinitions`)
5. Internal theme/tokens (`../../theme/tokens`)
6. Sibling/child components

**Path Aliases:**
- None configured. All imports use relative paths (`../../`, `../`, `./`)
- Paths from `src/components/canvas/` to state use `../../state/`

## Error Handling

**Patterns:**
- `try/catch` used only at effect boundaries where failure is expected and recoverable. Examples:
  - `src/state/actions.ts`: `saveProject()` wraps `URL.createObjectURL` in try/catch with empty catch body (SSR guard)
  - `src/state/actions.ts`: `loadProject()` catches deserialisation errors and logs via `sys.addLog('ERROR', ...)`
  - `src/graph/GraphModel.ts`: `deserializeGraph()` throws `new Error('Invalid graph document')` on malformed JSON
- Guard clauses are preferred over nested if-else: `if (!pendingWire) return;`
- Zustand store actions return early with a guard instead of throwing: `if (!can(state, 'running')) { log(...); return; }`
- No unhandled promise rejections — async patterns are not used (the data flow is synchronous/callback-based)

## Logging

**Pattern:**
- All structured log output routes through `useSystemStore.getState().addLog(level, message)`
- Log levels: `'INFO' | 'WARN' | 'ERROR' | 'SAFETY'` (defined in `src/types/system.ts`)
- `runtimeStore.ts` holds a local `log` shorthand: `const log = (level, msg) => useSystemStore.getState().addLog(level, msg)`
- `SAFETY` level is reserved for E-stop and fault events only
- No `console.log` calls in source files

## Comments

**When to Comment:**
- JSDoc block comments (`/** ... */`) on all exported interfaces, types, and non-obvious functions
- Inline section separator comments used in long files: `/* ----- canvas geometry ----- */`
- Design-intent comments explaining WHY decisions were made, especially around the data pipeline
- Future-work notes expressed as prose in comments (e.g., `// ROS bridge swap point`) — no TODO/FIXME markers

**Example (from `src/data/signalBus.ts`):**
```typescript
/**
 * The SignalBus is the seam between the (fast) data source and (slow) React UI.
 *
 *  - `ingest(frame)` runs at the DATA rate: it executes the graph, fills ring
 *    buffers, and updates `latest`. It does NOT touch React.
 *  - a requestAnimationFrame loop publishes a fresh `snapshot` and notifies
 *    React listeners at most ~30 fps.
 */
```

## Function Design

**Size:** Functions are kept short. `evalBlock` in `src/graph/mockExecutor.ts` is the largest (100 lines) due to its switch-case dispatch.

**Parameters:**
- Props objects destructured at component definition: `export function BlockNode({ node, selected, onSelect, onMove }: Props)`
- Store action functions accept flat primitives, not objects: `updateParam(nodeId: string, key: string, value: ParamValue)`
- Builder helpers in `blockDefinitions.ts` use short parameter names for compactness (`out`, `inp`, `num`, `enumP`)

**Return Values:**
- Hooks return typed values directly: `useSignals(): SignalSnapshot`
- Pure functions return computed values (no side effects): `validateGraph`, `topoSort`, `serializeGraph`, `portY`, `nodeHeight`
- Mutating operations return `void` (Zustand `set` callbacks)

## Module Design

**Exports:**
- Each module has one or more named exports — no default exports except `App` in `src/App.tsx`
- Stores exported as named constants: `export const useGraphStore = create<...>(...)`
- Singleton instances exported as named constants: `export const mockDataSource = new MockDataSource()`, `export const signalBus = new SignalBus()`

**Barrel Files:**
- `src/types/index.ts` re-exports from `signals`, `blocks`, and `system` — one barrel file
- All other modules import from their direct source path, not via barrel

**Theme / Token Centralisation:**
- All colors, fonts, and semantic color mappings live exclusively in `src/theme/tokens.ts`
- Components never hard-code color hex values except inside `src/components/chrome/Toolbar.tsx` (local `STATE_COLOR` map)

---

*Convention analysis: 2026-07-13*
