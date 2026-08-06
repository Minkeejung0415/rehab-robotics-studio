---
phase: 24-rosbridge-and-studio-mapping-workspace
plan: "02"
subsystem: rosbridge-data-source
tags: [tdd, rosbridge, mapping, typescript, parse-guards, service-calls]
dependency_graph:
  requires: [24-01-mappingStore]
  provides: [RosbridgeDataSource-mapping-extensions]
  affects: [appDataSource.ts (Plan 24-04), MappingWorkspace (Plan 24-03)]
tech_stack:
  added: []
  patterns:
    - guard-parse functions following parseOpenSimStatus pattern
    - optional constructor callbacks appended at known positions
    - callService delegation for rosbridge service calls
key_files:
  created: []
  modified:
    - rehab-robotics-studio/src/data/RosbridgeDataSource.ts
    - rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts
decisions:
  - Parse functions exported at module level (not class methods) for direct testability without instantiation
  - callIdentifyDevice added as new method (was not pre-existing on the class)
  - Service toResult extractors cast values as Record<string,unknown> to access non-standard rosbridge response fields
  - Invalid JSON in new topic handlers silently dropped via try/catch (not relying on outer catch)
metrics:
  duration_minutes: 4
  completed: "2026-08-05T22:16:29Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 24 Plan 02: RosbridgeDataSource Extensions Summary

**One-liner:** 5 exported guard-parse functions + 5 new topic subscriptions + 4 mapping service call methods added to RosbridgeDataSource; 15 new node:test tests pass alongside all 27 existing tests.

## What Was Built

Extended `RosbridgeDataSource.ts` to support the Phase 24 Mapping Workspace requirements (D-08 through D-11, D-17):

### 5 Exported Parse Functions (D-10, T-24-05)
Each follows the `parseOpenSimStatus` guard pattern — `isRecord` check + field-type validation — returning `null` on any failure, never throwing:

- `parseModelCatalog(payload)` — validates `model_hash` (string), `model_path` (string), `frame_list` (array of `{path, name}`)
- `parseMappingCurrent(payload)` — validates `revision` (number), `applied_revision` (number), `assignments` (record with per-device `{segment, frame, state}`)
- `parseFleetRegistry(payload)` — validates `devices` (array with required `device_id` string per entry)
- `parseNCalibrationStatus(payload)` — validates `state` is one of `'capturing'|'calibrated'|'uncalibrated'`
- `parseInputValidity(payload)` — validates `device_validities` (record of `device_id → boolean`)

### Constructor Extension (D-08)
5 new optional callbacks appended at positions 12-16, preserving all existing 11 positions unchanged:
- `onModelCatalog`, `onMappingCurrent`, `onFleetRegistry`, `onCalibrationStatus`, `onInputValidity`

### Topic Subscriptions (D-09)
5 new entries appended to the `subscriptions` array in `socket.onopen`:
- `/rehab/model/catalog`, `/rehab/mapping/current`, `/esp/fleet/registry`, `/rehab/calibration/status`, `/rehab/opensim/input_validity` — all as `std_msgs/msg/String`

### handleMessage Dispatch (D-10)
5 new topic dispatch blocks inserted before the IMU fallthrough check. Each: parse `envelope.msg.data` as JSON inside a try/catch (invalid JSON silently dropped), guard with parse function, invoke callback only when parse returns non-null.

### Service Call Methods (D-11, D-17)
4 new public methods delegate to the private `callService` pattern:
- `callSetAssignment(deviceId, segment, frame, state)` — service `/rehab/mapping/set_assignment`; `success` when `outcome === 'ok'`
- `callApplyMapping(expectedRevision)` — service `/rehab/mapping/apply`; `success` when `outcome === 'applied'`
- `callResetMapping(modelHash)` — service `/rehab/mapping/reset`; `success` when `outcome === 'ok'`
- `callIdentifyDevice(deviceId, timeoutMs=5000)` — service `/rehab/identify/device`

## TDD Gate Compliance

- RED commit `a3921d4`: 15 new Phase 24 tests appended to `RosbridgeDataSource.test.ts` — all failed (parse functions not exported, service methods not on class)
- GREEN commit `c67a90e`: implementation complete — all 15 new tests pass, all 27 existing tests still pass (42/42 total); `tsc --noEmit` clean

## Test Results

```
tests 42
pass  42
fail  0
duration_ms ~300
```

## Deviations from Plan

### Auto-fixed Issues

None. Plan executed exactly as written with one minor note:

**Note:** The plan mentioned vitest in the frontmatter artifact description (`"Vitest unit tests"`). Per the project's actual test infrastructure, `node:test` with `tsx --test` is used — the CRITICAL note in the prompt confirmed this. Tests were written using `node:test` patterns consistent with all existing test files.

## Threat Surface Scan

New topic subscriptions introduce 5 additional data flows from rosbridge WebSocket → handleMessage. These are covered by the existing T-24-05 threat entry (Tampering mitigation: field-type guards return null on any type mismatch; callback never called with partial data). No new trust boundaries introduced beyond what is in the plan's threat model.

## Known Stubs

None. No UI rendering paths or data source wiring in this plan — parse functions and service methods are pure logic, fully implemented and tested.

## Self-Check: PASSED

- `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` exists and contains `onModelCatalog` and `callSetAssignment`
- `rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts` exists and contains 15 new Phase 24 test cases
- RED commit `a3921d4` exists
- GREEN commit `c67a90e` exists
- All 42 tests pass
- `tsc --noEmit` exits 0
