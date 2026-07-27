# Project Research Summary

**Project:** Rehab Robotics Studio
**Domain:** Live paired-IMU quaternion-to-OpenSim inverse kinematics in ROS 2
**Milestone:** v1.4 Real-time OpenSim IK
**Researched:** 2026-07-27
**Confidence:** HIGH for the software contract and core APIs; MEDIUM overall until hardware, model, and timing decisions are validated

## Executive Summary

Rehab Robotics Studio v1.4 is a validity-gated biomechanical estimator: it must turn two timestamped, fused ESP32 orientations into calibrated OpenSim joint coordinates without presenting stale, under-observed, or conventionally incorrect values as live measurements. Experts build this as a staged pipeline with explicit frame semantics, timestamp-based pairing, reference-pose calibration, a persistent orientation IK solver, bounded latest-value processing, and separate standard kinematic and quality outputs. Acquisition integrity is a prerequisite; IK cannot repair unknown sensor identities, broken clocks, unfused orientations, or arbitrary gaps.

The recommended deployable architecture is a new C++20 `ament_cmake` package, `rehab_robotics_opensim`, using pinned OpenSim 4.6, `rclcpp`, `message_filters`, `BufferedOrientationsReference`, and a persistent `InverseKinematicsSolver`. It should remain a dedicated ROS process beside the existing Python acquisition bridge, with one serialized execution path owning all OpenSim/Simbody state. Exact timestamp pairing is preferred when upstream can provide a shared acquisition time or sequence; tightly bounded approximate pairing is a measured fallback. Publish canonical coordinates through timestamped `sensor_msgs/JointState`, and publish validity, provenance, residuals, latency, calibration identity, and reason-coded failures through a typed IK status plus `/diagnostics`.

The main risks are plausible-but-wrong quaternion/frame math, invalid reference-pose calibration, mismatched or stale samples, OpenSim/Jetson ABI failure, unbounded solver latency, and treating two-IMU/model-constrained outputs as clinically validated measurements. Mitigate them by freezing conventions and golden fixtures first, proving the native runtime on both x86-64 and ARM64, binding calibration to immutable model/config hashes, failing closed on stale or failed solutions, benchmarking the reduced model on target hardware, and finishing with observability, replay, drift, and offline OpenSense parity studies. Do not claim biomechanical or clinical accuracy without a separate external-reference validation protocol.

## Key Findings

### Recommended Stack

The stack research supersedes the architecture draft wherever that draft assumes OpenSim can run through the existing Humble Python 3.10 process. OpenSim 4.6's official Conda packages target newer Python versions on `linux-64`, not Jetson `linux-aarch64`; the deployable solution is therefore native C++ rather than an in-process Python binding. Preserve the architecture's useful logical boundaries—a narrow solver interface, fake implementation for deterministic tests, single ownership of mutable solver state, and a dedicated ROS process—but implement the production solver as the new C++ package rather than `backend/rehab_robotics_bridge/opensim/opensim_adapter.py`.

**Core technologies:**

- **ROS 2 Humble on Ubuntu 22.04:** preserves the existing ROS environment and provides Jammy ARM64 packages.
- **C++20 + `ament_cmake`:** required by OpenSim 4.6 and avoids Python ABI and Jetson package incompatibilities.
- **OpenSim 4.6, exact tag/commit pinned:** provides `BufferedOrientationsReference` and persistent `InverseKinematicsSolver::assemble()/track()` streaming APIs.
- **OpenSim-pinned Simbody dependencies:** avoids OpenSim/Simbody ABI drift; build one headless Release prefix per architecture.
- **`rclcpp`, `message_filters`, `sensor_msgs`, `diagnostic_updater`, `std_srvs`:** provide ROS process control, synchronized IMU ingress, standard outputs, health, and calibration/reset controls.
- **`rehab_robotics_interfaces`:** should carry a compact, versioned IK validity/quality contract; keep `JointState` as the canonical interoperable projection.
- **`ament_cmake_gtest`, deterministic publishers, and rosbag2:** support convention, calibration, timing, failure, replay, and offline-parity verification without connected hardware.
- **WSL2 Ubuntu 22.04:** is the authoritative local Linux development environment; native Windows can assist inspection but is not the deployment oracle.

