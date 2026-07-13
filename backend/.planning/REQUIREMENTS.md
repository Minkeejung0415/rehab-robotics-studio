---
project: Rehab Robotics ROS2 Backend
version: v1.0
---

# Requirements: Rehab Robotics ROS2 Backend

## Functional

| ID | Requirement |
|----|-------------|
| BRIDGE-01 | Bridge node connects to ESP32 master over TCP (WiFi) or USB serial |
| BRIDGE-02 | Bridge node parses Open Ephys binary frames (11-channel: accel, gyro, DIO, quat) |
| BRIDGE-03 | Publishes fused quaternion as `sensor_msgs/Imu` to `/esp32/{node_id}/imu` |
| BRIDGE-04 | Publishes raw channel array to `/esp32/{node_id}/raw` |
| BRIDGE-05 | Supports 2–4 simultaneous nodes (master + up to 3 slaves) |
| BRIDGE-06 | Node IDs assigned by connection order or config file |
| WS-01 | rosbridge WebSocket server runs on port 9090 |
| WS-02 | GUI can subscribe to `/esp32/+/imu` topics via roslibjs |
| WS-03 | Connection loss triggers clean reconnect attempt |
| GUI-01 | `RosBridgeDataSource.ts` implements `DataSource` interface |
| GUI-02 | `RosBridgeDataSource` maps `sensor_msgs/Imu` → `Frame.imu` |
| GUI-03 | Wiring `signalBus` to `RosBridgeDataSource` requires only one config change |

## Non-Functional

| ID | Requirement |
|----|-------------|
| PERF-01 | End-to-end latency (ESP32 → GUI) < 100 ms at 100 Hz sample rate |
| PERF-02 | Bridge node CPU < 5% on a laptop-class host |
| OPS-01 | Single `launch.py` file starts all ROS2 nodes + rosbridge |
| OPS-02 | Works without ROS2 installed: Docker Compose fallback |
| OPS-03 | README documents USB and WiFi setup paths |

## Out of Scope (v1.0)

- OpenSim IK integration (existing Python bridge handles this)
- Red Pitaya hardware (only ESP32 nodes)
- Recording/playback (already handled by Open Ephys / SD logger)
- Authentication or TLS on WebSocket
