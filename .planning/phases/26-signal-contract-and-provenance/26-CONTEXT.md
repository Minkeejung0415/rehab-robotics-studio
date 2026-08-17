# Phase 26: Signal Contract and Provenance - Context

**Gathered:** 2026-08-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Define and validate the canonical per-sample contract used by later viewer, export, fleet, and OpenSim phases. This phase carries trustworthy device identity, timing, reconnect/provenance epochs, channel capabilities, raw values, validated SI conversions, and authoritative applied mapping labels through the backend and frontend data boundary. It does not build the waveform viewer, full-body model, export UI, or full-body IK.

</domain>

<decisions>
## Implementation Decisions

### Sample identity and time
- Every sample is keyed by normalized full MAC, never role, connection order, IP address, or a shortened label.
- Preserve acquisition timestamp and sequence when supplied; also attach a reconnect epoch so sequence/time resets cannot silently join sessions.
- Capability and validity metadata travels with the canonical sample rather than being inferred by the rendering layer.
- Missing or malformed required identity/timing fields fail closed and surface an explicit validation reason.

### Raw and physical units
- Raw signed counts for ax/ay/az, gx/gy/gz, and mx/my/mz are lossless authoritative values.
- Acceleration SI uses m/s^2 and angular-rate SI uses rad/s only when the declared range/sensitivity contract validates.
- Magnetometer SI uses microtesla only when sensitivity and calibration provenance validate; otherwise raw counts remain available and SI is explicitly unavailable.
- Conversion helpers are deterministic shared-contract logic with cross-language fixtures, not ad hoc UI formulas.

### Mapping provenance
- Labels use only the authoritative applied mapping snapshot: applied revision, exact segment, and exact model frame.
- Unsaved and saved drafts cannot relabel current or buffered samples.
- Applying a new mapping creates a new provenance epoch; historical samples keep their original labels and revision.
- Unassigned sources remain explicitly unassigned rather than inheriting a role-based body part.

### Quaternion capability and validity
- Quaternion channels are advertised only when the source declares quaternion capability and the current value passes finite/norm validity checks.
- Missing, stale, zero-norm, or malformed quaternion input is unavailable and never replaced with an identity quaternion.
- Capability absence and transient invalidity are distinct machine-readable states.
- Later consumers may display or suppress quaternion channels but cannot manufacture orientation data.

### the agent's Discretion
- Exact type/module names, schema versioning mechanism, error-code naming, and internal normalization layout may follow established repository patterns.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/rehab_robotics_bridge/measurement_contract.py` already owns validated accel/gyro range and sensitivity conversions.
- `backend/test/test_measurement_contract.py` plus shared JSON fixtures provide an existing cross-language contract-test pattern.
- `rehab-robotics-studio/src/types/signals.ts` is the current frontend signal type boundary and `src/hooks/useSignals.ts` already throttles rendering independently from acquisition.
- Existing mapping and fleet stores/nodes provide applied-revision, full-MAC, and reconnect information that should be joined at ingestion rather than reconstructed in views.

### Established Patterns
- Backend contract logic is pure Python where possible and tested without requiring a ROS installation.
- Frontend payload contracts use explicit TypeScript interfaces and Vitest fixtures.
- Invalid safety- or biomechanics-relevant data is represented as unavailable rather than substituted with plausible defaults.

### Integration Points
- Extend the native per-MAC IMU publication path before rosbridge delivery.
- Normalize payloads at the frontend data-source/signal-bus boundary so later viewers consume one canonical shape.
- Join labels against the mapping store's applied snapshot and retain them per sample/provenance epoch.

</code_context>

<specifics>
## Specific Ideas

The operator wants Open Ephys-style individual ax/ay/az, gx/gy/gz, mx/my/mz traces, raw/SI switching, and full-MAC plus body-part identity. Phase 26 must make those later displays trustworthy without coupling display controls to acquisition, recording, or OpenSim.

</specifics>

<deferred>
## Deferred Ideas

- Waveform layout and controls are Phase 29.
- Full-rate export and reconciliation are Phase 30.
- Full-body model, calibration, IK, and physical remap evidence are Phases 27, 31, and 32.

</deferred>