**Critical version/platform requirements:**

- Pin OpenSim **4.6** and the dependency revisions selected by its release.
- Build separate `linux-x86_64` and `linux-aarch64` OpenSim prefixes; never copy x86-64 Conda libraries to Jetson.
- Jetson Orin with JetPack 6.x aligns cleanly with Humble/Jammy. Xavier on JetPack 5.x does not and requires an explicit platform, container/source-build, or hardware/OS decision before implementation.
- CUDA, TensorRT, Isaac ROS, Moco, CasADi, OpenSim GUI, and embedded 3D rendering do not help the CPU-based streaming IK objective and should not enter v1.4.

### Expected Features

**Must have (table stakes):**

- Fail-fast validation of the `.osim` model, absolute coordinate paths, IMU frames, sensor mapping, units, locks, constraints, and selected output set.
- One declared quaternion/frame boundary covering ROS `(x,y,z,w)`, SimTK scalar-first construction, active/passive direction, world axes, handedness, and sensor-to-OpenSim transform.
- Finite/unit quaternion gating, bounded normalization, antipode handling, counters, and deterministic identity/±90° fixtures.
- Timestamp-based master/slave synchronization with compatible QoS, bounded queues, skew/age/monotonicity rules, and no arrival-time or unbounded “latest pair” shortcut.
- Explicit `UNCALIBRATED`, `CALIBRATING`, `READY/TRACKING`, `DEGRADED`, `STALE`, and `ERROR` behavior.
- Stable multi-sample known-pose calibration with heading handling, rejection reasons, invalidation rules, and model/config/mapping provenance.
- Persistent OpenSense-compatible weighted orientation IK using initial `assemble()` and sequential `track()`.
- Latest-value bounded processing with solve time, queue wait, age, deadline misses, drops, and recovery metrics.
- Timestamped `JointState` in radians/metres plus typed validity/quality/provenance output and continuous standard diagnostics.
- Fail-closed stale/error behavior: never republish cached angles with a fresh timestamp.
- Deterministic local verification for convention, calibration, known poses, sync edges, dropout, solver failures, recovery, output schema, and offline OpenSense parity.

**Should have (competitive):**

- Versioned calibration save/load tied to model/config hashes and convention schema.
- Calibration preview and acceptance gate with stability, offset, heading, and residual evidence.
- Dry-run model/mapping introspection for custom models.
- Configurable per-observation weights with transparent effective values.
- Replay equivalence across online and rosbag/fixture modes.
- Percentile-ready latency budgeting and optional OpenSim-compatible motion export.
- A hardware-free calibration/solver self-test command.

**Defer (v2+):**

- Embedded OpenSim 3D visualization, mesh streaming, or an OpenSim-to-URDF/TF renderer.
- Automatic first-sample calibration, implicit partial-sensor fallback, adaptive weighting, drift correction, or interpolation across arbitrary gaps.
- Additional IMUs, whole-body/general models, inverse dynamics, muscle analysis, Moco, or clinical-use claims.
- Broad Docker packaging, CUDA/GPU tooling, and model hot-swapping.

### Architecture Approach

Keep acquisition and solving as separate ROS processes. The existing Python bridge remains responsible for trustworthy typed IMU messages and stable sensor identity. The new C++ process validates and synchronizes inputs, owns calibration and immutable model/config identities, runs OpenSim through one serialized owner, and publishes results. Use a capacity-one or very small bounded handoff so overload drops superseded observations rather than accumulating latency. The architecture draft's `IkSolverAdapter` remains valuable as a conceptual/test interface, but the production implementation belongs in C++20; pure quaternion/calibration functions and fake solvers can still make most tests independent of a full native OpenSim install.

