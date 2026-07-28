---
status: resolved
trigger: "OpenSim visualizer opens in the hardware-free test but fails with the live 100 Hz ESP pair"
created: 2026-07-28
updated: 2026-07-28
---

## Symptoms

- Expected: native OpenSim window stays open while both ESP devices stream near 100 Hz.
- Actual: both devices remain pair-online, OpenSim sensors alternate between `mapping_error` and `stale`, and the visualizer reports `visualizer_open_failed`.
- Reproduction: start the wireless stack, allow live IMU data to flow, then press `Open visualizer`.

## Current Focus

- hypothesis: Conda freeglut crashes under WSLg during sustained rendering, and the resulting display failure incorrectly rejects otherwise valid IMU samples.
- test: link the visualizer to Ubuntu system freeglut, use Simbody Sampling mode, and run 1,400 dual-sensor updates at 200 calls/second.
- expecting: no native crash, visualizer remains available, and display failure never blocks sensor freshness or IK.
- next_action: resolved; run the manual STEP_ESP32 verification flow.

## Evidence

- timestamp: 2026-07-28
  observation: live log transitions from `live` to `mapping_error: adapter_update_failed`, then visualizer becomes `visualizer_update_failed`.
- timestamp: 2026-07-28
  observation: standalone reproduction fails with `Broken pipe` after sustained `show()` calls.
- timestamp: 2026-07-28
  observation: WSL kernel log records SIGSEGV inside Conda `libglut.so.3.11.1`.
- timestamp: 2026-07-28
  observation: the same 1,400-update test succeeds with Ubuntu `/lib/x86_64-linux-gnu/libglut.so.3` and Simbody Sampling mode.
- timestamp: 2026-07-28
  observation: WSLg's D3D12 OpenGL path also crashed Ubuntu freeglut intermittently; `LIBGL_ALWAYS_SOFTWARE=1` made repeated service opens stable.
- timestamp: 2026-07-28
  observation: isolated ROS end-to-end test sustained more than 7,700 updates per sensor at 100 Hz, completed calibration with 301 samples, reported valid IK, and published `knee_angle_r` on `/opensim/joint_states`.
- timestamp: 2026-07-28
  observation: after deliberately terminating the native visualizer, resumed 100 Hz IMU traffic recreated it automatically; both sensors stayed live past 3,500 updates and `Open visualizer` succeeded.

## Eliminated

- hypothesis: STEP_ESP32 Wi-Fi or missing WSLg environment caused the failure.
  reason: the OpenSim process had valid `DISPLAY`, `WAYLAND_DISPLAY`, `PATH`, and library paths; the crash reproduces without ESP hardware.

## Resolution

- root_cause: Simbody's native freeglut process crashed in WSLg's OpenGL path. The ROS node then incorrectly converted a visualizer-only failure into `mapping_error`, which stopped sensor freshness and IK even though the ESP data remained valid.
- fix: build the OpenSim-compatible Simbody visualizer against Ubuntu system OpenGL/freeglut, force WSL software rendering, use Simbody Sampling mode at 30 FPS, keep visualizer failures independent from valid IMU acquisition and IK, and recreate a crashed native adapter when streaming resumes or the user retries Open.
- verification: 1,400-call native stress passed; 88 OpenSim tests passed; isolated 100 Hz ROS test kept both sensors live, opened the visualizer, calibrated, produced valid IK, published joint states, and recovered after deliberate native-process termination.
- files_changed: backend/rehab_robotics_bridge/opensim_adapter.py, backend/rehab_robotics_bridge/opensim_node.py, backend/test/test_opensim_adapter.py, backend/test/test_opensim_node.py, scripts/install_simbody_visualizer_wsl.sh, scripts/run_opensim_live_link_wsl.sh
