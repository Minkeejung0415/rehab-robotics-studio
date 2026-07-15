# Requirements: Rehab Robotics Studio

**Defined:** 2026-07-15
**Core Value:** Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.

## v1 Requirements

### Live Ingestion

- [ ] **INGEST-01**: The bridge completes the plugin-compatible TCP `REDPITAYA`/`START` handshake and accepts only UDP live transport.
- [ ] **INGEST-02**: Each bridge validates UDP source, header fields, payload bounds, and 14-channel frame shape before parsing samples.
- [ ] **INGEST-03**: Master and slave bridges publish canonical `oe_esp32.raw.v1` JSON payloads to `/esp/raw/{role}` with role, ID, segment, IMU, quaternion, DIO, and sync metadata.

### Processing Pipeline

- [ ] **PIPE-01**: Filter nodes consume raw JSON and publish metadata-preserving filtered JSON to `/esp/filtered/{role}`.
- [ ] **PIPE-02**: An OpenSim adapter forwards a configurable filtered topic to a configurable UDP endpoint.
- [ ] **PIPE-03**: A recorder writes non-blocking, per-topic JSONL session files and reports file errors.
- [ ] **PIPE-04**: A status node reports configured topics, endpoints, and observable pipeline health.

### Deployment

- [ ] **LAUNCH-01**: A single launch file configures and starts master/slave bridges, filters, OpenSim forwarding, optional recording, status, and GUI rosbridge access.

### Verification

- [ ] **VERIFY-01**: Automated tests cover frame validation, JSON conversion, filtering, OpenSim payloads, recording, and launch configuration.
- [ ] **VERIFY-02**: An offline replay path demonstrates the complete topic chain without ESP32 hardware.

## v2 Requirements

### GUI Hardware Runtime

- **GUI-01**: The React application replaces its mock source with a production rosbridge data source.

## Out of Scope

| Feature | Reason |
|---------|--------|
| ESP32 firmware protocol redesign | This milestone must follow the existing plugin protocol. |
| Motor control and EtherCAT integration | It is outside the wearable IMU processing pipeline. |
| Production GUI rosbridge client | Backend contract stability comes first. |
| ROS bag recording | Plugin-compatible JSONL recording is sufficient for this milestone. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGEST-01 | Phase 1 | Pending |
| INGEST-02 | Phase 1 | Pending |
| INGEST-03 | Phase 1 | Pending |
| PIPE-01 | Phase 2 | Pending |
| PIPE-02 | Phase 2 | Pending |
| PIPE-03 | Phase 2 | Pending |
| PIPE-04 | Phase 3 | Pending |
| LAUNCH-01 | Phase 3 | Pending |
| VERIFY-01 | Phase 4 | Pending |
| VERIFY-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0

---
*Requirements defined: 2026-07-15*
*Last updated: 2026-07-15 after research confirmation*
