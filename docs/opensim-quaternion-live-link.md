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

From a ROS 2 workspace containing this package:

```bash
colcon build --packages-select rehab_robotics_bridge
source install/setup.bash
ros2 launch rehab_robotics_bridge rehab_robotics.launch.py \
  model_path:=/absolute/path/to/model.osim
```

On PowerShell, use the ROS-generated PowerShell setup script instead:

```powershell
colcon build --packages-select rehab_robotics_bridge
.\install\setup.ps1
ros2 launch rehab_robotics_bridge rehab_robotics.launch.py model_path:=C:\models\subject.osim
```

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
hardware by default. Start it through the launch file:

```bash
ros2 launch rehab_robotics_bridge rehab_robotics.launch.py \
  model_path:=/absolute/path/to/model.osim \
  enable_opensim_test_publisher:=true
```

Or run it separately against an already-running bridge:

```bash
ros2 run rehab_robotics_bridge opensim_test_publisher \
  --ros-args \
  -p master_imu_topic:=/esp32/master/imu \
  -p slave_imu_topic:=/esp32/slave/imu \
  -p publish_rate_hz:=1.0
```

Each tick emits:

- master frame `opensim_test_master`: identity `(x,y,z,w)=(0,0,0,1)`
- slave frame `opensim_test_slave`: positive 90 degrees about Z,
  `(x,y,z,w)=(0,0,sqrt(0.5),sqrt(0.5))`

With a compatible model and OpenSim Python runtime, the master triad remains at
identity and the slave triad displays the corresponding positive 90-degree
active Z rotation.

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

Stop the deterministic publisher before reconnecting ESP hardware unless you
have intentionally assigned separate test topics.
