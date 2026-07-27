# Feature Research: Real-Time Quaternion-Driven OpenSim IK

**Domain:** Operator-controlled, ROS 2 real-time OpenSense-compatible inverse kinematics
**Milestone:** v1.4 Real-time OpenSim IK
**Researched:** 2026-07-27
**Confidence:** HIGH for OpenSense and ROS contracts; MEDIUM for product-specific thresholds pending hardware validation

## Recommended Product Contract

The bridge should behave as a validity-gated estimator, not as a best-effort angle generator. It may publish a solved sample only when the configured model and sensor mapping are valid, calibration is current, and one acceptable synchronized input set exists. Every solution must remain traceable to its measurement timestamp, model/mapping revision, calibration revision, and quality metrics.

The operator workflow should be:

1. Load a model and mapping; the bridge validates both before becoming calibratable.
2. Confirm that both required IMUs are present, fresh, normalized, and synchronized.
3. Assume the declared reference pose and explicitly request calibration.
4. Review calibration success or actionable rejection reasons.
5. Start IK; monitor joint states and quality/health separately.
6. If input integrity is lost, see a named degraded/stale state; never see an old angle presented as a fresh solution.
7. Recalibrate explicitly after sensor remounting, model/mapping change, or operator reset.

OpenSense explicitly assumes sensor fusion and synchronization have already occurred, associates sensors with model segments as IMU Frames, calibrates offsets against a known/default model pose, and solves joint coordinates by minimizing orientation error. The bridge therefore inherits acquisition integrity as a hard dependency rather than repairing arbitrary upstream defects inside IK.

## Feature Landscape

### Table Stakes (Users Expect These)

Missing any P1 item below makes the IK stream untrustworthy or unusable.

