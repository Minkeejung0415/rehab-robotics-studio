# Pitfalls Research

**Domain:** Real-time quaternion-driven OpenSim/OpenSense-compatible IK in ROS 2
**Researched:** 2026-07-27
**Confidence:** HIGH for OpenSense/ROS contracts; MEDIUM for numerical thresholds until measured on the target model and hardware

## Recommended Prevention Phases

The roadmap should continue numbering after the existing phases and preserve this dependency order:

1. **Phase 15 — OpenSim Runtime and Model Contract:** pin and prove the OpenSim environment; validate the model, component paths, coordinate projection, mappings, and units.
2. **Phase 16 — Orientation Ingress and Pair Integrity:** define quaternion semantics once; validate, normalize, canonicalize, synchronize, age, and diagnose both inputs.
3. **Phase 17 — Reference-Pose Calibration:** implement a bounded, stable capture; derive sensor-to-model transforms; version and validate the resulting artifact.
4. **Phase 18 — Real-time IK and Safe ROS Outputs:** give one worker ownership of OpenSim state, bound backlog and latency, publish quality and health, and fail closed on stale/failed solutions.
5. **Phase 19 — Deterministic and Biomechanical Validation:** compare live and offline results, exercise known rotations and recorded motion, quantify repeatability/drift/accuracy, and constrain product claims.

Phase 16 should depend on the existing Phase 10 orientation/timestamp integrity contract. Phase 19 is not optional polish: it is what distinguishes a functioning numerical pipeline from a valid measurement pipeline.

## Critical Pitfalls

### Pitfall 1: Correct numbers interpreted with the wrong quaternion convention

**What goes wrong:**
A stream remains finite and smooth but produces mirrored motion, inverted flexion, swapped axes, or a constant 90°/180° error. Common mismatches are ROS field order `(x,y,z,w)` versus scalar-first library constructors, active versus passive rotation, sensor-to-world versus world-to-sensor direction, and ROS/OpenSim axis or handedness assumptions. Calibration can absorb a constant mistake and make the reference pose look correct while dynamic rotations remain wrong.

**Why it happens:**
“Quaternion” does not fully specify component order or frame semantics. `geometry_msgs/Quaternion` fixes field order but does not declare what frames the rotation maps. OpenSense separately requires a sensor-coordinate-to-OpenSim transformation and associates orientations with named model IMU Frames.

**How to avoid:**
- Write one boundary contract using explicit notation, for example `R_GS` = rotation that expresses sensor-frame vectors in OpenSim ground.
- Convert ROS fields to the OpenSim/SimTK constructor in one adapter only. Do not pass four-element arrays between layers.
- Define every multiplication direction and handedness in code comments, configuration schema, model metadata, and calibration artifact.
- Test identity and positive/negative 90° rotations about each sensor axis. Verify the resulting rotation matrix, calibrated model IMU Frame, and expected model coordinate sign—not only round-trip quaternion equality.
- Keep global sensor-to-OpenSim axes separate from per-sensor mounting offsets and heading correction.

**Warning signs:**
Reference pose fits but motion about X changes a Y/Z coordinate; left and right motion are mirrored unexpectedly; an inverse/conjugate “fix” appears in several files; results depend on whether calibration occurred before or after an axis conversion.

**Phase to address:**
Phase 16, with a model-frame integration test repeated in Phase 17.

---

### Pitfall 2: Treating raw quaternion samples as ordinary four-vectors

**What goes wrong:**
Zero-norm, NaN, Inf, or grossly non-unit inputs poison calibration or the solver. Averaging or interpolating antipodes `q` and `-q` can collapse toward zero or take the long path even though they represent the same physical rotation. Sign flips can also create false angular-velocity spikes in diagnostics.

**Why it happens:**
Unit quaternions live on a sphere and have a double cover: `q` and `-q` represent the same rotation. Component-wise filtering and arithmetic ignore both properties.

**How to avoid:**
- Reject non-finite and near-zero-norm inputs; reject gross norm errors and only normalize within a documented tolerance.
- Before averaging, interpolation, or differencing, choose a hemisphere relative to the previous/reference quaternion (`if dot(q, q_ref) < 0, use -q`).
- Use a rotation-aware mean for calibration and an angular distance such as `2*acos(clamp(abs(dot(q1,q2)),0,1))`.
- Count normalization, antipode corrections, and invalid rejections per sensor.
- Preserve the original measurement timestamp after normalization; normalization is not a new measurement.

