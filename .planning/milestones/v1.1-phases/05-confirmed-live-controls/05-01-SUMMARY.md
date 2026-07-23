---
phase: 05-confirmed-live-controls
plan: 01
status: complete
requirements: [CTRL-01, CTRL-02, CTRL-03]
---

# Plan 05-01 Summary

Implemented a typed ROS-to-ESP32 live-control contract for paired sample rate,
effective rate, filter, accelerometer range, and gyroscope range.

- `esp32_bridge_node.py` validates all supported parameter values before sending
  hardware traffic and updates cached state only after a matching acknowledgement.
- The USB serial bridge now recognizes `FILTER` and `CFG` control clients, sends
  deterministic acknowledgements for valid control syntax, and always resumes
  the binary acquisition stream afterward.
- Added focused command-mapping and rejection tests in
  `backend/test/test_esp32_controls.py`.

Verification completed on 2026-07-16:

- `python -m py_compile` passed for the backend node and USB bridge.
- `python -m unittest backend.test.test_esp32_controls -v` passed (2 tests).
- Real USB/ROS master test acknowledged filter on/off, accel 8 g, gyro 500 dps,
  effective rate 137 Hz, and restored paired rate 100 Hz.
- A live `/esp/raw/master` frame arrived after the commands, confirming streaming resumed.
