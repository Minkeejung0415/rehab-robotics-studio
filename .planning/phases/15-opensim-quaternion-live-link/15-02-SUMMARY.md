---
phase: 15-opensim-quaternion-live-link
plan: "02"
subsystem: ros-bridge
tags: [ros2, sensor-msgs, imu, opensim, json-status, freshness]

requires:
  - phase: 15-opensim-quaternion-live-link
    plan: "01"
    provides: Quaternion conversion boundary and optional visualizer adapter
provides:
  - Configurable independent master and slave sensor_msgs/Imu subscriptions
  - Per-role conversion, update counters, freshness, errors, and lifecycle states
  - Compact timer-driven OpenSim live-link status JSON and transition logs
affects: [15-03, opensim-launch, opensim-documentation]

tech-stack:
  added: []
  patterns:
    - Injected adapter and monotonic clock for ROS-free deterministic tests
    - Visualization availability is orthogonal to accepted sensor input state

key-files:
  created:
    - backend/rehab_robotics_bridge/opensim_node.py
    - backend/test/test_opensim_node.py
  modified: []

key-decisions:
  - "Publish status on a bounded periodic timer instead of at IMU message rate."
  - "Clamp invalid or non-positive stale timeouts to 0.1 seconds and run the timer at no more than half the effective timeout."
  - "Treat unavailable-adapter success as live sensor input while preserving visualization availability and reason separately."

patterns-established:
  - "Role isolation: each subscription callback validates and updates only its fixed master or slave role."
  - "Transition observability: log only state or reason changes while publishing status on every timer tick."

requirements-completed: [LINK-01, LINK-02, LINK-03, LINK-04, LINK-05, LINK-06]

duration: 4min
completed: 2026-07-27
---

# Phase 15 Plan 02: Dual-IMU OpenSim Live-Link Node Summary

**Configurable native master/slave IMU subscriptions now drive independent OpenSim adapter updates with compact JSON lifecycle status, transition logs, and monotonic stale detection**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-27T19:39:04Z
- **Completed:** 2026-07-27T19:43:05Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Replaced the filtered-JSON UDP forwarder with exactly two configurable native `sensor_msgs/Imu` subscriptions and injected adapter construction.
- Kept master and slave conversion, accepted-update counters, last-valid timestamps, errors, and waiting/live/invalid/stale/mapping-error states fully independent.
- Added compact sorted JSON status on a bounded timer, transition-only logs, and healthy non-visual behavior for missing bindings, model failures, and unsupported decoration capabilities.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 1 RED: Freeze dual-IMU forwarding contracts** - `c2c2de1` (test)
2. **Task 1 GREEN: Route independent IMU streams to the adapter** - `cd3a56b` (feat)
3. **Task 2 RED: Freeze status and freshness contracts** - `4438209` (test)
4. **Task 2 GREEN: Publish status and track independent freshness** - `ca15aaa` (feat)

## Files Created/Modified

- `backend/rehab_robotics_bridge/opensim_node.py` - Dual subscriptions, adapter wiring, role state, compact JSON status, timer-driven freshness, and transition logging.
- `backend/test/test_opensim_node.py` - ROS stand-ins, fake adapters, controllable clock, fake publisher/logger, and forwarding/status lifecycle tests.

## Decisions Made

- Status is published on timer ticks rather than each IMU callback so high-rate input performs only validation, one adapter update, and state bookkeeping.
- The effective stale timeout has a safe `0.1` second minimum; timer cadence is the lesser of half the timeout and `0.5` seconds.
- A successful `UnavailableVisualizerAdapter` update advances freshness and counters exactly like a visual update; only actual adapter rejection or update failure produces `mapping_error`.

## Verification

- `$env:PYTHONPATH='backend'; python -m unittest backend.test.test_opensim_node.OpenSimNodeForwardingTests -v` - **PASS** (5 tests).
- `$env:PYTHONPATH='backend'; python -m unittest backend.test.test_opensim_node -v` - **PASS** (12 tests).
- `$env:PYTHONPATH='backend'; python -m unittest backend.test.test_opensim_adapter backend.test.test_opensim_node -v` - **PASS** (30 tests, 1 permitted skip because OpenSim is not installed).
- `python -m py_compile backend/rehab_robotics_bridge/opensim_node.py backend/test/test_opensim_node.py` - **PASS**.
- Legacy executable-symbol scan - **PASS**: `filtered_topic`, `udp_host`, `udp_port`, and `send_opensim_packet` are absent.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- OpenSim is not installed in this environment. The prior-plan installed-runtime smoke test skipped explicitly; all node behavior, including missing-runtime/model/capability no-op semantics, passed with deterministic adapters.

## Known Stubs

None.

## Threat Flags

None - the two ROS subscriptions, status publisher, operator parameters, and adapter boundary are all covered by the plan threat model.

## TDD Gate Compliance

- RED commit `c2c2de1` precedes GREEN commit `cd3a56b` for Task 1.
- RED commit `4438209` precedes GREEN commit `ca15aaa` for Task 2.
- Both task suites and the combined adapter/node regression pass after GREEN.

## User Setup Required

None - OpenSim remains optional and no package-manager dependency was added.

## Next Phase Readiness

- Plan 15-03 can wire the seven node parameters through launch files and document the live-link workflow.
- Native visualizer validation still requires a machine with the OpenSim Python runtime and a suitable model asset.

## Self-Check: PASSED

- Both declared key files exist.
- All four task commits exist in git history in RED/GREEN order.
- The complete adapter/node suite passes and the legacy UDP boundary is absent.
- No placeholders or known stubs exist in the two task-owned code files.
- No task-owned code file remains modified or untracked before summary commit.

---
*Phase: 15-opensim-quaternion-live-link*
*Completed: 2026-07-27*
