# Roadmap: Rehab Robotics Studio

## Overview

Milestone v1.7 turns the corrected multi-sensor fleet path into an operator-grade signal inspection and validation workflow. Work proceeds from trustworthy signal/provenance contracts through identity-safe ingestion, a bounded responsive viewer, independent full-rate export evidence, and finally a calibrated physical remap test that proves the same full-MAC identity agrees across Studio, recording, and the native OpenSim visualizer.

## Milestones

- **v1.1 Acquisition Operations** - Phases 5-8 completed and archived.
- **v1.2 Block Deployment** - Parked without phases.
- **v1.3 Acquisition Integrity** - Unfinished prior scope remains preserved in existing artifacts.
- **v1.4 OpenSim Quaternion Live Link** - Phase 15 implemented.
- **v1.5 OpenSim IK + Calibration + Visualizer Control** - Phases 16-19 completed.
- **v1.6 Multi-Sensor Bone Mapping** - Phases 20-25 completed on 2026-08-05.
- **v1.7 Multi-Sensor Signal Viewer & 3D Mapping Validation** - Phases 26-30 active.

## Phases

- [ ] **Phase 26: Signal Contract and Provenance** - Every sample has trustworthy identity, timing, capability, units, and applied-mapping meaning.
- [ ] **Phase 27: Identity-Safe Multi-Sensor Ingestion** - Every known ESP reaches the viewer independently with stable identity and explicit reconnect/remap boundaries.
- [ ] **Phase 28: Bounded Signal Viewer and Controls** - Operators can inspect and compare responsive stacked traces without affecting acquisition, recording, or OpenSim.
- [ ] **Phase 29: Full-Rate Export Integrity** - Recorded evidence retains full-rate values and provenance independently of all display behavior.
- [ ] **Phase 30: Calibrated 3D Remap Acceptance** - Physical evidence proves full-MAC mappings follow applied swaps and reconnects into the expected native OpenSim segments.

## Phase Details

### Phase 26: Signal Contract and Provenance

**Goal**: Operators can trust the identity, timing, validity, units, capabilities, and applied mapping attached to every displayed or exported sample.
**Depends on**: Phase 25
**Requirements**: SIG-01, SIG-02, SIG-03, SIG-04, SIG-05
**Success Criteria** (what must be TRUE):

  1. Operator can inspect lossless raw accel, gyro, and magnetometer counts whose samples retain full MAC, acquisition time or sequence, reconnect epoch, and channel capabilities.
  2. Operator can switch accel and gyro channels to validated SI values while raw counts remain available and unchanged.
  3. Operator sees magnetometer values labelled in microtesla only when sensor sensitivity and calibration provenance validate; otherwise SI is explicitly unavailable.
  4. Live and historical labels reflect only the authoritative applied mapping revision, exact segment, and frame, never a draft assignment.
  5. Quaternion channels appear only for sources declaring valid quaternion capability, and missing or invalid orientation is visibly unavailable rather than fabricated.

**Plans**: TBD
**UI hint**: yes

### Phase 27: Identity-Safe Multi-Sensor Ingestion

**Goal**: Operators can discover and follow every saved or connected ESP as an independent, stable signal source across reconnect and remap boundaries.
**Depends on**: Phase 26
**Requirements**: VIEW-01, VIEW-06
**Success Criteria** (what must be TRUE):

  1. Operator sees connected and saved ESP sources populate automatically with full MAC, role, connection state, rate/errors, and applied body part, including stable offline entries.
  2. Reconnecting a device produces an explicit visible gap and begins a new reconnect epoch instead of joining old and new samples silently.
  3. Applying a remap begins a new provenance epoch, and already buffered samples retain their original applied labels rather than being relabelled.

**Plans**: TBD
**UI hint**: yes

### Phase 28: Bounded Signal Viewer and Controls

**Goal**: Operators can responsively inspect and compare all available IMU channels while display choices remain isolated from authoritative data paths.
**Depends on**: Phase 27
**Requirements**: VIEW-02, VIEW-03, VIEW-04, VIEW-05, PERF-01, PERF-02
**Success Criteria** (what must be TRUE):

  1. Operator can view one ESP as stacked scrolling traces for all nine IMU components and any valid quaternion components, with synchronized time axes and persistent full-MAC/body-part labels.
  2. Operator can compare selected ESPs or the same channel across devices without losing device identity or time alignment.
  3. Operator can change group/channel visibility, raw or SI presentation, time window, local pause, vertical zoom/scale, and autoscale without interrupting incoming data.
  4. Viewer pause, visibility, scaling, and display reduction leave acquisition, health/services, recording, and OpenSim input counts and behavior unchanged.
  5. At the tested fleet/channel envelope, long-running memory stays bounded and extrema remain visible while the display sustains a responsive 20-30 FPS and exposes backlog, drops, freshness, and effective-rate diagnostics.

**Plans**: TBD
**UI hint**: yes

### Phase 29: Full-Rate Export Integrity

**Goal**: Operators can retain authoritative full-rate multi-sensor evidence whose identity and values reconcile with the displayed traces.
**Depends on**: Phase 28
**Requirements**: EXP-01, EXP-02, EXP-03
**Success Criteria** (what must be TRUE):

  1. Operator can record and export every configured canonical source at full received rate regardless of browser buffering, frame rate, visibility, pause, or display downsampling.
  2. Exported samples preserve timestamp or sequence, full MAC, role, channel, raw and applicable SI values/units, mapping revision, segment, frame, and provenance epoch.
  3. Automated reconciliation confirms that displayed trace identity, value, and time correspond to the authoritative export while allowing the display to render fewer points than were recorded.

**Plans**: TBD

### Phase 30: Calibrated 3D Remap Acceptance

**Goal**: Operators have retained physical evidence that applied full-MAC mappings determine which calibrated native OpenSim segment responds.
**Depends on**: Phase 29
**Requirements**: UAT-01, UAT-02, UAT-03, UAT-04
**Success Criteria** (what must be TRUE):

  1. Operator can Identify each physical ESP, apply a baseline mapping, recalibrate, move one sensor at a time, and retain evidence that the expected native OpenSim segment responds.
  2. Operator can atomically swap two segment assignments in Studio, recalibrate, and retain evidence that the responding native OpenSim segments swap with the full-MAC devices.
  3. After remap and reconnect, the same full MAC regains the expected applied label, export provenance, and observed 3D segment response without depending on role, route, or discovery order.
  4. The acceptance evidence clearly limits its conclusion to routing and visual segment correspondence for the tested configuration and makes no clinical, anatomical-accuracy, or biomechanical-validity claim.

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:** Phase 26 -> Phase 27 -> Phase 28 -> Phase 29 -> Phase 30

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 26. Signal Contract and Provenance | 0/TBD | Not started | - |
| 27. Identity-Safe Multi-Sensor Ingestion | 0/TBD | Not started | - |
| 28. Bounded Signal Viewer and Controls | 0/TBD | Not started | - |
| 29. Full-Rate Export Integrity | 0/TBD | Not started | - |
| 30. Calibrated 3D Remap Acceptance | 0/TBD | Not started | - |

---
*Roadmap created: 2026-08-13 for milestone v1.7*
