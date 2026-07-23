# Requirements: Rehab Robotics Studio

**Defined:** 2026-07-23
**Milestone:** v1.3 Acquisition Integrity
**Core Value:** Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.

## v1.3 Requirements

### Measurement Integrity

- [ ] **DATA-01**: An operator receives acceleration and angular velocity converted with each device's confirmed active accelerometer and gyroscope ranges.
- [ ] **DATA-02**: Published raw and live acquisition data carries sufficient range or unit metadata for backend and GUI consumers to interpret samples consistently.
- [ ] **TIME-01**: Synchronized device acquisition time survives firmware transport, backend parsing, ROS publication, and rosbridge delivery.
- [ ] **TIME-02**: TCP and UDP acquisition frames expose meaningful monotonic sequence values suitable for detecting gaps and reordering.
- [ ] **ORIENT-01**: Filtered quaternions handle equivalent antipodal inputs and remain normalized, finite, and valid orientations.

### Control And Recovery

- [ ] **CTRL-04**: Pausing live sample rendering does not block ROS service responses or create false control-command timeouts.
- [ ] **RECOV-01**: After fallback to mock data, an operator can reconnect live ROS acquisition without reloading the application.
- [ ] **RECOV-02**: Obsolete WebSocket callbacks cannot overwrite a newer connection, and established connection loss enters a controlled recovery state.

### Fresh Health

- [ ] **HEALTH-04**: Pair availability expires when slave-health updates exceed a defined freshness threshold.
- [ ] **HEALTH-05**: Stream and pair indicators clear or age offline after socket loss, acquisition stop/restart, or a sustained absence of valid frames.

### Verification

- [ ] **VERIFY-05**: Automated regression tests cover non-default scale conversion, timestamp and sequence preservation, quaternion geometry, paused service replies, socket-generation and fallback recovery, and health expiry.

## Future Requirements

### Block Deployment

- **DEPLOY-01**: Generate a typed ROS processing-block update draft whenever a valid processing block is connected directly to a source block.
- **DEPLOY-02**: Publish a finalized processing-block update when the operator deploys the graph.
- **DEPLOY-03**: Package one language-neutral source entry file with manifest YAML, dependencies, graph identity, revision, checksum, and deployment metadata.
- **DEPLOY-04**: Provide a local ROS observer or inspection path that verifies generated messages while the Jetson is disconnected.

## Out Of Scope

| Feature | Reason |
|---------|--------|
| Physical E-STOP and motor-driver integration | Audit finding 1 is safety-critical but requires a separately approved hardware and fail-safe scope. |
| Graph-load validation and ID restoration | Audit finding 8 is deferred until acquisition correctness and recovery are stable. |
| Docker packaging, stale aggregator, and documentation cleanup | Audit findings 9-10 are deferred from v1.3. |
| General streaming and GUI performance optimization | v1.3 addresses confirmed correctness defects; optimization follows measurement and recovery verification. |
| Block Deployment implementation | The former v1.2 scope is preserved as future work and will resume after acquisition integrity. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 9 | Pending |
| DATA-02 | Phase 9 | Pending |
| TIME-01 | Phase 10 | Pending |
| TIME-02 | Phase 10 | Pending |
| ORIENT-01 | Phase 10 | Pending |
| CTRL-04 | Phase 11 | Pending |
| RECOV-01 | Phase 11 | Pending |
| RECOV-02 | Phase 11 | Pending |
| HEALTH-04 | Phase 12 | Pending |
| HEALTH-05 | Phase 12 | Pending |
| VERIFY-05 | Phase 13 | Pending |

**Coverage:**
- v1.3 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0

---
*Requirements defined: 2026-07-23*
*Last updated: 2026-07-23 after v1.3 roadmap creation*
