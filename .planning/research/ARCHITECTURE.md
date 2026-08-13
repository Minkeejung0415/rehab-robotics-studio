# Architecture Research

**Domain:** Open Ephys-style multi-sensor live IMU traces integrated with ROS 2, rosbridge, recording, mapping, and OpenSim
**Researched:** 2026-08-13
**Confidence:** HIGH for integration boundaries and existing contracts; MEDIUM for the exact browser rendering primitive, which should be benchmarked with the target fleet size

## Executive Recommendation

Add a dedicated **fleet raw-sample stream** beside the existing derived `Frame`/`SignalBus` path. The fleet viewer must consume the canonical per-MAC JSON topics (`/esp/raw/mac_<12hex>`) because they are the only existing stream containing all accel, gyro, magnetometer, and quaternion components together with full device identity and raw counts. Keep the existing typed per-MAC `sensor_msgs/Imu` topics (`/esp/imu/mac_<12hex>`) as the OpenSim input and keep recording in ROS/firmware, upstream of rosbridge and all browser buffering.

Extend the existing `RosbridgeDataSource` rather than opening one WebSocket per sensor. It should dynamically subscribe/unsubscribe canonical raw topics based on `/esp/fleet/registry`, parse each raw message once into a lossless browser sample, and publish those samples through a new non-React `FleetSignalBus`. `FleetSignalBus` owns bounded display history and produces pixel-width downsampled snapshots at animation-frame cadence. It must never feed recording, OpenSim, the graph executor, or control services.

Treat source identity as `(deviceId, reconnectGeneration)` and displayed mapping identity as `(modelHash, appliedRevision, applied segment/frame)`. A reconnect-generation change starts a new trace epoch. An applied-mapping change starts a new provenance epoch and must clear or visibly split old display history; it must never silently relabel old samples. Draft assignments are not labels. The current browser mapping contract must therefore be extended to retain `applied_assignments` (or authoritative `assigned`) separately from editable `assignments`.

## Standard Architecture

### System Overview

```text
ESP32 fleet (full-rate packets)
        |
        v
FleetBridgeNode ---------------------------------------------------------------+
  | canonical raw String/JSON: /esp/raw/mac_<MAC>                              |
  | typed SI Imu:            /esp/imu/mac_<MAC>                                |
  | registry:                /esp/fleet/registry                               |
  | legacy aliases:          /esp/raw/{master,slave}, /esp32/{master,slave}/imu|
  |                                                                            |
  +--> Backend recorder/export (FULL RATE, canonical raw + provenance)          |
  |                                                                            |
  +--> OpenSimNode (FULL RATE typed Imu, applied mapping + calibration)         |
  |                                                                            |
  +--> rosbridge single WebSocket                                               |
          |                                                                     |
          +--> existing Frame path --> SignalBus --> existing dashboard         |
          |                                                                     |
          +--> FleetRawSample path --> FleetSignalBus --> trace projection      |
                                            |                  |                 |
                                   bounded raw display      min/max/LTTB-like    |
                                   history per device       pixel projection     |
                                                               |                |
                                                               v                |
                                                        React viewer/canvas      |
```

The three consumers branch at ROS publication. Browser load shedding occurs only on the viewer branch after the full-rate canonical message has already been published. No arrow returns from `FleetSignalBus` to the recorder or OpenSim.

### Component Responsibilities

