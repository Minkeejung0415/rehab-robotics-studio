# Pitfalls Research

**Domain:** Open Ephys-style multi-sensor IMU live traces in an existing React/rosbridge/ROS 2/OpenSim system
**Researched:** 2026-08-13
**Confidence:** HIGH for code-specific risks and ROS/browser contracts; MEDIUM for hardware limits until measured on the target fleet

## Recommended Phase Names Used Below

1. **Phase A — Signal and Provenance Contract:** channel schema, time semantics, units, capability/validity, immutable identity, and recording/export fields.
2. **Phase B — Identity-Safe Multi-Sensor Ingestion:** dynamic per-MAC subscriptions, reconnect epochs, remap handling, independent acquisition/display control, and diagnostic counters.
3. **Phase C — Bounded Viewer and Controls:** circular buffers, display reduction, renderer scheduling, pause/zoom/autoscale, overload behavior, and performance tests.
4. **Phase D — Recording and Export Integrity:** full-rate path isolation, mapping-transition provenance, export validation, and round-trip tests.
5. **Phase E — Physical 3D Remap Acceptance:** calibrated, hardware-backed UAT with retained evidence and explicit limits on claims.

This order is deliberate. Performance code must consume a settled sample/provenance contract; export cannot be trusted until identity and time survive reconnect/remap; physical 3D claims require all preceding provenance to be observable.

## Critical Pitfalls

### Pitfall 1: Building the viewer on the legacy Master/Slave composite frame

**What goes wrong:**
Traces appear to work for two devices but cannot represent every discovered ESP independently. A remap or reconnect can leave an old trace labelled with a new body part, mix pre- and post-reconnect samples, or silently continue plotting the legacy pair-derived signal rather than the selected physical sensor.

**Why it happens:**
`RosbridgeDataSource.ts` subscribes to two fixed aliases and reduces them to one emitted `Frame`; `frameFromPair()` even replaces the master accelerometer with a derived pair inclination. Meanwhile, the backend already publishes identity-stable `/esp/raw/mac_*` and `/esp/imu/mac_*` topics. Reusing the convenient old `DataSource.subscribe(Frame)` seam loses source identity before the viewer sees it.

**How to avoid:**
Create a separate multi-sensor sample stream keyed only by canonical full MAC. Each sample must carry `device_id`, source topic, sequence/sample index, connection epoch, acquisition time, receive time, channel validity, measurement configuration/version, and the **applied** mapping revision/body part captured at that instant. Subscribe/unsubscribe from fleet registry changes, but never key buffers by row index, role, IP, connection order, or display label. On reconnect, begin a new epoch and insert a visible discontinuity; on remap, retain the same device buffer but start a new provenance segment and update labels only from the authoritative applied snapshot.

**Warning signs:**
- The viewer data type contains `Frame` but no full MAC or mapping revision.
- Selecting two MACs produces identical or pair-derived traces.
- A source row is keyed by array index or `MASTER`/`SLAVE`.
- Old points remain connected by a line after reconnect.
- A draft mapping immediately changes a trace label before Apply succeeds.

**Phase to address:**
Phase A defines the identity/provenance envelope; Phase B implements and stress-tests it across reorder, remap, dropout, and reconnect.

---

### Pitfall 2: Treating receipt time as measurement time

**What goes wrong:**
Cross-sensor alignment looks precise while actually reflecting host receipt order and network jitter. Samples can plot backward or jump across reconnects, stale master/slave samples can be paired as though simultaneous, and exported timing cannot be reconciled with ROS/OpenSim outputs.

**Why it happens:**
The backend currently assigns `time_us = time.monotonic_ns()` while publishing a decoded frame, not when the IMU measured it. The browser converts that value to seconds and falls back to `performance.now()` when it is zero/missing. Typed `Imu` messages get a separate ROS clock timestamp. These are three clock domains with no explicit semantics. ROS 2 distinguishes ROS, system, and steady clocks and requires synchronized clocks for meaningful event timestamps; time can also jump when ROS time is used.

