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

- [ ] Decode accelerometer and gyroscope samples using the ranges confirmed by the ESP32 rather than fixed default scale factors.
- [ ] Preserve device timing and monotonic sequence information through the TCP/UDP, ROS, and rosbridge acquisition path.
- [ ] Filter quaternion samples without producing non-unit or zero orientations.
- [ ] Continue resolving ROS service responses while live-frame rendering is paused.
- [ ] Recover from ROSbridge fallback, close, and restart events without stale sockets or a forced page reload.
- [ ] Expire stale master/slave and stream-health state so disconnected hardware cannot remain falsely online.

### Out of Scope

- Generic neural-acquisition functions such as impedance measurement, headstage configuration, DAC audio routing, and AUX/ADC routing - not relevant to the paired IMU workflow.
- ESP32 firmware protocol redesign - the GUI should expose the existing plugin-compatible commands.
- Motor-control and EtherCAT integration - unrelated to IMU acquisition operations.
- Block Deployment work previously scoped as v1.2 - parked intact for a later milestone while acquisition integrity is corrected.
- Audit findings 1 and 8-10 - physical E-STOP integration, graph persistence, Docker packaging, stale aggregator/documentation, and broader performance work are deferred.

## Current Milestone: v1.3 Acquisition Integrity

**Goal:** Make live paired-ESP32 measurements, timing, transport recovery, command handling, and health reporting correct and trustworthy end to end.

**Target features:**
- Range-aware IMU conversion, preserved device timestamps/sequences, and geometry-safe quaternion filtering.
- Pause-safe service responses plus race-free ROSbridge fallback, restart, and hardware reconnection.
- Time-bounded master/slave and stream health that turns offline when valid updates stop.

## Context

The GUI and ROS 2 backend already expose paired ESP32 controls, health, processing, recording, and rosbridge integration. A repository-wide diagnosis confirmed six acquisition-integrity defect groups spanning firmware-configured scale factors, timing metadata, quaternion filtering, paused service handling, reconnection ownership, and stale health state. The former v1.2 Block Deployment scope is parked for later; v1.3 is limited to audit findings 2-7 and their regression coverage.

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
*Last updated: 2026-07-23 after starting v1.3 Acquisition Integrity*
