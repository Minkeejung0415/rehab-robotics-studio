# Roadmap: Rehab Robotics Studio

## Milestone v1.0: ROS2 Backend Alignment

**Goal:** Make this repository's ROS 2 backend operate like the plugin repository's full ESP32-to-filter-to-OpenSim-to-recording pipeline.

### Phase 1: Plugin-Compatible Ingestion

**Goal:** Replace the divergent local live-bridge behavior with a validated, plugin-compatible TCP-control and UDP-data bridge that emits canonical raw JSON.

**Requirements:** INGEST-01, INGEST-02, INGEST-03

**Success criteria:**
1. A bridge performs the `REDPITAYA` and `START` handshake, rejects non-UDP transport, and reconnects with bounded backoff.
2. UDP packets from an unexpected source or with malformed Open Ephys headers are discarded before parsing.
3. Valid 14-channel frames publish deterministic `oe_esp32.raw.v1` JSON to a role-specific raw topic.
4. Master and slave bridge instances can bind separate UDP ports on one host.

### Phase 2: Processing and Persistence Nodes

**Goal:** Implement plugin-compatible filtering, OpenSim forwarding, and JSONL recording around the canonical raw topic contract.

**Requirements:** PIPE-01, PIPE-02, PIPE-03

**Success criteria:**
1. A filter subscribes to raw JSON and publishes metadata-preserving filtered JSON.
2. The OpenSim adapter sends the selected filtered payload to its configured UDP target.
3. The recorder creates safe per-topic JSONL files without blocking publishers.
4. Each node supports offline input or pure-function paths suitable for tests.

### Phase 3: Workflow Orchestration and Health

**Goal:** Ship a configurable full-workflow launch path with status reporting and rosbridge access for the GUI.

**Requirements:** PIPE-04, LAUNCH-01

**Success criteria:**
1. One launch command starts master/slave bridges, filters, OpenSim, optional recording, status, and rosbridge.
2. All network, topic, segment, filter, recording, and OpenSim settings are explicit launch arguments or declared parameters.
3. Status output identifies configured pipeline stages and observed message activity.

### Phase 4: Offline Verification

**Goal:** Prove protocol compatibility and complete pipeline behavior without requiring live hardware.

**Requirements:** VERIFY-01, VERIFY-02

**Success criteria:**
1. Tests cover malformed and valid UDP frames, canonical JSON mapping, filtering, UDP forwarding, recorder output, and launch structure.
2. A documented offline replay command exercises raw-to-filtered-to-OpenSim/recording behavior.
3. Package installation and test commands run successfully in a ROS 2-capable environment.

## Progress

| Phase | Status |
|-------|--------|
| 1. Plugin-Compatible Ingestion | Not started |
| 2. Processing and Persistence Nodes | Not started |
| 3. Workflow Orchestration and Health | Not started |
| 4. Offline Verification | Not started |

---
*Roadmap created: 2026-07-15*
