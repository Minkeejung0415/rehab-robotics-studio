# Stack Research

**Domain:** Live paired-IMU quaternion-to-OpenSim inverse kinematics in ROS 2
**Researched:** 2026-07-27
**Confidence:** HIGH for OpenSim/ROS APIs and x86-64 packaging; MEDIUM for the Jetson deployment until its exact module and JetPack release are confirmed

## Recommendation

Add a small C++ ROS 2 package, `rehab_robotics_opensim`, beside the existing Python `rehab_robotics_bridge`. Build it with `ament_cmake`, link it to a pinned, headless OpenSim 4.6 installation, and run the live solver through `OpenSim::BufferedOrientationsReference` plus `OpenSim::InverseKinematicsSolver`.

Do **not** import OpenSim into the existing `ament_python` node. The current ROS environment is Humble on Ubuntu 22.04 with Python 3.10, while the official OpenSim 4.6 Conda channel currently publishes Python 3.11/3.12/3.13 packages only. More importantly, its Linux package is `linux-64` (x86-64), not `linux-aarch64`, so it cannot be installed on Jetson. A native C++ OpenSim build avoids the Python ABI collision and uses the same node source on WSL2 x86-64 and Jetson ARM64.

OpenSense remains the compatibility model for sensor naming, calibration, weights, and orientation error. Its `IMUPlacer` and `IMUInverseKinematicsTool` are file-oriented batch tools. They should be used to validate fixtures and exported sessions, not invoked once per live sample. OpenSim's genuine streaming API is the `BufferedOrientationsReference::putValues()` queue consumed by a persistent `InverseKinematicsSolver`.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| ROS 2 Humble Hawksbill | Existing distro; Ubuntu 22.04 packages | Node lifecycle, synchronization, standard messages, launch and diagnostics | Preserves the validated project environment and is available for Ubuntu Jammy on ARM64. Do not change ROS distro in this milestone. |
| C++ | C++20 | Live solver node | OpenSim 4.6 itself requires C++20. A compiled node avoids Python/SWIG overhead and the unavailable Jetson Conda package. |
| OpenSim Core | **4.6**, exact tag/commit pinned | Model loading, sensor-frame calibration representation and orientation IK | This is the current OpenSim release as of research. Its source includes the live-data `BufferedOrientationsReference` API and `InverseKinematicsSolver::assemble()/track()`. |
| Simbody | Revision vendored by OpenSim 4.6 dependency superbuild | Multibody assembly and orientation tracking | Use the revision pinned by the OpenSim release rather than selecting an independent Simbody version. This prevents OpenSim/Simbody ABI drift. |
| CMake + Ninja | CMake >=3.15; Ubuntu 22.04 CMake 3.22 is suitable | Build OpenSim and the ROS package | OpenSim 4.6 declares CMake 3.15 minimum. Ninja gives lower-overhead native builds on Jetson. |

### ROS 2 Libraries and Interfaces

| Library / interface | Version | Purpose | When to Use |
|---------------------|---------|---------|-------------|
| `rclcpp` | Humble, rosdep-managed | C++ ROS node | The new OpenSim node only; retain `rclpy` for the existing acquisition bridge. |
| `message_filters` | Humble (current Humble docs: 4.12.x) | Pair master/slave `sensor_msgs/Imu` samples by `header.stamp` | Prefer exact-time synchronization when the paired ESP32 messages carry the same source timestamp. Permit approximate-time only as an explicit, tightly bounded fallback. |
| `sensor_msgs/Imu` | Humble `sensor_msgs` 4.9.x | Quaternion input | Continue consuming the existing native IMU topics; no JSON or UDP intermediate is needed. |
| `sensor_msgs/JointState` | Humble `sensor_msgs` 4.9.x | Solved coordinate output | Publish revolute coordinates in radians and prismatic coordinates in metres, as required by the message definition. Leave velocity/effort empty unless they are actually estimated. |
| `diagnostic_updater` + `diagnostic_msgs` | Humble 4.0.x / 4.9.x | Periodic bridge and solver health | Report input age/rate, sync rejects, invalid quaternions, calibration state, sensors in use, solve latency, tracking failures, and orientation residuals on `/diagnostics`. |
| `std_srvs/Trigger` | Humble | Capture a reference-pose calibration | A `calibrate` service can arm the node to use the next valid synchronized pair. Use a separate reset/reload service only if required. |
| `rehab_robotics_interfaces` | Existing local package, increment its schema deliberately | Structured solver quality/status for the GUI | Add a compact IK status message only if `/diagnostics` is inconvenient through rosbridge. Keep `JointState` as the canonical kinematic output. |
| `ament_cmake_gtest` | Humble | Deterministic native tests | Test quaternion order, sign equivalence, calibration transforms, known poses, stale data, synchronizer behavior, and solver failure recovery without hardware. |

