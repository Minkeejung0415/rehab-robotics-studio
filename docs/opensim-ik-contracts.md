# OpenSim IK ROS Contracts (Phases 16–17)

**Status:** Phase 16 locked names/gate. Phase 17 implements calibration
capture/clear Trigger services, `/opensim/calibration_status` JSON, and the
hard joint_states publish gate on `opensim_bridge` (no InverseKinematicsSolver
— Phase 18).

**Machine-readable twin:**
`backend/rehab_robotics_bridge/opensim/ik_contracts.py`

This document locks the ROS names and the hard calibration gate for Phases
17–19. It supersedes the architecture draft that used bare `/joint_states`
(see D-16-03).

## Purpose and boundary

| In scope here | Out of this phase |
| --- | --- |
| Topic/service names and message types | OpenSim IK solver implementation (Phase 18) |
| Hard CALIBRATED gate for joint-state publish | Toolbar **Calibrate** / **Clear cal** (Phase 17 GUI plan) |
| Explicit retirement of custom `/opensim/joint_angle` | Visualizer start button |
| Phase 17 capture/clear + calibration_status | Live GUI JointState subscription |

Live triad visualization remains documented in
[`opensim-quaternion-live-link.md`](./opensim-quaternion-live-link.md) and is
**not** product IK.

## Paired IMU inputs

Defaults (launch-configurable):

| Role | Topic | Message | Frame default |
| --- | --- | --- | --- |
| Master | `/esp32/master/imu` | `sensor_msgs/Imu` | `femur_r_imu` |
| Slave | `/esp32/slave/imu` | `sensor_msgs/Imu` | `tibia_r_imu` |

Constants: `DEFAULT_MASTER_IMU_TOPIC`, `DEFAULT_SLAVE_IMU_TOPIC`,
`DEFAULT_MASTER_FRAME`, `DEFAULT_SLAVE_FRAME`.

## Hard calibration gate (D-16-04)

Calibration states:

- `UNCALIBRATED`
- `CAPTURING`
- `CALIBRATED`
- `FAILED`

**May-publish rule:** publish `sensor_msgs/JointState` on the product output
topic **only** when calibration state is `CALIBRATED` (and the future solver
marks the solution valid). Encoded as
`may_publish_joint_states(state) -> bool` — returns `True` only for
`CALIBRATED`.

No joint-state publication while `UNCALIBRATED`, `CAPTURING`, or `FAILED`.

## Locked product output (D-16-03)

| Item | Locked value |
| --- | --- |
| Topic | `/opensim/joint_states` |
| Type | `sensor_msgs/msg/JointState` (`sensor_msgs/JointState`) |
| Positions | Radians |
| Stamp | Synchronized observation / source measurement time (not wall publish time) |
| Stale policy | Do not republish stale solutions as fresh |

Constants: `JOINT_STATES_TOPIC`, `JOINT_STATES_MSG_TYPE`.

> **Supersedes** `.planning/research/ARCHITECTURE.md` draft `/joint_states`.
> Prefer `/opensim/joint_states` unless a later research rename is explicitly
> approved.

## Calibration services (Phase 17 — implemented on `opensim_bridge`)

| Service | Type | Purpose |
| --- | --- | --- |
| `/opensim/calibration/capture` | `std_srvs/Trigger` | Begin multi-sample standing / knees-extended capture |
| `/opensim/calibration/clear` | `std_srvs/Trigger` | Clear calibration → `UNCALIBRATED` |

Constants: `CALIBRATION_CAPTURE_SERVICE`, `CALIBRATION_CLEAR_SERVICE`.

Capture requires both master and slave IMU orientations live. Clear invalidates
active mounting offsets. JointState is never published until
`may_publish_joint_states` is true **and** an IK solution exists (Phase 17
leaves the solution absent).

## Status and diagnostics topics

| Topic | Role | Owner |
| --- | --- | --- |
| `/opensim/calibration_status` | JSON: `state`, `reason`, `known_pose`, `sample_count`, `window_s`, `calibration_id`, `has_offsets` | Phase 17 |
| `/opensim/status` | Embeds the same `calibration` object for Studio consumers | Phase 17 |
| `/opensim/ik_status` | Validity, residuals/age, calibration identity | Phase 18 |
| `/diagnostics` | Standard health summary | Phase 18 |

Constants: `IK_STATUS_TOPIC`, `CALIBRATION_STATUS_TOPIC`, `DIAGNOSTICS_TOPIC`.

## Retired non-product path

`/opensim/joint_angle` (`std_msgs/Float64` relative-quaternion degrees) is
**not** the product OpenSim IK output. It may exist only behind
`publish_joint_angle_enabled` default **OFF** for debug. Constant:
`PRODUCT_JOINT_ANGLE_TOPIC` (deprecated) — must not equal `JOINT_STATES_TOPIC`.

## Not in this document's remaining scope

- OpenSim IK solver process / package (Phase 18)
- Toolbar Calibrate / Clear cal chrome (Phase 17 GUI plan 03)
- Visualizer toolbar button (Phase 19)
- Studio subscription to `/opensim/joint_states` for live knee display (Phase 19)
