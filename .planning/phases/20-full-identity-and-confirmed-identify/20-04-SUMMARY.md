---
phase: 20-full-identity-and-confirmed-identify
plan: "04"
subsystem: firmware
tags: [esp32, xiao-esp32s3, gpio, identify, fail-closed, tdd]

requires:
  - phase: 20-full-identity-and-confirmed-identify
    plan: "01"
    provides: Loop-owned correlated Identify state machine and prior-state restoration seam
provides:
  - Exact ARDUINO_XIAO_ESP32S3 compile-time selection of the GPIO 21 active-low user LED
  - Pinless unsupported-board configuration that cannot compile a fallback Identify GPIO
  - Paired source contracts for guard parity, callback isolation, bounded timing, and prior-state restoration
affects: [20-06-hardware-uat, phase-21-fleet-routing]

tech-stack:
  added: []
  patterns:
    - Exact board-target capability guards with no fallback GPIO on unsupported targets
    - Source-contract tests that compare Master and Slave board branches byte-for-byte

key-files:
  created: []
  modified:
    - firmware/step_node/step_node.ino
    - firmware/step_node_slave/step_node_slave.ino
    - backend/test/test_stepesp_firmware_topology.py

key-decisions:
  - "Only ARDUINO_XIAO_ESP32S3 enables Identify and maps it to GPIO_NUM_21 with LOW as the active level."
  - "Unsupported targets define capability false but no Identify pin or active-level macro, so unknown boards fail closed at compile time."
  - "Compilation and source contracts are software/configuration evidence only; physical blink, polarity, timing, and restoration remain Plan 06 human UAT."

requirements-completed: [ID-03]

duration: 6 min
completed: 2026-07-30
---

# Phase 20 Plan 04: Exact XIAO ESP32S3 Identify LED Guard Summary

**GPIO 21 active-low Identify enabled only by the official XIAO ESP32S3 board macro, with pinless fail-closed behavior for every unknown target**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-30T20:22:37Z
- **Completed:** 2026-07-30T20:28:59Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments

- Both firmware roles now select `GPIO_NUM_21` and active level `LOW` only inside the exact `ARDUINO_XIAO_ESP32S3` compile-time branch.
- Unsupported board targets advertise Identify capability false without defining a fallback pin or polarity, keeping all Identify GPIO access unreachable.
- Topology coverage now compares the full Master/Slave board branches, pins the supported and unsupported tuples, and strengthens callback, acquisition-state, duration-deadline, and prior-state restoration contracts.
- Both official XIAO ESP32S3 sketches compile successfully without changing the existing loop-owned Identify state machine.

## Task Commits

1. **Task 1: Lock the official XIAO ESP32S3 LED behind an exact board guard**
   - `e3f4b0c` — RED: failing exact-board, parity, fail-closed, and isolation contracts.
   - `92bc52b` — GREEN: exact `GPIO_NUM_21` active-low selection with no unsupported fallback pin.

## Files Created/Modified

- `firmware/step_node/step_node.ino` — Exact Master XIAO ESP32S3 Identify board tuple and pinless unsupported branch.
- `firmware/step_node_slave/step_node_slave.ino` — Matching Slave board tuple and unsupported behavior.
- `backend/test/test_stepesp_firmware_topology.py` — Paired guard parsing plus non-blocking, callback, acquisition-state, and restoration assertions.

## Verification

- `python -m unittest backend.test.test_stepesp_firmware_topology -v` — PASS, 19 tests.
- `arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 firmware/step_node` — PASS, 30% flash and 14% dynamic memory.
- `arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 firmware/step_node_slave` — PASS, 30% flash and 14% dynamic memory.
- Acceptance gate — PASS: exact guard/configuration, pinless unsupported branch, Master/Slave parity, loop ownership, 1000–5000 ms bounds with 3000 ms default, millis deadline, callback isolation, acquisition/recording isolation, and captured prior-level restoration are covered by source contracts.

These results are software/configuration evidence only. They do not prove physical LED blink, electrical polarity, observed duration, or restoration on a device.

## Decisions Made

- Used the ESP-IDF `GPIO_NUM_21` enum supplied by the official Arduino ESP32 target rather than an untyped numeric fallback.
- Removed unsupported-branch pin and polarity definitions entirely; `STEPESP_IDENTIFY_LED_VERIFIED=0` remains the only unsupported capability setting.
- Kept the Plan 01 Identify state machine unchanged because its loop ownership, bounded timing, idempotency, and prior-state restoration already satisfy this plan.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no dependency or external service changes.

## Known Stubs

None.

## Human UAT Pending

Plan 06 must verify on one physical XIAO ESP32S3 that:

- only the selected device blinks;
- GPIO 21 is electrically active-low on the deployed board revision;
- the observed blink remains within the requested 1–5 second duration;
- the prior application-owned LED state is restored afterward; and
- acquisition and SD recording remain unaffected.

No physical evidence is claimed by this plan.

## Next Phase Readiness

- Software/configuration evidence is ready for Plan 06 hardware UAT.
- STATE/ROADMAP advancement is intentionally deferred to the phase orchestrator until the earlier 20-03 plan is closed, preserving the correct next-incomplete-plan position.

## Self-Check: PASSED

- All three plan-owned implementation/test files and this summary exist.
- Both `e3f4b0c` RED and `92bc52b` GREEN commits are present in Git history.
- The final 19-test suite and both official-board compile commands passed.

---
*Phase: 20-full-identity-and-confirmed-identify*
*Completed: 2026-07-30*
