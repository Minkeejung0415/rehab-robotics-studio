# Phase 18: Real-Time OpenSim IK Outputs - Context

**Gathered:** 2026-07-28
**Status:** Ready for planning / autonomous execution
**Mode:** Locked decisions for autonomous execution (pragmatic WSL OpenSim 4.5.2 Python path)

<domain>
## Phase Boundary

After Phase 17 calibration is CALIBRATED, run official OpenSim orientation IK (OpenSense-compatible) on paired master/slave IMU orientations, publish solved joint coordinates on `/opensim/joint_states`, and expose IK validity/residuals/age/calibration identity on status topics. Do not implement Studio live angle display or visualizer start button (Phase 19). Do not reintroduce custom `relative_orientation_angle_deg` as the product angle.

</domain>

<decisions>
## Implementation Decisions

### Product semantics (LOCKED)
- **D-18-01 (Official IK only):** Product joint angles come only from an `OrientationIkSolver` that performs OpenSim orientation IK (or a test Fake injected in unit tests). `relative_orientation_angle_deg` / `/opensim/joint_angle` remain debug-only (`publish_joint_angle_enabled` default OFF) and MUST NOT populate `/opensim/joint_states`.
- **D-18-02 (Runtime host):** Prefer a working OpenSim **Python** path inside the existing `opensim_bridge` process on WSL OpenSim **4.5.2** (micromamba). Research preferred a separate C++ OpenSense package — **deferred beyond this milestone**. Do not start `rehab_robotics_opensim` C++ scaffolding in Phase 18.
- **D-18-03 (Fail-closed when APIs missing):** If Python bindings lack usable InverseKinematics / orientation-reference APIs, production uses `UnavailableOrientationIkSolver` (no valid solution, reason codes). Never fall back to custom relative-quat degrees. Fake solver is for deterministic tests only.
- **D-18-04 (Output topic):** Locked: `sensor_msgs/JointState` on `/opensim/joint_states` (D-16-03). Positions in radians. Stamp = paired observation / source measurement time (not wall publish time). Do not republish stale solutions with a fresh stamp.
- **D-18-05 (Hard gate):** Publish JointState only when `may_publish_joint_states(calibration_state)` is true **and** the solver reports `solution_valid`. Clear cal / UNCALIBRATED / FAILED / invalid solution clears `_ik_solution` and stops publication (extends D-17-03 / D-16-04).
- **D-18-06 (Status surface):** Publish `/opensim/ik_status` as `std_msgs/String` JSON (rosbridge-friendly, same pattern as calibration_status). Schema id `rehab.opensim_ik_status.1`. Typed `rehab_robotics_interfaces/msg/IkStatus` is deferred. Also embed an `ik` object in `/opensim/status`. Publish a lightweight `/diagnostics` heartbeat (prefer `diagnostic_msgs/DiagnosticArray` if dependency added; otherwise String JSON with the same key fields).
- **D-18-07 (Calibration offsets):** When CALIBRATED, apply `CalibrationArtifact` master/slave mounting offsets before feeding orientations into the solver (OpenSense-style sensor-to-model correction). Clearing calibration must reset solver assemble state.
- **D-18-08 (Coordinate projection):** Default published joint name `knee_angle_r` (launch/node parameter `ik_joint_names` list, default single entry). Map 1:1 to OpenSim coordinate path(s) configured via `ik_coordinate_paths` (default matching name). Empty velocity/effort arrays unless genuinely computed.
- **D-18-09 (Pairing):** Solve only when both master and slave are `live` with finite orientations. Prefer min(source_stamp) of the pair as JointState stamp when both stamps exist; if either stamp missing, do not publish a fabricated wall-time stamp — mark solution invalid with reason `missing_source_timestamp` (fail closed on stamp integrity for product JointState).

### Claude's Discretion
- Exact residual threshold for `solution_valid` (start conservative; surface residual even when valid).
- Whether to call `assemble()` once then `track()` when APIs allow, or re-`assemble()` per sample on 4.5.2 if BufferedOrientationsReference is absent.
- Minimal synthetic `.osim` fixture construction for skipUnless OpenSim integration tests.
- Whether `/diagnostics` uses DiagnosticArray vs String — prefer DiagnosticArray when adding `diagnostic_msgs` is low-friction.

</decisions>

<canonical_refs>
## Canonical References

- `.planning/REQUIREMENTS.md` (IK-05, IK-06, IK-07)
- `.planning/ROADMAP.md` Phase 18
- `.planning/research/SUMMARY.md` — Phase 18 (C++ preferred; overridden by D-18-02 for this milestone)
- `docs/opensim-ik-contracts.md`
- `backend/rehab_robotics_bridge/opensim/ik_contracts.py`
- `backend/rehab_robotics_bridge/opensim/calibration.py`
- `backend/rehab_robotics_bridge/opensim_node.py` — `_ik_solution` seam + `_maybe_publish_joint_states`
- `backend/rehab_robotics_bridge/opensim_adapter.py` — quaternion boundary only (not product IK)
- Phase 17 VERIFICATION — gate ready; solver intentionally absent

</canonical_refs>

<code_context>
## Existing Code Insights

- Phase 17 left `_ik_solution = None` always; `_maybe_publish_joint_states` already gates on CALIBRATED + non-None solution dict with `name`/`position` lists, but does not yet set header.stamp.
- CalibrationController provides `CalibrationArtifact` with `calibration_id`, `master_xyzw`, `slave_xyzw`.
- Visualizer adapter already imports OpenSim Python when available; IK solver should follow the same optional-import pattern (`import_module("opensim")`) without coupling IK to the visualizer.
- No `.osim` product model is checked into the repo yet — runtime requires `model_path`; tests may synthesize a minimal pin-joint model when `opensim` is installed.

</code_context>

<specifics>
## Specific Ideas

User directive for this milestone: Prefer working OpenSim Python API on the existing WSL `opensim_bridge` if InverseKinematics / orientation tracking APIs exist in 4.5.2; otherwise thin adapter + Fake for tests + real path when bindings allow. Never productize custom relative-quat angle.

</specifics>

<deferred>
## Deferred Ideas

- Dedicated C++ `rehab_robotics_opensim` package with OpenSim 4.6 `BufferedOrientationsReference` (research recommendation)
- Typed `IkStatus.msg` in `rehab_robotics_interfaces`
- Studio subscription / live knee display from JointState (Phase 19)
- Visualizer toolbar button (Phase 19)
- Clinical / external-reference validation
- Cross-session versioned calibration bound to model hashes
- Full message_filters ApproximateTime sync queues (use live dual-latest pair with stamp integrity for v1.5)

</deferred>