**Major components:**

1. **ESP32 acquisition bridge** — publishes normalized, stamped `sensor_msgs/Imu` with stable frame IDs and preserves sequence/quality metadata where available.
2. **Ingress validator and synchronizer** — enforces quaternion, identity, timestamp, skew, age, QoS, queue, and drop rules before solving.
3. **Model/config loader** — resolves installed assets, hashes contents, validates frames/coordinates/units, and publishes immutable model metadata.
4. **Calibration controller** — captures a stable reference window, calculates heading and mounting transforms, validates a candidate, persists provenance, and gates IK.
5. **C++ streaming IK owner** — owns `Model`, `State`, `BufferedOrientationsReference`, and `InverseKinematicsSolver`; queues one row, assembles once, tracks sequentially, and performs bounded recovery.
6. **Output and health publisher** — emits source-timestamped `JointState`, typed IK status, calibration/model metadata, and diagnostics even while solutions are unavailable.
7. **Verification and replay harness** — uses fakes, golden rotations, synthetic model poses, offline OpenSense tools, and rosbag2 to reproduce behavior.

**Key patterns:**

- Functional core with ROS/OpenSim imperative shell.
- Single owner for every mutable OpenSim/Simbody object.
- Latest-value processing with explicit drops and deadlines.
- Provenance-bound, transactionally activated calibration.
- `assemble()` after init/reset/discontinuity; `track()` only for adjacent valid samples.
- Standard kinematics plus a separate authoritative validity/quality contract.

### Conflict Resolution

| Conflict | Resolution | Rationale |
|----------|------------|-----------|
| Architecture proposes Python `rclpy` orchestration with an in-process OpenSim adapter; stack recommends a C++20 package | **Choose the separate C++20 `ament_cmake` ROS package for production.** Keep the adapter seam and fake-test concept, but express the production seam in C++ and retain Python only for existing acquisition or offline disposable tests. | OpenSim 4.6 requires C++20; official packages do not match Humble Python 3.10 or Jetson ARM64. The C++ node is already OS-process isolated by ROS launch and uses one source base on WSL2 and Jetson. |
| Architecture defaults to approximate synchronization because current bridges stamp independently; stack prefers exact time | **Treat exact pairing as the target contract and approximate pairing as a measured fallback.** | Host-receipt timestamps are not proof of simultaneous acquisition. Phase 16 must measure skew and may require shared device sequence/acquisition time upstream. |
| Architecture sketches assets under the existing Python package; stack places solver/model fixtures in a new package | **Put solver-owned C++ code and its directly versioned model/mapping fixtures in `rehab_robotics_opensim`; keep shared interface definitions in `rehab_robotics_interfaces`.** | This follows the build-system and deployment boundary. The final asset location can be adjusted only if a deliberate shared-assets package is introduced. |
| Features request multi-sample calibration while stack describes using the next valid pair for a Trigger | **Use multi-sample, stable-window calibration.** | A single sample is too vulnerable to motion/noise; in-memory calibration math and solver rebuild remain as recommended by stack research. |

### Critical Pitfalls

1. **Plausible but wrong quaternion/frame conventions** — perform one explicit boundary conversion and prove identity plus ±90° rotations through the full model adapter before using live data.
2. **Bad, moving, or stale calibration** — require a bounded stable capture, validate a held-out reference and known non-reference pose, bind artifacts to model/config/mapping hashes, and invalidate on remount/reboot/schema changes.
3. **Incoherent timestamp pairing** — pair by measurement time with compatible QoS, measured skew/age limits, bounded expiry, and upstream shared acquisition identity if host stamps are inadequate.
4. **OpenSim runtime/ABI mismatch** — pin OpenSim 4.6, build per architecture, package dependent shared libraries, and gate the roadmap with model/init/assemble/track smoke tests on WSL2 and the exact Jetson.
5. **Unbounded latency or concurrent solver mutation** — use one serialized owner and latest-only queue, report latency percentiles/deadline misses, and benchmark the reduced model under representative motion.
6. **Stale or failed solutions presented as live** — stop new `JointState` publication, keep diagnostics/status alive with `solution_valid=false`, and never refresh cached timestamps.
7. **Under-observed coordinates and overclaimed validity** — constrain the model/output set, conduct sensitivity and multiple-initial-guess studies, and distinguish software parity, repeatability, biomechanical validity, and clinical validity.

