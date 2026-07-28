---
status: resolved
trigger: "OpenSim visualizer initialization failed and IK reported opensim_ik_api_unavailable"
created: 2026-07-28
updated: 2026-07-28
---

## Symptoms

- Expected: native OpenSim window opens and orientation IK publishes a valid knee coordinate after calibration.
- Actual: visualizer status reported `visualizer_initialization_failed`; IK reported `opensim_ik_api_unavailable`.
- Reproduction: launch the Phase 19 stack and inspect `/opensim/status` or open the Front Panel visualizer.

## Current Focus

- hypothesis: OpenSim 4.5.2 lacks the external visualizer binary, and its SWIG quaternion row API differs from the adapter assumptions.
- test: run the hardware-free publisher, open the visualizer service, calibrate, and inspect `/opensim/status`, `/opensim/ik_status`, and `/opensim/joint_states`.
- expecting: visualizer `available=true/state=open`; IK backend `OpenSimOrientationIkSolver`, `solution_valid=true`, reason `ok`.
- next_action: resolved; perform the visual confirmation on the next STEP_ESP32 run.

## Evidence

- timestamp: 2026-07-28
  observation: `simbody-visualizer` was absent while OpenSim shipped Simbody 3.8 libraries and headers.
- timestamp: 2026-07-28
  observation: OpenSim 4.5.2 rejected whole-Quaternion assignment to `RowVectorQuaternion`; component-wise proxy assignment constructs the table.
- timestamp: 2026-07-28
  observation: the old demo model contained two ground frames but no `knee_angle_r` coordinate.
- timestamp: 2026-07-28
  observation: hardware-free ROS status reached visualizer `state=open` and IK `solution_valid=true`.

## Eliminated

- hypothesis: ESP disconnection caused the OpenSim failures.
  reason: both failures reproduce and resolve with the hardware-free publisher.

## Resolution

- root_cause: The OpenSim Conda package did not include the external Simbody visualizer executable. Separately, OpenSim 4.5.2 requires component-wise SWIG quaternion row writes, and the demo model had no articulated knee coordinate.
- fix: Built a matching Simbody 3.8 visualizer in the user environment; added it to the launch path; corrected quaternion table construction; added a real femur/tibia demo model with `knee_angle_r`.
- verification: 88 OpenSim tests passed; native visualizer smoke passed; ROS status reached `available=true/state=open`; calibrated IK reached `solution_valid=true/reason=ok`; 2,000 solves completed with zero invalid results and zero angle error.
- files_changed: backend/rehab_robotics_bridge/opensim/opensim_orientation_ik.py, backend/test/test_opensim_orientation_ik_opensim.py, scripts/create_opensim_demo_model.py, scripts/install_simbody_visualizer_wsl.sh, scripts/setup_opensim_live_link_wsl.sh, scripts/run_opensim_live_link_wsl.sh, examples/opensim_quaternion_demo.osim, docs/opensim-quaternion-live-link.md, docs/stepesp-wireless-setup.md
