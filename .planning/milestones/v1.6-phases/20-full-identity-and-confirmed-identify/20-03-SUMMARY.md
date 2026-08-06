---
phase: 20-full-identity-and-confirmed-identify
plan: "03"
subsystem: ros-bridge
tags: [python, ros2, rosidl, esp32, identity, identify, tdd]

requires:
  - phase: 20-01
    provides: Versioned firmware full-MAC inventory and application-correlated Identify outcomes
  - phase: 20-02
    provides: Identity-confirmed relay routes and exact expected-device launch metadata
provides:
  - Primitive-only IdentifyDevice ROS service with explicit target, correlation, duration, outcome, applied duration, and detail
  - Strict full-MAC self/peer/end parsing with collision-safe canonical topic-token foundation
  - Self-only bridge binding, peer inventory health metadata, expected-ID gating, and changed-self rejection
  - Correlated Identify service that preserves unmatched replies and treats only confirmed as confirmed state
affects: [20-05-phase-verification, 20-06-hardware-uat, phase-21-fleet-routing, studio-device-mapping]

tech-stack:
  added: []
  patterns:
    - Complete counted id-v1 inventories gate bridge session acceptance
    - Identity replies use a dedicated bounded queue while sharing the existing serialized writer lock
    - Phase 20 exposes identity on compatibility health contracts without creating per-MAC publishers

key-files:
  created:
    - rehab_robotics_interfaces/srv/IdentifyDevice.srv
    - rehab_robotics_interfaces/CMakeLists.txt
  modified:
    - backend/rehab_robotics_bridge/esp32_bridge_node.py
    - backend/test/test_esp32_controls.py

key-decisions:
  - "Only a complete verified record=self row binds the bridge; peer rows remain bounded inventory and cannot satisfy expected_device_id."
  - "Existing Master/Slave publishers remain the only Phase 20 data publishers; device_topic_token is a pure Phase 21 foundation helper."
  - "sent_unconfirmed remains observable and non-success; only a correlated confirmed reply updates last-confirmed state."

patterns-established:
  - "Bridge identity gate: send IDENTITY?, consume self plus exact peers plus matching end, then start the legacy stream handshake."
  - "Identify correlation: validate before I/O, serialize writes, and match both bounded command ID and exact canonical target."

requirements-completed: [ID-01, ID-03]

duration: 35min
completed: 2026-07-30
---

# Phase 20 Plan 03: ROS Full Identity and Confirmed Identify Summary

**Strict self-bound ROS identity health plus a typed exact-target Identify service, without taking over Phase 21 per-MAC publisher lifecycle**

## Performance

- **Duration:** 35 min
- **Started:** 2026-07-30T20:31:38Z
- **Completed:** 2026-07-30T21:06:28Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Registered a primitive-only `IdentifyDevice` ROS service carrying explicit command correlation, full target identity, bounded duration, discriminated outcome, applied duration, and detail.
- Added strict full-48-bit canonical/display/topic-token helpers, counted self/peer/end inventory validation, bounded mixed binary/control admission, and low-32 collision coverage.
- The bridge now accepts streaming only after a complete verified self inventory, optionally matches `expected_device_id` against self alone, refreshes same-self metadata, and rejects replacement identity without mutating the prior binding.
- Existing health JSON now contains a versioned verified self snapshot, separate peer inventory, route/interface/capability metadata, and bounded unmatched Identify observability.
- `/esp32/{node_id}/identify` sends the exact firmware command through the existing writer lock and only accepts a terminal reply matching both command ID and target; no `/esp32/mac_*` publisher lifecycle was introduced.

## Task Commits

Each TDD task has a RED test commit followed by a GREEN implementation commit:

1. **Task 1: Define the typed Identify contract and strict identity helpers**
   - `5945178` — RED: failing primitive service, full-MAC, inventory, collision, correlation, and queue contracts.
   - `571cd55` — GREEN: registered service schema, strict identity helpers, and bounded mixed-stream admission.