**Warning signs:**
Quaternion component plots jump sign while the device is still; calibration mean norm approaches zero; sporadic 360° jumps appear; invalid samples cause all later outputs to become NaN.

**Phase to address:**
Phase 16; deterministic regression coverage belongs in Phase 19 and should also satisfy existing Phase 10 antipode/normalization requirements.

---

### Pitfall 3: Calibrating an unknown or moving reference pose

**What goes wrong:**
Sensor-to-segment offsets, heading, or model default coordinate errors become baked into every joint angle. A single noisy first frame makes results session-dependent. Reusing a calibration after a sensor moves, the model changes, or roles are swapped yields plausible but invalid kinematics.

**Why it happens:**
OpenSense's basic calibration registers orientation data to the model's declared/default pose. It estimates orientation relationships, not sensor position, model scale, or anatomical landmarks. Operators may not reproduce the assumed pose precisely, and soft-tissue-mounted sensors can shift.

**How to avoid:**
- Capture a bounded window of synchronized pairs, not “the next sample.”
- Require stillness/low dispersion, sufficient samples, fresh streams, expected sensor identities, and an explicit reference-pose coordinate set.
- Compute and retain separate global-axis/heading and per-sensor mounting transforms.
- Store model hash, mapping/config hash, sensor roles and frame IDs, capture time, software version, sample count, dispersion, reference pose, and transforms in an immutable calibration artifact.
- Invalidate calibration on model/mapping/frame-ID changes or explicit sensor-remount events.
- Verify calibration on held-out reference-pose samples and one non-reference known pose; do not accept solely because the calibration samples fit.

**Warning signs:**
Every recalibration changes neutral angles materially; neutral fits but a 90° fixture does not; calibration succeeds while the subject moves; swapping master/slave topics still yields “valid” output; an old calibration loads against a different model.

**Phase to address:**
Phase 17.

---

### Pitfall 4: Pairing by callback arrival instead of measurement time

**What goes wrong:**
Master and slave orientations from different physical instants are solved as one pose. The error grows during fast motion and may look like joint overshoot, phase lag, or solver instability. Large approximate-sync windows conceal clock errors; overly small windows silently starve the solver. Incompatible ROS QoS can prevent pairing entirely.

**Why it happens:**
Wi-Fi, TCP/UDP, ROS executors, and rosbridge introduce variable delay. OpenSense assumes synchronization has already occurred. ROS `message_filters` uses header stamps and explicitly warns that arrival-time/headerless synchronization is unpredictable; its subscribers also need compatible QoS.

**How to avoid:**
- Use device acquisition time propagated into `header.stamp`; never silently replace it with callback or solve time.
- Validate each sensor's timestamp monotonicity, clock epoch, sequence gaps, duplicates, and backward jumps before pairing.
- Use exact or bounded approximate matching with configurable maximum skew and queue age derived from measured hardware distributions.
- Expire unmatched samples and publish pair/drop/skew/age counters and percentiles.
- Use compatible sensor-data QoS on both publisher/subscriber paths and test it with the actual launch graph.
- Stamp outputs with the paired observation time (and report both source stamps), not publication time.

**Warning signs:**
Angles worsen with movement speed; pair skew clusters at the configured maximum; output pauses despite visible input topics; timestamps jump after device reboot; changing network load changes the joint trajectory.

**Phase to address:**
Phase 16, dependent on existing Phase 10 timestamp integrity.

---

### Pitfall 5: Assuming calibration removes orientation drift and mounting artefact

**What goes wrong:**
Heading or relative orientation slowly changes, magnetic disturbances create abrupt yaw errors, and strap/skin motion changes the effective sensor-to-segment transform. IK can redistribute those errors into anatomically plausible coordinates, so a smooth trajectory is not proof of stability.

**Why it happens:**
OpenSense consumes already-fused orientations; it is not itself the sensor-fusion or drift-correction layer. Published accuracy depends on the fusion algorithm, magnetic environment, activity, placement, model, and calibration protocol. Some validated workflows show low drift under their tested conditions, but those results do not transfer automatically to this ESP32 system.

