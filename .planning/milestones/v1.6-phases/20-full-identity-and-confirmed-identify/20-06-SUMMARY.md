---
phase: 20-full-identity-and-confirmed-identify
plan: "06"
subsystem: verification
tags: [esp32, identity, identify, regression, arduino, evidence, human-uat]

requires:
  - phase: 20-05
    provides: Cross-layer identity/Identify fixtures and the physical observation runbook
provides:
  - Passing 73-test local identity and Identify regression evidence
  - Passing official XIAO ESP32S3 compiles for both firmware roles
  - Pre/post source fingerprints proving the verification commands changed no scoped source or test
  - Explicit human_needed handoff for physical LED, timing, restoration, and live-work continuity
affects: [phase-21-fleet-routing, phase-25-capacity-promotion, human-uat]

tech-stack:
  added: []
  patterns:
    - Automated source/configuration evidence is classified separately from physical hardware observation
    - Whole-worktree and scoped SHA-256 fingerprints bracket verification-only execution

key-files:
  created:
    - .planning/phases/20-full-identity-and-confirmed-identify/20-06-SUMMARY.md
  modified: []

key-decisions:
  - "Physical Identify behavior remains human_needed because STEP_ESP hardware was disconnected; no fixture, source assertion, or compile result was promoted to physical evidence."
  - "Phase 20 makes no per-MAC publisher-lifecycle or fleet-capacity promotion claim; those boundaries remain owned by Phases 21 and 25."

requirements-completed: [ID-01, ID-03]

duration: 2 min
completed: 2026-07-30
---

# Phase 20 Plan 06: Final Identity and Identify Evidence Summary

**A clean 73-test cross-layer gate and two official-board firmware compiles, with byte-for-byte source preservation and physical Identify explicitly retained as HUMAN-UAT**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-30T21:26:26Z
- **Automated gate completed:** 2026-07-30T21:28:33Z
- **Tasks:** 1
- **Files created:** 1 summary
- **Source/test files modified:** 0

## Accomplishments

- Ran the complete firmware/relay/bridge identity and Identify matrix: all 73 tests passed.
- Compiled both official `esp32:esp32:XIAO_ESP32S3` firmware roles without editing source: both builds passed.
- Captured SHA-256 fingerprints for the firmware sketches, relay, bridge, interfaces, tests, launcher, and runbook before and after execution; every fingerprint matched.
- Preserved the entire pre-existing dirty worktree: the default `git status --short` snapshot remained 141 entries with the same SHA-256 digest before and after verification.
- Kept physical one-target blink, non-target stillness, board polarity, 1/3/5-second timing, prior-state restoration, streaming continuity, and SD-recording continuity explicitly `human_needed`.

## Task Commit

- Task 1 verification record: `a9ad06a` — automated gate, fingerprints, and explicit HUMAN-UAT handoff.

## Automated Evidence

### Focused regression matrix

Command:

```powershell
python -m unittest backend.test.test_stepesp_firmware_topology backend.test.test_stepesp_udp_relay backend.test.test_esp32_controls -v
```

Result: **PASS — 73 tests in 1.033 seconds.**

The passing named fixtures cover:

| Required coverage | Automated evidence |
| --- | --- |
| One Master/self plus at least two peers | Complete counted inventory fixtures use one self and two distinct peer IDs. |
| Full-MAC and low-32 collision safety | `esp32:1111ccddeeff` and `esp32:2222ccddeeff` remain distinct despite identical low 32 bits. |
| Self-only binding | Relay and bridge reject a peer row that matches the expected ID. |
| Malformed count/terminator and ordering | Missing/duplicate/reordered self, duplicate/reused peers, count mismatch, and missing/mismatched terminators fail closed. |
| Exact-target unicast and wrong target | Firmware target resolution is full-MAC exact; bridge correlation rejects a wrong target. |
| Duplicate, lost, and late acknowledgements | False-confirmation matrix preserves prior confirmed state and unrelated control traffic. |
| All seven outcomes | `confirmed`, `sent_unconfirmed`, `timeout`, `offline`, `unsupported`, `rejected`, and `invalid_target`. |
| Guarded GPIO configuration | Exact `ARDUINO_XIAO_ESP32S3` guard, GPIO 21 active-low configuration, and pinless unsupported fallback. |
| Prior-state restoration logic | Non-blocking loop-owned tick saves and restores the prior application LED level; duplicate delivery does not extend the deadline. |
| Acquisition/recording non-mutation | Static contract rejects Identify assignments to streaming, SD/recording, rate/timing, or filter state; live-route and control fixtures remain independent. |
| Phase 20 publisher boundary | Only compatibility role publishers/services remain; no canonical per-MAC publisher creation, cache, publication, or teardown exists. |

