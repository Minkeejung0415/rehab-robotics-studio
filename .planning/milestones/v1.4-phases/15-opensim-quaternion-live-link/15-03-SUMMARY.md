---
phase: 15-opensim-quaternion-live-link
plan: "03"
subsystem: ros-launch-and-verification
tags: [ros2, sensor-msgs, opensim, launch, quaternion, integration-testing]

requires:
  - phase: 15-opensim-quaternion-live-link
    plan: "01"
    provides: Quaternion conversion boundary and optional native visualizer adapter
  - phase: 15-opensim-quaternion-live-link
    plan: "02"
    provides: Dual native-IMU bridge callbacks and versioned freshness status
provides:
  - Configurable ROS launch wiring for topics, frames, model, freshness, status, and bridge enablement
  - Default-off deterministic identity and positive-90Z native Imu publisher
  - Hardware-free publisher-to-bridge-to-adapter integration proof
  - Operator guide for convention, status, fallback behavior, and non-IK scope
affects: [opensim-operations, local-verification, ros2-launch]

tech-stack:
  added: []
  patterns:
    - Default-off synthetic ROS publishers with explicit test frame identities
    - Source/AST launch contracts that require no ROS launch runtime
    - Exact producer messages reused as bridge callback inputs in cross-component tests

key-files:
  created:
    - backend/rehab_robotics_bridge/opensim_test_publisher.py
    - backend/test/test_opensim_launch.py
    - docs/opensim-quaternion-live-link.md
  modified:
    - backend/launch/rehab_robotics.launch.py
    - backend/setup.py

key-decisions:
  - "Keep deterministic messages opt-in and identify them as opensim_test_master/opensim_test_slave so synthetic data is explicit."
  - "Use the same launch topic arguments for the bridge and test publisher so hardware-free verification exercises the configured production paths."
  - "Document sensor triads strictly as raw mapped orientations, never as calibration, inverse kinematics, model pose, joint angles, or clinical output."

patterns-established:
  - "Fixture contract: known_orientations() creates fresh native Imu objects containing master identity and slave positive-90Z ROS xyzw quaternions."
  - "Launch preservation: source contracts lock OpenSim parameters while also asserting every unrelated acquisition and operator node remains present."

requirements-completed: [LINK-01, LINK-02, LINK-03, LINK-04, LINK-05, LINK-06]

duration: 5min
completed: 2026-07-27
---

# Phase 15 Plan 03: OpenSim Launch and Deterministic Live-Link Proof Summary

**A default-off native Imu fixture publisher, complete ROS launch parameter wiring, and hardware-free producer-to-bridge-to-adapter proof for identity and positive-90Z sensor orientations**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-27T19:44:48Z
- **Completed:** 2026-07-27T19:49:36Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added a packaged deterministic publisher that sends fresh, timestamped master identity and slave positive-90-degree-Z native `sensor_msgs/Imu` messages on configurable topics and rate.
- Replaced only the obsolete OpenSim filtered-JSON/UDP launch boundary with configurable native topics, model-frame mappings, model path, stale timeout, status topic, bridge enablement, and a default-off test publisher.
- Proved that the exact publisher-created message objects traverse both configured bridge callbacks into the correct fake-adapter roles/frames/normalized matrices with independent counters and freshness.
- Documented launch commands, hardware-free verification, status inspection, optional-runtime fallback, quaternion normalization, and the explicit non-IK/non-clinical scope.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 1 RED: Freeze deterministic publisher contracts** - `2b240fb` (test)
2. **Task 1 GREEN: Add deterministic native Imu publisher** - `6efe0ed` (feat)
3. **Task 2 RED: Freeze launch and cross-component contracts** - `dcb9f11` (test)
4. **Task 2 GREEN: Wire and document the OpenSim live link** - `ae95d54` (feat)

## Files Created/Modified

- `backend/rehab_robotics_bridge/opensim_test_publisher.py` - Fresh deterministic Imu construction, configurable publishers/rate, shared timestamps, and ROS entry point.
- `backend/launch/rehab_robotics.launch.py` - Native live-link arguments, exact bridge parameter wiring, and default-off test-publisher node.
- `backend/setup.py` - Additive `opensim_test_publisher` console entry.
- `backend/test/test_opensim_launch.py` - Publisher, setup, launch AST/source, and exact producer-to-adapter integration contracts.
- `docs/opensim-quaternion-live-link.md` - Operator build, launch, convention, status, fallback, and safety/meaning guide.

## Decisions Made

