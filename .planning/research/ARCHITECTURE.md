# Architecture Research

**Domain:** Real-time OpenSim/OpenSense-compatible inverse kinematics from paired ROS 2 IMU orientations
**Researched:** 2026-07-27
**Confidence:** HIGH for ROS 2 integration boundaries; MEDIUM for final OpenSim Python binding details until pinned against the target OpenSim build

## Recommendation

Replace the UDP forwarder with one dedicated `opensim_bridge` ROS 2 process. Run the OpenSim API in that process, but behind a small `IkSolverAdapter` interface and on a single solver-owner worker thread. ROS subscription callbacks should only validate, synchronize, and enqueue the newest paired orientation sample; they must never call OpenSim directly.

This is the right initial boundary because `launch_ros.actions.Node` already gives OpenSim an operating-system process separate from the ESP bridges, filters, recorder, rosbridge, and GUI. A native OpenSim exception or crash therefore cannot take down acquisition. A second subprocess or network daemon would add serialization, supervision, deployment, and calibration-consistency problems without providing useful isolation beyond the process boundary that already exists. Keep the adapter interface so a subprocess implementation can be introduced later if OpenSim binary/ABI packaging on the Jetson requires a separate environment.

Do not use the existing UDP packet path. It carries only one filtered JSON stream, has no paired timestamp contract, cannot return solver state, and makes calibration/model ownership ambiguous.

## Standard Architecture

### System Overview

```text
 ESP32 master process              ESP32 slave process
 /esp32/master/imu                 /esp32/slave/imu
 sensor_msgs/Imu                   sensor_msgs/Imu
          |                                 |
          +------------ ROS 2 DDS ----------+
                            |
                 opensim_bridge process
  +-----------------------------------------------------------+
  | input validation -> approximate-time pairing -> latest-only|
  | queue                                                     |
  |                             |                             |
  | calibration controller     solver-owner worker thread     |
  |                             |                             |
  | model/config asset loader -> IkSolverAdapter -> OpenSim API|
  |                             |                             |
  | output/health publisher <---+                             |
  +-----------------------------------------------------------+
       |                  |                 |             |
 /joint_states     /opensim/ik_status  /diagnostics  /opensim/model_info
 sensor_msgs/      typed quality       standard       latched metadata
 JointState        message             diagnostics
       |                  |                 |             |
       +-------- rosbridge / rosbag2 / future viewer ------+
```

The existing `/esp/raw/*` and `/esp/filtered/*` JSON topics remain useful for the current GUI and simple filtering/recording, but they should not be the authoritative IK input. `sensor_msgs/Imu` already provides a stamped, typed quaternion and frame ID, avoids reparsing JSON, and is the canonical interoperability boundary.

### Component Responsibilities

| Component | New or modified | Responsibility |
|-----------|-----------------|----------------|
| `Esp32BridgeNode` | Modified narrowly | Publish trustworthy `sensor_msgs/Imu.header.stamp`, monotonically increasing sequence metadata where available, normalized quaternions, and stable sensor frame IDs. It remains the acquisition and unit-conversion owner. |
| Pair synchronizer | New inside `opensim_bridge` | Subscribe to `/esp32/master/imu` and `/esp32/slave/imu` with identical sensor-data QoS; form pairs by header time; reject stale, non-finite, non-unit, duplicate, or excessive-skew inputs; expose pair/drop/skew counters. |
| Calibration controller | New | Capture a stationary reference-pose window, validate it, compute sensor-to-model rotations under one documented quaternion convention, persist a calibration artifact, and gate solving until a calibration matching the model and mapping is active. |
| Model asset loader | New | Resolve installed `.osim` and YAML assets, validate mapped frame/coordinate names, hash the model and configuration, initialize a fresh OpenSim model/state, and publish immutable model metadata. |
| `IkSolverAdapter` | New | Define the narrow API `configure`, `calibrate`, `assemble`, `track`, `reset`, and `close`. Production implementation wraps OpenSim; fake implementation supports deterministic tests. |
| OpenSim solver worker | New | Own all OpenSim/Simbody objects on one thread, seed with `assemble()`, use `track()` for subsequent nearby samples, collect coordinate values and orientation errors, and convert failures to status events. |
| Output publisher | New | Publish standard joint states in radians, typed solver-quality/status output, calibration events, model metadata, and standard diagnostics. |
| Existing line recorder | Unchanged for IK | Continue recording raw JSON if needed. Do not extend it into an ad hoc multi-type IK recorder. |
| `rosbag2` recorder | New launch integration | Optionally record typed IMU inputs, joint states, IK status, diagnostics, calibration events, and model metadata in one replayable time base. |
| Launch file | Modified | Pass input topics, model/config/calibration paths, timing limits, and enable/record flags; remove UDP parameters; start the bridge as its own process and optionally start rosbag2. |

