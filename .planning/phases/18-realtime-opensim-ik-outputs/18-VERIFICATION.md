---
phase: 18-realtime-opensim-ik-outputs
verified: 2026-07-28T18:55:00Z
status: passed
score: 3/3 must-haves verified
overrides_applied: 0
opensim_ik_path: Unavailable
human_verification:
  - test: "On WSL micromamba OpenSim 4.5.2 with a real .osim model_path, run opensim_bridge CALIBRATED with live master/slave IMUs."
    expected: "If probe shows InverseKinematicsSolver+OrientationsReference, /opensim/joint_states publishes knee_angle_r radians with source stamps; else ik_status reason opensim_ik_api_unavailable / model_path_* and no JointState."
    why_human: "This Windows agent host has no opensim Python module; binding integration tests skipUnless. Operator validates Available path on WSL OpenSim env."
---

# Phase 18: Real-Time OpenSim IK Outputs Verification Report

**Phase Goal:** After Phase 17 calibration is CALIBRATED, run official OpenSim orientation IK (or fail-closed Unavailable) on paired IMU orientations, publish solved joint coordinates on `/opensim/joint_states`, and expose IK validity/residuals/age/calibration identity on status topics. Do not start Phase 19 Studio display.
**Verified:** 2026-07-28T18:55:00Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Official Orientation IK solves joint coordinates after calibration (Fake in tests; OpenSim when APIs allow) | VERIFIED | `orientation_ik.py` Fake known-pose + `opensim_orientation_ik.py` factory; node injects Fake and publishes; production uses `create_orientation_ik_solver` |
| 2 | Solved coordinates publish on `/opensim/joint_states` with source stamps | VERIFIED | `_maybe_publish_joint_states` sets `header.stamp` from `source_timestamp_ns`; node tests assert stamp sec=200 |
| 3 | IK validity/residuals/age/calibration_id observable via ik_status + diagnostics | VERIFIED | `/opensim/ik_status` schema `rehab.opensim_ik_status.1`; embedded `ik` in `/opensim/status`; `/diagnostics` String JSON heartbeat |

**Score:** 3/3 ROADMAP truths verified at unit/integration level.

### Requirement Trace

| Req | Status | Evidence |
|---|---|---|
| IK-05 | Complete | OrientationIkSolver + OpenSim factory + node solve path; never relative_orientation_angle_deg for JointState |
| IK-06 | Complete | Stamped `sensor_msgs/JointState` on `/opensim/joint_states` when CALIBRATED+valid |
| IK-07 | Complete | ik_status + diagnostics + status.ik embed |

### Required Artifacts

| Artifact | Status | Details |
|---|---|---|
| `opensim/orientation_ik.py` | VERIFIED | IkSolution, Fake, Unavailable, offsets |
| `opensim/opensim_orientation_ik.py` | VERIFIED | probe + factory + OpenSimOrientationIkSolver |
| `test_opensim_orientation_ik.py` | VERIFIED | 7/7 pass |
| `test_opensim_orientation_ik_opensim.py` | VERIFIED | 3 always-on pass; 2 skipUnless (opensim absent) |
| `opensim_node.py` IK wiring | VERIFIED | solve, stamp, clear reset, publishers |
| `test_opensim_node.py` | VERIFIED | IK gate/status/diagnostics tests green |
| `docs/opensim-ik-contracts.md` | VERIFIED | Phase 18 schema + stamp policy |

### Automated Test Results

```
$env:PYTHONPATH='backend'; python -m unittest `
  backend.test.test_opensim_node `
  backend.test.test_opensim_orientation_ik `
  backend.test.test_opensim_orientation_ik_opensim `
  backend.test.test_ik_contracts `
  backend.test.test_opensim_calibration -q
→ Ran 47+ tests — OK (2 skipped: opensim not installed)
```

### OpenSim IK path in this environment

| Environment | Status |
|---|---|
| Windows agent Python (`importlib.util.find_spec("opensim")`) | **Unavailable** — False |
| Production factory with empty/missing `model_path` | Returns `UnavailableOrientationIkSolver` (fail closed) |
| WSL micromamba OpenSim 4.5.2 | Not verified in this run — operator/human smoke above |

**Product rule held:** Never uses `relative_orientation_angle_deg` as JointState source.

### Key Links

| From | To | Status |
|---|---|---|
| Dual-live IMU update | `OrientationIkSolver.solve` | WIRED |
| `_ik_solution` | `/opensim/joint_states` | WIRED (valid+CALIBRATED+stamp) |
| `ik_status_dict` | `/opensim/ik_status` + `status.ik` | WIRED |
| Clear cal | `ik_solver.reset()` + clear solution | WIRED |
| `create_orientation_ik_solver` | OpenSim or Unavailable | WIRED (never Fake in production) |

### Gaps / Deferred

- Phase 19 Studio JointState subscription / live knee display — not started
- Phase 19 visualizer toolbar button — not started
- Typed `IkStatus.msg` / `diagnostic_msgs/DiagnosticArray` — deferred (String JSON used)
- C++ `rehab_robotics_opensim` 4.6 streaming package — deferred (D-18-02)
- Live WSL OpenSim Available-path smoke — human verification above

### Plan Summaries

- `18-01-SUMMARY.md` — Orientation IK seam
- `18-02-SUMMARY.md` — OpenSim factory/adapter
- `18-03-SUMMARY.md` — Node wiring + contracts

### Blockers

None blocking Phase 18 unit/integration completion. OpenSim bindings absent on this Windows host → real IK path **Unavailable** until run under WSL OpenSim env with a valid `model_path`.
