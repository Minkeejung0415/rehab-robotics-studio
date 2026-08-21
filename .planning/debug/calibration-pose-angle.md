---
status: awaiting_human_verify
trigger: "Calibrate folds the OpenSim skeleton and the GUI angle remains unavailable"
created: "2026-08-21"
updated: "2026-08-21"
---

# Calibration Pose and Angle

## Symptoms

- expected: With the two mapped ESPs held in the instructed standing knees-extended pose, Calibrate should establish a neutral, anatomically straight OpenSim pose; subsequent movement should produce a live knee angle and matching 3D motion.
- actual: Pressing Calibrate folds the skeleton as shown in the user screenshot, and the GUI continues to show no angle.
- errors: No textual error was reported; the visualizer shows an implausible folded pose.
- timeline: Reproduced after the prior live fleet and mapped-IK fixes.
- reproduction: Start the wireless GUI with the paired ESPs, apply the femur/tibia mapping, press Calibrate while holding the reference pose, then inspect the visualizer and angle panel.

## Current Focus

reasoning_checkpoint:
  hypothesis: "The mapped N-sensor path saves calibration as an artifact but neither passes it into nor applies it in `solve_n`; meanwhile `/opensim/status` exposes the unrelated legacy calibration, so the frontend rejects the N-IK JointState despite it being valid."
  confirming_evidence:
    - "Live ROS reports N calibration artifact `calibration_76e65386_rev46.json`, valid N-IK, and knee_angle_r=3.176 rad, while `/opensim/status.calibration` is `UNCALIBRATED`."
    - "`_solve_and_publish_ik_n` calls `solve_n` without calibration and `solve_n` rebuilds an orientation reference directly from raw inputs."
    - "`deriveLiveKneeAngle` requires `openSimStatus.calibration.state === 'CALIBRATED'` and matching non-empty calibration IDs."
  falsification_test: "If passing a captured N artifact yields the same raw orientation table at reference pose, or if the public status remains legacy-un calibrated after the N status is merged, this hypothesis is wrong/incomplete."
  fix_rationale: "Apply q_current × conjugate(q_reference) per mapped frame before building the N-sensor OpenSim orientation table, propagate the N calibration identity to IK/status, and make the public status report that authoritative calibration. This makes the reference pose neutral and lets the angle gate accept the matching published joint state."
  blind_spots: "Physical sensor mounting may still require an anatomical axis transform beyond neutral-reference correction; this change must be verified on the live hardware after rebuild."

reasoning_checkpoint:
  hypothesis: "After every successful pose update the visualizer adapter changes its state to `ready`; the frontend parser only accepts `waiting|opening|open|unavailable|failed`, rejects the entire status payload, and therefore makes the angle gate see no calibration."
  confirming_evidence:
    - "The live backend status has valid calibrated and IK fields, but its visualization state is `ready`."
    - "The browser receives pair health and IK status but HealthPanel sees no OpenSim status."
    - "`parseOpenSimStatus` returns null for visualization state `ready`, before returning calibration/sensor data."
  falsification_test: "If allowing `ready` or preserving `open` does not produce a browser OpenSim status and finite knee angle while the same ROS payload is present, another WebSocket transport issue remains."
  fix_rationale: "Preserve `open` while pose updates occur and accept `ready` as a valid pre-open adapter state, so a harmless visualization status cannot invalidate the entire OpenSim health/calibration contract."
  blind_spots: "This only restores the UI status gate; it does not substitute for physical verification that the rendered skeleton moves after sensor movement."

next_action: User should refresh the GUI and perform the physical movement check after Calibrate; report any remaining mismatch between limb movement and the visualizer.

## Evidence

- timestamp: "2026-08-21"
  checked: User-provided visualizer and GUI screenshots
  found: The skeleton folds immediately after Calibrate while the UI reports a calibrated state but "Invalid - No solution yet" and no knee angle.
  implication: Calibration completion is not sufficient evidence of valid IK; calibration pose and solver/display paths must be independently checked.