No additional quaternion library is needed. Convert and validate at the boundary, then use `SimTK::Quaternion`, `SimTK::Rotation`, and `SimTK::Transform` consistently inside the solver. Avoid mixing Eigen, SciPy, `tf.transformations`, and SimTK conventions in the same calculation.

### Development and Deployment Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| WSL2 Ubuntu 22.04 | Primary Windows-hosted integration environment | Build the same Linux C++ source used on Jetson. Native Windows OpenSim may be useful for isolated model inspection, but is not the deployment reference. |
| `rosdep` + `colcon` | Resolve ROS dependencies and build the workspace | OpenSim is an external pinned native prefix, not a PyPI dependency and not rebuilt by every `colcon build`. |
| OpenSim 4.6 dependency superbuild | Produce compatible Simbody/spdlog dependencies | Disable visualization, CasADi/Moco solver dependencies, C3D parsing, Java, Python, examples, and tests in the deployable artifact. |
| `ldd`, `readelf`, and a launch-time smoke test | Verify the installed ARM64 artifact | Fail deployment if `libosim*.so` or `libSimTK*.so` resolves outside the packaged prefix. |
| `ros2 bag` / deterministic topic publisher | Replay paired orientation fixtures | Use existing ROS tooling; no new recording framework is required. |

## Package Boundary

Keep acquisition and solving separate:

```text
backend/                         # existing ament_python package
  rehab_robotics_bridge/
    esp32_bridge_node.py         # unchanged ownership: acquisition
    filter_node.py               # unchanged ownership: filtering
    opensim_node.py              # retire placeholder entry point after migration

rehab_robotics_opensim/          # new ament_cmake package
  CMakeLists.txt
  package.xml
  include/rehab_robotics_opensim/
    quaternion_validation.hpp
    calibration.hpp
    streaming_ik.hpp
  src/
    opensim_bridge_node.cpp
    calibration.cpp
    streaming_ik.cpp
  test/
    test_quaternion_conventions.cpp
    test_calibration.cpp
    test_known_pose_ik.cpp
  models/
    <versioned model and mapping fixtures>
```

The existing launch file can start both Python acquisition nodes and the C++ OpenSim executable. Package type is a build-system boundary: do not try to turn the existing `ament_python` package into a mixed Python/C++ package for this milestone.

## OpenSim API Pattern

### 1. Load and prepare a model once

Use `OpenSim::Model` to load the configured `.osim` file. Validate configured coordinate names and IMU-frame labels before calling `initSystem()`. The orientation-reference labels must match `PhysicalFrame` names in the model; OpenSim's solver forms the intersection by name.

For an OpenSense-compatible model, sensor frames should be named such as `femur_r_imu` and represented by `OpenSim::PhysicalOffsetFrame` objects. An `OpenSim::IMU` component connected to each offset frame preserves OpenSense model semantics, although the orientation solver itself matches the `PhysicalFrame` names.

### 2. Calibrate in memory from a known pose

OpenSense `IMUPlacer` computes the sensor offset using the known model pose and the measured calibration orientation. Its source implements the essential rotation as:

```text
R_body_sensor = inverse(R_ground_body_at_reference) * R_ground_sensor_measured
```

Apply the configured sensor-world-to-OpenSim-ground rotation before this step. Update or create the sensor `PhysicalOffsetFrame` transforms, call `finalizeConnections()`, then call `initSystem()` and construct a fresh solver. Model topology/offset mutation is a calibration transition, not a per-sample operation.

