# Roadmap: Rehab Robotics ROS2 Backend

**Milestone:** v1.0 — ESP32 IMU → ROS2 → GUI Live Stream
**Created:** 2026-07-13
**Phases:** 5

## Overview

| # | Phase | Goal | Requirements | Status |
|---|-------|------|--------------|--------|
| 1 | Package Scaffold | ROS2 Python package structure + Docker dev env | OPS-01, OPS-02, OPS-03 | Planned |
| 2 | ESP32 Bridge Node | Read TCP/serial stream, publish Imu topics | BRIDGE-01–04 | Planned |
| 3 | Multi-Node Support | Master + slave topic fan-out | BRIDGE-05, BRIDGE-06 | Planned |
| 4 | rosbridge WebSocket | WebSocket server, browser subscription | WS-01–03 | Planned |
| 5 | GUI DataSource | RosBridgeDataSource.ts, signalBus wiring | GUI-01–03, PERF-01–02 | Planned |

---

## Phase Details

### Phase 1: Package Scaffold & Dev Environment

**Goal:** Runnable ROS2 Python package with Docker dev environment.

**Success Criteria:**
1. `backend/` directory with valid `package.xml`, `setup.py`, `setup.cfg`
2. `docker-compose.yml` brings up ROS2 Humble + rosbridge
3. `ros2 run rehab_robotics_bridge dummy_node` prints "hello"
4. README explains USB and WiFi quickstart paths

**Key files:** `backend/package.xml`, `backend/setup.py`, `backend/docker-compose.yml`, `backend/README.md`

---

### Phase 2: ESP32 Bridge Node (Master)

**Goal:** rclpy node reads Open Ephys binary from ESP32 TCP stream and publishes IMU topics.

**Success Criteria:**
1. `esp32_bridge_node.py` connects to `ESP32_NODE_HOST:ESP32_NODE_PORT`
2. Parses 11-channel Open Ephys binary frames (REDPITAYA/START handshake)
3. Publishes `sensor_msgs/Imu` to `/esp32/master/imu` at acquisition rate
4. Publishes `std_msgs/Float32MultiArray` to `/esp32/master/raw` (all channels)
5. `ros2 topic echo /esp32/master/imu` shows live quaternion updates when ESP32 is connected

**Key files:** `backend/rehab_robotics_bridge/esp32_bridge_node.py`

---

### Phase 3: Multi-Node Support

**Goal:** Handle master + up to 3 slave nodes, each on their own topic.

**Success Criteria:**
1. Config file (`nodes.yaml`) maps node IDs to TCP host:port
2. Aggregator node spawns per-node bridge connections
3. Topics: `/esp32/master/imu`, `/esp32/slave_1/imu`, ... `/esp32/slave_3/imu`
4. Node loss (disconnect) is logged; reconnect attempted every 5 s
5. `ros2 topic list` shows all active node topics

**Key files:** `backend/rehab_robotics_bridge/imu_aggregator_node.py`, `backend/config/nodes.yaml`

---

### Phase 4: rosbridge WebSocket

**Goal:** Expose ROS2 topics over WebSocket so browser GUI can subscribe.

**Success Criteria:**
1. `launch/rehab_robotics.launch.py` starts all nodes + rosbridge on port 9090
2. Browser `roslibjs` test page connects and logs quaternion messages
3. Connection lost → GUI shows error, auto-reconnects when rosbridge is back
4. Documented in README

**Key files:** `backend/launch/rehab_robotics.launch.py`

---

### Phase 5: GUI DataSource

**Goal:** Replace `MockDataSource` with `RosBridgeDataSource` in the Rehab Robotics GUI.

**Success Criteria:**
1. `rehab-robotics-studio/src/data/RosBridgeDataSource.ts` implements `DataSource`
2. Subscribes to `/esp32/master/imu` via roslibjs WebSocket
3. Maps `sensor_msgs/Imu` → `Frame.imu` (quat, accel, gyro)
4. Changing one env var (`VITE_BACKEND=ros`) switches from mock to live
5. End-to-end: ESP32 IMU rotation visible in the GUI block diagram sensor node

**Key files:** `rehab-robotics-studio/src/data/RosBridgeDataSource.ts`, `rehab-robotics-studio/src/data/signalBus.ts`