**How to avoid:**
- Expose upstream fusion status, reset/reboot events, orientation covariance/quality when available, and elapsed time since calibration.
- Run static pre/post checks and repeated-pose checkpoints; measure angular and joint-coordinate drift over the intended session duration.
- Detect discontinuities and sustained per-sensor orientation residual increases; mark quality degraded rather than silently recalibrating.
- Define an operator remount/recalibrate workflow and record calibration revisions.
- Characterize magnetic/no-magnetic operation on the actual hardware and lab environment before choosing thresholds.

**Warning signs:**
Neutral pose does not return to baseline; errors grow with elapsed time; yaw changes near equipment; one sensor residual shifts after strap adjustment; restarting the ESP32 changes orientation without a calibration state change.

**Phase to address:**
Instrumentation in Phases 16–18; acceptance limits and claims in Phase 19.

---

### Pitfall 6: Solving more coordinates than two orientations can observe

**What goes wrong:**
The solver returns a unique-looking answer that is driven by model constraints, coordinate priors, initial state, or numerical regularization rather than measurements. Uninstrumented segments and coupled multi-axis coordinates can move without enough independent information. Low residual can coexist with wrong joint angles.

**Why it happens:**
Orientation IK minimizes disagreement between measured and model IMU Frames subject to model constraints; it does not make unobserved degrees of freedom measurable. Two sensor orientations provide limited independent information, and calibration/model assumptions consume some of that information.

**How to avoid:**
- Declare the intended body chain, coordinate subset, locks, constraints, priors, and sensor weights explicitly.
- At startup, resolve every required sensor frame and coordinate; fail on missing/duplicate mappings.
- Perform a numerical observability/sensitivity study around representative poses: perturb each published coordinate and inspect whether the sensor orientation residual changes independently.
- Publish only coordinates that are justified by the sensor/model arrangement. Mark model-constrained or inferred values in metadata.
- Test multiple initial guesses and slow trajectories for solution dependence; large variation signals ambiguity.

**Warning signs:**
Different initial states yield different angles with similar residual; coordinates move on segments with no sensor influence; adding a weak prior changes results substantially; the solver reports good fit at impossible known poses.

**Phase to address:**
Model contract in Phase 15; observability and publication decision in Phase 19.

---

### Pitfall 7: Discovering OpenSim ABI/runtime incompatibility only on launch

**What goes wrong:**
The ROS node imports on a developer workstation but fails on the target because the Python ABI, architecture, native shared-library path, OpenSim version, model/plugins, or ROS environment differs. Worse, it starts with a different OpenSim version and produces non-reproducible behavior.

**Why it happens:**
OpenSim's Python interface wraps native C++ libraries. Official installation guidance varies by OpenSim version and platform; manual installations can require `PATH`, `LD_LIBRARY_PATH`, or a source build. ROS Python and OpenSim package constraints may not align automatically.

**How to avoid:**
- Select and pin one OpenSim distribution/version, Python version, OS/architecture, and installation method after a target compatibility spike; do not use unpinned `pip install opensim`.
- Add a startup self-test that reports `GetVersionAndDate()`, loads the configured model, resolves frames/coordinates, initializes the system, constructs the orientation IK solver, and solves a synthetic identity/reference pose.
- Keep the pure ROS node testable with a fake solver adapter so local CI does not pretend to test native OpenSim.
- Add a separate native-runtime smoke test in the deployment environment and document shared-library requirements.
- Reject calibration artifacts created by incompatible model/config versions.

**Warning signs:**
`ImportError`/missing DLL or `.so`; crashes during model initialization; the package works only in an interactive Conda shell; launch and unit tests use different Python interpreters; model plugins are silently absent.

**Phase to address:**
Phase 15, before live-stream implementation.

---

### Pitfall 8: Running OpenSim in subscription callbacks or concurrently

**What goes wrong:**
Solver work blocks ROS callbacks, sync queues grow, diagnostics stop, latency becomes unbounded, and outputs represent old motion. A multithreaded executor can concurrently mutate one OpenSim `Model`, `State`, reference buffer, or solver, creating races or native crashes. Processing every queued sample after overload preserves throughput statistics while destroying real-time behavior.

