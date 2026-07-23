---
status: diagnosed
trigger: "focus on number 2 -7 for now"
created: "2026-07-23"
updated: "2026-07-23T13:30:00-07:00"
---

# Acquisition Integrity Findings 2-7

## Symptoms

- expected: Configured IMU ranges produce correctly scaled measurements; device timestamps and sequences survive transport; filtered quaternions remain valid unit orientations; paused acquisition still resolves service replies; rosbridge fallback/restart reconnects reliably; disconnected hardware and streams age offline.
- actual: The audit found fixed default IMU scale factors, discarded device timing and zero TCP sequences, component-wise quaternion averaging, paused service-response drops, unrecoverable/racy rosbridge reconnection, and health flags that can remain online indefinitely.
- errors: No single exception is required. Observable failures include under-reported IMU values at non-default ranges, seq/sample_index stuck at zero, invalid or zero quaternions, false ten-second command timeouts while paused, reconnect requiring reload, and stale PAIR ONLINE/Streaming indicators.
- timeline: Confirmed during the 2026-07-23 repository audit after recent firmware, networking, and high-rate acquisition changes.
- reproduction: Trace and probe only audit findings 2-7 using the existing code and tests. Configure non-default ranges, inspect TCP/UDP metadata, exercise quaternion counterexamples, issue a service command while paused, force rosbridge fallback/restart, and age or remove slave/stream updates. Diagnose only; do not modify implementation files.

## Current Focus

- hypothesis: Confirmed. Findings 2-7 are six concrete acquisition-contract failures: unused range state, missing/discarded device metadata, invalid Euclidean quaternion averaging, pause-gated control replies, generation-unaware/fallback-blocked WebSocket reconnection, and health without freshness expiry.
- test: Completed static writer-reader tracing plus direct scale, quaternion, TCP metadata, paused-response, stale-socket, and stale-health probes.
- expecting: Diagnosis-only handoff to v1.3 requirements and roadmap planning; no implementation modification in this session.
- next_action: Return the root-cause report with per-finding fix direction and regression-test boundaries.
- reasoning_checkpoint:
- tdd_checkpoint:

## Evidence

- timestamp: "2026-07-23T12:24:00-07:00"
  checked: Project-local skills and debug knowledge base
  found: Neither .codex/skills nor .agents/skills exists, and .planning/debug/knowledge-base.md does not exist.
  implication: No project-specific debugging rules or known-pattern candidate applies; investigate directly from current first-party source.

- timestamp: "2026-07-23T12:24:00-07:00"
  checked: Git worktree status
  found: The repository contains extensive pre-existing modified and untracked files, including backend/rehab_robotics_bridge/esp32_bridge_node.py and rehab-robotics-studio/src/data/RosbridgeDataSource.ts.
  implication: Preserve all user changes and treat the current working tree, rather than HEAD, as the audited implementation state.

- timestamp: "2026-07-23T12:29:00-07:00"
  checked: Repository-wide search for findings 2-7 symptom signatures
  found: Fixed ACC_SCALE/GYRO_SCALE constants and socket lifecycle/message dispatch are in rehab-robotics-studio/src/data/RosbridgeDataSource.ts; configured ranges, frame parsing, metadata, and publication are in backend/rehab_robotics_bridge/esp32_bridge_node.py; quaternion filtering is in backend aggregation/filter code; health display consumes pair_available in HealthPanel.tsx; firmware exposes sequence, streaming, and freshness fields.
  implication: The source search identifies concrete first-party writer-reader paths for all six findings; complete-file reading is required to check whether any compensating logic exists.

- timestamp: "2026-07-23T12:42:00-07:00"
  checked: Complete backend bridge and firmware wire path
  found: The bridge stores acknowledged _accel_range_g and _gyro_range_dps values but _publish_frame always multiplies by module-level default ACC_SCALE/GYR_SCALE. Firmware places synchronized low-32-bit device microseconds in OeHeader.offset, but the bridge unpacks it as _off and publishes host monotonic time. Firmware assigns StreamRecord.seq yet TCP and UDP writers transmit only header plus channels; the bridge TCP path calls _publish_frame without sample_index, whose default is zero, while UDP invents a connection-local counter.
  implication: Findings 2 and 3 have direct writer-consumer contract breaks; configured conversion state is unused, device timing is discarded, device sequence is absent from the wire, and TCP metadata is deterministically zero.

