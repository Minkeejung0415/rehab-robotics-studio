---
phase: 18-realtime-opensim-ik-outputs
plan: "01"
subsystem: opensim-ik
tags: [opensim, orientation-ik, fake-solver, mounting-offsets, tdd]

requires:
  - phase: 17-reference-pose-calibration
    provides: CalibrationArtifact, may_publish_joint_states gate
provides:
  - IkSolution / OrientationIkSolver protocol
  - FakeOrientationIkSolver known-pose direction fixture
  - UnavailableOrientationIkSolver fail-closed backend
  - apply_mounting_offsets OpenSense-style helper
affects:
  - 18-02 OpenSim Python adapter
  - 18-03 opensim_bridge wiring

tech-stack:
  added: []
  patterns:
    - "OrientationIkSolver Protocol with Fake + Unavailable; never relative-quat product path"
    - "q_corrected = q_sensor ⊗ conjugate(q_mount) shared offset helper"

key-files:
  created:
    - backend/rehab_robotics_bridge/opensim/orientation_ik.py
    - backend/test/test_opensim_orientation_ik.py
  modified:
    - backend/rehab_robotics_bridge/opensim/__init__.py

key-decisions:
  - "Fake maps offset-corrected relative orientation about +X to knee_angle_r radians"
  - "Unavailable always solution_valid=False with empty positions_rad"
  - "Docstring avoids naming relative_orientation_angle_deg so grep contract stays clean"

patterns-established:
  - "ROS-free IK seam in opensim/orientation_ik.py before OpenSim bindings"

requirements-completed: [IK-05, IK-07]

duration: 15min
completed: 2026-07-28
---

# Phase 18 Plan 01: Orientation IK Seam Summary

**ROS-free OrientationIkSolver protocol with Fake (identity→0, flexed→+π/2) and Unavailable fail-closed backends plus shared mounting-offset helper.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-28T17:49:00Z
- **Completed:** 2026-07-28T18:05:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Locked IkSolution / OrientationIkSolver shapes for product JointState path
- Fake proves positive flexion direction for `knee_angle_r` without OpenSim
- Unavailable never validates; offsets applied via shared helper

## Task Commits

1. **Task 1: Failing tests for Orientation IK seam** - `a3826e3` (test)
2. **Task 2: Implement orientation_ik seam to green** - `26b96e0` (feat)

## Files Created/Modified

- `backend/rehab_robotics_bridge/opensim/orientation_ik.py` - seam + Fake/Unavailable
- `backend/rehab_robotics_bridge/opensim/__init__.py` - public exports
- `backend/test/test_opensim_orientation_ik.py` - ROS-free TDD

## Decisions Made

- Flexion axis for Fake is body +X; mounting correction uses conjugate(mount) Hamilton product
- Followed D-18-01/03/07/08 locked decisions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring contained forbidden symbol name**
- **Found during:** Task 2 verification
- **Issue:** Module contract test greps for `relative_orientation_angle_deg` substring; docstring mentioned it
- **Fix:** Rephrased docstring to "debug relative-quaternion angle helper"
- **Files modified:** `orientation_ik.py`
- **Verification:** unittest green
- **Committed in:** `26b96e0`

## Self-Check: PASSED