## Process and Runtime Boundaries

### Recommended Boundary

```text
ROS executor thread(s)
  - deserialize messages
  - validate headers/quaternions
  - synchronize master/slave
  - update counters
  - enqueue newest accepted pair
                 |
                 | bounded queue, capacity 1
                 v
OpenSim worker thread (single owner)
  - calibration math requiring model pose
  - model/state/solver mutation
  - assemble/track
  - produce immutable result
                 |
                 v
ROS publisher timer/callback
  - publish JointState/status/diagnostics
```

OpenSim and Simbody objects must not cross threads. The worker owns the model, state, orientation reference, and solver for their entire lifetimes. A bounded capacity-one queue intentionally drops superseded pairs when solving falls behind; rehabilitation monitoring needs current pose, not an ever-growing latency backlog. Drop counts and solver latency must be reported.

Use an ordinary `rclpy.Node` with an explicit domain state machine rather than introducing ROS managed lifecycle in this milestone. Managed lifecycle would complicate calibration subscriptions and rosbridge controls while not eliminating the need for calibration/solver states. The explicit states should be:

```text
STARTING -> UNCALIBRATED -> CALIBRATING -> READY -> TRACKING
                ^              |             |         |
                +--------------+-------------+---------+
                         clear/reset/reconfigure

Any state -> DEGRADED (transient input/solve failures)
Any state -> ERROR    (model/config/native initialization failure)
```

Model/config parameter changes are not hot-applied. They trigger a controlled stop, worker teardown, asset validation, fresh solver construction, and calibration revalidation. A model hash or sensor-frame mapping change invalidates the active calibration.

### Adapter Contract

The adapter is an in-process code boundary, not a network protocol:

```python
class IkSolverAdapter(Protocol):
    def configure(self, model_path, sensor_frames, coordinates, weights): ...
    def set_calibration(self, sensor_to_model_rotations): ...
    def assemble(self, observation_time, orientations): ...
    def track(self, observation_time, orientations): ...
    def reset(self): ...
    def close(self): ...
```

The production adapter should use an OpenSim orientation reference designed for streaming, preferably `BufferedOrientationsReference` when it is usable from the pinned Python bindings, with `InverseKinematicsSolver`. The official API describes this reference as a live-data queue for `InverseKinematicsSolver`; `track()` is specifically optimized when the model and goals are unchanged and the prior state is near the next solution. If the pinned Python wheel does not expose the buffered API reliably, implement the same adapter in a small C++ ROS package before inventing a socket daemon. This binding check is a phase-specific research flag.

## Topic, Service, and Asset Contracts

### Inputs

| Name | Type | Owner | Contract |
|------|------|-------|----------|
| `/esp32/master/imu` | `sensor_msgs/msg/Imu` | existing master bridge | Orientation in ROS message order `x,y,z,w`; finite, normalized; stamped on receipt until hardware acquisition time exists; stable `frame_id=esp32_master`. |
| `/esp32/slave/imu` | `sensor_msgs/msg/Imu` | existing slave bridge | Same contract, `frame_id=esp32_slave`. |
| `/esp/status/master`, `/esp/status/slave`, `/esp/status/pair` | existing String JSON | existing bridge | Optional upstream-health context only. Loss of IMU data is determined from the typed input timers, not inferred solely from these JSON topics. |

`message_filters.ApproximateTimeSynchronizer` is appropriate because each bridge stamps independently. Make queue size and slop parameters; start local validation around queue `10` and slop `0.010 s`, then derive production values from measured skew. ROS documentation warns that synchronizer subscribers must use matching QoS and that arrival-time/headerless synchronization is unpredictable. Do not set `allow_headerless` or synchronize the String JSON streams.

