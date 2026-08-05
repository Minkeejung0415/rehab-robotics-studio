---
phase: 24-rosbridge-and-studio-mapping-workspace
plan: "01"
subsystem: studio-state
tags: [zustand, tdd, mapping, state-management]
dependency_graph:
  requires: []
  provides:
    - useMappingStore
    - MappingRow
    - MappingStore
    - computeMappingStatus
    - ModelCatalogSnapshot
    - MappingCurrentSnapshot
    - FleetRegistrySnapshot
    - NCalibrationStatusSnapshot
    - InputValiditySnapshot
  affects:
    - rehab-robotics-studio/src/state/mappingStore.ts
tech_stack:
  added:
    - zustand 4.5.7 (existing dep, new store file)
    - node:test mock.timers (fake timer testing)
  patterns:
    - zustand create<T>() with typed interface
    - computeMappingStatus pure exported helper
    - globalThis.setTimeout for mockable auto-clear
key_files:
  created:
    - rehab-robotics-studio/src/state/mappingStore.ts
    - rehab-robotics-studio/src/state/mappingStore.test.ts
  modified: []
decisions:
  - "Used node:test runner (tsx --test) instead of vitest — vitest not installed in project; node:test mock.timers provides equivalent fake timer API"
  - "setIdentifyResult uses globalThis.setTimeout (not window.setTimeout) to work in both browser and Node.js test environments"
  - "computeMappingStatus checks draft before backend state — draft always wins per D-07 intent"
metrics:
  duration: "~8 minutes"
  completed: "2026-08-05T22:09:36Z"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
---

# Phase 24 Plan 01: mappingStore — Zustand State for Mapping Workspace Summary

**One-liner:** Zustand mapping store with typed MappingRow/MappingStore interfaces, computeMappingStatus D-07 priority logic, D-05/D-06 row upsert rules, and 5-second identify auto-clear — all covered by 20 node:test unit tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Write failing vitest unit tests | 9ce8857 | `mappingStore.test.ts` |
| 2 (GREEN) | Implement mappingStore.ts | cfdd653 | `mappingStore.ts` |

## TDD Gate Compliance

- RED gate: `test(24-01)` commit `9ce8857` — 20 test cases, all failing with `ERR_MODULE_NOT_FOUND`
- GREEN gate: `feat(24-01)` commit `cfdd653` — all 20 tests pass, TypeScript clean

## What Was Built

### mappingStore.ts

Zustand store implementing all Mapping Workspace client-side state:

**Exported types:**
- `ModelCatalogSnapshot`, `MappingCurrentSnapshot`, `FleetRegistrySnapshot`, `NCalibrationStatusSnapshot`, `InputValiditySnapshot` — topic payload shapes
- `MappingRow` — per-device row with backend/draft/computed fields per D-04
- `MappingStore` — store interface with all actions including `calibrationInterlocked` and `updateFromCalibrationStatus`
- `computeMappingStatus` — pure exported function, D-07 priority order: runtime_ready > applied > saved > draft > unassigned

**Actions:**
- `updateFromFleetRegistry` — upserts rows by `device_id`, never deletes (D-05), guards with `isRecord` (T-24-01)
- `updateFromMappingCurrent` — guards revision fields as numbers (T-24-02); updates backend segment/frame/state; never touches draft fields (D-06)
- `updateFromCatalog` — sets `catalogModelHash`, `catalogModelPath`, `catalogFrameList`
- `updateInputValidity` — sets `ikValid` per device from `device_validities` dict
- `updateFromCalibrationStatus` — sets `calibrationInterlocked=true` when state='capturing'
- `setDraftSegment` / `setDraftNotUsed` / `clearDraft` / `clearAllDrafts` — draft lifecycle
- `setIdentifyResult` — sets result + schedules auto-clear via `globalThis.setTimeout(5000)` (D-18)
- `setApplyStatus` — sets `applyStatus` and optional `applyError`

### mappingStore.test.ts

20 node:test unit tests covering:
- Row creation and upsert from fleet registry (D-05 persistence)
- Draft preservation through `updateFromMappingCurrent` (D-06)
- All five `computeMappingStatus` states (D-07)
- Draft set/clear lifecycle
- Calibration interlock flag
- Identify auto-clear via `mock.timers.enable()` / `mock.timers.tick(5001)`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test runner: node:test instead of vitest**
- **Found during:** Task 1 setup
- **Issue:** Plan specified `npx vitest run` but vitest is not installed in the project. All existing tests use `node:test` + `node:assert/strict` via `tsx --test`.
- **Fix:** Used `node:test` APIs (`describe`, `it`, `mock.timers`) throughout. Verification command changed to `node_modules/.bin/tsx --test src/state/mappingStore.test.ts`. All semantics are equivalent.
- **Files modified:** `mappingStore.test.ts` (uses `node:test` imports)
- **Commit:** 9ce8857

**2. [Rule 2 - Missing functionality] globalThis.setTimeout instead of window.setTimeout**
- **Found during:** Task 2
- **Issue:** Plan specified `window.setTimeout` for the auto-clear timer. `window` is undefined in Node.js test context.
- **Fix:** Used `globalThis.setTimeout` which resolves to `window.setTimeout` in browser context and to Node's global `setTimeout` in test context. `mock.timers.enable({ apis: ['setTimeout'] })` intercepts `globalThis.setTimeout` correctly.
- **Files modified:** `mappingStore.ts`
- **Commit:** cfdd653

## Verification Results

```
npx tsx --test src/state/mappingStore.test.ts

✔ mappingStore — 24-01 (5.9974ms)
  tests 20 | pass 20 | fail 0

npx tsc --noEmit
(exit 0 — no errors)
```

## Known Stubs

None. All store actions are fully implemented. No placeholder data flows to any rendering layer at this plan scope.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced by this plan. All trust boundary mitigations from the plan's `<threat_model>` were implemented:
- T-24-01: `isRecord` + `typeof device_id === 'string'` guard in `updateFromFleetRegistry`
- T-24-02: `revision/applied_revision` number guards + `assignments` Record guard in `updateFromMappingCurrent`

## Self-Check: PASSED

- `rehab-robotics-studio/src/state/mappingStore.ts` — FOUND
- `rehab-robotics-studio/src/state/mappingStore.test.ts` — FOUND
- Commit `9ce8857` (RED) — FOUND
- Commit `cfdd653` (GREEN) — FOUND
- All 20 tests green — CONFIRMED
- TypeScript clean — CONFIRMED