## Implications for Roadmap

Continue numbering after the preserved earlier roadmap. The recommended structure is five dependency-ordered phases.

### Phase 15: Native Runtime and Model Contract

**Rationale:** No streaming work is credible until the deployable OpenSim ABI and the exact model/frame/coordinate contract are proven.

**Delivers:** A pinned OpenSim 4.6 C++20 build recipe and x86-64 smoke test; confirmed target-platform plan; new package scaffold; versioned model/mapping assets; fail-fast frame, coordinate, unit, lock, and output projection validation; synthetic `assemble()`/`track()` proof.

**Addresses:** Model validation, explicit mapping, model/mapping introspection foundation, standard coordinate projection.

**Avoids:** Runtime/ABI surprises, ambiguous names/units, model hot-swap errors, and publishing more coordinates than the declared model contract supports.

**Research flag:** **Required.** Confirm exact Jetson module/JetPack/L4T, intended `.osim`, OpenSim plugins, reduced coordinate set, sensor-frame placement, and ARM64 build/package procedure.

### Phase 16: Orientation Ingress and Pair Integrity

**Rationale:** Calibration and IK can look numerically stable while consuming conventionally wrong or temporally incoherent orientations.

**Delivers:** A frozen quaternion/frame/time contract; full-boundary golden rotations; normalization/antipode/invalid handling; exact or bounded approximate synchronization; QoS, age, skew, duplicate, regression, expiry, and queue counters; evidence on whether shared hardware time/sequence is required.

**Addresses:** Declared quaternion convention, validity gate, timestamp synchronization, freshness, deterministic convention/timing tests.

**Avoids:** Mirrored/inverted motion, NaN poisoning, callback-arrival pairing, excessive synchronizer slop, and silent starvation from QoS mismatch.

**Dependency:** Requires the existing Phase 10 acquisition orientation/timestamp integrity contract or an explicit prerequisite repair.

**Research flag:** **Required.** Firmware/plugin semantics and actual clock/skew behavior remain project-specific.

### Phase 17: Reference-Pose Calibration

**Rationale:** Sensor-to-model offsets are meaningful only after model, mapping, frame, and synchronized-input contracts are fixed.

**Delivers:** Explicit calibration controls and state machine; stable multi-sample capture; heading/global-axis and per-sensor mounting transforms; transactionally activated calibration; model/config/convention-bound artifact; invalidation and held-out validation tests.

**Addresses:** Known-pose capture, heading alignment, calibration state/invalidation, versioned artifact, preview metrics foundation.

**Avoids:** First-frame calibration, moving/unknown pose capture, role swaps, stale calibration reuse, and conflating heading with mounting offsets.

**Research flag:** **Required.** Reference pose, heading method, stability/residual thresholds, remount/reboot semantics, and domain-acceptable model assumptions need hardware and biomechanical input.

### Phase 18: Real-Time IK and Safe ROS Outputs

**Rationale:** The persistent solver and public ROS contract should be integrated only after its inputs and calibration are trustworthy.

**Delivers:** C++ streaming solver with persistent reference/state, `assemble()`/`track()`, single ownership, latest-only queue, bounded recovery, selected coordinates, orientation residuals, timestamped `JointState`, typed IK status, calibration/model metadata, diagnostics heartbeat, launch integration, and fault-injection coverage.

