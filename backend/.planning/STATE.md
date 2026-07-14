---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: ESP32 IMU to ROS2 to GUI Live Stream
status: planning
last_updated: "2026-07-13"
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State: Rehab Robotics ROS2 Backend

## Current Position

Phase: — (not started)
Status: Planning complete — ready to begin Phase 1

## Progress

| Phase | Name | Status |
|-------|------|--------|
| 1 | Package Scaffold & Dev Environment | Planned |
| 2 | ESP32 Bridge Node | Planned |
| 3 | Multi-Node Support | Planned |
| 4 | rosbridge WebSocket | Planned |
| 5 | GUI DataSource | Planned |

Progress: [__________] 0%

## Key Facts

- ESP32 firmware (step_node v1.8): 14-channel Open Ephys binary over TCP :5000
  - ch[0-2]  accel X/Y/Z  (int16, ±2g default → ÷16384 × 9.80665 m/s²)
  - ch[3-5]  gyro  X/Y/Z  (int16, ±250dps default → ÷131.072 × π/180 rad/s)
  - ch[6-8]  mag   X/Y/Z  (int16, 0 if no mag)
  - ch[9-12] quat  W/X/Y/Z (Q15 int16 → ÷32767, VQF-fused)
  - ch[13]   DIO   (packed int16)
- WiFi: join STEP_ESP32 (pass: step1234), ESP32 master at 192.168.4.1:5000
- USB: run Plugin repo serial_tcp_bridge.py → connects to 127.0.0.1:5000
- We do NOT run Open Ephys software — our backend replaces it
- GUI interface: `rehab-robotics-studio/src/data/DataSource.ts`
- rosbridge WebSocket default: ws://localhost:9090
- Frame type GUI expects: `{ t, force: ForceData, emg: EmgData, imu: ImuData, motor: MotorState }`
- IMU data shape: `{ quat: [w,x,y,z], accel: [x,y,z], gyro: [x,y,z], t }`

## Session Continuity

Last session: 2026-07-13
Stopped at: Project initialized — Phase 1 ready to plan
Resume: Run `/gsd-plan-phase 1` in `backend/` directory