| Component | Status | Responsibility | Must Not Own |
|-----------|--------|----------------|--------------|
| `FleetBridgeNode` | Modify narrowly | Continue publishing one canonical raw JSON topic and one typed `Imu` topic per full MAC; expose reconnect generation consistently | Display windows, browser pause, trace scaling |
| `/esp/fleet/registry` contract | Modify | Discovery, full MAC, route state, observed rate, drops, registry revision, per-device reconnect generation | Body-part mapping truth |
| `/rehab/mapping/current` contract | Modify | Publish draft and applied snapshots distinctly, with `model_hash`, `revision`, and `applied_revision` | Live sample buffering |
| `RosbridgeDataSource` | Modify | Single-socket topic management, guarded parsing, websocket-session generation fencing, raw fleet sample fan-out | Long histories or chart downsampling |
| `FleetRawSample` contract/parser | New | Preserve raw counts, converted SI values, sensor config, sequence, source time, device ID, role, and reconnect generation | Mapping labels derived from drafts |
| `FleetSignalBus` | New | Own bounded per-device sample rings, display pause, viewport, per-channel visibility, and immutable render snapshots | Recording, exporting authoritative data, OpenSim input |
| `TraceProjector` | New | Convert the visible time interval into at most O(canvas pixels) min/max buckets per visible channel | Source sample retention |
| `viewerStore` | New | Low-frequency operator preferences: source selection, groups/channels, raw/SI, window, pause, scale, autoscale | High-rate numeric arrays in Zustand/React state |
| `SignalViewer` UI | New | Controls, labels, stacked rendering, gap/remap markers, status | Parsing ROS payloads |
| backend recorder/export | Modify or add | Subscribe to canonical per-MAC raw topics, retain every received sample, and write session provenance | Browser-projected/downsampled points |
| `OpenSimNode` | Existing; harden generation handling | Consume typed per-MAC `Imu` based only on authoritative applied mapping and calibration | Raw trace units or browser state |
| physical remap verifier/UAT artifacts | New tests/procedure | Correlate full MAC, applied revision, calibration ID, displayed label, exported columns, and visibly responding model segment | Inferring success from topic existence alone |

## Recommended Project Structure

```text
rehab-robotics-studio/src/
├── data/
│   ├── RosbridgeDataSource.ts       # extend dynamic per-MAC subscriptions and fan-out
│   ├── fleetSampleContract.ts       # new guarded raw JSON parser and unit conversion
│   ├── fleetSignalBus.ts            # new bounded high-rate external store
│   ├── traceProjector.ts             # new viewport/downsampling functions
│   ├── signalBus.ts                  # retain for legacy derived dashboard; do not extend
│   └── appDataSource.ts              # expose subscribeFleetSamples, not buffer ownership
├── state/
│   ├── mappingStore.ts               # distinguish draft and applied assignments
│   └── viewerStore.ts                # new low-rate viewer preferences
├── components/viewer/
│   ├── SignalViewer.tsx
│   ├── SourceSelector.tsx
│   ├── ViewerControls.tsx
│   ├── TraceCanvas.tsx
│   └── provenanceLabel.ts
└── hooks/
    └── useFleetSignalSnapshot.ts      # useSyncExternalStore adapter

backend/rehab_robotics_bridge/
├── fleet_bridge_node.py              # canonical streams + reconnect generation contract
├── mapping_node.py                   # authoritative applied snapshot (already persisted)
├── recorder_node.py                  # dynamic canonical per-MAC recording/export
└── opensim_node.py                   # generation-aware freshness and applied mapping consumer
```

### Structure Rationale

- Keep high-rate mutable rings outside React and Zustand. React subscribes only to immutable, rate-limited snapshots.
- Keep `signalBus.ts` unchanged in purpose. It currently executes the graph and maintains force/EMG/knee histories from a pair-derived `Frame`; adding fleet raw signals would mix incompatible semantics.
- Centralize raw payload validation and unit conversion in `fleetSampleContract.ts`. UI components must not reinterpret JSON or sensor scales.
- Place downsampling in a pure module so correctness (first/last point, extrema preservation, gaps, bounds) can be tested without a canvas.
- Keep authoritative export backend-owned because a background tab, WebSocket interruption, or a bounded browser ring cannot guarantee completeness.

## Data Contracts

### Canonical Fleet Raw Sample

The existing backend JSON is the correct base contract and already includes `device_id`, `sample_index`/`seq`, `time_us`, `node_role`, raw `imu` including magnetometer, raw quaternion counts, and `sensor_config`.

Normalize it at the browser boundary to:

```typescript
type FleetRawSample = {
  deviceId: `esp32:${string}`;       // canonical full MAC; never role/order identity
  topicToken: `mac_${string}`;
  role: string;
  seq: number;
  sourceTimeUs: number;
  receivedAtMs: number;
  reconnectGeneration: number;
  websocketGeneration: number;
  raw: {
    accel: readonly [number, number, number];
    gyro: readonly [number, number, number];
    mag: readonly [number, number, number];
    quat: readonly [number, number, number, number]; // qw,qx,qy,qz
  };
  si: {
    accelMps2: readonly [number, number, number];
    gyroRadS: readonly [number, number, number];
    magUt: readonly [number, number, number] | null;
    quat: readonly [number, number, number, number];
  };
  sensorConfig: SensorConfig;
};
```

