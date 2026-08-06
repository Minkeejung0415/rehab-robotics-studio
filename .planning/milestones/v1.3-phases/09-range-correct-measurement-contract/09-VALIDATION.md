---
phase: 09
slug: range-correct-measurement-contract
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-23
---

# Phase 09 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Backend | Frontend |
|----------|---------|----------|
| **Framework** | Python `unittest` | Node `node:test` through project-local `tsx` |
| **Config file** | none | `rehab-robotics-studio/package.json` |
| **Quick run command** | `python -m unittest backend.test.test_measurement_contract -v` | `npm exec -- tsx --test src/data/measurementContract.test.ts src/data/RosbridgeDataSource.test.ts` |
| **Full suite command** | `$env:PYTHONPATH='backend'; python -m unittest discover -s backend/test -p 'test_*.py' -v` | `npm test && npm run typecheck` |
| **Estimated runtime** | under 30 seconds | under 60 seconds |

Frontend commands run from `rehab-robotics-studio/`. No new test runner or dependency is required.

---

## Sampling Rate

- **After every task commit:** Run the directly affected backend or frontend quick command.
- **After every plan wave:** Run backend discovery, frontend `npm test`, and frontend `npm run typecheck`.
- **Before `$gsd-verify-work`:** Both full suites must be green.
- **Max feedback latency:** 60 seconds.

---

## Per-Task Verification Map

Task identifiers are provisional until Phase 09 planning is complete. The planner must preserve this coverage when assigning final task IDs.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | DATA-01, DATA-02 | T-09-01 | Reject malformed or inconsistent scale metadata | unit, table-driven | `python -m unittest backend.test.test_measurement_contract -v` | no - W0 | pending |
| 09-01-02 | 01 | 1 | DATA-01, DATA-02 | T-09-01 | Use one acknowledged config snapshot for raw metadata and native SI | controlled bridge unit | `python -m unittest backend.test.test_measurement_contract -v` | no - W0 | pending |
| 09-01-03 | 01 | 2 | DATA-01 | T-09-01 | Preserve last confirmed range after rejection | controlled bridge unit | `python -m unittest backend.test.test_esp32_controls -v` | existing file needs cases | pending |
| 09-02-01 | 02 | 1 | DATA-01, DATA-02 | T-09-01, T-09-02 | Validate finite, supported, internally consistent metadata before conversion | shared-fixture unit | `npm exec -- tsx --test src/data/measurementContract.test.ts` | no - W0 | pending |
| 09-02-02 | 02 | 2 | DATA-02 | T-09-03, T-09-04 | Drop untrusted frames, warn once per connection, and clear cross-connection cache state | data-source unit | `npm exec -- tsx --test src/data/RosbridgeDataSource.test.ts` | no - W0 | pending |
| 09-02-03 | 02 | 2 | DATA-01 | T-09-01 | Coordinate the real master/slave services without optimistic state changes | data-source unit | `npm exec -- tsx --test src/data/RosbridgeDataSource.test.ts` | no - W0 | pending |
| 09-03-01 | 03 | 3 | DATA-01, DATA-02 | all | Prove both roles and all ranges agree across backend and GUI | full regression | backend discovery plus `npm test && npm run typecheck` | no - W0 | pending |

Status values: pending, green, red, or flaky.

---

## Threat Model

| Ref | Threat | Mitigation | Verification |
|-----|--------|------------|--------------|
| T-09-01 | Malformed, spoofed, or range-inconsistent `sensor_config` produces unsafe physical values | Strict shape, enum, unit, finite-number, and range/sensitivity consistency validation; fail closed | Python and TypeScript rejection partitions |
| T-09-02 | NaN or Infinity poisons relative/differential calculations | Require finite positive sensitivities before caching or conversion | Pure helper and data-source tests |
| T-09-03 | Invalid-frame traffic floods operator logs | One warning latch per WebSocket connection | Fake-WebSocket warning-count tests |
| T-09-04 | Cached peer samples cross connection boundaries | Clear master/slave caches and pair stabilizer whenever a new socket is created | Reconnect generation tests |

---

## Required Matrix

- Roles: `master`, `slave`.
- Accelerometer ranges: 2, 4, 8, and 16 g.
- Gyroscope ranges: 250, 500, 1000, and 2000 deg/s.
- Metadata rejection partitions: absent object, missing field, unsupported range, zero/negative/non-finite sensitivity, range/sensitivity mismatch, and missing/wrong unit token.
- Pair ordering: either role alone, both roles, invalid current role with a valid cached peer, and reconnect followed by one role.
- Acknowledgment outcomes: both success, unsupported before I/O, either device rejection, partial success with successful compensation, and partial success with failed compensation.

---

## Wave 0 Requirements

- [ ] `backend/rehab_robotics_bridge/measurement_contract.py` - pure scale definition, validation, and SI conversion seam.
- [ ] `backend/test/fixtures/measurement_contract_cases.json` - shared Python/TypeScript cases for every range and role.
- [ ] `backend/test/test_measurement_contract.py` - backend tables, raw JSON metadata, native SI, and filtered preservation.
- [ ] `rehab-robotics-studio/src/data/measurementContract.ts` - strict browser metadata validation and conversion seam.
- [ ] `rehab-robotics-studio/src/data/measurementContract.test.ts` - shared-fixture conversion and rejection cases.
- [ ] `rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts` - warning latch, cache, emission, service-name, and acknowledgment behavior.
- [ ] Extend `rehab-robotics-studio/package.json` test script to include `src/data/*.test.ts`; install nothing.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Non-default range is visible in a real raw message and produces the matching native ROS IMU value for each device | DATA-01, DATA-02 | ROS 2 runtime and paired hardware are unavailable in the local test environment | With both flashed devices connected, set a non-default range on each role, inspect one `/esp/raw/{role}` message for `sensor_config`, and compare one known raw axis count to `/imu/{role}` using the declared scale |
| Existing range controls, readouts, and warning row retain the Phase 09 UI contract | DATA-01, DATA-02 | Visual placement and operator clarity require a rendered UI | Exercise success, rejection, missing-metadata, later-valid, and reconnect cases; confirm no new panel, one persistent amber warning per connection, and no false Streaming state |

---

## Phase Acceptance

1. Raw counts remain integers and `topic_schema` remains `oe_esp32.raw.v1`.
2. Every accepted raw and filtered frame has a complete, internally consistent `sensor_config`.
3. Native ROS and GUI results match the shared fixture for all supported ranges and both roles.
4. Invalid metadata causes zero subscriber emissions, zero first-frame callbacks, and exactly one warning per connection.
5. A later valid frame resumes without a success notification.
6. A rejected request does not overwrite the rejecting node's last confirmed scale.
7. No timestamp, sequence, OE framing, quaternion, recovery retry, or freshness behavior changes in this phase.

---

## Validation Sign-Off

- [ ] All tasks have automated verification or explicit Wave 0 dependencies.
- [ ] Sampling continuity: no three consecutive tasks without automated verification.
- [ ] Wave 0 covers all missing test references.
- [ ] No watch-mode flags.
- [ ] Feedback latency is under 60 seconds.
- [ ] `nyquist_compliant: true` is set in frontmatter.

**Approval:** pending plan finalization.