**Why it happens:**
OpenSim calculations operate on mutable `State`; `InverseKinematicsSolver.track()` is efficient only when the model/goals remain unchanged and the state is already near a valid assembled solution. Native calls can have variable latency and are tempting to place directly in a callback.

**How to avoid:**
- Give one dedicated worker thread sole ownership of the model, state, live orientation reference, and solver.
- Subscription callbacks only validate/pair and place the newest pair into a bounded latest-value slot (or very small queue).
- Call `assemble()` for initialization/reset and `track()` sequentially for accepted nearby states; rebuild/reset after model/calibration changes or tracking failure.
- Measure queue wait, solve time, end-to-end age, deadline misses, resets, exceptions, and output rate.
- Drop superseded samples under overload and declare degraded/stale state; never accumulate an unbounded backlog.
- Benchmark worst-case representative motion on target hardware and set a deadline below the freshness budget, not merely below average sample period.

**Warning signs:**
Input frequency is healthy but output age grows; stopping motion causes the output to “catch up”; diagnostics freeze during solves; failures are load-dependent; native crashes appear only with a multithreaded executor.

**Phase to address:**
Phase 18.

---

### Pitfall 9: Treating display labels as a stable model-coordinate contract

**What goes wrong:**
The wrong coordinate is published under a plausible ROS joint name, radians are mistaken for degrees, translational coordinates are treated as angular, or a model update silently reorders outputs. Downstream GUI or future visualization animates the wrong joint.

**Why it happens:**
OpenSim coordinates have model component paths, names, motion types, locks, constraints, and defaults; ROS `JointState` supplies only parallel name/value arrays. Short names can collide and array order is not a durable identity.

**How to avoid:**
- Configure an explicit one-to-one mapping from stable ROS joint name to absolute OpenSim coordinate component path.
- Validate existence, uniqueness, motion type, lock/constraint state, and allowed publication set at startup.
- Publish angular positions in radians and translational positions in metres as required by `JointState`; leave velocity/effort empty unless truly computed.
- Publish model/config hash and coordinate metadata on a latched/transient-local model-info topic.
- Keep names and positions equal length and deterministic, but require consumers to join by name, not index.

**Warning signs:**
Values differ by about 57.3; duplicate short coordinate names exist; changing the `.osim` changes array order; locked coordinates are advertised as measurements; GUI code uses `position[0]`.

**Phase to address:**
Phase 15 contract, enforced at publication in Phase 18.

---

### Pitfall 10: Publishing stale or failed solutions as current joint state

**What goes wrong:**
When one IMU stops, synchronization fails, calibration is cleared, or IK throws, the last good angles continue with fresh timestamps. Operators and controllers interpret cached history as current motion. Reconnection can combine a new sensor session with an old calibration or solver state.

**Why it happens:**
Republishing last-known values makes a dashboard look stable. `JointState` has no validity field, and rosbridge consumers may not independently enforce age.

**How to avoid:**
- Define an explicit state machine: `STARTING → UNCALIBRATED → CALIBRATING → READY/TRACKING → DEGRADED/STALE/ERROR`.
- Gate `JointState` on fresh synchronized input, valid calibration, successful solve, finite/in-range coordinates, and age/deadline limits.
- On failure, stop publishing new joint states; continue heartbeat diagnostics and typed IK status with `solution_valid=false` and a reason.
- Never refresh the timestamp of cached angles. Reset synchronization queues and require calibration compatibility after sensor reboot, role/frame change, time jump, or model reload.
- Make downstream consumers test status and source-time freshness, not topic connectivity.

**Warning signs:**
Joint-state timestamps advance while input stamps do not; output persists after one topic is killed; reconnection resumes immediately without identity/calibration checks; the UI says “live” because WebSocket traffic exists.

**Phase to address:**
Phase 18, coordinated with existing Phase 12 freshness semantics.

---

### Pitfall 11: Shipping angles without enough evidence to diagnose them

**What goes wrong:**
There is no way to distinguish input corruption, poor synchronization, bad calibration, unobservable motion, model mismatch, or solver failure. A single “healthy” boolean hides progressive degradation, and recorded joint states cannot be reproduced.

