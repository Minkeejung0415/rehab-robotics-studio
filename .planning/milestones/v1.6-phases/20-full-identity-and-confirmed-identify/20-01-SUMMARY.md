---
phase: 20-full-identity-and-confirmed-identify
plan: "01"
subsystem: firmware
tags: [esp32, esp-now, identity, mac, identify, xiao-esp32s3, tdd]

requires:
  - phase: 19-studio-controls-live-angle
    provides: Existing paired Master/Slave acquisition, recording, and OpenSim operator workflow
provides:
  - Verified six-byte base identity and separate STA/AP/ESP-NOW metadata for both firmware roles
  - Ordered IDENTITY_OK, IDENTITY_PEER, and IDENTITY_END host inventory protocol
  - Exact-target non-blocking Identify with application acknowledgement and reason-coded outcomes
affects: [20-02-relay-sessions, 20-03-ros-identify, 20-04-hardware-led-verification, phase-21-fleet-routing]

tech-stack:
  added: []
  patterns:
    - Packed versioned ESP-NOW packets with exact received-length and packet_size validation
    - Callback-to-loop deferral for timing-sensitive application actions
    - Full six-byte MAC comparison for identity and routing

key-files:
  created: []
  modified:
    - firmware/step_node/step_node.ino
    - firmware/step_node_slave/step_node_slave.ino
    - backend/test/test_stepesp_firmware_topology.py

key-decisions:
  - "Identity uses the full six-byte eFuse/base MAC; interface MACs, route, role, slot, and deprecated slave_id remain metadata."
  - "Identify confirmation is emitted only by target loop code after the bounded LED action starts; ESP-NOW send completion is never confirmation."
  - "The LED capability is enabled only for ARDUINO_XIAO_ESP32S3 at GPIO 21 active-low; all other board targets fail closed as unsupported."

patterns-established:
  - "Identity inventory: exactly one session-self record, counted peer rows, then one matching terminator."
  - "Identify idempotency: replay the cached result for duplicate command IDs without extending the active deadline."

requirements-completed: [ID-01, ID-03]

duration: 21min
completed: 2026-07-30
---

# Phase 20 Plan 01: Firmware Full Identity and Confirmed Identify Summary

**Versioned full-MAC firmware identity with exact-target, application-confirmed, non-blocking LED Identify over ESP-NOW**

## Performance

- **Duration:** 21 min
- **Started:** 2026-07-30T19:39:19Z
- **Completed:** 2026-07-30T20:00:15Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Both firmware roles now preserve and normalize the complete 48-bit eFuse/base MAC while reporting STA, AP, ESP-NOW transport, role, capability, and route metadata separately.
- The Master reports one self record, one row per current peer (including explicit unverified legacy peers), and a counted terminator for every `IDENTITY?` exchange.
- Identify validates token-safe host input, routes to self or one verified six-byte peer, distinguishes all seven outcomes, and accepts confirmation only from a correlated target application ACK.
- Target callbacks only validate and copy bounded packets; loop-owned state saves/restores the prior LED level, handles duplicate replay without deadline extension, and never assigns acquisition or recording state.

## Task Commits

Each TDD task has a RED test commit followed by a GREEN implementation commit:

1. **Task 1: Carry verified six-byte identity through both firmware roles**
   - `f0b2325` — RED: failing full-identity firmware contracts
   - `b516cd2` — GREEN: matching identity packets and ordered inventory
2. **Task 2: Implement correlated exact-target non-blocking Identify**
   - `d9542ea` — RED: failing confirmed-Identify contracts
   - `202c5cd` — GREEN: unicast routing, loop-owned action, and correlated outcomes

## Files Created/Modified

- `firmware/step_node/step_node.ino` — Master full-identity inventory, exact peer resolver, self-Identify, ACK correlation, timeout handling, and host result lines.
- `firmware/step_node_slave/step_node_slave.ino` — Slave identity publication plus deferred, idempotent Identify execution and application ACK return.
- `backend/test/test_stepesp_firmware_topology.py` — Hardware-free source contracts for schema parity, collision-safe identity, exact validation, unicast targeting, and non-blocking state isolation.

## Verification

- `python -m unittest backend.test.test_stepesp_firmware_topology -v` — PASS, 19 tests.
- `arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 firmware/step_node` — PASS, 30% flash and 14% dynamic memory.
- `arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 firmware/step_node_slave` — PASS, 30% flash and 14% dynamic memory.
- Static preservation check found zero Identify assignments to streaming, SD/recording, sample-rate/timing, or filter state.

## Decisions Made

- Used distinct packet magic/type/version fields for identity, Identify request, and Identify ACK so mixed firmware continues using the legacy status/control packets unchanged.
- Cached application ACKs by bounded command ID and full target; duplicate requests replay the prior result without changing the deadline, while a conflicting target for the same ID is rejected.
- Kept `sent_unconfirmed` as an observable intermediate result and emitted `confirmed` only after target loop code starts the action.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Repaired malformed execution-metric placement**
- **Found during:** Plan close-out
- **Issue:** The state SDK matched the next table after `Performance Metrics` and appended the plan metric to `Deferred Items`; it also left the frontmatter percentage and milestone plan count stale.
- **Fix:** Moved the metric into a dedicated Performance Metrics table and synchronized the 17% / 1-plan counters.
- **Files modified:** `.planning/STATE.md`
- **Verification:** State now reports plan 2 of 6, 1 completed plan, 17%, and one Phase 20 P01 metric row.
- **Committed in:** Plan metadata commit.

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** Tracking-only correction; firmware scope and verification were unchanged.

## Issues Encountered

- Arduino sketch auto-prototype generation required forward declarations for the new packed packet structs; declarations were added before compilation.
- One implementation compile exposed a packet type-name typo; it was corrected and both sketches were recompiled successfully.
- Physical LED pin, active-level, electrical interaction, and one-device blink behavior cannot be validated without the target hardware. The software guard and exact board build pass; physical acceptance remains intentionally assigned to Phase 20 hardware verification.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Next Phase Readiness

- Ready for `20-02-PLAN.md` to consume the ordered identity and correlated Identify host lines.
- Physical XIAO ESP32S3 LED/electrical behavior remains a human-needed hardware check for the dedicated Phase 20 hardware plan; no physical evidence is claimed here.

## Self-Check: PASSED

- All three plan-owned implementation/test files and this summary exist.
- All four RED/GREEN task commits are present in Git history.
- The final focused test and both exact-target firmware compile commands passed.

---
*Phase: 20-full-identity-and-confirmed-identify*
*Completed: 2026-07-30*