- timestamp: "2026-07-23T12:42:00-07:00"
  checked: Complete filter implementation and tests
  found: SampleFilter maintains an independent integer deque for qw/qx/qy/qz and replaces each component with its rounded arithmetic mean. It performs neither quaternion sign alignment nor post-average normalization. Existing tests assert only schema/body-segment preservation and do not validate quaternion norm or antipodal equivalence.
  implication: Finding 4 matches a data-shape/math-contract bug and lacks regression coverage.

- timestamp: "2026-07-23T12:42:00-07:00"
  checked: Complete RosbridgeDataSource and appDataSource lifecycle
  found: handleMessage returns immediately when paused before inspecting envelope.op, so service_response messages are dropped. Socket callbacks read/write shared this.socket and connected state without checking callback socket identity. Initial connection failure switches active to mock, after which reconnectHardware rejects because active is not rosbridge; stop/start assigns a new socket before the old socket's asynchronous onclose can unconditionally set this.socket=null and connected=false.
  implication: Findings 5 and 6 are specific dispatch-order and ownership-generation defects, not generic network instability.

- timestamp: "2026-07-23T12:42:00-07:00"
  checked: Complete backend health, frontend health store, and UI paths
  found: Master pair health caches _latest_slave_health forever and computes pair_available solely from its cached connection_state, without receive-time age. Frontend setEspStreamActive(true) runs only on the first frame because receivedFrame is never reset or aged, and pairHealth persists unchanged in Zustand when updates stop. EspStatusNode publishes cumulative counts rather than recent activity.
  implication: Finding 7 is caused by absent freshness semantics at multiple layers; loss of slave/status/frame updates does not transition cached online/streaming state offline.

- timestamp: "2026-07-23T13:28:00-07:00"
  checked: Non-default-range numeric counterexamples against firmware sensitivity tables and host constants
  found: Firmware defines accelerometer sensitivities [16384, 8192, 4096, 2048] LSB/g and gyro sensitivities [131.072, 65.536, 32.768, 16.384] LSB/dps, but host constants always use the first entries. At ±8g, a 1g raw value of 4096 is reported as 2.4516625 m/s² instead of 9.80665; at ±2000dps, a 250dps raw value of 4096 is reported as 31.25dps instead of 250dps.
  implication: Finding 2 is reproduced with deterministic factor-of-four and factor-of-eight under-reporting.

- timestamp: "2026-07-23T13:28:00-07:00"
  checked: TCP parser probe using frames whose OE offsets were 123456 and 123556
  found: _read_frames called _publish_frame with exactly three arguments for both frames; neither device offset appeared in the call, and omitted sample_index therefore used the default zero.
  implication: Finding 3 is reproduced on TCP independently of timing or hardware; metadata loss occurs at the parser-to-publisher call boundary.

- timestamp: "2026-07-23T13:28:00-07:00"
  checked: SampleFilter antipodal quaternion probe
  found: Filtering Q15 quaternions (32767,0,0,0) followed by (-32767,0,0,0), which represent the same orientation, produced (0,0,0,0) with norm 0.0.
  implication: Finding 4 is reproduced exactly; downstream consumers can receive a non-orientation even when every input is a valid unit orientation.

- timestamp: "2026-07-23T13:28:00-07:00"
  checked: Transpiled RosbridgeDataSource with a deterministic fake WebSocket
  found: A matching service_response delivered while paused left the service promise unsettled; delivering the same response after resume resolved it. In a rapid stop/start, the new socket opened successfully, then the old socket's delayed onclose caused setRecording to return "ROS bridge is not connected."
  implication: Findings 5 and the socket-generation part of 6 are directly reproduced from the current class implementation.

