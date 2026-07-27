# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## angle-display-not-updating — Connected ESP devices produced a frozen GUI angle
- **Date:** 2026-07-27
- **Error patterns:** ESP connected, displayed angle unchanged, frozen angle, missing sensor_config, raw telemetry rejected
- **Root cause:** The wireless launcher used a stale WSL ROS bridge build that emitted `oe_esp32.raw.v1` messages without the required `sensor_config`. The current GUI rejected those messages before caching/emitting frames, while independent pair-health messages still reported both ESPs connected.
- **Fix:** Added handshake-order regression coverage and rebuilt the launcher's `/home/justi/.rehab-install-v12` package from the current bridge implementation, which confirms or falls back sensor ranges before START and includes canonical `sensor_config` in every raw message.
- **Files changed:** backend/test/test_esp32_controls.py, rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts
---