Do not run `IMUPlacer` against a temporary one-row `.sto` file during live operation. A one-row OpenSense fixture is still valuable as an offline oracle: the in-memory calibration should produce the same offset frame as `IMUPlacer`.

### 3. Create the streaming reference and persistent solver

Seed a `TimeSeriesTable_<SimTK::Rotation>` with the sensor labels so the reference has a stable observation order, then create:

```cpp
auto refs = std::make_shared<OpenSim::BufferedOrientationsReference>(
    labeled_seed_table, &orientation_weights);
SimTK::Array_<OpenSim::CoordinateReference> coordinate_refs;
OpenSim::InverseKinematicsSolver solver(
    model, nullptr, refs, coordinate_refs);
solver.setAccuracy(1e-4);
solver.setAdvanceTimeFromReference(true);
```

The `1e-4` accuracy matches the value used by OpenSim's `IMUInverseKinematicsTool`; expose it as an advanced parameter, but begin with that default. Before the first `assemble(state)`, queue the first sample with `refs->putValues(time, rotations)`. For each subsequent synchronized sample, queue one row and call `track(state)`. Reuse the same model, state, reference and solver; `track()` is explicitly optimized for small updates after an initial `assemble()`.

If `track()` throws or residuals exceed policy, mark the output degraded and do not publish a silently stale pose. A bounded recovery may attempt `assemble()` on the current valid sample. Repeated failure should transition the node out of solving until recalibration/model reload.

### 4. Convert conventions explicitly

ROS `geometry_msgs/Quaternion` fields are `(x, y, z, w)`. SimTK's four-scalar quaternion constructor is scalar-first, so construct:

```cpp
SimTK::Quaternion q(ros_q.w, ros_q.x, ros_q.y, ros_q.z);
SimTK::Rotation R_GS(q);
```

Before construction, reject non-finite values and norms below a small threshold; normalize only quaternions within a configured tolerance of unit length. Treat `q` and `-q` as the same rotation in tests. Document whether each ESP32 quaternion is active or passive and what its source/target frames are; field order alone is not a complete convention.

### 5. Publish results and quality

Read each configured OpenSim coordinate with `Coordinate::getValue(state)`. OpenSim state values and `JointState.position` are both radians for rotational coordinates, so do not convert the canonical ROS output to degrees. The GUI may convert for display.

Use:

- `/opensim/joint_states` — `sensor_msgs/JointState`, timestamped with the synchronized input measurement time.
- `/diagnostics` — standard diagnostic status with input, calibration, model, and solver health.
- `/opensim/status` — optional typed local message for rosbridge with solve time, input skew/age, number of sensors used, per-sensor or RMS orientation error, calibration generation, and state.

`InverseKinematicsSolver::computeCurrentOrientationErrors()` and `getOrientationSensorNameForIndex()` provide the solver residuals and stable sensor names. Confirm residual units with a deterministic known-angle test before presenting degrees in the UI; the C++ API documentation describes orientation error but does not state units next to that method.

## Synchronization and Execution Model

Use sensor-data QoS on both IMU subscriptions, and ensure both `message_filters` subscribers request compatible QoS. ROS documentation warns that incompatible QoS prevents synchronization entirely.

Recommended policy:

1. Exact timestamp pair when both ESP32 messages inherit a shared acquisition timestamp or pair sequence.
2. Approximate-time fallback only when exact stamping is impossible, with a small configurable slop derived from the acquisition rate.
3. Reject pairs whose source timestamps go backwards, exceed maximum skew, or are already stale at solve time.
4. Never pair "latest master" with "latest slave" without a timestamp bound.

Keep all OpenSim mutation and solver calls on one serialized execution path. Subscription callbacks may feed a bounded queue, but `Model`, `State`, `BufferedOrientationsReference`, and `InverseKinematicsSolver` should not be accessed concurrently. Bound the queue to favor fresh motion over accumulated latency.

## Runtime Packaging

### Build one OpenSim prefix per architecture

Pin the exact OpenSim 4.6 source commit in a lock/provisioning file. Build Release mode separately for:

- `linux-x86_64` — WSL2/CI/local deterministic testing.
- `linux-aarch64` — the Jetson target.

Do not copy the x86-64 Conda libraries to Jetson. Package the OpenSim install prefix together with its copied Simbody dependencies, preserve RPATH, and expose `OpenSim_DIR`/`CMAKE_PREFIX_PATH` while building the ROS node.

Illustrative headless build:

```bash
# Checkout the exact 4.6 tag/commit first.
cmake -S opensim-core/dependencies -B build/opensim-deps -GNinja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/opt/opensim-4.6/dependencies \
  -DSUPERBUILD_ezc3d=OFF \
  -DSUPERBUILD_catch2=OFF \
  -DOPENSIM_WITH_CASADI=OFF \
  "-DSIMBODY_EXTRA_CMAKE_ARGS=-DSIMBODY_BUILD_VISUALIZER:BOOL=OFF"
cmake --build build/opensim-deps --parallel

cmake -S opensim-core -B build/opensim -GNinja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/opt/opensim-4.6 \
  -DOPENSIM_DEPENDENCIES_DIR=/opt/opensim-4.6/dependencies \
  -DBUILD_API_ONLY=ON \
  -DBUILD_TESTING=OFF \
  -DBUILD_PYTHON_WRAPPING=OFF \
  -DBUILD_JAVA_WRAPPING=OFF \
  -DOPENSIM_WITH_CASADI=OFF \
  -DOPENSIM_C3D_PARSER=None \
  -DOPENSIM_COPY_DEPENDENCIES=ON \
  -DOPENSIM_INSTALL_UNIX_FHS=ON \
  -DOPENSIM_DISABLE_LOG_FILE=ON
cmake --build build/opensim --parallel
cmake --install build/opensim
```

The official all-features Linux script installs visualization, Java, SWIG, Python, C3D and optional Moco dependencies. Those are unnecessary for this node; use the release's CMake options to produce a smaller headless runtime. Validate the exact command on both target architectures and record checksums of the resulting artifact.

Install ROS-side dependencies through rosdep/apt:

```bash
sudo apt install \
  ros-humble-rclcpp \
  ros-humble-message-filters \
  ros-humble-sensor-msgs \
  ros-humble-std-srvs \
  ros-humble-diagnostic-updater \
  ros-humble-ament-cmake-gtest

export OpenSim_DIR=/opt/opensim-4.6/lib/cmake/OpenSim
colcon build --packages-select rehab_robotics_opensim
```

Link the executable with the OpenSim CMake package:

```cmake
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(OpenSim 4.6 REQUIRED)
find_package(rclcpp REQUIRED)
find_package(message_filters REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(diagnostic_updater REQUIRED)

ament_target_dependencies(opensim_bridge
  rclcpp message_filters sensor_msgs diagnostic_updater)
target_link_libraries(opensim_bridge ${OpenSim_LIBRARIES})
```

### Windows development

Use the existing WSL2 Ubuntu 22.04/Humble environment as the authoritative development runtime. It matches Linux path, compiler, loader, ROS, and OpenSim behavior closely enough for deterministic local validation.

OpenSim's native Windows or Conda package can run offline exploratory scripts, but do not make native Windows output the only test oracle. Native Windows ROS, MSVC-built OpenSim, and Linux/GCC-built OpenSim are different binary ecosystems.

### Jetson compatibility gate

JetPack 6.2.1 uses an Ubuntu 22.04-based Jetson Linux release and is the clean match for ROS 2 Humble. JetPack 6 supports Jetson Orin modules. Before implementation, record:

- exact Jetson module (Orin versus Xavier family),
- JetPack/L4T version,
- architecture (`aarch64`),
- available RAM/swap and storage,
- whether ROS Humble is native Jammy apt or container/custom source installed.

If the target is an Orin on JetPack 6.x, build OpenSim 4.6 natively or in an equivalent ARM64 build environment and deploy the relocatable prefix. If it is a Xavier restricted to JetPack 5/Ubuntu 20.04, native Humble Jammy packages are not a supported match; that is a platform decision requiring a container/source-build plan or OS/hardware change. Do not bury this incompatibility inside the IK phase.