**Why it happens:**
`JointState` cannot carry input provenance, pair skew, solver residuals, calibration identity, or runtime timing. Logging only exceptions misses plausible-but-wrong results.

**How to avoid:**
- Publish a typed IK status containing source stamps, pair skew, input age, solve/queue latency, sequence/drop counters, per-sensor and aggregate orientation error, calibration/model/config IDs, state, validity, and failure reason.
- Publish standard `DiagnosticArray` heartbeat entries for ingress, sync, calibration, solver, output freshness, and runtime version.
- Record raw/filtered IMU messages, calibration events/artifact ID, model metadata, joint states, IK status, and diagnostics together in rosbag2.
- Use OpenSim's current orientation-error APIs where available, but treat residual as fit quality—not ground-truth accuracy.
- Define rate-limited logs plus monotonically increasing counters so intermittent faults remain visible.

**Warning signs:**
Only joint angles are recorded; “solver OK” is true while no new pair arrives; residuals are available only in debug builds; a bad trial cannot be replayed with the same model/calibration.

**Phase to address:**
Phase 18; replay verification in Phase 19.

---

### Pitfall 12: Overclaiming biomechanical or clinical validity

**What goes wrong:**
The bridge is described as “accurate,” “clinical-grade,” or suitable for rehabilitation decisions because known synthetic poses pass or trajectories look smooth. Errors from subject/model scaling, sensor placement, soft-tissue artefact, fusion, calibration, task, axis, and limited observability are ignored. Model constraints can make output plausible without making it true.

**Why it happens:**
Software correctness, OpenSense compatibility, repeatability, concurrent validity against a reference, and clinical validity are different claims. Published OpenSense errors vary by coordinate and task; favorable results from other sensors/protocols do not validate paired ESP32 hardware.

**How to avoid:**
- Initially claim only “OpenSense-compatible orientation IK” and report the exact model, sensors, fusion, calibration, tasks, rates, and tested conditions.
- Separate verification tiers:
  1. algebra/convention fixtures;
  2. synthetic model-generated orientations with known coordinates;
  3. offline OpenSense parity from the same recorded orientations;
  4. repeated don/doff and within-session repeatability;
  5. drift/latency on the intended duration;
  6. concurrent validity against an external reference and a predeclared error budget.
- Report per-coordinate bias, RMSE/MAE, limits of agreement, repeatability, dropout, latency distribution, and failure rate—not one aggregate score.
- Do not infer kinetics, muscle forces, diagnosis, treatment efficacy, or safety-control suitability from orientation IK alone.
- Require domain/research review and an application-specific validation protocol before clinical/research outcome claims.

**Warning signs:**
Acceptance is visual; validation uses the calibration samples; only sagittal flexion is tested but all 3D coordinates are advertised; published literature accuracy is copied into product documentation; residual is labeled “accuracy.”