- timestamp: "2026-07-23T13:28:00-07:00"
  checked: Pair-health publication with a cached connected slave timestamp_us of 1
  found: The current _publish_health_status emitted pair_available=true despite the deliberately ancient slave snapshot.
  implication: Finding 7 is directly reproduced; no timestamp or receive-age threshold participates in pair availability.

- timestamp: "2026-07-23T13:28:00-07:00"
  checked: Existing focused backend control tests
  found: All seven unittest cases passed, but they cover command mapping, control parsing, and TCP resynchronization only; repository search found no assertions for dynamic scale conversion, timestamp/sequence preservation, quaternion validity, paused replies, socket generation, or health expiry.
  implication: Findings 2-7 are compatible with the passing suite because their regression boundaries are currently untested.

## Eliminated

- hypothesis: Non-default IMU values are wrong because range commands are not acknowledged or stored.
  evidence: _control_command_for_parameter maps every supported range, _on_set_parameters requires the firmware acknowledgement, and _store_confirmed_control_value updates the corresponding in-memory range. The defect is downstream: conversion never reads that state.
  timestamp: "2026-07-23T13:28:00-07:00"

- hypothesis: Quaternion invalidity is only a small Q15 rounding artifact.
  evidence: Exact antipodal valid inputs produced an exact all-zero quaternion with norm 0.0; the failure is the averaging model, not quantization noise.
  timestamp: "2026-07-23T13:28:00-07:00"

- hypothesis: Paused command timeouts originate in firmware or ROS service latency.
  evidence: A matching already-arrived service_response was synchronously discarded by the frontend pause guard and resolved immediately when replayed after resume.
  timestamp: "2026-07-23T13:28:00-07:00"

- hypothesis: Stale pair state is caused only by delayed rendering.
  evidence: The backend itself emitted pair_available=true from an ancient cached slave snapshot, before frontend storage or rendering.
  timestamp: "2026-07-23T13:28:00-07:00"

## Resolution

- root_cause: |
    Finding 2 — Range changes update firmware and bridge state, but both backend/rehab_robotics_bridge/esp32_bridge_node.py and rehab-robotics-studio/src/data/RosbridgeDataSource.ts convert raw IMU counts with fixed ±2g/±250dps constants. The raw JSON contract carries no active range, so the frontend cannot select a correct divisor.
    Finding 3 — Firmware computes synchronized device microseconds in OeHeader.offset and stores seq in StreamRecord, but its TCP/UDP writers transmit only OeHeader plus channels, omitting StreamRecord.seq. The bridge explicitly ignores OeHeader.offset, substitutes host monotonic receipt time, defaults TCP sample_index/seq to zero, and uses only a connection-local counter for UDP.
    Finding 4 — backend/rehab_robotics_bridge/pipeline.py filters quaternion Q15 components as four unrelated integer moving averages. It neither aligns antipodal signs nor normalizes or validates the result, so equivalent q/-q inputs cancel to the zero quaternion.
    Finding 5 — RosbridgeDataSource.handleMessage applies the paused guard before routing service_response envelopes. Pausing sample emission therefore also drops control-plane replies, leaving pending promises to report false ten-second timeouts.
    Finding 6 — RosbridgeDataSource has no socket generation/identity ownership. Callbacks mutate shared socket/connected state even when fired by an obsolete socket; rapid stop/start is clobbered by the old onclose. Its initial-unavailable callback also changes app-level active ownership to mock, while reconnectHardware requires active to still equal rosbridge, making fallback unrecoverable through the UI. Established connection closes have no automatic retry.
    Finding 7 — Health is modeled as cached state rather than a time-bounded lease. The master never expires _latest_slave_health, UDP receive timeouts do not degrade connection state, EspStatusNode exposes cumulative counts without recent activity, and the frontend never ages or clears pairHealth/Streaming; receivedFrame is a one-way lifetime latch.
- fix: Not applied; diagnosis-only milestone planning.
- verification: Root causes confirmed by complete first-party source tracing and isolated read-only probes reproducing scale errors, TCP metadata loss, zero quaternion output, paused reply loss, stale-socket clobbering, and stale pair availability. Seven existing focused backend control tests pass but do not cover these contracts.
- files_changed: []