**Addresses:** OpenSense-compatible IK, bounded processing, standard and authoritative outputs, degraded/stale behavior, deterministic recovery, per-observation weights.

**Avoids:** Per-frame batch tools, solver calls in callbacks, concurrent state mutation, unbounded backlog, freshly stamped cached poses, and quality hidden in logs.

**Research flag:** **Targeted only.** Core APIs and ROS patterns are well documented; deeper work is needed only for orientation-error units, final message schema, and measured target deadlines.

### Phase 19: Deterministic, Replay, and Biomechanical Validation

**Rationale:** Passing unit tests proves software behavior, not that two sensors identify the advertised coordinates or that results are valid for rehabilitation use.

**Delivers:** Offline `IMUPlacer`/`IMUInverseKinematicsTool` parity; deterministic rosbag replay; target latency p50/p95/p99/max and drop/deadline results; drift and repeated-pose tests; coordinate sensitivity/observability and multiple-initial-guess study; calibrated accuracy/repeatability report; conservative product claims.

**Addresses:** Replay equivalence, quantified latency, self-test, motion export if core recording is stable, and final evidence for the publishable coordinate subset.

**Avoids:** Low-residual-as-accuracy assumptions, full-body/two-sensor overreach, copied literature accuracy claims, and visually judged acceptance.

**Research flag:** **Required.** The external reference, tasks, duration, coordinate-specific error budget, and clinical/research claim boundary require domain validation and user decisions.

### Phase Ordering Rationale

- Native runtime and model names must be stable before frame math can be tested through the real adapter.
- Convention and timestamp integrity must precede calibration; otherwise calibration can hide systematic frame errors or average incoherent poses.
- Calibration must precede IK publication; identity offsets are not an acceptable degraded mode.
- Interfaces and failure semantics belong with the solver integration so every solution is valid, timestamped, diagnosable, and replayable from its first public release.
- Observability and biomechanical validation come last because they require the complete pipeline, but they are a release gate rather than optional polish.

### Research Flags

Phases likely needing `$gsd-plan-phase --research-phase <N>`:

- **Phase 15:** exact Jetson/JetPack compatibility, ARM64 packaging, chosen model/plugin behavior, and reduced coordinate set.
- **Phase 16:** firmware quaternion direction/world frame, source timestamps, clock relationship, sequence propagation, and actual skew distributions.
- **Phase 17:** calibration pose/protocol, heading basis, stability/residual criteria, and artifact lifecycle.
- **Phase 19:** observability method, reference measurement protocol, task-specific validation, and defensible claims.

Phases with mostly established patterns:

- **Phase 18:** OpenSim streaming APIs, single-owner execution, bounded queues, standard `JointState`, and ROS diagnostics are documented. Research should be limited to measured thresholds and any API detail that fails the Phase 15 spike.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH / MEDIUM on target | OpenSim 4.6 source/release, ROS Humble APIs, Python/architecture package gaps, and JetPack compatibility are primary-source backed. Exact Jetson hardware and build artifact remain unconfirmed. |
| Features | HIGH for contract; MEDIUM for thresholds | OpenSense and ROS directly support the validity, mapping, calibration, synchronization, output, and diagnostics requirements. Product-specific tolerances require measurements. |
| Architecture | HIGH after conflict resolution | ROS process separation, persistent streaming solver, serialized ownership, bounded latest-value flow, provenance, and output boundaries are well supported. The original Python production adapter is rejected for deployment compatibility. |
| Pitfalls | HIGH for failure modes; MEDIUM for acceptance limits | Convention, sync, stale output, runtime, observability, and claim risks are strongly supported. Numeric limits and coordinate-level accuracy are system-specific. |

**Overall confidence:** MEDIUM-HIGH. The recommended software architecture is clear; deployment and measurement acceptance depend on unresolved hardware and biomechanical choices.

### Gaps and Decisions Requiring User Input

