# Roadmap: Rehab Robotics Studio

## Overview

Milestone v1.7 turns the corrected multi-sensor fleet path into an operator-grade full-body signal inspection and OpenSim workflow. Work proceeds from trustworthy signal/provenance contracts through a compatible full-body model and mapping vocabulary, measured fleet-scale ingestion, a bounded Open Ephys-style viewer, independent full-rate export, simultaneous full-body calibration/official IK, and retained physical acceptance evidence.

## Milestones

- **v1.1 Acquisition Operations** - Phases 5-8 completed and archived.
- **v1.2 Block Deployment** - Parked without phases.
- **v1.3 Acquisition Integrity** - Unfinished prior scope remains preserved in existing artifacts.
- **v1.4 OpenSim Quaternion Live Link** - Phase 15 implemented.
- **v1.5 OpenSim IK + Calibration + Visualizer Control** - Phases 16-19 completed.
- **v1.6 Multi-Sensor Bone Mapping** - Phases 20-25 completed on 2026-08-05.
- **v1.7 Multi-Sensor Signal Viewer & Full-Body 3D Mapping Validation** - Phases 26-32 active.

## Phases

- [x] **Phase 26: Signal Contract and Provenance** - Every channel sample has trustworthy identity, timing, capability, units, and applied-mapping meaning. (completed 2026-08-17)
- [ ] **Phase 27: Full-Body Model and Mapping Vocabulary** - Studio exposes exact compatible Frames for all required head, trunk, arm, and leg segments.
- [ ] **Phase 28: Fleet-Scale Identity-Safe Ingestion** - The required full-body sensor fleet reaches the viewer independently with measured capacity and explicit reconnect/remap boundaries.
- [ ] **Phase 29: Bounded Signal Viewer and Controls** - Operators can inspect and compare responsive stacked traces without affecting authoritative data paths.
- [ ] **Phase 30: Full-Rate Export Integrity** - Recorded evidence retains full-rate values and provenance independently of all display behavior.
- [ ] **Phase 31: Full-Body Calibration and Official OpenSim IK** - One complete synchronized mapped sensor set drives provenance-bound full-body joint output and native visualization.
- [ ] **Phase 32: Full-Body Physical Acceptance** - Physical evidence proves full-MAC mappings, remaps, reconnects, exports, and simultaneous full-body 3D response agree.

## Phase Details

### Phase 26: Signal Contract and Provenance

**Goal**: Operators can trust the identity, timing, validity, units, capabilities, and applied mapping attached to every displayed or exported sample.
**Depends on**: Phase 25
**Requirements**: SIG-01, SIG-02, SIG-03, SIG-04, SIG-05
**Success Criteria**:

1. Raw accel, gyro, and magnetometer samples retain full MAC, acquisition time/sequence, reconnect epoch, and channel capabilities.
2. Accel and gyro switch between lossless raw counts and validated SI values.
3. Magnetometer values show microtesla only with validated sensitivity/calibration provenance; otherwise SI is explicitly unavailable.
4. Labels use the authoritative applied revision and exact segment/frame, never drafts, while invalid quaternion data remains unavailable rather than fabricated.

**Plans**: 6 plans

Plans:
**Wave 1**

- [x] 26-01-PLAN.md — Define the immutable backend canonical contract and shared cross-language fixture.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 26-02-PLAN.md — Implement strict TypeScript contract and conversion parity.
- [x] 26-03-PLAN.md — Publish additive canonical envelopes with session and applied provenance.

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 26-04-PLAN.md — Validate dynamic rosbridge ingress and separate applied mapping state.

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 26-05-PLAN.md — Carry latest accepted samples and bounded rejections through SignalBus.

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 26-06-PLAN.md — Deliver the accessible responsive Signal Contract inspector.

**UI hint**: yes

### Phase 27: Full-Body Model and Mapping Vocabulary

**Goal**: Operators can map sensors to a compatible model-derived full-body Frame set without lower-body hard-coding.
**Depends on**: Phase 26
**Requirements**: BODY-01, BODY-02
**Success Criteria**:

1. A bundled compatible full-body `.osim` model loads with exact sensor Frames for head, torso, pelvis, and bilateral upper arms, forearms, hands, thighs, shanks, and feet.
2. Every compatible full-body segment/frame appears in Studio directly from the active model catalog.
3. Operators can assign, save, apply, restore, and atomically swap full-body assignments by full MAC while invalid or duplicate candidates fail closed.

**Plans**: TBD
**UI hint**: yes

### Phase 28: Fleet-Scale Identity-Safe Ingestion

**Goal**: Operators can discover and follow the complete supported full-body ESP fleet as stable independent sources across reconnect and remap boundaries.
**Depends on**: Phase 27
**Requirements**: BODY-03, VIEW-01, VIEW-06
**Success Criteria**:

1. Connected and saved sources populate automatically with full MAC, role, state, rate/errors, and applied body part, including stable offline entries.
2. The required full-body sensor count operates within a measured rate/drop/reconnect/synchronization envelope rather than the previous assumed six-route limit.
3. Reconnect produces an explicit gap and new reconnect epoch without silently joining samples.
4. Apply/remap produces a new provenance epoch while buffered historical samples retain their original labels.

**Plans**: TBD
**UI hint**: yes

### Phase 29: Bounded Signal Viewer and Controls

**Goal**: Operators can responsively inspect and compare all available IMU channels while display choices remain isolated from authoritative paths.
**Depends on**: Phase 28
**Requirements**: VIEW-02, VIEW-03, VIEW-04, VIEW-05, PERF-01, PERF-02
**Success Criteria**:

1. One selected ESP renders stacked synchronized traces for nine IMU components and valid quaternion components with persistent MAC/body labels.
2. Selected ESPs or the same channel across devices can be compared on synchronized axes without losing identity.
3. Group/channel visibility, raw/SI, time window, local pause, vertical scale/zoom, and autoscale work without interrupting incoming data.
4. Viewer behavior leaves acquisition, health/services, recording, and OpenSim input unchanged.
5. At the supported full-body fleet envelope, memory remains bounded, extrema remain visible, and display sustains 20-30 FPS with backlog/drop/freshness/effective-rate diagnostics.

**Plans**: TBD
**UI hint**: yes

### Phase 30: Full-Rate Export Integrity

**Goal**: Operators can retain authoritative full-rate full-body evidence whose identity and values reconcile with displayed traces.
**Depends on**: Phase 29
**Requirements**: EXP-01, EXP-02, EXP-03
**Success Criteria**:

1. Every configured canonical source records/exports at full received rate regardless of viewer state or display downsampling.
2. Export preserves time/sequence, full MAC, role, channel, raw/applicable SI values and units, mapping revision, segment, frame, and provenance epoch.
3. Automated reconciliation proves displayed trace identity/value/time corresponds to full-rate export while allowing fewer rendered points.

**Plans**: TBD

### Phase 31: Full-Body Calibration and Official OpenSim IK

**Goal**: Operators can calibrate one complete mapped full-body sensor set and receive official synchronized full-body OpenSim joint output and visualization.
**Depends on**: Phase 30
**Requirements**: BODY-04, BODY-05, BODY-06
**Success Criteria**:

1. Calibration captures the exact model hash, applied mapping revision, ordered full-MAC/frame set, solver profile, and per-sensor mounting offsets.
2. Official OpenSim IK consumes the complete synchronized full-body set and publishes all configured full-body joint coordinates.
3. Missing, stale, pre-reconnect, or skewed required sensors suppress new full-body IK output with actionable per-device status while acquisition/recording continue.
4. Native visualization responds across head, trunk, bilateral arms, and bilateral legs with mapping/calibration/solver provenance visible in Studio.

**Plans**: TBD
**UI hint**: yes

### Phase 32: Full-Body Physical Acceptance

**Goal**: Operators have retained physical evidence that full-MAC mappings determine the expected native OpenSim regions before and after remap/reconnect.
**Depends on**: Phase 31
**Requirements**: UAT-01, UAT-02, UAT-03, UAT-04, UAT-05
**Success Criteria**:

1. Each physical ESP is Identified, mapped, calibrated, and moved independently with evidence that its expected model segment responds.
2. Two assignments can be atomically swapped, recalibrated, and shown to swap their responding native OpenSim segments with the full-MAC devices.
3. Remap/reconnect restores the same MAC's applied label, trace identity, export provenance, and observed 3D response independent of role/route/order.
4. A complete supported full-body configuration produces retained simultaneous joint-output and native 3D response evidence by body region.
5. Acceptance explicitly limits conclusions to routing and visual correspondence and makes no clinical/anatomical/biomechanical accuracy claim.

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:** Phase 26 -> Phase 27 -> Phase 28 -> Phase 29 -> Phase 30 -> Phase 31 -> Phase 32

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 26. Signal Contract and Provenance | 6/6 | Complete   | 2026-08-17 |
| 27. Full-Body Model and Mapping Vocabulary | 0/TBD | Not started | - |
| 28. Fleet-Scale Identity-Safe Ingestion | 0/TBD | Not started | - |
| 29. Bounded Signal Viewer and Controls | 0/TBD | Not started | - |
| 30. Full-Rate Export Integrity | 0/TBD | Not started | - |
| 31. Full-Body Calibration and Official OpenSim IK | 0/TBD | Not started | - |
| 32. Full-Body Physical Acceptance | 0/TBD | Not started | - |

---
*Roadmap revised: 2026-08-13 after full-body IK scope expansion*
