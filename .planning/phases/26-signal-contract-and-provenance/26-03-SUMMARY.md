---
phase: 26-signal-contract-and-provenance
plan: 03
subsystem: backend-signal-ingestion
tags: [esp32, provenance, capabilities, calibration, ros2]
requires:
  - phase: 26-signal-contract-and-provenance
    provides: canonical Python signal builder and measurement validation
provides:
  - Identity-bound signal-cap-v1 firmware capability declarations
  - Applied-mapping and reconnect provenance epochs in canonical samples
  - Additive canonical envelopes on verified per-MAC legacy publications
affects: [signal-viewer, recording, mapping, firmware]
tech-stack:
  added: []
  patterns: [source-authoritative capability handshake, fail-closed canonical publication, immutable applied snapshot]
key-files:
  created: []
  modified:
    - backend/rehab_robotics_bridge/fleet_bridge_node.py
    - backend/test/test_fleet_bridge.py
    - backend/test/test_stepesp_firmware_topology.py
    - firmware/step_node/step_node.ino
    - firmware/step_node_slave/step_node_slave.ino
key-decisions:
  - "Firmware signal-cap-v1 declarations are the sole capability source; route metadata is comparison-only."
  - "The existing OeHeader plus 14 int16 frame remains unchanged; sequence and time are labeled as bridge-session facts."
  - "Mapping epochs advance only on changed applied revision, assignment, or model-hash signatures."
patterns-established:
  - "Canonical readiness is session-scoped and refreshed after every verified identity handshake."
  - "Invalid capability, calibration, or mapping inputs produce bounded reason codes without raw detail."
requirements-completed: [SIG-01, SIG-02, SIG-03, SIG-04, SIG-05]
duration: 11min
completed: 2026-08-16
---

# Phase 26 Plan 03: Verified Capability Publication Summary

**Identity-bound firmware capabilities, immutable applied/reconnect provenance, and calibrated canonical envelopes now ride alongside unchanged legacy per-MAC JSON.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-08-17T01:45:36Z
- **Completed:** 2026-08-17T01:56:44Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added strict `SIGNAL_STATUS?` / `signal-cap-v1` declarations to both firmware roles, derived from initialized sensor and filter state.
- Added a bounded applied-mapping cache whose epoch ignores draft/save changes and remains independent from reconnect generation.
- Published `rehab.signal_sample.1` under `sample_contract` only after verified identity, capability, mapping, and calibration validation while retaining `oe_esp32.raw.v1` fields.
- Proved the network frame remains exactly `OeHeader + 14 int16`; internal `StreamRecord.seq` is not transmitted.

## Task Commits

1. **Task 1: Prove explicit session metadata and additive publication** - `ebf2a31` (test)
2. **Task 2 RED: Define applied provenance epochs** - `343c481` (test)
3. **Task 2 GREEN: Snapshot authoritative applied mapping** - `56d2898` (feat)
4. **Task 3: Emit canonical envelopes at the verified per-MAC seam** - `0d3d941` (feat)

## Files Created/Modified

- `backend/rehab_robotics_bridge/fleet_bridge_node.py` - Capability parser, calibration loader, mapping cache, handshake binding, and canonical publication.
- `backend/test/test_fleet_bridge.py` - Protocol rejection, calibration, provenance epoch, handshake, and additive publication coverage.
- `backend/test/test_stepesp_firmware_topology.py` - Firmware declaration and unchanged binary framing assertions.
- `firmware/step_node/step_node.ino` - Master capability status response.
- `firmware/step_node_slave/step_node_slave.ino` - Slave capability status response.

## Decisions Made

- Route expectations can reject a mismatched source declaration but can never populate canonical capabilities.
- Old, silent, malformed, duplicated, or wrong-MAC capability responses preserve legacy publication while withholding `sample_contract`.
- Magnetometer sensitivity alone does not authorize microtesla; a matching validated `rehab.mag_calibration.1` artifact is also required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Made ROS test stubs import-order independent**
- **Found during:** Task 2 verification
- **Issue:** Running mapping tests before fleet tests preloaded partial `std_msgs` and interface modules, causing collection errors.
- **Fix:** Augmented existing modules and installed stubs before importing the bridge helper.
- **Files modified:** `backend/test/test_fleet_bridge.py`
- **Verification:** Mandated combined mapping/fleet command passes 14 tests.
- **Committed in:** `56d2898`

**2. [Rule 1 - Bug] Scoped the sequence framing assertion to binary transports**
- **Found during:** Task 3 GREEN
- **Issue:** The RED test incorrectly rejected `rec.seq` in the separate CSV diagnostic path even though only binary network framing must exclude it.
- **Fix:** Asserted the TCP/UDP wire section excludes `rec.seq` while retaining CSV compatibility.
- **Files modified:** `backend/test/test_stepesp_firmware_topology.py`
- **Verification:** Focused firmware protocol suite passes.
- **Committed in:** `0d3d941`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 test bug)
**Impact on plan:** Both fixes were required for deterministic validation; no feature scope was added.

## Issues Encountered

- The shared working tree contained unrelated edits in all target files. Task commits used exact index blobs so those edits remained unstaged and untouched.

## User Setup Required

None. `signal_calibration_path` is optional; absent calibration intentionally keeps magnetometer SI unavailable.

## Verification

- Focused contract/integration: `87 passed, 136 subtests passed`
- Task 2 mapping/provenance: `14 passed`
- Full backend regression: `425 passed, 8 skipped, 284 subtests passed`

## Known Stubs

None. Empty internal dictionaries represent bounded initial cache state, not deferred UI or mock data.

## Next Phase Readiness

- Browser ingress can now trust sample-owned capabilities, mapping labels, and epochs without consulting mutable draft state.
- Hardware smoke testing can validate the same bounded status line without changing binary acquisition framing.

## Self-Check: PASSED

- All five modified implementation/test files exist.
- Commits `ebf2a31`, `343c481`, `56d2898`, and `0d3d941` exist in repository history.

---
*Phase: 26-signal-contract-and-provenance*
*Completed: 2026-08-16*
