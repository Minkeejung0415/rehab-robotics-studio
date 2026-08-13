# Requirements: Rehab Robotics Studio

**Defined:** 2026-08-13
**Milestone:** v1.7 Multi-Sensor Signal Viewer & 3D Mapping Validation
**Core Value:** Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.

## v1.7 Requirements

### Signal Contract

- [ ] **SIG-01**: Every viewer sample preserves full device MAC, acquisition timestamp or sequence, reconnect epoch, and channel-capability metadata.
- [ ] **SIG-02**: Operator can inspect lossless raw counts for ax/ay/az, gx/gy/gz, and mx/my/mz and switch accelerometer and gyroscope channels to validated SI values.
- [ ] **SIG-03**: Operator can view mx/my/mz in validated microtesla using an explicit sensor-sensitivity and magnetometer-calibration contract.
- [ ] **SIG-04**: Viewer and export labels use only the authoritative applied mapping revision and exact segment/frame; an unsaved or saved draft never relabels live or historical samples.
- [ ] **SIG-05**: Quaternion channels appear only when the source declares valid quaternion capability; missing or invalid orientation is never fabricated as an identity quaternion.

### Signal Viewer

- [ ] **VIEW-01**: Operator sees connected and saved ESP sources automatically, identified by full MAC, role, connection state, rate/errors, and applied body part.
- [ ] **VIEW-02**: Operator can view one selected ESP as Open Ephys-style stacked scrolling traces for nine IMU components plus available qw/qx/qy/qz channels.
- [ ] **VIEW-03**: Operator can select multiple ESPs or the same channel across devices for synchronized comparison without losing full-MAC/body-part identity.
- [ ] **VIEW-04**: Operator can control sensor-group and individual-channel visibility, raw/SI units, time window, local pause, vertical scale/zoom, and autoscale.
- [ ] **VIEW-05**: Viewer pause, visibility, scaling, and downsampling never pause acquisition, suppress health or service responses, alter recording, or change OpenSim input.
- [ ] **VIEW-06**: Reconnects render explicit gaps and remaps create a new provenance epoch; buffered samples are never silently joined or relabelled across either boundary.

### Full-Body Mapping and IK

- [ ] **BODY-01**: Operator can load a bundled compatible full-body `.osim` model whose catalog exposes exact sensor Frames for head, torso, pelvis, and bilateral upper arms, forearms, hands, thighs, shanks, and feet.
- [ ] **BODY-02**: Operator can assign any known ESP to every supported full-body segment using exact model-derived segment/frame choices without lower-body hard-coding.
- [ ] **BODY-03**: Fleet routing and diagnostics support the simultaneous sensor count required by the selected full-body solver profile, with measured rate, drop, reconnect, and synchronization limits.
- [ ] **BODY-04**: Operator can capture one provenance-bound full-body calibration artifact containing the exact model hash, applied revision, ordered full-MAC/frame set, and per-sensor mounting offsets.
- [ ] **BODY-05**: Official OpenSim IK consumes the complete synchronized full-body sensor set and publishes all configured full-body joint coordinates while suppressing output when required inputs are incomplete, stale, or skewed.
- [ ] **BODY-06**: Native OpenSim visualization visibly responds across mapped head, trunk, bilateral arm, and bilateral leg segments, with solver/input validity and mapping provenance available to Studio.

### Performance

- [ ] **PERF-01**: Long-running viewer memory remains bounded through fixed-capacity typed rings and extrema-preserving display projection rather than unbounded arrays or shift/copy buffers.
- [ ] **PERF-02**: The tested device/channel envelope sustains a responsive 20–30 FPS display and exposes viewer backlog, source drops, freshness, and effective display rate diagnostics.

### Recording and Export

- [ ] **EXP-01**: Full-rate recording and export remain upstream and independent of browser buffering, frame rate, visibility, pause, and display downsampling.
- [ ] **EXP-02**: Exported samples preserve timestamp/sequence, full MAC, role, channel, raw and applicable SI values/units, mapping revision, segment, frame, and provenance epoch.
- [ ] **EXP-03**: Automated reconciliation verifies displayed trace identity/value/time against the corresponding full-rate export without requiring every recorded sample to be rendered.

