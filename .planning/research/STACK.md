# Stack Research: Processing-Block Deployment Messages

**Domain:** Browser-authored ROS 2 processing-block deployment contracts
**Researched:** 2026-07-20
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| ROS 2 Humble | Existing project version | Typed topic contract and local inspection | Retains compatibility with the running Jetson/WSL environment. |
| `rosidl_default_generators` / `rosidl_default_runtime` | Humble 1.2.x | Generate Python/C/C++ type support for `ProcessingBlockUpdate.msg` | ROS interfaces are compile-time contracts; the interface belongs in a dedicated `ament_cmake` package. |
| rosbridge_suite | Existing Humble installation | Publish the custom message from the browser | The protocol advertises a concrete ROS type, validates published fields, and supports explicit QoS. |
| React + TypeScript + Zustand | Existing app versions | Build artifacts from graph and custom-block state | The graph connection and Deploy boundaries already live here. |
| Web Crypto `SubtleCrypto.digest` | Browser-native | SHA-256 integrity hash | Avoids a new hashing dependency and hashes the exact UTF-8 payload sent. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `yaml` | 2.x | Parse and normalize `processor.yaml` | Validate custom folders and generate deterministic manifest text. |
| `rclpy` | Humble | Local observer/validator node | Subscribe, recalculate integrity, and report accepted/rejected messages without executing code. |

## Package Layout

Create a sibling `rehab_robotics_interfaces` package using `ament_cmake`; ROS documentation notes that custom interface definitions live in a CMake package even when consumers are Python. Keep runtime nodes in the existing `ament_python` `rehab_robotics_bridge` package.

```text
rehab_robotics_interfaces/
  msg/ProcessingBlockUpdate.msg
  CMakeLists.txt
  package.xml

backend/rehab_robotics_bridge/
  processing_block_observer.py

rehab-robotics-studio/src/deployment/
  artifact.ts
  manifest.ts
  publisher.ts
```

## Message Direction

- `/processing_blocks/draft`: reliable, volatile, depth 10; connection/edit feedback.
- `/processing_blocks/update`: reliable, transient-local, depth 1; the latest finalized update remains available to late subscribers while its publisher remains alive.
- `/processing_blocks/status`: optional local validation status; it does not imply Jetson installation.

ROS 2 requires compatible requested/offered QoS. Both sides must request transient-local durability to receive an older sample, and rosbridge only uses the first advertisement's QoS for a shared topic. Advertise each topic once with its final intended QoS.

## What Not to Add in v1.2

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `std_msgs/String` as the whole contract | Loses field-level validation and type discovery | Custom `ProcessingBlockUpdate.msg` |
| Base64/compressed project archives | Conflicts with the selected single-entry text-file scope | UTF-8 `source_code` string plus `entrypoint` |
| Jetson SSH/Tailscale client | Target is disconnected and remote mutation is deferred | Local ROS observer and CLI inspection |
| Dynamic execution sandbox | Message creation must never execute uploaded code | Parse metadata and hash bytes only |

## Sources

- ROS 2 custom interfaces: https://docs.ros.org/en/iron/Tutorials/Beginner-Client-Libraries/Custom-ROS2-Interfaces.html
- ROSIDL internals and generators: https://docs.ros.org/en/humble/Concepts/About-Internal-Interfaces.html
- ROS 2 QoS: https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html
- rosbridge protocol: https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/ROSBRIDGE_PROTOCOL.md

---
*Stack research for: v1.2 Block Deployment*

