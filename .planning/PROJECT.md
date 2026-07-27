# Rehab Robotics Studio

## What This Is

Rehab Robotics Studio is a local LabVIEW-style rehabilitation robotics GUI and ROS 2 backend for collecting, processing, and recording paired ESP32 IMU data. It provides a practical operator surface for live acquisition, SD sessions, and biomechanical monitoring.

## Core Value

Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- Existing ROS 2 package scaffold and TCP ESP32 bridge are present, but the end-to-end hardware pipeline is not yet validated.

### Active

- [ ] Start an `opensim_bridge` that subscribes to the existing master and slave ESP quaternion topics.
- [ ] Convert incoming ROS quaternions into the ordering and rotation representation expected by OpenSim.
- [ ] Map the two ESP sensors to configurable OpenSim model frames and update their live orientations.
- [ ] Provide a simple launch path and observable connection/error status for the live link.
- [ ] Verify the subscription and quaternion forwarding path locally with deterministic test messages.

### Out of Scope

- Generic neural-acquisition functions such as impedance measurement, headstage configuration, DAC audio routing, and AUX/ADC routing - not relevant to the paired IMU workflow.
- ESP32 firmware protocol redesign - the GUI should expose the existing plugin-compatible commands.
- Motor-control and EtherCAT integration - unrelated to IMU acquisition operations.
- Block Deployment work previously scoped as v1.2 - parked intact for a later milestone while acquisition integrity is corrected.
- Audit findings 1 and 8-10 - physical E-STOP integration, graph persistence, Docker packaging, stale aggregator/documentation, and broader performance work are deferred.
- Inverse kinematics, joint-angle solving, calibration workflows, deployment packaging, and biomechanical validation - deferred until the quaternion live link works.
- Embedded Studio 3D visualization - deferred; this milestone may use OpenSim's own visualizer only as a live-link demonstration.
- Remaining v1.3 Acquisition Integrity phases - preserved as unfinished prior scope while v1.4 is active.

## Current Milestone: v1.4 OpenSim Quaternion Live Link

**Goal:** Open an OpenSim model and feed it the live quaternion values already published by the paired ESP devices.

**Target features:**
- Subscription to the existing native master and slave `sensor_msgs/Imu` topics.
- Explicit ROS-to-OpenSim quaternion conversion and configurable sensor/frame mapping.
- A minimal OpenSim-side live orientation update path using the native visualizer when available.
- Launch parameters, status reporting, and deterministic local verification.

## Context

The GUI and ROS 2 backend already expose paired ESP32 controls, health, processing, recording, native `sensor_msgs/Imu` topics, and rosbridge integration. A placeholder `opensim_bridge` currently forwards one filtered JSON stream over UDP, but OpenSim does not natively subscribe to that packet. v1.4 is deliberately a narrow proof of connection: subscribe to the two ROS IMU quaternion streams, convert and map them, and feed them into an OpenSim model/live visualizer. IK, calibration, and production deployment are later milestones. The unfinished v1.3 roadmap and Phase 9 artifacts remain preserved in repository history and on disk.

## Constraints

- **Protocol compatibility**: Follow the plugin repository's live handshake, UDP frame validation, node-role metadata, and JSON schema - it is the requested behavioral reference.
- **ROS 2 compatibility**: Keep standard ROS 2 launch/package conventions and retain rosbridge access for the GUI.
- **Safety and observability**: Pipeline stages must report malformed data, connection loss, and recording failures rather than silently dropping them.
- **Repository hygiene**: Preserve unrelated work already present in the dirty working tree.
- **Disconnected target**: The Jetson is not currently connected, so v1.2 must be testable entirely through local ROS publication and inspection.
- **Code safety**: Creating and inspecting a message must not execute user-provided processing code in the browser or local ROS bridge.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use the plugin acquisition board as the hardware-operation reference | The user wants operational equivalence for the paired ESP32 workflow | Active |
| Treat Rec as parallel SD logging, not the acquisition switch | Run/Stop and recording need independent semantics in the lab workflow | Implemented |
| Require confirmed hardware acknowledgements before the GUI commits a setting | Prevents the UI from reporting a configuration that the board rejected | Implemented |
| Use a typed ROS processing-block update contract | Explicit fields make the future updater deterministic and versionable while still carrying YAML and code text | Active |
| Generate drafts on connection and finalize on Deploy | Connection provides immediate feedback while Deploy remains the operator-controlled release boundary | Active |
| Keep the source payload language-neutral and single-entry | Supports future processor languages without introducing archive handling in v1.2 | Active |
| Park Block Deployment and prioritize acquisition integrity as v1.3 | Incorrect measurements and misleading live state undermine every downstream processing or deployment feature | Active |
| Reduce v1.4 to an OpenSim quaternion live-link prototype | The immediate need is only to prove that OpenSim can consume the quaternion values already published by the ESP devices | Active |
| Defer IK and embedded visualization beyond v1.4 | Solver, calibration, packaging, and Studio rendering are unnecessary until the basic subscription path works | Active |
| Preserve unfinished v1.3 artifacts and continue phase numbering | Avoid losing prior planning work or colliding with existing phase identifiers | Active |

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
*Last updated: 2026-07-27 - reduced v1.4 to OpenSim Quaternion Live Link*