Rules:

1. Reject a message whose topic MAC and payload `device_id` disagree.
2. Reject missing/non-finite required channel values; do not coerce invalid values to zero. The existing pair parser's `numeric(...)=0` fallback is unsuitable for diagnostic traces because it creates false flat-line samples.
3. Preserve raw and SI forms together so changing the UI unit mode never reparses history and never touches acquisition.
4. Accel and gyro SI conversions use the validated `sensor_config` already shared by frontend/backend.
5. Magnetometer SI display requires an authoritative scale/config field. Until that contract exists, expose magnetometer as raw counts and show SI as unavailable; do not invent a µT conversion.
6. Quaternion is dimensionless. Raw mode may show signed counts; normalized mode uses the existing `1 / 32767` factor and should flag implausible norm rather than silently renormalizing.

### Fleet Registry

The frontend parser currently discards top-level `revision`, `topic_token`, `last_seen_us`, and nested `reconnects.generation`. Retain them. At minimum:

```typescript
type FleetDeviceDescriptor = {
  deviceId: string;
  topicToken: string;
  route: 'connected' | 'reconnecting' | 'offline' | string;
  observedHz?: number;
  reconnectGeneration: number;
  lastSeenUs: number;
};
```

`registry.revision` orders registry snapshots. `reconnectGeneration` fences per-device samples. The WebSocket's existing `connectionGeneration` fences entire rosbridge sessions. Both are required: a device can reconnect while the browser socket remains connected, and the browser can reconnect while a device session does not.

### Applied Mapping Provenance

`mapping_node.py` already persists and publishes all needed fields: editable `assignments`, immutable-until-apply `applied_assignments`, derived `assigned`, `revision`, `applied_revision`, and `model_hash`. The current `parseMappingCurrent` drops `applied_assignments` and `assigned`, causing Studio rows to treat draft assignments as if they were runtime labels.

Extend the TypeScript snapshot/store with separate fields:

```typescript
type AppliedIdentity = {
  deviceId: string;
  segment: string;
  frame: string;
  modelHash: string;
  appliedRevision: number;
};
```

Viewer labels and exported provenance use only `applied_assignments`/`assigned`. The mapping editor continues to use `assignments`. When `appliedRevision` changes, the viewer creates a new provenance epoch and clears or partitions old visible history.

### Recording/Export Provenance

Every backend recording session needs a manifest containing:

- schema version and session ID;
- start/end times;
- canonical device IDs and canonical raw topic names;
- model hash and applied mapping revision;
- per-device applied segment/frame snapshot;
- reconnect generation at session start and any generation transitions;
- sensor configuration/unit conversion metadata;
- per-device received count, first/last sequence, detected sequence gaps, and ROS/relay drop counters.

Data rows should include at least `source_time_us`, `seq`, `device_id`, `reconnect_generation`, channel name/value or stable wide columns, and applied segment/frame/revision (directly or by manifest foreign key). Full MAC is mandatory; role is optional metadata, never the primary key.

Mapping apply is already blocked while recording, so a recording normally has one applied mapping epoch. Preserve that interlock. If any alternate recorder permits remapping, it must close the current provenance epoch before accepting the new revision.

## Architectural Patterns

### Pattern 1: One Acquisition Fan-out, Three Independent Consumers

**What:** `FleetBridgeNode` publishes each decoded frame once to canonical raw JSON and typed `Imu`. ROS recording, OpenSim, and rosbridge independently subscribe.

**When to use:** Always for live acquisition.

**Trade-offs:** Some duplicate serialization is accepted in exchange for strong isolation. A slow browser cannot backpressure the hardware recorder or solver.

**Invariant:** Display sampling settings (`pause`, window, zoom, scale, autoscale, hidden channels, render FPS, downsampling threshold) cannot change ROS QoS, backend subscriptions, firmware recording commands, raw topics, or OpenSim subscriptions.

### Pattern 2: Mutable High-rate Core, Immutable Low-rate Snapshots

