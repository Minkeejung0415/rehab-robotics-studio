# Project Research Summary

**Project:** Rehab Robotics Studio — v1.7 Multi-Sensor Signal Viewer & 3D Mapping Validation
**Domain:** Local React/TypeScript + ROS 2 instrument viewer for multi-ESP IMU acquisition, recording provenance, and OpenSim mapping validation
**Researched:** 2026-08-13
**Confidence:** HIGH on architecture, identity, and isolation requirements; MEDIUM on target-hardware capacity, time synchronization, and magnetometer SI semantics

## Executive Summary

v1.7 is an operator-grade signal inspection and identity-validation milestone, not a dashboard chart enhancement. Experts build this class of system as parallel data planes: a full-rate authoritative ROS path feeds recording and OpenSim, while a deliberately bounded and lossy browser path feeds visualization. The viewer must discover every ESP by canonical full MAC, consume the per-MAC raw stream, retain exact raw counts in fixed-capacity typed-array rings, and project only the visible window into spike-preserving pixel buckets for synchronized canvas plots. React and Zustand should own controls and low-rate metadata, never per-sample data.

The recommended implementation adds only `uplot@1.6.32` to the existing React 18/TypeScript/Vite stack. Extend the existing single rosbridge connection with dynamic `/esp/raw/mac_<12hex>` subscriptions and a strict `FleetRawSample` contract; keep the legacy pair-derived `Frame` path untouched for existing panels. Build provenance around full MAC, reconnect generation, sequence/time semantics, sensor configuration, model hash, and authoritative **applied** mapping revision. Draft assignments must never relabel traces or exports. Raw/SI switching is a presentation transform over retained raw counts, and magnetometer SI must remain unavailable until its scale and calibration contract is verified.

The largest risks are false identity, false continuity, false units, and accidental coupling of display load or pause to acquisition. Prevent them with explicit identity/provenance epochs, visible gaps, strict validation, display-only pause, bounded O(1) buffers, extrema-preserving display projection, backend-owned full-rate recording, and count-based isolation tests. The milestone closes only with physical calibrated segment-remap UAT: LED-identify the hardware, capture applied revisions and calibration IDs, perform isolated motion before and after an atomic remap and recalibration, then verify the same MAC trace/export identity drives the newly assigned native OpenSim segment. This evidence proves mapping-to-visualizer correspondence under the tested configuration; it does **not** prove clinical or biomechanical accuracy.

## Key Findings

### Recommended Stack

Use the current application and ROS stack, adding one focused plotting dependency. The high-rate sample plane should be project-owned TypeScript using preallocated typed arrays and pure projection functions. This minimizes integration risk and makes the safety-critical separation between visualization and recording testable.

**Core technologies:**

- `uplot@1.6.32`: imperative canvas time-series rendering — accepts aligned typed arrays and supports data, scale, visibility, size, cursor, and lifecycle updates without React reconciliation.
- React / React DOM `18.3.1`: controls, layout, accessibility, and chart lifecycle — retain the existing version; do not upgrade as part of v1.7.
- TypeScript `5.6.3`: versioned channel, unit, validity, capability, timing, and provenance contracts — fixed channel types reduce ordering and unit mistakes.
- ROS 2 Humble + existing native rosbridge WebSocket: authoritative transport and services — dynamically add canonical per-MAC raw subscriptions on the existing socket; do not add `roslib` or one socket per sensor.
- Zustand `4.5.5`: low-rate viewer preferences only — source/group/channel visibility, window, pause, unit mode, and scale preferences; never store samples per update.
- Native typed arrays: `Float64Array` timestamps and `Int16Array` raw counts in fixed-capacity circular buffers — O(1) writes and memory bounded independently of session duration.
- Project-owned min/max envelope projector: time/pixel buckets with aligned per-group extrema — preserves spikes and gaps while bounding rendered points; its output is display-only.
- `requestAnimationFrame`, `ResizeObserver`, and optional `useSyncExternalStore`: cap repaint around 20–30 fps, resize plots, and expose immutable low-rate snapshots while full-rate ingestion continues.
- Existing Node `--test` + `tsx` and Playwright `1.61.1`: deterministic contract/buffer/projection tests plus browser interaction and performance regression tests; no new test framework is needed.

**Critical version and implementation requirements:**

- Import `uplot` directly with its bundled stylesheet and TypeScript declarations; do not add `@types/uplot` or a React wrapper.
- Start capacity planning around 30 seconds at a 200 Hz design ceiling (6,000 samples per device plus explicit margin), but treat this as a profiling hypothesis rather than an accepted product limit.
- Keep chart data aligned on original timestamps. For each pixel bucket, use the sorted union of visible channels' extrema indices so narrow events in any channel survive.
- Add a Web Worker only if target-hardware profiling proves projection/conversion causes unacceptable long tasks. Recording and OpenSim remain unchanged if workerization is needed.

Detailed rationale: [STACK.md](./STACK.md).

### Expected Features

The viewer should behave like an instrument monitor: stable source identity, synchronized traces, explicit state and units, and observational controls that cannot alter acquired data.

**Must have (v1.7 table stakes):**

- Stable source catalog keyed by canonical full MAC, merged from live fleet and saved mapping state; known offline, unassigned, and `Not used` devices remain visible and clearly labelled.
- Authoritative labels in the form `applied body part — full MAC`, including applied revision, health, reconnect status, and capability state. Draft mapping is editor state, not runtime truth.
- Independent ax/ay/az, gx/gy/gz, mx/my/mz, and capability-gated qw/qx/qy/qz traces for each source; missing or invalid channels produce gaps/reasons, never invented zeros.
- Source → group → axis visibility with stable ordering, readable persistent labels, shared time navigation, and separate numeric scales for acceleration, gyro, magnetometer, and quaternion dimensions.
- Explicit Raw/SI presentation with units on axes, cursor values, and exports. Accel/gyro conversions use captured versioned configuration; magnetometer remains raw-only until a verified sensitivity/calibration contract exists; quaternion is unitless and validity/norm aware.
- Bounded browser history, O(1) rings, shape-preserving display downsampling, visible reduction/overflow/lag counters, and responsive behavior at the declared maximum fleet/rate/window.
- Display-only pause, time-window control, paused history navigation, vertical range, predictable autoscale, zoom, and responsive/keyboard-accessible controls. The UI must say that acquisition and recording continue while display is paused.
- Honest discontinuities across invalid samples, missing timestamps, reconnect generations, and remap epochs; no interpolation or line bridging.
- Full-rate backend recording/export with full MAC, canonical channel identity, raw value and units/conversion metadata, timing and sequence semantics, reconnect generation, applied segment/frame/revision, model hash, and calibration/session provenance.
- Remap epoch handling: draft edits do nothing to live labels; a successful Apply creates a new applied provenance epoch, invalidates prior calibration, and clears or visibly partitions old display history.
- Hardware-backed calibrated remap/reconnect/export UAT using the existing native OpenSim visualizer and a retained evidence bundle.

**Should have after the core path is validated (v1.x):**

- Cross-source synchronized cursor with keyboard nudge and numeric identity/unit readout.
- Viewer-only operator presets such as placement check, raw integrity, and motion/IK views.
- Rich clipping, dropout, timestamp-gap, quaternion-norm, and transport-quality annotations.
- Intentional linked-scale compare mode for compatible channels across mapped segments.

**Defer (v2+ or separate scope):**

- Offline recording playback and file/session indexing.
- User event annotations until the timestamp/event export contract is settled.
- Embedded OpenSim rendering; native OpenSim is the v1.7 validation surface.
- Recording-channel selection; if added later, it requires a separate strongly confirmed recorder workflow.
- Generic neural-acquisition functions, firmware protocol redesign, motor/EtherCAT integration, and clinical or biomechanical accuracy claims.

Detailed feature analysis: [FEATURES.md](./FEATURES.md).

### Architecture Approach

Branch the authoritative data at ROS publication into three independent consumers: backend recording consumes full-rate canonical raw messages, OpenSim consumes full-rate typed per-MAC `sensor_msgs/Imu` under applied mapping and calibration, and rosbridge feeds a bounded display-only browser branch. Add a new `FleetRawSample` / `FleetSignalBus` path beside the legacy `Frame` / `SignalBus`; never extend the pair-derived frame into the fleet viewer because it has already lost independent identity, raw values, magnetometer channels, and timing. Treat `(websocket generation, full MAC, reconnect generation)` as stream identity and `(model hash, applied revision, applied segment/frame)` as mapping identity. Every generation/revision transition starts a visible epoch.

**Major components:**

1. **Fleet registry and mapping contracts** — preserve registry revision/topic token/reconnect generation and keep editable assignments distinct from authoritative applied assignments, model hash, and applied revision.
2. **`RosbridgeDataSource` dynamic fleet seam** — use the existing single socket to diff canonical topics, fence stale callbacks, validate topic/payload MAC agreement, parse once, and fan out lossless samples without owning history.
3. **`fleetSampleContract.ts`** — strict channel, validity, capability, unit/conversion, timestamp, sequence, and generation normalization. Invalid data is rejected or marked unavailable, never defaulted to zero.
4. **`FleetSignalBus`** — per-device fixed-capacity rings, gap/remap epochs, viewport state, display-only pause, overflow counters, and rate-limited immutable snapshots; it has no control edge to ROS acquisition, recorder, OpenSim, or service handling.
5. **`TraceProjector`** — pure visible-window extraction and shared time/pixel min/max projection with first/last, gap, and epoch preservation. Reduced output is never a recording/export source.
6. **`viewerStore` + `SignalViewer`** — low-rate preferences and accessible controls around synchronized uPlot group charts; high-rate numeric arrays remain external and imperative.
7. **Backend recorder/export** — dynamically record canonical per-MAC raw topics at full rate and emit rows plus an immutable provenance manifest and reconciliation counters.
8. **OpenSim mapping/calibration path** — continue consuming typed per-MAC IMU from the authoritative applied snapshot; reconnect generation and applied/model changes reset freshness and invalidate calibration as appropriate.
9. **Physical remap evidence procedure** — joins LED-identified physical sensors, full MACs, applied revisions, calibration IDs, trace/export identities, joint-state metadata, native visualizer observations, and operator sign-off.

**Architectural invariants:**

- Display settings — pause, visibility, unit mode, time window, scale, autoscale, FPS, and downsampling — cannot alter ROS QoS, source subscriptions used by recording/OpenSim, firmware recording, backend sample counts, or OpenSim update counts.
- The browser ring is bounded, lossy, reloadable, and non-authoritative. Only the backend full-rate path can support recording/export completeness claims.
- Mapping labels and provenance come from applied state only. A draft edit must not change viewer labels, recorder metadata, or OpenSim subscriptions.
- Sequence numbers are compared only within a reconnect epoch. Clock fields retain their domains; bridge receipt time must not be advertised as device acquisition time.
- Raw counts are canonical for viewer history. SI values are derived through named, versioned conversions; config changes create provenance boundaries.

Detailed boundaries and flows: [ARCHITECTURE.md](./ARCHITECTURE.md).

### Critical Pitfalls

1. **Building on the legacy Master/Slave `Frame`** — avoids only short-term work but permanently loses per-MAC identity, raw components, magnetometer channels, and independent timing. Add a separate canonical per-MAC fleet sample seam.
2. **Coupling pause or overload to the shared data/control plane** — the current whole-message-handler pause can suppress health, mapping, and service responses. Make pause projection-only; prioritize state/control work and shed only display work with visible counters.
3. **Confusing bounded count with bounded cost or using naive decimation** — `shift()`, full-window copies, per-sample React updates, and every-Nth sampling create GC stalls and hide transients. Use preallocated O(1) rings, capped snapshot cadence, and shared pixel-time extrema buckets tested with impulses, alternating samples, irregular timestamps, gaps, and reconnects.
4. **Treating units, time, quaternion, and channel availability as cosmetic** — silent time fallbacks, missing-to-zero parsing, unverified magnetometer SI, or quaternion renormalization create plausible false data. Version and validate these semantics at the contract boundary; surface uncertainty and invalidity explicitly.
5. **Late-binding export or mapping labels** — joining samples to the current UI state rewrites history. Persist immutable applied mapping/model/calibration/configuration events and generation-tagged sample identity as recording occurs.
6. **Using rendered points as recording evidence** — browser history is intentionally lossy and downsampled. Reconcile backend-received and recorded full-rate counts independently of plotted point counts and browser state.
7. **Overclaiming physical validation** — a moving model or correct topic proves neither physical identity nor accuracy. Require LED identification, isolated movement, atomic remap, calibration invalidation/recalibration, before/after/reconnect evidence, and narrowly worded mapping-correspondence acceptance.

Detailed failure modes and tests: [PITFALLS.md](./PITFALLS.md).

## Implications for Roadmap

The research supports five dependency-ordered phases. Contract and identity work must land before performance/UI work; recording integrity must consume the settled identity contract; physical validation is a final release gate over the complete live chain.

### Phase 1: Signal, Time, Capability, and Provenance Contract

**Rationale:** Every downstream component depends on stable definitions of device identity, channel order, validity, units, time domains, generations, and applied mapping. Deferring these decisions would force rewrites and invalidate visual/export evidence.

**Delivers:**

- Versioned `FleetRawSample`, fleet descriptor, applied identity, conversion/capability, and recording manifest contracts.
- Strict validation rules for finite signed counts, topic/payload MAC agreement, optional quaternion, magnetometer availability, sequence, and clock-domain fields.
- Separate draft and applied mapping snapshots in frontend state.
- Explicit reconnect and remap epoch semantics plus calibration invalidation keys.
- Declared product bounds to benchmark: maximum sensors, rate, visible channels, retained window, and acceptable display/control latency.

**Addresses:** stable full-MAC/applied-body labels, complete channel schema, raw/SI semantics, remap provenance, trustworthy export metadata.

**Avoids:** legacy composite identity loss, receipt-time ambiguity, false magnetometer units, invalid quaternion-as-zero, draft-state relabelling, and end-state export joins.

**Requirement implications:**

- SI magnetometer display is conditional on verified hardware sensitivity/range, axes, and calibration provenance; otherwise v1.7 must explicitly ship raw counts with SI unavailable.
- Cross-device synchronization claims must state the available timebase. Bridge receipt timing is insufficient for device-level synchronization claims without firmware/protocol evidence.
- Applied mapping revision, model hash, and calibration identity are mandatory acceptance data, not optional diagnostics.

### Phase 2: Identity-Safe Multi-Sensor Ingestion and Epoch Handling

**Rationale:** The viewer cannot be built reliably until every discovered device reaches the browser independently with stable identity and control-plane isolation. Reconnect semantics must also be consistent across bridge, Studio, and OpenSim before buffers or exports consume them.

**Delivers:**

- Dynamic canonical `/esp/raw/mac_<12hex>` subscriptions on the existing rosbridge socket.
- Lossless parse/fan-out path keyed by full MAC and fenced by websocket and reconnect generations.
- Registry revision/topic-token retention, stable offline rows, same-MAC preference restoration, and explicit gaps.
- Standard reconnect-generation comparison in bridge, Studio, and OpenSim freshness handling.
- Display sample ingestion independent of legacy pair frames, global `DataSource.pause()`, service callbacks, health/mapping state, recording, and OpenSim.
- Diagnostic counters for invalid samples, sequence gaps, stale generations, display lag, and overload.

**Addresses:** automatic fleet discovery, independent 9/13-channel sources, reconnect continuity without false continuity, visible health/failure state.

**Avoids:** role/order/IP identity, old-socket mutation, missing-to-zero data, false continuity, whole-socket pause, and display load starving state/control processing.

**Verification:** arbitrary registry order, multiple MACs, malformed payloads, topic/payload mismatch, device reconnect, websocket reconnect, draft/apply divergence, and paused display must not cross-contaminate buffers or delay service/state updates beyond the accepted threshold.

### Phase 3: Bounded Viewer, Projection, and Operator Controls

**Rationale:** UI interaction and performance behavior should be built over a settled, independently testable ingestion seam. Buffering and projection correctness precede chart polish because pause, history, zoom, cursor, and autoscale all depend on them.

**Delivers:**

- Fixed-capacity typed-array rings with O(1) writes, one time axis per device, explicit overflow policy, and epoch/gap markers.
- Pure aligned min/max pixel projection retaining endpoints, extrema, invalid gaps, and reconnect/remap boundaries.
- Direct uPlot group charts for accel, gyro, magnetometer, and capability-gated quaternion, with synchronized time navigation and dimension-safe scales.
- Source/group/axis selection, raw/SI mode, display-only pause, windows, paused pan/zoom, manual scale, explicit autoscale, active range, responsive layout, and keyboard/non-color accessibility.
- Long-soak and max-envelope performance evidence on the target browser/Jetson-class environment, including hidden-tab recovery and simultaneous recording/control activity.

**Addresses:** stacked traces, visibility/grouping, bounded display history, display reduction, pause/zoom/scale/autoscale, responsive accessible controls.

**Avoids:** React sample state, `Array.shift()`, full-window copies, background-tab catch-up, naive stride sampling, mixed-unit scaling, pumping autoscale, invisible reduction, and accidental upstream throttling.

**Verification:** ring wrap/capacity, exact raw retention, invalid/gap handling, one-sample impulse, alternating values, irregular timestamps, aligned multi-channel extrema, stable heap, bounded projected point count, render cadence, long tasks, service latency, and unchanged backend/OpenSim counts.

### Phase 4: Full-Rate Recording and Export Integrity

**Rationale:** Recording is not a browser feature. Once identity, generations, time semantics, units, and applied provenance are stable, the backend recorder can be upgraded from fixed aliases to canonical fleet topics and verified independently of every display control.

**Delivers:**

- Dynamic backend recording of every configured canonical per-MAC raw stream at full received rate.
- Session manifest and rows containing full MAC, topic/schema, channel/raw values, unit/conversion config, sequence and epoch, time fields/domains, gaps/validity, applied segment/frame/revision, model hash, calibration/session identity, and software/firmware versions as available.
- Per-device source-versus-recorder count, sequence-gap, and reconnect reconciliation.
- Explicit labelling for any later display-window export as reduced/non-authoritative, including algorithm and parameters.
- Automated non-contamination tests across pause, visibility, unit mode, window, scale, autoscale, browser visibility, and display overload.

**Addresses:** recording independence, identity-safe export, unit/provenance integrity, remap/reconnect segmentation.

**Avoids:** browser snapshots as recorder input, alias/role-based recording, current-state joins, silent omissions, and assuming plotted count equals acquired count.

**Verification:** inject N canonical frames per MAC and reconcile backend/recorder counts independent of rendered points; deliberately exercise reconnect/config boundaries; confirm mapping Apply remains interlocked during active/finalizing recording and next-session provenance uses the new applied revision.

### Phase 5: Physical Calibrated Segment-Remap Acceptance

**Rationale:** Software fixtures prove contracts but cannot prove physical sensor identity, placement, calibration, or native OpenSim segment response. This is the milestone release gate after all observable identities and provenance are available.

**Delivers:**

- A scripted before-swap, after-swap, and after-reconnect hardware procedure using two LED-identified physical ESPs.
- Baseline applied mapping revision/model hash, full-MAC placement record, reconnect generations, calibration ID, fresh/synchronized OpenSim status, isolated movement trace, export manifest, joint-state metadata, and native visualizer evidence.
- Atomic A/B segment swap performed outside active recording, followed by proof that viewer labels change only after Apply, old calibration becomes invalid, and a new required-pose calibration is captured.
- Repeated isolated motion proving the same physical MAC retains its trace/export identity while the newly mapped native OpenSim segment responds; a reconnect repeat proves restoration by MAC rather than route/order.
- Retained machine-readable logs, screenshots/video as supporting evidence, and operator sign-off in one evidence bundle.

**Addresses:** end-to-end identity ribbon, remap epoch/calibration behavior, exported column identity, and physical 3D mapping validation.

**Avoids:** topic-only or screenshot-only proof, stale calibration, both-sensor motion, hand-authored fixture bypass, and overclaiming accuracy.

**Acceptance boundary:** A pass establishes that the tested physical sensor's full-MAC identity, applied Studio segment mapping, recording/export provenance, recalibrated OpenSim input, and responding native visualizer segment agree for the tested hardware/software/model configuration. It does not establish clinical validity, biomechanical angle accuracy, general sensor fusion accuracy, or performance outside the declared test envelope. Those claims require a separate external-reference protocol and are out of scope for v1.7.

### Phase Ordering Rationale

- Contract decisions precede ingestion because identity, validity, units, time, and provenance must survive every later transform.
- Ingestion precedes UI because buffer and renderer tests need a canonical independent per-MAC stream, not the pair-derived legacy frame.
- Bounded buffer/projection foundations precede interaction polish; pause/history/zoom/autoscale are projections over retained data, not acquisition controls.
- Recorder/export work follows settled identity contracts but remains parallel to and independent from the browser implementation. Phase 4 acceptance explicitly proves this separation.
- Physical UAT comes last because meaningful evidence requires applied-revision labels, calibration invalidation, full-rate provenance, reconnect epochs, and native OpenSim freshness to be observable together.

### Scope Boundaries

- **Display plane:** bounded, lossy, downsampled, repaint-capped, and safe to pause. It may discard display work under overload with visible counters.
- **Recording plane:** backend/ROS-owned, full received rate, provenance-bearing, and unaffected by all viewer controls or browser lifecycle. It never consumes reduced display points.
- **OpenSim plane:** full-rate typed per-MAC `Imu`, authoritative applied mapping, generation-aware freshness, and calibration gated. It never consumes viewer buffers or raw/SI UI choices.
- **Legacy panels:** retain the existing pair-derived `Frame` / `SignalBus`; the new fleet viewer is a separate data product.
- **3D validation:** uses the existing native OpenSim visualizer. Embedded rendering and accuracy validation against external reference systems are explicitly deferred.
- **Future viewer capabilities:** offline playback, annotations, presets, compare/cursor enhancements, and recorder channel selection must not expand the v1.7 critical path.

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 1:** targeted hardware/firmware research is required for magnetometer capability, sensitivity/range, axes, hard/soft-iron calibration provenance, and whether device acquisition timestamps exist. Do not infer these contracts from current JSON keys.
- **Phase 3:** target-hardware profiling is mandatory to set accepted fleet/rate/window, memory, point-count, render-cadence, long-task, and service-latency thresholds and to decide whether a Worker or viewport virtualization is needed.
- **Phase 4:** inspect and lock the actual recorder container/schema and firmware/software provenance sources before finalizing manifest layout and reconciliation rules.
- **Phase 5:** plan the exact physical fixture, calibration pose, discriminating motion, expected OpenSim segments, reconnect behavior, and evidence retention/sign-off protocol with the available hardware.

Phases with well-documented patterns (skip broad research-phase):

- **Phase 2:** dynamic topic subscription, full-MAC keys, websocket/reconnect generations, strict parsing, and control/display isolation are already well supported by repository contracts and ROS/browser documentation. Use focused implementation validation rather than broad ecosystem research.
- **Phase 3 rendering primitives:** uPlot lifecycle, typed rings, `requestAnimationFrame`, `ResizeObserver`, and `useSyncExternalStore` are established. Research should be limited to measured capacity decisions, not chart-library selection.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | uPlot's official API and existing package versions directly fit aligned typed arrays and imperative canvas updates. Capacity and Worker thresholds remain measurement-dependent. |
| Features | HIGH | MVP behavior follows explicit v1.7 requirements, current mapping/recording decisions, Open Ephys operator conventions, OpenSense calibration semantics, and accessibility standards. Export layout and hardware limits remain open. |
| Architecture | HIGH | Repository evidence confirms canonical per-MAC raw and typed streams, legacy pair collapse, applied mapping revisions, recorder upgrade point, and the required fan-out/isolation boundaries. |
| Pitfalls | HIGH | Most critical failures are visible in current code/contracts and supported by authoritative ROS, WebSocket, React/browser, and OpenSim semantics. Quantitative thresholds remain MEDIUM until tested. |

**Overall confidence:** HIGH for roadmap structure and non-negotiable invariants; MEDIUM for quantitative acceptance limits and unresolved sensor/time metadata.

### Gaps to Address

- **Magnetometer SI contract:** identify the deployed sensor, configured range/sensitivity, axis convention, raw availability bit, and calibration provenance. Until confirmed, require raw counts and mark SI unavailable.
- **Clock and synchronization semantics:** determine whether firmware exposes device acquisition time. Preserve bridge monotonic, ROS, browser receipt, sequence, and epoch separately; do not claim device-level synchronization from receipt time.
- **Maximum supported envelope:** select and test maximum connected/visible sensors, 9–13 channels each, maximum sample rate, longest retained window, canvas width, memory ceiling, render cadence, and acceptable state/service latency on target hardware.
- **Recorder format:** decide JSONL/CSV/binary/sidecar details only after preserving the invariant manifest/row fields and full-rate count reconciliation described above.
- **Quaternion policy:** lock availability/norm tolerances, component order, display-only sign continuity, invalid handling, and any normalized derived path without altering recorded raw components.
- **Applied snapshot frontend contract:** verify Studio retains `applied_assignments`/`assigned` separately from draft `assignments` and labels only on Apply acknowledgement/current applied snapshot.
- **Reconnect contract consistency:** standardize nested generation comparison across FleetBridge, Studio, recorder, and OpenSim; transient event flags alone are insufficient.
- **Physical evidence protocol:** define hardware labels, isolated motions, expected segments, calibration artifact keys, evidence filenames/manifest, operator sign-off, and pass/fail language before execution.

## Sources

### Primary (HIGH confidence)

- [PROJECT.md](../PROJECT.md) — active v1.7 scope, display/recording separation, full-MAC/applied-body provenance, and physical calibrated remap requirement.
- Repository implementation: `fleet_bridge_node.py`, `mapping_node.py`, `opensim_node.py`, `recorder_node.py`, `RosbridgeDataSource.ts`, `signalBus.ts`, and `mappingStore.ts` — current topic schemas, generation fields, pair collapse, pause behavior, draft/applied state, buffer costs, and integration seams.
- [uPlot official repository](https://github.com/leeoniya/uPlot), [API declarations](https://github.com/leeoniya/uPlot/blob/master/dist/uPlot.d.ts), and [documentation](https://github.com/leeoniya/uPlot/blob/master/docs/README.md) — aligned typed-array data, imperative updates, scales, series visibility, size, and lifecycle.
- [React `useSyncExternalStore`](https://react.dev/reference/react/useSyncExternalStore) — external-store snapshot contract.
- [MDN `requestAnimationFrame`](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame) and [WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API/index.html) — repaint scheduling/background behavior and lack of receive backpressure.
- [ROS 2 Clock and Time design](https://design.ros2.org/articles/clock_and_time.html) and [Humble QoS guidance](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html) — time domains and bounded sensor-data delivery semantics.
- [ROS `sensor_msgs/Imu`](https://docs.ros.org/en/humble/p/sensor_msgs/msg/Imu.html) and [MagneticField](https://docs.ros.org/en/ros2_packages/rolling/api/sensor_msgs/msg/MagneticField.html) definitions — SI fields, validity conventions, and the absence of magnetometer data from `Imu`.
- [Open Ephys LFP Viewer](https://open-ephys.github.io/gui-docs/User-Manual/Plugins/LFP-Viewer.html), [recording guidance](https://open-ephys.github.io/gui-docs/User-Manual/Recording-data.html), and [binary format](https://open-ephys.github.io/gui-docs/User-Manual/Data-formats/Binary-format.html) — instrument-viewer controls, display/record separation, channel metadata, conversions, timestamps, and sample numbers.
- [OpenSim OpenSense kinematics](https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084203/OpenSense+-+Kinematics+with+IMU+Data), [IMU Placer settings](https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53112999), and [OpenSense FAQ](https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084548/Frequently+Asked+Questions) — physical placement identity, calibration pose, model-frame labels, and native visual inspection.
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) — keyboard operation, visible focus, non-color cues, dragging alternatives, and target size.

### Secondary (MEDIUM confidence / validation required)

- Recommended 30-second, 200 Hz, 6,000-sample-per-device starting capacity — engineering starting point from stack research; replace with measured accepted bounds.
- Main-thread parsing/projection sufficiency and 20–30 fps render target — credible for the expected scale, but must be proven on the target browser/Jetson-class environment.
- Magnetometer SI availability and device-level synchronization — unresolved until firmware/hardware metadata and timing evidence are inspected.
- [SciPy decimation reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.decimate.html) — authoritative for formal filtered decimation; the recommended min/max visual envelope is an engineering choice for transient-preserving diagnostic display, not an analysis transform.

---
*Research completed: 2026-08-13*
*Ready for roadmap: yes*
