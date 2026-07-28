---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: OpenSim IK + Calibration + Visualizer Control
status: Phase 17 complete — ready for Phase 18
last_updated: "2026-07-28T18:12:00.000Z"
last_activity: 2026-07-28 — Executed 17-01, 17-02, 17-03; wrote 17-VERIFICATION.md
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 9
  completed_plans: 7
  percent: 50
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-07-28)

**Core value:** Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.
**Current focus:** Phase 17 complete — next is Phase 18 (Real-Time OpenSim IK Outputs) when started

## Current Position

Phase: 17 (Reference-Pose Calibration) — COMPLETE
Plan: 03/03
Status: Phase 17 complete — ready for Phase 18
Last activity: 2026-07-28 — Executed 17-01, 17-02, 17-03; wrote 17-VERIFICATION.md

Current Plan: 3 of 3
Total Plans in Phase: 3

## Performance Metrics

**Current milestone:**

| Phase-Plan | Duration | Tasks | Files |
|------------|----------|-------|-------|
| 16-01 | ~15min | 2 | 8 |
| 16-02 | ~12min | 2 | 10 |
| 16-03 | ~8min | 2 | 4 |
| 17-01 | ~12min | 2 | 3 |
| 17-02 | ~15min | 2 | 3 |
| 17-03 | ~18min | 2 | 8 |

- Total plans completed: 6 (v1.5 phases 16–17)

## Accumulated Context

### Decisions

- [v1.5]: Official OpenSim orientation IK only — custom relative-quat angle is not product IK.
- [v1.5 D-CAL-01]: Toolbar **Calibrate** (chrome next to Rec/Deploy).
- [v1.5 D-CAL-02]: Fixed known pose = standing, knees extended.
- [v1.5 D-CAL-03]: Hard gate — no joint-angle publication until CALIBRATED.
- [v1.5 D-CAL-04]: Separate **Clear cal** control.
- [v1.5 D-VIS-01]: Toolbar button starts/shows native OpenSim 3D visualizer.
- [v1.5 D-16-01]: Custom `/opensim/joint_angle` is not OpenSim IK; default product publish OFF.
- [v1.5 D-16-02]: Default GUI graph uses waiting placeholder until calibrated joint states.
- [v1.5 D-16-03]: Product output locked to `sensor_msgs/JointState` on `/opensim/joint_states`.
- [v1.5 D-16-04]: `may_publish_joint_states` true only when CALIBRATED.
- [v1.5 D-17]: DEFAULT_CAPTURE_WINDOW_S=1.5, MIN_SAMPLES=10, MAX_DISPERSION_DEG=8.0.
- [v1.5 D-17]: Failed re-capture while CALIBRATED keeps prior artifact (transactional).
- [v1.5 D-17]: Phase 17 never fabricates JointState even when CALIBRATED (solver = Phase 18).
- [v1.5 D-17]: Clear cal on toolbar only (no HealthPanel mirror).

### Pending Todos

None recorded.

### Blockers/Concerns

- Full OpenSense-compatible IK may require a dedicated solver process (research preferred C++ package); Phase 18 must choose deployable approach against current WSL OpenSim 4.5.2 Python path.
- Phase 15 native visualizer human smoke remains dependency-sensitive (`simbody-visualizer`).
- Phase 17 live hardware/rosbridge Calibrate smoke remains operator-side (unit/integration verified).

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Block Deployment | DEPLOY-01 through DEPLOY-04 | Parked | v1.2 |
| Clinical validation | External-reference accuracy claims | Out of v1.5 | v1.5 |
| Embedded Studio 3D | In-app solved-model renderer | Out of v1.5 | v1.5 |
| Calibration persistence | Cross-session versioned save/load | Deferred | Phase 17 |

---
*State updated: 2026-07-28*