OpenSim/Simbody IK is CPU work. CUDA, TensorRT, cuDNN, Isaac ROS, and GPU containers do not accelerate this solver and should not be added.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| C++ `rclcpp` node with source-built OpenSim 4.6 | Python `rclpy` + OpenSim Conda | Only for a disposable x86-64 desktop prototype. OpenSim 4.6 lacks official Python 3.10 and Linux ARM64 Conda artifacts. |
| OpenSim 4.6 | OpenSim 4.5.2 | Use 4.5.2 only if an already-validated model/plugin fails on 4.6 and the incompatibility is documented. Version 4.5.2 does have official Python 3.10 x86-64 packages, but still no Jetson Linux ARM64 package. |
| Persistent `InverseKinematicsSolver` + `BufferedOrientationsReference` | `IMUInverseKinematicsTool` | Use the tool for recorded `.sto` batch validation and comparison, not for a callback-driven stream. |
| In-memory known-pose calibration | `IMUPlacer` with a temporary `.sto` | Use `IMUPlacer` offline to generate/verify calibrated `.osim` fixtures or as an oracle in a test. |
| Exact timestamp synchronization | Approximate-time synchronization | Use approximate time only when upstream cannot stamp the pair identically; enforce explicit skew and age limits. |
| Prebuilt per-architecture OpenSim prefix | Build OpenSim inside every colcon build | A full source build in colcon is acceptable only for dedicated CI/vendor packaging, not normal iteration on WSL or Jetson. |

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| OpenSim GUI or embedded 3D renderer | Visualization is explicitly deferred and pulls unrelated graphics dependencies | Headless OpenSim API and standard ROS outputs |
| `IMUInverseKinematicsTool::run()` per frame | It loads an orientation file, initializes the solver, iterates a table, and writes batch results | Persistent streaming reference and solver |
| Python OpenSim 4.6 in the Humble interpreter | Official package versions do not target Python 3.10, and no Linux ARM64 artifact exists | C++20 OpenSim node |
| Conda as the Jetson runtime | The official channel lists `linux-64`, not `linux-aarch64` | Pinned ARM64 source build |
| OpenSimLive as the primary dependency | It is useful prior art, but its published implementation targeted OpenSim 4.1 and adds another integration layer | Use the upstream OpenSim 4.6 streaming APIs directly |
| Moco/CasADi/Ipopt | Trajectory optimization is not frame-by-frame orientation IK and substantially increases build size | `InverseKinematicsSolver` |
| CUDA/TensorRT/Isaac ROS | The chosen solver is CPU-based; these do not remove its bottleneck | Profile the C++ solver and reduce model DOFs if needed |
| Generic full-body model with only two equally weighted IMUs | Two orientations do not observe every full-body coordinate, producing plausible but non-identifiable motion | A reduced, constrained model with only intended coordinates unlocked |
| Extra Eigen/SciPy quaternion layer | Increases convention and ownership ambiguity | Boundary conversion followed by SimTK rotations |
| Unbounded callback/solver queue | Produces growing latency while appearing healthy | Bounded newest-sample queue plus dropped-frame diagnostics |
| Docker packaging in this milestone | Project scope explicitly defers broader Docker packaging | Native WSL2 and Jetson prefixes with recorded build metadata |

## Version Compatibility

| Package / platform | Compatible With | Notes |
|--------------------|-----------------|-------|
| OpenSim 4.6 | CMake >=3.15, C++20 | Current release; `BufferedOrientationsReference` and orientation IK APIs remain available. |
| OpenSim 4.6 Conda | Python 3.11, 3.12, 3.13 on `linux-64`; Windows x64 and macOS variants also published | No official Python 3.10 build and no `linux-aarch64` build in the official file list. |
| OpenSim 4.5.2 Conda | Python 3.10/3.11/3.12 on x86-64 desktop platforms | Possible offline Python fallback, not a Jetson deployment solution. |
| ROS 2 Humble debs | Ubuntu 22.04 Jammy; Python 3.10; ARM64 packages | Matches current WSL environment and JetPack 6.x Ubuntu base. |
| JetPack 6.2.1 | Ubuntu 22.04-based Jetson Linux; Orin family | Recommended Jetson baseline for native Humble. Confirm the actual target before scheduling ARM64 packaging. |
| JetPack 5.x / Xavier | Ubuntu 20.04-based platform | Does not natively align with Humble's Jammy binary target; requires an explicit platform strategy. |
| `sensor_msgs/JointState` | radians/metres positions | OpenSim rotational coordinate values can be published directly in radians. |

