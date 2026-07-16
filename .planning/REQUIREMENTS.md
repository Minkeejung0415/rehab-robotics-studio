# Requirements: Rehab Robotics Studio

**Defined:** 2026-07-16
**Milestone:** v1.1 Acquisition Operations
**Core Value:** Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.

## v1.1 Requirements

### Live IMU Controls

- [ ] **CTRL-01**: An operator can enable or disable the ESP32 firmware filter from the IMU acquisition block and sees the confirmed state.
- [ ] **CTRL-02**: An operator can set master/slave accelerometer and gyroscope ranges from the IMU acquisition block and sees the confirmed values.
- [ ] **CTRL-03**: An operator can set the paired hardware rate and each sensor's effective rate, with validation and acknowledgement before the GUI commits the value.

### Recording And Pair Health

- [ ] **HEALTH-01**: An operator can see SD readiness, recording/finalization state, current session ID, sample counts, file size, checksum, and recording errors.
- [ ] **HEALTH-02**: An operator can see master/slave availability, slave recording state, synchronization state, and paired-device errors in one place.
- [ ] **HEALTH-03**: A finalized recording exposes an explicit retrieval/conversion result or a clear actionable failure state.

### Acquisition Diagnostics

- [ ] **DIAG-01**: An operator can see live stream rate, configured hardware rate, connection/reconnect state, and the last valid frame time.
- [ ] **DIAG-02**: Acquisition control or transport failures are surfaced in the GUI with the failed command and a recovery action.

### Verification

- [ ] **VERIFY-03**: Automated tests cover ESP control command parsing, state mapping, and GUI acknowledgement behavior.
- [ ] **VERIFY-04**: A documented USB hardware test validates controls, recording/pair health, and diagnostic status with two connected ESP32s.

## Future Requirements

- **FUTURE-01**: TTL/DIO event markers and broadcast trigger controls.
- **FUTURE-02**: Open Ephys session metadata and event-stream integration.
- **FUTURE-03**: OpenSim Live joint-selection and trigger workflows.

## Out Of Scope

| Feature | Reason |
|---------|--------|
| Neural headstage, impedance, AUX/ADC, or DAC/audio controls | These generic acquisition-board functions do not apply to the paired ESP32 IMU system. |
| ESP32 firmware protocol redesign | This milestone exposes existing plugin-compatible commands. |
| Motor control and EtherCAT | Separate rehabilitation-control scope. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CTRL-01 | Phase 5 | Pending |
| CTRL-02 | Phase 5 | Pending |
| CTRL-03 | Phase 5 | Pending |
| HEALTH-01 | Phase 6 | Pending |
| HEALTH-02 | Phase 6 | Pending |
| HEALTH-03 | Phase 7 | Pending |
| DIAG-01 | Phase 6 | Pending |
| DIAG-02 | Phase 7 | Pending |
| VERIFY-03 | Phase 8 | Pending |
| VERIFY-04 | Phase 8 | Pending |

**Coverage:**
- v1.1 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0

---
*Requirements defined: 2026-07-16*
