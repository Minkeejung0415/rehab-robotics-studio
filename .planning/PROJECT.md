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

- [ ] Consume synchronized, normalized master and slave IMU quaternions through a real ROS 2 `opensim_bridge` node.
- [ ] Calibrate sensor-to-model orientation from a known reference pose and reject invalid or stale orientation inputs.
- [ ] Run real-time OpenSim/OpenSense-compatible inverse kinematics against a configurable musculoskeletal model.
- [ ] Publish solved joint angles, timestamps, solver quality, and bridge health for ROS and rosbridge consumers.
- [ ] Verify quaternion conventions, calibration, synchronization, and known-pose IK results with deterministic local tests.

### Out of Scope

- Generic neural-acquisition functions such as impedance measurement, headstage configuration, DAC audio routing, and AUX/ADC routing - not relevant to the paired IMU workflow.
- ESP32 firmware protocol redesign - the GUI should expose the existing plugin-compatible commands.
- Motor-control and EtherCAT integration - unrelated to IMU acquisition operations.
- Block Deployment work previously scoped as v1.2 - parked intact for a later milestone while acquisition integrity is corrected.
- Audit findings 1 and 8-10 - physical E-STOP integration, graph persistence, Docker packaging, stale aggregator/documentation, and broader performance work are deferred.
- Embedded or native OpenSim 3D visualization - explicitly deferred to a later milestone; v1.4 only preserves compatible joint/model outputs for it.
- Remaining v1.3 Acquisition Integrity phases - preserved as unfinished prior scope while v1.4 is active.

## Current Milestone: v1.4 Real-time OpenSim IK

**Goal:** Turn synchronized paired-ESP32 quaternion streams into calibrated, real-time OpenSim inverse-kinematics joint angles exposed through ROS 2.

**Target features:**
- A real `opensim_bridge` ROS 2 node that synchronizes and validates master/slave quaternion inputs.
- Reference-pose sensor-to-model calibration with explicit quaternion frame and ordering conventions.
- Real-time OpenSim/OpenSense-compatible IK with configurable model, IMU frame mapping, and joint selection.
- Standard ROS joint-angle and diagnostic outputs suitable for rosbridge and later 3D visualization.
- Local deterministic verification that does not require the disconnected Jetson target.

## Context

The GUI and ROS 2 backend already expose paired ESP32 controls, health, processing, recording, native `sensor_msgs/Imu` topics, and rosbridge integration. A placeholder `opensim_bridge` currently forwards one filtered JSON stream over UDP but does not synchronize multiple IMUs, calibrate sensor frames, execute IK, or publish joint states. v1.4 replaces that placeholder with the real-time IK boundary. OpenSim GUI or embedded web 3D visualization is intentionally deferred, while outputs should remain compatible with that future milestone. The unfinished v1.3 roadmap and Phase 9 artifacts remain preserved in repository history and on disk.

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
| Start v1.4 as a separate real-time OpenSim IK milestone | OpenSim integration is a distinct model/calibration/solver boundary and the user explicitly selected a new milestone | Active |
| Defer 3D visualization beyond v1.4 | First establish trustworthy real-time IK outputs; visualization can consume the stable ROS/model contract later | Active |
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
*Last updated: 2026-07-27 - started v1.4 Real-time OpenSim IK milestone*
