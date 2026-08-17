---
phase: 26
slug: signal-contract-and-provenance
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-16
updated: 2026-08-16
---

# Phase 26 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python pytest 9.1.1 collecting `unittest`; Node `node:test` through `tsx` 4.23.1 |
| **Config file** | Frontend commands in `rehab-robotics-studio/package.json`; no dedicated pytest config |
| **Quick run command** | `$env:PYTHONPATH='backend'; & python -m pytest backend/test/test_signal_contract.py backend/test/test_measurement_contract.py backend/test/test_fleet_bridge.py backend/test/test_stepesp_firmware_topology.py -q; if($LASTEXITCODE -ne 0){throw 'backend quick suite failed'}; Push-Location rehab-robotics-studio; try { & npm exec -- tsx --test src/data/signalContract.test.ts src/data/measurementContract.test.ts src/data/RosbridgeDataSource.test.ts src/data/signalBus.test.ts src/state/mappingStore.test.ts src/components/dashboard/SignalContractPanel.test.tsx; if($LASTEXITCODE -ne 0){throw 'frontend quick suite failed'} } finally { Pop-Location }` |
| **Full suite command** | `$env:PYTHONPATH='backend'; & python -m pytest backend/test -q; if($LASTEXITCODE -ne 0){throw 'backend full suite failed'}; Push-Location rehab-robotics-studio; try { & npm test; if($LASTEXITCODE -ne 0){throw 'frontend full suite failed'}; & npm run typecheck; if($LASTEXITCODE -ne 0){throw 'frontend typecheck failed'} } finally { Pop-Location }` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task-specific command below, then the quick contract/integration suite when the task is GREEN.
- **After every plan wave:** Run the full backend suite, frontend tests, and TypeScript typecheck.
- **Before `$gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 120 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 26-01-01 | 01 | 1 | SIG-01..05 | T-26-01..05 | Shared cases execute the builder and fail only on the intended unimplemented behavior | focused inverted RED | `$env:PYTHONPATH='backend'; $o=& python -m pytest backend/test/test_signal_contract.py -k identity_time -q 2>&1; $c=$LASTEXITCODE; $t=[string]::Join(' ', $o); if($c -ne 1 -or $t -notmatch 'canonical_validation_unimplemented'){throw 'wrong RED state'}` | ❌ W0 | ⬜ pending |
| 26-01-02 | 01 | 1 | SIG-01, SIG-04, SIG-05 | T-26-01..04 | MAC/topic, timing/epoch, applied snapshot, bounded labels, and quaternion guards fail closed | Python unit | `python -m pytest backend/test/test_signal_contract.py -k "identity_time or quaternion or applied" -q` | ❌ W0 | ⬜ pending |
| 26-01-03 | 01 | 1 | SIG-02, SIG-03 | T-26-02, T-26-05 | Exact raw int16 values and validated sensitivity/calibration SI gate | Python unit | `python -m pytest backend/test/test_measurement_contract.py backend/test/test_signal_contract.py -q` | ✅ extend/W0 | ⬜ pending |
| 26-02-01 | 02 | 2 | SIG-01..05 | T-26-06..10 | Readonly TS contract and shared fixture establish only the intended parser RED state | focused inverted RED | `Push-Location rehab-robotics-studio; try { $o=& npm exec -- tsx --test src/data/signalContract.test.ts 2>&1; $c=$LASTEXITCODE; $t=[string]::Join(' ', $o); if($c -ne 1 -or $t -notmatch 'canonical_parser_unimplemented'){throw 'wrong RED state'} } finally { Pop-Location }` | ❌ W0 | ⬜ pending |
| 26-02-02 | 02 | 2 | SIG-02, SIG-03 | T-26-07, T-26-10 | TS measurement validation and µT gating match Python | Node unit | `Push-Location rehab-robotics-studio; try { & npm exec -- tsx --test src/data/measurementContract.test.ts; if($LASTEXITCODE -ne 0){throw 'measurement tests failed'} } finally { Pop-Location }` | ✅ extend | ⬜ pending |
| 26-02-03 | 02 | 2 | SIG-01..05 | T-26-06..10 | Unknown JSON accepts/rejects identically across Python and TS | cross-language contract | `Push-Location rehab-robotics-studio; try { & npm exec -- tsx --test src/data/signalContract.test.ts src/data/measurementContract.test.ts; if($LASTEXITCODE -ne 0){throw 'contract tests failed'}; & npm run typecheck; if($LASTEXITCODE -ne 0){throw 'typecheck failed'} } finally { Pop-Location }` | ❌ W0 | ⬜ pending |
| 26-03-01 | 03 | 2 | SIG-01, SIG-03, SIG-05 | T-26-11, T-26-12, T-26-15 | Source capability protocol, unchanged frame bytes, and calibration gate establish intended RED assertions | focused inverted RED + byte contract | `$env:PYTHONPATH='backend'; $o=& python -m pytest backend/test/test_fleet_bridge.py backend/test/test_stepesp_firmware_topology.py -k signal_status_protocol -q 2>&1; $c=$LASTEXITCODE; $t=[string]::Join(' ', $o); if($c -ne 1 -or $t -notmatch 'signal_status_protocol'){throw 'wrong RED state'}` | ✅ extend | ⬜ pending |
| 26-03-02 | 03 | 2 | SIG-04 | T-26-13, T-26-14 | Only applied snapshots increment mapping provenance; reconnect remains independent | backend integration | `python -m pytest backend/test/test_mapping_node.py backend/test/test_fleet_bridge.py -k "applied or provenance or reconnect" -q` | ✅ extend | ⬜ pending |
| 26-03-03 | 03 | 2 | SIG-01..05 | T-26-11..15 | Identity-bound firmware status is the sole capability source; additive envelope uses honest timing | firmware/source + backend integration | `python -m pytest backend/test/test_signal_contract.py backend/test/test_measurement_contract.py backend/test/test_fleet_bridge.py backend/test/test_stepesp_firmware_topology.py -q` | ✅ extend | ⬜ pending |
| 26-04-01 | 04 | 3 | SIG-04 | T-26-18, T-26-19 | Draft and bounded applied snapshots stay separate and atomic | Node store/integration | `Push-Location rehab-robotics-studio; try { & npm exec -- tsx --test src/state/mappingStore.test.ts src/data/RosbridgeDataSource.test.ts; if($LASTEXITCODE -ne 0){throw 'mapping tests failed'} } finally { Pop-Location }` | ✅ extend | ⬜ pending |
| 26-04-02 | 04 | 3 | SIG-01, SIG-04, SIG-05 | Dynamic topics enforce MAC agreement; rejections cannot reach accepted callbacks | Node integration | `Push-Location rehab-robotics-studio; try { & npm exec -- tsx --test src/data/RosbridgeDataSource.test.ts src/data/signalContract.test.ts src/state/mappingStore.test.ts; if($LASTEXITCODE -ne 0){throw 'ingress tests failed'}; & npm run typecheck; if($LASTEXITCODE -ne 0){throw 'typecheck failed'} } finally { Pop-Location }` | ✅ extend | ⬜ pending |
| 26-05-01 | 05 | 4 | SIG-01 | T-26-21, T-26-22, T-26-25 | Accepted/rejected subscriptions stay separate; mock mode fabricates no source | Node unit | `Push-Location rehab-robotics-studio; try { & npm exec -- tsx --test src/data/signalBus.test.ts src/data/RosbridgeDataSource.test.ts; if($LASTEXITCODE -ne 0){throw 'subscription tests failed'} } finally { Pop-Location }` | ❌ W0/extend | ⬜ pending |
| 26-05-02 | 05 | 4 | SIG-01..05 | T-26-21..25 | Full-MAC latest state is immutable, bounded-rate, and rejection-retaining | Node unit | `Push-Location rehab-robotics-studio; try { & npm exec -- tsx --test src/data/signalBus.test.ts src/data/signalContract.test.ts; if($LASTEXITCODE -ne 0){throw 'signal bus tests failed'}; & npm run typecheck; if($LASTEXITCODE -ne 0){throw 'typecheck failed'} } finally { Pop-Location }` | ❌ W0 | ⬜ pending |
| 26-06-01 | 06 | 5 | SIG-02, SIG-03, SIG-04, SIG-05 | T-26-27..30 | Presentation never fabricates SI/quaternion and maps bounded availability copy accessibly | server-render + pure view-model unit | `Push-Location rehab-robotics-studio; try { & npm exec -- tsx --test src/components/dashboard/SignalContractPanel.test.tsx; if($LASTEXITCODE -ne 0){throw 'panel tests failed'}; & npm run typecheck; if($LASTEXITCODE -ne 0){throw 'typecheck failed'} } finally { Pop-Location }` | ❌ W0 | ⬜ pending |
| 26-06-02 | 06 | 5 | SIG-01, SIG-04 | T-26-26..30 | Persistent panel retains accepted values on rejection and renders applied identity first | component + bus unit | `Push-Location rehab-robotics-studio; try { & npm exec -- tsx --test src/components/dashboard/SignalContractPanel.test.tsx src/data/signalBus.test.ts; if($LASTEXITCODE -ne 0){throw 'panel composition tests failed'}; & npm run typecheck; if($LASTEXITCODE -ne 0){throw 'typecheck failed'} } finally { Pop-Location }` | ❌ W0 | ⬜ pending |
| 26-06-03 | 06 | 5 | SIG-01..05 | T-26-26..30 | Responsive production build and full phase contract stay green | full regression/build | `$env:PYTHONPATH='backend'; & python -m pytest backend/test/test_signal_contract.py backend/test/test_measurement_contract.py backend/test/test_fleet_bridge.py backend/test/test_stepesp_firmware_topology.py -q; if($LASTEXITCODE -ne 0){throw 'backend phase tests failed'}; Push-Location rehab-robotics-studio; try { & npm test; if($LASTEXITCODE -ne 0){throw 'frontend tests failed'}; & npm run typecheck; if($LASTEXITCODE -ne 0){throw 'typecheck failed'}; & npm run build; if($LASTEXITCODE -ne 0){throw 'build failed'} } finally { Pop-Location }` | ✅ suite | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/test/fixtures/signal_contract_cases.json` — shared SIG-01..05 accept/reject/conversion/provenance cases.
- [ ] `backend/test/test_signal_contract.py` — pure backend builder/validator tests without ROS.
- [ ] `rehab-robotics-studio/src/data/signalContract.test.ts` — shared-fixture TS acceptance and reason-code parity.
- [ ] Focused firmware/fleet `signal_status_protocol` cases — old/no-response, valid, malformed, duplicate, MAC mismatch, route-expectation mismatch, and reconnect refresh.
- [ ] Byte-level current-frame cases — exact `OeHeader + 14 int16` wire contract with no transmitted device sequence/time.
- [ ] `rehab.mag_calibration.1` cases — valid, missing, invalid hash, MAC/sensor mismatch, invalid axes, and non-finite/bad-shape coefficients.
- [ ] Extend `rehab-robotics-studio/src/state/mappingStore.test.ts` with differing draft/applied assignments.
- [ ] Extend `backend/test/test_fleet_bridge.py` with reconnect generation, applied snapshot, source capability, calibration, and time-origin assertions.
- [ ] `rehab-robotics-studio/src/data/signalBus.test.ts` — immutable latest-by-MAC and bounded rejection state.
- [ ] `rehab-robotics-studio/src/components/dashboard/SignalContractPanel.test.tsx` — availability matrix, exact copy, accessibility, and server-render contract.
- [ ] Keep firmware stream framing unchanged; any later negotiated extension requires separately approved old/new fixtures.

---

## Manual-Only Verifications

All Phase 26 behaviors have automated verification. Live ROS/hardware smoke evidence may supplement but does not replace the deterministic contract suite.

---

## Validation Sign-Off

- [x] All 16 actual plan tasks appear in the Per-Task Verification Map with automated verification or explicit Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verification.
- [x] Wave 0 covers contract/parser/bus/panel files, source-status protocol cases, unchanged-frame byte cases, and calibration artifacts.
- [x] RED tasks use explicit exit-code/output inversion and cannot pass on import/collection errors.
- [x] Source capability origin and route-expectation mismatch are covered before canonical publication.
- [x] No watch-mode flags.
- [x] Feedback latency ≤ 120s.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-08-16 for revised planning; execution remains pending.