Current stamps are host receipt times, not device acquisition times. This supports bounded host-side pairing but is not proof of hardware simultaneity. If validation shows unacceptable skew, the prerequisite fix is to propagate a shared hardware sequence/acquisition timestamp from firmware or the master/slave protocol into both `Imu` headers. Do not hide that limitation with a larger synchronizer slop.

### Controls

| Name | Type | Behavior |
|------|------|----------|
| `/opensim/calibration/capture` | `std_srvs/srv/Trigger` | Begin a bounded reference-pose capture from accepted pairs. Return “accepted” immediately; completion/failure is reported on calibration status. Reject if model/mapping is invalid or streams are stale. |
| `/opensim/calibration/clear` | `std_srvs/srv/Trigger` | Stop tracking, clear the active calibration in memory, and return to `UNCALIBRATED`; preserve prior artifact as history unless explicitly replaced. |
| `/opensim/solver/reset` | `std_srvs/srv/Trigger` | Rebuild solver state from the same model and calibration, then require a fresh `assemble()` before `track()`. |

Calibration capture should average a configurable window of synchronized quaternion pairs (for example 1–2 seconds), reject windows with excessive angular velocity/orientation dispersion or pair skew, and record the exact source interval. A calibration operation is transactional: compute and validate a candidate, write it to a temporary artifact, atomically replace the active artifact, then switch the worker. A failed capture leaves the prior valid calibration active.

### Outputs

| Name | Type | QoS / content |
|------|------|---------------|
| `/joint_states` | `sensor_msgs/msg/JointState` | Best-effort or reliable depth 5 after measurement; stable names matching selected OpenSim coordinate names; positions always radians; velocities/efforts empty unless genuinely computed. Stamp with the paired observation time, not publication time. |
| `/opensim/ik_status` | new `rehab_robotics_interfaces/msg/IkStatus` | Reliable depth 10. State, source stamps, pair skew, input age, solve duration, sequence, drop counts, orientation RMS/max error, failure code/message, calibration ID, model hash, and `solution_valid`. |
| `/opensim/calibration_status` | new typed message or compact versioned JSON | Reliable + transient local. State, calibration ID, model/config hashes, capture interval, sample count, validation metrics, and failure reason. |
| `/opensim/model_info` | new typed message or versioned JSON | Reliable + transient local. Model hash/name, coordinate names/order/units, sensor-to-model frame mapping, calibration ID, and configuration schema version. |
| `/diagnostics` | `diagnostic_msgs/msg/DiagnosticArray` | Standard 1 Hz summary with OK/WARN/ERROR entries for input sync, calibration, model, solver, and output. Include numeric values as `KeyValue`s. |

Prefer typed interfaces for high-rate or correctness-critical data. A versioned JSON `model_info` is acceptable because it is low-rate descriptive metadata and easy for the existing rosbridge client. Joint states and diagnostics must remain standard messages.

Never publish the last good angles with a new timestamp after an input or solver failure. Either publish no `JointState` or retain its original timestamp while `IkStatus.solution_valid=false`; the first choice is clearer. Consumers detect staleness from status and timestamp.

### Model and Calibration Assets

Recommended installed/read-only assets:

```text
backend/
├── config/
│   └── opensim_ik.yaml             # model, mappings, weights, limits, timing
├── models/
│   └── lower_limb.osim             # versioned source model
└── rehab_robotics_bridge/
    ├── opensim_node.py             # ROS orchestration only
    └── opensim/
        ├── contracts.py             # immutable observations/results
        ├── synchronizer.py          # validation/pairing policy
        ├── calibration.py           # frame math and artifact schema
        ├── assets.py                # resolution, hashes, name validation
        ├── adapter.py               # protocol + fake
        └── opensim_adapter.py       # production native API wrapper

results/
└── calibration/
    └── <calibration-id>.yaml        # writable, provenance-bearing artifact
```

The YAML config should contain:

- package-relative model asset path resolved through the ament package share directory;
- sensor role/topic/frame ID to OpenSim model frame mapping;
- global sensor-world to OpenSim-ground transform;
- reference-pose coordinate values and locked coordinates;
- orientation weights and output coordinate allowlist/order;
- quaternion convention (`ROS xyzw`, active rotation, sensor-to-ground meaning) and schema version;
- pair slop, stale timeout, calibration window/dispersion limits, solve deadline, and diagnostic thresholds.

Calibration artifacts must include model SHA-256, config hash, sensor role and frame IDs, sensor-to-model rotations, reference pose, source time interval, validation metrics, software/OpenSim versions, and creation time. Never mutate the checked-in `.osim` during a live calibration. A calibrated `.osim` may be exported as a derived artifact for offline OpenSense comparison, but the runtime source of truth is the versioned model plus calibration artifact.

OpenSense's IMU Placer conceptually finds IMU frame orientations relative to model body segments and does not use IMU position. Mirror that contract. Define and test one equation explicitly; for example, if `R_GS` maps sensor coordinates into ground and `R_GM` is the expected model sensor frame in the reference pose, solve `R_SM = inverse(R_GS) * R_GM` and apply `R_GM_measured = R_GS * R_SM`. Confirm multiplication direction with identity and 90-degree fixtures before hardware testing.

## Data Flow

### Live Solve Flow

```text
1. ESP bridge receives frame and publishes stamped Imu.
2. Synchronizer forms master/slave pair within max_pair_skew.
3. Validator checks age, order, frame IDs, finiteness, norm, and sign continuity.
4. Calibrator applies global and per-sensor frame transforms.
5. Latest accepted observation replaces any unsolved observation in queue.
6. Worker calls assemble() for first valid sample after init/reset/calibration.
7. Worker calls track() for later samples, seeded by the preceding solution.
8. Adapter returns selected coordinate values and residual/error metrics.
9. ROS side publishes JointState with source time, IkStatus, and diagnostics counters.
10. rosbridge and rosbag2 consume the same published contracts.
```

Quaternion sign (`q` versus `-q`) represents the same rotation. Enforce temporal sign continuity before averaging or interpolation; otherwise an apparently stationary calibration window can cancel numerically.

### Calibration Flow

```text
Operator Trigger
  -> verify model + fresh pair stream
  -> CALIBRATING, collect accepted stationary window
  -> quaternion mean + dispersion/skew checks
  -> compute candidate sensor-to-model rotations
  -> initialize fresh solver and solve known pose
  -> validate coordinate/orientation residual thresholds
  -> persist artifact atomically
  -> activate candidate and publish calibration event
  -> READY/TRACKING
```

Calibration and solving must not mutate the same OpenSim state concurrently. Build and validate a candidate off the live state on the solver-owner thread, then swap only after success.

### Failure and Recovery Flow

| Failure | Boundary behavior | Recovery |
|---------|-------------------|----------|
| Invalid quaternion / wrong frame | Drop before queue; increment reason counter | Continue when valid pairs resume |
| Missing or stale sensor | Stop publishing solutions; diagnostics ERROR after timeout | Reassemble on first fresh pair |
| Pair skew above limit | Do not solve unmatched samples; diagnostics WARN/ERROR by rate | Investigate clocks/hardware sequence; do not simply increase slop |
| Solver misses deadline | Drop superseded queued pair; WARN with latency/drop counts | Continue latest-only; reset after configured consecutive failures |
| `track()` convergence failure | Mark invalid, attempt one controlled re-`assemble()` | Resume only on successful assembly |
| Model/config/calibration mismatch | Refuse tracking and enter ERROR or UNCALIBRATED | Correct asset or capture matching calibration |
| Native OpenSim process crash | Other ROS nodes remain alive; topic staleness exposes failure | Launch may respawn with delay; repeated init failure remains visible in logs/supervision |
| Recording failure | IK continues; recorder reports its own diagnostic | Operator resolves storage; never block solver |

## Recording and Replay

Keep three recording meanings distinct:

1. ESP32 SD recording is hardware acquisition controlled by the existing `/esp/recording/set`.
2. The existing `esp_record` node is a simple raw JSON audit trail.
3. IK experiment recording should use `rosbag2` so typed inputs and derived outputs share replayable ROS timestamps.

Add an optional launch action or separate launch file that records an explicit allowlist:

