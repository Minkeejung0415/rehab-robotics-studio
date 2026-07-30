# Roadmap: Rehab Robotics Studio

## Overview

Milestone v1.6 generalizes the existing fixed Master/Slave acquisition and OpenSim path into an identity-safe multi-sensor workflow. Work proceeds from verified hardware identity through isolated fleet routing, authoritative model and mapping revisions, dynamic N-sensor calibration and IK, the operator mapping workspace, and finally hardware-backed compatibility evidence before dynamic mode can become the default.

## Milestones

- **v1.1 Acquisition Operations** - Phases 5-8 completed and archived.
- **v1.2 Block Deployment** - Parked without phases.
- **v1.3 Acquisition Integrity** - Unfinished prior scope remains preserved in existing artifacts.
- **v1.4 OpenSim Quaternion Live Link** - Phase 15 implemented.
- **v1.5 OpenSim IK + Calibration + Visualizer Control** - Phases 16-19 completed.
- **v1.6 Multi-Sensor Bone Mapping** - Phases 20-25 planned.

## Phases

- [ ] **Phase 20: Full Identity and Confirmed Identify** - Every Master and Slave has a verified stable identity and a safely acknowledged physical Identify action.
- [ ] **Phase 21: N-Route Relay and Canonical ROS Fleet** - All devices remain independently discoverable, routed, observable, and compatible with explicit legacy aliases.
- [ ] **Phase 22: Model Catalog, Mapping Store, and Transactional Contracts** - Model-derived assignments are validated, revisioned, persisted, and applied atomically.
- [ ] **Phase 23: N-Sensor Calibration and Official OpenSim IK** - Applied mappings drive provenance-bound calibration and valid synchronized N-sensor OpenSim solves.
- [ ] **Phase 24: Rosbridge and Studio Mapping Workspace** - Operators manage the authoritative fleet mapping through stable, actionable device rows.
- [ ] **Phase 25: Multi-Device Compatibility and Promotion Gate** - Deterministic and physical acceptance evidence preserves existing workflows and determines default-mode readiness.

## Phase Details

### Phase 20: Full Identity and Confirmed Identify

**Goal**: Operators can reliably distinguish and physically identify every Master and Slave without disrupting live work.
**Depends on**: Phase 19
**Requirements**: ID-01, ID-03
**Success Criteria** (what must be TRUE):

  1. Operator can see a verified, normalized full 48-bit identity for the Master and every discovered Slave, with role, IP address, and transport MAC shown as separate metadata.
  2. A physical device retains the same canonical identity across DHCP changes, reconnects, and discovery-order changes, while the canonical data-topic instantiation remains owned by Phase 21.
  3. Operator can target exactly one device with a bounded, non-blocking LED Identify action and see whether it was confirmed, timed out, offline, unsupported, or rejected without interrupting acquisition or recording.

**Plans**: 6 plans

Plans:
**Wave 1**

- [x] 20-01-PLAN.md — Firmware full identity and confirmed non-blocking Identify

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 20-02-PLAN.md — Identity-confirmed relay sessions and DHCP-safe launch
- [ ] 20-04-PLAN.md — Hardware-only LED pin and active-level verification

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 20-03-PLAN.md — Stable canonical ROS topics and typed Identify service

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 20-05-PLAN.md — Evidence-backed board activation and operator runbook

**Wave 5** *(blocked on Wave 4 completion)*

- [ ] 20-06-PLAN.md — Final local and Master-plus-two-Slave acceptance

### Phase 21: N-Route Relay and Canonical ROS Fleet

**Goal**: Operators can observe and use every known IMU through failure-isolated, identity-keyed ROS routes.
**Depends on**: Phase 20
**Requirements**: ID-02, FLEET-01, FLEET-02, FLEET-03
**Success Criteria** (what must be TRUE):

  1. Operator can see the Master and every current or previously known Slave in one MAC-keyed fleet registry with distinct discovery, command, route, orientation freshness, synchronization, and rate states.
  2. Each device publishes canonical per-MAC IMU and health data on the same topics after DHCP, reconnect, or ordering changes, while fixed Master/Slave aliases remain explicitly bound to identities and carry matching data.
  3. A failed, stale, or reconnecting route does not stop acquisition, health, Identify, or recording for other devices, and its bounded queue, drop, and reconnect diagnostics remain visible.

**Plans**: TBD

### Phase 22: Model Catalog, Mapping Store, and Transactional Contracts

