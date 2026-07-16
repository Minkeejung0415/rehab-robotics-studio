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

- [ ] Expose live ESP32 hardware configuration from the IMU acquisition block, including filter, IMU ranges, and effective rates.
- [ ] Provide an operator-facing recording and paired-device health surface with trustworthy SD session state and counters.
- [ ] Surface live acquisition diagnostics for connection, stream rate, synchronization, and actionable errors.

### Out of Scope

- Generic neural-acquisition functions such as impedance measurement, headstage configuration, DAC audio routing, and AUX/ADC routing - not relevant to the paired IMU workflow.
- ESP32 firmware protocol redesign - the GUI should expose the existing plugin-compatible commands.
- Motor-control and EtherCAT integration - unrelated to IMU acquisition operations.

## Current Milestone: v1.1 Acquisition Operations

**Goal:** Make the GUI a trustworthy operator surface for paired ESP32 acquisition, recording, and hardware health.

**Target features:**
- Live IMU configuration: editable sample rate, filter, accel/gyro ranges, and per-sensor effective rate.
- Recording and pair-health panel: SD session lifecycle, master/slave state, counters, and session metadata.
- Acquisition diagnostics: connection/reconnect state, stream rate, synchronization, and actionable hardware errors.

## Context

The GUI already receives real paired ESP32 frames through rosbridge and can command timestamped SD recordings and an editable paired sample rate. The plugin acquisition board remains the behavioral reference for remaining runtime controls and operational observability. The ESP32 firmware already supports `FILTER`, `FREQ`, and `CFG` commands plus rec-v1 status/session metadata; the current gap is exposing those capabilities coherently in the GUI and ROS bridge.

## Constraints

- **Protocol compatibility**: Follow the plugin repository's live handshake, UDP frame validation, node-role metadata, and JSON schema - it is the requested behavioral reference.
- **ROS 2 compatibility**: Keep standard ROS 2 launch/package conventions and retain rosbridge access for the GUI.
- **Safety and observability**: Pipeline stages must report malformed data, connection loss, and recording failures rather than silently dropping them.
- **Repository hygiene**: Preserve unrelated work already present in the dirty working tree.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use the plugin acquisition board as the hardware-operation reference | The user wants operational equivalence for the paired ESP32 workflow | Active |
| Treat Rec as parallel SD logging, not the acquisition switch | Run/Stop and recording need independent semantics in the lab workflow | Implemented |
| Require confirmed hardware acknowledgements before the GUI commits a setting | Prevents the UI from reporting a configuration that the board rejected | Implemented |

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
*Last updated: 2026-07-16 after starting v1.1 Acquisition Operations*