```text
/esp32/master/imu
/esp32/slave/imu
/esp/status/master
/esp/status/slave
/esp/status/pair
/joint_states
/opensim/ik_status
/opensim/calibration_status
/opensim/model_info
/diagnostics
```

Record model/calibration IDs in every bag through transient-local metadata topics and copy the referenced immutable config/model/calibration files into the session manifest. A bag alone is insufficient if model assets can later change. Deterministic replay should support `/clock`/simulation time or inject recorded messages into the adapter harness; timeout logic must use the appropriate ROS/source time for data and monotonic wall time for execution deadlines.

## Future Visualization Contract

Do not add OpenSim GUI embedding, mesh streaming, or a fake URDF/TF tree now. Preserve a clean future seam:

- stable OpenSim coordinate names and radians in `/joint_states`;
- immutable model hash and coordinate ordering in `/opensim/model_info`;
- model-space frame mapping and calibration ID in metadata;
- source timestamps and validity in `/opensim/ik_status`;
- optionally, in the visualization milestone, a separate `opensim_visualization_adapter` can load the same `.osim`, apply joint coordinates, and publish mesh transforms or a web-viewer-specific state.

`robot_state_publisher` cannot directly interpret `.osim`; translating OpenSim geometry/joints to URDF/TF is a distinct adapter and should not contaminate the IK node. The IK output contract should describe model coordinates, not rendering transforms.

## Exact File and Package Changes

### Modify

| File/component | Change |
|----------------|--------|
| `backend/rehab_robotics_bridge/opensim_node.py` | Replace UDP forwarding with orchestration, subscriptions, control services, state machine, bounded worker interface, and publishers. Keep native OpenSim calls out of callbacks. |
| `backend/rehab_robotics_bridge/esp32_bridge_node.py` | Tighten timestamp/sequence/orientation validity contract; preserve acquisition metadata where available. Do not add calibration or OpenSim frame transforms here. |
| `backend/launch/rehab_robotics.launch.py` | Remove `opensim_udp_host/port`; add model/config/calibration/input/timing parameters, bridge enable flag, and optional rosbag2 integration. |
| `backend/setup.py` | Install model/config assets and new Python modules; retain `opensim_bridge` entry point. |
| `backend/package.xml` | Add `message_filters`, `diagnostic_msgs`, and any generated interface/runtime dependencies; document OpenSim as a system/native dependency rather than assuming pip alone. |
| `rehab_robotics_interfaces/CMakeLists.txt` and `package.xml` | Generate typed IK/calibration status interfaces if selected. |

### Add

| File/component | Purpose |
|----------------|---------|
| `backend/rehab_robotics_bridge/opensim/contracts.py` | Typed immutable observation/result/error records. |
| `backend/rehab_robotics_bridge/opensim/synchronizer.py` | Input validation and pairing policy wrapper. |
| `backend/rehab_robotics_bridge/opensim/calibration.py` | Quaternion convention, reference capture, transforms, artifact schema. |
| `backend/rehab_robotics_bridge/opensim/assets.py` | Ament path resolution, hashing, and model/config name validation. |
| `backend/rehab_robotics_bridge/opensim/adapter.py` | Solver protocol and fake implementation. |
| `backend/rehab_robotics_bridge/opensim/opensim_adapter.py` | Production OpenSim implementation. |
| `backend/config/opensim_ik.yaml` | Runtime mapping and thresholds. |
| `backend/models/<model>.osim` | Versioned model containing named IMU frames. |
| `rehab_robotics_interfaces/msg/IkStatus.msg` | High-rate typed quality/validity contract. |
| tests/fixtures for known poses and quaternion conventions | Deterministic identity, 90-degree, stale/skew, calibration, and known-pose IK cases. |

Do not modify the React client until the ROS contracts and rosbridge serialization are stable. Its eventual change is to call calibration services and subscribe to status/joint states.

## Dependency-Aware Build Order

1. **Freeze conventions and fixtures.**
   - Define ROS quaternion meaning/order, OpenSim ground axes, frame names, units, timestamp semantics, reference pose, and expected known-pose coordinates.
   - Add identity and 90-degree transform fixtures before solver code.

