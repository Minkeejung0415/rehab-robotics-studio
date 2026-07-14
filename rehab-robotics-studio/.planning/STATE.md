---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: ROS2 Backend + ESP32 Hardware Integration
status: in_progress
stopped_at: Phase 06 scaffold complete — needs build verification
last_updated: "2026-07-14"
last_activity: 2026-07-14
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State — v2.0

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-07-14)

**Core value:** Real IMU data from wearable ESP32 nodes flows into the visual programming canvas in real-time.
**Current focus:** Phase 06 — verify `colcon build` and `docker compose up`

## Current Position

Phase: 06 (in progress — scaffolded, needs verification)
Plan: none yet
Status: Code scaffold committed; build not yet verified on target OS

Progress: [__________] 0%

## Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 06 | Package Scaffold & Dev Env | Scaffolded — build unverified |
| 07 | ESP32 Bridge Node | Scaffolded — hardware test pending |
| 08 | Multi-Node Support | Scaffolded — hardware test pending |
| 09 | rosbridge WebSocket | Planned |
| 10 | GUI DataSource | Planned |

## Accumulated Context

### Architecture Decisions

- [v2.0 init]: Plugin repo firmware (step_node v1.8) is untouched — we consume its TCP stream
- [v2.0 init]: We do NOT run Open Ephys software — our backend replaces it as the TCP consumer
- [v2.0 init]: ROS2 Humble/Iron chosen for multi-node pipeline support and future IK extensibility
- [v2.0 init]: backend/ at repo root alongside rehab-robotics-studio/ — co-located, separate concerns
- [v2.0 init]: Docker optional — native ROS2 install is the primary path; Docker kept as convenience only
- [v2.0 init]: ROS2 used for pub/sub transport only (topics/nodes), NOT for container orchestration
- [v2.0 init]: VITE_BACKEND env var switches signalBus between mock and live — one-line change

### ESP32 Protocol Facts

- 14-channel OE binary over TCP :5000 (REDPITAYA/START handshake)
- ch[0-2]  accel X/Y/Z   int16, ÷16384 × 9.80665 m/s² (±2g default)
- ch[3-5]  gyro  X/Y/Z   int16, ÷131.072 × π/180 rad/s (±250dps default)
- ch[6-8]  mag   X/Y/Z   int16 (0 if no magnetometer)
- ch[9-12] quat  W/X/Y/Z Q15 int16 → ÷32767 (VQF-fused)
- ch[13]   DIO            packed int16
- All nodes share STEP_ESP32 WiFi AP (pass: step1234); host PC joins same AP
- Master fixed IP 192.168.4.1:5000; slaves get DHCP IPs 192.168.4.2, .3, ...
- Each node runs its own TCP :5000; aggregator connects to each independently
- USB fallback: Plugin repo serial_tcp_bridge.py → 127.0.0.1:5000 (single node)

### Scaffolded Files

| File | Status |
|------|--------|
| `backend/package.xml` | Written — needs colcon verify |
| `backend/setup.py` | Written — needs colcon verify |
| `backend/docker-compose.yml` | Written — needs docker test |
| `backend/rehab_robotics_bridge/esp32_bridge_node.py` | Written — needs hardware test |
| `backend/rehab_robotics_bridge/imu_aggregator_node.py` | Written — needs hardware test |
| `backend/config/nodes.yaml` | Written |
| `backend/launch/rehab_robotics.launch.py` | Written |

## Deferred Items

| Category | Item | Deferred At |
|----------|------|-------------|
| v3 | OpenSim IK node (subscribe to /imu, publish joint angles) | v2.0 init |
| v3 | Recording pipeline integration | v2.0 init |
| v1.0 | Undo/redo, copy/paste, multi-select | v1.0 init |

## Session Continuity

Last session: 2026-07-14
Stopped at: v2.0 milestone created, Phase 06 scaffold in place
Next: Run `/gsd-plan-phase 06` to plan build verification for the scaffolded package