## Validation Required Before Roadmap Execution

1. Build a minimal OpenSim 4.6 C++ program in WSL2 that loads the intended model, confirms both configured sensor frames are in use, calls `assemble()`, then calls `track()` across a deterministic quaternion sequence.
2. Confirm the exact Jetson module/JetPack and complete the same smoke test on ARM64 before treating deployment as solved.
3. Compare one recorded fixture against `IMUPlacer` + `IMUInverseKinematicsTool` offline results within documented tolerances.
4. Benchmark solve time at the intended IMU rate using the reduced production model. If it misses deadline, simplify/lock coordinates before considering new compute libraries.
5. Verify orientation-error units and frame direction with a known single-axis pose, rather than relying on labels or visual plausibility.

## Sources

### OpenSim primary sources

- OpenSim 4.6 release and C++20 change: https://github.com/opensim-org/opensim-core/releases/tag/4.6
- OpenSim 4.6 core source and official build support: https://github.com/opensim-org/opensim-core/tree/4.6
- Live orientation reference API (`putValues`, queue semantics): https://github.com/opensim-org/opensim-core/blob/4.6/OpenSim/Simulation/BufferedOrientationsReference.h
- Live reference implementation: https://github.com/opensim-org/opensim-core/blob/4.6/OpenSim/Simulation/BufferedOrientationsReference.cpp
- IK constructors, `assemble`, `track`, sensor errors, and streaming time control: https://github.com/opensim-org/opensim-core/blob/4.6/OpenSim/Simulation/InverseKinematicsSolver.h
- Batch OpenSense IK implementation and its `1e-4` accuracy: https://github.com/opensim-org/opensim-core/blob/4.6/OpenSim/Tools/IMUInverseKinematicsTool.cpp
- `IMUPlacer` calibration-frame implementation: https://github.com/opensim-org/opensim-core/blob/4.6/OpenSim/Simulation/OpenSense/IMUPlacer.cpp
- OpenSim dependency superbuild and headless Simbody option: https://github.com/opensim-org/opensim-core/blob/4.6/dependencies/CMakeLists.txt
- Official OpenSim Conda file/platform matrix: https://anaconda.org/opensim-org/opensim/files
- OpenSense batch tool documentation: https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084203/OpenSense+-+Kinematics+with+IMU+Data
- SimTK quaternion scalar-first representation: https://simbody.github.io/3.6.0/Quaternion_8h_source.html

### ROS and NVIDIA primary sources

- ROS 2 Humble QoS and sensor-data profile: https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html
- Humble `message_filters` C++ API: https://docs.ros.org/en/ros2_packages/humble/api/message_filters/generated/index.html
- `sensor_msgs/JointState` units: https://docs.ros.org/en/ros2_packages/humble/api/sensor_msgs/msg/JointState.html
- Humble `diagnostic_updater`: https://docs.ros.org/en/ros2_packages/humble/api/diagnostic_updater/index.html
- NVIDIA JetPack 6.2.1 release notes and Orin support: https://docs.nvidia.com/jetson/jetpack/6.2.1/release-notes/index.html
- NVIDIA Jetson Linux 36.x Ubuntu 22.04 release basis: https://docs.nvidia.com/jetson/archives/r36.4/ReleaseNotes/Jetson_Linux_Release_Notes_r36.4.pdf

### Corroborating implementation research

- OpenSimLive paper (useful evidence for persistent real-time C++ IK, but based on OpenSim 4.1): https://pmc.ncbi.nlm.nih.gov/articles/PMC10082569/

---
*Stack research for: Rehab Robotics Studio v1.4 Real-time OpenSim IK*
*Researched: 2026-07-27*
