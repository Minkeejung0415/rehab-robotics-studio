---
phase: 16-retire-custom-angle-ik-contracts
plan: "02"
subsystem: ui
tags: [opensim, graph, rosbridge, health-panel, fail-closed]

requires:
  - phase: 16-retire-custom-angle-ik-contracts
    provides: Backend default-OFF custom joint_angle publisher
provides:
  - Default graph opensim_ik_waiting placeholder (no product knee angle)
  - Demoted opensim_ik_live debug block without fake-zero fallback
  - Rosbridge without default /opensim/joint_angle attach
  - HealthPanel calibration-required waiting copy for IK angles
affects:
  - 16-03 IK ROS contract lock
  - Phase 19 JointState GUI wiring

tech-stack:
  added: []
  patterns:
    - "Product knee fail-closed: empty executor output, no angles=0 placeholder"
    - "getDefaultGraphDocument() for deterministic product-path tests"

key-files:
  created:
    - rehab-robotics-studio/src/graph/productKneeReadout.test.ts
  modified:
    - rehab-robotics-studio/src/state/graphStore.ts
    - rehab-robotics-studio/src/graph/mockExecutor.ts
    - rehab-robotics-studio/src/graph/blockDefinitions.ts
    - rehab-robotics-studio/src/data/RosbridgeDataSource.ts
    - rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts
    - rehab-robotics-studio/src/components/dashboard/HealthPanel.tsx
    - rehab-robotics-studio/src/types/signals.ts
    - rehab-robotics-studio/src/types/health.ts
    - rehab-robotics-studio/package.json

key-decisions:
  - "Replace default B8 with opensim_ik_waiting placeholder block"
  - "Delete default rosbridge /opensim/joint_angle subscribe rather than gate ON"
  - "HealthPanel shows Waiting (requires calibration) instead of custom deg"

patterns-established:
  - "Waiting biomechanics blocks emit no finite angles port values"
  - "Deprecated Frame.jointAngleDeg remains typed but unused by product path"

requirements-completed: [IK-00]

duration: 12min
completed: 2026-07-28
---

# Phase 16 Plan 02: Retire Studio Custom Angle as Product IK Summary

**Default graph, rosbridge, and HealthPanel no longer present custom `/opensim/joint_angle` as OpenSim IK; product knee stays waiting until calibrated joint states**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-28T17:30:00Z
- **Completed:** 2026-07-28T17:42:00Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Fail-closed `productKneeReadout.test.ts` (22 Studio tests green including new suite)
- Default B8 is `opensim_ik_waiting`; `opensim_ik_live` demoted to debug with empty output when no sample
- Rosbridge no longer attaches Float64 joint angle to frames by default

## Task Commits

1. **Task 1: Fail-closed product knee readout tests** - `71e77f1` (test)
2. **Task 2: Default graph, executor, rosbridge, and HealthPanel retirement** - `6747003` (feat)

## Files Created/Modified
- `productKneeReadout.test.ts` - Product knee contract tests
- `graphStore.ts` / `blockDefinitions.ts` / `mockExecutor.ts` - Waiting placeholder + demoted live block
- `RosbridgeDataSource.ts` (+ tests) - Removed default joint_angle attach
- `HealthPanel.tsx` - Calibration-required waiting copy
- `signals.ts` / `health.ts` - Deprecated field comments

## Decisions Made
- Prefer deleting default rosbridge subscribe over a gated-ON flag (per plan discretion)
- Keep `opensim_ik_live` in palette as clearly named debug block

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Several Studio source files (`mockExecutor.ts`, `HealthPanel.tsx`, type modules) were previously untracked WIP; included the retired versions in the feat commit so the product path is versioned.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- GUI product path waiting; ready for machine-checkable IK contracts (16-03).

---
*Phase: 16-retire-custom-angle-ik-contracts*
*Completed: 2026-07-28*