**What:** `FleetSignalBus.ingest()` appends to preallocated per-device sample rings without touching React. A requestAnimationFrame scheduler publishes a new immutable view at no more than 30–60 Hz.

**When to use:** Every live trace.

**Trade-offs:** The external store is more code than component state, but it avoids one React update per sample/channel.

```typescript
rawStream.subscribe((sample) => fleetSignalBus.ingest(sample)); // every valid sample

// Display pause freezes projection/snapshot publication only.
fleetSignalBus.setDisplayPaused(true);
// It does NOT call appDataSource.pause() and does not unsubscribe upstream.
```

Store one time/sample record per device ring, not thirteen independent timestamp arrays. Channel accessors project that record. Allocate capacity from a configured hard maximum, for example `ceil(maxSampleHz * maxWindowSeconds * 1.25)`, and expose overflow counters. Changing to a shorter window changes projection, not retained acquisition or recording.

### Pattern 3: Extrema-preserving Pixel Projection

**What:** For each visible channel and horizontal pixel bucket, emit minimum and maximum values in time order (plus first/last endpoints). This bounds render work by canvas width and preserves spikes that simple every-Nth sampling would miss.

**When to use:** When samples in the visible window exceed roughly two points per horizontal pixel.

**Trade-offs:** It is visually faithful for inspection but is not an analysis dataset. The projected points must never be offered as a full-rate export.

Autoscale runs over raw samples in the visible window or bucket extrema (which preserve range), with robust padding and a zero-range fallback. It changes only y-axis transforms.

### Pattern 4: Ordered Identity Epochs

**What:** Accept samples only for the current `(websocketGeneration, deviceId, reconnectGeneration)`. A newer fleet registry generation atomically resets that device's sequence/time continuity and emits a gap marker. A new applied mapping revision emits a remap marker and new label epoch.

**When to use:** Reconnect, rosbridge restart, model change, or applied remap.

**Trade-offs:** Short gaps are visible rather than deceptively connected. Historical display is either partitioned or cleared, but never relabeled.

Do not compare raw `seq` across reconnect generations; it restarts at one. Do not use TCP route, role, array order, or abbreviated MAC as identity.

## Key Data Flows

### Discovery and Dynamic Subscription

```text
/esp/fleet/registry
    -> validate monotonic registry revision
    -> upsert device descriptor by full MAC
    -> derive /esp/raw/<topic_token>
    -> subscribe once on current rosbridge WebSocket
    -> on route offline: keep row and mark stale/gap (subscription may remain)
    -> on reconnect generation increment: reset sequence epoch, retain row/preferences
```

Keeping canonical topic subscriptions across temporary offline states avoids churn and preserves user channel preferences. On an entire WebSocket reconnect, rebuild all desired subscriptions for the new websocket generation.

### Live Display

```text
/esp/raw/mac_<MAC> String JSON (full rate)
    -> RosbridgeDataSource generation/topic fence
    -> fleetSampleContract strict parse + raw/SI conversion
    -> FleetSignalBus per-device bounded sample ring
    -> select visible time window
    -> extrema-preserving pixel projection
    -> immutable snapshot at render cadence
    -> stacked canvas traces
```

Hidden channels need not be projected, but their samples may remain in the device ring so toggling visibility is immediate within the retained window.

### Recording (Explicit Separation)

```text
/esp/raw/mac_<MAC> full-rate ROS messages
    -> backend recorder/export writer
    -> lossless rows + session manifest + counts/checks

Browser ring/downsampler --------------------X----> recorder
Browser pause/visibility/window/scale --------X----> recorder
```

The current `recorder_node.py` defaults to `/esp/raw/master` and `/esp/raw/slave`. For v1.7 it must discover or be configured with canonical per-MAC topics; alias recording is insufficient for “every connected ESP” and can make identity depend on role. Firmware SD recording remains a separate control path via `/esp/recording/set`; the viewer must not redefine the Rec button as browser capture.

### OpenSim and Remap

```text
/rehab/mapping/current (authoritative applied snapshot)
    -> OpenSimNode creates/destroys /esp/imu/mac_<MAC> subscriptions
    -> applied revision/model hash invalidate prior calibration artifact
    -> operator captures new calibration
/esp/imu/mac_<MAC> typed full-rate SI orientation
    -> freshness/sync gate -> OpenSim IK -> native visualizer
```

