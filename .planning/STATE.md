---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: Multi-Sensor Bone Mapping
status: planning
last_updated: "2026-07-30T17:54:08.812Z"
last_activity: 2026-07-30
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-07-28)

**Core value:** Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.
**Current focus:** Phase 19 — Studio Controls + Live Angle Display

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-07-30 — Milestone v1.6 started

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
| 18-01 | ~15min | 2 | 3 |
| 18-02 | ~20min | 2 | 3 |
| 18-03 | ~25min | 2 | 5 |

- Total plans completed: 9 (v1.5 phases 16–18)

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
- [v1.5 D-18-01]: Product angles only via OrientationIkSolver; never relative_orientation_angle_deg for JointState.
- [v1.5 D-18-02]: Prefer OpenSim 4.5.2 Python in opensim_bridge; C++ package deferred.
- [v1.5 D-18-03]: Unavailable fail-closed when OpenSim IK APIs/model missing.
- [v1.5 D-18-06]: ik_status String JSON + diagnostics String JSON (DiagnosticArray deferred).

### Pending Todos

None recorded.

### Blockers/Concerns

- Real OpenSim IK path is **Unavailable** on the Windows agent Python host (`opensim` not installed); validate Available path under WSL micromamba OpenSim 4.5.2 with a real `model_path`.
- Research still prefers dedicated C++ 4.6 streaming package long-term; Python path is the v1.5 pragmatic choice.
- Phase 15 native visualizer human smoke remains dependency-sensitive (`simbody-visualizer`).
- Phase 17/18 live hardware/rosbridge smoke remains operator-side (unit/integration verified).

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Block Deployment | DEPLOY-01 through DEPLOY-04 | Parked | v1.2 |
| Clinical validation | External-reference accuracy claims | Out of v1.5 | v1.5 |
| Embedded Studio 3D | In-app solved-model renderer | Out of v1.5 | v1.5 |
| Calibration persistence | Cross-session versioned save/load | Deferred | Phase 17 |
| C++ OpenSense package | rehab_robotics_opensim 4.6 streaming | Deferred | Phase 18 |
| Typed IkStatus.msg | rehab_robotics_interfaces | Deferred | Phase 18 |

---
*State updated: 2026-07-28*