These are **automated software/configuration assertions only**. They do not demonstrate physical LED behavior or deployed stream/recording continuity.

### Official firmware compiles

Commands and results:

```powershell
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 firmware/step_node
# PASS: 1,009,968 bytes flash (30%); 49,052 bytes dynamic memory (14%)

arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 firmware/step_node_slave
# PASS: 1,010,772 bytes flash (30%); 48,068 bytes dynamic memory (14%)
```

No package install or source modification was performed.

## Source Fingerprints

SHA-256 values were identical before and after the test/build commands:

| Path | Bytes | SHA-256 | Baseline status |
| --- | ---: | --- | --- |
| `firmware/step_node/step_node.ino` | 129973 | `d3932ec0c5360b68186de76b41ff08eae7f7b210ee546180a0a23d2b683e933c` | clean |
| `firmware/step_node_slave/step_node_slave.ino` | 117832 | `736a85a6c12a94319e7c1d46d9a8151e1f9c7714831cfdf5ae8f8c518a4ae6ff` | clean |
| `scripts/stepesp_tcp_udp_relay.py` | 31593 | `a1a787171f24bc560eb04e622a26b4d81113b9f5cdc458986a59fcaa54ffa3ef` | clean |
| `backend/rehab_robotics_bridge/esp32_bridge_node.py` | 75740 | `379084a1f3ea8ac551f367ad3e0708f7d21a3b681a2d70f5d0199fac14d105c1` | clean |
| `rehab_robotics_interfaces/srv/IdentifyDevice.srv` | 163 | `286eced96f241aecdfef54a8407d55667134360c304ef6dd07ced5292fb4fc2d` | clean |
| `rehab_robotics_interfaces/CMakeLists.txt` | 386 | `c2f513b0be8129d40a502c93e424bd5511d73755635cc1aebf2e06109ed6ccf4` | clean |
| `rehab_robotics_interfaces/package.xml` | 614 | `c14ad141dd930039ce43d82fd7d5a71025773f3408f3164a1cc9acc70c8d27bb` | pre-existing untracked |
| `backend/test/test_stepesp_firmware_topology.py` | 22889 | `a7db4a15024a523f185c77e85b08199d2c69097ab74d0394cd39387346b58407` | clean |
| `backend/test/test_stepesp_udp_relay.py` | 20409 | `1fac2f51c9046bc2a7d4ffe2ccc82037f474bff66065e8a15df6a65245096ef5` | clean |
| `backend/test/test_esp32_controls.py` | 41117 | `f81d56db55f211abbed366030ca9a8013ea94782cade8d6e8ec1215c054ec279` | clean |
| `scripts/start_stepesp_wireless.ps1` | 23691 | `1fe6d1a8ceb1ef0ef25d2b9c6db9fcbf9f2d9c5a310fdec0b1732ec31b9c6f55` | clean |
| `docs/stepesp-identity-identify.md` | 12278 | `0d2af44ab6274e672ec85974254a85520bb9c7eea1da0931c71edc53d95796e3` | clean |

### Dirty-worktree preservation

- Pre-run capture: `2026-07-30T21:27:00Z`
- Post-run capture: `2026-07-30T21:28:06Z`
- Default `git status --short` entry count: **141 before / 141 after**
- UTF-8 LF-joined status snapshot SHA-256: `7f1670dd5301fb1e0f2a63e7d0968765cac1704324a95ef6701b136e8fa902dc` before and after
- Scoped path hashes: **12/12 identical**
- Verification-generated source/test changes: **none**