2. **Repair the input time contract.**
   - Verify monotonic `Imu.header.stamp`, stable `frame_id`, quaternion normalization, and actual master/slave skew.
   - Decide from evidence whether host receipt stamps suffice or shared hardware sequence propagation is prerequisite.

3. **Create assets and validate names offline.**
   - Add the `.osim`, named IMU frames, YAML mapping, coordinate allowlist, hashes, and package installation.
   - Fail fast on missing/duplicate frames or coordinates.

4. **Build pure synchronization and calibration modules.**
   - Test invalid/stale/skew handling, sign continuity, stationary-window acceptance, transform direction, persistence, and model-hash invalidation without OpenSim.

5. **Define ROS output/control interfaces.**
   - Add `IkStatus`, calibration status/metadata choice, diagnostics fields, Trigger services, and rosbridge-friendly schemas before GUI work.

6. **Implement and verify the adapter offline.**
   - Fake adapter first; then pinned OpenSim adapter using streaming orientations, `assemble()`, `track()`, coordinate extraction, and residual metrics.
   - Compare deterministic fixture output with the offline OpenSense/IMU IK tool using the same model and calibration.

7. **Integrate the dedicated ROS process.**
   - Add approximate-time subscriptions, bounded queue, single-owner worker, state machine, outputs, reset/recovery, and execution-deadline diagnostics.

8. **Integrate launch and recording.**
   - Parameterize assets/topics/thresholds, remove UDP, install dependencies/assets, add optional rosbag2 allowlist, and test replay.

9. **Add rosbridge/UI controls last.**
   - Expose calibration state, model identity, solution validity, and joint angles only after message contracts pass ROS-level tests.

10. **Hardware validation and tuning.**
    - Measure skew, solve latency, drop rate, reference-pose residual, and known-motion error; tune thresholds from captured evidence rather than broadening them until warnings disappear.

This order prevents expensive solver debugging from masking timestamp, convention, frame-name, or calibration errors.

## Architectural Patterns

### Functional Core, Imperative Shell

Keep quaternion normalization, transform composition, calibration statistics, artifact validation, and result conversion as pure functions. Let the ROS node own subscriptions/services and let the adapter own native state. This makes most correctness tests independent of ROS and OpenSim installation.

### Latest-Value Real-Time Processing

Use bounded overwrite semantics between synchronization and solving. This guarantees memory and latency bounds at the cost of intentional sample loss under overload. Report every overwrite.

### Provenance-Bound Calibration

Treat calibration as a versioned artifact bound to a model hash, config hash, sensor mapping, and convention version. This prevents a plausible-looking but invalid calibration from silently surviving a model or sensor-layout change.

### Assemble Then Track

Use a full assembly on initialization, calibration activation, reset, discontinuity, or recovery. Use tracking only for temporally adjacent samples. The official OpenSim API identifies `track()` as efficient when model/goals are unchanged and the initial state is close to the new solution.

## Anti-Patterns

### Solving in ROS Subscription Callbacks

**Why it fails:** Native solve time blocks DDS handling, queues stale samples, and makes OpenSim state vulnerable to concurrent callbacks.
**Instead:** Validate/enqueue in callbacks and solve on one owning thread.

### Treating Two Latest Messages as a Pair

**Why it fails:** A reconnect or rate difference can combine orientations from different physical instants.
**Instead:** Pair by stamped time with bounded skew, age, queue, and explicit drop metrics.

### Applying a “Calibration Quaternion” Without a Frame Equation

**Why it fails:** ROS/OpenSim order, active/passive interpretation, multiplication direction, world axes, and `q/-q` ambiguity can all yield plausible but wrong angles.
**Instead:** Name every source/target frame in the equation and lock it with deterministic rotations.

### Hot-Swapping Model State

**Why it fails:** Frame/coordinate handles and solver goals become stale; calibration may refer to another model.
**Instead:** Tear down and construct a fresh worker state, then revalidate calibration by hash.

### Publishing Angles Without Validity and Provenance

**Why it fails:** rosbridge and future visualization cannot distinguish current solutions from held/stale/failed ones or know which model they animate.
**Instead:** Pair standard `JointState` with typed validity/quality and latched model metadata.

### Expanding Synchronizer Slop Until Data Pairs

