# Architecture Research

**Domain:** Multi-sensor ESP-NOW discovery, stable hardware identity, model-derived OpenSim segment mapping, and dynamic ROS 2 routing
**Researched:** 2026-07-30
**Confidence:** HIGH for repository integration boundaries and migration strategy; MEDIUM for exact OpenSim runtime-frame construction until exercised against the pinned OpenSim 4.5.2 Python bindings

## Recommendation

Generalize around immutable hardware identity, not the current `master`/`slave` role labels or DHCP addresses.

Use the ESP32 base MAC as the device identity, normalized as `esp32:<12 lowercase hex>` (for example, `esp32:aabbccddeeff`). Preserve role as mutable metadata (`master` or `slave`) and preserve IP only as a transport route. Publish canonical per-device ROS topics under `/esp32/mac_<12hex>/...`; never put segment names into acquisition topic names. A segment assignment can change without changing the sensor's identity or breaking rosbag, health, and reconnect behavior.

Make the backend OpenSim process the authoritative owner of:

- the loaded model fingerprint and model-derived segment catalog;
- the persisted desired mapping for each model;
- the currently applied mapping revision;
- mapping validation and one-device-per-segment enforcement;
- calibration artifacts bound to a model and mapping revision;
- dynamic subscriptions and construction of the orientation set used by IK.

Studio owns only an editable draft and request state. It renders backend status and sends transactional set/apply requests; it does not use `localStorage` as the source of truth for mappings. The Windows relay owns only host/IP/port routing. The ROS fleet bridge owns connection and stream health. Firmware owns hardware identity and the physical Identify LED behavior.

Migrate additively. Keep the existing `/esp32/master/*`, `/esp32/slave/*`, `/esp/raw/master`, `/esp/raw/slave`, `/esp/status/pair`, OpenSim services, `/opensim/joint_states`, and the current two-input launch parameters as compatibility aliases until the fleet path passes end-to-end hardware validation. Do not choose a "first slave" nondeterministically when several slaves exist: persist an explicit `legacy_slave_id`.

## Current Architecture and Where It Collapses

| Layer | Repository evidence | Current fixed assumption | Required change |
|---|---|---|---|
| ESP-NOW master firmware | `firmware/step_node/step_node.ino:654-743` | The master already stores six slave status slots keyed by source MAC, but commands are broadcast/unicast to every active slot and status is represented as "slave" aggregate data. | Promote MAC to a versioned identity contract, add targeted Identify with application acknowledgement, and expose peer inventory without disturbing streaming. |
| ESP-NOW slave firmware | `firmware/step_node_slave/step_node_slave.ino:628-718`, `1226-1285` | Status carries a truncated 32-bit `slave_id`; no full stable identity or Identify capability exists. | Carry full base/transport MAC identity, capabilities, and Identify acknowledgement in a backward-compatible status version. |
| Windows relay | `scripts/stepesp_tcp_udp_relay.py:220-233` | Exactly one master and optional one slave; UDP is demultiplexed by DHCP source IP. | Discover/register N routes, bind IP to MAC only after firmware identity confirmation, and expose a local route registry for the ROS fleet manager. |
| Startup | `scripts/start_stepesp_wireless.ps1:112-141`, `173-193` | More than one responding station is treated as an error; exactly two ROS bridge processes and two OpenSim topics are launched. | Discover all candidates, launch one fleet bridge manager, and start OpenSim in mapping mode. |
| ROS ESP bridge | `backend/rehab_robotics_bridge/esp32_bridge_node.py:167-235` | `node_id` is `master` or `slave`; topics and health keys derive from that role; pair health subscribes to one slave. | Extract a reusable device session and add a fleet manager that publishes per-MAC topics and fleet health while retaining aliases. |
| Raw schema | `backend/rehab_robotics_bridge/esp32_bridge_node.py:915-936` | `node_role`, `node_id`, and `body_segment` are startup parameters and therefore conflate source identity with mapping. | Add immutable `device_id` and full MAC; remove mapping authority from the acquisition bridge. Keep deprecated fields for v1 compatibility. |
| OpenSim node | `backend/rehab_robotics_bridge/opensim_node.py:49-166`, `262-298` | `_ROLES = ("master", "slave")`; two subscriptions and two frame parameters are constructed once. | Replace role dictionaries with device-ID dictionaries and transactional dynamic subscriptions derived from an applied mapping. |
| Calibration | `backend/rehab_robotics_bridge/opensim/calibration.py` | Artifact and capture buffers have `master_xyzw` and `slave_xyzw`. | Store offsets and capture samples by device ID/model frame, and bind artifacts to `model_id` + `mapping_revision`. |
| Official orientation IK | `backend/rehab_robotics_bridge/opensim/opensim_orientation_ik.py` | Tables, labels, offsets, and `solve()` take exactly two orientations. | Build N-column quaternion tables in deterministic segment order and accept a mapping-keyed orientation set. |
| Visualizer adapter | `backend/rehab_robotics_bridge/opensim_adapter.py:228-240`, `318-337` | The adapter already accepts an arbitrary `frame_mappings` dictionary; the ROS caller limits it to two. | Keep the adapter boundary and pass the applied N-device mapping. Generalize labels/status, not the process boundary. |
| Rosbridge source | `rehab-robotics-studio/src/data/RosbridgeDataSource.ts:48-55`, `353-387`, `406-416` | Static master/slave raw subscriptions, pair health, and two cached frames. | Preserve this legacy stream for the graph while adding fleet/mapping subscriptions and custom mapping/Identify service calls. |
| Studio state/UI | `rehab-robotics-studio/src/state/systemStore.ts`, `types/health.ts`, `components/dashboard/HealthPanel.tsx` | Pair-shaped types and hard-coded MASTER/SLAVE rows. | Add normalized device/mapping stores and a dedicated mapping panel keyed by device ID. |

## Standard Architecture

### System Overview

