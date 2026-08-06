# Phase 15: OpenSim Quaternion Live Link - Context

**Gathered:** 2026-07-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Prove the live path from the existing master and slave ESP `sensor_msgs/Imu` quaternion topics through `opensim_bridge` into an OpenSim-hosted native visualizer. Display the two sensor orientations as mapped, labeled coordinate axes. Do not solve inverse kinematics, calibrate sensor mounting, rotate articulated bodies as a pose solution, automate the separate OpenSim desktop GUI, or add Studio 3D rendering.

</domain>

<decisions>
## Implementation Decisions

### Subscription Behavior
- Subscribe to `/esp32/master/imu` and `/esp32/slave/imu` as `sensor_msgs/Imu`.
- Process each sensor's newest valid orientation independently; timestamp pairing is not required for this live-link prototype.
- Configure the topic-to-OpenSim-frame mapping through launch parameters, defaulting master to `femur_r_imu` and slave to `tibia_r_imu`.
- Update whichever mapped sensor is available while reporting the other sensor as waiting or stale.

### OpenSim Demonstration
- `opensim_bridge` owns the OpenSim model and starts OpenSim's native Simbody visualizer in the bridge process.
- Display each incoming sensor orientation as a labeled coordinate triad associated with its configured model frame.
- Do not imply that the articulated model pose or joint angles have been solved; that requires later calibration and IK work.
- Select the model through a configurable `model_path` and report a clear error when the asset cannot be loaded.
- If the Python OpenSim runtime is unavailable, keep subscription and status behavior alive in a non-visual mode and report visualization as unavailable.

### Status and Verification
- Publish compact machine-readable JSON status in addition to logging state changes.
- Reject non-finite and near-zero quaternions; normalize otherwise valid non-unit input at the ROS-to-OpenSim boundary.
- Track master and slave freshness independently and mark a stream stale after a configurable timeout without terminating the node.
- Put the visualizer behind an adapter so deterministic tests can use a fake adapter without installed OpenSim or connected ESP devices.
- Cover identity and known 90-degree axis rotations, topic/mapping configuration, invalid input, staleness, and unavailable-runtime behavior.

### the agent's Discretion
- Exact status topic name and JSON field layout, provided both sensor states and visualization availability are explicit.
- Exact visualizer adapter API and coordinate-triad styling.
- Exact normalization tolerance and stale-timeout default.
- Whether the optional OpenSim import is isolated in the adapter module or a factory module.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Esp32BridgeNode` already publishes native `sensor_msgs/Imu` on `/esp32/{node_id}/imu` when `publish_native_topics` is enabled.
- `opensim_node.py` already provides the `opensim_bridge` console entry point and a launch integration seam.
- The launch file already supplies `master_segment=femur_r_imu` and `slave_segment=tibia_r_imu`.
- Existing backend tests favor pure helpers and controlled node/adaptor objects so hardware is not required.

### Established Patterns
- ROS node configuration uses declared parameters and standard launch arguments.
- Operator-relevant failures are logged rather than silently dropped.
- Optional external integrations should not prevent the core acquisition pipeline from starting.
- The worktree contains unrelated changes that must be preserved.

### Integration Points
- Replace the single filtered-JSON/UDP subscription in `backend/rehab_robotics_bridge/opensim_node.py`.
- Add a narrow OpenSim visualizer adapter under `backend/rehab_robotics_bridge/`.
- Update `backend/launch/rehab_robotics.launch.py` from UDP parameters to native IMU topic, mapping, model, and stale-timeout parameters.
- Add focused backend tests and a deterministic local publisher or fixture path.
- Update backend documentation with the ROS-to-OpenSim quaternion convention and launch instructions.

</code_context>

<specifics>
## Specific Ideas

The user wants the smallest useful result: open OpenSim and have it receive the quaternion values already provided by the ESP devices. The hosted native visualizer should make that connection visible without turning this phase into an IK milestone.

</specifics>

<deferred>
## Deferred Ideas

- Sensor-to-model calibration and heading correction.
- Timestamp synchronization and paired observation solving.
- Inverse kinematics and joint-angle publication.
- Jetson production packaging and native ARM64 OpenSim builds.
- Automating the separate OpenSim desktop GUI.
- Embedded Rehab Robotics Studio 3D visualization.

</deferred>
