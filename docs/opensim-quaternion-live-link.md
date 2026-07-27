# OpenSim Quaternion Live Link

This prototype forwards the newest valid orientation from each native ESP IMU
topic to a labeled sensor-coordinate triad in an OpenSim-owned native
visualizer. Master and slave update independently; they are not timestamp
paired.

The displayed triads are raw mapped sensor orientations. They are **not** a
calibrated model pose, inverse-kinematics result, joint angle, clinical
measurement, or biomechanical-validity claim. The bridge does not mutate model
coordinates.

## Build and launch

This repository includes PowerShell wrappers that use the installed
Ubuntu-22.04 WSL distribution. They avoid the apostrophe in the Windows
project path, build in `~/rehab_robotics_ws`, install the compatible OpenSim
4.5.2 Python API, and generate a minimal demo model.

Run setup once from the repository root while ordinary internet access is
available:

```powershell
.\scripts\setup_opensim_live_link.ps1
```

Run the deterministic hardware-free check:

```powershell
.\scripts\run_opensim_live_link.ps1 -Test
```

Stop it with `Ctrl+C`, connect the computer to the STEP_ESP32 network, and run
the same subscriber against the real ESP topics:

```powershell
.\scripts\run_opensim_live_link.ps1
```

Use a subject model instead of the generated demo model:

```powershell
.\scripts\run_opensim_live_link.ps1 -ModelPath C:\models\subject.osim
```

Opening the native 3D window requires a Linux OpenSim/Simbody installation
with `simbody-visualizer` discoverable on WSL's `PATH`. The installed official
OpenSim 4.5.2 Conda API performs model/quaternion calculations but does not
ship that executable. In its absence, subscriptions, validation, independent
live counters, staleness, and status publication continue normally and status
reports `visualizer_initialization_failed`.

The locked defaults are:

| Launch argument | Default |
| --- | --- |
| `master_imu_topic` | `/esp32/master/imu` |
| `slave_imu_topic` | `/esp32/slave/imu` |
| `master_frame` | `femur_r_imu` |
| `slave_frame` | `tibia_r_imu` |
| `model_path` | empty |
| `stale_timeout_s` | `1.0` |
| `status_topic` | `/opensim/status` |
| `enable_opensim_bridge` | `true` |
| `enable_opensim_test_publisher` | `false` |

Override topics and exact OpenSim frame names without changing source:

```bash
ros2 launch rehab_robotics_bridge rehab_robotics.launch.py \
  model_path:=/data/subject.osim \
  master_imu_topic:=/lab/right_thigh/imu \
  slave_imu_topic:=/lab/right_shank/imu \
  master_frame:=femur_r_imu \
  slave_frame:=tibia_r_imu \
  stale_timeout_s:=2.0
```

The frame names must resolve exactly in the selected `.osim` model. An empty or
missing model path leaves subscriptions and status active in non-visual mode.

## Hardware-free deterministic check

The synthetic publisher is opt-in so its messages cannot be mistaken for live
hardware by default. The recommended command is:

```powershell
.\scripts\run_opensim_live_link.ps1 -Test
```

For direct ROS usage inside a configured WSL shell, use the dedicated launch:

```bash
ros2 launch rehab_robotics_bridge opensim_live_link.launch.py \
  model_path:=/absolute/path/to/model.osim \
  enable_test_publisher:=true
```

Each tick emits:

- master frame `opensim_test_master`: identity `(x,y,z,w)=(0,0,0,1)`
- slave frame `opensim_test_slave`: positive 90 degrees about Z,
  `(x,y,z,w)=(0,0,sqrt(0.5),sqrt(0.5))`

With a compatible model, OpenSim Python bindings, and a complete native
visualizer installation whose `simbody-visualizer` executable is on `PATH`,
the master triad remains at identity and the slave triad displays the
corresponding positive 90-degree active Z rotation.

## Quaternion convention

`sensor_msgs/Imu.orientation` enters the bridge in ROS `(x, y, z, w)` order.
The single ROS-to-OpenSim boundary rejects non-finite and near-zero values,
normalizes every otherwise valid quaternion, then represents it as
scalar-first `(w, x, y, z)` and an equivalent right-handed active 3x3 rotation
matrix for OpenSim/SimTK. No mounting calibration, heading correction, or IK
transform is applied.

## Inspect status and failures

Inspect the compact JSON status:

```bash
ros2 topic echo /opensim/status --field data
```

The schema identifier is `rehab.opensim_live_link.1`. Its `visualization`
object reports `available`, `state`, `reason`, and `model_path`. The
`sensors.master` and `sensors.slave` objects independently report `topic`,
`frame`, `state`, `age_s`, `updates`, and `last_error`.

Expected sensor states:

- `waiting`: no valid message has arrived for that role.
- `live`: the newest valid orientation was accepted.
- `invalid`: the quaternion was non-finite or near zero; it was not forwarded.
- `mapping_error`: the adapter rejected the mapped frame/update.
- `stale`: time since the last valid update exceeded `stale_timeout_s`.

An unavailable OpenSim runtime, missing model, model-load failure, unknown
frame, or unsupported dynamic-decoration API is visible in `visualization`
state/reason and transition logs. Missing runtime/model support does not stop
subscriptions: valid messages still advance each sensor's independent live
counter and freshness in non-visual mode.

If the bindings are importable but the native executable cannot start, the
visualization reason is `visualizer_initialization_failed`. The bridge then
continues in subscription/status-only mode: sensor validation, freshness, live
counters, status publication, and transition logs remain active, but no native
window is shown.

Stop the deterministic publisher before reconnecting ESP hardware unless you
have intentionally assigned separate test topics.
