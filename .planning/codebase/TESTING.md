# Testing Patterns

**Analysis Date:** 2026-07-13

## Test Framework

**Runner:**
- None installed. No `jest`, `vitest`, `mocha`, or any other test runner appears in `package.json` dependencies or devDependencies.
- Config: No test config files present (`jest.config.*`, `vitest.config.*` — absent)

**Assertion Library:**
- None installed.

**Run Commands:**
```bash
# No test commands defined in package.json scripts.
# Current scripts are:
npm run dev          # Vite dev server
npm run build        # tsc + vite build
npm run preview      # Vite preview
npm run typecheck    # tsc --noEmit (type checking only)
```

## Test File Organization

**Location:**
- No test files exist in `src/`. Zero `.test.ts`, `.test.tsx`, `.spec.ts`, or `.spec.tsx` files.

**Naming:**
- Not applicable — no test files.

**Structure:**
- Not applicable.

## Current Quality Enforcement

The only automated quality gate currently in place is TypeScript type checking:

```bash
npm run typecheck    # Runs: tsc --noEmit
```

TypeScript is configured with `strict: true` in `rehab-robotics-studio/tsconfig.json`:
- `strict: true` — enables all strict type checks
- `noFallthroughCasesInSwitch: true` — enforces exhaustive switch handling
- `isolatedModules: true` — no implicit global type sharing

## Testability Analysis

### Highly Testable Units (Pure Functions)

These modules contain pure functions with no side effects and are ideal first candidates for unit tests:

**`src/graph/validation.ts` — `validateGraph(nodes, edges)`**
- Input: `BlockInstance[]`, `EdgeDefinition[]`
- Output: `ValidationIssue[]`
- Pure, no imports from React or stores
- Tests should cover: missing source block, missing target block, type mismatch, unsafe motor path, disconnected required inputs

**`src/graph/GraphModel.ts` — geometry and serialization helpers**
- `nodeHeight(def)`, `portY(index)`, `orthPath(p1, p2)`, `wireLabelPos(p1, p2)` — pure math
- `serializeGraph(nodes, edges)` → JSON string
- `deserializeGraph(json)` → `GraphDocument` or throws
- `topoSort(nodes, edges)` — pure topological sort, cycle-safe

**`src/graph/mockExecutor.ts` — `runMockExecutor(nodes, edges, frame, mem)`**
- Input: graph snapshot + data frame + mutable memory object
- Output: `ExecResult`
- Deterministic given fixed inputs (modulo `Math.random()` in some block cases)

**`src/graph/blockDefinitions.ts` — `getDef(type)`, `defaultParams(type)`**
- Simple registry lookups — trivial to test

### Harder to Test (Side-Effect-Heavy)

**Zustand stores** (`src/state/graphStore.ts`, `src/state/runtimeStore.ts`, `src/state/systemStore.ts`):
- Stores are singletons; require reset between tests
- `runtimeStore` has a direct import-time reference to `mockDataSource` (side effect)
- `signalBus` starts a `requestAnimationFrame` loop and subscribes to `mockDataSource` at import time

**`src/data/MockDataSource.ts`** — uses `setInterval`, `performance.now()`; requires timer mocking

**`src/data/signalBus.ts`** — uses `requestAnimationFrame` and couples to `useGraphStore` at runtime; difficult to isolate without a DOM environment

**React components** — would require `@testing-library/react` + jsdom

## Recommended Test Setup (When Adding Tests)

### Suggested Framework

```bash
npm install -D vitest @vitest/coverage-v8
# For component tests:
npm install -D @testing-library/react @testing-library/jest-dom jsdom
```

Add to `package.json` scripts:
```json
{
  "test": "vitest",
  "test:ui": "vitest --ui",
  "coverage": "vitest run --coverage"
}
```

Add `vitest.config.ts`:
```typescript
import { defineConfig } from 'vitest/config';
export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
});
```

### Recommended Test File Placement

Co-locate tests with source files:
```
src/
  graph/
    GraphModel.ts
    GraphModel.test.ts       # geometry + serialization
    validation.ts
    validation.test.ts       # graph validation rules
    mockExecutor.ts
    mockExecutor.test.ts     # per-block eval + full graph pass
  state/
    graphStore.test.ts       # store actions (reset store between tests)
```

### Example Test Patterns for This Codebase