**Why it fails:** It conceals a time-base or hardware synchronization defect and produces biomechanically inconsistent poses.
**Instead:** Measure skew distributions and propagate hardware sequence/time if host receipt timing is inadequate.

## Scaling and Performance Considerations

The relevant scale is sensor rate and model complexity, not web-user count.

| Load | Architecture response |
|------|-----------------------|
| 2 IMUs at 100 Hz, small model | Python ROS shell plus native OpenSim worker should be adequate if measured solve time remains comfortably below the sample interval. |
| Higher sensor rate or larger model | Keep latest-only queue, publish at a configured output rate, reduce tracked coordinates/goals only with biomechanical justification, and profile native solve time. |
| More IMUs | Generalize mapping/config and synchronizer only after paired flow is correct; evaluate C++ adapter if Python conversion overhead becomes material. |
| Multiple simultaneous subjects | Run one namespaced bridge process and immutable model/calibration set per subject; do not share mutable OpenSim models. |

First bottleneck is likely native solve latency relative to the 10 ms period at 100 Hz. Second is timestamp quality/pair skew, not DDS bandwidth. Optimize only after publishing solve-time, queue-overwrite, skew, and end-to-end latency distributions.

## Sources

- OpenSim, [InverseKinematicsSolver API](https://opensim-org.github.io/opensim-moco-site/docs/1.0.0/html_user/classOpenSim_1_1InverseKinematicsSolver.html) — solver construction and `assemble()`/`track()` usage (HIGH confidence).
- OpenSim, [BufferedOrientationsReference API](https://opensim-org.github.io/opensim-moco-site/docs/1.1.0/html_user/classOpenSim_1_1BufferedOrientationsReference.html) — official streaming-orientation reference (HIGH confidence; Python exposure still requires target-version verification).
- OpenSim, [OrientationsReference API](https://opensim-org.github.io/opensim-moco-site/docs/1.1.0/html_user/classOpenSim_1_1OrientationsReference.html) — orientation frames, rotations, and weights (HIGH confidence).
- OpenSim, [How to Use the IMU Placer](https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084302/How%2Bto%2BUse%2Bthe%2BIMU%2BPlacer) — sensor-world to OpenSim-ground transformation and heading correction (HIGH confidence).
- OpenSim, [OpenSense FAQ](https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084548/Frequently%2BAsked%2BQuestions) — calibration estimates orientation, not sensor position; OpenSense outputs joint angles (HIGH confidence).
- ROS 2, [message_filters API](https://docs.ros.org/en/ros2_packages/kilted/api/message_filters/message_filters.html) and [time synchronizer tutorial](https://docs.ros.org/en/kilted/p/message_filters/doc/Tutorials/Writing-A-Time-Synchronizer-Python.html) — timestamp pairing, slop, and matching QoS requirements (HIGH confidence; verify Humble API availability on target).
- ROS, [REP-107 Diagnostic System](https://docs.ros.org/en/independent/api/rep/html/rep-0107.html) and [diagnostic_msgs](https://docs.ros.org/en/ros2_packages/humble/api/diagnostic_msgs/) — `/diagnostics` contract and status levels (HIGH confidence).
- Repository evidence: `.planning/PROJECT.md`, `backend/rehab_robotics_bridge/opensim_node.py`, `backend/launch/rehab_robotics.launch.py`, and `backend/rehab_robotics_bridge/esp32_bridge_node.py` inspected 2026-07-27.

## Research Flags

- Verify the exact OpenSim version and Python binding on the deployment image, especially construction and queue APIs for `BufferedOrientationsReference`. If missing, prefer a C++ adapter package inside the same ROS graph over a custom network daemon.
- Measure whether independent host-receipt stamps meet the required master/slave synchronization tolerance. The current firmware/bridge contract does not demonstrate shared hardware acquisition time.
- Select biomechanically defensible model, sensor-frame placement, coordinate constraints, weights, residual thresholds, and reference pose with domain validation; software architecture cannot establish their clinical validity.
- Confirm the chosen ROS 2 distribution's `message_filters` Python QoS behavior and rosbag2 launch/record options on the disconnected Jetson image.

---
*Architecture research for: Rehab Robotics Studio v1.4 real-time OpenSim IK*
*Researched: 2026-07-27*
