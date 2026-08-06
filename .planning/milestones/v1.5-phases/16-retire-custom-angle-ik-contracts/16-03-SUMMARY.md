---
phase: 16-retire-custom-angle-ik-contracts
plan: "03"
subsystem: contracts
tags: [opensim, ros2, joint-states, calibration-gate, contracts]

requires:
  - phase: 16-retire-custom-angle-ik-contracts
    provides: Retired custom joint_angle product path (backend + GUI)
provides:
  - Locked /opensim/joint_states JointState contract (D-16-03)
  - Hard CALIBRATED may_publish_joint_states gate (D-16-04)
  - Calibration capture/clear service name constants
  - docs/opensim-ik-contracts.md human-readable twin
affects:
  - Phase 17 calibration services
  - Phase 18 IK solver / joint_states publisher
  - Phase 19 GUI JointState wiring

tech-stack:
  added: []
  patterns:
    - "Frozen string constants + may_publish helper as machine-checkable contracts"
    - "Docs twin required strings asserted by unittest/python -c"

key-files:
  created:
    - backend/rehab_robotics_bridge/opensim/__init__.py
    - backend/rehab_robotics_bridge/opensim/ik_contracts.py
    - backend/test/test_ik_contracts.py
    - docs/opensim-ik-contracts.md
  modified: []

key-decisions:
  - "Lock product output at /opensim/joint_states (supersedes ARCHITECTURE /joint_states draft)"
  - "may_publish_joint_states true only for CALIBRATED"
  - "No solver or calibration UI code in this plan"

patterns-established:
  - "rehab_robotics_bridge.opensim package for IK contract modules"
  - "PRODUCT_JOINT_ANGLE_TOPIC marked deprecated and asserted unequal to JOINT_STATES_TOPIC"

requirements-completed: [IK-00]

duration: 8min
completed: 2026-07-28
---

# Phase 16 Plan 03: Lock OpenSim IK ROS Contracts Summary

**Documented and unittest-locked `/opensim/joint_states` JointState output with hard CALIBRATED publication gate and calibration capture/clear service names**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-07-28T17:42:00Z
- **Completed:** 2026-07-28T17:50:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `ik_contracts.py` freezes topic/service/state constants + `may_publish_joint_states`
- `docs/opensim-ik-contracts.md` is the human twin for Phases 17–19
- Custom `/opensim/joint_angle` explicitly retired as product IK

## Task Commits

1. **Task 1: Machine-checkable IK contract constants and tests** - `6cc0da6` (test) + constants in feat
2. **Task 2: Write opensim-ik-contracts.md** - included in `feat(16-03)` below

## Files Created/Modified
- `backend/rehab_robotics_bridge/opensim/ik_contracts.py` - Frozen contract constants
- `backend/rehab_robotics_bridge/opensim/__init__.py` - Package init
- `backend/test/test_ik_contracts.py` - Unittest coverage
- `docs/opensim-ik-contracts.md` - Human-readable contract sheet

## Decisions Made
- Prefer D-16-03 `/opensim/joint_states` over ARCHITECTURE draft `/joint_states`
- Contracts-only: no rclpy nodes, no OpenSim imports

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 16 contracts complete; Phase 17 can implement calibration services against locked names. Do not start Phase 17 in this execution wave.

---
*Phase: 16-retire-custom-angle-ik-contracts*
*Completed: 2026-07-28*