### Physical 3D Validation

- [ ] **UAT-01**: Operator can Identify each physical ESP, apply mapping A, recalibrate, move one sensor at a time, and retain evidence that the expected native OpenSim segment responds.
- [ ] **UAT-02**: Operator can swap two segment assignments in Studio, Apply, recalibrate, and retain evidence that the responding native OpenSim segments swap with the full-MAC devices.
- [ ] **UAT-03**: After remap and device reconnect, applied mapping, viewer labels, export provenance, and observed 3D segment response reattach to the same full MAC.
- [ ] **UAT-04**: Acceptance reports only routing and visual segment correspondence; it makes no clinical, anatomical-accuracy, or biomechanical-validity claim.
- [ ] **UAT-05**: A complete supported full-body sensor configuration is Identified, mapped, calibrated, moved by body region, and retained as evidence that all required full-body joint outputs and native 3D regions respond simultaneously.

## Future Requirements

### Advanced Analysis

- **ANLY-01**: Operator can run spectral, FFT, event-aligned, and offline review tools over recorded channels.
- **ANLY-02**: Operator can define arbitrary derived channels and processing expressions in the live viewer.
- **ANLY-03**: Operator can synchronize external force, EMG, video, or laboratory reference systems with the IMU trace timeline.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Clinical or biomechanical accuracy claims | v1.7 validates routing and visual correspondence only; accuracy needs an external-reference protocol. |
| Embedded replacement for the native OpenSim 3D renderer | The existing native visualizer remains the authoritative 3D surface for this milestone. |
| Unbounded waveform history in the browser | Conflicts with deterministic long-running memory and responsiveness. |
| Display settings that modify acquisition or recording | The viewer is observational; control and full-rate data paths remain independent. |
| Fabricated magnetometer SI or quaternion values | Values must remain raw/unavailable until their capability and calibration contracts validate them. |
| WebGL, OffscreenCanvas, or worker architecture by default | Research found Canvas/uPlot plus typed rings sufficient; add complexity only if measured capacity requires it. |
| Partial-sensor output presented as complete full-body IK | Missing required sensors must be explicit and suppress the selected full-body profile rather than producing misleading output. |

## Traceability

Traceability is populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SIG-01 | Phase 26 | Pending |
| SIG-02 | Phase 26 | Pending |
| SIG-03 | Phase 26 | Pending |
| SIG-04 | Phase 26 | Pending |
| SIG-05 | Phase 26 | Pending |
| VIEW-01 | Phase 28 | Pending |
| VIEW-02 | Phase 29 | Pending |
| VIEW-03 | Phase 29 | Pending |
| VIEW-04 | Phase 29 | Pending |
| VIEW-05 | Phase 29 | Pending |
| VIEW-06 | Phase 28 | Pending |
| BODY-01 | Phase 27 | Pending |
| BODY-02 | Phase 27 | Pending |
| BODY-03 | Phase 28 | Pending |
| BODY-04 | Phase 31 | Pending |
| BODY-05 | Phase 31 | Pending |
| BODY-06 | Phase 31 | Pending |
| PERF-01 | Phase 29 | Pending |
| PERF-02 | Phase 29 | Pending |
| EXP-01 | Phase 30 | Pending |
| EXP-02 | Phase 30 | Pending |
| EXP-03 | Phase 30 | Pending |
| UAT-01 | Phase 32 | Pending |
| UAT-02 | Phase 32 | Pending |
| UAT-03 | Phase 32 | Pending |
| UAT-04 | Phase 32 | Pending |
| UAT-05 | Phase 32 | Pending |

**Coverage:**
- v1.7 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0

---
*Requirements defined: 2026-08-13*
*Last updated: 2026-08-13 after full-body IK scope expansion*