```text
  ESP32 master                          ESP32 slaves (0..6 current limit)
  base MAC + AP/ESP-NOW MAC             base MAC + STA/ESP-NOW MAC
  local Identify LED                    local Identify LED
        |                                      |
        +-------- versioned ESP-NOW -----------+
        |  sync + existing commands + status + targeted Identify/ack
        |
  STEP_ESP32 TCP/UDP endpoints (DHCP is transport only)
        |
  Windows STEP_ESP relay
  - probes IDENTITY? before registering a route
  - routes UDP by current source IP
  - maintains device_id -> current IP -> stable local relay endpoint
  - exposes bounded local registry API to WSL
        |
  ROS 2 esp32_fleet_bridge
  - one reusable session per route
  - canonical topics /esp32/mac_<hex>/{imu,raw}
  - raw JSON /esp/raw/mac_<hex>
  - status /esp/status/mac_<hex> and /esp/status/fleet
  - compatibility aliases master/slave + pair
        |
        +---------------------+-------------------------+
        |                     |                         |
   rosbag/other users   opensim_bridge            rosbridge_server
                       - model catalog                  |
                       - mapping store                  |
                       - dynamic subscriptions          |
                       - N-sensor calibration           |
                       - N-sensor orientation IK        |
                       - native visualizer              |
                              |                         |
                       existing OpenSim topics/services |
                              +------------+------------+
                                           |
                                    React Studio
                                    - backend fleet status
                                    - model segment choices
                                    - draft + apply controls
                                    - Identify action
```

### Authoritative State Ownership

| State | Authoritative owner | Cached/derived copies | Rule |
|---|---|---|---|
| Hardware ID | Firmware base MAC | relay, ROS, Studio | Use `esp_read_mac(..., ESP_MAC_BASE)` or an equivalent full 48-bit base MAC API. Never derive identity from IP, slot, role, or the current 32-bit `slave_id`. |
| ESP-NOW destination MAC | Master firmware peer table | relay/ROS status for diagnostics | Keep separate from base MAC because AP/STA interface MACs can differ. |
| Device role/capabilities/firmware version | Firmware identity response | relay and fleet status | Role is metadata, not identity and not a topic key. |
| Current IP and local relay endpoint | Windows relay route registry | ROS fleet bridge | Route may change on reconnect; it must never rewrite `device_id`. |
| Stream connection/freshness/rate | ROS fleet bridge | `/esp/status/*`, Studio | Compute from accepted frames and connection events, not from UI timers. |
| Loaded model | `opensim_bridge` | mapping status and Studio | Identify with SHA-256 of model bytes plus schema version; path/name are descriptive. |
| Selectable segment catalog | `opensim_bridge` model catalog | Studio mapping store | Enumerate the loaded model's `BodySet`; resolve each body to an existing compatible IMU frame or a deterministic runtime frame before `initSystem()`. |
| Desired per-model mapping | backend `MappingStore` inside `opensim_bridge` | Studio draft | Persist atomically by `model_id`; disconnected devices remain in the mapping. |
| Applied mapping | `opensim_bridge` | mapping status and Studio | One monotonically increasing revision; only swap after complete validation and successful solver/adapter staging. |
| Calibration | backend calibration controller | status/UI | Bind to `model_id`, mapping revision, exact device-to-frame set, and convention version. Any applied mapping/model change invalidates it. |
| IK validity and outputs | `opensim_bridge` | rosbridge/Studio | Continue the existing hard gate: no new `JointState` unless mapping is ready, every required input is fresh, calibration matches, and solve is valid. |
| UI selections/busy state | Studio | none | Ephemeral. A reload rehydrates from backend mapping status. |

## Identity and Topic Strategy

### Canonical Identity

```text
display_mac:     AA:BB:CC:DD:EE:FF
mac_hex:         aabbccddeeff
device_id:       esp32:aabbccddeeff
ros_token:       mac_aabbccddeeff
canonical topic: /esp32/mac_aabbccddeeff/imu
canonical node:  esp_bridge_mac_aabbccddeeff
```

Normalize and validate at every trust boundary:

- exactly 48 bits / 12 hexadecimal digits;
- lowercase for keys and ROS names;
- colon-separated uppercase only for display;
- reject all-zero, broadcast, malformed, or duplicate IDs;
- compare normalized values, never user-provided display strings.

The master must report both `base_mac` and the MAC used by its AP/ESP-NOW interface. Each slave must report `base_mac`, `sta_mac`, and the master-observed `espnow_mac`. In the usual case the slave base and STA MAC match; the architecture must not require that assumption.

### ROS Topics

| Topic | Type | Purpose |
|---|---|---|
| `/esp32/mac_<hex>/imu` | `sensor_msgs/msg/Imu` | Canonical typed orientation/accel/gyro stream for one immutable device ID. |
| `/esp32/mac_<hex>/raw` | `std_msgs/msg/Float32MultiArray` | Canonical normalized raw stream. |
| `/esp/raw/mac_<hex>` | `std_msgs/msg/String` | Rosbridge-friendly existing raw schema extended with identity. |
| `/esp/status/mac_<hex>` | `std_msgs/msg/String` | Per-device connection, freshness, recording, capability, and Identify state. |
| `/esp/status/fleet` | `std_msgs/msg/String` | Versioned full inventory and topology health. Publish on change and heartbeat. |
| `/esp32/master/*`, `/esp/raw/master`, `/esp/status/master` | existing types | Compatibility alias to the one device whose firmware role is master. |
| `/esp32/slave/*`, `/esp/raw/slave`, `/esp/status/slave` | existing types | Compatibility alias to persisted `legacy_slave_id`, never an arbitrary first device. |
| `/esp/status/pair` | existing String JSON | Existing pair view constructed from master + `legacy_slave_id`. |

Do not create segment-named sensor topics such as `/femur/imu`. Segment assignment is model state and may change; encoding it in the acquisition namespace produces stale subscribers and ambiguous recordings. OpenSim subscribes to hardware topics and maps those streams to model frames internally.

### Fleet Status Schema

Publish `rehab.esp_fleet.2` on `/esp/status/fleet`:

```json
{
  "schema": "rehab.esp_fleet.2",
  "revision": 17,
  "timestamp_us": 123456789,
  "legacy_slave_id": "esp32:112233445566",
  "devices": [
    {
      "device_id": "esp32:aabbccddeeff",
      "mac": "AA:BB:CC:DD:EE:FF",
      "role": "master",
      "connection_state": "connected",
      "espnow_state": "local",
      "last_frame_age_ms": 8.2,
      "observed_stream_rate_hz": 99.9,
      "capabilities": ["stream", "record", "identify"],
      "identify": {"state": "idle", "command_id": null, "until_ms": null}
    }
  ],
  "issues": []
}
```

Connected, ESP-NOW-visible, and stream-routable are separate states:

- `espnow_state=visible` but `connection_state=transport_unreachable` means the master sees the peer but the Windows relay cannot reach its TCP endpoint;
- a TCP route without recent ESP-NOW status is `espnow_state=stale`;
- only accepted data frames make a stream `connected/live`.

This distinction is necessary because the existing master can see up to six ESP-NOW status slots even when a slave DHCP/TCP route is unhealthy.