**Goal**: Operators can create, save, restore, and atomically apply a valid mapping against the exact loaded OpenSim model.
**Depends on**: Phase 21
**Requirements**: MODEL-01, MODEL-02, MODEL-03, MAP-01, MAP-02, MAP-03, MAP-04, MAP-05, MAP-06
**Success Criteria** (what must be TRUE):

  1. The loaded `.osim` model is identified by the SHA-256 hash of its exact bytes, and assignment choices contain only exact non-Ground model segments and compatible sensor Frames reported by that model.
  2. Missing, ambiguous, or unsupported Frames fail closed with an actionable reason and never trigger a fuzzy selection or source-model modification.
  3. Operator can mark every known device Assigned, Not used, or Unassigned, while duplicate, unknown, incomplete, and solver-insufficient candidates are rejected authoritatively.
  4. Desired mappings survive restart and corruption recovery under a versioned, revisioned, atomic backend store; the same MAC reattaches under an unchanged model/revision while a different MAC remains Unassigned.
  5. Apply validates and stages the complete candidate against the expected revision, atomically swaps only on success, preserves the previous applied revision on failure, and remains blocked during calibration capture, recording, or finalization without altering that active operation.

**Plans**: TBD

### Phase 23: N-Sensor Calibration and Official OpenSim IK

**Goal**: Operators receive official OpenSim results only from a complete, current, provenance-matched mapped sensor set.
**Depends on**: Phase 22
**Requirements**: IK-01, IK-02, IK-03, IK-04
**Success Criteria** (what must be TRUE):

  1. Applying or replacing a mapping creates one deterministic ordered N-sensor input set and tears down obsolete MAC-keyed subscriptions, callbacks, and queues without resource growth across repeated remaps.
  2. Calibration artifacts identify the exact model hash, applied mapping revision, device-to-Frame assignments, and solver profile, and become invalid after any semantic change.
  3. Joint states publish only when every required input is valid, fresh, post-reconnect, and within the synchronization-skew bound; degraded inputs suppress new IK output while acquisition and recording continue.
  4. Official OpenSim orientation IK consumes mapped inputs in deterministic order and exposes mapping revision, calibration identity, input validity, solver status, and visualizer provenance.

**Plans**: TBD

### Phase 24: Rosbridge and Studio Mapping Workspace

**Goal**: Operators can identify, assign, validate, save, and apply the multi-sensor mapping from a dedicated Studio workspace without browser state masquerading as runtime truth.
**Depends on**: Phase 23
**Requirements**: UI-01, UI-02, UI-03, UI-04
**Success Criteria** (what must be TRUE):

  1. Operator can open a dedicated mapping panel with stable rows for the Master, all known Slaves, and saved devices that are currently offline.
  2. Each row shows full MAC, role and capabilities, layered readiness, rate and errors, a model-derived segment selector, an explicit Not used option, and a targeted Identify control.
  3. Operator can distinguish Draft, Saved, Applied, and Runtime Ready states and receives immediate conflict feedback plus authoritative validation, interlock, and stale-revision errors.
  4. Reload, reconnect, arbitrary status ordering, and temporary dropout preserve row identity and restore backend state without treating local browser state as applied truth.

**Plans**: TBD
**UI hint**: yes

### Phase 25: Multi-Device Compatibility and Promotion Gate

**Goal**: Operators can rely on both dynamic and legacy workflows within a measured hardware envelope before dynamic mode is promoted.
**Depends on**: Phase 24
**Requirements**: COMP-01, COMP-02, COMP-03
**Success Criteria** (what must be TRUE):

  1. Existing two-sensor startup, pair health, frequency/range controls, recording, calibration, joint-state, graph, and visualizer workflows remain functional through explicit aliases and rollback mode.
  2. Deterministic acceptance tests reproduce and pass full-MAC collision, arbitrary ordering, DHCP/reconnect, Identify failure, partial-Apply rollback, corrupt persistence, stale/skewed input, interlock, and repeated-cleanup cases.
  3. Hardware acceptance states the supported fleet size and rates from Master-plus-multiple-Slave evidence covering Identify safety, acquisition and recording continuity, reconnect, radio/relay load, and OpenSim solve latency.
  4. Dynamic mode becomes the default only when the documented acceptance gate passes; otherwise the tested legacy mode remains available with the unmet evidence visible.

**Plans**: TBD

## Progress

**Execution Order:** Phase 20 -> Phase 21 -> Phase 22 -> Phase 23 -> Phase 24 -> Phase 25

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 20. Full Identity and Confirmed Identify | 2/6 | In Progress | - |
| 21. N-Route Relay and Canonical ROS Fleet | 0/TBD | Not started | - |
| 22. Model Catalog, Mapping Store, and Transactional Contracts | 0/TBD | Not started | - |
| 23. N-Sensor Calibration and Official OpenSim IK | 0/TBD | Not started | - |
| 24. Rosbridge and Studio Mapping Workspace | 0/TBD | Not started | - |
| 25. Multi-Device Compatibility and Promotion Gate | 0/TBD | Not started | - |

---
*Roadmap created: 2026-07-30 for milestone v1.6*
