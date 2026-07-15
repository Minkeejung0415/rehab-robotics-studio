# Rehab Robotics Studio

## What This Is

Rehab Robotics Studio is a local LabVIEW-style rehabilitation robotics GUI and ROS 2 backend for collecting, processing, and recording ESP32 IMU data. This milestone brings the backend in line with the plugin repository's working ROS 2 pipeline so clinicians and developers can use the GUI against real, processed biomechanical data.

## Core Value

Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- Existing ROS 2 package scaffold and TCP ESP32 bridge are present, but the end-to-end hardware pipeline is not yet validated.

### Active

- [ ] Align ESP32 live acquisition with the plugin backend's handshake, UDP transport, framing validation, and raw JSON ROS contract.
- [ ] Provide the plugin-style filtering, OpenSim, recording, and status stages as a launchable ROS 2 pipeline.
- [ ] Preserve GUI-facing ROS access while exposing the processed pipeline's data and health state.
- [ ] Add executable verification for protocol parsing and pipeline startup behavior.

### Out of Scope

- Replacing the React GUI's mock data source with a production rosbridge client - this milestone provides the backend contract first.
- Redesigning the ESP32 firmware protocol - the backend must follow the established plugin protocol.
- Motor-control and EtherCAT integration - unrelated to the IMU acquisition and biomechanics pipeline.

## Current Milestone: v1.0 ROS2 Backend Alignment

**Goal:** Make this repository's ROS 2 backend operate like the plugin repository's full ESP32-to-filter-to-OpenSim-to-recording pipeline.

**Target features:**
- Plugin-compatible ESP32 live ingestion and raw ROS topics.
- Filter, OpenSim, recorder, and status nodes with a single launch path.
- GUI-compatible rosbridge access and end-to-end verification.

## Context

The local backend package is `rehab_robotics_bridge`; it currently publishes ROS-native `sensor_msgs/Imu` and `Float32MultiArray` messages from a TCP frame stream and launches rosbridge. The reference plugin package, `oe_esp32_bridge`, completes the ESP32 handshake over TCP, receives live frames through UDP, publishes JSON `std_msgs/String` raw topics, and includes filtering, OpenSim, recording, and status nodes. Both share the same 14-channel Open Ephys-style frame semantics, but their runtime contracts diverge after the handshake.

## Constraints

- **Protocol compatibility**: Follow the plugin repository's live handshake, UDP frame validation, node-role metadata, and JSON schema - it is the requested behavioral reference.
- **ROS 2 compatibility**: Keep standard ROS 2 launch/package conventions and retain rosbridge access for the GUI.
- **Safety and observability**: Pipeline stages must report malformed data, connection loss, and recording failures rather than silently dropping them.
- **Repository hygiene**: Preserve unrelated work already present in the dirty working tree.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use the plugin ROS 2 backend as the behavioral reference | The user wants equivalent operational behavior, not merely similar code | Pending |
| Align on raw JSON ROS topics before GUI integration | This gives every downstream stage a stable, testable contract | Pending |
| Keep rosbridge in the backend launch stack | The GUI needs a ROS-facing access path while its mock data source remains in place | Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `$gsd-transition`):
1. Requirements invalidated? Move to Out of Scope with reason
2. Requirements validated? Move to Validated with phase reference
3. New requirements emerged? Add to Active
4. Decisions to log? Add to Key Decisions
5. "What This Is" still accurate? Update if drifted

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check - still the right priority?
3. Audit Out of Scope - reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-15 after starting v1.0 ROS2 Backend Alignment*