## Firmware Integration

### Modify: Both Sketches

Modify:

- `firmware/step_node/step_node.ino`
- `firmware/step_node_slave/step_node_slave.ino`
- `backend/test/test_stepesp_firmware_topology.py`

Add a small protocol header inside each Arduino sketch directory (Arduino builds do not reliably include a sibling shared directory):

- `firmware/step_node/step_espnow_protocol.h`
- `firmware/step_node_slave/step_espnow_protocol.h`

The regression test should require the two headers to be byte-identical.

### Additive Firmware Contracts

1. `IDENTITY?` TCP command, valid before or during streaming.
   - Reply is one bounded ASCII line:
     `IDENTITY_OK schema=device-v1 device_id=esp32:aabb... base_mac=AA:... transport_mac=AA:... role=master capabilities=stream,record,identify firmware=<version>`
   - The bridge/relay rejects a route whose response is missing, malformed, or changes identity during a connection.

2. `PEERS?` master TCP command.
   - Reply begins with `PEERS_BEGIN revision=<n> count=<n>`, contains one bounded line per active/stale slot, and ends with `PEERS_END`.
   - Each line includes full base/ESP-NOW MAC, status age, stream/SD/sync flags, and last Identify acknowledgement.
   - The ROS fleet manager polls at a low rate (for example 1 Hz) only through the wireless master session. Do not reuse the very large `REC STATUS` response as fleet discovery.

3. Targeted Identify command.
   - Host command: `IDENTIFY target=<device_id> duration_ms=<bounded> command_id=<u32>`.
   - For the master target, blink locally.
   - For a slave target, send a new versioned ESP-NOW `IdentifyCmdPacket` directly to that peer's observed ESP-NOW MAC.
   - Slave status v3 echoes `last_command_id`, `last_command_result`, and `identify_active`.
   - The master returns `IDENTIFY_OK` only after seeing the matching application-level status acknowledgement; otherwise return a bounded timeout/error code.

ESP-NOW send callbacks are not an application acknowledgement. Espressif documents send success at the MAC layer and explicitly does not guarantee application receipt; therefore the status echo is required before Studio reports success.

### LED Safety

No LED pin is currently defined in either sketch. Add compile-time board settings:

```c
#define IDENTIFY_LED_PIN ...
#define IDENTIFY_LED_ACTIVE_LEVEL LOW_OR_HIGH
#define IDENTIFY_MAX_DURATION_MS 5000
```

Identify must be non-blocking and driven from `millis()` state in the main loop. Never call `delay(duration_ms)` in the receive callback or acquisition loop. Restore the prior LED state after timeout. If the board has no safe user LED configuration, advertise no `identify` capability and return `identify_unavailable`; do not guess a pin that could conflict with SPI, DIO, or SD.

### Backward Compatibility

- Master accepts existing status v2 and new v3 by checking `version` and `packet_size`.
- Slave continues accepting legacy 2-byte commands, current `CmdPacket` v2, `FreqCmdPacket`, and `CfgCmdPacket`.
- Existing recording, scheduled start/stop, frequency, filter, and range packet layouts do not change.
- New Identify uses its own packet type and length so it cannot be misread as `SyncPacket` or `CmdPacket`.
- Keep `MAX_SLAVE_STATUS_SLOTS=6` for this milestone; surface `capacity_exceeded` instead of overwriting slot 0 when full. The current `rememberSlaveStatus()` fallback to slot 0 must be removed.

## Windows Relay and Startup Integration

### Modify: Relay

Modify `scripts/stepesp_tcp_udp_relay.py` from a dual-route object into:

- `DeviceRoute`: immutable `device_id`, current ESP host/port, stable local relay port, role, last identity confirmation, connection state;
- `RouteRegistry`: reconciles subnet scan candidates and identity replies, preserves stable local ports by device ID, and publishes registry revisions;
- `UdpRouter`: continues demultiplexing UDP by current source IP but resolves IP through `RouteRegistry`;
- `RegistryServer`: bounded localhost/WSL-facing NDJSON request/response API for `LIST` and change notifications.

Keep `StepEspRelay` as the per-device TCP forwarder. Its transport translation (`STARTED ... udp` to downstream TCP plus appended UDP records) remains valid.

Recommended local registry response:

```json
{"schema":"stepesp.relay_registry.1","revision":9,"routes":[
  {"device_id":"esp32:aabbccddeeff","role":"master","listen_port":5100,"state":"ready"},
  {"device_id":"esp32:112233445566","role":"slave","listen_port":5101,"state":"ready"}
]}
```

The registry must not expose a route as ready until `IDENTITY?` confirms it. Port assignment must persist for the relay process lifetime and remain attached to `device_id` if DHCP changes. A disconnected route remains in the registry as `unreachable`, allowing the ROS session and UI row to retain identity.

### Modify: Startup

Modify:

- `scripts/start_stepesp_wireless.ps1`
- `scripts/stop_stepesp_wireless.ps1`
- `scripts/run_opensim_live_link.ps1`
- `scripts/run_opensim_live_link_wsl.sh`
- `backend/launch/opensim_live_link.launch.py`

Remove the current "multiple stations is an error" branch. Start one relay registry and one `esp32_fleet_bridge` ROS process. Start OpenSim with `mapping_mode:=dynamic`, `model_path:=...`, and a configurable mapping-store path.

Retain a `-LegacyPairMode` switch for one milestone. It invokes the existing two-route arguments and two `esp32_bridge_node` processes unchanged. This is the rollback path for hardware sessions while fleet routing is validated.

### Relay Failure Containment

- One device connection task failing must not cancel `asyncio.gather()` for other routes.
- Use per-route bounded UDP queues and per-route drop counters.
- An unknown UDP source is quarantined and triggers identity reconciliation; it is never attached to an existing device based only on IP.
- A changed identity on a known IP closes that route and creates a new registry entry.
- Registry API failure leaves already-connected streams running; the fleet bridge reports discovery degraded.
- Relay discovery never sends recording or acquisition commands.

## ROS 2 Fleet Bridge

### New and Modified Components

Add:

- `backend/rehab_robotics_bridge/device_identity.py`
- `backend/rehab_robotics_bridge/esp32_transport.py`
- `backend/rehab_robotics_bridge/esp32_fleet_node.py`
- `backend/test/test_device_identity.py`
- `backend/test/test_esp32_fleet_node.py`
- `backend/test/test_stepesp_relay_registry.py`

Modify:

