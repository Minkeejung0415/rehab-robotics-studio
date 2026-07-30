---
phase: 20-full-identity-and-confirmed-identify
plan: "05"
subsystem: testing
tags: [python, esp32, identity, identify, regression, runbook]

requires:
  - phase: 20-01
    provides: Firmware full-MAC inventory and application-confirmed Identify protocol
  - phase: 20-02
    provides: Self-bound relay sessions and exact expected-device routing
  - phase: 20-03
    provides: Strict bridge inventory parsing and typed correlated Identify service
  - phase: 20-04
    provides: Exact XIAO ESP32S3 GPIO 21 active-low board guard
provides:
  - Shared cross-layer self/peer/count/end adversarial regression matrix
  - Deterministic false-confirmation, low-32 collision, route-isolation, and Phase 21 boundary coverage
  - Operator identity/Identify runbook with explicit pending physical HUMAN-UAT worksheet
affects: [20-06-hardware-uat, phase-21-fleet-routing, phase-25-capacity-promotion]

tech-stack:
  added: []
  patterns:
    - One named protocol matrix shared by firmware, relay, and bridge regression suites
    - Physical observations remain pending worksheets rather than inferred software evidence

key-files:
  created:
    - docs/stepesp-identity-identify.md
  modified:
    - backend/test/test_stepesp_firmware_topology.py
    - backend/test/test_stepesp_udp_relay.py
    - backend/test/test_esp32_controls.py

key-decisions:
  - "Cross-layer regression shares one named matrix for inventory attacks, low-32 collisions, Identify outcomes, and false-confirmation cases."
  - "Phase 20 permits only the pure mac_<12hex> helper; canonical per-MAC publisher creation, caching, publication, and teardown remain Phase 21."
  - "Fixture and compile evidence never satisfy the pending physical HUMAN-UAT; Phase 25 remains the fleet capacity and promotion gate."

patterns-established:
  - "Regression boundary: malformed identity on one route and Identify timeout on one request cannot poison unrelated acquisition or control traffic."
  - "Evidence boundary: every hardware observation is recorded as HUMAN NEEDED/Pending until performed on the selected board."

requirements-completed: [ID-01, ID-03]

duration: 8 min
completed: 2026-07-30
---

# Phase 20 Plan 05: Cross-Layer Identity and Identify Contract Summary

**Shared adversarial identity/Identify regression across firmware, relay, and bridge, plus an operator runbook that keeps physical evidence explicitly pending**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-30T21:13:08Z
- **Completed:** 2026-07-30T21:20:58Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Established one shared protocol matrix covering missing/duplicate/reordered self records, peer reuse/duplication, count and terminator errors, peer-as-expected binding attacks, full-MAC collisions, all seven Identify outcomes, and wrong/duplicate/late/lost reply cases.
- Proved malformed identity on one relay route and Identify timeout/unmatched replies in the bridge do not poison unrelated live acquisition or control traffic.
- Strengthened the Phase 21 boundary so the collision-safe `mac_<12hex>` helper remains available while Phase 20 rejects canonical publisher creation, caches, publication, or teardown.
- Published an actionable identity/Identify runbook with exact transcripts, terminal and typed ROS examples, metadata separation, mixed-firmware behavior, and an unfilled one-target physical `HUMAN-UAT` worksheet.

## Task Commits

Each task was committed atomically:

1. **Task 1: Lock the self-peer-terminator contract across all host layers** - `d258248` (test)
2. **Task 2: Publish the operator contract and pending physical UAT** - `1ecb59d` (docs)

## Files Created/Modified

- `backend/test/test_stepesp_firmware_topology.py` - Shared cross-layer matrices plus exact firmware producer, target, outcome, collision, LED guard, and preservation assertions.
- `backend/test/test_stepesp_udp_relay.py` - Complete adversarial inventory matrix, self-only expected-ID binding, all-outcome byte transparency, and malformed-route isolation.
- `backend/test/test_esp32_controls.py` - Bridge inventory matrix, low-32 token distinction, false-confirmation/lateness isolation, control preservation, and per-MAC lifecycle rejection.
- `docs/stepesp-identity-identify.md` - Canonical identity and Identify operator contract with exact protocol examples and pending physical worksheet.