| Feature | Testable requirement | Why expected | Complexity | Notes |
|---------|----------------------|--------------|------------|-------|
| Fail-fast model validation | On startup or model reload, the bridge shall load the configured `.osim`, verify every requested coordinate and IMU frame, and remain `ERROR/not_ready` without publishing solutions if any reference is missing or ambiguous. | IK has no meaningful contract without a known model. | MEDIUM | Report model path, stable model/config identifier, OpenSim version, and exact invalid names. |
| Explicit sensor-to-model mapping | Each input sensor role shall map explicitly to one model IMU Frame/body segment; duplicate, unknown, or incomplete required mappings shall block calibration. | OpenSense relies on sensor/model association and strict frame naming or an equivalent mapping. | MEDIUM | Do not infer a body from topic order. Preserve both ROS input identity and OpenSim frame name in diagnostics. |
| Declared quaternion and frame convention | Configuration shall declare input component order, rotation direction, world convention, sensor frame, and sensor-to-OpenSim axis rotation; fixtures shall prove identity and ±90° rotations. | Quaternion order and active/passive/frame mistakes can produce plausible but wrong motion. | HIGH | ROS stores quaternion fields as `x,y,z,w`; convert once at the boundary into the documented internal convention. |
| Quaternion validity gate | A sample shall be rejected if any component is non-finite, its norm is below a safe minimum, or its norm error exceeds a configured tolerance; acceptable near-unit inputs may be normalized and counted. | The solver assumes valid orientations. | LOW | Include accepted-normalization and rejection counters per sensor. Handle quaternion sign equivalence (`q` and `-q`) in tests. |
| Timestamp-based paired synchronization | The bridge shall solve only from one master/slave set whose measurement timestamps differ by no more than configured `max_pair_skew`; unmatched samples shall expire after a bounded queue/window. | OpenSense assumes synchronized orientation data; a joint angle from different instants is not a coherent observation. | MEDIUM | Use header measurement time, not callback arrival time. ROS `message_filters` warns that arrival-time synchronization is unpredictable. QoS must be compatible across inputs. |
| Freshness and acquisition-integrity gate | A synchronized pair shall also satisfy maximum input age and monotonic-time rules; duplicate, regressed, stale, and dropped/expired samples shall be diagnosed and excluded. | IK cannot restore data that never arrived or arrived with invalid timing. | MEDIUM | Existing acquisition must supply trustworthy timestamps, sensor identity, normalized fused orientation, and comparable time bases. |
| Explicit calibration state machine | The bridge shall expose at least `UNCALIBRATED`, `CALIBRATING`, `READY`, `DEGRADED`, `STALE`, and `ERROR`; IK publication is allowed only from a valid calibration revision. | Operators need to know whether an angle is referenced to the intended pose. | MEDIUM | Calibration must be an explicit service/action or command with success/failure response, not an incidental first callback. |
| Known-pose calibration capture | A calibration request shall collect a configured number/duration of synchronized pairs, reject motion/instability or insufficient data, and compute sensor-to-model orientation offsets against declared model coordinate values. | OpenSense calibration assumes the subject pose matches the model default/declared pose. | HIGH | Store reference-pose name/coordinates, base IMU and heading-axis choice, capture timestamps, quality summary, and mapping/model identifiers. |
| Heading and axis alignment | The bridge shall support a declared base IMU and one of `x,-x,y,-y,z,-z` as heading, or an explicit no-heading mode; the chosen transformation shall be inspectable. | OpenSense exposes heading correction because sensor/world heading can differ from model forward. | MEDIUM | Treat heading correction separately from per-sensor mounting offsets. |
| Calibration invalidation rules | Changing model, coordinate set, sensor mapping, quaternion convention, sensor-to-OpenSim rotation, or reference pose shall invalidate calibration and stop fresh solution publication. | Reusing offsets under changed geometry silently corrupts results. | MEDIUM | Sensor remount cannot be detected reliably; provide a deliberate operator reset/recalibrate control and document it. |
| OpenSense-compatible orientation IK | For each accepted pair, the solver shall update the model coordinates selected in configuration to minimize weighted orientation error between experimental orientations and calibrated model IMU Frames. | This is the defining OpenSense IK behavior. | HIGH | Use the previous accepted state as the next initial guess where supported, while deterministic reset behavior remains testable. Coordinate locks/constraints come from the model/config. |
| Bounded real-time processing | Input queues shall be bounded and the solver shall prefer the newest valid sample over accumulating latency; publish processing time, end-to-end age, achieved rate, deadline misses, and dropped-pair counts. | “Real-time” for operator feedback means bounded age, not eventual processing of every sample. | HIGH | Establish numeric rate/latency acceptance thresholds on target hardware during validation; do not claim hard real-time without evidence. |
| Standard joint-state projection | Each accepted solution shall publish `sensor_msgs/msg/JointState` with the synchronized measurement timestamp, stable configured ROS joint names, and positions in radians (or metres for prismatic coordinates); optional arrays shall be empty unless genuinely computed. | ROS and rosbridge consumers expect standard, timestamped joint positions. | MEDIUM | Maintain an explicit 1:1 mapping from each published scalar ROS joint name to an OpenSim coordinate path. `name` and `position` lengths must match. Never put solver residuals in `effort`. |
| Full solved-state/metadata contract | Alongside `JointState`, publish a typed quality/state message containing solution sequence, measurement time, model/config ID, calibration ID, OpenSim coordinate paths and values, input sensor stamps, pair skew, input age, solve duration, aggregate/per-sensor orientation error, and validity/state reason. | `JointState` cannot carry provenance or solver quality, yet those are required for safe interpretation and later OpenSim visualization. | HIGH | This message is the authoritative biomechanics stream; `JointState` is the interoperable projection. Keep schema versioned and rosbridge-safe. |
| ROS diagnostics and heartbeat | Publish `diagnostic_msgs/DiagnosticArray` (prefer `diagnostic_updater`) with `OK/WARN/ERROR/STALE`, actionable text, and key/value counters for inputs, sync, calibration, solver, output rate, latency, and last-success age. | Operators must distinguish no data, bad data, bad calibration, and solver failure. | MEDIUM | Diagnostics continue at a low heartbeat rate even when no joint state can be published. |
| Explicit degraded/stale behavior | On loss/invalidity of a required IMU, calibration, or solver result, stop publishing fresh solved samples, transition health within a configured timeout, and retain the last value only as explicitly invalid historical state if exposed. | Holding the last angle with a new timestamp creates false live motion. | MEDIUM | Partial-sensor solving is permitted only for a separately validated configuration whose remaining observations make the requested coordinates identifiable; it must be labeled degraded. Default: suppress. |
| Deterministic recovery | After transient input recovery, the bridge shall resume only when it has a new valid synchronized pair and calibration remains applicable; it shall not recalibrate automatically or replay queued stale pairs. | Recovery must not change the biomechanical reference without operator knowledge. | MEDIUM | Flush synchronization queues on time reset, model reload, calibration, and lifecycle restart. |
| Deterministic local verification | Tests shall cover convention fixtures, mapping failures, known reference-pose calibration, known rotations with expected coordinates, synchronization boundaries, invalid quaternions, stale/dropout transitions, solver failure, and exact output stamps/names/units. | The Jetson is disconnected and the highest-risk errors are deterministic convention/contract errors. | HIGH | Provide a synthetic ROS publisher or direct fixture harness; use seeded/no-random golden data and tolerances. Include rosbag replay once the message boundary is stable. |