- `backend/rehab_robotics_bridge/esp32_bridge_node.py`
- `backend/setup.py`
- `backend/package.xml`
- `backend/launch/rehab_robotics.launch.py`
- existing ESP bridge/control tests

Refactor the current handshake, mixed text/binary scanner, range confirmation, frame conversion, and recording response logic into `Esp32DeviceSession`. Keep `Esp32BridgeNode` as a thin single-device legacy wrapper. `Esp32FleetNode` owns a dictionary of sessions keyed by `device_id`, watches relay registry revisions, and constructs/destroys sessions independently.

The fleet node:

- publishes canonical per-MAC topics;
- includes `device_id`, `mac`, and `role` in raw schema v2;
- publishes fleet and per-device health;
- owns the master recording/control services;
- forwards Identify to the master control session and returns only confirmed results;
- publishes legacy aliases from master and explicit `legacy_slave_id`.

Never put `body_segment` in this layer's authoritative state. Keep it only as a deprecated v1 compatibility field on alias raw messages until Studio no longer depends on it.

### Custom ROS Interfaces

Add to `rehab_robotics_interfaces`:

```text
msg/SensorSegmentMapping.msg
  string device_id
  string segment_id

srv/SetSensorMapping.srv
  string model_id
  uint64 expected_revision
  SensorSegmentMapping[] assignments
  bool persist_draft
  ---
  bool success
  string code
  string message
  uint64 revision
  string state

srv/ApplySensorMapping.srv
  string model_id
  uint64 expected_revision
  ---
  bool success
  string code
  string message
  uint64 applied_revision

srv/IdentifySensor.srv
  string device_id
  uint16 duration_ms
  ---
  bool success
  string code
  string message
  uint32 command_id
```

Use services because set/apply/identify are short request/response operations that require confirmation. Use topics for fleet, mapping, model, and solver status because they are continuous state streams. This matches ROS 2's documented interface semantics and the existing rosbridge `call_service` correlation flow.

Services:

- `/esp/identify`
- `/opensim/mapping/set`
- `/opensim/mapping/apply`

Existing `/esp/recording/set`, parameter services, calibration services, and visualizer service remain.

## Model Catalog and Mapping Ownership

### New Backend Modules

Add:

- `backend/rehab_robotics_bridge/opensim/model_catalog.py`
- `backend/rehab_robotics_bridge/opensim/mapping_store.py`
- `backend/rehab_robotics_bridge/opensim/orientation_set.py`
- `backend/test/test_opensim_model_catalog.py`
- `backend/test/test_opensim_mapping_store.py`
- `backend/test/test_opensim_orientation_set.py`

Modify:

- `backend/rehab_robotics_bridge/opensim_node.py`
- `backend/rehab_robotics_bridge/opensim/calibration.py`
- `backend/rehab_robotics_bridge/opensim/orientation_ik.py`
- `backend/rehab_robotics_bridge/opensim/opensim_orientation_ik.py`
- `backend/rehab_robotics_bridge/opensim_adapter.py`
- OpenSim launch and tests

### Model Identity and Segment Catalog

Compute:

```text
model_id = "sha256:" + sha256(exact .osim bytes)
```

The catalog enumerates `BodySet`, excluding Ground. A segment ID is the absolute component path, for example `/bodyset/femur_r`, not only the display name. This avoids collisions in more complex component trees.

For each body:

1. Prefer an existing IMU `PhysicalFrame`/`PhysicalOffsetFrame` attached to that body, especially the OpenSense convention `<bodyname>_imu`.
2. If absent, stage a deterministic identity-offset runtime `PhysicalOffsetFrame` before `initSystem()` and expose its path as the orientation frame.
3. If the pinned Python binding cannot add and connect that frame safely before initialization, mark the body `sensor_ready=false` and require a model-authored IMU frame in this milestone. Do not silently map to a joint offset frame.

The current demo model already contains `femur_r_imu` and `tibia_r_imu` attached to `/bodyset/femur_r` and `/bodyset/tibia_r`, so compatibility mappings resolve without generated frames.

OpenSense documentation treats each IMU as a Frame in the model and expects names such as `<bodyname>_imu`. The mapping catalog should show body/segment labels to the operator but give the solver the resolved IMU frame path.

Publish `/opensim/mapping/status` as versioned JSON `rehab.opensim_mapping.1`:

```json
{
  "schema": "rehab.opensim_mapping.1",
  "model": {
    "model_id": "sha256:...",
    "name": "rehab_lower_limb_skeleton_live_link",
    "path": "/home/.../model.osim"
  },
  "revision": 12,
  "applied_revision": 11,
  "state": "incomplete",
  "segments": [
    {
      "segment_id": "/bodyset/femur_r",
      "name": "femur_r",
      "sensor_frame": "/femur_r_imu",
      "sensor_ready": true
    }
  ],
  "assignments": [
    {
      "device_id": "esp32:aabbccddeeff",
      "segment_id": "/bodyset/femur_r",
      "connected": true,
      "valid": true
    }
  ],
  "issues": [
    {"code": "connected_device_unassigned", "device_id": "esp32:112233445566"}
  ]
}
```

Publish on startup, model/mapping/topology changes, and a low-rate heartbeat so current Humble rosbridge clients do not depend on transient-local QoS support.

### Mapping Validation

`SetSensorMapping` accepts the entire desired assignment set, not incremental row mutations. The backend validates it as one candidate:

- request `model_id` matches the loaded model;
- `expected_revision` matches to prevent two browser tabs from overwriting each other;
- every device ID is normalized and unique;
- every segment ID exists and is `sensor_ready`;
- every segment occurs at most once;
- unknown disconnected device IDs may be retained only if already present in persisted history; arbitrary new IDs are rejected;
- every currently connected fleet device is assigned before state can be `ready`;
- at least the model/solver-required minimum number of sensors is assigned;
- no mapping mutation occurs while recording finalization is being controlled only if it would interfere with the shared control session; acquisition itself remains independent.

Incomplete, non-conflicting candidates may be persisted as drafts so operator work is not lost. Conflicting/invalid candidates are rejected and never replace the persisted last valid draft.

`ApplySensorMapping` is transactional:

1. Revalidate desired mapping against current model and fleet.
2. Stage subscriptions, model frames, visualizer adapter, and N-sensor IK solver.
3. If staging fails, keep the prior applied mapping, solver, and calibration active; publish `apply_failed`.
4. If staging succeeds, atomically swap the applied mapping.
5. Clear calibration because the device-to-frame set changed.
6. Increment `applied_revision` and publish status.

### Persistence

Default to a configurable backend path such as:

```text
~/.rehab_robotics/sensor_mappings.json
```

