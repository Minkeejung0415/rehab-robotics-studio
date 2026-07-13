---
phase: 3
slug: context-menu-block-management
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-13
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none — match Phases 1–2; no new test deps |
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
| 03-01-T1 | 01 | 1 | CTX-03, BLK-01, BLK-02 | T-3-01 | Controlled rename string; shallow param clone | typecheck | `npm run typecheck` | ✅ | ⬜ pending |
| 03-01-T2 | 01 | 1 | CTX-03 | T-3-02 | Multi-delete only selected ids | typecheck | `npm run typecheck` | ✅ | ⬜ pending |
| 03-02-T1 | 02 | 2 | CTX-01, CTX-02, CTX-03 | T-3-01 | preventDefault on handled targets only | typecheck | `npm run typecheck` | ✅ | ⬜ pending |
| 03-02-T2 | 02 | 2 | BLK-01, CTX-01 | T-3-01 | React text escape; empty blur revert | typecheck+build | `npm run typecheck && npm run build` | ✅ | ⬜ pending |
| 03-02-T3 | 02 | 2 | CTX-01–03, BLK-01–02 | — | Browser gate | typecheck+build | `npm run typecheck && npm run build` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements (typecheck + build + browser checklist). Do **not** install a test runner in this phase.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Block context menu | CTX-01 | No e2e runner | Right-click block → Duplicate / Rename / Delete; native menu suppressed |
| Wire context menu | CTX-02 | No e2e runner | Right-click wire → Delete removes wire only |
| Select All | CTX-03 | No e2e runner | Right-click canvas → Select All; all blocks selected; wires not |
| Rename in properties | BLK-01 | No e2e runner | Edit Name; canvas label updates; empty blur reverts |
| Duplicate offset | BLK-02 | No e2e runner | Duplicate → +40,+40, name ends with ` copy`, no new wires |
| Multi-delete | CTX-03 + GRAPH | No e2e runner | Select All then Delete removes all selected blocks |

---

## Validation Sign-Off

- [x] All tasks have automated verify (`typecheck`) or Wave 0 documentation
- [x] Sampling continuity via typecheck after commits
- [x] Wave 0: no framework install (intentional)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-13