**How to avoid:**
Define separate fields: device/sample counter, device acquisition timestamp if firmware provides one, bridge monotonic receive timestamp, ROS header timestamp, browser receive timestamp, and reconnect epoch. Never silently substitute one for another. Use sequence and epoch for ordering; use an explicitly chosen aligned timebase for cross-sensor plots. Detect duplicate, missing, backward, and implausibly large deltas. Render gaps rather than interpolating them. Document whether current hardware supports only bridge-receipt timing; if so, label synchronization confidence honestly and do not claim device-level temporal alignment.

**Warning signs:**
- A single field named `t` is used for ordering, latency, synchronization, and export.
- `performance.now()` appears as a silent fallback.
- Pairing is “latest from each sensor” with no skew bound.
- Reconnect resets sequence without changing epoch.
- Plot lines span offline intervals.

**Phase to address:**
Phase A for the time contract; Phase B for discontinuity/skew diagnostics; Phase E must reject 3D evidence when the tested inputs were stale or outside the accepted skew.

---

### Pitfall 3: Pause stops acquisition or control-plane processing

**What goes wrong:**
The operator believes only the display is frozen, but messages are discarded, health and mapping state stop updating, and service responses time out. Recording may be unintentionally affected if later code shares the paused path. Resume then shows a discontinuity with no honest explanation.

**Why it happens:**
`RosbridgeDataSource.handleMessage()` currently returns immediately when `paused`, before parsing service responses, fleet state, health, mapping, or raw samples. That pause semantic is incompatible with the milestone decision that UI controls must not affect acquisition or recording.

**How to avoid:**
Make pause a viewer cursor/state only. Continue parsing diagnostics, resolving services, ingesting into the bounded live buffer (or intentionally freeze the visible viewport while the ring advances), and recording at full rate. Define resume behavior explicitly: jump to live, or remain in historical inspection. Show “PAUSED — acquisition and recording continue,” buffer coverage, dropped-display count, and the timestamp/epoch at the frozen cursor.

**Warning signs:**
- `paused` is checked in the socket message handler or ROS subscription callback.
- Mapping Apply/recording Stop times out only while the plot is paused.
- Health age stays artificially constant during pause.
- Tests assert no callbacks occur while paused instead of only no viewport movement.

**Phase to address:**
Phase B separates data/control planes; Phase C owns only viewport semantics; Phase D verifies recording byte/sample counts are invariant under pause and other display controls.

---

### Pitfall 4: Naive display decimation invents or hides motion

**What goes wrong:**
Taking every Nth sample can erase short spikes, make a high-frequency signal look like slow motion (aliasing), suppress dropouts, or create false phase relationships between channels. A smooth trace then becomes misleading evidence about sensor or biomechanical behavior.

**Why it happens:**
The viewer has many more samples than horizontal pixels, and “downsampling” is often implemented as index stride or last-value-only. Formal decimation applies an anti-alias filter, but a diagnostic waveform viewer also needs to preserve extrema and gaps; filtering alone may hide clinically or operationally important transients.

**How to avoid:**
Keep full-rate acquisition/recording separate. For display, bucket by **time and pixel column**, preserving first/last plus min/max (and gap/invalid markers) for each channel; never bridge epochs or missing intervals. If a filtered/decimated mode is offered, label it as filtered and specify the algorithm. Use the same bucket boundaries across simultaneously compared channels. Include a raw short-window inspection mode and adversarial tests: one-sample impulse, alternating Nyquist-like samples, irregular timestamps, gaps, and reconnect boundaries.

**Warning signs:**
- Implementation is `samples.filter((_, i) => i % n === 0)`.
- A one-sample impulse disappears when the window grows.
- Dropouts become diagonal lines.
- Different channels choose unrelated sample indices.
- Exported rows equal plotted points rather than acquired points.

**Phase to address:**
Phase C, with the algorithm fixed by acceptance tests before visual styling or autoscale polish.

---

### Pitfall 5: Bounded sample count is mistaken for bounded cost