Tests always inject a temporary path. Store:

```json
{
  "schema": "rehab.sensor_mapping_store.1",
  "models": {
    "sha256:...": {
      "model_name": "rehab_lower_limb_skeleton_live_link",
      "revision": 12,
      "legacy_slave_id": "esp32:112233445566",
      "assignments": {
        "esp32:aabbccddeeff": "/bodyset/femur_r",
        "esp32:112233445566": "/bodyset/tibia_r"
      }
    }
  }
}
```

Write to a sibling temporary file, flush/fsync where available, and atomically replace. Keep the previous file as a bounded `.bak`. On corrupt JSON, report `mapping_store_corrupt`, preserve the file for recovery, and start with an empty in-memory draft; do not overwrite corruption automatically.

Loading a model restores that model's candidate. If all segment paths still resolve, connected devices match, and no duplicates exist, auto-apply it. Reconnecting a device with the same MAC reattaches automatically without changing revision. A changed `.osim` file has a new hash, preventing stale segment mappings from silently crossing model revisions.

## Dynamic OpenSim Calibration and Solver

### Orientation Set Aggregation

Do not attempt an N-way `message_filters` synchronizer with one callback signature per sensor. Maintain one bounded latest-value cache per applied device ID:

```text
device_id -> {xyzw, source_timestamp_ns, arrival_monotonic, generation}
```

On a fixed-rate solve timer or after an input update:

- require every applied device to have a valid quaternion;
- require every device state to be live;
- require each generation to have advanced since the prior solve;
- require `max(source_timestamp) - min(source_timestamp) <= max_sensor_skew`;
- require every arrival age below `stale_timeout`;
- build an immutable orientation set ordered by resolved model frame path;
- stamp the solved pose with the oldest contributing source timestamp, preserving the current conservative behavior.

One stale/missing mapped sensor closes the IK output gate but does not stop acquisition, recording, other ROS topics, or Identify.

### Calibration Generalization

Change `CalibrationArtifact` from:

```text
master_xyzw
slave_xyzw
```

to:

```text
model_id
mapping_revision
known_pose
offsets_xyzw: device_id -> quaternion
frame_paths: device_id -> model frame path
sample_count_by_device
captured source interval
mean/max dispersion by device
```

The capture controller accepts complete immutable orientation sets. It performs antipode-aware means and dispersion checks independently for every mapped sensor. If any required sensor moves, becomes stale, or exceeds skew during capture, the candidate fails transactionally and a prior valid artifact remains active only if it matches the still-applied mapping revision.

Calibration capture is rejected while mapping state is not `active/ready`. Applying any different mapping clears the calibration and the existing `/opensim/joint_states` hard gate remains closed until a new capture succeeds.

### Official Orientation IK Generalization

Modify `OpenSimOrientationIkSolver` to accept:

```python
solve(
    orientations_xyzw: Mapping[str, Sequence[float]],  # keyed by device_id
    frame_paths: Mapping[str, str],
    calibration: CalibrationArtifact | None,
    ...
)
```

Build `TimeSeriesTableQuaternion` columns in deterministic applied mapping order, labeled by the resolved OpenSim IMU frame names/paths. Generalize `_make_quat_table()` and mounting-offset application from two values to N values. Keep one OpenSim Model/State/Solver owner in the dedicated `opensim_bridge` process.

The current Python fallback reconstructs a static `OrientationsReference` when buffered binding support is unavailable. Preserve that fallback for compatibility, but profile solve duration as sensor count grows. Do not fork one solver per sensor: orientation IK is one model-wide solve.

### Status Compatibility

Keep:

- `/opensim/joint_states`
- `/opensim/ik_status`
- `/opensim/calibration_status`
- `/opensim/status`
- `/opensim/calibration/capture`
- `/opensim/calibration/clear`
- `/opensim/visualizer/open`

Extend `/opensim/status` additively:

- keep `sensors.master` and `sensors.slave` compatibility aliases;
- add `mapped_sensors[]` keyed by `device_id`;
- add `model_id`, `mapping_revision`, `mapping_state`, and `required_sensor_count`;
- preserve visualization/calibration objects so the current Studio parser continues working.

Extend IK status with mapping provenance and skew, but do not change the existing validity fields. Existing JointState consumers need no change.

## React Studio Integration

### Add

- `rehab-robotics-studio/src/types/sensorMapping.ts`
- `rehab-robotics-studio/src/state/sensorMappingStore.ts`
- `rehab-robotics-studio/src/components/mapping/SensorMappingPanel.tsx`
- `rehab-robotics-studio/src/components/mapping/SensorRow.tsx`
- `rehab-robotics-studio/src/components/mapping/mappingValidation.ts`
- corresponding unit/component tests

### Modify

- `rehab-robotics-studio/src/data/RosbridgeDataSource.ts`
- `rehab-robotics-studio/src/data/DataSource.ts`
- `rehab-robotics-studio/src/data/appDataSource.ts`
- `rehab-robotics-studio/src/state/systemStore.ts`
- `rehab-robotics-studio/src/types/health.ts`
- `rehab-robotics-studio/src/components/dashboard/HealthPanel.tsx`
- `rehab-robotics-studio/src/components/dashboard/Dashboard.tsx`
- `rehab-robotics-studio/src/App.tsx`
- `rehab-robotics-studio/src/styles/app.css`

Add a dedicated `Sensor Mapping` workspace tab. Rows are keyed by `device_id`, never array index, IP, or role. Each row shows:

- role + shortened MAC;
- connected/ESP-NOW/stream health;
- assigned model segment;
- persisted-but-disconnected state;
- Identify busy/success/failure state.

Segment options come only from `/opensim/mapping/status.segments`. Disable a segment already selected by another row and still validate again in the backend. Show explicit global states: `loading model`, `incomplete`, `conflict`, `ready to apply`, `applying`, `active`, and `apply failed`.

The store separates:

```text
backendSnapshot   # authoritative desired/applied mapping and catalog
draftAssignments  # ephemeral UI edits
dirty             # draft differs from backend revision
requestState      # set/apply/identify pending results
```

On stale-revision rejection, replace `backendSnapshot`, preserve the user's draft separately, and ask them to review differences. Never report applied until the backend status publishes the returned revision.

### Rosbridge Contracts

Subscribe to:

- `/esp/status/fleet`
- `/opensim/mapping/status`
- existing OpenSim and legacy acquisition topics

Call:

- `/esp/identify` with `rehab_robotics_interfaces/srv/IdentifySensor`
- `/opensim/mapping/set`
- `/opensim/mapping/apply`

