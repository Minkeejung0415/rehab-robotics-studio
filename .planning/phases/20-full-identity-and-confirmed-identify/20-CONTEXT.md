# Phase 20: Full Identity and Confirmed Identify - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Give every Master and Slave a verified full 48-bit stable identity and add a safely targeted, application-acknowledged physical Identify action. This phase defines and implements identity and Identify across firmware and the immediately adjacent host-facing contracts; it does not yet build N-route ROS fleet routing, model mapping, N-sensor IK, or the final Studio mapping workspace.

</domain>

<decisions>
## Implementation Decisions

### Canonical Hardware Identity
- Persist the ESP eFuse/base MAC as the stable full 48-bit device identity; never use DHCP IP, discovery slot, role, or the existing low-32-bit `slave_id` as the identity key.
- Use canonical internal IDs in the form `esp32:aabbccddeeff` and display the same identity as uppercase `AA:BB:CC:DD:EE:FF`.
- Report base, STA, AP, and current ESP-NOW transport MACs as separate metadata until their relationship is verified on every deployed board revision.
- If a known route later reports a different stable identity, retain the original device as offline and register the new identity as a distinct device; never mutate one identity into another.

### Identify Command Contract
- Add a versioned, additive Identify request containing a unique command ID, exact target full MAC, and bounded duration; the Master routes it only to the requested peer and can target itself explicitly.
- Report success only after the target firmware validates the request, starts the LED action, and returns an application-level acknowledgement correlated to the command ID.
- Distinguish confirmed, sent-unconfirmed, timeout, offline, unsupported, rejected, and invalid-target outcomes rather than treating ESP-NOW send completion as confirmation.
- Make duplicate delivery idempotent by command ID; a new accepted command may replace the active Identify deadline, but replaying the same command must not extend it indefinitely.

### LED and Timing Safety
- Implement Identify as a non-blocking deadline checked from the normal loop; no `delay()`, blocking callback work, or acquisition/recording state changes are permitted.
- Clamp requested blink duration to a documented safe range, with a 3-second default and 1-5-second accepted range.
- Advertise Identify capability only after the exact board LED pin and active level are configured and verified; unknown board revisions return `unsupported` instead of guessing a pin.
- Restoring the LED after Identify must restore its prior application-owned state and must not interfere with any recording, fault, or other future LED semantics.

### Compatibility and Verification
- Extend packet schemas with explicit version and exact-size checks; malformed or unknown versions fail visibly without out-of-bounds reads or partial interpretation.
- Mixed old/new firmware continues acquisition and recording; older devices appear with their known identity metadata where possible and return `unsupported` for Identify.
- Preserve current Master/Slave status and control behavior while adding full identity fields; the low-32-bit `slave_id` may remain only as deprecated diagnostic metadata.
- Verification must include two full MACs sharing the same low 32 bits, Master plus at least two Slaves, wrong-target rejection, lost/duplicate ACK, timeout, unsupported firmware, and unchanged sample/recording timing during Identify.

### the agent's Discretion
- Exact packet type numbers, field packing, checksum reuse, and host-side helper names, provided the contracts are versioned and fixture-tested.
- Exact blink cadence within the bounded Identify duration.
- Whether the Master executes its self-Identify directly or through the same internal dispatcher, provided result semantics are identical.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `firmware/step_node/step_node.ino` already stores the six-byte ESP-NOW source MAC in `SlaveStatusSlot`, tracks up to six peers, registers unicast peers, and fans control packets to active slots.
- `firmware/step_node_slave/step_node_slave.ino` already uses `ESP.getEfuseMac()` but truncates it into a 32-bit `slave_id`; that source can provide the full stable identity.
- Existing ESP-NOW packet validation, status printing, TCP/UDP status contracts, and command acknowledgement patterns provide the seams for additive identity and Identify messages.

### Established Patterns
- Firmware packet changes are additive and guarded by version/size checks.
- Acquisition, streaming, and SD recording are independent state machines; diagnostics and controls must not block the high-rate sample loop.
- GUI and backend failures are reason-coded and fail closed instead of displaying a false healthy state.

### Integration Points
- Extend Master and Slave identity/status payloads and serial diagnostics with full base and transport MAC fields.
- Add targeted Identify request/ack handling to both firmware roles and the host-facing control/status path.
- Add parser fixtures and topology tests under `backend/test` and script-level tests without requiring physical hardware.
- Leave canonical per-device ROS publishers and fleet lifecycle ownership for Phase 21.

</code_context>

<specifics>
## Specific Ideas

The user wants to identify which physical ESP belongs on which bone. The row must always show MAC/status, and pressing Identify must blink only the corresponding ESP LED without disturbing live acquisition or SD recording.

</specifics>

<deferred>
## Deferred Ideas

- N-route relay and per-MAC ROS fleet publishers are Phase 21.
- Model-derived segment mapping and persistence are Phase 22.
- N-sensor calibration/IK and the dedicated Studio mapping workspace are Phases 23-24.

</deferred>
