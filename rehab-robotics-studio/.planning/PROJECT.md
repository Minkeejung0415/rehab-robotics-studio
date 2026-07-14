# Rehab Robotics Studio

## What This Is

A LabVIEW-style visual programming environment for rehabilitation robotics, built with React + TypeScript + Zustand. Users wire together sensor sources, signal processing blocks, biomechanics models, motor controllers, and indicators on a node-graph canvas.

**v1.0** (complete) — fully interactive frontend running on mock/synthetic data.
**v2.0** (active) — real hardware backend: ESP32 IMU nodes → ROS2 → WebSocket → GUI live stream.

## Core Value

Real biomechanical data from wearable ESP32 IMU nodes flows into the visual programming canvas in real-time — researchers wire signal-processing blocks and see joint angles, forces, and motor state driven by actual hardware, not synthetic signals.

## Milestone History

| Milestone | Goal | Status |
|-----------|------|--------|
| v1.0 | Interactive frontend (mock data) | Complete 2026-07-13 |
| v2.0 | ROS2 backend + ESP32 hardware integration | Active |

## Requirements

### Validated (v1.0)

- ✓ Block diagram canvas with draggable nodes, zoom, context menus
- ✓ Wired connections between blocks (visual, interactive)
- ✓ Block palette with search, drag-drop, custom block loading (block.json)
- ✓ Properties panel with editable parameters and block rename
- ✓ Live dashboard (Force, EMG, Motor/Joint panels) — Front Panel tab
- ✓ System log with clear button
- ✓ Runtime state machine (Run/Pause/Stop/E-Stop/Reset)
- ✓ Mock data source with graph executor and signal bus
- ✓ Save/Load project as JSON
- ✓ Graph validation
- ✓ Status strip with system indicators
- ✓ Tabbed workspace (Block Diagram / Front Panel)

### Active (v2.0)

- [ ] ROS2 Python package (`backend/rehab_robotics_bridge`) builds and runs
- [ ] ESP32 bridge node connects to 192.168.4.1:5000, publishes sensor_msgs/Imu
- [ ] Multi-node support: master + up to 3 slaves via nodes.yaml config
- [ ] rosbridge WebSocket on :9090 — browser can subscribe to ROS2 topics
- [ ] `RosBridgeDataSource.ts` implements `DataSource` interface using roslibjs
- [ ] Switching `VITE_BACKEND=ros` replaces mock with live ESP32 stream
- [ ] End-to-end: ESP32 IMU rotation visible in GUI sensor block in real-time

### Out of Scope

- OpenSim IK integration — separate Python pipeline (Plugin repo handles this)
- Red Pitaya hardware — v1.0 Plugin milestone covered that
- Multi-user collaboration — not needed
- Undo/redo, copy/paste, multi-select — deferred beyond v2.0

## Architecture

```
ESP32 master (step_node v1.8)           backend/                    rehab-robotics-studio/
  STEP_ESP32 WiFi AP                    rehab_robotics_bridge       Rehab Robotics Studio GUI
  192.168.4.1:5000 TCP                                              (React + Zustand)
  14-ch OE binary
    ch[0-2]  accel                      esp32_bridge_node   →  /esp32/master/imu
    ch[3-5]  gyro            →  ROS2    imu_aggregator_node →  /esp32/slave_N/imu
    ch[6-8]  mag                        rosbridge :9090    →   RosBridgeDataSource.ts
    ch[9-12] quat (VQF)                                    →   signalBus → React
    ch[13]   DIO

ESP32 slaves (ESP-NOW → master)
  → aggregated through master TCP stream
```

## Context

- Frontend: React 18.3 + TypeScript + Vite 5 + Zustand 4.5
- Backend: Python 3.10+ ROS2 Humble/Iron, rclpy, rosbridge_suite
- No new frontend dependencies; backend has its own package.xml
- DataSource interface: `src/data/DataSource.ts` — swap MockDataSource → RosBridgeDataSource
- Frame type: `{ t, force: ForceData, emg: EmgData, imu: ImuData, motor: MotorState }`
- imu: `{ quat: [w,x,y,z], accel: [x,y,z], gyro: [x,y,z], t }`

## Constraints

- **Frontend**: No new npm dependencies
- **Backend**: ROS2 Humble/Iron, Python 3.10+, Docker Compose fallback
- **ESP32**: Firmware untouched — use validated step_node v1.8 from Plugin repo
- **Protocol**: 14-channel OE binary over TCP :5000 (handshake: REDPITAYA/START)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Mock-only v1.0 | Needed interactable UI before hardware | Validated — frontend complete |
| Use existing store methods | removeNode, wiring etc. already implemented | Validated Phase 01 |
| DataSource interface abstraction | Allows swapping mock ↔ real without UI changes | Architecture from init |
| ROS2 as backend middleware | Enables multi-node pipelines, future IK node | v2.0 decision |
| Plugin repo firmware untouched | step_node v1.8 validated — no firmware changes | v2.0 decision |
| backend/ at repo root | Keeps frontend and backend co-located, separate concerns | v2.0 decision |

## Evolution

**After each phase transition**: Update Validated/Active/Out of Scope, add decisions.
**After each milestone**: Full review, Core Value check, archive to milestones/.

---
*Last updated: 2026-07-14 — v2.0 milestone started*
