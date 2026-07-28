# Requirements: Rehab Robotics Studio

**Defined:** 2026-07-28
**Milestone:** v1.5 OpenSim IK + Calibration + Visualizer Control
**Core Value:** Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.

## v1.5 Requirements

### Replace Custom Angle

- [x] **IK-00**: Remove the custom relative-quaternion `/opensim/joint_angle` path and stop presenting it as OpenSim IK in the GUI graph/display.

### Calibration / Mounting Offset

- [x] **IK-01**: Operator can press a top-level toolbar **Calibrate** control to capture a bounded stable window in a fixed standing / knees-extended pose and compute sensor-to-model mounting offsets.
- [x] **IK-02**: Operator can press **Clear cal** to invalidate the active calibration and return to UNCALIBRATED.
- [x] **IK-03**: Joint-angle publication is hard-gated — no IK angles are published until calibration state is CALIBRATED.
- [x] **IK-04**: Calibration status (UNCALIBRATED / CAPTURING / CALIBRATED / FAILED + reason) is visible in the Front Panel OpenSim section.

### Official OpenSim IK

- [ ] **IK-05**: After calibration, OpenSim (OpenSense-compatible orientation IK) solves joint coordinates from the paired master/slave IMU orientations.
- [ ] **IK-06**: Solved coordinates are published on a standard ROS joint-state topic for the GUI to display.
- [ ] **IK-07**: IK validity, residuals, input age, and calibration identity are observable via status/diagnostics (not only logs).

### Visualizer Control

- [ ] **VIS-01**: Operator can press a top-level toolbar button to start/show the OpenSim 3D visualizer when the runtime supports it.
- [ ] **VIS-02**: Visualizer availability / failure reason remains visible when the window cannot open.

## Future Requirements

- Versioned calibration save/load across sessions bound to model/config hashes.
- Multi-pose calibration library and clinical validation protocols.
- Embedded Studio 3D rendering of the solved model (not only native OpenSim window).

## Out of Scope

| Feature | Reason |
|---------|--------|
| Custom relative-quat “IK” as the product angle | Explicitly rejected — must use OpenSim IK |
| Classical marker-based IK | Hardware is IMU-only |
| Clinical accuracy claims | Needs separate external-reference validation |
| Jetson production packaging | Follows after local IK path works |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| IK-00 | Phase 16 | Complete |
| IK-01 | Phase 17 | Complete |
| IK-02 | Phase 17 | Complete |
| IK-03 | Phase 17 | Complete |
| IK-04 | Phase 17 | Complete |
| IK-05 | Phase 18 | Pending |
| IK-06 | Phase 18 | Pending |
| IK-07 | Phase 18 | Pending |
| VIS-01 | Phase 19 | Pending |
| VIS-02 | Phase 19 | Pending |

**Coverage:**
- v1.5 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0

---
*Requirements defined: 2026-07-28*
