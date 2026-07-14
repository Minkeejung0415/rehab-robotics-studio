---
milestone: v2.0
title: ROS2 Backend + ESP32 Hardware Integration
supersedes: v1.0 requirements (archived in milestones/v1.0/)
---

# Requirements: v2.0

## Functional

| ID | Requirement |
|----|-------------|
| PKG-01 | `backend/` is a valid ROS2 ament_python package — `colcon build` succeeds |
| PKG-02 | `ros2 launch rehab_robotics_bridge rehab_robotics.launch.py` starts all nodes natively (Docker optional) |
| BRIDGE-01 | `esp32_bridge_node` connects to ESP32 TCP :5000 and completes REDPITAYA/START handshake |
| BRIDGE-02 | Parses 14-channel OE binary frames correctly (accel, gyro, mag, quat, DIO) |
| BRIDGE-03 | Publishes `sensor_msgs/Imu` to `/esp32/{node_id}/imu` with correct physical units |
| BRIDGE-04 | Publishes `std_msgs/Float32MultiArray` to `/esp32/{node_id}/raw` (all 14 ch) |
| BRIDGE-05 | Connection loss triggers a warning log and reconnect attempt every 5 s |
| MULTI-01 | `nodes.yaml` config maps node IDs → host:port |
| MULTI-02 | `imu_aggregator_node` spawns one bridge per entry in nodes.yaml |
| MULTI-03 | Supports 2–4 simultaneous nodes (master + slaves); each on its own topic |
| WS-01 | `rosbridge_websocket` runs on port 9090 after launch |
| WS-02 | Browser can connect via roslibjs and receive messages from `/esp32/master/imu` |
| WS-03 | `launch/rehab_robotics.launch.py` starts aggregator + rosbridge in one command |
| GUI-01 | `RosBridgeDataSource.ts` implements the `DataSource` interface in full |
| GUI-02 | Maps `sensor_msgs/Imu` orientation/accel/gyro → `Frame.imu` correctly |
| GUI-03 | Setting env var `VITE_BACKEND=ros` switches signalBus from mock to live |
| GUI-04 | Connection status (connected / disconnected) visible in the status strip |

## Non-Functional

| ID | Requirement |
|----|-------------|
| PERF-01 | End-to-end latency (ESP32 → GUI update) < 100 ms at 100 Hz |
| OPS-01 | USB path documented: run Plugin repo's serial_tcp_bridge.py + set host=127.0.0.1 |
| OPS-02 | WiFi path documented: join STEP_ESP32, host=192.168.4.1 |

## Out of Scope

- OpenSim IK (separate Python pipeline, not GUI-integrated in v2.0)
- Recording/SD card management (Plugin repo + Open Ephys handle this)
- Red Pitaya hardware (ESP32 only)
- TLS / authentication on WebSocket