- The deterministic publisher is disabled by default and uses explicit `opensim_test_*` frame IDs to mitigate accidental synthetic-data spoofing.
- Both bridge and publisher consume the same configurable launch topic arguments, avoiding a separate verification-only routing convention.
- The operator guide consistently calls the visual output mapped sensor-coordinate triads; it does not claim model-pose, IK, calibration, joint-angle, or clinical results.

## Inherited Dirty Hunks Preserved

The required pre-edit baseline showed unrelated, uncommitted changes in both overlapping files:

- `backend/setup.py` had already replaced `imu_aggregator_node` with the existing `esp_filter`, `opensim_bridge`, `esp_record`, `esp_status`, and `processing_block_observer` entries. Plan 15-03 added only the `opensim_test_publisher` entry; every inherited entry was retained.
- `backend/launch/rehab_robotics.launch.py` had already replaced the aggregator/config launch with paired master/slave bridges, per-role filters, recorder, status, processing observer, conditional rosbridge, and an interim OpenSim UDP node. Plan 15-03 retained all unrelated nodes, arguments, parameters, and conditions while replacing only the interim OpenSim UDP arguments/wiring and adding the opt-in publisher.

Because the inherited changes shared the same tracked files and were not separately committed before execution, the task commits necessarily contain those captured baseline hunks. The source contracts and before/after comparison distinguish the Plan 15-03 additions from that inherited content.

## Verification

- Focused fake/source/cross-component command - **PASS** (36 tests).
- `python -m unittest discover -s backend/test -p 'test_*.py' -v` - **PASS** (64 tests, 1 permitted skip because OpenSim is not installed).
- `python -m unittest backend.test.test_opensim_adapter.OpenSimInstalledRuntimeSmokeTests -v` - **PASS** with one explicit `opensim module is not installed` skip.
- Python AST parsing for publisher, launch, setup, and test sources - **PASS**.
- Post-edit source contracts confirm all existing non-OpenSim launch nodes/setup entries remain and `opensim_udp_host`, `opensim_udp_port`, and the obsolete OpenSim filtered-topic mapping are absent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Made ROS test stubs stable across direct and discovery imports**
- **Found during:** Task 2 full backend discovery
- **Issue:** The new test module imported `backend.test.test_opensim_node` unconditionally, while discovery loads the same test as top-level `test_opensim_node`; the duplicate module identities created different stub `Node` classes and caused two false discovery failures.
- **Fix:** Select the matching import namespace from `__package__`, so direct module execution and discovery each reuse one canonical stub module.
- **Files modified:** `backend/test/test_opensim_launch.py`
- **Verification:** Both the 36-test focused command and 64-test discovery command pass.
- **Committed in:** `ae95d54`

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** Test-harness-only correction required for the mandated dual execution modes; no runtime scope change.

## Issues Encountered

- OpenSim is not installed in this environment. The separately invoked installed-runtime smoke skipped for that exact reason; fake adapter, optional-runtime fallback, source, and cross-component contracts all passed.
- A supplementary `py_compile` attempt encountered an access-denied rename inside the pre-existing untracked `backend/rehab_robotics_bridge/__pycache__`. No owned source was affected; direct AST parsing and all unittest gates passed.

## Known Stubs

None.

## Threat Flags

None - launch configuration, synthetic ROS input, and operator semantics are all covered by T-15-08 through T-15-10.

## TDD Gate Compliance

- RED commit `2b240fb` precedes GREEN commit `6efe0ed` for Task 1.
- RED commit `dcb9f11` precedes GREEN commit `ae95d54` for Task 2.
- Both focused task contracts and the complete backend suite pass after GREEN.

## User Setup Required

None - no dependency was installed. Native visualization remains optional and requires an existing OpenSim Python runtime plus a compatible `.osim` model.

## Next Phase Readiness

- All three Phase 15 plans are implemented and locally verified without connected ESP hardware or ROS/OpenSim launch imports.
- A machine with OpenSim installed should run the documented launch with a compatible model and execute `OpenSimInstalledRuntimeSmokeTests` for native-wrapper validation.

## Self-Check: PASSED

- All five declared implementation/test/documentation files exist.
- All four TDD task commits exist in git history in RED/GREEN order.
- Owned implementation paths are clean after task commits.
- Focused, discovery, and installed-runtime-smoke commands completed with only the permitted missing-OpenSim skips.
- No placeholders, TODOs, FIXME markers, or goal-blocking stubs exist in Plan 15-03 files.

---
*Phase: 15-opensim-quaternion-live-link*
*Completed: 2026-07-27*
