# Requirements: Rehab Robotics Studio

**Defined:** 2026-07-27
**Milestone:** v1.4 OpenSim Quaternion Live Link
**Core Value:** Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.

## v1.4 Requirements

### Quaternion Live Link

- [ ] **LINK-01**: An operator can launch `opensim_bridge` with configurable master and slave `sensor_msgs/Imu` input topics.
- [ ] **LINK-02**: The bridge reads the orientation quaternion from each ESP IMU message and converts it through one documented ROS-to-OpenSim convention boundary.
- [ ] **LINK-03**: The operator can map each ESP input to a named OpenSim model frame without changing source code.
- [ ] **LINK-04**: Valid incoming orientations update the corresponding frames in a running OpenSim model or native OpenSim visualizer demonstration.
- [ ] **LINK-05**: Missing OpenSim runtime/model assets, invalid quaternions, unknown frame mappings, and stale subscriptions produce visible status instead of silent failure.
- [ ] **LINK-06**: A deterministic local publisher/test proves that known quaternion messages reach the bridge and produce the expected OpenSim orientation update without connected ESP hardware.

## Future Requirements

### OpenSim IK

- **IK-01**: Calibrate sensor-to-model mounting orientations from a known pose.
- **IK-02**: Run persistent real-time inverse kinematics and publish joint angles.
- **IK-03**: Validate solved coordinates, synchronization, latency, and biomechanical accuracy.

### Visualization

- **VIS-01**: Render the solved OpenSim model inside Rehab Robotics Studio.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Inverse kinematics and joint-angle publication | The milestone first proves that OpenSim can receive the existing ESP quaternion streams. |
| Full calibration workflow | Fixed/configured frame mapping is sufficient for the live-link prototype. |
| Jetson production packaging | Deployment architecture follows after the local OpenSim path is demonstrated. |
| Embedded Studio 3D rendering | OpenSim's native visualizer is sufficient for this prototype. |
| Clinical or biomechanical validity claims | No IK or external-reference validation is included. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| LINK-01 | Phase 15 | Pending |
| LINK-02 | Phase 15 | Pending |
| LINK-03 | Phase 15 | Pending |
| LINK-04 | Phase 15 | Pending |
| LINK-05 | Phase 15 | Pending |
| LINK-06 | Phase 15 | Pending |

**Coverage:**
- v1.4 requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0

---
*Requirements defined: 2026-07-27*
*Last updated: 2026-07-27 after scope reduction*