The pre-existing untracked `rehab_robotics_interfaces/package.xml` remained present with the same hash and was neither staged nor edited.

## HUMAN-UAT — `human_needed`

**Status: HUMAN NEEDED / Pending.**

Codex was disconnected from the STEP_ESP hardware, so none of the following physical observations was performed, inferred, or approved:

1. Power at least two official XIAO ESP32S3 devices so one exact full-MAC target and one non-target witness are simultaneously visible.
2. Record target and non-target canonical IDs, display/base MACs, STA/AP/ESP-NOW MACs, board markings/revisions, and the flashed firmware sketch SHA-256 from this summary.
3. Send fresh command IDs to the selected full-MAC target for `duration_ms=1000`, `3000`, and `5000`.
4. For every run, observe that only the selected onboard LED blinks, the non-target remains still, and the visible duration is bounded to the request.
5. Verify the deployed board's GPIO 21 LED polarity is physically active-low.
6. Capture the exact application-owned LED level before Identify and confirm that exact level returns after each deadline.
7. Repeat Identify while acquisition is streaming; record sample rate, continuity, drops, and errors before/during/after.
8. Repeat Identify during active SD recording and finalization; record session state, saved samples, file size, checksum/status, and any discontinuity.
9. Record command ID, exact target, terminal outcome, applied duration, detail, timestamps, and observable evidence. Only a matching `confirmed` reply may be paired with a successful physical observation.

Record the results in the runbook's **Pending one-selected-target physical UAT** worksheet. If any non-target blinks, timing is out of bounds, restoration is not exact, or acquisition/recording changes, mark `HUMAN-UAT` failed and retain compatibility mode.

## Phase Boundary

- Phase 20 proves the software/configuration contracts and leaves the physical check visible as pending.
- Phase 21 exclusively owns canonical per-MAC publisher lifecycle and N-route fleet routing.
- Phase 25 exclusively owns supported fleet size/rate, compatibility-mode promotion, and final capacity acceptance.
- This plan makes no physical, fleet-capacity, or default-promotion claim.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Repaired malformed SDK tracking updates**

- **Found during:** Plan close-out
- **Issue:** The SDK changed frontmatter progress to 17% despite 6/6 plan completion, left milestone counters at 5 plans and 0 phases, appended the Plan 06 metric below the prior-milestone section, and left the current-position label as EXECUTING.
- **Fix:** Restored 100% phase-plan progress, synchronized counters to 6 plans and 1/6 phases, moved the metric into the Performance Metrics table, and labeled the position VERIFYING.
- **Files modified:** `.planning/STATE.md`
- **Verification:** STATE now reports 6/6 plans, 100%, one completed milestone phase, a correctly placed Plan 06 metric, and ready-for-verification status.
- **Committed in:** Plan metadata commit.

---

**Total deviations:** 1 auto-fixed (1 tracking bug).
**Impact on plan:** Tracking-only correction; automated evidence and the pending physical boundary are unchanged.

## Issues Encountered

None.

## User Setup Required

None for the automated gate. Physical completion requires access to the official XIAO ESP32S3 STEP_ESP devices described in the HUMAN-UAT section.

## Known Stubs

None. `HUMAN NEEDED` / `Pending` entries are deliberate evidence gates, not product stubs.

## Threat Flags

None. This verification-only plan introduced no runtime endpoint, authentication path, file-access behavior, or schema change.

## Next Phase Readiness

- Automated Phase 20 evidence is complete.
- Physical Identify acceptance remains pending `HUMAN-UAT`.
- Phase 21 may proceed within its publisher/routing boundary; Phase 25 retains capacity and promotion ownership.

## Self-Check: PASSED

- This summary exists at the plan-required path.
- Task commit `a9ad06a` exists in Git history and deletes no tracked files.
- All 12 scoped paths still exist with the recorded post-run fingerprints.
- All five acceptance criteria pass: automated gate, required coverage, worktree preservation, explicit `human_needed` physical handoff, and Phase 21/25 boundaries.

---
*Phase: 20-full-identity-and-confirmed-identify*
*Completed: 2026-07-30*
