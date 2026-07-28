---
phase: 19
slug: studio-controls-live-angle
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-28
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Node `--test` through `tsx`; Python `unittest` |
| **Config file** | `rehab-robotics-studio/package.json`; backend tests are self-contained |
| **Quick run command** | `cd rehab-robotics-studio && npm test` or `python -m unittest backend.test.test_opensim_node backend.test.test_opensim_adapter` |
| **Full suite command** | `cd rehab-robotics-studio && npm test && npm run typecheck && npm run build`; then `python -m unittest discover -s backend/test -p "test_*.py"` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run the narrow test file named in that task
- **After every plan wave:** Run the affected frontend or backend suite
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | VIS-01 | T-19-01 | Browser invokes only the bounded ROS Trigger service; backend isolates adapter exceptions | backend unit | `python -m unittest backend.test.test_opensim_node backend.test.test_opensim_adapter` | ✅ | ⬜ pending |
| 19-02-01 | 02 | 1 | VIS-02, IK-06 | T-19-02 | Malformed, invalid, uncalibrated, and stale samples fail closed | frontend unit | `cd rehab-robotics-studio && npm test` | ✅ | ⬜ pending |
| 19-03-01 | 03 | 2 | VIS-01, VIS-02 | T-19-03 | Late rosbridge replies and stale samples cannot restore obsolete UI state | integration/build | `cd rehab-robotics-studio && npm test && npm run typecheck && npm run build` | ✅ | ⬜ pending |
| 19-03-02 | 03 | 2 | VIS-01, VIS-02 | — | Wireless operator sequence is repeatable and records native-window limitation | documentation + smoke | production-preview fake-rosbridge scenario | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Add focused frontend test coverage for JointState parsing, calibrated/valid/fresh
  gating, visualizer Trigger lifecycle, and stale-session protection.
- [ ] Add focused backend service tests for visualizer success, failure, idempotence,
  and exception isolation.
- [ ] Add a deterministic production-preview fake-rosbridge smoke script or test
  covering Toolbar → Calibrate → live angle → stale angle.

Existing Node and Python test infrastructure requires no new framework.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Native Simbody window opens and remains live under WSLg | VIS-01 | Current WSL runtime lacks the native `simbody-visualizer` component; fake adapters can verify the service contract but not OS window presentation | Start the OpenSim node in WSL with the runtime installed, connect Studio wirelessly, click `Open visualizer`, calibrate, confirm the native window updates, then retry/reopen while IK and recording remain alive |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