### Differentiators (Competitive Advantage)

These improve confidence and operator efficiency after the table-stakes contract is stable.

| Feature | Value proposition | Testable requirement | Complexity | Notes |
|---------|-------------------|----------------------|------------|-------|
| Calibration preview and acceptance gate | Prevents “calibrated” from meaning merely “the math returned.” | Report capture stability, per-sensor offset, heading correction, and reference-pose residual; accept only below configured thresholds and require operator retry otherwise. | HIGH | Thresholds require real hardware evidence. |
| Versioned calibration artifact | Makes sessions reproducible and auditable. | Serialize calibration with schema version, model/config hash, mapping, conventions, offsets, pose, timestamp, and quality; reject an artifact whose identifiers do not match current configuration. | MEDIUM | Loading an artifact should be explicit and visible, not silent startup magic. |
| Model/mapping introspection report | Catches configuration errors before a participant is instrumented. | Provide a dry-run command/service listing model coordinates, locks/constraints, IMU frames, requested outputs, unresolved mappings, and units without requiring live sensors. | MEDIUM | Especially valuable for custom `.osim` models. |
| Per-observation weighting | Allows known weaker sensors/segments to influence the fit less without hiding them. | Accept configured orientation weights, expose effective weights, and verify that zero-weight observations do not affect a fixture solution. | MEDIUM | Never adjust weights silently from residuals in the MVP. Adaptive weighting needs separate validation. |
| Replay equivalence | Makes failures reproducible locally and across target hardware. | Given the same model, calibration artifact, configuration, and ordered input pairs, online and replay modes shall produce coordinate values equal within declared tolerance and identical state transitions. | HIGH | Stronger than a visual “looks right” test. |
| Quantified latency budget | Turns “real-time” into an enforceable operational target. | Publish percentile-ready stage timings and flag WARN/ERROR when configured age or solve deadlines are exceeded for a defined consecutive count. | MEDIUM | Separate input age, queue wait, solve time, and publish time. |
| OpenSim motion export from accepted solutions | Enables immediate offline inspection in the OpenSim GUI without building 3D into this milestone. | Optionally record authoritative coordinate paths/values and timestamps into an OpenSim-compatible motion artifact while preserving the same model/calibration identifiers. | MEDIUM | Add only after live correctness and existing recording semantics are stable. |
| Calibration/solver self-test command | Gives operators a fast pre-session confidence check. | Run bundled known-pose fixtures and report pass/fail without hardware or user code execution. | MEDIUM | Complements, not replaces, participant-specific calibration. |

### Anti-Features (Explicitly Do Not Build)

