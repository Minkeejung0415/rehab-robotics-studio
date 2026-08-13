# Feature Research

**Domain:** Open Ephys-style multi-sensor live IMU trace viewer for rehabilitation robotics operators
**Researched:** 2026-08-13
**Confidence:** HIGH for operator workflow, trace controls, accessibility, and existing mapping dependencies; MEDIUM for the final export schema and hardware performance limits until the actual recorder format and target fleet are exercised

## Operator Experience Recommendation

The viewer should behave like an instrument monitor, not a collection of dashboard sparklines. The operator selects a stable hardware source, sees its applied body assignment and health, and inspects synchronized component traces without changing the acquisition or recording state.

Recommended flow:

1. Open **Signals** and see one stable source entry for every known full MAC. Connected sources appear first; saved-but-offline sources remain visible and clearly disabled rather than disappearing.
2. Read each source as `Applied body part — full MAC`, with role and stream health secondary. An unassigned device reads `Unassigned — full MAC`; a `Not used` device is still inspectable.
3. Select one or more sources, then expand Acceleration, Gyroscope, Magnetometer, and Quaternion groups. The nine physical axes are available whenever the source streams them; quaternion appears only when actually supported.
4. Use group toggles and axis toggles to reduce clutter. Defaults should show one selected source and its accel/gyro groups, while preserving the operator's session-local choices as other devices arrive.
5. Choose Raw or SI presentation. Every y-axis, cursor value, and export field states its unit. Raw/SI changes presentation only and does not mutate the samples being recorded.
6. Set a time window, pause the display, inspect history, pan/zoom, change vertical range, or autoscale. Pause freezes that viewer only; acquisition and recording continue.
7. On dropout, the trace stops with a visible gap and the source becomes stale/offline. On reconnect, the same full MAC resumes in the same row and channel choices; the viewer never connects a line across the gap.
8. On an applied remap, start a new visual/provenance epoch, clear or visibly separate the old display buffer, show the new applied revision, and require recalibration before claiming calibrated OpenSim motion.

