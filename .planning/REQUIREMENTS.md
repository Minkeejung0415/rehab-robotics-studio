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

## Traceability

Traceability is populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SIG-01 | TBD | Pending |
| SIG-02 | TBD | Pending |
| SIG-03 | TBD | Pending |
| SIG-04 | TBD | Pending |
| SIG-05 | TBD | Pending |
| VIEW-01 | TBD | Pending |
| VIEW-02 | TBD | Pending |
| VIEW-03 | TBD | Pending |
| VIEW-04 | TBD | Pending |
| VIEW-05 | TBD | Pending |
| VIEW-06 | TBD | Pending |
| PERF-01 | TBD | Pending |
| PERF-02 | TBD | Pending |
| EXP-01 | TBD | Pending |
| EXP-02 | TBD | Pending |
| EXP-03 | TBD | Pending |
| UAT-01 | TBD | Pending |
| UAT-02 | TBD | Pending |
| UAT-03 | TBD | Pending |
| UAT-04 | TBD | Pending |

**Coverage:**
- v1.7 requirements: 20 total
- Mapped to phases: 0
- Unmapped: 20

---
*Requirements defined: 2026-08-13*
*Last updated: 2026-08-13 after v1.7 scope approval*
