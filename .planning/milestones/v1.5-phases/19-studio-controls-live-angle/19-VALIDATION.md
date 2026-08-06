---
phase: 19
slug: studio-controls-live-angle
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-28
reviewed: 2026-07-28
---

# Phase 19 — Validation Strategy

> Every implementation task has a bounded automated command plus source, behavior,
> test, security, preservation, and (where applicable) UI acceptance criteria.
> Wave 0 remains incomplete only because new test/harness files are created during
> execution; their exact owning tasks and commands are already specified.

**Plan count:** 7 plans across 6 execution waves.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Node `--test` through installed `tsx`; Python `unittest`; installed Playwright for production DOM |
| **Config** | `rehab-robotics-studio/package.json`; backend tests are self-contained |
| **Quick frontend** | `cd rehab-robotics-studio; npm test` |
| **Quick backend** | `$env:PYTHONPATH='backend'; python -m unittest backend.test.test_opensim_node backend.test.test_opensim_adapter -v` |
| **Full gate** | Frontend test + typecheck + production fake-rosbridge E2E, then backend discovery |
| **Feedback target** | Narrow task command after each task; complete gate in Plan 05 |

## Wave Structure

| Wave | Plan | Ownership |
|------|------|-----------|
| 1 | 19-01 | Dirty-worktree checkpoint; backend visualizer adapter + Trigger |
| 2 | 19-02 | Live-angle types, pure contract, monotonic stale timer |
| 3 | 19-03 | Typed rosbridge/store/service/session integration |
| 4 | 19-04 | Default graph/SignalBus product routing |
| 4 | 19-05 | Toolbar + HealthPanel fast tests and plan-level production DOM |
| 5 | 19-06 | Nullable readouts, series clearing, approved CSS |
| 6 | 19-07 | QA syntax/contract gate, complete production E2E, full regression, runbook |

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Automated Command | Test Artifact State |
|---------|------|------|-------------|------------|-------------------|---------------------|
| 19-PF | 01 | 1 | Preservation gate | dirty-worktree | Exact-path `git status --short -- <all planned targets>` plus tracked diff/untracked content+SHA baseline | `19-WORKTREE-BASELINE.local.md` created before source edits |
| 19-01-01 | 01 | 1 | VIS-01, VIS-02 | T-19-01..04 | `$env:PYTHONPATH='backend'; python -m unittest backend.test.test_opensim_adapter -v` | Existing test extended |
| 19-01-02 | 01 | 1 | VIS-01, VIS-02 | T-19-01..04 | `$env:PYTHONPATH='backend'; python -m unittest backend.test.test_opensim_node backend.test.test_opensim_adapter -v` | Existing tests extended |
| 19-02-01 | 02 | 2 | IK-06, VIS-02 | T-19-05..11 | `cd rehab-robotics-studio; npm exec -- tsx --test src/data/liveKneeAngle.test.ts` | ❌ Wave 0: created in task |
| 19-03-01 | 03 | 3 | VIS-01, VIS-02, IK-06 | T-19-05,07,10,11 | `cd rehab-robotics-studio; npm exec -- tsx --test src/data/RosbridgeDataSource.test.ts` | Existing rosbridge test extended |
| 19-04-01 | 04 | 4 | IK-06, VIS-02 | T-19-13,19 | Direct `productKneeReadout.test.ts` + `liveKneeAngle.test.ts`, then typecheck | Existing graph test extended |
| 19-05-01 | 05 | 4 | VIS-01, VIS-02 | T-19-12,15,18 | Direct `HealthPanel.test.ts` + `Toolbar.test.ts` | Health test exists; Toolbar test created in task |
| 19-06-01 | 06 | 5 | IK-06, VIS-02 | T-19-13,19 | Direct `liveKneeAngle.test.ts`, then typecheck and build | Created by 19-02-01, extended here |
| 19-07-01 | 07 | 6 | VIS-01, VIS-02, IK-06 | T-19-14,17,20 | `node --check scripts/phase19-qa.mjs`, then `--contract-check` | QA script created by 19-05, completed here |

## Required Deterministic Assertions

- Backend: fixed argument-free `/opensim/visualizer/open` Trigger; idempotent open;
  native exceptions isolated from calibration, IK, JointState, diagnostics, recording.
- Rosbridge: malformed envelopes fail closed; all callbacks/replies/timeouts are
  socket-identity and generation guarded; obsolete sessions cannot mutate current UI.
- Live angle: CALIBRATED + valid + matching non-empty calibration ID + named finite
  coordinate + usable ordered source stamp + local receipt age <= 2,000 ms.
- Product path: PI/2 -> `90.0 deg`; valid zero -> `0.0 deg`; every closed gate -> `—`
  plus waiting copy and an empty/new trace.
- Plan 05 fast tests: toolbar order/controller, pending, duplicate suppression, settlement,
  retry, and all HealthPanel format/replacement cases.
- Plan 05 plan-level production DOM: exact toolbar order, `Opening…`, `aria-busy=true`,
  same-button focus preservation, one service request under duplicate attempts, failure
  persistence, enabled retry, and backend Open replacement.
- Final production flow: Open visualizer -> Calibrate -> invalid waiting -> valid live
  angle -> stale clearing -> recovery, plus malformed and superseded-session messages.

## Wave 0 Requirements

- [ ] `19-02-01` creates `src/data/liveKneeAngle.test.ts` before its command runs.
- [ ] `19-05-01` creates `Toolbar.test.ts` and `scripts/phase19-qa.mjs` with
  `--toolbar-only` before its
  production-DOM command runs.
- [ ] `19-07-01` completes the same QA script, adds `--contract-check`, and adds
  `test:phase19`.
- [ ] The preflight creates the local baseline record before any source edit.

Wave 0 is intentionally marked incomplete at planning time because these files do not
yet exist. Nyquist compliance is true because every missing artifact has an owning
task, exact behavior criteria, and an automated command; execution must not mark
`wave_0_complete: true` until the files exist and their first commands pass.

## Manual-Only Verification

| Behavior | Requirement | Classification | Instructions |
|----------|-------------|----------------|--------------|
| Native Simbody window opens/updates/reopens under WSLg | VIS-01 | `human_needed` only when `simbody-visualizer` runtime is absent | Follow the updated wireless runbook; confirm window behavior while calibrated IK and recording remain operational |

## Dirty-Worktree Preservation Gate

- One blocking checkpoint precedes all source work in Plan 01.
- It rechecks every planned exact path, including known modified `app.css` and
  untracked `DataSource.ts`, `signalBus.ts`, `systemStore.ts`, `MiniChart.tsx`,
  and `MotorPanel.tsx`; it also checks the newly planned `Toolbar.test.ts`.
- Tracked diffs and complete untracked contents/hashes are recorded before approval.
- Executors must never stash/reset/checkout/clean/replace these files.
- Every task rechecks its exact paths and stages only explicit phase-owned files;
  broad `git add .`, `git add -A`, and globs are prohibited.

## Validation Sign-Off

- [x] Every implementation task has `<read_first>`.
- [x] Every implementation task has independently checkable `<acceptance_criteria>`.
- [x] Every implementation task has an `<automated>` command.
- [x] No three consecutive implementation tasks lack automated feedback.
- [x] High-severity service, message, session, stale-data, and native-adapter threats are blocked by tests.
- [x] Production build and fake-rosbridge E2E are owned by final Plan 07.
- [ ] Wave 0 artifacts created and first commands green — execution-time gate.

**Approval:** approved planning contract — reviewed 2026-07-28
