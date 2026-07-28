---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: OpenSim IK + Calibration + Visualizer Control
status: Autonomous discuss→plan→execute
last_updated: "2026-07-28T17:27:08.885Z"
last_activity: 2026-07-28 — Milestone v1.5 started; locked calibration decisions 1A/2A/3A/4A
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 3
  completed_plans: 1
  percent: 0
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-07-28)

**Core value:** Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.
**Current focus:** Phase 16 — Retire Custom Angle + IK Contracts

## Current Position

Phase: 16 (Retire Custom Angle + IK Contracts) — EXECUTING
Plan: —
Status: Autonomous discuss→plan→execute
Last activity: 2026-07-28 — Milestone v1.5 started; locked calibration decisions 1A/2A/3A/4A

## Performance Metrics

**Current milestone:**

- Total plans completed: 0

## Accumulated Context

### Decisions

- [v1.5]: Official OpenSim orientation IK only — custom relative-quat angle is not product IK.
- [v1.5 D-CAL-01]: Toolbar **Calibrate** (chrome next to Rec/Deploy).
- [v1.5 D-CAL-02]: Fixed known pose = standing, knees extended.
- [v1.5 D-CAL-03]: Hard gate — no joint-angle publication until CALIBRATED.
- [v1.5 D-CAL-04]: Separate **Clear cal** control.
- [v1.5 D-VIS-01]: Toolbar button starts/shows native OpenSim 3D visualizer.

### Pending Todos

None recorded.

### Blockers/Concerns

- Full OpenSense-compatible IK may require a dedicated solver process (research preferred C++ package); Phase 18 must choose deployable approach against current WSL OpenSim 4.5.2 Python path.
- Phase 15 native visualizer human smoke remains dependency-sensitive (`simbody-visualizer`).

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Block Deployment | DEPLOY-01 through DEPLOY-04 | Parked | v1.2 |
| Clinical validation | External-reference accuracy claims | Out of v1.5 | v1.5 |
| Embedded Studio 3D | In-app solved-model renderer | Out of v1.5 | v1.5 |

---
*State updated: 2026-07-28*
