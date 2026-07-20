# Stack Research: ROS2 Backend Alignment

## Existing Stack

- Python `ament_python` ROS 2 package using `rclpy` and `std_msgs/String`.
- ESP32 TCP control channel with Open Ephys-style binary frames.
- Local backend package: `rehab_robotics_bridge`.
- Reference package: `oe_esp32_bridge` in the sibling Plugin repository.

## Required Additions

- `numpy` for endian-safe, shaped int16 UDP payload parsing, matching the reference bridge.
- Canonical JSON sample model shared by bridge, filter, OpenSim adapter, recorder, and tests.
- ROS 2 launch configuration for master/slave bridge instances and downstream nodes.
- `rosbridge_server` retained as an optional GUI access node.

## Decision

Use `std_msgs/String` carrying the plugin-compatible `oe_esp32.raw.v1` JSON payload as the stable internal contract. Native `sensor_msgs/Imu` may be published as a compatibility side output, but it must not replace the raw JSON contract.

## Sources

- Plugin repository: `oe_esp32_bridge` source and launch files.
- [ROS 2 parameters documentation](https://docs.ros.org/en/lyrical/Concepts/Basic/About-Parameters.html): declare and launch-configure every node parameter.
- [ROS 2 nodes documentation](https://docs.ros.org/en/lyrical/Concepts/Basic/About-Nodes.html): keep bridge, filter, adapter, and recorder as separate single-purpose nodes.
