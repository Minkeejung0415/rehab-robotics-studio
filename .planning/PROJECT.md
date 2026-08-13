# Rehab Robotics Studio

## What This Is

Rehab Robotics Studio is a local LabVIEW-style rehabilitation robotics GUI and ROS 2 backend for collecting, processing, and recording paired ESP32 IMU data. It provides a practical operator surface for live acquisition, SD sessions, and biomechanical monitoring.

## Core Value

Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- Existing ROS 2 package scaffold and TCP ESP32 bridge are present, but the end-to-end hardware pipeline is not yet validated.
- Paired Master/Slave ESP32 health and native IMU topics are visible through ROS 2 and Studio.
- OpenSim calibration, orientation IK status, joint-state output, and native visualizer controls exist for the current two-sensor path.
- v1.6 provides full-MAC fleet identity, model-derived sensor mapping, persistent desired/applied revisions, dynamic per-MAC OpenSim inputs, and a dedicated Studio mapping workspace.
- Live hardware verification proved two mapped ESP inputs reconnect at approximately 100 Hz, remain fresh/synchronized, and can be swapped and restored through the GUI mapping workflow.

### Active

- [ ] Show every connected ESP as an automatically discovered, full-MAC and body-part-labelled signal source.
- [ ] Show Open Ephys-style stacked live traces for ax/ay/az, gx/gy/gz, mx/my/mz, and optional qw/qx/qy/qz channels.
- [ ] Let the operator control channel visibility, grouping, raw/SI units, time window, pause, zoom/scale, and autoscale without affecting acquisition or recording.
- [ ] Keep rendering responsive through bounded buffering and display downsampling while preserving the full-rate recording path.
- [ ] Prove displayed channel identity, exported data columns, full MAC, and applied body-part mapping remain consistent across remap and reconnect.
- [ ] Prove on physical hardware that an applied Studio segment swap changes which OpenSim 3D model segment responds after recalibration.

### Out of Scope

- Generic neural-acquisition functions such as impedance measurement, headstage configuration, DAC audio routing, and AUX/ADC routing - not relevant to the paired IMU workflow.
- ESP32 firmware protocol redesign - the GUI should expose the existing plugin-compatible commands.
- Motor-control and EtherCAT integration - unrelated to IMU acquisition operations.
- Block Deployment work previously scoped as v1.2 - parked intact for a later milestone while acquisition integrity is corrected.
- Audit findings 1 and 8-10 - physical E-STOP integration, graph persistence, Docker packaging, stale aggregator/documentation, and broader performance work are deferred.
- Clinical or biomechanical validity claims without an external-reference protocol.
- Embedded Studio 3D rendering of the solved model - deferred; native OpenSim visualizer is used via an operator button.
- Remaining unfinished v1.3 Acquisition Integrity phases - preserved as unfinished prior scope.

## Current Milestone: v1.7 Multi-Sensor Signal Viewer & 3D Mapping Validation

**Goal:** Let an operator inspect every raw IMU component as a responsive Open Ephys-style live trace and prove that displayed, recorded, mapped, and OpenSim 3D sensor identities agree end to end.

**Target features:**
- An automatically populated ESP/source selector labelled by full MAC and applied body part.
- Stacked live traces for the nine accel/gyro/magnetometer components plus optional quaternion channels.
- Per-group and per-channel visibility, raw/SI units, time-window, pause, zoom/scale, and autoscale controls.
- Bounded browser buffers and display downsampling that do not reduce the full-rate recording path.
- Recording/export provenance that retains channel, full-MAC, and applied body-part identity.
- Hardware-backed calibrated 3D remap validation proving the UI assignment changes the responding OpenSim segment.

## Context

v1.6 generalized the prior fixed Master/Slave path into stable full-MAC fleet rows, authoritative model-derived mapping revisions, and dynamic per-MAC OpenSim inputs. Live testing subsequently exposed and fixed the GUI frame-option collision, atomic sensor-swap behavior, desired-versus-applied snapshot separation, mapping payload contract, and canonical typed per-MAC IMU path. v1.7 builds an operator-grade signal inspection surface on that corrected stream and closes the remaining visual proof that an applied segment remap drives the corresponding calibrated 3D model segment.

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
| Defer IK and embedded visualization beyond v1.4 | Solver, calibration, packaging, and Studio rendering are unnecessary until the basic subscription path works | Superseded by v1.5 |
| v1.5 uses official OpenSim orientation IK, not custom relative-quat math | User rejected presenting hand-rolled angle as OpenSim IK | Active |
| Toolbar Calibrate + Clear cal; fixed standing/knees-extended pose; hard CALIBRATED gate | User accepted discuss-phase recommendations (1A/2A/3A/4A) | Active |
| Toolbar button starts/shows native OpenSim 3D visualizer | Operator control separate from IK solve | Active |
| Discover and map all Master/Slave IMUs, not Slaves only | The Master is also a wearable orientation source and must be assignable to a model segment | Active |
| Use loaded `.osim` model segments as the mapping vocabulary | Prevents stale hard-coded bone lists and keeps assignments valid for the active model | Active |
| Persist mappings by model identity and ESP MAC | Reconnecting hardware should restore the operator's prior assignment without depending on DHCP addresses | Active |
| Identify hardware with status plus temporary LED blink | MAC addresses alone are difficult to match to physical sensors during setup | Active |
| Enforce one sensor per segment | Duplicate orientation sources for one segment are ambiguous for calibration and IK | Active |
| Use bounded display buffers with downsampling, independent from recording | Open Ephys-style traces must remain responsive without discarding full-rate recorded samples | Active |
| Label every trace and export by full MAC plus applied body part | Role or connection order cannot safely identify a wearable sensor | Active |
| Require calibrated physical 3D remap UAT | Topic and subscription checks alone do not prove the operator sees the intended model segment move | Active |

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
*Last updated: 2026-08-13 - started v1.7 Multi-Sensor Signal Viewer & 3D Mapping Validation*
