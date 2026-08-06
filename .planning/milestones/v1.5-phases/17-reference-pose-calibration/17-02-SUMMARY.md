---
phase: 17-reference-pose-calibration
plan: "02"
subsystem: opensim-bridge
tags: [ros2, calibration, trigger, joint-states, opensim_bridge]

requires:
  - phase: 17-reference-pose-calibration
    provides: CalibrationController pure-Python module
provides:
  - /opensim/calibration/capture and /clear Trigger services
  - /opensim/calibration_status JSON + status_snapshot.calibration
  - Hard joint_states gate seam (_maybe_publish_joint_states)
affects:
  - 17-03 Studio toolbar/HealthPanel
  - 18 IK solver publish path

tech-stack:
  added: []
  patterns:
    - "Injectable CalibrationController for ROS-free node tests"
    - "may_publish_joint_states AND ik_solution required before JointState"

key-files:
  created: []
  modified:
    - backend/rehab_robotics_bridge/opensim_node.py
    - backend/test/test_opensim_node.py
    - docs/opensim-ik-contracts.md

key-decisions:
  - "Capture rejects when sensors missing/not live"
  - "Phase 17 never fabricates JointState even when CALIBRATED"
  - "calibration_window_s and calibration_max_dispersion_deg as ROS params"

patterns-established:
  - "create_service(Trigger) pattern mirrored from esp32 SetBool services"
  - "status_snapshot embeds calibration for existing Studio /opensim/status consumers"

requirements-completed: [IK-01, IK-02, IK-03, IK-04]

duration: 15min
completed: 2026-07-28
---

# Phase 17 Plan 02: OpenSim Bridge Calibration Wiring Summary

**opensim_bridge exposes capture/clear Trigger services, publishes calibration status, and hard-gates /opensim/joint_states**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-28T17:42:00Z
- **Completed:** 2026-07-28T17:55:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Trigger services at locked `/opensim/calibration/capture|clear` names
- Live IMU pairs feed CalibrationController while CAPTURING
- JointState publisher never emits without CALIBRATED + IK solution (solution absent in Phase 17)

## Task Commits

1. **Task 1: Extend opensim_node tests** - `d3e52f5` (test)
2. **Task 2: Wire CalibrationController into OpenSimBridgeNode** - `aa50858` (feat)

## Files Created/Modified
- `backend/rehab_robotics_bridge/opensim_node.py` - Services, status, gate
- `backend/test/test_opensim_node.py` - Stub create_service + calibration tests
- `docs/opensim-ik-contracts.md` - Phase 17 implementation notes

## Decisions Made
- Injectable controller for fast unit windows
- Optional ROS params for window/dispersion
- No InverseKinematicsSolver (Phase 18)

## Deviations from Plan

**1. [Rule 1 - Bug] Updated existing publisher-count assertions**
- **Found during:** Task 1 (tests)
- **Issue:** New publishers broke `len(node.publishers) == 1` assumptions
- **Fix:** Assert by topic name instead of fixed indices
- **Files modified:** backend/test/test_opensim_node.py
- **Committed in:** d3e52f5

---

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** Necessary for suite green; no scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Ready for 17-03 Studio Calibrate / Clear cal + HealthPanel status

## Self-Check: PASSED
- FOUND: opensim_node.py calibration wiring
- FOUND: d3e52f5, aa50858

---
*Phase: 17-reference-pose-calibration*
*Completed: 2026-07-28*