Use the existing request ID/pending-call mechanism in `RosbridgeDataSource`. Add strict runtime parsers for every JSON status boundary. Cap array lengths, string lengths, and issue counts so malformed ROS JSON cannot allocate unbounded browser state.

Keep the current master/slave raw frame path and `frameFromPair()` for graph compatibility. The mapping panel does not subscribe to every raw sensor stream; it consumes fleet health. Product OpenSim output continues to come from `/opensim/joint_states`, not browser quaternion math.

## Key Data Flows

### Discovery and Reconnect

```text
Slave sends ESP-NOW status with full identity
  -> master peer inventory marks MAC visible
  -> relay subnet scan receives IDENTITY? from current DHCP host
  -> relay binds device_id to route and stable local endpoint
  -> fleet bridge opens/reopens one device session
  -> canonical per-MAC topics and fleet status resume
  -> mapping store finds same device_id
  -> OpenSim cache reattaches it to the saved segment
  -> once all mapped inputs are fresh, calibration/IK gate may reopen
```

Reconnect does not rewrite the mapping revision. A device with a different MAC is a new device and remains unassigned even if it appears at the old IP.

### Identify

```text
Studio Identify click
  -> rosbridge call_service(id, device_id, duration)
  -> fleet bridge validates connected/capable target
  -> master TCP IDENTIFY command
  -> master local blink OR targeted ESP-NOW packet
  -> slave starts non-blocking blink and echoes command_id in status
  -> master replies only after matching status ack
  -> ROS service response correlated by rosbridge id
  -> Studio shows success/timeout for that row only
```

### Mapping Apply

```text
Studio edits draft
  -> SetSensorMapping(full candidate, expected revision)
  -> backend validates and atomically persists desired mapping
  -> mapping status says incomplete/ready
  -> ApplySensorMapping(expected revision)
  -> backend stages subscriptions + model frames + solver + visualizer
  -> atomic applied mapping swap
  -> calibration invalidated
  -> mapping status active, calibration UNCALIBRATED
  -> operator captures calibration
  -> N-sensor orientation sets feed official OpenSim IK
```

### Model Change

```text
new .osim loaded
  -> compute model_id and catalog
  -> stop publishing new IK solutions
  -> restore candidate for this exact model hash
  -> validate segment paths and connected device set
  -> auto-apply only if fully valid
  -> always require matching calibration
```

## Failure Containment

| Failure | Contained behavior | Recovery |
|---|---|---|
| One slave disappears | Its session/status becomes stale; other streams and SD recording continue; mapping is retained; IK gate closes if it was required. | Same MAC reconnect reattaches automatically. |
| New unassigned device appears | Fleet acquisition continues; mapping state becomes `incomplete`; no silent assignment. | Operator assigns and applies. |
| Duplicate segment request | Backend rejects whole candidate; prior desired/applied mapping remains. | Correct draft and retry. |
| Mapping store corruption | Publish explicit error and keep corrupt file; start empty without overwriting. | Restore `.bak` or save a reviewed new mapping. |
| Model segment removed/renamed | Restored candidate reports `segment_missing`; no auto-apply or calibration reuse. | Reassign against new catalog. |
| Apply-stage OpenSim error | Old applied solver/visualizer remains active; candidate reports failure. | Fix mapping/model and retry. |
| Identify packet lost | Service times out for that row; no false success; acquisition is untouched. | Retry; inspect ESP-NOW health. |
| LED unavailable/misconfigured | Firmware omits capability or returns explicit error. | Correct board configuration and reflash. |
| Relay registry down | Existing sessions remain; discovery status degrades. | Restart registry/relay without changing saved mapping. |
| DHCP address changes | Relay re-identifies and moves route; device ID/topic stay unchanged. | Automatic session reconnect. |
| Malformed firmware identity | Quarantine route; do not publish under guessed identity. | Firmware/transport repair. |
| One invalid quaternion | Drop for that device, mark mapping input invalid, stop new IK output; other acquisition remains. | Resume after valid complete orientation sets. |
| Calibration fails on one sensor | Candidate capture fails transactionally; matching prior calibration may remain only if mapping unchanged. | Stabilize all mapped sensors and recapture. |
| Native visualizer fails | Preserve current behavior: visualizer status fails independently; IK/acquisition continue. | Bounded adapter recreation or operator retry. |
| Native IK solve fails | Publish invalid status and no new JointState; do not hold values with a fresh stamp. | Reassemble/reset after bounded failures. |
| Recording finalization failure | Mapping/IK status remains observable; no mapping operation claims recording success. | Existing recording recovery path. |

## Compatibility and Migration Strategy

### Firmware

- Add new identity/peer/Identify commands; do not alter current Open Ephys handshake or record commands.
- Accept old and new ESP-NOW packet versions.
- Keep current two-sketch flashing workflow and topology tests.

### Relay and ROS

- Keep the current relay CLI arguments and `Esp32BridgeNode` executable.
- Add fleet-mode arguments/registry and a new `esp32_fleet_bridge` executable.
- Publish both canonical per-MAC topics and legacy aliases from fleet mode.
- Seed `legacy_slave_id` from the one slave used by the old startup path; never recalculate it from discovery order.

### OpenSim

- Keep `master_imu_topic`, `slave_imu_topic`, `master_frame`, and `slave_frame` launch parameters in `mapping_mode=legacy`.
- Add `mapping_mode=dynamic` as the new startup default only after canonical topics and mapping status pass integration tests.
- Keep all existing service/topic names and the current native visualizer control.
- Include compatibility aliases in `/opensim/status` so existing Studio health remains functional during UI migration.

### Studio

- Add mapping features without removing the current graph data source, toolbar calibration buttons, live knee output, or pair health.
- Switch HealthPanel from two hard-coded rows to fleet rows only after `/esp/status/fleet` is available; fall back to pair health when it is absent.
- Backend state wins after reload/reconnect; no browser-only mapping persistence.

### Removal Gate

Do not remove fixed contracts in this milestone. Mark them deprecated only after all of these pass:

1. one-master/one-slave legacy startup and tests;
2. one-master/N-slave discovery with stable per-MAC topics;
3. same-MAC reconnect after DHCP address change;
4. saved per-model mapping restore;
5. official calibration + IK + JointState through dynamic mapping;
6. recording start/stop/finalization with multiple slaves;
7. Studio and rosbridge end-to-end regression.

## Recommended Project Structure