**What goes wrong:**
Memory churn, garbage collection, and main-thread CPU grow until the UI stutters even though arrays have a nominal maximum length. Scaling from 2 sources × a few series to 6 sources × 13 channels at 100–1000 Hz magnifies JSON parsing, object allocation, copying, and path construction.

**Why it happens:**
The current `RingBuffer.push()` uses `Array.shift()` and each publish returns `slice()` copies. That is tolerable for three 240-point series, but not a suitable primitive for dozens of longer traces. The stable browser `WebSocket` API has no receive backpressure; if messages arrive faster than JavaScript processes them, memory or CPU can saturate. `requestAnimationFrame()` is also paused in background tabs, so treating it as the only maintenance/drain loop is unsafe.

**How to avoid:**
Use preallocated circular typed arrays with timestamps/validity/epoch in parallel arrays, O(1) writes, and bounded capacities derived from `max_rate × max_window × margin`. Do not clone full windows into React state. Let a worker or non-React store parse/aggregate data; expose immutable versioned views or already reduced draw batches. Cap work per paint, coalesce redraws, measure handler lag and dropped-display buckets, and degrade display fidelity before diagnostics/control. Prefer backend/rosbridge display-only throttling or bounded queueing where compatible, but never apply it to the recording path. Test the maximum supported fleet/rate/window for at least 30 minutes, including hidden-tab recovery.

**Warning signs:**
- `shift`, `splice(0, …)`, spread, or `slice()` appears in per-sample/per-frame hot paths.
- React state updates once per sample/channel.
- Heap sawtooths grow over time or long tasks exceed a frame budget.
- Returning from a hidden tab freezes for seconds while catching up.
- Health/service messages lag behind raw trace traffic.

**Phase to address:**
Phase C, after Phase A defines maximum supported rates/windows and Phase B exposes overload counters.

---

### Pitfall 6: Units are cosmetic labels instead of a conversion contract

**What goes wrong:**
The same values are exported or interpreted under different units, raw counts are displayed as SI, range changes alter scale mid-trace without provenance, or channels with unrelated dimensions share an axis/autoscale. Magnetometer counts may be falsely labelled µT/T despite no verified sensitivity or calibration.

**Why it happens:**
The browser currently converts accel and gyro to SI using `sensor_config`, while the raw JSON retains counts. The backend includes magnetometer counts but no magnetometer conversion metadata. ROS `sensor_msgs/Imu` requires acceleration in m/s² and angular velocity in rad/s; `sensor_msgs/MagneticField` is a separate message in Tesla. A UI toggle cannot reconstruct raw counts from rounded SI values safely or infer magnetometer scaling.

**How to avoid:**
Retain canonical raw integer counts and validated configuration with every sample/provenance segment. Derive SI views from named, versioned conversion functions. Encode dimension/unit per channel (`count`, `m/s²`, `rad/s`, `T`, unitless), never only in a title. Range/config changes create visible segment boundaries. Group/scale channels by dimension. Until magnetometer sensitivity, availability, calibration state, and frame convention are verified, display it as `raw counts` and explicitly mark SI unavailable.

**Warning signs:**
- Unit toggle multiplies the already displayed array back and forth.
- Accel, gyro, magnetometer, and quaternion share one numeric y-scale.
- Exports contain a value but unit only in the UI.
- A range change creates an unexplained amplitude step.
- Magnetometer zero is indistinguishable from unavailable.

**Phase to address:**
Phase A defines raw/SI and configuration provenance; Phase C implements dimension-safe controls; Phase D verifies exported values and units by recomputation.

---

### Pitfall 7: Quaternion components are treated like four ordinary sensor axes

**What goes wrong:**
Invalid or non-unit quaternions reach the viewer/OpenSim; `q` to `-q` sign-equivalent transitions appear as huge component jumps; zero/missing quaternion fields become a plausible all-zero trace; autoscale exaggerates quantization noise; quaternion values are labelled or scaled like angles.

