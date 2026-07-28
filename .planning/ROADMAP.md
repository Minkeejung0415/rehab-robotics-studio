# Roadmap: Rehab Robotics Studio

## Overview

Milestone v1.5 replaces the incorrect custom relative-quaternion angle with official OpenSim orientation IK, adds operator calibration/mounting-offset capture from the Studio toolbar, and adds a toolbar control for the OpenSim 3D visualizer. Phase 15 (quaternion live link) remains the prerequisite acquisition/visualizer substrate.

## Milestones

- **v1.1 Acquisition Operations** - Phases 5-8 completed and archived.
- **v1.2 Block Deployment** - Parked without phases.
- **v1.3 Acquisition Integrity** - Unfinished prior scope preserved in repository history and existing Phase 9 artifacts.
- **v1.4 OpenSim Quaternion Live Link** - Phase 15 implemented (human visualizer/hardware smoke still noted).
- **v1.5 OpenSim IK + Calibration + Visualizer Control** - Phases 16-19.

## Phases

- [x] **Phase 15: OpenSim Quaternion Live Link** - Live ESP quaternions map into OpenSim frames/status (prerequisite).
- [x] **Phase 16: Retire Custom Angle + IK Contracts** - Remove fake IK angle path; define OpenSim IK input/output and pairing contracts.
- [x] **Phase 17: Reference-Pose Calibration** - Toolbar Calibrate / Clear cal; mounting offsets; hard gate until CALIBRATED.
- [x] **Phase 18: Real-Time OpenSim IK Outputs** - Official OpenSim orientation IK publishes joint states + status. (completed 2026-07-28)
- [ ] **Phase 19: Studio Controls + Live Angle Display** - Toolbar visualizer button; GUI displays calibrated OpenSim IK angles only.

## Phase Details

### Phase 16: Retire Custom Angle + IK Contracts

**Goal**: Stop treating custom relative-quat math as IK, and lock the ROS contracts the solver and GUI will use.
**Depends on**: Phase 15
**Requirements**: IK-00
**Plans:** 3/3 plans complete

Plans:
- [x] 16-01-PLAN.md — Demote backend custom `/opensim/joint_angle` product path (default OFF)
- [x] 16-02-PLAN.md — Retire GUI default `opensim_ik_live`/HealthPanel custom-angle presentation
- [x] 16-03-PLAN.md — Lock `/opensim/joint_states` + calibration-gate contracts (docs + constants)

**Success Criteria**:
1. `/opensim/joint_angle` custom publisher and GUI `opensim_ik_live` dependency on it are removed or clearly demoted as non-IK debug only (default graph no longer uses them as product IK).
2. Documented contracts exist for paired IMU inputs, calibration gate, `/opensim/joint_states` (or agreed name), and IK/calibration status topics/services.
3. Deterministic tests fail closed when attempting to present uncalibrated custom angle as the product knee readout.

### Phase 17: Reference-Pose Calibration

**Goal**: Operator can capture mounting offsets from a fixed standing / knees-extended pose via top-level Studio controls; IK remains gated until CALIBRATED.
**Depends on**: Phase 16
**Requirements**: IK-01, IK-02, IK-03, IK-04
**Plans:** 3/3 plans complete
**Status:** Complete

Plans:
- [x] 17-01-PLAN.md — Pure-Python CalibrationController + stable-window mounting offsets (TDD)
- [x] 17-02-PLAN.md — opensim_bridge capture/clear services, status publish, joint_states gate
- [x] 17-03-PLAN.md — Toolbar Calibrate/Clear cal + HealthPanel status via rosbridge

**Success Criteria**:
1. Toolbar **Calibrate** starts a bounded stable-window capture in the fixed known pose and transitions status through CAPTURING → CALIBRATED or FAILED with reason.
2. Toolbar/control **Clear cal** returns to UNCALIBRATED and invalidates active offsets.
3. No joint-angle publication occurs while UNCALIBRATED (Phase 17 leaves IK solution absent — gate seam ready for Phase 18).
4. Front Panel shows calibration state and last error/reason.

### Phase 18: Real-Time OpenSim IK Outputs

**Goal**: After calibration, OpenSim orientation IK solves and publishes joint coordinates the GUI can trust as OpenSim results.
**Depends on**: Phase 17
**Requirements**: IK-05, IK-06, IK-07
**Plans**: 3 plans

Plans:
- [x] 18-01-PLAN.md — OrientationIkSolver seam + Fake/Unavailable + mounting offsets (TDD)
- [x] 18-02-PLAN.md — OpenSim 4.5.2 Python orientation IK adapter + capability probe
- [x] 18-03-PLAN.md — opensim_bridge JointState + ik_status/diagnostics wiring

**Success Criteria**:
1. Calibrated master/slave orientations produce OpenSim-solved joint coordinates (not custom relative-quat degrees).
2. Coordinates publish on the agreed joint-state topic with source-aligned timestamps.
3. Status/diagnostics expose solution validity, residuals/age, and calibration identity.
4. Hardware-free deterministic fixtures prove a known pose → expected coordinate direction.

### Phase 19: Studio Controls + Live Angle Display

**Goal**: Operator runs the experiment from Studio chrome: open visualizer, calibrate, and see live OpenSim IK angles.
**Depends on**: Phase 18
**Requirements**: VIS-01, VIS-02, (consumes IK-06 display path)
**Success Criteria**:
1. Toolbar button starts/shows the OpenSim 3D visualizer when runtime allows; failure reason remains visible otherwise.
2. Default angle display subscribes to OpenSim IK joint states and updates only when CALIBRATED + valid solution.
3. End-to-end operator checklist for the wireless stack is documented and runnable.

## Progress

**Execution Order:** 16 → 17 → 18 → 19

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 15. OpenSim Quaternion Live Link | 3/3 | human_needed (prerequisite) | 2026-07-27 |
| 16. Retire Custom Angle + IK Contracts | 3/3 | Complete   | 2026-07-28 |
| 17. Reference-Pose Calibration | 3/3 | Complete   | 2026-07-28 |
| 18. Real-Time OpenSim IK Outputs | 3/3 | Complete   | 2026-07-28 |
| 19. Studio Controls + Live Angle Display | 1/7 | In Progress|  |

---
*Roadmap created: 2026-07-28 for milestone v1.5*