The viewer observes this flow but does not mediate it. After a segment swap, success requires a new applied revision, invalid/cleared old calibration, successful recalibration for that exact model hash/revision/device order, fresh post-reconnect inputs, and visible motion of the newly assigned physical segment.

## Remap and Reconnect Handling

### Required Generation Semantics

| Event | Generation/revision | Viewer action | Recorder action | OpenSim action |
|-------|---------------------|---------------|-----------------|----------------|
| Browser WebSocket reconnect | increment `connectionGeneration` | reject old-socket callbacks; rebuild subscriptions | none | none |
| One ESP reconnects | increment device `reconnectGeneration` | insert gap; reset sequence/time continuity; keep preferences | record generation transition and gaps | mark device not fresh until first new-generation frame |
| Draft assignment edited | increment mapping `revision` only | no trace relabel | no provenance change | no input remap |
| Mapping successfully applied | set new `appliedRevision`; replace `applied_assignments` atomically | new label/provenance epoch; clear or split history | blocked while active; otherwise snapshot next session | rebuild MAC subscriptions/frame mapping and invalidate old calibration |
| Model changes | new `modelHash` | invalidate body-part labels until applied snapshot matches | new session metadata only | invalidate artifact and recalibrate |

`OpenSimNode._on_fleet_registry` currently looks for `reconnected_devices` or per-device `event == "reconnect"`, while `FleetBridgeNode` publishes nested `reconnects.generation`. Standardize on generation comparison in all consumers. This closes a contract mismatch and is more reliable than transient event flags.

## Physical 3D Remap Verification Architecture

Treat hardware verification as an evidence-producing end-to-end test, not a visual spot check.

1. Identify both physical sensors using full MAC and LED identify; record MAC-to-physical placement.
2. Capture baseline applied mapping snapshot (`model_hash`, `applied_revision`, full `applied_assignments`) and reconnect generations.
3. Record a short baseline motion where only physical sensor A moves. Save viewer screenshot/trace identity, export columns/manifest, calibration ID, OpenSim joint-state metadata, and the visibly responding native model segment.
4. Stop recording and calibration capture, stage an atomic A/B segment swap, and apply the expected draft revision.
5. Verify the published applied snapshot changed atomically and the viewer labels changed only after the apply acknowledgement/snapshot—not at draft edit time.
6. Clear/confirm invalidation of the prior calibration; recalibrate in the specified standing pose against the new `model_hash + applied_revision + device_order`.
7. Repeat the same isolated physical motion. The same full MAC trace and exported device columns must remain associated with sensor A, while the responding OpenSim model segment must now be the newly applied segment.
8. Reconnect sensor A and repeat one short motion. Verify its reconnect generation increments, no old samples bridge the gap, applied mapping reattaches by MAC, recalibration/freshness gates behave as specified, and identity remains unchanged.

Minimum evidence table:

| Trial | Physical sensor | Full MAC | Reconnect gen | Applied rev | Applied segment/frame | Calibration ID | Viewer trace label | Export identity | Model segment observed |
|-------|-----------------|----------|---------------|-------------|-----------------------|----------------|--------------------|-----------------|------------------------|
| Before swap | A | value | value | value | value | value | value | value | value |
| After swap | A | same | value | newer | swapped value | new value | swapped label | same MAC + new provenance | swapped value |
| After reconnect | A | same | newer | same | same | valid/new as required | same | same | same |

## Scaling and Performance Considerations

This is a local operator application, so scale is sensors × channels × sample rate, not user count.

| Load | Architecture adjustment |
|------|-------------------------|
| 2 sensors × 13 channels × 100 Hz | Main-thread parser and typed-array rings should be sufficient; render at 30–60 Hz |
| 8–16 sensors × 13 channels × 100–200 Hz | Preallocated structure-of-arrays or compact sample rings; canvas; project only visible channels; benchmark JSON parse cost |
| Higher rate/longer windows | Move parsing/projection to a Web Worker and transfer compact numeric blocks; keep the recording path unchanged |

First bottlenecks are React reconciliation and canvas draw count, then JSON parsing/allocation. Fix them with external-store snapshots, pixel projection, preallocated rings, and optionally a Worker. Do not respond by throttling ROS subscriptions unless the user explicitly selects a display-only throttle that is proven not to alter other consumers; even then, backend recording and OpenSim subscriptions remain full rate.