| Anti-feature | Why it seems attractive | Why problematic | Recommended alternative |
|--------------|-------------------------|-----------------|-------------------------|
| Embedded/native OpenSim 3D visualization | Makes the milestone visually impressive. | Expands scope before the numerical contract is trustworthy and couples solver work to rendering. | Publish model-aware, timestamped solved-state metadata and defer the viewer. |
| “Calibrate from the first sample” automatically | One-click startup. | The first sample may be moving, unsynchronized, stale, or in the wrong pose; it silently changes the reference. | Explicit multi-sample calibration with stability and pose checks. |
| Guess quaternion order, handedness, or rotation direction | Reduces configuration. | Wrong guesses often yield plausible motion and are hard to detect. | Require declared conventions and verify with canonical rotation fixtures. |
| Synchronize on callback arrival time | Easy when clocks are awkward. | Network and executor jitter make arrival-time pairing unpredictable and non-reproducible. | Repair the upstream timestamp/time-base contract and pair on measurement stamps. |
| Interpolate across arbitrary gaps | Keeps output visually smooth. | Creates invented biomechanical observations and can hide packet loss. | Permit only bounded, explicitly configured interpolation after empirical validation; otherwise suppress and diagnose. |
| Publish last-good angles with a current timestamp | Avoids a frozen UI or empty topic. | Misrepresents stale estimates as live data. | Preserve original timestamp and mark invalid/stale in the quality stream, or stop solution publication. |
| Clamp implausible solutions silently | Produces tidy graphs. | Hides model, mapping, calibration, or solver errors and changes the estimator output. | Respect model constraints in the solver; diagnose residual/limit violations and reject if necessary. |
| Implicit partial-sensor fallback | Appears resilient to dropout. | Two-sensor observability is already limited; removing one may make requested coordinates underdetermined while still returning numbers. | Default to no solution; enable only an explicitly modeled, tested degraded profile. |
| Unbounded reliable queues | Avoids losing any sample. | Backlog converts packet loss or slow solving into growing latency; old motion is not useful real-time feedback. | Bounded sensor-data QoS/queues, latest-valid processing, and explicit drop/deadline metrics. |
| Hot-swap models without stopping or recalibrating | Fast experimentation. | Existing offsets and coordinate mappings become invalid midstream. | Atomic stop → validate → invalidate calibration → recalibrate → restart sequence. |
| Put all quality fields into `JointState` | Avoids a custom message. | Standard fields have defined units/semantics and cannot express provenance, validity, residuals, or calibration. | Standard `JointState` plus a versioned typed quality/state message and diagnostics. |
| Treat IK output as a clinical measurement guarantee | Encourages immediate use in rehab decisions. | Software correctness alone does not establish biomechanical or clinical validity for a sensor placement, model, or population. | Label outputs as estimates and conduct a separate validation study against reference measurements. |
| Add inverse dynamics, muscle forces, or Moco “inverse” | “Inverse” sounds like the next part of IK. | These solve different problems and require additional inputs/assumptions; they are not needed for quaternion-to-kinematics. | Keep v1.4 strictly orientation IK and expose clean kinematics for future analyses. |

## Feature Dependencies

```text
Existing acquisition integrity
  (stable sensor identity + fused unit quaternions + trustworthy comparable stamps)
    -> quaternion/frame boundary validation
    -> bounded timestamp synchronization + freshness gate
        -> explicit known-pose calibration
            -> calibrated model + calibration revision
                -> OpenSense-compatible real-time IK
                    -> authoritative solved-state + quality
                    -> standard JointState projection
                    -> diagnostics/health
                    -> later recorder and 3D visualization

Model + requested coordinate set + sensor-to-model mapping
    -> startup/dry-run validation
    -> calibration eligibility
    -> output-name/coordinate mapping

Deterministic fixtures
    -> convention verification
    -> calibration verification
    -> known-pose IK verification
    -> dropout/recovery contract verification

Model/mapping/convention change
    -> invalidates calibration
    -> suppresses new solutions until recalibrated
```

### Dependency Notes

- **Acquisition integrity is upstream, not optional:** OpenSense documentation assumes fusion and synchronization are already performed. The bridge may normalize a near-unit quaternion and pair samples within a declared skew, but it should not repair unidentified sensors, broken clocks, arbitrary gaps, or unfused raw inertial data.
- **Calibration requires a validated mapping and pose:** Offsets only have meaning for a specific sensor placement, model IMU Frame, coordinate convention, and reference pose.
- **IK requires calibration:** Starting a solver with identity offsets is not a degraded mode; it is an uncalibrated estimate and must be blocked.
- **Standard output requires an explicit projection:** OpenSim coordinates and ROS joint names are not automatically interchangeable, especially for multi-coordinate joints. Define the mapping once and publish its revision.
- **Visualization compatibility depends on provenance:** A future viewer needs the same model/config identifier, coordinate paths, calibration identifier, timestamps, and units—not only a flat array of angles.
- **Diagnostics must not depend on solutions:** Health must continue publishing when IK cannot.

## Acceptance-Oriented System Behaviors