```text
firmware/
|-- step_node/
|   |-- step_node.ino                       # modified master identity/peer/Identify
|   `-- step_espnow_protocol.h              # new versioned packet definitions
`-- step_node_slave/
    |-- step_node_slave.ino                 # modified slave identity/LED/ack
    `-- step_espnow_protocol.h              # identical protocol header

scripts/
|-- stepesp_tcp_udp_relay.py                # modified N-route registry
|-- start_stepesp_wireless.ps1              # modified fleet startup
`-- stop_stepesp_wireless.ps1               # modified fleet shutdown

backend/rehab_robotics_bridge/
|-- device_identity.py                      # new MAC normalization/contracts
|-- esp32_transport.py                      # new reusable session/parser
|-- esp32_bridge_node.py                    # modified legacy wrapper
|-- esp32_fleet_node.py                     # new dynamic session owner
|-- opensim_node.py                         # modified mapping/model authority
`-- opensim/
    |-- model_catalog.py                    # new model hash/body/frame inventory
    |-- mapping_store.py                    # new atomic per-model persistence
    |-- orientation_set.py                  # new N-sensor freshness/skew gate
    |-- calibration.py                      # modified N-sensor artifact
    |-- orientation_ik.py                   # modified generic solver contract
    `-- opensim_orientation_ik.py           # modified N-column official IK

rehab_robotics_interfaces/
|-- msg/SensorSegmentMapping.msg            # new
`-- srv/
    |-- SetSensorMapping.srv                # new
    |-- ApplySensorMapping.srv              # new
    `-- IdentifySensor.srv                  # new

rehab-robotics-studio/src/
|-- types/sensorMapping.ts                  # new transport/domain types
|-- state/sensorMappingStore.ts             # new draft vs authoritative state
|-- components/mapping/
|   |-- SensorMappingPanel.tsx              # new dedicated panel
|   |-- SensorRow.tsx                       # new stable-MAC row
|   `-- mappingValidation.ts                # new immediate UX checks
|-- data/RosbridgeDataSource.ts             # modified subscriptions/services
|-- data/appDataSource.ts                   # modified application commands
|-- state/systemStore.ts                    # modified fleet/OpenSim health
|-- types/health.ts                         # modified fleet status types
`-- App.tsx                                 # modified Sensor Mapping tab
```

## Dependency-Aware Build Order

### Phase 1: Identity and Targeted Identify

Build firmware identity, full-MAC status v3, non-blocking LED state, targeted packet/ack, and parser tests.

End-to-end test:

- query master and two simulated/physical slaves;
- prove unique full IDs;
- Identify each device independently;
- prove lost acknowledgement returns failure;
- prove sample/recording loop timing is unchanged.

### Phase 2: N-Route Relay and Canonical ROS Fleet Topics

Build relay route registry, reusable device session, fleet bridge, canonical topics/status, and legacy aliases.

End-to-end test:

- discover master plus at least two slaves in any DHCP order;
- observe three stable `/esp32/mac_*/imu` topics;
- power-cycle one slave and verify the same topic resumes;
- verify one failed route does not stop the others;
- run existing pair, recording, frequency, and range tests through aliases.

### Phase 3: Model Catalog and Persistent Mapping Contracts

Build custom interfaces, model hash/catalog, mapping store, validation, set/apply transactions, and status topic using fake adapter/solver.

End-to-end test:

- load the demo model and receive pelvis/femur/tibia-derived choices;
- reject duplicate segments;
- persist an incomplete draft;
- apply a complete mapping;
- restart backend and restore by exact model hash/MAC;
- change model bytes and prove old mapping does not silently apply.

### Phase 4: N-Sensor Calibration, Official IK, and Visualizer

Generalize orientation aggregation, calibration artifact, solver table, node status, and visualizer labels.

End-to-end test:

- feed deterministic 2-sensor fixtures and prove current knee result remains within tolerance;
- feed 3+ mapped orientations and verify deterministic table labels;
- stale one sensor and prove JointState stops while other topics continue;
- recapture after mapping change;
- open/update native visualizer without changing product JointState contract.

This phase needs deeper research if runtime IMU frames must be generated for bodies lacking model-authored `<body>_imu` frames, because the pinned OpenSim 4.5.2 Python binding behavior must be verified.

### Phase 5: Rosbridge and Studio Mapping Panel

Build parsers, mapping store, workspace tab, row actions, conflict/incomplete UX, and service calls.

End-to-end test:

- render rows in stable MAC order while status updates;
- Identify one row and correlate the correct response;
- prevent duplicate selection locally and verify backend rejection still works;
- apply mapping and wait for authoritative revision;
- reload the page and recover backend mapping;
- preserve existing Run/Rec/Calibrate/Clear/visualizer/live-angle workflows.

### Phase 6: Hardware Compatibility and Failure Matrix

Exercise master + multiple slaves at supported rates, recording, reconnect, malformed packets, relay restart, stale sensor, corrupt store, model mismatch, calibration, IK, and visualization.

Do not promote dynamic mode as default until all legacy and fleet tests pass from the same startup script.

## Architectural Patterns

### Stable Identity, Mutable Metadata

MAC-backed `device_id` is immutable; role, IP, connection state, and segment assignment are mutable projections. This prevents DHCP and remapping from changing topic identity.

### Desired vs Applied Configuration

Persist an editable desired mapping separately from the applied solver mapping. Apply through a staged transaction and retain the last known-good solver on failure.

### Backend Authority, UI Projection

Studio renders and edits state but does not decide whether a model segment exists, whether a mapping is valid, or whether calibration matches it. This makes restart, multi-tab use, and non-GUI ROS clients consistent.

### Latest Complete Orientation Set

Cache one newest sample per mapped sensor and solve only a complete, fresh, bounded-skew set. Do not queue unbounded N-sensor combinations.

### Compatibility Aliases

Publish canonical per-MAC topics once, then republish explicit master/legacy-slave aliases. Compatibility does not leak role labels back into the canonical data model.

## Anti-Patterns

### Using DHCP IP or Slot as Identity

**Why it fails:** DHCP order changes and the current firmware may reuse slot 0 when full.
**Instead:** Confirm the full firmware base MAC and attach transport routes to it.

### Truncating MAC to `slave_id`

**Why it fails:** The current low 32 bits are not the complete requested hardware identity and increase collision risk.
**Instead:** carry and normalize all 48 bits.

### Encoding Segment in ROS Topic Names

**Why it fails:** Remapping changes topic identity and invalidates subscribers/recordings.
**Instead:** canonical hardware topics plus backend mapping metadata.

### Letting Studio Persist the Only Mapping