- **Exact Jetson hardware:** module/family, RAM/storage, architecture, and whether it can run JetPack 6.x.
- **Exact JetPack/L4T and ROS installation:** native Humble Jammy, container, or source-built environment.
- **Production model contract:** `.osim` file, required plugins, two sensor-to-frame mappings, reference pose, coordinate locks/constraints, published coordinate allowlist, and ROS names.
- **Quaternion contract:** sensor-to-world or world-to-sensor direction, active/passive interpretation, world axes/handedness, firmware fusion/reset behavior, and quality/covariance availability.
- **Time contract:** shared hardware acquisition stamp/sequence versus host receipt time and how reboots/time jumps are represented.
- **Numeric thresholds:** quaternion norm tolerance; pair skew; input age; calibration duration/sample count/dispersion; residual acceptance; target input/output rate; solve deadline; consecutive-failure policy; drift and replay tolerances. These must be derived from captured distributions and target benchmarks, not guessed.
- **Status schema:** one custom `IkStatus` plus low-rate versioned metadata is recommended, but the final calibration/model message split should be selected before interface generation.
- **Validation scope:** target activities, participant/session duration, external reference, coordinate-specific error budget, and the wording of any biomechanical or clinical claims.

## Sources

### Primary (HIGH confidence)

- OpenSim 4.6 release and source — C++20 requirement, build system, streaming orientation reference, IK solver, IMU tools, and calibration implementation: https://github.com/opensim-org/opensim-core/tree/4.6
- OpenSim `BufferedOrientationsReference` and `InverseKinematicsSolver` APIs — live queue, `assemble()`, `track()`, and orientation-error access: https://github.com/opensim-org/opensim-core/blob/4.6/OpenSim/Simulation/BufferedOrientationsReference.h and https://github.com/opensim-org/opensim-core/blob/4.6/OpenSim/Simulation/InverseKinematicsSolver.h
- OpenSense kinematics and calibration documentation — preprocessing assumptions, model IMU frames, reference pose, heading, and orientation IK: https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084203/OpenSense+-+Kinematics+with+IMU+Data
- OpenSim official Conda package matrix — Python and architecture availability: https://anaconda.org/opensim-org/opensim/files
- ROS 2 Humble QoS, `message_filters`, `sensor_msgs/JointState`, and diagnostics documentation: https://docs.ros.org/en/humble/
- NVIDIA JetPack 6.2.1 and Jetson Linux 36.x release documentation — Orin and Ubuntu 22.04 basis: https://docs.nvidia.com/jetson/jetpack/6.2.1/release-notes/index.html
- Repository planning and implementation evidence — `.planning/PROJECT.md`, current launch/package files, and ESP32/OpenSim bridge placeholders inspected 2026-07-27.

### Secondary (MEDIUM confidence)

- Al Borno et al., *OpenSense: An open-source toolbox for inertial-measurement-unit-based measurement of lower extremity kinematics over long durations* (2022) — task-specific validity and drift evidence: https://doi.org/10.1186/s12984-022-01001-x
- Bailey et al., *Validity and Sensitivity of an IMU-Driven Biomechanical Model of Motor Variability for Gait* (2021) — coordinate-dependent error and sensitivity: https://doi.org/10.3390/s21227690
- Slade et al., *An Open-Source and Wearable System for Measuring 3D Human Motion in Real-Time* (2022) — feasibility of real-time OpenSim orientation IK, with system-specific accuracy/latency: https://doi.org/10.1109/TBME.2021.3103201
- OpenSimLive paper — corroborating persistent C++ real-time IK architecture, based on older OpenSim 4.1: https://pmc.ncbi.nlm.nih.gov/articles/PMC10082569/

### Tertiary (LOW confidence)

- None used for roadmap-defining conclusions. All numeric defaults mentioned in the detailed research are provisional until measured on the selected hardware/model.

---
*Research completed: 2026-07-27*
*Ready for roadmap: yes, with explicit Phase 15 platform/model gates*
