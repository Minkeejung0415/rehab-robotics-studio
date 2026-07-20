# Pitfalls Research: ROS2 Backend Alignment

## Protocol Risks

- Treating the post-handshake stream as TCP: the plugin expects live data on UDP and must reject incompatible transport acknowledgements.
- Accepting packets from arbitrary IPs: validate the UDP source against the configured ESP32 host.
- Parsing untrusted headers without validating element size, payload length, channel count, and samples per packet.
- Reusing one UDP port for master and slave on the same host.

## Contract Risks

- Changing field names or quaternion ordering breaks filters, replay, recordings, and OpenSim consumers.
- Mixing calibrated ROS-native IMU values with raw JSON in the primary topic creates ambiguous units. Keep raw JSON canonical and native IMU explicitly secondary.
- Retaining the local aggregator's stale bridge assumptions would mask multi-node failures; it should be replaced or retired by independent bridge nodes.

## Operational Risks

- Blocking disk I/O in a subscriber callback can stall the pipeline; recorder must isolate file handling and report failures.
- Failure loops need bounded exponential backoff to avoid noisy logs and network pressure.
- ROS 2 parameters must be declared and supplied through launch or YAML; hidden CLI-only configuration undermines repeatability.

## Testing Guidance

- Unit-test header validation, source filtering, frame-to-JSON mapping, filtering, OpenSim packet creation, and recorder file naming.
- Test the pipeline offline with JSON/CSV fixtures before hardware validation.
- Use the official `rosbag2_py` API only if bag recording becomes a requirement; this milestone retains plugin-compatible JSONL recording. [ROS 2 bag recording API](https://docs.ros.org/en/jazzy/Tutorials/Advanced/Recording-A-Bag-From-Your-Own-Node-Py.html)
