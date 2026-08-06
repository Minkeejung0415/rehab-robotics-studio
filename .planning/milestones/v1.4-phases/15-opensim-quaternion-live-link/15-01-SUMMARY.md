---
phase: 15-opensim-quaternion-live-link
plan: "01"
subsystem: opensim-adapter
tags: [python, opensim, simbody, quaternion, native-visualizer, tdd]

requires:
  - phase: existing-esp32-bridge
    provides: ROS sensor_msgs/Imu orientation values in x-y-z-w order
provides:
  - Deterministic normalized ROS quaternion to OpenSim rotation boundary
  - Optional OpenSim model/native-visualizer adapter with independently updateable labeled sensor triads
  - Stable unavailable adapter for absent bindings, model assets, frames, or dynamic-decoration support
  - Hardware-free fake-binding contracts and optional installed-runtime smoke coverage
affects: [15-02-opensim-node, ros-live-link, opensim-status]

tech-stack:
  added: []
  patterns:
    - Lazy optional native-runtime import behind an adapter factory
    - Immutable normalized rotation value at the ROS-to-OpenSim trust boundary
    - Retained ground decorations with documented decoration-generator fallback

key-files:
  created:
    - backend/rehab_robotics_bridge/opensim_adapter.py
    - backend/test/test_opensim_adapter.py
  modified: []

key-decisions:
  - "Mapped OpenSim frames supply only ground position; incoming sensor quaternions supply absolute displayed triad orientation."
  - "Native visualization failures degrade to stable JSON-safe unavailable status instead of breaking module import or live subscription."
  - "Retained Simbody decorations are preferred, with a DecorationGenerator callback fallback when exposed by the installed bindings."

patterns-established:
  - "Quaternion boundary: accept ROS xyzw, reject non-finite/norm below 1e-8, normalize once, and expose scalar-first plus active 3x3 representations."
  - "Visualizer ownership: one adapter owns the model, state, frame references, visualizer, decorations, and indices for its lifetime."

requirements-completed: [LINK-02, LINK-03, LINK-04, LINK-05, LINK-06]

duration: 8min
completed: 2026-07-27
---

# Phase 15 Plan 01: OpenSim Quaternion Live Link Adapter Summary

**A deterministic ROS-to-OpenSim quaternion boundary plus a lazy native-visualizer adapter that anchors independently mutable labeled sensor triads at exact configured model frames**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-27T19:29:00Z
- **Completed:** 2026-07-27T19:37:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added immutable, stdlib-only quaternion validation, normalization, scalar-first semantics, and right-handed active rotation matrices.
- Added an optional OpenSim adapter that owns model/native state, resolves exact configured frames, retains labeled ground decorations, and updates each sensor independently.
- Added stable non-visual fallback states for missing bindings/assets/frames/capabilities plus deterministic fake-binding tests and an installed-runtime smoke contract.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 1 RED: Freeze quaternion contracts** - `1143db8` (test)
2. **Task 1 GREEN: Implement quaternion conversion boundary** - `0f77bcd` (feat)
3. **Task 2 RED: Freeze visualizer adapter contracts** - `4fad657` (test)
4. **Task 2 GREEN: Implement optional native visualizer adapter** - `4f3a36e` (feat)

## Files Created/Modified

- `backend/rehab_robotics_bridge/opensim_adapter.py` - Pure quaternion boundary, adapter protocol/factory, unavailable implementation, and native visualizer implementation.
- `backend/test/test_opensim_adapter.py` - Golden quaternion cases, API-shaped fake OpenSim contracts, failure-mode coverage, and optional real-runtime smoke test.

## Decisions Made

- Quaternion output carries both normalized scalar-first `(w, x, y, z)` semantics and the equivalent immutable active 3x3 matrix so callers never depend on native OpenSim objects.
- Exact mapped frames contribute only `getTransformInGround(state).p()`; sensor messages do not mutate model coordinates or combine with articulated frame rotation.
- Retained ground-attached `Decorations` groups preserve role/frame labels and style while only the selected decoration transform changes per update.
- The factory validates model paths before lazy OpenSim import and returns reason-coded unavailable adapters for every initialization boundary.

## Verification

- `python -m unittest backend.test.test_opensim_adapter.QuaternionConversionTests backend.test.test_opensim_adapter.OpenSimAdapterContractTests -v` - **PASS** (17 tests).
- `python -m unittest backend.test.test_opensim_adapter.OpenSimInstalledRuntimeSmokeTests -v` - **PASS** with one permitted skip because the `opensim` module is not installed.
- `python -m py_compile backend/rehab_robotics_bridge/opensim_adapter.py backend/test/test_opensim_adapter.py` - **PASS**.
- Required binding-path scan confirms lazy `import_module("opensim")`, `setUseVisualizer` before `initSystem`, exact `getTransformInGround`, native visualizer access, retained add/update decoration calls, generator fallback, and one `show(state)` per accepted update.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Context7 was unavailable locally, so the implementation was checked against the official OpenSim `Model`/`ModelVisualizer` and Simbody `Visualizer` API references before freezing the fake binding.
- OpenSim is not installed in this environment. The plan-defined installed-runtime smoke class therefore skipped explicitly for module absence; it did not mask model, frame, decoration, or update failures.

## Known Stubs

None.

## TDD Gate Compliance

- RED commit exists for Task 1 and precedes its GREEN implementation commit.
- RED commit exists for Task 2 and precedes its GREEN implementation commit.
- Both task-level verification suites pass after GREEN.

## User Setup Required

None - OpenSim remains an optional pre-existing runtime and no package was installed.

## Next Phase Readiness

- Plan 15-02 can consume `VisualizerAdapter`, `ros_xyzw_to_opensim_rotation`, and `create_visualizer_adapter` without importing OpenSim or exposing native objects in ROS callbacks.
- A machine with OpenSim installed should run `OpenSimInstalledRuntimeSmokeTests` to exercise its exact wrapper/native visualizer capabilities.

## Self-Check: PASSED

- Both declared key files exist.
- All four task commits exist in git history.
- The complete always-run suite passes.
- No task-owned file remains modified or untracked before summary commit.

---
*Phase: 15-opensim-quaternion-live-link*
*Completed: 2026-07-27*
