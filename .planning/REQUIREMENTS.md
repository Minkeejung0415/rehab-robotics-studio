# Requirements: Rehab Robotics Studio

**Defined:** 2026-07-30
**Milestone:** v1.6 Multi-Sensor Bone Mapping
**Core Value:** Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.

## v1.6 Requirements

### Device Identity and Identify

- [ ] **ID-01**: Operator can see a verified, normalized full 48-bit hardware identity for the Master and every discovered Slave.
- [ ] **ID-02**: A device keeps the same canonical identity and data topic across DHCP changes, reconnects, and discovery-order changes; role, IP, and transport MAC remain separate metadata.
- [ ] **ID-03**: Operator can target one device with a bounded, non-blocking LED Identify action whose result is application-acknowledged and distinguishes confirmed, timeout, offline, unsupported, and rejected outcomes.

### Fleet Discovery and Routing

- [ ] **FLEET-01**: Operator can see the Master and every currently or previously known Slave in one MAC-keyed fleet registry with separate discovery, command, route, orientation freshness, synchronization, and rate states.
- [ ] **FLEET-02**: Each routed device publishes canonical per-MAC IMU and health data while the existing fixed Master/Slave topics remain compatible aliases bound to explicit device identities.
- [ ] **FLEET-03**: A failed, stale, or reconnecting device route does not stop acquisition, health, Identify, or recording for other devices, and queue/drop/reconnect diagnostics remain bounded and visible.

### OpenSim Model Catalog

- [ ] **MODEL-01**: The loaded `.osim` file is identified by a SHA-256 hash of its exact bytes, not only its filename or path.
- [ ] **MODEL-02**: Operator can choose only exact model-derived non-Ground segment/component paths and compatible sensor Frames reported by the loaded OpenSim model.
- [ ] **MODEL-03**: Missing, ambiguous, or unsupported sensor Frames fail closed with an actionable reason and never silently select a similarly named component or modify the source model.

### Mapping and Persistence

- [ ] **MAP-01**: Operator can explicitly mark every known device as Assigned to one model segment, Not used, or Unassigned; Unassigned devices keep the mapping incomplete.
- [ ] **MAP-02**: Studio and backend reject duplicate segment assignments, unknown devices/segments, incomplete decisions, and mappings that do not satisfy the selected solver profile.
- [ ] **MAP-03**: Desired mappings persist authoritatively in the backend by exact model hash and full device identity with a versioned schema, revision, atomic write, backup, and corruption recovery.
- [ ] **MAP-04**: Applying a mapping validates and stages the complete candidate against the expected revision, swaps it atomically on success, and preserves the previous applied revision on any failure.
- [ ] **MAP-05**: Same-device reconnect under an unchanged model/mapping revision reattaches automatically, while a different MAC at the old route remains a new Unassigned device.
- [ ] **MAP-06**: Apply is blocked during calibration capture, SD recording, and recording finalization without stopping or altering the active recording session.

### Dynamic Calibration and OpenSim IK

- [ ] **IK-01**: The applied mapping creates and tears down deterministic MAC-keyed subscriptions and one ordered N-sensor orientation input set without leaking subscriptions, callbacks, or queues across remaps.
- [ ] **IK-02**: Calibration artifacts are bound to model hash, applied mapping revision, exact device-to-Frame assignments, and solver profile, and are invalidated by any semantic change.
- [ ] **IK-03**: Joint-state publication occurs only when every required mapped input is valid, fresh, post-reconnect, and within the configured synchronization-skew bound; degraded input suppresses new IK output without stopping acquisition or recording.
- [ ] **IK-04**: Official OpenSim orientation IK consumes the mapped N-sensor set in deterministic order and reports mapping revision, calibration identity, input validity, solver status, and visualizer provenance.

### Studio Mapping Workspace

- [ ] **UI-01**: Operator can open a dedicated mapping panel containing stable rows for the Master and every known Slave, including offline saved devices.
- [ ] **UI-02**: Each row shows full MAC identity, role/capabilities, layered readiness, live rate/errors, model-derived segment selector, explicit Not used choice, and targeted Identify control.
- [ ] **UI-03**: Operator can distinguish Draft, Saved, Applied, and Runtime Ready states and receives immediate local conflict feedback plus authoritative backend validation and stale-revision errors.
- [ ] **UI-04**: Reload, reconnect, arbitrary status ordering, and temporary dropout preserve row identity and restore the backend mapping without treating browser state as applied truth.

### Compatibility and Promotion

- [ ] **COMP-01**: Existing two-sensor startup, pair health, frequency/range controls, recording, calibration, joint-state, graph, and visualizer workflows remain functional through explicit compatibility aliases and rollback mode.
- [ ] **COMP-02**: Deterministic tests cover full-MAC collisions, arbitrary discovery order, DHCP/reconnect, Identify acknowledgement failures, partial-Apply rollback, corrupt persistence, stale/skewed samples, interlocks, and repeated resource cleanup.
- [ ] **COMP-03**: Hardware acceptance documents the supported fleet size and rates after testing Master plus multiple Slaves for Identify safety, acquisition/recording continuity, reconnect, radio/relay load, and OpenSim solve latency before dynamic mode becomes the default.

## Future Requirements

- Profile-defined partial-sensor or degraded IK after accuracy and observability are independently validated.
- Explicit export of a derived `.osim` model when runtime sensor Frames must be generated.
- Per-sensor orientation weights and advanced biomechanical placement calibration.
- Mapping profile import/export and bounded audit history beyond the core backend store.
- Fleet OTA, battery analytics, cloud operation, and generic Wi-Fi provisioning.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Browser/localStorage as applied-mapping authority | Cannot prove ROS/OpenSim runtime state or provide atomic multi-client revisions |
| IP address, discovery slot, role, or truncated ID as persistent identity | These values are mutable or collision-prone |
| Automatic segment choice or duplicate segment sources | Ambiguous for calibration and official IK |
| Silently modifying the source `.osim` model | Model provenance must remain explicit and reproducible |
| Auto-stopping recording to permit mapping Apply | Recording integrity and operator intent take precedence |
| Partial-sensor IK and clinical accuracy claims | Require separate biomechanical validation |
| Replacing the existing ROS 2, rosbridge, React, Zustand, or OpenSim stack | Current dependencies already support the milestone |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ID-01 | TBD | Pending |
| ID-02 | TBD | Pending |
| ID-03 | TBD | Pending |
| FLEET-01 | TBD | Pending |
| FLEET-02 | TBD | Pending |
| FLEET-03 | TBD | Pending |
| MODEL-01 | TBD | Pending |
| MODEL-02 | TBD | Pending |
| MODEL-03 | TBD | Pending |
| MAP-01 | TBD | Pending |
| MAP-02 | TBD | Pending |
| MAP-03 | TBD | Pending |
| MAP-04 | TBD | Pending |
| MAP-05 | TBD | Pending |
| MAP-06 | TBD | Pending |
| IK-01 | TBD | Pending |
| IK-02 | TBD | Pending |
| IK-03 | TBD | Pending |
| IK-04 | TBD | Pending |
| UI-01 | TBD | Pending |
| UI-02 | TBD | Pending |
| UI-03 | TBD | Pending |
| UI-04 | TBD | Pending |
| COMP-01 | TBD | Pending |
| COMP-02 | TBD | Pending |
| COMP-03 | TBD | Pending |

**Coverage:**
- v1.6 requirements: 26 total
- Mapped to phases: 0
- Unmapped: 26

---
*Requirements defined: 2026-07-30*