| Given | When | Then |
|-------|------|------|
| Valid model/mapping, no calibration | synchronized IMUs arrive | health reports `UNCALIBRATED`; no valid solved sample is published |
| Operator is in a stable declared pose | calibration is requested with enough valid pairs | one new calibration revision is accepted and state becomes `READY` |
| Motion exceeds calibration stability threshold | calibration is requested | request fails with an actionable reason; previous valid calibration remains active only if configuration is unchanged |
| Pair skew equals the configured limit | both samples are fresh | behavior is defined inclusively and tested; one solution carries the chosen pair measurement timestamp |
| Pair skew exceeds the limit | messages arrive | no solution is produced; unmatched/expired counters and WARN state update |
| One quaternion is NaN, zero-norm, or grossly non-unit | its pair arrives | pair is rejected and the named sensor/reason appears in diagnostics |
| One required sensor stops | stale timeout elapses | no newly stamped `JointState` is emitted; state becomes `STALE` or `DEGRADED` per explicit configuration |
| Solver throws, fails to converge, or returns non-finite coordinates | a valid pair is processed | result is rejected; last-success age and solver-error counter advance; node remains observable |
| Input resumes after a short dropout | a new valid pair arrives | queues contain no pre-dropout sample; solving resumes under the same still-valid calibration without auto-recalibration |
| Mapping/model/convention parameter changes | reload is requested | publication stops atomically, configuration is revalidated, calibration is invalidated, and recalibration is required |
| A consumer joins through rosbridge | valid solutions are active | it receives standard joint state and typed quality/diagnostic JSON without relying on OpenSim-native bindings |

## MVP Definition for v1.4

### Launch With (P1)

- [ ] Validated model, coordinate selection, and explicit two-IMU-to-model mapping.
- [ ] Documented quaternion/frame conversion with deterministic canonical fixtures.
- [ ] Bounded timestamp synchronization, freshness checks, invalid-input rejection, and acquisition counters.
- [ ] Explicit stable known-pose calibration, heading correction, calibration invalidation, and operator-visible state.
- [ ] OpenSense-compatible weighted orientation IK with bounded latest-sample processing.
- [ ] Standard timestamped `JointState` plus a typed authoritative solved-state/quality message.
- [ ] Continuous ROS diagnostics with unambiguous uncalibrated, ready, degraded/stale, and error behavior.
- [ ] Deterministic local tests for known poses, rotations, timing edges, dropouts, failures, and recovery.

### Add After Core Validation (P2)

- [ ] Versioned calibration save/load after artifact compatibility rules are proven.
- [ ] Dry-run model/mapping introspection command for custom models.
- [ ] Calibration preview with empirically chosen stability/residual thresholds.
- [ ] Rosbag replay equivalence and OpenSim-compatible motion export.
- [ ] Configurable per-sensor weights and deadline-warning policy.

### Future Consideration (P3)

- [ ] 3D visualization consuming the authoritative model/coordinate/calibration contract.
- [ ] Validated partial-sensor degraded profiles, only if requested coordinates remain observable.
- [ ] Adaptive sensor weighting, drift correction, or advanced calibration methods backed by a validation dataset.
- [ ] Additional IMUs and whole-body models after the paired-sensor path is verified.
- [ ] Inverse dynamics, muscle analysis, or clinical validation as separate milestones.

## Feature Prioritization Matrix

| Feature group | User value | Implementation cost | Priority |
|---------------|------------|---------------------|----------|
| Model/mapping/convention validation | HIGH | MEDIUM | P1 |
| Synchronization and freshness gate | HIGH | MEDIUM | P1 |
| Explicit known-pose calibration | HIGH | HIGH | P1 |
| Real-time orientation IK | HIGH | HIGH | P1 |
| Standard + authoritative outputs | HIGH | HIGH | P1 |
| Degraded-state diagnostics | HIGH | MEDIUM | P1 |
| Deterministic local fixture suite | HIGH | HIGH | P1 |
| Calibration artifact and preview | MEDIUM | MEDIUM/HIGH | P2 |
| Replay and motion export | MEDIUM | MEDIUM | P2 |
| Partial-sensor estimation | LOW until validated | HIGH | P3 |
| Embedded 3D visualization | DEFERRED | HIGH | P3 |

## Ecosystem Comparison

