---
project: Rehab Robotics ROS2 Backend
created: 2026-07-13
milestone: v1.0
---

# Project: Rehab Robotics ROS2 Backend

## Summary

A ROS2 (Humble/Iron) Python backend that bridges ESP32-S3 IMU sensor nodes
to the Rehab Robotics Studio GUI via rosbridge WebSocket.

The ESP32 system (from `Minkeejung0415/Plugin`) uses a master + 1–3 slave
architecture over ESP-NOW sync. Each node runs an ICM20948 IMU and streams
fused quaternions + raw accel/gyro over TCP (WiFi) or USB serial using the
Open Ephys binary protocol.

This backend:
1. Reads data from each ESP32 node (via serial-to-TCP bridge or direct TCP)
2. Publishes per-node `sensor_msgs/Imu` ROS2 topics
3. Exposes a rosbridge WebSocket server so the browser GUI can subscribe
4. The GUI's `RosBridgeDataSource` replaces `MockDataSource` for live use

## Core Value

Real IMU data from wearable ESP32 nodes flows into the Rehab Robotics GUI
in real-time — joint angles, forces, and motor state driven by actual hardware,
not synthetic signals.

## Architecture

```
ESP32 Master (WiFi/USB)
  → serial_tcp_bridge.py (if USB)
  → ESP32BridgeNode (rclpy)
      → /esp32/master/imu  (sensor_msgs/Imu)
      → /esp32/master/raw  (custom Float32MultiArray)

ESP32 Slave n (via ESP-NOW → Master)
      → /esp32/slave_1/imu
      → /esp32/slave_2/imu
      ...

ROS2 topics
  → rosbridge_suite WebSocket (:9090)
      → GUI RosBridgeDataSource.ts
          → Frame { imu, force, emg, motor }
          → signalBus → React components
```

## Constraints

- ROS2 Humble (Ubuntu 22.04) or Iron (Ubuntu 22.04/24.04)
- Python 3.10+ only
- No extra firmware changes — ESP32 firmware already streams Open Ephys binary
- Must work alongside existing `opensim_live_realtime.py` (does not conflict)
- Browser GUI connects via `ws://localhost:9090` (rosbridge default)

## References

- ESP32 firmware: `Minkeejung0415/Plugin` → `esp32/firmware/`
- Existing bridge scripts: `esp32/host/serial_tcp_bridge.py`, `esp32_to_opensim_bridge.py`
- GUI DataSource interface: `rehab-robotics-studio/src/data/DataSource.ts`
- ROS2 rosbridge: https://github.com/RobotWebTools/rosbridge_suite