**Phase to address:**
Phase 19, with conservative terminology enforced from Phase 18 onward.

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Scatter quaternion conversions through ROS, calibration, and solver code | Faster first demo | Convention drift and untestable transforms | Never |
| Use the first frame as calibration | Minimal UI/state | Noise and motion become permanent offsets | Synthetic tests only |
| Infer model frames from topic order or substring names | Less configuration | Silent sensor/body swaps | Never |
| Publish every model coordinate | Rich-looking output | Unobservable/model-imposed values appear measured | Never |
| Process every queued pair | No apparent data loss | Unbounded real-time lag | Offline replay only |
| Put quality in log strings only | Avoid custom interfaces | rosbridge cannot reason about validity; no replayable provenance | Prototype spike only |
| Use unpinned OpenSim/native dependencies | Easy setup | Irreproducible ABI/runtime failures | Disposable exploration only |
| Mutate the checked-in `.osim` during live calibration | Mirrors offline IMU Placer output | Hidden state and unreproducible sessions | Never; export a derived artifact explicitly |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| ESP32/VQF → `sensor_msgs/Imu` | Preserve four values but not direction/frame semantics | Document source/target frames, ROS `(x,y,z,w)` fields, `frame_id`, acquisition timestamp, sequence, and quality |
| ROS `message_filters` | Different QoS or arrival-time synchronization | Matching sensor QoS; synchronize header measurement stamps; bound slop and queue age |
| OpenSense frame mapping | Assume topic labels automatically match model frames | Explicit sensor-role → model IMU Frame mapping, resolved and hashed at startup |
| IMU Placer concept | Expect it to scale the model or locate sensors | Treat calibration as orientation registration only; manage scaling/model suitability separately |
| SimTK/OpenSim quaternion construction | Pass ROS field order positionally | Named adapter plus identity and ±90° matrix fixtures |
| OpenSim live solver | Share one solver/state across executor callbacks | Single-owner worker and bounded latest-pair handoff |
| `JointState` | Use degrees, array indices, or `effort` for residual | Stable names, radians/metres, equal arrays; separate typed IK quality |
| rosbridge | Treat WebSocket traffic as fresh valid biomechanics | Propagate source stamps and validity; consumer enforces age and state |
| rosbag2 replay | Recompute with whichever model/config is installed | Record and verify model/config/calibration hashes and runtime version |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| IK inside subscription callback | Pair drops and frozen diagnostics | Dedicated solver worker | As soon as solve time approaches callback interval |
| Unbounded FIFO | Output increasingly lags real motion | Latest-value slot/small bounded queue; drop superseded pairs | Any sustained solve time above input period |
| Rebuilding model/solver every sample | High jitter and CPU | Initialize once; sequential `track()`; rebuild only on controlled reset | Even at modest IMU rates |
| Optimizing a full complex model for two sensors | Deadline misses and unstable coordinates | Lock irrelevant coordinates; use a model/coordinate subset justified by observability | Model- and hardware-dependent; benchmark before roadmap acceptance |
| Reporting average latency only | Rare dangerous stale frames hidden | p50/p95/p99/max plus deadline-miss count and end-to-end age | Bursty Wi-Fi or difficult poses |
| Unlimited diagnostic/log rate | Solver competes with serialization/I/O | Fixed-rate diagnostics, counter aggregation, rate-limited logs | Fault storms |

No universal safe solver-rate threshold should be copied from literature. Phase 18 must measure the chosen model on the target processor and set input-rate, deadline, and stale limits from the end-to-end freshness budget.

## Security and Integrity Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Accept arbitrary model/calibration paths from ROS parameters or services | Load unintended files or inconsistent artifacts | Resolve against configured roots, validate extensions/hashes, and make runtime model changes an operator-controlled restart |
| Allow remote calibration/reset without operator/session context | Invalidates live measurements unexpectedly | Restrict service exposure, log requester/event where possible, and require explicit state transitions |
| Trust model/config names instead of content | Wrong calibration reused | SHA-256 content IDs for model, mapping, and calibration artifact |
| Treat diagnostics as advisory while consumers use stale `JointState` | Unsafe downstream behavior | Validity/freshness is part of the data contract and consumer tests |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| One green “OpenSim connected” light | Runtime may be loaded while inputs, calibration, or solution are invalid | Separate runtime, pair, calibration, solver, and output-freshness states |
| Auto-calibration with no capture evidence | Operator cannot tell whether pose was stable or sensors were swapped | Explicit capture, countdown/window, role display, quality result, calibration ID |
| Showing frozen angles during faults | Looks like the patient stopped moving | Mark stale prominently and stop updating the biomechanical display |
| Labeling residual as accuracy | False confidence | Call it orientation fit/error and explain that external validation determines accuracy |
| Hiding model and calibration identity | Sessions cannot be compared | Display model/config/calibration IDs and capture time |

## "Looks Done But Isn't" Checklist

