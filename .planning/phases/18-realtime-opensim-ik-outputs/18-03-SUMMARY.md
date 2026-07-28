---
phase: 18-realtime-opensim-ik-outputs
plan: "03"
subsystem: opensim-ik
tags: [ros2, joint-states, ik-status, diagnostics, opensim-bridge]

requires:
  - phase: 18-01
    provides: OrientationIkSolver, Fake, Unavailable, ik_status_dict
  - phase: 18-02
    provides: create_orientation_ik_solver
provides:
  - Stamped /opensim/joint_states publish gate
  - /opensim/ik_status JSON schema rehab.opensim_ik_status.1
  - /diagnostics String JSON heartbeat
  - Launch params ik_joint_names / ik_coordinate_paths
affects:
  - Phase 19 Studio JointState subscription

tech-stack:
  added: []
  patterns:
    - "Dual gate: may_publish_joint_states + solution_valid + source stamp"
    - "Diagnostics as std_msgs/String JSON (DiagnosticArray deferred)"

key-files:
  created: []
  modified:
    - backend/rehab_robotics_bridge/opensim_node.py
    - backend/test/test_opensim_node.py
    - backend/rehab_robotics_bridge/opensim/ik_contracts.py
    - docs/opensim-ik-contracts.md
    - backend/launch/opensim_live_link.launch.py

key-decisions:
  - "Diagnostics use String JSON on /diagnostics for stubbed-test simplicity"
  - "Never feed relative_orientation_angle_deg into JointState"
  - "Clear cal resets solver and clears _ik_solution"

patterns-established:
  - "ik_solver= constructor injection for OpenSim-free node tests"

requirements-completed: [IK-05, IK-06, IK-07]

duration: 25min
completed: 2026-07-28
---

# Phase 18 Plan 03: opensim_bridge IK Wiring Summary

**Calibrated live IMU pairs drive OrientationIkSolver; stamped `/opensim/joint_states` publish only when solution_valid, with ik_status + diagnostics observability.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Fake path proves identity knee_angle_r → 0 rad stamped JointState through the node
- UNCALIBRATED / clear / invalid / missing stamp fail closed
- Contracts doc updated for Phase 18 ik_status schema and stamp policy

## Task Commits

1. **Task 1: Extend opensim_node tests** - (test(18-03))
2. **Task 2: Wire solver + status + docs** - (feat(18-03))

## Decisions Made

- Chose String JSON diagnostics over DiagnosticArray to keep ROS-free stubs simple
- Production default solver from `create_orientation_ik_solver` (Unavailable when model/APIs missing)

## Deviations from Plan

**1. [Rule 2 - Missing critical] Diagnostics format**
- Used `std_msgs/String` JSON on `/diagnostics` instead of `diagnostic_msgs/DiagnosticArray`
- Rationale: Claude discretion in plan; avoids new stub/package friction in unit tests
- Documented in contracts + this SUMMARY

## Self-Check: PASSED