## Verification

- `python -m unittest backend.test.test_stepesp_firmware_topology backend.test.test_stepesp_udp_relay backend.test.test_esp32_controls -v` - PASS, 73 tests.
- Runbook required-term validation from the plan - PASS.
- `python -m py_compile backend/test/test_stepesp_firmware_topology.py backend/test/test_stepesp_udp_relay.py backend/test/test_esp32_controls.py` - PASS.
- Acceptance gates - PASS: protocol, binding, Identify correlation/outcomes, Phase 21 boundary, preservation, operator actionability, identity separation, hardware evidence boundary, and Phase 25 scope.

## Decisions Made

- Used a shared named matrix in the firmware topology suite as the single vocabulary imported by relay and bridge tests, preventing outcome and attack-case drift without introducing a production dependency.
- Kept all Plan 20-05 changes in tests and documentation because Plans 20-01 through 20-04 already implemented the required runtime behavior and this plan explicitly owns regression closure rather than new production behavior.
- Required matching command ID plus exact target for `confirmed`; every wrong, duplicate-unmatched, late, lost, non-confirmed, unsupported, rejected, invalid, offline, or timed-out case leaves confirmed state unchanged.
- Kept every physical worksheet result `HUMAN NEEDED` and `Pending`; no fixture, source inspection, or compile result was promoted to board evidence.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Repaired malformed SDK tracking updates**
- **Found during:** Plan close-out
- **Issue:** The SDK set frontmatter progress to 0 instead of 83, left the body completed-plan count at 4, appended the new metric below the prior-milestone section, and removed ROADMAP table spacing/placeholders.
- **Fix:** Synchronized STATE to 5/6 and 83%, moved the Plan 05 metric into the current milestone table, and restored the ROADMAP row format.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** STATE reports Plan 6 of 6 ready with 5 completed plans and 83%; ROADMAP reports 5/6 In Progress.
- **Committed in:** Plan metadata commit.

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** Tracking-only correction; regression, runbook, scope, and hardware-evidence outcomes are unchanged.

## TDD Gate Compliance

Task 1 is marked `tdd="true"` but is explicitly a regression-only task whose owned files are tests and whose action requires one atomic three-test commit. The required production behavior already existed from Plans 20-01 through 20-04, so the new matrix correctly passed on first execution. No artificial failing test or out-of-scope production change was introduced; `d258248` records the test-only regression outcome.

## Issues Encountered

- The installed SDK's current handlers require named arguments for metrics and decisions even though the executor reference showed positional examples. The failed calls made no content changes; rerunning with the installed workflow's named arguments succeeded.

## User Setup Required

None - no dependency, package, environment variable, or external service changes.

## Known Stubs

None. Empty queues, lists, and dictionaries in the modified test files are intentional test-double startup state. The runbook's `HUMAN NEEDED` cells are an offline evidence worksheet, not product stubs.

## Threat Flags

None. This plan adds tests and documentation only; it introduces no runtime network endpoint, authentication path, file-access behavior, or schema change.

## Hardware Evidence

Physical XIAO ESP32S3 LED selection, GPIO 21 electrical active-low behavior, observed 1/3/5-second timing, exact prior-level restoration, streaming isolation, SD recording isolation, and base/STA/AP/ESP-NOW MAC relationships remain pending `HUMAN-UAT`. No physical result is claimed by this plan.

## Next Phase Readiness

- Ready for `20-06-PLAN.md` to record the explicitly human-needed one-target board evidence.
- Phase 21 remains the sole owner of canonical per-MAC publisher lifecycle and N-route fleet routing.
- Phase 25 remains the final supported fleet capacity, rate, compatibility-mode, and promotion gate.

## Self-Check: PASSED

- All four plan-owned test/document paths and this summary exist.
- Task commits `d258248` and `1ecb59d` are present in Git history.
- The final 73-test suite, runbook contract validation, Python compilation, and all acceptance gates pass.
- The hardware worksheet remains unfilled and explicitly classified as pending `HUMAN-UAT`.

---
*Phase: 20-full-identity-and-confirmed-identify*
*Completed: 2026-07-30*
