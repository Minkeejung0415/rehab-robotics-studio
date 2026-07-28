---
phase: 17-reference-pose-calibration
verified: 2026-07-28T18:12:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "With rosbridge + opensim_bridge running and live master/slave IMUs, press Toolbar Calibrate while standing with knees extended."
    expected: "Toast shows standing/knees-extended instruction; HealthPanel moves CAPTURING→CALIBRATED (or FAILED with dispersion reason); /opensim/joint_states stays empty until Phase 18 IK."
    why_human: "Executor verified ROS-free unit/integration tests and Studio Trigger facades; live hardware/rosbridge smoke is operator-side."
---

# Phase 17: Reference-Pose Calibration Verification Report

**Phase Goal:** Make sensor-to-model mounting-offset calibration possible from Studio chrome; multi-sample stable window; hard-gate joint-angle publication until CALIBRATED.
**Verified:** 2026-07-28T18:12:00Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Toolbar Calibrate captures a standing / knees-extended stable window and produces mounting offsets | VERIFIED | `Toolbar.tsx` Calibrate → `captureOpenSimCalibration` → `/opensim/calibration/capture`; controller averages antipode-aware quats into `CalibrationArtifact`; tests in `test_opensim_calibration.py` and node path tests |
| 2 | Clear cal returns to UNCALIBRATED and invalidates offsets | VERIFIED | Clear service + `CalibrationController.clear()`; toolbar **Clear cal**; unit + node tests |
| 3 | No joint angles published until CALIBRATED (and no fabricated IK in Phase 17) | VERIFIED | `may_publish_joint_states` + `_maybe_publish_joint_states` requires solution; joint publisher empty while uncalibrated and when calibrated without IK |
| 4 | Front Panel shows calibration state and reason | VERIFIED | HealthPanel rows + `formatCalibrationStatus`; status embedded in `/opensim/status` |

**Score:** 4/4 ROADMAP truths verified at unit/integration level.

### Requirement Trace

| Req | Status | Evidence |
|---|---|---|
| IK-01 | Complete | Toolbar Calibrate + capture service + stable window |
| IK-02 | Complete | Toolbar Clear cal + clear service |
| IK-03 | Complete | Hard gate in controller + node JointState seam |
| IK-04 | Complete | HealthPanel state/reason from `openSim.calibration` |

### Required Artifacts

| Artifact | Status | Details |
|---|---|---|
| `opensim/calibration.py` | VERIFIED | CalibrationController + artifact |
| `test_opensim_calibration.py` | VERIFIED | 7/7 pass |
| `opensim_node.py` calibration wiring | VERIFIED | Trigger services, status, gate |
| `test_opensim_node.py` calibration tests | VERIFIED | 6 new + prior suite green (34 total with contracts) |
| Studio Toolbar / HealthPanel / facades | VERIFIED | Calibrate/Clear cal + status rows |
| Studio tsx tests | VERIFIED | 18/18 pass (Rosbridge + formatCalibrationStatus) |

### Automated Test Results

```
$env:PYTHONPATH='backend'; python -m unittest backend.test.test_opensim_calibration backend.test.test_opensim_node backend.test.test_ik_contracts -q
→ Ran 34 tests — OK

cd rehab-robotics-studio; npx tsx --test src/data/RosbridgeDataSource.test.ts src/components/dashboard/HealthPanel.test.ts
→ 18 tests — pass 18
```

### Key Links

| From | To | Status |
|---|---|---|
| Toolbar | `captureOpenSimCalibration` / `clearOpenSimCalibration` | WIRED |
| RosbridgeDataSource | `/opensim/calibration/capture\|clear` Trigger | WIRED |
| OpenSimBridgeNode | CalibrationController feed_pair | WIRED |
| `_maybe_publish_joint_states` | `may_publish_joint_states` + `_ik_solution` | WIRED (solution always None in Phase 17) |
| HealthPanel | `openSim.calibration.state/reason` | WIRED |

### Gaps / Deferred

- Phase 18 InverseKinematicsSolver — intentionally not started
- Phase 19 visualizer toolbar button — intentionally not started
- Cross-session versioned calibration persistence — deferred per CONTEXT
- Live hardware human smoke listed above

### Plan Summaries

- `17-01-SUMMARY.md` — controller TDD
- `17-02-SUMMARY.md` — ROS service wiring
- `17-03-SUMMARY.md` — Studio chrome

---
*Phase: 17-reference-pose-calibration*
*Verified: 2026-07-28*
