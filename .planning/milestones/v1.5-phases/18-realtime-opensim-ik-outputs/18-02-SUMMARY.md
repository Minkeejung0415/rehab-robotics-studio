---
phase: 18-realtime-opensim-ik-outputs
plan: "02"
subsystem: opensim-ik
tags: [opensim, inverse-kinematics, factory, fail-closed, python-bindings]

requires:
  - phase: 18-01
    provides: OrientationIkSolver protocol, UnavailableOrientationIkSolver, apply_mounting_offsets
provides:
  - create_orientation_ik_solver factory
  - OpenSimOrientationIkSolver Python adapter
  - probe_opensim_orientation_ik_apis capability report
affects:
  - 18-03 opensim_bridge wiring

tech-stack:
  added: []
  patterns:
    - "Factory probes APIs then OpenSimOrientationIkSolver or Unavailable — never Fake in production"
    - "Catch native exceptions → solution_valid=False with opensim_ik_solve_failed"

key-files:
  created:
    - backend/rehab_robotics_bridge/opensim/opensim_orientation_ik.py
    - backend/test/test_opensim_orientation_ik_opensim.py
  modified:
    - backend/rehab_robotics_bridge/opensim/__init__.py

key-decisions:
  - "D-18-02 pragmatic Python 4.5.2 path; C++ 4.6 deferred"
  - "Production factory never returns FakeOrientationIkSolver"
  - "This Windows agent host has no opensim module — binding tests skipUnless"

patterns-established:
  - "Capability probe dict before constructing InverseKinematicsSolver"

requirements-completed: [IK-05]

duration: 20min
completed: 2026-07-28
---

# Phase 18 Plan 02: OpenSim Orientation IK Adapter Summary

**Official OpenSim Python orientation-IK factory with capability probing and fail-closed Unavailable fallback — never custom relative-quat product path.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `create_orientation_ik_solver` returns Unavailable for empty/missing model
- `OpenSimOrientationIkSolver` applies mounting offsets then assemble/track when APIs exist
- Always-on tests green; OpenSim binding tests skip when `opensim` not installed

## Task Commits

1. **Task 1: Factory/probe tests** - (see git log test(18-02))
2. **Task 2: Implement OpenSimOrientationIkSolver + factory** - (see git log feat(18-02))

## Decisions Made

- Prefer BufferedOrientationsReference when present; else rebuild OrientationsReference per sample on 4.5.x
- Fail closed on any native exception during solve

## Deviations from Plan

None - plan executed as written (OpenSim skipUnless path exercised as Unavailable environment).

## OpenSim availability (this environment)

**Unavailable** — `importlib.util.find_spec("opensim")` is False on the Windows Python used for unittest. Binding integration tests skipped cleanly.

## Self-Check: PASSED
