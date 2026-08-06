---
phase: 19-studio-controls-live-angle
plan: "01"
subsystem: opensim-visualizer-control
tags: [ros2, std-srvs, trigger, opensim, simbody, status]

requires:
  - phase: 18-realtime-opensim-ik-outputs
    provides: Calibrated Orientation IK, JointState publication, and OpenSim status
provides:
  - Argument-free `/opensim/visualizer/open` Trigger contract
  - Idempotent adapter-owned native visualizer open/retry operation
  - Persistent opening/open/unavailable/failed visualization status
  - Failure isolation from calibration, IK status, diagnostics, and JointState publication
affects: [19-02, 19-05, studio-toolbar, health-panel]

tech-stack:
  added: []
  patterns:
    - "Node-owned std_srvs/Trigger delegates once to an adapter-owned native resource"
    - "Optional native failures are normalized into persistent JSON-safe status"

key-files:
  created: []
  modified:
    - backend/rehab_robotics_bridge/opensim/ik_contracts.py
    - backend/rehab_robotics_bridge/opensim_adapter.py
    - backend/rehab_robotics_bridge/opensim_node.py
    - backend/test/test_opensim_adapter.py
    - backend/test/test_opensim_node.py

key-decisions:
  - "The browser-facing service accepts no path, command, process, or executable input."
  - "Visualizer request failures persist until a successful retry, while later adapter-native failures may replace an open state."

patterns-established:
  - "Visualizer transitions are signature-deduplicated and published through the existing `/opensim/status` visualization object."
  - "Native open failures are caught at both adapter and ROS callback boundaries."

requirements-completed: [VIS-01, VIS-02]

duration: 4min
completed: 2026-07-28
---

# Phase 19 Plan 01: Native Visualizer Trigger Summary

**A bounded ROS Trigger now shows the node-owned OpenSim visualizer idempotently, with retryable persistent status and complete isolation from the calibrated IK path.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-28T20:10:46Z
- **Completed:** 2026-07-28T20:14:40Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added the fixed `/opensim/visualizer/open` `std_srvs/Trigger` service without exposing any caller-controlled process or path input.
- Added adapter operations for native success, repeated show/raise requests, unavailable runtimes, contained exceptions, and successful retry recovery.
- Preserved `opening`, `open`, `unavailable`, and `failed` state/reason through the existing JSON-safe OpenSim status snapshot.
- Proved visualizer failure does not interrupt calibration, IK status, diagnostics, or stamped JointState publication.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add the idempotent native visualizer adapter operation** - `1bc00da` (feat)
2. **Task 2: Expose the bounded Trigger and persistent node status** - `4ff1ddd` (feat)

## Files Created/Modified

- `backend/rehab_robotics_bridge/opensim/ik_contracts.py` - Defines the fixed visualizer-open service name.
- `backend/rehab_robotics_bridge/opensim_adapter.py` - Adds no-spawn open operations with stable failure and retry semantics.
- `backend/rehab_robotics_bridge/opensim_node.py` - Registers the Trigger, normalizes callback results, and publishes deduplicated status transitions.
- `backend/test/test_opensim_adapter.py` - Covers success, repeat, unavailable, exception persistence, and recovery without OpenSim installed.
- `backend/test/test_opensim_node.py` - Covers service type/name, one delegation per request, malformed/exception containment, retry, transition deduplication, and IK isolation.

## Decisions Made

- Kept native-window ownership entirely inside `OpenSimVisualizerAdapter`; the ROS callback only performs one argument-free delegation.
- Retained explicit request failures in node status until a successful retry, while allowing a later adapter-native failure to replace an open state.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The three installed-binding/native-window smoke tests remain skipped because the Windows Python host has no OpenSim/Simbody runtime; this is the expected `human_needed` boundary documented by the plan.

## Known Stubs

None.

## Verification

- `$env:PYTHONPATH='backend'; python -m unittest backend.test.test_opensim_node backend.test.test_opensim_adapter -v`
  - Result: 62 tests run, 59 passed, 3 expected runtime-dependent skips.
- `git diff --check HEAD~2..HEAD`
  - Result: passed.
- Security scan found no subprocess, shell, WSL, or caller-controlled process-launch path in the five plan files.
- Preservation baseline remained untracked and unstaged; all five backend targets were clean before execution and only exact task paths were staged.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for Plan 19-02 to expose the Trigger through rosbridge and add typed IK/JointState frontend snapshots.
- Real native-window appearance still requires the documented WSL/OpenSim/Simbody human smoke when that runtime is available.

## Self-Check: PASSED

- All five modified key files exist.
- Task commits `1bc00da` and `4ff1ddd` exist in git history.
- Plan-level backend verification passes.
- `.planning/phases/19-studio-controls-live-angle/19-WORKTREE-BASELINE.local.md` remains untracked and unstaged.

---
*Phase: 19-studio-controls-live-angle*
*Completed: 2026-07-28*