- [ ] **Quaternion bridge:** ROS/OpenSim order, direction, axes, and handedness pass identity and ±90° fixtures through the full adapter.
- [ ] **Quaternion validity:** NaN, Inf, zero norm, excessive norm error, and `q/-q` sequences are rejected/canonicalized deterministically with counters.
- [ ] **Synchronization:** asymmetric delays, drops, duplicates, reordering, clock jumps, and incompatible QoS produce bounded, diagnosed behavior.
- [ ] **Calibration:** moving capture, wrong role/frame, insufficient samples, old model hash, and remount/reboot scenarios fail or invalidate cleanly.
- [ ] **Model contract:** every required IMU Frame and coordinate path resolves uniquely with declared motion type and units.
- [ ] **Observability:** each published coordinate has demonstrated sensitivity/justification; model-imposed outputs are identified.
- [ ] **Native runtime:** a clean deployment environment imports OpenSim, reports its version, loads the model, initializes, and solves a synthetic pose.
- [ ] **Real time:** target benchmark reports end-to-end p50/p95/p99/max age, solve time, drop count, and deadline misses under representative motion.
- [ ] **Thread ownership:** no ROS callback or second thread mutates the OpenSim model/state/solver.
- [ ] **Safe failure:** killing either IMU, clearing calibration, forcing a solver exception, or jumping time stops new `JointState` and emits valid stale/error health.
- [ ] **Output contract:** joint names map to absolute coordinate paths; radians/metres and parallel-array rules are verified through rosbridge.
- [ ] **Reproducibility:** rosbag2 plus recorded model/config/calibration IDs reproduces deterministic outputs within a declared tolerance.
- [ ] **Validity:** live results match offline OpenSense for the same inputs before comparison with an external biomechanical reference.
- [ ] **Claims:** documentation distinguishes software verification, OpenSense parity, repeatability, and externally established biomechanical/clinical validity.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Convention error discovered before data collection | LOW | Correct the single adapter; rerun golden fixtures and offline parity |
| Convention error discovered after trials | HIGH | Correct adapter, invalidate calibrations and derived angles, reprocess raw orientation bags if complete; otherwise recollect |
| Bad/remounted calibration | MEDIUM | Stop output, capture a new stable reference, preserve old artifact for audit, restart solver |
| Clock/synchronization defect | MEDIUM–HIGH | Fix timestamp source, characterize skew, replay raw packets if acquisition identity/time was preserved |
| OpenSim runtime mismatch | MEDIUM | Recreate pinned environment, run native smoke test, rebuild/redeploy for target ABI |
| Solver overload | MEDIUM | Reduce/lock coordinate set, latest-sample scheduling, benchmark; never mask it by increasing stale tolerance |
| Stale output consumed downstream | HIGH | Fix producer gating and consumer freshness check; audit sessions/actions that used stale values |
| Unsupported validity claim | HIGH | Retract/narrow claim, define reference protocol, collect representative validation data, report coordinate/task-specific results |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| OpenSim ABI/runtime mismatch | Phase 15 | Clean-environment import/version/model/init/synthetic-solve smoke test |
| Model frame/coordinate naming and units | Phase 15 | Startup schema validation plus known coordinate projection test |
| Quaternion order/frame/handedness | Phase 16 | Full-boundary identity and ±90° axis fixtures with expected matrices/signs |
| Normalization and antipodes | Phase 16 | Invalid corpus and alternating `q/-q` sequence yield identical physical rotations without spikes |
| Timestamp sync/QoS | Phase 16 | Delayed/reordered/drop/clock-jump tests; enforce skew, age, and queue bounds |
| Sensor-to-segment/reference calibration | Phase 17 | Stable multi-sample capture, held-out neutral pose, known non-neutral pose, artifact compatibility tests |
| Drift/remount/fusion resets | Phases 16–19 | Pre/post repeated-pose drift test, reboot/remount invalidation, representative-duration trial |
| Solver latency/threading/backlog | Phase 18 | Target stress benchmark, single-owner test instrumentation, bounded queue and deadline behavior |
| Unsafe stale/failed output | Phase 18 | Kill-topic, calibration-clear, solver-exception, and reconnect tests prove no freshly stamped cached angles |
| Missing observability/quality | Phase 18 | Typed status and diagnostics remain live through every injected fault; bag contains provenance |
| Under-observed coordinates | Phase 19 | Sensitivity/rank and multiple-initial-guess study; publish only justified coordinates |
| Overclaiming biomechanical validity | Phase 19 | Offline parity, repeatability, drift, and external-reference report with coordinate/task-specific error budget |

## Sources

### Official OpenSim / OpenSense

