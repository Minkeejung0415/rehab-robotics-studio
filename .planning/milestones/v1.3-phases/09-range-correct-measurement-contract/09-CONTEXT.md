# Phase 9: Range-Correct Measurement Contract - Context

**Gathered:** 2026-07-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Make backend and GUI interpretation of paired ESP32 accelerometer and gyroscope samples depend on each device's confirmed active ranges. Extend the existing raw ROS JSON contract with sufficient scale context, keep native ROS IMU values in SI units, and prove consistent conversion across every supported range. Firmware timing and sequence framing belongs to Phase 10.

</domain>

<decisions>
## Implementation Decisions

### Conversion Ownership
- Preserve integer sensor counts as the canonical values on `/esp/raw/master` and `/esp/raw/slave`.
- Add explicit scale and range metadata rather than replacing raw counts with physical values.
- Use one shared backend definition for mapping supported ranges to scale factors; the GUI converts transmitted counts using the metadata instead of fixed constants.
- Treat the last firmware-acknowledged range stored independently by each bridge node as the source of truth.
- Scale master and slave independently before relative-angle or differential calculations.

### Metadata and Compatibility
- Add a `sensor_config` object to every raw frame containing `accel_range_g`, `gyro_range_dps`, accelerometer and gyroscope LSB sensitivities, and declared units.
- Keep the additive JSON contract under `oe_esp32.raw.v1`; existing consumers may ignore unknown fields.
- Treat live frames without valid scale metadata as untrusted: do not silently assume the default range or emit misleading physical GUI frames.
- Preserve the last confirmed range after an unsupported or rejected request and surface the rejection; never clamp or optimistically update scaling.

### Operator Feedback and Proof
- Reuse the existing confirmed-range controls and physical readouts; do not add a separate scale diagnostics panel.
- Emit one actionable warning per connection when scale context is missing and suppress misleading physical frames until valid metadata arrives.
- Parameterize every supported accelerometer and gyroscope range for both master and slave.
- Compare backend SI output with GUI conversion for identical raw counts and confirmed ranges.
- Do not redesign firmware framing in this phase; sequence and device-time transport are Phase 10.

### the agent's Discretion
- Exact helper/module placement for shared range tables and validation.
- Exact warning wording and whether the one-per-connection latch lives in the data source or system-status integration.
- Test fixture organization, provided every supported range and both device roles are covered.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Esp32BridgeNode._store_confirmed_control_value` already stores acknowledged `accel_range_g` and `gyro_range_dps` independently for each node.
- `Esp32BridgeNode._publish_frame` is the central backend boundary for raw JSON and native `sensor_msgs/Imu` publication.
- `RosbridgeDataSource.frameFromRaw` is the GUI conversion boundary for raw ESP JSON.
- Existing IMU controls already expose and display confirmed range values.

### Established Patterns
- Hardware state is committed only after firmware acknowledgement.
- ROS raw frames use additive JSON under `oe_esp32.raw.v1`.
- The GUI isolates hardware transport in `RosbridgeDataSource` and reports operator-facing state through Zustand system stores.
- Backend tests use focused pure helpers and controlled bridge objects to avoid requiring live ROS hardware.

### Integration Points
- Backend range constants and `_publish_frame` conversion in `backend/rehab_robotics_bridge/esp32_bridge_node.py`.
- Raw-message types and `frameFromRaw` conversion in `rehab-robotics-studio/src/data/RosbridgeDataSource.ts`.
- Confirmed control flow through the ESP parameter service and existing range controls.
- Backend and frontend regression suites for contract-level scale checks.

</code_context>

<specifics>
## Specific Ideas

The operator should continue using the same range controls and readouts. Correctness should be visible through stable physical measurements, not through additional interface complexity.

</specifics>

<deferred>
## Deferred Ideas

- Firmware device timestamps and sequences are Phase 10.
- Physical E-STOP integration, graph persistence, packaging, stale aggregator/documentation, and broad performance optimization remain outside v1.3.

</deferred>
