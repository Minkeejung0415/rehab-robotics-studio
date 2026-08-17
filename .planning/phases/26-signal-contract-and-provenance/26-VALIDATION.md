---
phase: 26
slug: signal-contract-and-provenance
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-16
---

# Phase 26 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python pytest 9.1.1 collecting `unittest`; Node `node:test` through `tsx` 4.23.1 |
| **Config file** | Frontend commands in `rehab-robotics-studio/package.json`; no dedicated pytest config |
| **Quick run command** | `$env:PYTHONPATH='backend'; python -m pytest backend/test/test_signal_contract.py backend/test/test_measurement_contract.py backend/test/test_fleet_bridge.py -q; Push-Location rehab-robotics-studio; npm exec -- tsx --test src/data/signalContract.test.ts src/data/measurementContract.test.ts src/state/mappingStore.test.ts; Pop-Location` |
| **Full suite command** | `$env:PYTHONPATH='backend'; python -m pytest backend/test -q; Push-Location rehab-robotics-studio; npm test; npm run typecheck; Pop-Location` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick contract and integration suite.
- **After every plan wave:** Run the full backend suite, frontend tests, and TypeScript typecheck.
- **Before `$gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 120 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 26-01-01 | 01 | 1 | SIG-01 | T-26-01 | MAC/topic agreement and identity/time/epoch/capability fields fail closed | shared fixture + unit | `python -m pytest backend/test/test_signal_contract.py -k identity_time -q` | ❌ W0 | ⬜ pending |
| 26-01-02 | 01 | 1 | SIG-02 | T-26-02 | int16 raw counts remain exact and SI requires validated configuration | cross-language unit | `python -m pytest backend/test/test_measurement_contract.py -q` | ✅ extend | ⬜ pending |
| 26-01-03 | 01 | 1 | SIG-03 | magnetometer SI remains unavailable without sensitivity and calibration provenance | shared fixture + unit | `python -m pytest backend/test/test_signal_contract.py -k magnetometer -q` | ❌ W0 | ⬜ pending |
| 26-02-01 | 02 | 2 | SIG-04 | only applied assignments label accepted samples; old epochs remain immutable | integration + frontend unit | `python -m pytest backend/test/test_mapping_node.py backend/test/test_fleet_bridge.py -k applied -q` | ✅ extend | ⬜ pending |
| 26-02-02 | 02 | 2 | SIG-05 | incapable and invalid quaternion states remain distinct; no identity fallback | shared fixture + unit | `python -m pytest backend/test/test_signal_contract.py -k quaternion -q` | ❌ W0 | ⬜ pending |
| 26-02-03 | 02 | 2 | SIG-01..05 | Python and TypeScript accept/reject identical fixtures and reason codes | cross-language contract | `npm exec -- tsx --test src/data/signalContract.test.ts src/data/measurementContract.test.ts` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/test/fixtures/signal_contract_cases.json` — shared SIG-01..05 accept/reject/conversion/provenance cases.
- [ ] `backend/test/test_signal_contract.py` — pure backend builder/validator tests without ROS.
- [ ] `rehab-robotics-studio/src/data/signalContract.test.ts` — consumes the same fixture and asserts identical results/reason codes.
- [ ] Extend `rehab-robotics-studio/src/state/mappingStore.test.ts` with differing draft/applied assignments.
- [ ] Extend `backend/test/test_fleet_bridge.py` with reconnect generation, applied snapshot, capability, and time-origin publication assertions.
- [ ] Add byte-level old/new stream fixtures only if firmware framing is extended.

---

## Manual-Only Verifications

All Phase 26 behaviors have automated verification. Live ROS/hardware smoke evidence may supplement but does not replace the deterministic contract suite.

---

## Validation Sign-Off

- [x] All anticipated tasks have automated verification or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verification.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency < 120s.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-08-16 for planning; execution remains pending.