2. **Task 2: Bind connected self identity and serve correlated Identify**
   - `163d4e0` — RED: failing handshake binding, reconnect, health, publisher-boundary, and Identify outcome contracts.
   - `8f12f30` — GREEN: self-only bridge binding, health identity metadata, and correlated typed Identify service.

## Files Created/Modified

- `rehab_robotics_interfaces/srv/IdentifyDevice.srv` — Primitive request/response contract for exact-target correlated Identify.
- `rehab_robotics_interfaces/CMakeLists.txt` — Registers `IdentifyDevice.srv` alongside the preserved `ProcessingBlockUpdate.msg`.
- `backend/rehab_robotics_bridge/esp32_bridge_node.py` — Strict identity parsers, handshake binding, health snapshot, bounded queues, and typed Identify service.
- `backend/test/test_esp32_controls.py` — ROS-free service, parser, collision, handshake, reconnect, publisher-boundary, and outcome coverage.

## Verification

- `python -m unittest backend.test.test_esp32_controls -v` — PASS, 30 tests.
- `python -m unittest backend.test.test_stepesp_udp_relay backend.test.test_stepesp_firmware_topology -v` — PASS, 38 tests.
- `python -m py_compile backend/rehab_robotics_bridge/esp32_bridge_node.py` — PASS.
- Static phase-boundary check — PASS: fixed role raw/IMU/status publishers remain, the role Identify service exists, and bridge source contains no `/esp32/mac_*` publisher or canonical publisher cache.
- Preservation check — PASS: existing recording, filter, sample-rate, confirmed-range, Open Ephys framing/resync, relay, and firmware topology contracts remain green.

## Decisions Made

- Used the complete firmware inventory as the sole session-binding source and retained peer rows only as separate inventory metadata.
- Routed Identify replies to their own bounded queue while reusing the existing writer lock, preventing unrelated recording/control traffic from satisfying an Identify request.
- Kept `sent_unconfirmed` as a non-success result if no later correlated terminal line arrives before the host deadline; only `confirmed` updates the bridge's last-confirmed record.
- Preserved all fixed Master/Slave publishers and kept `device_topic_token()` pure and unused by publisher construction until Phase 21.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Matched host command-ID tokens to the firmware-safe alphabet**
- **Found during:** Task 2
- **Issue:** The Task 1 host validator initially allowed `@`, `:`, and `+`, while the firmware accepts only ASCII alphanumeric characters plus `-`, `_`, and `.`. Such a request could pass ROS validation but be rejected by firmware.
- **Fix:** Tightened `_COMMAND_ID_RE` to the exact firmware-safe token alphabet and added a pre-I/O rejection fixture for `bad@command`.
- **Files modified:** `backend/rehab_robotics_bridge/esp32_bridge_node.py`, `backend/test/test_esp32_controls.py`
- **Verification:** The invalid-input fixture performs no writer I/O; all 68 tests pass.
- **Committed in:** `8f12f30`

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** The correction aligns host and firmware validation without changing the service schema or expanding scope.

## Issues Encountered

None.

## User Setup Required

None - no dependency or external service configuration required. Launchers may optionally provide an exact canonical `expected_device_id`.

## Known Stubs

None. Empty identity, writer, and peer fields are intentional disconnected startup state and are populated only after a complete verified handshake.

## Hardware Evidence

No physical LED, polarity, duration, acquisition-isolation, recording-isolation, or board MAC-relationship behavior is claimed by this plan. Those observations remain assigned to Phase 20 hardware UAT.

## Next Phase Readiness

- Plan 20-04 is already complete and its summary remains unchanged.
- Tracking can advance to the next incomplete Phase 20 plan with strict ROS identity and Identify contracts available.
- Phase 21 remains the sole owner of canonical per-MAC publisher instantiation, caching, teardown, and N-route fleet lifecycle.

## Self-Check: PASSED

- All four plan-owned implementation/test files and this summary exist.
- All four RED/GREEN task commits are present in Git history.
- The final 68-test verification set and Python compilation pass.
- The completed `20-04-SUMMARY.md` remains present and unchanged.

---
*Phase: 20-full-identity-and-confirmed-identify*
*Completed: 2026-07-30*