## Anti-Patterns

### Reusing the Existing Pair `Frame` for Fleet Traces

**Why it fails:** `frameFromPair` replaces raw Master IMU values with derived relative accel/gyro and Slave quaternion, and `Frame` has no magnetometer. Channel identity and raw fidelity are lost.

**Instead:** Parse canonical per-MAC raw JSON into `FleetRawSample`; retain the old `Frame` path for existing dashboard/graph behavior.

### Calling `appDataSource.pause()` from the Viewer

**Why it fails:** `RosbridgeDataSource.handleMessage` returns early while paused, suppressing health, mapping, service responses, and raw processing—not merely chart motion.

**Instead:** implement display pause inside `FleetSignalBus`. Acquisition, recording, mapping callbacks, and OpenSim continue.

### Recording from Downsampled Browser Snapshots

**Why it fails:** bounded rings overwrite history; background tabs reduce animation frames; WebSockets disconnect; extrema buckets are not original samples.

**Instead:** record canonical raw ROS topics or firmware SD data before rosbridge/display transformations.

### Labelling with Draft `assignments`

**Why it fails:** draft revision can diverge from the applied snapshot consumed by OpenSim. The UI can claim a body part that the solver is not using.

**Instead:** labels and export provenance use `applied_assignments` plus `applied_revision`; mapping controls separately show drafts.

### Simple Every-Nth Downsampling

**Why it fails:** narrow spikes and dropouts can vanish, undermining diagnostic inspection.

**Instead:** use time-bucket min/max projection and render explicit gaps.

### Role/Connection-order Identity

**Why it fails:** role aliases can change and reconnect order is unstable.

**Instead:** full canonical MAC keys every buffer, preference, recorded row, mapping join, and test assertion.

## Integration Points

### ROS Topics and Services

| Contract | Producer | Consumer(s) | v1.7 action |
|----------|----------|-------------|-------------|
| `/esp/raw/mac_<12hex>` `std_msgs/String` `oe_esp32.raw.v1` | Fleet bridge | viewer, backend recorder | Primary viewer source; strict identity check; preserve all 13 IMU/quaternion fields |
| `/esp/imu/mac_<12hex>` `sensor_msgs/Imu` | Fleet bridge | OpenSim | Do not route through viewer/downsampler; note it excludes magnetometer |
| `/esp/fleet/registry` `oe_esp32.fleet_registry.v1` | Fleet bridge | mapping, OpenSim, Studio | Preserve registry revision, topic token, nested reconnect generation |
| `/rehab/mapping/current` `rehab.mapping_current.1` | Mapping node | OpenSim, Studio, recorder metadata | Parse draft and applied snapshots separately |
| `/rehab/calibration/status` and `/rehab/opensim/input_validity` | OpenSim | Studio/mapping | Show validation gates; do not infer calibration from trace freshness |
| `/esp/recording/set` | Fleet bridge service | Studio toolbar | Keep independent from display Run/Pause |
| `/opensim/calibration/{capture,clear}` | OpenSim services | Studio toolbar/UAT | Required after applied remap before 3D proof |
| `/opensim/visualizer/open` | OpenSim service | Studio toolbar | Opens native visual proof surface |

### Internal Boundaries

| Boundary | Communication | Contract rule |
|----------|---------------|---------------|
| `RosbridgeDataSource` → `FleetSignalBus` | subscribe callback | Every valid sample, ordered and generation-tagged; no React state |
| `FleetSignalBus` → React | `useSyncExternalStore` | Immutable bounded snapshot at render cadence |
| `mappingStore` → viewer label resolver | selector/read | Applied snapshot only; draft shown separately if desired |
| `viewerStore` → `FleetSignalBus` | control methods | Display-only effects; no `DataSource.pause()` |
| Fleet bridge → recorder | ROS subscription | Full-rate canonical raw message before browser processing |
| Fleet bridge → OpenSim | typed ROS subscription | Full-rate SI `Imu`, applied mapping only |

## Recommended Build Order