- OpenSim, **OpenSense — Kinematics with IMU Data** (updated 2024-08-27): OpenSense assumes fusion and synchronization are already performed; calibration registers IMUs to model segments; IK minimizes orientation error. https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084203/OpenSense+-+Kinematics+with+IMU+Data
- OpenSim, **IMU Placer Settings File and XML Tag Definitions**: strict sensor/frame naming, space-fixed XYZ sensor-to-OpenSim rotations, reference orientation file, base sensor, and heading axis. https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53112999/IMU+Placer+Settings+File+and+XML+Tag+Definitions
- OpenSim, **OpenSense FAQ**: IMU Placer estimates sensor orientation relative to segments, does not consider sensor position, and OpenSense does not scale a model. https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084548/Frequently+Asked+Questions
- OpenSim API, **InverseKinematicsSolver**: orientation references/weights, `assemble()`, efficient sequential `track()` conditions, and orientation-error computation. https://opensim-org.github.io/opensim-moco-site/docs/1.0.0/html_user/classOpenSim_1_1InverseKinematicsSolver.html
- OpenSim, **Scripting in Python** (updated 2026-06-26): official package options, version/platform caveats, native-library paths, and installation self-test. https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53085346/Scripting+in+Python

### Official ROS 2

- ROS 2 `geometry_msgs/msg/Quaternion`: message field order `x,y,z,w`. https://docs.ros.org/en/ros2_packages/rolling/api/geometry_msgs/msg/Quaternion.html
- ROS 2 `sensor_msgs/msg/Imu`: orientation/covariance semantics and invalid orientation convention. https://docs.ros.org/en/ros2_packages/rolling/api/sensor_msgs/msg/Imu.html
- ROS 2 `message_filters`: timestamp synchronization, bounded queue/slop, and warnings against headerless/arrival-time synchronization. https://docs.ros.org/en/ros2_packages/rolling/api/message_filters/message_filters.html
- ROS 2 Approximate Time tutorial: synchronized publisher/subscriber QoS compatibility requirement. https://docs.ros.org/en/ros2_packages/jazzy/api/message_filters/doc/Tutorials/Approximate-Synchronizer-Cpp.html
- ROS 2 `sensor_msgs/msg/JointState`: one common measurement timestamp, radians/metres, and equal-or-empty parallel arrays. https://docs.ros.org/en/ros2_packages/rolling/api/sensor_msgs/msg/JointState.html
- ROS 2 `diagnostic_msgs/msg/DiagnosticStatus`: standard `OK`, `WARN`, `ERROR`, and `STALE` levels. https://docs.ros.org/en/ros2_packages/rolling/api/diagnostic_msgs/msg/DiagnosticStatus.html

### Primary validation evidence

- Al Borno et al., **OpenSense: An open-source toolbox for inertial-measurement-unit-based measurement of lower extremity kinematics over long durations** (2022): task/coordinate-specific optical comparison and measured drift; supports validation under stated conditions, not transfer of accuracy claims. https://doi.org/10.1186/s12984-022-01001-x
- Bailey et al., **Validity and Sensitivity of an IMU-Driven Biomechanical Model of Motor Variability for Gait** (2021): OpenSense error varied by coordinate, with larger concerns in some non-sagittal motions. https://doi.org/10.3390/s21227690
- Slade et al., **An Open-Source and Wearable System for Measuring 3D Human Motion in Real-Time** (2022): evidence that real-time OpenSim orientation IK is feasible, while accuracy/latency remain system-specific. https://doi.org/10.1109/TBME.2021.3103201

## Confidence Notes and Open Questions

- **HIGH confidence:** OpenSense preprocessing/calibration assumptions; ROS quaternion field order, synchronization behavior, `JointState` units/array rules; the need for explicit validity and stale handling.
- **MEDIUM confidence:** Specific calibration dispersion, pair-skew, stale-age, residual, drift, and solver-deadline thresholds. These must come from Phase 16–19 measurements.
- **Open question:** Exact ESP32 quaternion direction, world frame, acquisition clock semantics, fusion reset behavior, and covariance/quality availability must be confirmed from the firmware/plugin contract.
- **Open question:** The selected `.osim` model, intended published coordinates, OpenSim version, ROS distribution, and target Jetson ABI are not yet fixed; Phase 15 must resolve them before implementation.
- **Open question:** With only master/slave orientations, the publishable coordinate subset depends on the actual segment mapping and model constraints; Phase 19 must demonstrate observability rather than assume three anatomical angles are independently measured.

---
*Pitfalls research for: v1.4 Real-time OpenSim IK*
*Researched: 2026-07-27*
