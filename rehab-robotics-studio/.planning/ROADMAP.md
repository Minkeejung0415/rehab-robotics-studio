# Roadmap: Rehab Robotics Studio — v2.0

**Milestone:** v2.0 — ROS2 Backend + ESP32 Hardware Integration
**Created:** 2026-07-14
**Phases:** 5
**Requirement coverage:** 17/17 v2.0 requirements mapped

> v1.0 roadmap archived at: `.planning/milestones/v1.0/ROADMAP.md`

## Overview

| # | Phase | Goal | Requirements | Status |
|---|-------|------|--------------|--------|
| 06 | Package Scaffold & Dev Env | Runnable ROS2 package + Docker zero-install path | PKG-01, PKG-02, OPS-01, OPS-02 | Scaffolded |
| 07 | ESP32 Bridge Node | TCP → sensor_msgs/Imu for master node | BRIDGE-01–05 | Scaffolded |
| 08 | Multi-Node Support | Master + slave fan-out via nodes.yaml | MULTI-01–03 | Scaffolded |
| 09 | rosbridge WebSocket | Browser can subscribe to ROS2 topics | WS-01–03 | Planned |
| 10 | GUI DataSource | RosBridgeDataSource.ts + VITE_BACKEND switch | GUI-01–04, PERF-01 | Planned |

> **Scaffolded** = code skeleton exists in `backend/`, needs build verification and testing.
> **Planned** = not yet started.

---

## Phase Details

### Phase 06: Package Scaffold & Dev Environment

**Goal:** ROS2 package builds natively and the launch file starts all nodes.

**Success Criteria:**
1. `cd backend && colcon build --packages-select rehab_robotics_bridge` exits 0
2. `source install/setup.bash && ros2 run rehab_robotics_bridge esp32_bridge_node` starts without import errors
3. `ros2 launch rehab_robotics_bridge rehab_robotics.launch.py` starts aggregator + rosbridge, port 9090 open
4. `ros2 topic list` shows `/esp32/master/imu` and `/esp32/master/raw`

**Setup (once):**
```bash
sudo apt install ros-humble-rosbridge-suite  # or ros-iron-rosbridge-suite
pip3 install pyyaml
```

**Key files:** `backend/package.xml`, `backend/setup.py`, `backend/launch/rehab_robotics.launch.py`

> Docker (`backend/docker-compose.yml`) remains available as an optional convenience but is not the primary path.

---

### Phase 07: ESP32 Bridge Node

**Goal:** `esp32_bridge_node` connects to the ESP32, parses 14-ch frames, and publishes live IMU topics.

**Success Criteria:**
1. Node connects to 192.168.4.1:5000 (WiFi) or 127.0.0.1:5000 (USB bridge) and logs "connected"
2. REDPITAYA/START handshake completes — firmware responds with STARTED + SENSORS
3. `ros2 topic echo /esp32/master/imu` shows quaternion values changing in real time
4. `ros2 topic hz /esp32/master/imu` reports ~100 Hz matching firmware sample rate
5. Accel units are m/s² (not raw ADC), gyro is rad/s, quat is unit-length float

**Key files:** [backend/rehab_robotics_bridge/esp32_bridge_node.py](../../../backend/rehab_robotics_bridge/esp32_bridge_node.py)

---

### Phase 08: Multi-Node Support

**Goal:** Master + up to 3 slave nodes each publish on their own topic, with reconnect on loss.

**Success Criteria:**
1. `nodes.yaml` with 2 entries → `ros2 topic list` shows both `/esp32/master/imu` and `/esp32/slave_1/imu`
2. Disconnecting one node logs a warning; reconnect attempt fires after 5 s
3. Reconnected node resumes publishing without restarting the aggregator
4. `launch/rehab_robotics.launch.py` starts both aggregator and rosbridge in one command

**Key files:** [backend/rehab_robotics_bridge/imu_aggregator_node.py](../../../backend/rehab_robotics_bridge/imu_aggregator_node.py), [backend/config/nodes.yaml](../../../backend/config/nodes.yaml), [backend/launch/rehab_robotics.launch.py](../../../backend/launch/rehab_robotics.launch.py)

---

### Phase 09: rosbridge WebSocket Integration

**Goal:** Browser connects to ws://localhost:9090 and receives live IMU messages via roslibjs.

**Success Criteria:**
1. Open a test HTML page with roslibjs — subscribes to `/esp32/master/imu`, logs orientation.w to console
2. Messages arrive at ~100 Hz without dropped connections
3. Disconnecting the backend → browser gets an error event; reconnecting resumes messages
4. Status strip in GUI shows "ROS Connected" / "ROS Disconnected" based on WebSocket state

**Key files:** `rehab-robotics-studio/src/components/chrome/StatusStrip.tsx`, new `src/data/RosBridgeDataSource.ts`

---

### Phase 10: GUI DataSource — Live Hardware Stream

**Goal:** Set `VITE_BACKEND=ros` and the GUI receives real IMU data from the ESP32 instead of mock signals.

**Success Criteria:**
1. `src/data/RosBridgeDataSource.ts` exports a class implementing `DataSource` interface fully
2. Connects to `ws://localhost:9090` using roslibjs (already a transitive dep via rosbridge)
3. Maps `sensor_msgs/Imu` → `Frame.imu`: `quat=[w,x,y,z]`, `accel=[x,y,z]`, `gyro=[x,y,z]`
4. `signalBus.ts` checks `import.meta.env.VITE_BACKEND` — `'ros'` uses `rosBridgeDataSource`, else `mockDataSource`
5. Rotating the physical ESP32 causes visible change in the IMU block's output on the canvas
6. Disconnecting the ESP32 → GUI logs warning, status strip shows disconnected, mock data does NOT resume automatically

**Key files:** `rehab-robotics-studio/src/data/RosBridgeDataSource.ts`, `rehab-robotics-studio/src/data/signalBus.ts`

---

## Progress

| Phase | Name | Status |
|-------|------|--------|
| 06 | Package Scaffold & Dev Env | Scaffolded — needs build verification |
| 07 | ESP32 Bridge Node | Scaffolded — needs hardware test |
| 08 | Multi-Node Support | Scaffolded — needs hardware test |
| 09 | rosbridge WebSocket | Planned |
| 10 | GUI DataSource | Planned |