**Pure function test (validation):**
```typescript
import { describe, it, expect } from 'vitest';
import { validateGraph } from '../graph/validation';
import type { BlockInstance, EdgeDefinition } from '../types/blocks';

describe('validateGraph', () => {
  it('returns no issues for a valid connected graph', () => {
    const nodes: BlockInstance[] = [
      { id: 'B1', type: 'fake_load_cell', name: 'Fake Load Cell', position: { x: 0, y: 0 }, params: {}, status: 'idle' },
      { id: 'B2', type: 'low_pass_filter', name: 'Low Pass Filter', position: { x: 200, y: 0 }, params: {}, status: 'idle' },
    ];
    const edges: EdgeDefinition[] = [
      { id: 'e1', sourceBlockId: 'B1', sourcePortId: 'force', targetBlockId: 'B2', targetPortId: 'in', signalType: 'force3d' },
    ];
    expect(validateGraph(nodes, edges)).toHaveLength(0);
  });

  it('emits ERROR for an edge referencing a missing source block', () => {
    const nodes: BlockInstance[] = [];
    const edges: EdgeDefinition[] = [
      { id: 'e1', sourceBlockId: 'MISSING', sourcePortId: 'out', targetBlockId: 'ALSO_MISSING', targetPortId: 'in', signalType: 'number' },
    ];
    const issues = validateGraph(nodes, edges);
    expect(issues.some((i) => i.level === 'ERROR')).toBe(true);
  });
});
```

**Serialization round-trip test:**
```typescript
import { describe, it, expect } from 'vitest';
import { serializeGraph, deserializeGraph } from '../graph/GraphModel';

describe('graph serialization', () => {
  it('round-trips a graph document', () => {
    const nodes = [/* ... */];
    const edges = [/* ... */];
    const json = serializeGraph(nodes, edges);
    const doc = deserializeGraph(json);
    expect(doc.nodes).toEqual(nodes);
    expect(doc.edges).toEqual(edges);
  });

  it('throws on invalid JSON structure', () => {
    expect(() => deserializeGraph('{"version":1}')).toThrow('Invalid graph document');
  });
});
```

**Zustand store test (requires store reset):**
```typescript
import { beforeEach, describe, it, expect } from 'vitest';
import { useGraphStore } from '../state/graphStore';

beforeEach(() => {
  useGraphStore.setState({ nodes: [], edges: [], selectedId: null, validationIssues: [] });
});

describe('graphStore.addNode', () => {
  it('adds a node and selects it', () => {
    useGraphStore.getState().addNode('fake_load_cell', 100, 100);
    const { nodes, selectedId } = useGraphStore.getState();
    expect(nodes).toHaveLength(1);
    expect(selectedId).toBe(nodes[0].id);
  });
});
```

## Mocking

**What to mock when tests are added:**
- `Math.random` — mock to a fixed value for deterministic executor tests
- `performance.now` — mock for `MockDataSource` timer tests
- `setInterval` / `clearInterval` — use Vitest fake timers: `vi.useFakeTimers()`
- `requestAnimationFrame` — polyfill or mock in jsdom setup for `SignalBus` tests

**What NOT to mock:**
- `validateGraph`, `topoSort`, `serializeGraph`, `deserializeGraph` — test these as real pure functions
- `blockDefinitions` registry — test against the real registry to catch registration errors

## Coverage

**Requirements:** None enforced (no test framework installed, no coverage thresholds configured).

**View Coverage (once vitest is installed):**
```bash
npm run coverage
```

## Test Types

**Unit Tests:**
- Priority targets: `src/graph/validation.ts`, `src/graph/GraphModel.ts`, `src/graph/mockExecutor.ts`
- All are pure or near-pure with no DOM dependencies

**Integration Tests:**
- Store action chains (e.g., `run()` → state transitions → log entries)
- `signalBus` + `mockDataSource` pipeline integration

**E2E Tests:**
- Not applicable — no E2E framework (Playwright, Cypress) installed or planned at current level

## Test Coverage Gaps

**All application logic is currently untested.** Priority ordering for first test additions:

**High:**
- `src/graph/validation.ts` — safety-critical logic (motor control path gating, type mismatch detection)
- `src/graph/GraphModel.ts` — `topoSort` cycle detection and `deserializeGraph` error path
- `src/state/runtimeStore.ts` — state machine transition guards (E-stop, fault, reset)

**Medium:**
- `src/graph/mockExecutor.ts` — per-block `evalBlock` cases (low_pass_filter EMA, safety_gate clamping)
- `src/state/graphStore.ts` — `addNode`, `removeNode`, `addEdge` (duplicate prevention), `finishWire`
- `src/graph/blockDefinitions.ts` — `defaultParams` coverage for every block type

**Low:**
- React components — visual rendering is low risk compared to logic layer
- `src/data/MockDataSource.ts` — timer-dependent, low business logic value

---

*Testing analysis: 2026-07-13*