**Why it happens:**
The current parser defaults every missing/non-finite field to zero and scales signed int16 values by `1/32767`, without norm validation or normalization. Quaternions are unitless constrained orientation representations, not four independent degrees of freedom. ROS tf2 normalization explicitly targets `x²+y²+z²+w² = 1`.

**How to avoid:**
Represent quaternion availability/validity separately. Reject or gap near-zero and grossly non-unit samples; normalize only within a documented tolerance, retaining raw components for audit. For component traces, apply sign continuity for display only (`q` or `-q` chosen by dot product with prior valid display sample), and make that transformation visible in metadata; never mutate recorded raw data. Use a fixed default range of [-1, 1], unitless labels, and a norm/error diagnostic. Preserve declared component order `qw,qx,qy,qz` at every boundary and test known rotations.

**Warning signs:**
- Missing quaternion becomes `[0,0,0,0]` with no invalid marker.
- Component plots flip sign together while physical orientation is continuous.
- Quaternion autoscale uses the same policy as gyro.
- Code alternates between w-first and x-first arrays without named fields.
- OpenSim responds to a trace whose norm is far from one.

**Phase to address:**
Phase A fixes semantics/validation; Phase C owns sign-continuous display and fixed scaling; Phase E validates known physical rotations after calibration.

---

### Pitfall 8: “Nine-axis” is claimed when magnetometer data is absent, stale, or uncalibrated

**What goes wrong:**
mx/my/mz render as zeros and look valid, the typed ROS path silently omits them, or raw counts are interpreted as field strength. Users cannot tell unsupported hardware from a real zero field.

**Why it happens:**
The backend raw JSON includes channels 6–8, but `RawEspMessage`, `ImuData`, and `frameFromRaw()` omit magnetometer values. The typed `sensor_msgs/Imu` path cannot carry magnetometer data; ROS defines `sensor_msgs/MagneticField` separately. The current backend also sets all s16 values without a per-sensor availability bit or magnetic scale/calibration metadata.

**How to avoid:**
Make channel capability and sample validity explicit per device. Extend the raw viewer contract to carry mx/my/mz without routing them through `sensor_msgs/Imu`, or publish a synchronized per-MAC `MagneticField` topic once SI conversion is verified. Use `null/invalid + reason`, never zero, for unavailable channels. Verify the firmware/header capability and physical response before enabling the group. Treat hard/soft-iron calibration and bias as distinct from raw availability.

**Warning signs:**
- All three magnetometer traces are exactly zero across movement.
- UI advertises 9-axis merely because three JSON keys exist.
- `sensor_msgs/Imu` is expected to provide magnetic field.
- No capability or calibration status accompanies magnetometer traces.

**Phase to address:**
Phase A decides the channel/capability and unit contract; Phase B proves per-MAC transport; Phase E includes a physical magnetic-response check if magnetometer channels are claimed.

---

### Pitfall 9: Rendering overload contaminates diagnostics and recording

**What goes wrong:**
A heavy trace workload delays service responses, mapping status, health, and recording controls on the same WebSocket event loop. Engineers then “fix” the UI by lowering acquisition rate or throttling the source globally, silently reducing recorded data.

**Why it happens:**
All rosbridge traffic is currently parsed synchronously in one `onmessage` handler, and `paused` gates all traffic. Standard WebSockets do not provide receive backpressure. ROS 2 sensor QoS intentionally favors timely latest samples and small bounded queues, but using one reliability/queue policy indiscriminately for control, state, live display, and recording gives the wrong failure behavior for at least one of them.

**How to avoid:**
Separate logical paths and budgets: authoritative state/service responses, full-rate recording, and lossy bounded display telemetry. Process control/state first; coalesce or drop **display-only** work with counters and an overload badge. If rosbridge subscription throttling/queue limits are used, use dedicated subscriptions/topics and prove recorder inputs are untouched. Consider a Worker for JSON parsing/reduction. Record latency distributions for raw handler, state/service response, draw, and recording, not only FPS.

**Warning signs:**
- Plot visibility changes ROS publish/sample rate.
- Record Stop or Mapping Apply latency rises with channel count.
- One giant `onmessage` switch does parsing and canvas path generation.
- Display drops have no counter, or recorder counts fall when the viewer is open.

**Phase to address:**
Phase B establishes plane isolation and counters; Phase C enforces render budgets; Phase D provides the non-contamination gate.

---

### Pitfall 10: Export provenance describes the end state, not the recorded sample

**What goes wrong:**
An export is labelled with the current body-part mapping even though the session crossed remap/reconnect/configuration boundaries. Full-MAC identity, exact units, gaps, or conversion settings are lost. A downsampled display export is mistaken for the full-rate recording.

**Why it happens:**
It is tempting to join samples to the latest mapping store only when exporting. But desired and applied mappings are revisioned separately, and an operator may apply, reconnect, recalibrate, or change sensor range during a session. Late binding rewrites history.

**How to avoid:**
Persist immutable provenance events/segments as recording occurs: session ID, canonical MAC, source topic/schema, sample sequence and epoch, all time fields and clock semantics, raw channel values, unit/conversion version, sensor configuration, model hash, applied mapping revision, segment/frame, calibration ID, validity/drop/gap flags, and software/firmware versions. Export a manifest plus data; repeat identity/unit fields in columns where practical. Label display-derived exports explicitly (`display_reduced`, algorithm, parameters) and never present them as full-rate. Round-trip exported rows against source messages and count expected/actual samples per MAC/epoch.

**Warning signs:**
- Export code calls `mappingStore.getState()` once at the end.
- CSV has `body_part` but no applied revision/model hash/full MAC.
- Unit or sensor range is only in a filename.
- Pausing/hiding channels changes recorded/exported sample count.
- No distinction exists between viewer download and acquisition recording.

**Phase to address:**
Phase A defines provenance; Phase D implements and verifies exports using deliberate mid-session remap/reconnect/config changes.

---

### Pitfall 11: Declaring 3D remap validation from topics or a convincing demo

**What goes wrong:**
The system is said to prove remapping because the UI label, subscription topic, joint state, or model moved. In reality the wrong physical sensor may drive the expected segment, stale calibration may mask the swap, both sensors may have moved, or a hand-authored fixture may have bypassed the live chain.

**Why it happens:**
Visual plausibility is persuasive, and software-only checks validate wiring but not physical identity, mounting, calibration, or operator-observed segment response. The project explicitly excludes clinical/biomechanical validity without an external reference, so the evidence must not overreach.

**How to avoid:**
Use a scripted physical protocol: capture software/firmware/model hash; Identify both full-MAC devices; record initial applied revision and body placements; calibrate in the accepted pose; move only sensor A through a distinctive axis sequence while B stays still; record trace identity and responding model segment; atomically swap assignments; invalidate/recalibrate as required; repeat the same motion and show the other expected segment responds; restore mapping and repeat a control. Retain timestamps, full-MAC traces, mapping/calibration/IK status, joint-state logs, visualizer evidence, and operator sign-off in one evidence bundle. State the narrow claim: mapping-to-visualizer segment correspondence under the tested hardware/configuration—not clinical angle accuracy.

**Warning signs:**
- Evidence contains only screenshots or a video without machine-readable logs.
- No LED Identify step ties a MAC to the moved physical unit.
- Mapping changes without a new calibration/provenance ID.
- Both wearables move during the discriminating trial.
- Acceptance language says “biomechanically accurate” without an external reference.

**Phase to address:**
Phase E. It is a release gate, not an optional demonstration.

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Reuse the legacy composite `Frame` | Fast first plot | Identity and raw components are irretrievably collapsed | Only for an explicitly labelled legacy demo, never v1.7 acceptance |
| Store arrays in React state | Simple component code | Per-sample renders, copies, GC, and coupling to UI lifecycle | Tiny synthetic fixture only |
| Use `Array.shift()` ring buffers | Few lines of code | O(window) writes and allocation churn | Short test buffers, not production traces |
| Default malformed/missing fields to zero | Keeps numeric code simple | Invents valid-looking measurements | Never for acquisition channels |
| Use current mapping during export | Easy join | Historical relabelling and unauditable remap sessions | Never |
| Throttle the shared ROS source | Immediate FPS gain | Reduces recording/IK fidelity and hides overload | Never; throttle only a dedicated display path |
| Plot every sample as SVG/DOM | Easy interactions | Node/path cost explodes across sensors and windows | Only for low-rate, short static fixtures |
| Treat magnetometer counts as SI | Completes the 9-axis UI | Scientifically false units | Never |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Fleet registry → subscriptions | Subscribe by role/order and recreate rows | Key by canonical full MAC; diff topics; retain offline rows; use reconnect epochs |
| Mapping store → labels | Display draft or latest desired assignment as truth | Label samples from applied revision/model hash captured at sample time |
| Raw JSON → typed IMU | Expect mx/my/mz inside `sensor_msgs/Imu` | Keep raw magnetometer contract or add synchronized `sensor_msgs/MagneticField` |
| ROS → browser time | Treat bridge monotonic `time_us` as device measurement time | Preserve clock domain and all relevant time fields; use sequence/epoch |
| Quaternion → OpenSim/viewer | Blind `int16 / 32767` and missing→zero | Validate availability/norm/order; normalize within tolerance; preserve raw |
| rosbridge → UI | Parse, aggregate, and draw synchronously for every message | Bound/coalesce display work; prioritize state/control; expose overload counters |
| Viewer → recorder | Reuse visible/downsampled channel arrays | Recorder consumes a separate full-rate source and immutable provenance events |
| Mapping Apply → calibration | Continue using prior calibration | Invalidate by applied revision/model/frame assignment and recalibrate |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Shift-and-copy buffers | GC spikes, rising long tasks | Preallocated circular typed arrays, versioned views | Likely once dozens of channels use multi-second windows; benchmark exact target |
| Drawing all raw points | FPS falls as window grows | Pixel-time bucketing with first/min/max/last and gaps | When samples per visible channel materially exceed horizontal pixels |
| Per-sample React updates | Component tree churn | External store + paint-rate notifications | At hundreds of aggregate messages/s |
| Unbounded WebSocket event backlog | Old data shown, memory/CPU growth | Dedicated display throttling/bounds, worker reduction, lag counters | Whenever aggregate arrival exceeds sustained handler throughput |
| Catch-up after hidden tab | Multi-second freeze on return | Continue bounded ingestion independent of rAF; render only latest viewport on visibility | rAF is normally suspended in hidden tabs |
| String JSON fan-out | High parse/allocation cost | Parse once per payload; compact internal representation | Multi-sensor × 13-channel × high-rate operation |
| One budget for data and control | Service/status delays under load | Priority/separate logical queues or sockets/topics | At the first sustained display overload |

No fleet-size threshold should be claimed from calculation alone. Phase C must test the project’s declared maximum sensor count, 13 optional channels per sensor, maximum supported rate, and maximum time window on the target browser/Jetson-class environment.

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Trusting device-provided labels/IDs in DOM or filenames | UI injection, path/CSV formula hazards, misleading identity | Canonicalize MAC at backend boundary; render as text; sanitize filenames; escape spreadsheet-active prefixes |
| Accepting export provenance from browser draft state | Tampered or false audit metadata | Source applied mapping/calibration/model identity from authoritative backend events |
| Allowing arbitrary topic names from payloads | Subscription to unintended ROS data | Construct topics only from validated canonical MAC/token registry fields |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Autoscale independently every paint | Motion appears/disappears due to a moving axis | Hysteresis, visible scale values, manual lock, reset control |
| One scale for mixed dimensions | Small quaternion/magnetic signals disappear or imply comparability | Group by unit/dimension; independent group scales |
| Pause looks like acquisition stopped | Operator may disconnect or mis-handle recording | Explicit “display paused; acquisition/recording live” state |
| Gaps connected with lines | Dropouts look like motion | Break paths at missing samples, epoch changes, invalid time, and reconnect |
| “9-axis” despite unavailable magnetometer | False confidence | Per-device capability badges and unavailable-channel reasons |
| Truncated MAC as primary label | Similar devices are confused | Always show full MAC with applied body part; optional short nickname secondary |
| Quaternion autoscale without norm | Quantization noise looks dramatic | Default [-1,1], norm diagnostic, optional manual scale |
| Silent reduction | Smooth plot is mistaken for recorded truth | Display reduction badge/algorithm and full-rate recorder status/counts |

## "Looks Done But Isn't" Checklist

- [ ] **Stacked traces:** Every discovered MAC has independent raw ax–mz and optional qw–qz values; the legacy pair-derived frame is not feeding them.
- [ ] **Bounded buffers:** Capacity is bounded in bytes and time, writes are O(1), snapshots do not clone all channels, and a long soak shows stable heap.
- [ ] **Downsampling:** Impulses, alternating samples, irregular timestamps, gaps, and reconnects remain honestly represented.
- [ ] **Pause:** Display freezes while health, mapping, service responses, acquisition, and recording continue.
- [ ] **Units:** Raw and SI values round-trip using captured config; magnetometer stays raw/unavailable until its scale is verified.
- [ ] **Quaternion:** Missing/zero/non-unit samples are invalid, order is stable, display sign continuity does not mutate recording, and norm is observable.
- [ ] **Identity:** Reorder, reconnect, DHCP change, role alias change, and remap never move samples between MAC buffers.
- [ ] **Export:** Every row/segment has full MAC, applied mapping revision, model/calibration identity, unit/config, sequence/epoch, time semantics, and validity.
- [ ] **Recording isolation:** Changing visibility, time window, scale, autoscale, units, pause, or browser-tab visibility does not change recorder sample counts.
- [ ] **Overload:** A visible counter/badge reports display drops/lag while service and status latency remain within acceptance limits.
- [ ] **3D remap:** Evidence binds physical LED-identified sensors to full MAC, applied revision, recalibration, traces, and distinct before/after model response.
- [ ] **Claim boundary:** Acceptance states mapping correspondence only, not clinical or biomechanical accuracy.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Viewer built on composite frame | HIGH | Introduce identity-bearing stream, rewrite buffers/selectors, repeat provenance and hardware UAT |
| Mixed clock semantics | HIGH | Version schema, preserve all clocks, split epochs, invalidate old synchronization claims |
| Naive decimation | MEDIUM | Replace reducer, add adversarial fixtures, mark earlier visual evidence invalid |
| Memory/render overload | MEDIUM | Profile hot path, replace buffers, move parse/reduction off React, add bounds and degradation |
| False units/magnetometer labels | HIGH | Correct schema/conversions, version exports, withdraw affected datasets/claims |
| Quaternion discontinuity/invalidity | MEDIUM | Add validity/norm and display-only sign continuity; rerun OpenSim tests |
| Late-bound export labels | HIGH | Rebuild from authoritative event logs if available; otherwise data provenance is unrecoverable |
| False 3D validation claim | HIGH | Retract claim and rerun full physical protocol with linked evidence |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Legacy composite loses identity | A + B | Arbitrary order/remap/reconnect fixture shows no cross-MAC contamination |
| Receipt time masquerades as sample time | A + B | Clock-domain fields, sequence/epoch tests, gaps and skew diagnostics |
| Pause stops data/control plane | B + C + D | Pause during Apply/Stop/record; services complete and recorder counts match |
| Misleading decimation | C | Impulse/alternating/gap/reconnect golden-image and data-level tests |
| Bounded count but unbounded cost | C | Max-envelope soak with stable heap, bounded long tasks, stated FPS/latency |
| Cosmetic/false units | A + C + D | Raw↔SI recomputation and range-change export fixtures |
| Quaternion scaling/semantics | A + C | Norm/order/zero/sign-flip tests and fixed-scale UI inspection |
| Magnetometer availability fiction | A + B + E | Capability contract plus physical response; absent channels remain invalid |
| Rendering contaminates control/recording | B + C + D | Load test shows bounded state/service latency and unchanged recorder counts |
| Export uses final mapping state | A + D | Mid-session remap/reconnect/config fixture produces distinct immutable segments |
| False 3D remap validation | E | Signed evidence bundle passes scripted swap/restore protocol |

## Sources

### Primary project evidence

- `.planning/PROJECT.md` — active v1.7 requirements and explicit decisions on bounded display buffers, full-rate recording independence, full-MAC provenance, and calibrated physical 3D UAT. **HIGH confidence.**
- `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` — fixed alias subscriptions, composite frame emission, missing magnetometer fields, zero-default parsing, timestamp fallback, quaternion scaling, pause-at-handler behavior, and single WebSocket dispatch. **HIGH confidence.**
- `rehab-robotics-studio/src/data/signalBus.ts` — current `shift()` ring writes, copied snapshots, and rAF-limited React notification seam. **HIGH confidence.**
- `backend/rehab_robotics_bridge/fleet_bridge_node.py` — per-MAC topics, bridge-receipt `time_us`, raw magnetometer/quaternion channels, typed `Imu` content, queue depth, reconnect registry, and recording control. **HIGH confidence.**

### Authoritative external references

- [ROS 2 Clock and Time design](https://design.ros2.org/articles/clock_and_time.html) — clock domains, synchronization, ROS time jumps, and isolating steady time inside implementations. **HIGH confidence.**
- [ROS 2 `sensor_msgs/Imu` definition](https://docs.ros.org/en/rolling/p/sensor_msgs/msg/Imu.html) — SI acceleration/angular velocity and covariance validity conventions. **HIGH confidence.**
- [ROS 2 `sensor_msgs/MagneticField` definition](https://docs.ros.org/en/ros2_packages/rolling/api/sensor_msgs/msg/MagneticField.html) — separate magnetic field message, Tesla units, timestamp/frame semantics, and NaN for unreported axes. **HIGH confidence.**
- [ROS 2 QoS settings](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html) — Keep Last depth and sensor-data preference for timely best-effort delivery with smaller queues. **HIGH confidence.**
- [ROS tf2 quaternion API](https://docs.ros.org/en/noetic/api/tf2/html/classtf2_1_1Quaternion.html) — unit normalization condition. **HIGH confidence.**
- [MDN WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API/index.html) — stable WebSocket receive path has no backpressure and may saturate memory/CPU. **HIGH confidence.**
- [MDN `requestAnimationFrame`](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame) — callbacks track display refresh and are usually paused in background tabs. **HIGH confidence.**
- [SciPy `signal.decimate`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.decimate.html) — formal downsampling applies an anti-aliasing filter. Used as DSP reference; the min/max visual envelope recommendation is an engineering inference for diagnostic plots. **MEDIUM confidence.**

## Confidence and Remaining Research Flags

- **HIGH:** Current code will lose magnetometer data at the browser `Frame` boundary, collapse per-MAC identity into legacy pair output, treat pause as a whole-socket gate, and incur array shift/copy cost.
- **HIGH:** Recording and display must remain separate, and provenance must be tied to applied mapping rather than draft/current UI state; these are explicit project requirements reinforced by the existing revisioned architecture.
- **MEDIUM:** Exact sustainable sensor count, rate, window, memory ceiling, reducer budget, and service-latency threshold. These require target-hardware/browser measurement in Phase C.
- **MEDIUM:** Magnetometer SI conversion and calibration semantics. The raw channel positions exist, but no verified sensitivity/capability metadata was found in the reviewed path; Phase A must investigate firmware/device configuration rather than guess.
- **MEDIUM:** Device-level synchronization accuracy. The reviewed backend exposes bridge receipt time, not proven acquisition time; stronger claims require firmware/protocol evidence or an external timing protocol.

---
*Pitfalls research for: v1.7 Multi-Sensor Signal Viewer & 3D Mapping Validation*
*Researched: 2026-08-13*