| Capability | OpenSense offline workflow | OpenSenseRT reference system | Recommended ROS 2 bridge |
|------------|----------------------------|-----------------------------|--------------------------|
| Sensor preparation | Assumes fusion, sync, and preprocessing are already done | Integrated hardware/software arrangement | Consume existing fused ROS IMUs but enforce timestamp, freshness, and validity gates |
| Sensor/model association | IMU naming/mapping to OpenSim IMU Frames | Settings map ports to body segments | Explicit topic/sensor-role → OpenSim frame → published-coordinate mapping |
| Calibration | Calibration orientation data matched to model default/declared pose; optional base heading | User begins each recording in a default pose | Explicit multi-sample service/action, stability gate, revision, diagnostics, and invalidation |
| IK | Minimizes model-versus-experimental IMU orientation error | Computes wearable real-time kinematics | Same orientation objective in a bounded, stateful ROS node |
| Output | OpenSim motion/model artifacts | Saved raw data, kinematics `.mot`, timestamps | Typed live solved state, `JointState`, diagnostics; optional `.mot` only after validation |
| Failure visibility | Primarily tool/file errors and troubleshooting | LED/basic operational workflow | Continuous reason-coded health, counters, timestamps, residuals, and latency |
| Later visualization | OpenSim GUI loads model and motion | Saved files visualized in OpenSim | Preserve model/config ID, OpenSim coordinate paths, units, and timestamps for a future viewer |

## Sources

- OpenSim, **OpenSense - Kinematics with IMU Data** (updated 2024-08-27): workflow, preprocessing assumptions, model/IMU mapping, calibration, and orientation-error IK. https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084203/OpenSense+-+Kinematics+with+IMU+Data
- OpenSim, **How IMU Placer Works** (updated 2024-03-22): calibration offsets, reference pose assumption, and heading correction. https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53086387/How+IMU+Placer+Works
- OpenSim, **IMU Placer Settings File and XML Tag Definitions**: strict sensor/frame naming, sensor-to-OpenSim rotations, base IMU, and heading-axis choices. https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53112999/IMU+Placer+Settings+File+and+XML+Tag+Definitions
- OpenSim, **Wearable and Real-time Kinematics Estimates with OpenSense** (updated 2024-03-22): configurable segments, reference-pose operation, real-time/offline modes, and OpenSim motion output. https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084280/Wearable+and+Real-time+Kinematics+Estimates+with+OpenSense
- ROS 2 `message_filters`: exact/approximate timestamp synchronization, bounded queue, skew (`slop`), and warning against arrival-time synchronization. https://docs.ros.org/en/ros2_packages/rolling/api/message_filters/message_filters.html
- ROS 2 Approximate Time Synchronizer tutorial: matching QoS requirement for synchronized subscribers. https://docs.ros.org/en/ros2_packages/jazzy/api/message_filters/doc/Tutorials/Approximate-Synchronizer-Cpp.html
- ROS 2 `sensor_msgs/msg/JointState`: shared measurement timestamp, radians/metres, and equal-or-empty array rules. https://docs.ros.org/en/ros2_packages/humble/api/sensor_msgs/msg/JointState.html
- ROS 2 `diagnostic_msgs/msg/DiagnosticStatus`: standard `OK`, `WARN`, `ERROR`, and `STALE` levels. https://docs.ros.org/en/iron/p/diagnostic_msgs/interfaces/msg/DiagnosticStatus.html
- ROS 2 `diagnostic_updater`: periodic component diagnostics and diagnosed publisher support. https://docs.ros.org/en/ros2_packages/kilted/api/diagnostic_updater/
- ROS 2 QoS documentation: sensor-data profile favors timely latest readings with best effort and a smaller queue; publisher/subscriber compatibility rules. https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html
- ROS 2 `geometry_msgs/Quaternion`: field order `x, y, z, w`. https://docs.ros.org/en/hydro/api/geometry_msgs/html/msg/Quaternion.html

## Confidence and Open Decisions

- **HIGH:** The need for pre-synchronized fused orientations, explicit IMU/model registration, reference-pose calibration, heading correction, and orientation-error IK is directly documented by OpenSim.
- **HIGH:** `JointState`, ROS diagnostic levels, timestamp synchronizers, and bounded sensor QoS semantics are directly documented by ROS.
- **MEDIUM:** Numeric tolerances for quaternion norm, calibration stability/residual, maximum pair skew, maximum input age, target rate, and latency deadlines must be selected from the actual ESP32 rate/jitter and target OpenSim model performance. The requirement is to configure, expose, and test them—not to guess universal values.
- **Decision needed before implementation:** canonical input rotation semantics/world convention; exact `.osim` model; required IMU Frames; selected coordinates; ROS-name projection; reference-pose coordinate values; target solve rate/latency; and whether the authoritative quality contract is one custom message or a small versioned message family.

---
*Feature research for: v1.4 Real-time OpenSim IK*