The current `MiniChart` is useful for compact status panels but is not a base for this feature: it autoscales each snapshot without visible units, time axis, provenance, pause state, or fixed-range comparison. Build the full viewer as a separate surface and leave dashboard sparklines lightweight.

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Dynamic source discovery with stable rows | An operator cannot preconfigure a fixed Master/Slave list in a dynamic ESP fleet | MEDIUM | Key rows and trace buffers by canonical full MAC, never IP, role, topic order, or truncated ID. Merge `/esp/fleet/registry` with saved mapping rows so offline known devices remain visible. |
| Full-MAC and applied-body labels everywhere | Wearable identity mistakes invalidate both biomechanical interpretation and exports | MEDIUM | Primary label is applied segment plus full MAC. Also show `Unassigned`, `Not used`, stale/offline, and applied revision. Use backend applied state, not a browser draft. |
| Complete per-device channel set | The milestone is incomplete if only fused orientation or a derived angle is visible | MEDIUM | Provide ax/ay/az, gx/gy/gz, mx/my/mz, and optional qw/qx/qy/qz. Do not invent quaternion channels when absent. |
| Source → group → axis navigation | 9–13 channels per device become unusable as a flat checkbox wall | MEDIUM | Hierarchical selection, select-all/none per group, collapse groups, and stable ordering: accel, gyro, mag, quaternion; x/y/z and w/x/y/z. |
| Stacked synchronized traces with a shared time axis | Operators need to compare axes and sensors at the same instant | HIGH | All visible traces use one horizontal time window and aligned timestamps. Give each trace a persistent label and zero/reference line where meaningful. |
| Explicit Raw/SI presentation | Raw counts help diagnose saturation and protocol problems; SI values support physical interpretation | HIGH | Acceleration: counts or m/s²; angular velocity: counts or rad/s; magnetometer: counts or T (displaying µT is an acceptable SI-prefixed convenience); quaternion: dimensionless. Conversion configuration/range must be known and provenance-bound. |
| Time-window control | A fixed sparkline length cannot serve both noise inspection and movement review | MEDIUM | Offer a small set of useful windows plus numeric entry within safe bounds. Show seconds and current displayed sample density. |
| Display-only pause | Open Ephys users expect to freeze a display without halting acquisition or recording | MEDIUM | Freeze the viewport and allow inspection of retained history. Label clearly `Display paused — acquisition/recording continuing`. Resume jumps to live unless operator explicitly chooses another behavior. |
| Horizontal navigation and vertical zoom/scale | Operators need to inspect a transient and compare amplitude without changing data | HIGH | While paused, pan retained history and zoom time. Vertical range is independent per physical group/source; include numeric range controls so dragging is never the only input method. |
| Predictable autoscale plus manual range | Signals with changing amplitude must remain visible, but continuously pumping scales are disorienting | MEDIUM | Autoscale on request and optionally on a slow, hysteretic policy. Display the active y-range. Manual range remains fixed until reset; never silently revert to autoscale. |
| Bounded display history and downsampled drawing | A long-running browser viewer must not accumulate memory or redraw every full-rate sample | HIGH | Use a bounded time/ring buffer and min/max or equivalent shape-preserving downsampling per pixel column. Downsample only the display branch. Surface dropped/invalid display frames separately from recorder health. |
| Recording independence | Operators must be free to inspect traces during a recording without changing what is captured | HIGH | Visibility, pause, scale, units, and rendering rate have zero effect on acquisition or full-rate recording. Recording remains the existing independent toolbar operation. |
| Recording/export identity and units | A CSV with `ax` but no device/body/revision context is unsafe to interpret | HIGH | Bind session/export metadata to full MAC, channel key, source/raw unit, conversion configuration, applied segment/frame, model hash, mapping revision, timestamps, and sample rate. Prefer stable machine keys plus human labels. |
| Reconnect continuity without false continuity | Wireless devices will drop out; hiding the gap makes the trace scientifically misleading | HIGH | Retain row/settings by MAC, mark stale, render a gap, and resume only with new timestamps. Never interpolate, bridge, or reassign a returning stream by connection order. |
| Remap provenance boundary | The same MAC can legitimately move from one body segment to another between trials | HIGH | An applied revision change invalidates the label on old buffered samples. Clear the affected buffer or preserve it as a separately labelled prior epoch; invalidate calibrated state and require recalibration. |
| Visible quality and failure state | A smooth-looking stale trace is worse than no trace | MEDIUM | Show online/stale/offline, route readiness, rate, drop/error counters, last-sample age, clipping/invalid values, and recorder failure. Do not collapse these into one green/red dot. |
| Keyboard- and non-color-dependent controls | Dense lab interfaces must work without precise pointer input and remain readable under color-vision differences | MEDIUM | Native controls, logical tab order, visible focus, text/state icons in addition to color, 24×24 CSS px minimum targets, keyboard alternatives to pan/zoom drag, and no canvas-only labels. |
| Responsive layout | Operators may use a laptop beside hardware or a larger lab monitor | MEDIUM | Keep the source/channel controls reachable; virtualize or scroll the trace stack rather than compressing channel height below readability. Preserve labels and the shared time axis on narrow screens. |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| End-to-end identity ribbon | Makes the safety-critical chain visible: physical MAC → applied body/frame → live topic/channel → recording column → OpenSim input | HIGH | A compact provenance drawer should expose model hash and applied mapping revision without crowding every trace. This directly advances the project's core value. |
| Applied-remap epoch markers | Prevents old data from silently inheriting a new biomechanical label | HIGH | Record and display the precise mapping revision boundary. Because mapping Apply is already blocked during recording, each recording can remain revision-immutable. |
| Cross-source synchronized cursor | Lets an operator point at one instant and compare numerical values across devices and groups | MEDIUM | Keyboard-nudgeable cursor; show timestamp, value, unit, MAC, and segment. This is more valuable than arbitrary decorative chart interactions. |
| Operator presets | Rapidly switches between `Placement check`, `Raw integrity`, and `Motion/IK` views without altering recording | MEDIUM | Presets save only viewer state: visible sources/groups, time window, ranges, units. Never save an applied mapping inside a viewer preset. |
| Clipping, dropout, and timestamp-gap annotations | Turns the trace viewer into a preflight and fault-localization tool | HIGH | Mark discontinuities and raw-range clipping in the trace and summarize counts. Distinguish transport gaps from renderer downsampling. |
| Source compare mode | Side-by-side or stacked comparison of the same group across multiple mapped body segments reveals swapped sensors and synchronization problems | HIGH | Example: show all devices' gz or quaternion components with the same timebase and compatible fixed scale. Avoid overlaying unlike units. |
| Hardware-backed 3D remap UAT workflow | Proves that Studio labels, mappings, calibration, solver input, and the native OpenSim model agree physically | HIGH | Provide a checklist/evidence surface, not an automatic clinical-validity claim. Capture MACs, before/after revision, calibration ID, moved physical segment, expected model segment, observed segment, and pass/fail. |
| Accessible channel identity beyond color | Preserves fast visual grouping without making color the only discriminator | LOW | Combine stable axis colors with axis text, group headers, line styles or badges, and persistent source/body labels. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Pause button that pauses acquisition | `Pause` sounds like a global halt | It can create recording gaps or stop upstream processing when the operator only wanted to inspect a trace | Name and implement `Pause display`; keep Run/Stop and Rec separate and show their states concurrently. |
| Channel visibility controls that select recorded channels | One control seems simpler | Hiding a noisy trace could irreversibly remove data from a recording; Open Ephys warns that deselected recorded channels cannot be recovered | Record the complete configured full-rate stream; make viewer selection observational only. If recording selection is ever added, place it in a separately confirmed recorder workflow. |
| One autoscale recalculated every render | Keeps every trace on screen | Produces pumping axes, hides amplitude changes, and makes cross-device comparison meaningless | Stable manual ranges plus explicit autoscale; if continuous autoscale exists, use hysteresis and clearly show that it is active. |
| One vertical scale across accel, gyro, mag, and quaternion | Gives a visually uniform panel | Unlike dimensions and magnitudes make traces unreadable and imply invalid comparisons | Share time, but scale by source and physical group; allow intentional linked scaling only among compatible channels. |
| Unlimited browser history | Feels like a complete review tool | Causes memory growth, garbage collection stalls, and eventual long-session failure | Bounded history for inspection; use the full-rate recording/export for long-term review. |
| Plot every received sample directly in React state | Seems most faithful | Render work scales with sample rate × devices × channels and can block controls while offering no extra visual information beyond screen pixels | Keep samples outside component render state, snapshot at a bounded UI rate, and downsample shape-preservingly for canvas/WebGL. |
| Smooth interpolation over loss/reconnect | Makes lines look polished | Fabricates continuity and hides wireless or timestamp failures | Explicit gaps and annotations; optionally retain last value only as a separately styled stale indicator, never as data. |
| Relabel old buffered samples immediately after remap | Keeps the screen populated | Attributes prior movement to the wrong body segment | Clear or epoch-separate affected buffers and show the new applied revision. |
| Device labels based on Master/Slave, IP, row order, or shortened MAC only | Short labels fit easily | Roles and routes are mutable; truncation can collide; operators can confuse identical units | Always retain full MAC and applied body label; optionally add a verified operator alias as secondary text. |
| Auto-apply mapping or auto-recalibrate on reconnect | Removes clicks | A transient event would change biomechanical meaning or claim calibration without the required pose | Reattach the same MAC to the unchanged applied revision automatically; require explicit remap Apply and explicit calibrated-pose capture. |
| Show quaternion zeros when unavailable | Keeps channel layouts consistent | Converts missing data into a valid-looking orientation | Hide the group and show `Quaternion unavailable`; distinguish unsupported, stale, and invalid. |
| Normalize quaternions in the display and silently export the normalized value | Makes a clean orientation trace | Conceals upstream data-quality faults and breaks raw provenance | Display raw quaternion components and norm/error annotation; normalize only in an explicitly named derived processing path. |
| Embedded 3D model as a substitute for physical UAT | Looks like visual proof inside Studio | Duplicates the deferred renderer and still may not prove native OpenSim routing | Launch the existing native OpenSim visualizer and execute a controlled, calibrated physical remap test. |
| Dense color-only axis controls and tiny click targets | Maximizes traces per screen | Excludes keyboard and low-vision users and increases wrong-channel selections | Text labels, visible focus, adequate targets, keyboard shortcuts, and scroll/virtualization. |
| Claim biomechanical or clinical validity from a successful remap demo | A moving model looks convincing | Identity/routing validation does not establish accuracy against an external reference | State the result narrowly: end-to-end mapping identity passed. Defer validity claims to a separate reference protocol. |

## Feature Dependencies

```text
Canonical full-MAC fleet registry
    + applied mapping snapshot (segment, frame, model hash, revision)
        -> stable source catalog and labels
            -> channel selection and trace stack
            -> remap/reconnect epoch handling
            -> export provenance

Per-MAC timestamped full-rate IMU stream
    -> raw/SI conversion metadata
    -> bounded display ring buffers
        -> shape-preserving display downsampling
            -> responsive stacked rendering
            -> pause/history/zoom/cursor

Existing independent recording path
    + immutable applied mapping revision during a session
        -> full-rate identity-safe recording/export

Applied mapping
    -> calibration captured in required pose
        -> provenance-matched OpenSim IK
            -> physical 3D remap UAT
```

### Dependency Notes

- **Source catalog requires both fleet and mapping truth:** fleet discovery says which MACs exist and whether their route is live; `/rehab/mapping/current` says the authoritative applied body/frame and revision. Neither alone can label traces safely.
- **The viewer needs a per-MAC stream contract:** the current `DataSource`/`Frame` path collapses data into a paired/derived frame and the parser currently covers accel/gyro but not the full magnetometer fleet. The viewer requires timestamped ax–mz and optional quaternion values keyed by full MAC.
- **Raw/SI requires versioned conversion metadata:** accel/gyro conversion already depends on configuration. Magnetometer scaling and raw range must join that contract. Labels must not claim SI when the conversion configuration is unknown.
- **Trace rendering depends on bounded buffering first:** pause, history, zoom, cursor inspection, and long-run responsiveness all build on a well-tested ring buffer and display downsampler. Implementing interactions directly over unbounded React arrays creates a rewrite.
- **Recording provenance depends on applied revision immutability:** existing mapping Apply is interlocked during recording/finalization. Preserve that rule, snapshot mapping/model/conversion metadata at recording start, and never let viewer settings enter the recorder selection path.
- **Reconnect handling depends on full-MAC identity:** restore view state only for the exact MAC. Insert a time gap and reset rate-sensitive display state after reconnect rather than treating the first sample as continuous with the old session.
- **Physical 3D validation requires recalibration after remap:** OpenSense associates IMUs to model frames and registers their orientation in a known pose. A segment swap invalidates that registration; observing the correct native OpenSim segment after an explicit new calibration is the relevant end-to-end proof.

## Hardware 3D Remap Acceptance Feature

This should be a documented operator UAT with recorded evidence:

1. Connect two physically labelled ESPs and record each full MAC.
2. Apply mapping revision A (for example MAC A → segment A, MAC B → segment B).
3. Assume the fixed calibration pose, calibrate, open the native OpenSim visualizer, and move one instrumented segment in isolation. Confirm the expected segment responds and the other does not.
4. Stop recording if active. Atomically swap the assignments in Studio and confirm applied mapping revision B is reported by the backend.
5. Confirm viewer buffers show a revision boundary/new body labels and calibration becomes invalid.
6. Reassume the required pose and recalibrate under revision B.
7. Move the same physical sensor/segment again. Confirm the model segment now associated with that MAC under revision B responds, while the former mapped segment does not.
8. Reconnect both devices and repeat a short motion check to prove identity restoration follows MAC, not route/order.
9. Export a short capture and verify its channel columns/metadata contain the same full MAC, applied segment/frame, model hash, mapping revision, units, and timestamps shown by the viewer.

Pass means identity agrees end to end. It does not establish clinical or biomechanical accuracy.

## MVP Definition

### Launch With (v1.7)

- [ ] Stable dynamically discovered source list labelled by full MAC and authoritative applied body segment, including unassigned/not-used/offline states
- [ ] Complete ax/ay/az, gx/gy/gz, mx/my/mz, and capability-gated quaternion trace stack
- [ ] Per-group/per-axis visibility with shared time axis and readable labels
- [ ] Explicit raw/SI units and trustworthy conversion metadata
- [ ] Bounded display buffers plus shape-preserving downsampling, verified in a long-running multi-device session
- [ ] Display-only pause, time window, paused history pan/zoom, manual vertical range, and explicit autoscale
- [ ] Visible gaps and stable same-MAC restoration across dropout/reconnect
- [ ] Recording/export provenance bound to full MAC, channel, units, applied mapping revision, model hash, and body/frame
- [ ] Remap epoch boundary and calibration invalidation
- [ ] Keyboard/non-color accessibility and responsive trace layout
- [ ] Physical calibrated 3D remap/reconnect/export UAT using the native OpenSim visualizer

### Add After Validation (v1.x)

- [ ] Cross-source synchronized cursor and numeric readout — add once timestamp alignment and gap semantics pass hardware UAT
- [ ] Named operator viewer presets — add once the default source/group arrangement is validated with real sessions
- [ ] Rich clipping/dropout annotations and session summary — add once raw range and transport diagnostic contracts are authoritative
- [ ] Intentional linked-scale compare mode — add once operators confirm the most useful cross-segment comparisons

### Future Consideration (v2+)

- [ ] Offline recording playback in the same viewer — valuable, but it introduces file indexing and session navigation beyond the live milestone
- [ ] User annotations/event markers — defer until a stable timestamp/event export contract exists
- [ ] Embedded OpenSim rendering — explicitly deferred; native visualizer is the accepted validation surface
- [ ] Configurable recording-channel selection — only with a separate, strongly confirmed recorder workflow and recovery safeguards

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Stable full-MAC/applied-body source catalog | HIGH | MEDIUM | P1 |
| Complete component traces | HIGH | HIGH | P1 |
| Bounded buffer and display downsampling | HIGH | HIGH | P1 |
| Display-only pause/time window/range/autoscale | HIGH | HIGH | P1 |
| Raw/SI units with conversion provenance | HIGH | HIGH | P1 |
| Reconnect gaps and remap epochs | HIGH | HIGH | P1 |
| Full-rate recording/export identity | HIGH | HIGH | P1 |
| Accessible responsive controls | HIGH | MEDIUM | P1 |
| Physical calibrated 3D remap UAT | HIGH | HIGH | P1 |
| Cross-source cursor | MEDIUM | MEDIUM | P2 |
| Viewer presets | MEDIUM | MEDIUM | P2 |
| Quality annotations | MEDIUM | HIGH | P2 |
| Offline playback | MEDIUM | HIGH | P3 |
| Embedded 3D view | LOW for this milestone | HIGH | P3 |

**Priority key:**

- P1: Must have for v1.7 acceptance
- P2: Should add after the core hardware workflow is stable
- P3: Defer beyond this milestone

## Competitor / Reference Feature Analysis

| Feature | Open Ephys LFP Viewer | OpenSim OpenSense | Rehab Robotics Studio approach |
|---------|------------------------|-------------------|--------------------------------|
| Continuous display | Stacked continuous channels with timebase, channel height/range, labels, and single-channel inspection | Not a general raw component trace viewer | Reuse the monitoring interaction model, specialized for grouped IMU axes and multi-MAC identity |
| Pause | Pauses an individual display without affecting acquisition/recording; supports paused history inspection | Not applicable | Match the display-only semantic and state it directly in the UI |
| Channel selection | Display controls and Record Node selection are separate concepts | Sensor orientation labels must correspond to model IMU frames | Viewer visibility never selects recorder content; exports retain channel/MAC/frame metadata |
| Units/metadata | Recorded binary format includes channel metadata and conversion information | Orientation input is quaternion-based and naming binds sensors to model frames | Preserve raw plus SI conversion provenance and bind every session to mapping/model identity |
| Mapping validation | Channel names reveal reordering in the viewer | Calibration registers IMUs to body segments; IK tracks model IMU frames | Prove MAC → displayed label → exported column → calibrated native 3D segment after swap/reconnect |

## Sources

### HIGH confidence — official documentation and repository evidence

- Open Ephys GUI, **LFP Viewer**: continuous stacked traces, timebase, channel height/range, labels, individual-display pause, and paused-history interaction. https://open-ephys.github.io/gui-docs/User-Manual/Plugins/LFP-Viewer.html
- Open Ephys GUI, **Recording data**: display/processing is separate from recording; individual channel recording choices can cause unrecoverable omission and recording buffers require health monitoring. https://open-ephys.github.io/gui-docs/User-Manual/Recording-data.html
- Open Ephys GUI, **Binary Format**: channel metadata, conversion information, timestamps, and sample numbers are persisted alongside samples. https://open-ephys.github.io/gui-docs/User-Manual/Data-formats/Binary-format.html
- Open Ephys GUI, **Channel Map**: channel names in the viewer are used to confirm mapping/reordering. https://open-ephys.github.io/gui-docs/User-Manual/Plugins/Channel-Map.html
- OpenSim, **OpenSense — Kinematics with IMU Data** (updated 2024-08-27): physical sensor identity must be tracked by body placement; calibration uses a known pose; sensor labels correspond to model frames; inverse kinematics tracks IMU orientations. https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084203/OpenSense+-+Kinematics+with+IMU+Data
- OpenSim, **IMU Placer Settings**: calibration orientation data, sensor-to-OpenSim rotation, and strict sensor-name/body mapping semantics. https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53112999
- OpenSim, **OpenSense FAQ**: IMU Placer registers orientation rather than position and the OpenSim GUI can be used to visually inspect sensor coordinate transformations. https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084548/Frequently+Asked+Questions
- ROS 2 `sensor_msgs/Imu`: standard physical units for angular velocity and linear acceleration. https://docs.ros.org/en/iron/p/sensor_msgs/interfaces/msg/Imu.html
- ROS 2 `sensor_msgs/MagneticField`: magnetic-field vector is expressed in tesla. https://docs.ros.org/en/iron/p/sensor_msgs/interfaces/msg/MagneticField.html
- W3C, **WCAG 2.2**: keyboard operation, visible focus, non-color cues, dragging alternatives, and minimum target size. https://www.w3.org/TR/WCAG22/
- Local project contract: `.planning/PROJECT.md` — v1.7 scope, recording independence, full-MAC/applied-body identity, bounded viewer buffers, and mandatory physical calibrated 3D remap UAT.
- Existing implementation: `rehab-robotics-studio/src/state/mappingStore.ts` — stable MAC-keyed rows, authoritative desired/applied revisions, mapping status, fleet liveness, and calibration state.
- Existing implementation: `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` — current paired-frame parsing, raw-to-SI accel/gyro conversion, recording service, fleet/mapping subscriptions, and atomic mapping Apply surface.
- Existing implementation: `rehab-robotics-studio/src/components/common/MiniChart.tsx` — lightweight per-snapshot autoscaling canvas without full viewer semantics.

### MEDIUM confidence — requires milestone validation

- Exact browser buffer duration, downsampling budget, supported simultaneous device count, and redraw rate must be selected through long-running target-hardware profiling rather than assumed from desktop performance.
- Exact recording/export container and column layout were not specified in the milestone context; the identity and provenance fields above are requirements independent of whether the implementation uses CSV, binary, or a sidecar manifest.

---
*Feature research for: v1.7 Multi-Sensor Signal Viewer & 3D Mapping Validation*
*Researched: 2026-08-13*