- timestamp: "2026-08-21"
  checked: N-sensor calibration and IK implementation
  found: `_on_calibration_capture_n` stores raw per-device reference quaternions in `_n_calib_artifact`, but `_solve_and_publish_ik_n` calls `solve_n(inputs=..., source_timestamp_ns=..., input_age_s=..., joint_names=...)` without that artifact; `solve_n` accepts `calibration` but never reads it.
  implication: The N-sensor calibration capture currently has no mathematical effect on IK or the visualizer, directly explaining a non-neutral calibrated pose.

- timestamp: "2026-08-21"
  checked: Live ROS N-IK status, metadata, joint states, and OpenSim status
  found: Current N-IK metadata is `solver_status=ok`, `/opensim/joint_states` publishes `knee_angle_r=3.176 rad` (an implausible near-180 degree pose), while `/opensim/status.calibration` remains legacy `UNCALIBRATED` with `may_publish_joint_states=false`; N-calibration is stored separately as `calibration_76e65386_rev46.json`.
  implication: The solver emits a joint angle but the visible health contract still carries legacy calibration state; the UI's knee-angle gate can reject the valid N-IK joint state. The numerical folded pose is independently consistent with the inert N-calibration artifact.

- timestamp: "2026-08-21"
  checked: Legacy and N-sensor solve ownership plus targeted regression tests
  found: Legacy `/esp32/master/imu` callbacks continue to invoke `_solve_and_publish_ik` after mapping, which writes `_last_ik_solution` from an uncalibrated path; focused tests and the full backend suite pass after making mapped N-sensor IK authoritative, applying persisted reference corrections, and exposing its calibration identity through the public status contract.
  implication: The fixes are contractually validated; the installed WSL OpenSim overlay now needs rebuilding for hardware verification.

- timestamp: "2026-08-21"
  checked: Rebuilt live hardware stack and browser E2E after GUI-triggered calibration
  found: Live ROS now reports CALIBRATED, matching calibration IDs, a valid N-IK solution, and a neutral 0.0008-rad knee state. However the browser's HealthPanel still receives no OpenSim status (Waiting/UNCALIBRATED) while it receives pair health and valid IK status.
  implication: The pose correction works in the physical backend, but a separate frontend transport/parser defect still prevents the displayed angle and visualizer health from updating.

- timestamp: "2026-08-21"
  checked: Live `/opensim/status` payload against `parseOpenSimStatus`
  found: The rebuilt adapter reports `visualization.state=ready` after `update_pose`; the parser accepts no `ready` value and discards the entire otherwise valid payload, including CALIBRATED and its identity.
  implication: This directly explains the GUI's Waiting/UNCALIBRATED state despite valid ROS IK and joint data.

- timestamp: "2026-08-21"
  checked: Rebuilt iPhone hardware stack, GUI-triggered mapping/apply/calibration/open-visualizer E2E, and final backend suite
  found: GUI live E2E passes with explicit assertions for CALIBRATED, valid IK, finite displayed knee angle, and an opened visualizer. The physical ROS contract after that run reports matching `calibration_76e65386_rev50.json` IDs, `solution_valid=true`, a neutral `knee_angle_r=0.00045 rad`, and visualizer state `open`. Full backend suite passes: 413 passed, 11 skipped, 289 subtests passed.
  implication: The reported folded-reference and missing-angle defects are fixed in the live stack; only operator movement verification remains.

## Eliminated

## Resolution

root_cause: "N-sensor calibration was persisted but unused by `solve_n`, and the legacy uncalibrated pair solver raced the mapped N-sensor result. The public status reported the legacy calibration, causing the UI's calibrated-IK gate to hide a valid mapped angle."
fix: "Apply per-frame current×conjugate(reference) N-sensor offsets before OpenSim IK, pass the N artifact into solve_n, publish its calibration identity/status, and suppress the legacy solver whenever a mapping is active."
verification: "Physical stack rebuilt and calibrated; live ROS reports a neutral 0.00045-rad knee pose, matching calibrated IDs, valid IK, and visualizer open. GUI E2E asserted the finite displayed angle after the real GUI Calibrate action. Frontend: 163 passed/build passed. Backend: 413 passed, 11 skipped, 289 subtests passed."
files_changed:
  - backend/rehab_robotics_bridge/opensim/n_sensor_calibration.py
  - backend/rehab_robotics_bridge/opensim/opensim_orientation_ik.py
  - backend/rehab_robotics_bridge/opensim_node.py
  - backend/test/test_n_sensor_calibration.py
