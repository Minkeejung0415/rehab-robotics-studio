---
gsd_state_version: 1.0
milestone: v1.7
milestone_name: Multi-Sensor Signal Viewer & 3D Mapping Validation
status: verifying
stopped_at: Completed 26-06-PLAN.md
last_updated: "2026-08-17T17:24:43.633Z"
last_activity: 2026-08-17
progress:
  total_phases: 7
  completed_phases: 1
  total_plans: 6
  completed_plans: 6
  percent: 100
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-08-13)

**Core value:** Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.
**Current focus:** Phase 26 — Signal Contract and Provenance

## Current Position

Phase: 26 (Signal Contract and Provenance) — VERIFYING
Plan: 6 of 6
Status: Phase complete — ready for verification
Last activity: 2026-08-17

Progress: [██████████] 100%

## Performance Metrics

**Current milestone:**

- Plans completed: 6
- Phases completed: 1/7
- Average duration: 2h 37min
- Total execution time: 15h 41min

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 26-32 | 6 | 15h 41min | 2h 37min |

**Prior milestone reference:** v1.6 Phases 20-25 completed on 2026-08-05; detailed execution artifacts remain preserved.
| Phase 26 P01 | 7min | 3 tasks | 5 files |
| Phase 26 P02 | 8min | 3 tasks | 5 files |
| Phase 26 P03 | 11min | 3 tasks | 5 files |
| Phase 26 P04 | 9min | 2 tasks | 4 files |
| Phase 26 P05 | 5min | 2 tasks | 4 files |
| Phase 26 P06 | 15h 1min | 3 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in `PROJECT.md`. Current milestone decisions:

- Display is bounded and lossy; backend recording remains full-rate and independent.
- Full MAC plus the authoritative applied mapping revision owns trace and export identity.
- Reconnects and applied remaps create explicit provenance epochs and visible gaps.
- Magnetometer SI is available only with validated sensitivity and calibration provenance.
- Milestone acceptance requires calibrated physical remap evidence in the native OpenSim visualizer without accuracy claims.
- [Phase 26]: Canonical integers use cross-language safe bounds and applied labels/hashes use fixed maximum lengths. — Prevents Python and TypeScript precision or unbounded-input divergence.
- [Phase 26]: Quaternion values are preserved exactly and accepted only inside the bounded norm policy. — Consumers must not normalize or fabricate orientation.
- [Phase 26]: Magnetometer SI requires sensitivity plus bounded xyz calibration provenance. — Nominal sensitivity alone cannot authorize microtesla.
- [Phase 26]: The browser parser validates shared fixture inputs and serialized canonical envelopes into one deeply frozen sample.
- [Phase 26]: Canonical availability must agree with explicit source capabilities; contradictions fail closed.
- [Phase 26]: Magnetometer microtesla requires both validated sensitivity and bounded calibration provenance.
- [Phase 26]: Firmware signal-cap-v1 declarations are the sole capability source; route metadata is comparison-only.
- [Phase 26]: Binary sample framing remains OeHeader plus 14 int16; sequence and timing origins remain bridge-session facts.
- [Phase 26]: Mapping provenance epochs advance only on changed applied snapshots.
- [Phase 26]: Mapping-current payloads validate draft and applied assignments independently and freeze the applied snapshot.
- [Phase 26]: Canonical rosbridge topics derive only from normalized fleet full MAC identities; payload topic aliases are ignored.
- [Phase 26]: Rejections emit bounded counts on every event while repeated identical source/reason announcements are suppressed.
- [Phase 26]: Canonical accepted and rejected callbacks remain separate from legacy Frame subscriptions and are silent while mock fallback is active.
- [Phase 26]: SignalBus retains parser-owned immutable samples by exact full MAC and copies only snapshot maps at the bounded publication boundary.
- [Phase 26]: Rejection totals and per-source metadata are bounded; repeated source/reason signatures suppress announcements without suppressing counts.
- [Phase 26]: Raw/SI selection remains local to each source card and retained SI mode fails closed with em dashes when later validity disappears.
- [Phase 26]: Signal Contract presentation remains pure for server rendering while Dashboard owns useSignals and bounded rejection logging.
- [Phase 26]: Rejection feedback retains last accepted values and announces only changed per-source reason signatures.

### Pending Todos

None recorded.

### Blockers/Concerns

- Phase 26 must confirm deployed magnetometer sensitivity/range, axis convention, calibration provenance, quaternion validity policy, and available acquisition timebase.
- Phase 28 must measure and declare the supported fleet/rate/channel/window envelope and responsiveness thresholds on target-class hardware.
- Phase 29 must lock the recorder schema and available firmware/software provenance sources during planning.
- Phase 30 requires physical ESP hardware, a discriminating movement protocol, recalibration, and retained native visualizer evidence.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Block Deployment | DEPLOY-01 through DEPLOY-04 | Parked | v1.2 |
| Acquisition Integrity | Remaining unfinished scope | Preserved | v1.3 |
| Advanced analysis | FFT, derived channels, and external-system synchronization | Future | v1.7 |
| Clinical validation | External-reference accuracy claims | Out of scope | v1.7 |
| Embedded Studio 3D | In-app solved-model renderer | Out of scope | v1.7 |

## Session Continuity

Last session: 2026-08-17T17:24:43.623Z
Stopped at: Completed 26-06-PLAN.md
Resume file: None