**Why it fails:** Backend IK cannot recover independently; browser reloads/tabs can diverge.
**Instead:** backend atomic per-model persistence with optimistic revision checks.

### Choosing the First Discovered Slave

**Why it fails:** discovery/DHCP order is nondeterministic.
**Instead:** explicit persisted `legacy_slave_id`.

### Reporting ESP-NOW Send Success as Identify Success

**Why it fails:** link-layer delivery is not application execution.
**Instead:** command ID echoed in slave status and confirmed by the master.

### Mutating the Live Solver During Mapping Validation

**Why it fails:** a bad model frame or subscription can destroy the current valid path.
**Instead:** stage, validate, then atomically swap.

### Solving with "Latest N" Without Skew/Age Gates

**Why it fails:** a plausible pose can mix fresh and stale sensors.
**Instead:** complete-set generation, age, skew, and per-device generation checks.

## Scaling and Performance Considerations

The current firmware limit is one master plus six status slots and the AP allows eight clients. Design collections dynamically but validate this milestone at that concrete limit; do not claim arbitrary fleet size.

| Concern | Current two-device path | Target at master + six slaves |
|---|---|---|
| Firmware status traffic | Slave status every 10 ms | 6 x 100 Hz status may be significant; measure airtime and consider a lower health rate while retaining sample streams. |
| Windows UDP routing | Two IP queues | One bounded queue per identified route with per-route drops. |
| ROS publishers | Static two sets | Dynamic per-device publishers; topic count remains small. |
| Studio rendering | Two rows | Seven keyed rows; trivial if raw samples are not stored in React state. |
| OpenSim solve | Two orientation columns | One model-wide N-column solve; native solve latency is the likely bottleneck. |
| Synchronization | Latest pair | Complete N-device set with max skew/age; missing sensor becomes more likely. |

Measure:

- ESP-NOW status/send errors per peer;
- relay route reconnects and UDP drops per device;
- observed stream rates and frame ages;
- orientation-set skew and incomplete-set reasons;
- calibration dispersion per sensor;
- OpenSim solve duration and output age.

If N-sensor solve cannot keep up, retain only the newest complete orientation set and publish at a configured solve rate. Never allow latency to grow through an unbounded queue.

## Sources

### Repository Evidence

- `.planning/PROJECT.md` - active milestone requirements and compatibility constraints.
- `firmware/step_node/step_node.ino` - six MAC-keyed status slots, ESP-NOW peer registration, current command/status packet layouts, relay commands, and master TCP controls.
- `firmware/step_node_slave/step_node_slave.ino` - current truncated `slave_id`, 100 Hz status packet, master-peer registration, and direct TCP stream behavior.
- `scripts/stepesp_tcp_udp_relay.py` - two-route Windows NAT/UDP bridge and source-IP demultiplexing.
- `scripts/start_stepesp_wireless.ps1` - current single-slave discovery rejection, fixed two bridge processes, and fixed OpenSim topics.
- `backend/rehab_robotics_bridge/esp32_bridge_node.py` - role-derived topic/health/control ownership and raw JSON schema.
- `backend/rehab_robotics_bridge/opensim_node.py` - fixed role dictionary, two subscriptions, calibration gate, official IK, status, and visualizer isolation.
- `backend/rehab_robotics_bridge/opensim/calibration.py` and `opensim/opensim_orientation_ik.py` - two-sensor artifacts/table/solve APIs requiring generalization.
- `backend/rehab_robotics_bridge/opensim_adapter.py` - already-generic mapping dictionary at the visualizer boundary.
- `backend/launch/opensim_live_link.launch.py` - fixed master/slave parameters.
- `rehab-robotics-studio/src/data/RosbridgeDataSource.ts`, `state/systemStore.ts`, `types/health.ts`, and `components/dashboard/HealthPanel.tsx` - fixed subscriptions, pair caches, services, state, and UI rows.
- `examples/opensim_quaternion_demo.osim` - model-authored `femur_r_imu` and `tibia_r_imu` frames attached to model bodies.

### Authoritative External Sources

- Espressif ESP-IDF, ESP-NOW API: https://docs.espressif.com/projects/esp-idf/en/v5.2/esp32/api-reference/network/esp_now.html - peer MAC targeting, peer registration, and send semantics (HIGH).
- Espressif Arduino ESP32 network API: https://docs.espressif.com/projects/arduino-esp32/en/latest/api/network.html - retrieving full interface MAC addresses (HIGH).
- ROS 2 Humble interface concepts: https://docs.ros.org/en/humble/Concepts/Basic/Interfaces-Topics-Services-Actions.html - topics for continuous state and services for confirmed short operations (HIGH).
- ROS 2 Humble parameters: https://docs.ros.org/en/humble/Concepts/Basic/About-Parameters.html - node-bound parameter lifetime and lack of automatic persistence (HIGH).
- rosbridge v2 protocol: https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/ROSBRIDGE_PROTOCOL.md - subscribe and correlated `call_service`/`service_response` contracts (HIGH).
- OpenSim OpenSense overview: https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084203 - IMUs represented as model Frames and `<bodyname>_imu` naming (HIGH).
- OpenSim IMU Placer: https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53086410/Getting%2BStarted%2Bwith%2BIMU%2BPlacer - associating/registering sensors to body segments (HIGH).
- OpenSense real-time system: https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084280/WearableandReal-timeKinematicsEstimateswithOpenSense - variable number of additional IMUs (MEDIUM-HIGH; architecture precedent, not a drop-in library contract).

## Research Flags

- Verify runtime construction/connection of missing per-body `PhysicalOffsetFrame`s in the pinned OpenSim 4.5.2 Python environment. If unreliable, require model-authored IMU frames and expose unsupported bodies as `sensor_ready=false`.
- Measure ESP-NOW airtime and callback load with six slaves sending the current 10 ms status packet. The existing status rate may need reduction or separation from sample delivery.
- Verify which XIAO ESP32S3 LED is electrically safe and its active level for each deployed board revision before enabling Identify.
- Confirm base, AP, STA, and ESP-NOW MAC relationships on the actual boards; preserve all values in diagnostics even if they currently match.
- Define the biomechanically required minimum sensor set and allowed optional segments per loaded model. Software can enforce a declared rule but cannot infer clinical sufficiency from BodySet alone.
- Validate official orientation IK accuracy and latency with three or more sensors on the pinned OpenSim build; repository tests currently establish only the two-sensor path.

---
*Architecture research for: Rehab Robotics Studio v1.6 Multi-Sensor Bone Mapping*
*Researched: 2026-07-30*
