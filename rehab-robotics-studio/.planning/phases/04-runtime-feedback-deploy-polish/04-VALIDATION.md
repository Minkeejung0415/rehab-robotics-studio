---
phase: 4
slug: runtime-feedback-deploy-polish
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-13
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none — match Phases 1–3; no new test deps |
| **Config file** | none |
| **Quick run command** | `npm run typecheck` |
| **Full suite command** | `npm run typecheck && npm run build` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `npm run typecheck`
- **After every plan wave:** Run `npm run typecheck && npm run build`
- **Before `/gsd:verify-work`:** Full suite must be green + browser checklist
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-T1 | 01 | 1 | RT-01 | T-4-01 | Typed BlockStatus only | typecheck | `npm run typecheck` | ✅ | ⬜ pending |
| 04-01-T2 | 01 | 1 | RT-01 | T-4-01 | Runtime→graph sync only on successful transitions | typecheck+build | `npm run typecheck && npm run build` | ✅ | ⬜ pending |
| 04-02-T1 | 02 | 2 | DEP-01 | T-4-04 | Toast text nodes; locked copy from parent | typecheck | `npm run typecheck` | ✅ | ⬜ pending |
| 04-02-T2 | 02 | 2 | RT-02, DEP-01 | T-4-05, T-4-06 | Mock copy; Rec disabled when blocked | typecheck+build | `npm run typecheck && npm run build` | ✅ | ⬜ pending |
| 04-02-T3 | 02 | 2 | RT-01, RT-02, DEP-01 | — | Browser gate | typecheck+build | `npm run typecheck && npm run build` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements (typecheck + build + browser checklist). Do **not** install a test runner in this phase.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Badges on Run/Stop | RT-01 | No e2e unit suite | Run → all `running`; Stop → all `idle`; Pause keeps `running` |
| Rec → strip | RT-02 | No e2e unit suite | Toggle Rec; strip Recording On/Off; disabled when estopped |
| Deploy toast | DEP-01 | No e2e unit suite | Deploy → toast + log; auto-dismiss; click dismiss; no stack |

---

## Validation Sign-Off

- [x] All tasks have automated verify (`typecheck`) or Wave 0 documentation
- [x] Sampling continuity via typecheck after commits
- [x] Wave 0: no framework install (intentional)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-13 (planner autonomous)
