# Rehab Robotics ROS2 Backend

ROS2 (Humble/Iron) bridge that connects ESP32-S3 IMU nodes to the Rehab Robotics Studio GUI via WebSocket.

## Architecture

```
ESP32 Master (WiFi) ──TCP:5000──→ imu_aggregator_node ──→ /esp32/master/imu
ESP32 Slave 1 (ESP-NOW→Master) ──────────────────────────→ /esp32/slave_1/imu
                                                                    ↓
                                                     rosbridge_websocket :9090
                                                                    ↓
                                                     GUI RosBridgeDataSource
                                                                    ↓
                                                     signalBus → React components
```

## Quick Start (Docker — no ROS2 install needed)

```bash
# Edit your ESP32 node IPs first:
nano config/nodes.yaml

# Start backend + rosbridge:
docker compose up

# GUI connects to ws://localhost:9090 automatically
```

## Quick Start (Native ROS2 Humble)

```bash
# Install rosbridge:
sudo apt install ros-humble-rosbridge-suite

# Build package:
cd /path/to/this/backend
colcon build --symlink-install
source install/setup.bash

# Launch:
ros2 launch rehab_robotics_bridge rehab_robotics.launch.py
```

## USB Path (no WiFi)

When the ESP32 is connected via USB instead of WiFi:

```bash
# 1. Start the serial-to-TCP bridge (from the Plugin repo):
python3 ../esp32/host/serial_tcp_bridge.py COM5 --plugin   # Windows
# python3 ../esp32/host/serial_tcp_bridge.py /dev/ttyUSB0 --plugin  # Linux

# 2. Set host to 127.0.0.1 in config/nodes.yaml:
#      - id: master
#        host: 127.0.0.1
#        port: 5000

# 3. Start the backend normally
```

## Configuration

Edit `config/nodes.yaml` to match your hardware:

```yaml
nodes:
  - id: master
    host: 192.168.4.1   # ESP32 master IP (or 127.0.0.1 for USB)
    port: 5000
  # - id: slave_1
  #   host: 192.168.4.2
  #   port: 5000
```

## Topics Published

| Topic | Type | Description |
|-------|------|-------------|
| `/esp32/{id}/imu` | `sensor_msgs/Imu` | Fused quaternion + accel + gyro |
| `/esp32/{id}/raw` | `std_msgs/Float32MultiArray` | All 11 raw channels normalized |

## GUI Integration

The GUI connects via `ws://localhost:9090` using roslibjs (rosbridge protocol).
See `../rehab-robotics-studio/src/data/RosBridgeDataSource.ts` (Phase 5).

## Channel Map (firmware v1.4+)

| Channel | Signal | Scale |
|---------|--------|-------|
| ch0–2 | Accel X/Y/Z | m/s² |
| ch3–5 | Gyro X/Y/Z | rad/s |
| ch6 | DIO input | — |
| ch7–10 | Quat W/X/Y/Z | float (int16/32767) |
