# OpenSim IK ROS Contracts (Phases 16–18)

**Status:** Phase 16 locked names/gate. Phase 17 implements calibration
capture/clear Trigger services, `/opensim/calibration_status` JSON, and the
hard joint_states publish gate. Phase 18 wires Orientation IK into
`opensim_bridge`: stamped `/opensim/joint_states`, `/opensim/ik_status`, and
`/diagnostics` heartbeat.

**Machine-readable twin:**
`backend/rehab_robotics_bridge/opensim/ik_contracts.py`

This document locks the ROS names and the hard calibration gate for Phases
17–19. It supersedes the architecture draft that used bare `/joint_states`
(see D-16-03).

## Purpose and boundary

| In scope here | Out of this phase |
| --- | --- |
| Topic/service names and message types | Studio JointState subscription (Phase 19) |
| Hard CALIBRATED + solution_valid gate | Toolbar visualizer start button (Phase 19) |
| Orientation IK product path via `OrientationIkSolver` | Typed `IkStatus.msg` (deferred) |
| Explicit retirement of custom `/opensim/joint_angle` as product | Clinical / external-reference validation |

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

## Hard calibration gate (D-16-04 / D-18-05)

Calibration states:

- `UNCALIBRATED`
- `CAPTURING`
- `CALIBRATED`
- `FAILED`

**May-publish rule:** publish `sensor_msgs/JointState` on the product output
topic **only** when calibration state is `CALIBRATED` **and** the Orientation
IK solver reports `solution_valid=True` with a usable `source_timestamp_ns`.
Encoded as `may_publish_joint_states(state) -> bool` for the calibration half;
the node also requires `solution_valid` and source stamp integrity.

No joint-state publication while `UNCALIBRATED`, `CAPTURING`, or `FAILED`, or
when the solver is invalid / Unavailable.

## Locked product output (D-16-03 / D-18-04)

| Item | Locked value |
| --- | --- |
| Topic | `/opensim/joint_states` |
| Type | `sensor_msgs/msg/JointState` (`sensor_msgs/JointState`) |
| Positions | Radians |
| Default joint name | `knee_angle_r` (`ik_joint_names` / `ik_coordinate_paths`) |
| Stamp | `min(master, slave)` source observation time from IMU headers |
| Stale policy | Do not republish stale solutions with a fresh wall-clock stamp |
| Missing stamp | Fail closed — `missing_source_timestamp`; no fabricated wall stamp |

Constants: `JOINT_STATES_TOPIC`, `JOINT_STATES_MSG_TYPE`.

> **Supersedes** `.planning/research/ARCHITECTURE.md` draft `/joint_states`.
> Prefer `/opensim/joint_states` unless a later research rename is explicitly
> approved.

Product angles come **only** from `OrientationIkSolver` (OpenSim Python adapter
or injected Fake in tests). `relative_orientation_angle_deg` / `/opensim/joint_angle`
remain debug-only (`publish_joint_angle_enabled` default OFF) and must **not**
populate `/opensim/joint_states`.

## Calibration services (Phase 17)

| Service | Type | Purpose |
| --- | --- | --- |
| `/opensim/calibration/capture` | `std_srvs/Trigger` | Begin multi-sample standing / knees-extended capture |
| `/opensim/calibration/clear` | `std_srvs/Trigger` | Clear calibration → `UNCALIBRATED`; resets IK assemble state |

Constants: `CALIBRATION_CAPTURE_SERVICE`, `CALIBRATION_CLEAR_SERVICE`.

## Status and diagnostics topics

| Topic | Role | Owner |
| --- | --- | --- |
| `/opensim/calibration_status` | JSON: `state`, `reason`, `known_pose`, `sample_count`, `window_s`, `calibration_id`, `has_offsets` | Phase 17 |
| `/opensim/status` | Embeds `calibration` + `ik` objects for Studio consumers | Phase 17–18 |
| `/opensim/ik_status` | String JSON schema `rehab.opensim_ik_status.1` | Phase 18 |
| `/diagnostics` | String JSON heartbeat (`rehab.opensim_diagnostics.1`) — DiagnosticArray deferred | Phase 18 |

Constants: `IK_STATUS_TOPIC`, `CALIBRATION_STATUS_TOPIC`, `DIAGNOSTICS_TOPIC`.

### `/opensim/ik_status` schema (`rehab.opensim_ik_status.1`)

Minimum keys:

| Key | Type | Notes |
| --- | --- | --- |
| `schema` | string | `rehab.opensim_ik_status.1` |
| `solution_valid` | bool | Required for JointState publish |
| `reason` | string | e.g. `ok`, `missing_source_timestamp`, `opensim_ik_api_unavailable` |
| `calibration_id` | string \| null | Active artifact id |
| `orientation_residual_rms` | number \| null | When OpenSim exposes orientation error |
| `orientation_residual_max` | number \| null | |
| `input_age_s` | number \| null | Freshest paired sensor age |
| `solve_duration_s` | number \| null | |
| `backend` | string | `OpenSimOrientationIkSolver` / `unavailable` / `fake` |
| `joint_names` | string[] | |
| `source_timestamp_ns` | int \| null | Paired observation stamp |

## Retired non-product path

`/opensim/joint_angle` (`std_msgs/Float64` relative-quaternion degrees) is
**not** the product OpenSim IK output. It may exist only behind
`publish_joint_angle_enabled` default **OFF** for debug. Constant:
`PRODUCT_JOINT_ANGLE_TOPIC` (deprecated) — must not equal `JOINT_STATES_TOPIC`.

## Not in this document's remaining scope

- Studio subscription to `/opensim/joint_states` for live knee display (Phase 19)
- Visualizer toolbar button (Phase 19)
- Typed `IkStatus.msg` / `diagnostic_msgs/DiagnosticArray` migration
- Dedicated C++ `rehab_robotics_opensim` package (research preferred; deferred)