1. **Lock and test contracts.** Extend frontend fleet registry parsing for revision/topic token/reconnect generation; extend mapping parsing/store for `applied_assignments`/`assigned`; add mismatch and stale-generation tests.
2. **Harden backend generation semantics.** Standardize `FleetBridgeNode`, Studio, and `OpenSimNode` on nested reconnect-generation comparison; verify first post-reconnect sample reopens freshness without joining old sequence continuity.
3. **Create the lossless browser sample seam.** Add `fleetSampleContract.ts`, strict validation, raw/SI conversion, dynamic canonical topic subscription, and `subscribeFleetSamples` on the existing source. Include magnetometer raw values from day one.
4. **Implement `FleetSignalBus`.** Bounded per-device rings, epoch/gap handling, display-only pause, time-window selection, and rate-limited immutable snapshots. Unit-test capacity and ensure ingestion continues while display is paused.
5. **Implement and benchmark projection/rendering.** Pure min/max bucket projector, stacked canvas traces, visibility/groups, unit switch, zoom/scale/autoscale. Test that extrema survive downsampling and output size is bounded by pixels.
6. **Upgrade recording/export independently.** Discover canonical per-MAC topics, write full-rate rows and provenance manifest, and add count/sequence/generation reconciliation. Prove viewer controls do not change recorded sample counts or OpenSim update counts.
7. **Integrate labels and remap epochs.** Join trace source identity to applied mapping only; add remap markers/clear behavior and reconnect gap indicators.
8. **Run automated end-to-end integrity tests.** Simulate multiple MACs, draft/apply divergence, remap, WebSocket reconnect, device reconnect, malformed payloads, and browser pause. Compare publisher counts, recorder counts, and OpenSim input counts.
9. **Execute physical 3D swap UAT.** Capture the before/after/reconnect evidence matrix and retain screenshots, session manifests, applied snapshots, calibration IDs, and joint-state metadata.

## Verification Gates

- A browser test injects N raw samples while display is paused; after resume the bus reflects continued ingestion (subject only to ring capacity), while no upstream pause call was made.
- A backend integration test sends N canonical frames and verifies recorder receives N and OpenSim typed input receives N regardless of viewer window/downsampling settings.
- Exported source rows reconcile with backend-received samples and document gaps; they do not reconcile against rendered point count.
- Draft mapping edits do not change viewer applied labels, recorder provenance, or OpenSim subscriptions.
- Successful Apply changes all three on the new applied revision boundary, with recording interlock respected.
- Old websocket callbacks and old reconnect-generation samples cannot mutate current buffers.
- Physical UAT proves the same full MAC moves a different native OpenSim segment only after atomic apply and recalibration.

## Sources

Primary evidence is the current repository implementation (HIGH confidence):

- `.planning/PROJECT.md` — active milestone constraints and explicit decision to isolate bounded display buffering/downsampling from recording.
- `backend/rehab_robotics_bridge/fleet_bridge_node.py` — canonical per-MAC raw JSON and typed `Imu` topics, registry schema, raw magnetometer fields, reconnect generation, role aliases, and recording control.
- `backend/rehab_robotics_bridge/mapping_node.py` — persisted draft/applied snapshots, atomic apply, recording/calibration interlocks, and full applied `assigned` list.
- `backend/rehab_robotics_bridge/opensim_node.py` — dynamic per-MAC typed subscriptions, applied-revision tracking, calibration artifacts, freshness/synchronization gates, and current reconnect-event parsing.
- `backend/rehab_robotics_bridge/recorder_node.py` — current fixed alias-topic JSONL recorder, establishing the required v1.7 upgrade point.
- `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` — single WebSocket, session generation fencing, current fixed pair parsing, mapping/fleet callbacks, and pause behavior.
- `rehab-robotics-studio/src/data/signalBus.ts` — existing high-rate-to-React external-store pattern and its pair-derived buffer ownership.
- `rehab-robotics-studio/src/state/mappingStore.ts` — current conflation of backend draft assignment fields with applied status/labels and frontend registry field loss.

No external library choice is required to establish these boundaries. Canvas vs. a specialized plotting library remains a phase-level benchmark decision; it must preserve the contracts and invariants above.

---
*Architecture research for: v1.7 Multi-Sensor Signal Viewer & 3D Mapping Validation*
*Researched: 2026-08-13*
