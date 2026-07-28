---
status: resolved
trigger: "Replace the primitive OpenSim demo with a skeleton, diagnose REC ERR already_recording, and fix minimal master-sensor influence on the knee angle"
created: 2026-07-28
updated: 2026-07-28
---

## Symptoms

- Expected: the native OpenSim window displays an anatomical skeleton rather than two cylinders and oversized sensor labels.
- Actual: the window displays only primitive femur/tibia cylinders plus large MASTER/SLAVE triad labels.
- Expected: pressing Record once starts one recording session without an error.
- Actual: the GUI reports `REC ERR code=already_recording ... retryable=false detail=active`.
- Expected: rotating either the master (femur) or slave (tibia) sensor changes the relative knee angle consistently.
- Actual: moving the master has minimal or no angle impact compared with moving the slave.
- Reproduction: run the wireless stack, open the visualizer, calibrate, move each sensor independently, and press Record.

## Current Focus

- hypothesis: confirmed root causes fixed.
- test: native OpenSim model/IK tests, isolated 100 Hz ROS launch, recording contract tests, and frontend state tests.
- expecting: anatomical bone meshes render; master/slave rotations produce equal-and-opposite knee deltas; repeated Record is accepted and health drives the button state.
- next_action: user performs the final STEP_ESP32 hardware movement and SD-recording check.

## Evidence

- timestamp: 2026-07-28
  observation: `create_opensim_demo_model.py` used primitive Cylinder geometry and welded femur directly to ground.
- timestamp: 2026-07-28
  observation: synthetic native IK on the old welded model reproduced negligible master influence because no model coordinate could rotate the femur.
- timestamp: 2026-07-28
  observation: installed OpenSim 4.5.2 OpenSense assets provide Rajagopal anatomical pelvis, femur, tibia, fibula, and patella geometry.
- timestamp: 2026-07-28
  observation: the new pelvis + 3-DOF hip + knee model returned +0.523599 rad for slave +30 degrees and -0.523599 rad for master +30 degrees.
- timestamp: 2026-07-28
  observation: firmware `already_recording` means a valid session was active; the GUI had not synchronized its button state from pair health.
- timestamp: 2026-07-28
  observation: isolated ROS test sustained 1,791 updates per sensor at 100 Hz, opened the anatomical visualizer, calibrated with 303 samples, and published JointState.

## Eliminated

- hypothesis: weak master response is caused by ESP32 packet loss or lower master update rate.
  reason: both roles were live at the same rate and the asymmetry reproduced without hardware on the welded model.
- hypothesis: `already_recording` indicates SD-card corruption.
  reason: firmware returned `retryable=false detail=active` with a valid active session ID.

## Resolution

- root_cause: the primitive model welded femur to ground, so IK could only move tibia; recording state was local UI state rather than authoritative hardware health, causing duplicate Start.
- fix: use Rajagopal anatomical lower-limb meshes with a 3-DOF hip and knee, register/copy geometry assets at setup, shrink sensor labels, make repeated recording commands idempotent, and synchronize the GUI recording indicator from master health.
- verification: native sensitivity passed; OpenSim 91/91, ESP control 15/15, and frontend 56/56 tests passed; production build and isolated 100 Hz visualizer/calibration/JointState test passed.
- files_changed: scripts/create_opensim_demo_model.py, scripts/setup_opensim_live_link_wsl.sh, scripts/run_opensim_live_link_wsl.sh, examples/opensim_quaternion_demo.osim, backend/rehab_robotics_bridge/opensim_adapter.py, backend/rehab_robotics_bridge/opensim/opensim_orientation_ik.py, backend/rehab_robotics_bridge/esp32_bridge_node.py, backend/test/test_opensim_orientation_ik_opensim.py, backend/test/test_esp32_controls.py, rehab-robotics-studio/src/state/systemStore.ts, rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts
