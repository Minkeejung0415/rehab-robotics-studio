# Stack Research

**Domain:** Open Ephys-style browser viewer for multi-ESP IMU traces in an existing React/TypeScript + ROS 2 application
**Researched:** 2026-08-13
**Confidence:** HIGH for the browser rendering and buffering stack; MEDIUM for magnetometer SI conversion until the deployed sensor's scale/calibration contract is confirmed

## Recommendation in One Sentence

Add only `uplot@1.6.32`; keep React 18, Zustand, Vite, the native WebSocket rosbridge client, and the ROS recording path, then implement the viewer's fixed-capacity typed-array rings, min/max display downsampling, and animation-frame scheduler as small project-owned TypeScript modules.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `uplot` | `1.6.32` | Canvas-based, multi-series time plots | It accepts aligned typed arrays, exposes `setData`, `setScale`, `setSeries`, and explicit destruction, and is designed for dense time-series rendering. Those primitives map directly to bounded display snapshots, shared time axes, visibility controls, zoom, fixed/manual scale, and autoscale without putting samples into React state. The package includes TypeScript declarations; do not add `@types/uplot`. |
| React / React DOM | Keep existing `18.3.1` | Viewer controls, layout, source/group/channel selection | No framework upgrade is required. React owns low-rate UI state and the chart lifecycle, while the high-rate sample plane remains imperative and outside React reconciliation. `useSyncExternalStore` is already available for low-rate metadata snapshots if needed. |
| TypeScript | Keep existing `5.6.3` | Typed sample contracts, buffers, unit conversion, downsampling | Fixed channel unions and discriminated raw/SI sample types prevent channel-order mistakes. Native typed arrays and deterministic pure functions are sufficient; no numeric or DSP package is needed. |
| Browser `requestAnimationFrame` | Native Web API | Coalesce arbitrary sample arrivals into display refreshes | Append every accepted sample immediately, but update plots at a capped 20-30 fps on animation frames. Hidden tabs naturally stop repaint work. Acquisition and ROS-side recording continue because neither is controlled by the viewer render loop. |
| ROS 2 Humble + rosbridge | Existing | Per-MAC sample transport and fleet/mapping metadata | Preserve the validated backend. Dynamically subscribe to canonical `/esp/raw/mac_<12hex>` `std_msgs/msg/String` topics derived from registry rows. That one payload contains raw accel, gyro, magnetometer, quaternion, timestamp, device ID, and sensor configuration; the existing typed `sensor_msgs/msg/Imu` topic does not contain magnetometer or raw counts. |

### Supporting Libraries and Project-Owned Primitives

| Library / Primitive | Version | Purpose | When to Use |
|---------------------|---------|---------|-------------|
| Zustand | Keep existing `4.5.5` | Source selection, channel/group visibility, raw/SI mode, time window, pause, manual scale/autoscale preferences | Store controls and metadata only. Never call `set` for every incoming sample. |
| `Float64Array` timestamp ring | Native | Monotonic seconds for each device | Use one time ring per device. `Float64` avoids loss of time precision over long sessions. |
| `Int16Array` raw-channel rings | Native | Exact ax-ay-az, gx-gy-gz, mx-my-mz, and quaternion counts | The wire values are signed 16-bit counts. Keeping counts preserves exact raw display and defers unit presentation without duplicating object graphs. |
| Project-owned circular buffer | N/A | Fixed memory per device and channel | Allocate capacity from `maxWindowSeconds * configuredMaxRateHz` plus a small reconnect/rate margin. Overwrite oldest samples in O(1); never `shift()` JS arrays. Start with a 30 s maximum window, 200 Hz design ceiling, and 6,000 samples per device unless milestone requirements choose different bounds. |
| Project-owned min/max envelope downsampler | N/A | Bound each visible group to O(canvas width x visible channels) points | For each time/pixel bucket, find every visible channel's min/max sample indices, take their sorted union, and emit aligned values at those timestamps. This preserves narrow spikes and saturation evidence while satisfying uPlot's shared-x aligned-data contract. Run only when producing a display snapshot; never feed its output to recording/export. |
| `ResizeObserver` | Native | Resize chart canvases with the workspace | Observe the chart host and call `setSize` only when dimensions actually change. |
| `useSyncExternalStore` | React 18 built-in | Optional low-frequency snapshot bridge | Use for source availability, newest timestamp, drop/overflow counters, and paused state if those live in an external viewer store. Do not publish a new snapshot per sample. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Existing Node `--test` + `tsx` | Unit-test ring wraparound, reconnect resets, units, and downsampling | Add deterministic tests for extrema order, NaN/invalid rejection, exact raw counts, capacity bounds, and timestamp-window slicing. No Jest/Vitest dependency is necessary. |
| Existing Playwright `1.61.1` | Browser responsiveness and control regression | Use a deterministic synthetic rosbridge fixture. Assert source discovery, pause semantics, raw/SI labels, visibility, resize, zoom, and bounded point counts. Capture long-task/render cadence metrics rather than pixel-perfect antialiasing. |
| Browser Performance panel / `PerformanceObserver` | Validate frame budget and allocation behavior | Acceptance should include maximum fleet size, all channels visible, longest supported window, reconnect churn, and simultaneous recording. |

## Installation

```bash
# From rehab-robotics-studio/
npm install uplot@1.6.32

# No new dev dependencies are required.
```

Import both the module and its stylesheet from the viewer component or application stylesheet:

```typescript
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
```

## Integration Points

### 1. Add a dedicated per-device viewer feed at the rosbridge boundary

Do not reuse the existing `DataSource.subscribe(Frame)` result for the new viewer. `RosbridgeDataSource.handleMessage()` currently accepts only the two Master/Slave aliases, converts them to SI, and collapses them into a derived paired frame. That loses per-MAC identity, raw counts, magnetometer values, and independent device timing.

Extend the rosbridge boundary with a separate contract such as:

```typescript
type ViewerSample = {
  deviceId: `esp32:${string}`;
  topic: string;
  sampleIndex: number;
  timeUs: number;
  raw: Int16Array; // fixed order: ax..mz,qw..qz
  sensorConfig: SensorConfig & { magnetometer?: MagnetometerScale };
};
```

When `/esp/fleet/registry` adds a verified device, subscribe once to its canonical `/esp/raw/mac_<12hex>` String topic; unsubscribe or ignore by connection generation when it leaves. Validate `envelope.topic`, `topic_schema`, the payload `device_id`, finite integer channel bounds, timestamp, and configuration before appending. Topic identity and payload identity must agree. Keep the existing alias subscriptions and paired-frame callback intact for current panels.

Use the canonical raw JSON as the viewer source because it is the only existing single stream that covers all required data:

- raw accel/gyro/magnetometer counts;
- optional quaternion counts;
- per-MAC `device_id`;
- sample timestamp/index;
- accel/gyro conversion configuration.

The canonical typed `sensor_msgs/msg/Imu` stream remains the right OpenSim input, but is not sufficient for this viewer: by definition and in the current publisher it carries SI acceleration, SI angular velocity, and orientation, but no magnetic field and no raw counts. Do not subscribe to both raw JSON and typed IMU for the same plot; that creates timestamp joins and identity mismatch failure modes for no benefit.

### 2. Put samples in an external buffer store, not React/Zustand state

Use `Map<deviceId, DeviceRingBuffer>`. Each device buffer owns one timestamp ring and fixed-order channel rings with a shared write index, length, generation, and overflow counter. Append is synchronous O(channels) and allocation-free after device initialization.

Raw/SI switching is a presentation transform:

- accel counts -> m/s2 using the existing validated `measurementContract`;
- gyro counts -> rad/s using the same contract;
- magnetometer counts -> tesla (display may use microtesla) only after a validated sensor-specific sensitivity/calibration field is present;
- quaternion counts -> dimensionless normalized values using the existing scale, with channel availability explicit.

Do not silently label magnetometer counts as tesla. The current `SensorConfig` and `RosbridgeDataSource` conversion helpers cover accel/gyro but not magnetometer. Before enabling magnetometer SI mode, extend the versioned measurement contract with the deployed sensor's sensitivity/range and calibration provenance, or publish a canonical per-MAC `sensor_msgs/msg/MagneticField` companion. This is a data-contract change, not a reason to add a browser math library.

### 3. Downsample only the display snapshot

On a scheduled repaint:

1. Read the selected time window from each visible device ring.
2. If samples exceed the drawable width, use a shared time/pixel bucket plan; collect each visible channel's min/max indices, sort/deduplicate their union, and use those original timestamps as the aligned x array. With three or four channels per group this is bounded by six or eight points per pixel bucket and preserves every channel's extrema.
3. Convert the chosen raw points to the selected units into reusable `Float64Array`/`Float32Array` scratch buffers.
4. Call `uPlot.setData(alignedData, false)` and update scale limits only when the operator's scale mode requires it.

Cap repaint cadence at 20-30 fps; the input may remain 100 Hz per sensor. Pause freezes the viewer cursor/snapshot only. It must not call `RosbridgeDataSource.pause()`, unsubscribe, stop buffers globally, change sample rate, or invoke the recording service. A useful implementation choice is to keep appending while paused so Resume jumps to live; if the product instead freezes history, make that an explicit viewer-only policy while still consuming/dropping into a bounded ring.

### 4. Render groups as a few synchronized plots

Use one `uPlot` instance per visible signal group (accel, gyro, magnetometer, optional quaternion), with three or four series per selected source/group and synchronized x-range/cursor. This yields readable stacked lanes and native per-group scale control without constructing one canvas per channel. If simultaneous multi-device display is required, create the same four-group stack per selected device and cap the number of actively rendered device panels; sources not on screen continue to use bounded buffers only.

Keep stable series definitions where possible and toggle visibility with `setSeries`. Rebuild a plot only when its channel topology changes (for example, quaternion becomes available), not for each sample or checkbox click.

### 5. Preserve recording/export independence

The full-rate recorder remains ROS/backend-owned and parallel to rosbridge display delivery. The browser buffer is explicitly non-authoritative and lossy after its time bound. Display overflow/downsampling must never publish upstream, change the ROS QoS/sample rate, or become the export source for a recorded session.

For export provenance, extend the backend recording schema/manifest on its existing path with `device_id`, canonical channel name, applied body part/revision, raw count, converted value/unit where applicable, and conversion/calibration version. Browser export, if later added for the visible window, must be labelled as a display-window export and must not masquerade as the full-rate recording.

## Why This Fits the Quality Gate

| Requirement | Stack mechanism |
|-------------|-----------------|
| Bounded buffers | Preallocated typed-array circular buffers have an explicit sample capacity and overwrite policy; memory is independent of session duration. |
| Downsampling | Project-owned min/max envelopes reduce each three/four-channel group to O(canvas width x group channels) aligned points while retaining every channel's transient extrema; full ring data remains untouched until naturally overwritten. |
| Multi-channel rendering | `uPlot` consumes aligned typed-array series, supports per-series visibility and multiple scales, and updates imperatively without rebuilding React nodes at sample rate. Four synchronized group charts keep axes and unit domains understandable. |
| Raw/SI switching | Exact `Int16Array` counts are the buffer truth; validated conversion functions create display snapshots on demand. Labels derive from the selected unit contract, not from chart configuration guesses. |
| Full-rate recording independence | Recording stays on the backend's existing path. Browser `requestAnimationFrame`, pause, buffer capacity, and display downsampling have no control edge back to acquisition or recording. |

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `uplot@1.6.32` | Custom Canvas 2D renderer | Use only if the exact Open Ephys lane layout cannot be achieved with synchronized uPlot group charts and the team is willing to own axes, ticks, cursors, selection, DPI scaling, and accessibility. |
| `uplot@1.6.32` | LightningChart JS / SciChart.js | Consider for hundreds to thousands of simultaneously visible channels, GPU-specific rendering requirements, or commercial support, after licensing/procurement is acceptable. Current fleet scale does not justify it. |
| Main-thread typed rings + min/max | Web Worker | Add a worker only after profiling shows snapshot extraction/conversion/downsampling creates long tasks at the accepted maximum fleet/window. If added, transfer reusable typed-array buffers; do not copy nested sample objects every frame. uPlot itself remains DOM/main-thread owned. |
| Project-owned min/max buckets | `downsample` or generic LTTB package | Use a library only if later static-history views need shape-oriented LTTB. Live diagnostic traces need spike-preserving, pixel-aware extrema and shared channel buckets, which is small and safer to test locally. |
| Dynamic rosbridge subscriptions | `roslib` | Use roslib only if the project later needs its broader ROS object API (TF, URDF, actions) throughout the frontend. For a validated lightweight WebSocket client, adding it duplicates connection/subscription/service abstractions. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Plotly, Recharts, Victory, or SVG/D3 paths for the live trace plane | Their component/SVG/object overhead is poorly matched to frequent dense multi-series updates. D3 utilities may be fine for static analysis, but are unnecessary here. | `uPlot` canvas plus imperative typed-array updates. |
| Chart.js with React wrappers | General-purpose chart lifecycle and wrapper rerenders add machinery without solving per-device rings, display decimation, or recording isolation. | Direct `uPlot` lifecycle in a small React component. |
| A React wrapper around uPlot | The wrapper becomes another lifecycle/version surface and can encourage prop replacement on each frame. | Instantiate/destroy uPlot in an effect and update through a stable ref. |
| Zustand/React state per sample | Causes subscription fan-out, object allocation, reconciliation, and avoidable garbage collection. | External mutable ring store; expose only low-rate immutable metadata snapshots. |
| Unbounded arrays or `Array.shift()` | Memory grows with session length, and shifting is O(n). | Fixed-capacity typed-array circular buffers. |
| Stride sampling or average-only buckets | Can erase brief peaks, clipping, packet glitches, and other diagnostic evidence. | Min/max envelope in temporal order. |
| OffscreenCanvas/WebGL/WebGPU in the first implementation | Adds worker/canvas ownership, fallback, text/axis, and test complexity before profiling demonstrates a bottleneck. | Main-thread uPlot at capped repaint cadence; workerize downsampling later if measured. |
| Browser buffer as recorder/export authority | Browser pauses, reloads, disconnections, bounded overwrites, and display downsampling make it intentionally incomplete. | Existing ROS/backend full-rate recording path with provenance. |
| Dual raw + typed subscriptions for plots | Requires cross-topic timestamp joining and risks showing raw and SI values from different samples. It still does not supply typed magnetometer data today. | One canonical per-MAC raw payload, one validated conversion contract. |

## Stack Patterns by Variant

**If one device is selected at a time:**

- Keep buffers for every connected device, but mount only four group plots for the selected device.
- This is the simplest and most responsive interpretation of an automatically populated source selector.

**If several devices must be compared simultaneously:**

- Mount one four-group chart stack per selected device, synchronize x ranges, and virtualize/collapse panels outside the viewport.
- Keep each device's scale state explicit; never combine accel, gyro, magnetometer, and quaternion onto one numeric scale.

**If profiling shows display snapshot work exceeds the frame budget:**

- Move only window extraction, min/max selection, and unit conversion to a dedicated worker.
- Retain rosbridge ownership and uPlot rendering on the main thread, and exchange reusable typed arrays with transferable buffers.

**If sampling rates become irregular:**

- Keep actual timestamps and uPlot's temporal x scale.
- Bucket by x/time range mapped to pixels, not by sample index, and do not interpolate gaps unless the UI explicitly distinguishes interpolation from measurements.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `uplot@1.6.32` | React `18.3.1` | No React peer dependency because integration is imperative. Create after the host DOM node mounts; call `destroy()` on cleanup, including Strict Mode's development remount cycle. |
| `uplot@1.6.32` | TypeScript `5.6.3` | Package ships `dist/uPlot.d.ts`; `AlignedData` accepts typed arrays. No DefinitelyTyped package exists or is needed. |
| React `18.3.1` | `useSyncExternalStore` | Built into React 18. Cache immutable metadata snapshots; do not return a fresh snapshot object on every read. |
| Existing Vite `5.4.11` | `uplot` ESM/CSS import | No bundler change required. Keep current Vite until a separate maintenance milestone; upgrading the build stack is unrelated to viewer delivery. |
| ROS 2 Humble `sensor_msgs/msg/Imu` | Existing per-MAC typed stream | Appropriate for OpenSim and SI accel/gyro/orientation, but not a complete viewer source because `Imu` has no magnetometer/raw-count fields. |

## Sources

- [uPlot official repository](https://github.com/leeoniya/uPlot) - performance-oriented time-series scope, package usage, demos, and direct API integration (HIGH confidence).
- [uPlot 1.6.32 npm registry entry](https://www.npmjs.com/package/uplot) - current published version and package metadata checked 2026-08-13 (HIGH confidence).
- [uPlot bundled TypeScript declaration](https://github.com/leeoniya/uPlot/blob/master/dist/uPlot.d.ts) - `AlignedData` typed arrays and `setData`, `setScale`, `setSeries`, `setSize`, `destroy` APIs (HIGH confidence).
- [uPlot official documentation](https://github.com/leeoniya/uPlot/blob/master/docs/README.md) - aligned data, scales, and performance behavior (HIGH confidence).
- [MDN `requestAnimationFrame`](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame) - paint-aligned scheduling and background-tab behavior (HIGH confidence).
- [React `useSyncExternalStore`](https://react.dev/reference/react/useSyncExternalStore) - supported external-store subscription and cached snapshot contract (HIGH confidence).
- [ROS 2 Humble `sensor_msgs/msg/Imu`](https://docs.ros.org/en/humble/p/sensor_msgs/msg/Imu.html) - standard SI acceleration/angular velocity/orientation message fields (HIGH confidence).
- [ROS 2 `sensor_msgs/msg/MagneticField`](https://docs.ros.org/en/iron/p/sensor_msgs/interfaces/msg/MagneticField.html) - magnetic field in tesla; used only as the recommended typed companion if SI magnetometer publication is added (HIGH confidence on message semantics).
- Repository evidence: `rehab-robotics-studio/package.json`, `rehab-robotics-studio/src/data/RosbridgeDataSource.ts`, and `backend/rehab_robotics_bridge/fleet_bridge_node.py` - existing dependency versions, paired-frame collapse, canonical raw payload contents, and typed per-MAC publisher behavior (HIGH confidence).

## Confidence Notes and Open Validation

- **HIGH:** `uPlot@1.6.32` is the smallest fitting rendering addition, and its public API directly supports this design.
- **HIGH:** Fixed typed rings, display-only extrema downsampling, and render scheduling are independent of backend recording when the control edges described above are enforced.
- **MEDIUM:** The exact maximum window/capacity should be set from product requirements and measured sample-rate ceiling; 30 s at 200 Hz is a recommended starting bound, not a discovered requirement.
- **MEDIUM:** Magnetometer SI conversion cannot be finalized from the current browser contract. Confirm the deployed magnetometer model, configured range/sensitivity, axes, and calibration provenance before exposing tesla/microtesla labels.
- **Phase research flag:** profile the accepted maximum number of simultaneously visible device panels on target Jetson/browser hardware before deciding whether a downsampling worker or viewport virtualization is necessary.

---
*Stack research for: v1.7 Multi-Sensor Signal Viewer & 3D Mapping Validation*
*Researched: 2026-08-13*
