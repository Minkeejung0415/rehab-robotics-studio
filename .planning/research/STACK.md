# Stack Research

**Domain:** Dynamic multi-ESP-NOW discovery and per-model OpenSim sensor mapping in an existing ROS 2/React application
**Researched:** 2026-07-30
**Confidence:** HIGH for repository versions and extension points; MEDIUM for the final slave sample transport until the firmware-to-host multi-peer frame contract is chosen

## Recommendation

Extend the current stack in place. This milestone does **not** need a database, a new frontend state library, `roslibjs`, a ROS dynamic-types package, an XML parser, a new OpenSim version, or a new ESP-NOW library.

The smallest coherent change is:

1. Make the existing master bridge the authoritative device registry. Use the full 48-bit ESP-NOW interface MAC as the stable device key for the Master and every Slave.
2. Keep versioned inventory/model/status snapshots on the project's existing `std_msgs/msg/String` JSON control plane.
3. Add only two local ROS services to the existing `rehab_robotics_interfaces` package: one acknowledged Identify command and one atomic mapping-apply command.
4. Enumerate model segments inside the existing OpenSim 4.5.2 Python process, not in the browser. Return canonical OpenSim component paths plus a model content hash.
5. Persist only confirmed `model_id -> MAC -> segment_path` assignments in the Studio with Zustand 4.5.7's included `persist` middleware and browser `localStorage`.
6. Refactor the existing two-element OpenSim dictionaries, subscriptions, calibration inputs, and quaternion table construction into MAC-keyed collections. `rclpy.Node.create_subscription()`/`destroy_subscription()` are sufficient because every dynamic input is still the known `sensor_msgs/msg/Imu` type.
7. Extend the existing firmware command enum with a targeted, non-blocking Identify blink. Use the peer MAC already registered by the master and `esp_now_send(peer_mac, ...)`; do not add an LED or ESP-NOW dependency.

This preserves the validated Windows -> WSL2 Ubuntu 22.04 -> ROS 2 Humble -> OpenSim 4.5.2 runtime and keeps the browser out of filesystem/model parsing.

## Recommended Stack

### Core Technologies

| Technology | Repository version | Purpose in v1.6 | Why recommended |
|------------|--------------------|-----------------|-----------------|
| React | 18.3.1 | Multi-sensor mapping panel and validation UI | Already installed and validated. Dynamic device rows are ordinary keyed React components; no UI framework is needed. |
| Zustand | 4.5.7 resolved (`^4.5.5` manifest) | Live inventory/mapping state and per-model browser persistence | `zustand/middleware` already includes `persist`, `partialize`, schema `version`, and `migrate`. This adds no package and fits the existing store architecture. |
| TypeScript | 5.9.3 resolved (`^5.6.3` manifest) | MAC, inventory, model metadata, mapping, and command-result contracts | Existing build already type-checks transport boundaries. Use discriminated states for discovered/offline/conflict/incomplete/applied instead of adding a runtime schema library. |
| ROS 2 Humble + `rclpy` | Humble on Ubuntu 22.04; Python 3.10.12; Humble `rclpy` docs report 3.2.1 | Inventory publication, acknowledged services, dynamic IMU subscriptions, health, and launch | This is the deployed environment. The message types remain statically known, so ordinary runtime-created subscriptions work on Humble. |
| rosbridge server | Installed Humble package 2.0.7 | Browser subscriptions and service calls | The existing raw WebSocket implementation already performs `subscribe`, `unsubscribe`, `call_service`, and `service_response`. Keep that code and add IDs for dynamic subscriptions. |
| OpenSim Python | 4.5.2 (`4.5.2-2025-05-03-6a4c6ec41`) | Load the active `.osim`, enumerate bodies/frames, validate mappings, calibrate, and solve orientation IK | Already installed and validated in `/home/justi/.micromamba/envs/rehab-opensim`. `Model.getBodySet()` and Component paths are the authoritative model vocabulary. Do not parse model XML separately. |
| Arduino ESP32 core | 3.3.10 from `logs/arduino_build_master_current/build.options.json` | Stable MAC discovery, targeted peer command, non-blocking LED timer | The current sketches already register ESP-NOW peers by full source MAC and send unicast packets. The new command is a small protocol extension, not a library change. |
| Firmware contract | Existing firmware 1.8.0; bump the peer/status command schema deliberately | Full-MAC identity, Master identity, peer presence, Identify request/ack | Both sketches already share `CMD_MAGIC`, command enums, and versioned `SlaveStatusPacket`. Update sender/receiver structs together and retain explicit version rejection. |

### Supporting Libraries and Interfaces

| Library / interface | Version | Purpose | When to use |
|---------------------|---------|---------|-------------|
| `zustand/middleware` | Included in Zustand 4.5.7 | Persist confirmed mappings to `localStorage` | Persist a versioned `mappingsByModelId` slice only. Never persist live age, online state, service requests, calibration state, or topic handles. |
| Python `hashlib`, `json`, `pathlib` | Python 3.10 standard library | Model SHA-256 identity, versioned snapshot JSON, canonical path handling | Compute SHA-256 over the `.osim` bytes in WSL after a successful model load. No package installation is required. |
| `sensor_msgs/msg/Imu` | ROS 2 Humble | Per-MAC orientation input to OpenSim | Continue the existing native topic contract. Use MAC-derived ROS-safe topic tokens; preserve the canonical colon-delimited MAC in metadata. |
| `std_msgs/msg/String` | ROS 2 Humble | Device inventory, model metadata, aggregate health/status | Matches the current JSON-through-rosbridge pattern and permits versioned snapshots without forcing frontend-generated ROS bindings. Publish complete snapshots, not an event-only stream. |
| `rehab_robotics_interfaces/srv/IdentifyDevice` | New local interface; package version should advance from 0.1.0 | Reliable `mac + duration_ms -> success + message` request/response | Use for the operator Identify action. A service result must mean the master accepted a known, currently reachable full MAC and received the firmware-level acknowledgement policy chosen for the command. |
| `rehab_robotics_interfaces/srv/ApplySensorMapping` | New local interface; package version should advance from 0.1.0 | Atomically apply one complete model mapping | Request should carry `model_id` and parallel arrays or local `DeviceMapping[]`; response should reject stale model IDs, duplicate segments, unknown MACs/topics, and missing model frames as one transaction. |
| Existing OpenSim classes | OpenSim 4.5.2 | `Model`, `BodySet`, `PhysicalFrame`, `TimeSeriesTableQuaternion`, `OrientationsReference`, `InverseKinematicsSolver` | Generalize current hard-coded Master/Slave adapters. No OpenSim API family needs to be added. |
| Existing Arduino/ESP-IDF APIs | Arduino core 3.3.10 | `WiFi.softAPmacAddress()`, receive `src_addr`, `esp_now_send(peer_addr, ...)`, `millis()`, `digitalWrite()` | Use the MAC for the interface that actually participates in ESP-NOW: AP MAC for the Master AP interface and received source MAC for Slaves. |

### Local ROS Interface Shape

Prefer local typed services for commands and versioned JSON snapshots for state.

Illustrative service definitions:

```text
# rehab_robotics_interfaces/srv/IdentifyDevice.srv
string mac
uint32 duration_ms
---
bool success
string message

# rehab_robotics_interfaces/msg/DeviceMapping.msg
string mac
string imu_topic
string segment_path

# rehab_robotics_interfaces/srv/ApplySensorMapping.srv
string model_id
DeviceMapping[] mappings
---
bool success
string message
```

If avoiding a new local message is important, `ApplySensorMapping.srv` may instead use three equal-length `string[]` fields. Do not send an opaque mapping JSON string through the service: the local interface package already exists precisely to give ROS commands a typed boundary.

Recommended state topics:

```text
/esp/devices              std_msgs/msg/String  rehab.esp_inventory.1
/opensim/model_metadata   std_msgs/msg/String  rehab.opensim_model.1
/opensim/mapping_status   std_msgs/msg/String  rehab.opensim_mapping.1
```

Each inventory row should include at minimum:

```text
mac, role, online, last_seen_ms, imu_topic, connection_state,
firmware_version, identify_state, last_error
```

Use a canonical MAC string such as `AA:BB:CC:DD:EE:FF` everywhere outside ROS names. For a ROS topic token, use a reversible lowercase form such as `aa_bb_cc_dd_ee_ff`:

```text
/esp32/by_mac/aa_bb_cc_dd_ee_ff/imu
/esp/status/by_mac/aa_bb_cc_dd_ee_ff
```

Do not use the current 32-bit `slave_id` as identity. It is only the low 32 bits of `ESP.getEfuseMac()` and is needlessly collision-prone when the full peer MAC is already available.

## Exact Integration Points

### Firmware

| File | Required change | Stack impact |
|------|-----------------|--------------|
| `firmware/step_node/step_node.ino` | Expose the Master's ESP-NOW-interface MAC; retain every active peer's full MAC; add host `IDENTIFY` handling; send the identify command only to the selected peer; report an explicit accepted/unknown/stale result. | No dependency. Extend `CONTROL_RESPONSE_PREFIXES` in the bridge for the new reply. |
| `firmware/step_node_slave/step_node_slave.ino` | Add the matching command enum/packet handling and a non-blocking LED-off deadline; expose identify state/token in status if used for application acknowledgement. | No `FastLED`, NeoPixel, timer, or RTOS library. Use existing Arduino/FreeRTOS primitives. |
| Both sketches | Bump the command/status version when packet layout changes and keep exact packet-size checks. | Prevents mixed firmware from being interpreted as current. |

Espressif documents that `esp_now_send(peer_addr, ...)` targets one registered MAC, but its send callback only confirms MAC-layer delivery, not application receipt. For a trustworthy Studio result, include a request token in the command and echo it in the Slave's next status/ack; otherwise label the response “command sent,” not “device identified.”

### ROS acquisition and discovery

| File | Required change | Stack impact |
|------|-----------------|--------------|
| `backend/rehab_robotics_bridge/esp32_bridge_node.py` | Replace pair-only cached health with a MAC-keyed registry; parse full peer status; publish inventory snapshots; expose Identify service; publish native `Imu`/health topics by MAC. | Reuse `asyncio`, `json`, `sensor_msgs`, and the existing control-command queue. |
| `backend/rehab_robotics_bridge/status_node.py` | Replace fixed `master`/`slave` aggregation with a bounded MAC-keyed snapshot and per-device TTL. | No library. Do not leave disconnected devices permanently online from the last cached message. |
| `backend/launch/rehab_robotics.launch.py` and `scripts/start_stepesp_wireless.ps1` | Remove fixed two-device assumptions from process/topic arguments. | No launch plugin. Keep ROS discovery and device discovery distinct. |
| `scripts/stepesp_tcp_udp_relay.py` | If direct TCP/UDP slave streams remain the high-rate data path, generalize its fixed two endpoints to an `N`-endpoint table and maintain MAC-to-endpoint metadata. | Python standard library is sufficient. Do not add ZeroMQ, MQTT, or a service-discovery package. |

The current firmware already holds several peer snapshots, including latest quaternion data, while the host stack exposes one fixed Slave. The exact high-rate host transport is the one remaining design gate:

- **Preferred if firmware can forward peer-native frames without destabilizing acquisition:** one Master connection carries peer MAC with each Slave sample, and the ROS bridge fans out per-MAC `Imu` topics.
- **Fallback if each Slave must keep its direct TCP/UDP stream:** the Windows relay manages `N` endpoints and binds the stream to the full MAC learned through the control plane.

Do not infer identity from DHCP address. IP is a transport endpoint and may change; MAC is the mapping key.

### OpenSim model metadata and dynamic routing

| File | Required change | Stack impact |
|------|-----------------|--------------|
| `backend/rehab_robotics_bridge/opensim_node.py` | Load model metadata once; compute `model_id`; enumerate segments; replace `_ROLES`, two sensor states, two callbacks, and two subscription attributes with MAC-keyed dictionaries; apply mappings atomically; destroy/recreate subscriptions when the applied mapping changes. | Existing `rclpy` APIs are enough. Reuse the current `_IMU_QOS`. |
| `backend/rehab_robotics_bridge/opensim/opensim_orientation_ik.py` | Replace the two-column `RowVectorQuaternion(2)` and Master/Slave parameters with ordered collections derived from the applied mapping. | Existing OpenSim classes. Preserve a deterministic sensor order for table labels and residual reporting. |
| `backend/rehab_robotics_bridge/opensim/calibration.py` | Key samples/offsets by MAC plus segment path and invalidate artifacts when `model_id` or applied mapping generation changes. | No library. Calibration from one mapping must never be reused under another. |
| `backend/rehab_robotics_bridge/opensim_adapter.py` | Resolve canonical segment/body paths to the model frame used for visualization/IK and reject missing/ambiguous components. | Existing `Model.getComponent()` and frame down-casts. |
| `backend/launch/opensim_live_link.launch.py` | Retain `model_path`, remove fixed Master/Slave topic/frame arguments once mapping service owns runtime routing. | Keep launch configuration for startup defaults only. |

Model metadata should be produced only after `OpenSim.Model(model_path)` succeeds:

```text
model_id       = "sha256:" + SHA256(osim_file_bytes)
model_name     = model.getName()
segments       = each BodySet item's canonical absolute component path
display_name   = body.getName()
```

Store the canonical body/segment path as the mapping value. At apply time, resolve the actual orientation target frame:

1. Prefer an existing OpenSense-compatible sensor frame/IMU associated with that body.
2. Otherwise use the body `PhysicalFrame` with the existing reference-pose mounting-offset correction.
3. Reject mappings whose frame cannot be resolved; do not silently fall back to a similarly named component.

OpenSense expects sensor observations to correspond to Frames in the model and commonly names them `<bodyname>_imu`. Therefore the UI vocabulary can be model bodies, but the backend must explicitly resolve and report the frame actually tracked.

### Studio

| File | Required change | Stack impact |
|------|-----------------|--------------|
| `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` | Add inventory/model/mapping subscriptions, Identify and Apply service calls, subscription IDs, and matching unsubscribe messages. | Keep direct WebSocket protocol; do not install `roslibjs`. |
| `rehab-robotics-studio/src/data/appDataSource.ts` | Expose discovery/mapping controls separately from sample `DataSource`; do not collapse unavailable ROS into persisted mock mappings. | No library. |
| `rehab-robotics-studio/src/state/` | Add a dedicated sensor-mapping store using `persist`; keep current `systemStore` focused on runtime status. | Use `zustand/middleware`, already installed. |
| `rehab-robotics-studio/src/types/` | Add full transport-boundary types and canonical MAC normalization/validation helpers. | TypeScript only; no validation package is warranted for these small closed schemas. |

Persisted store pattern:

```typescript
persist(
  (set) => ({
    mappingsByModelId: {},
    // actions...
  }),
  {
    name: 'rehab-sensor-mappings',
    version: 1,
    partialize: (state) => ({
      mappingsByModelId: state.mappingsByModelId,
    }),
    migrate: (persisted, version) => {
      // Explicit future schema migration.
      return persisted
    },
  },
)
```

On hydration or reconnect:

1. Wait for current model metadata.
2. Select only the entry whose `model_id` exactly matches.
3. Normalize and match full MACs.
4. Remove assignments whose segment paths are absent from the current metadata.
5. Detect duplicates/incompleteness locally.
6. Call `ApplySensorMapping`.
7. Mark mappings applied only after backend success.

The backend remains authoritative for the active mapping. `localStorage` is a remembered operator preference, not proof that OpenSim is currently routed.

## Installation

No new third-party installation is recommended.

The only build-system addition is generating the new local services:

```cmake
# rehab_robotics_interfaces/CMakeLists.txt
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/ProcessingBlockUpdate.msg"
  "msg/DeviceMapping.msg"
  "srv/IdentifyDevice.srv"
  "srv/ApplySensorMapping.srv"
  DEPENDENCIES std_msgs
)
```

Rebuild and source the interfaces before the Python backend and before starting rosbridge:

```bash
source /opt/ros/humble/setup.bash
colcon build --packages-select rehab_robotics_interfaces rehab_robotics_bridge
source install/setup.bash
```

No `npm install` should be necessary. Import persistence from the installed package:

```typescript
import { persist } from 'zustand/middleware'
```

## Alternatives Considered

| Recommended | Alternative | When to use the alternative |
|-------------|-------------|-----------------------------|
| Zustand `persist` + browser `localStorage` | Backend JSON file | Use a backend file only if mappings must be shared across browsers/operators or survive browser storage clearing. If added later, use Python stdlib JSON plus atomic replace; SQLite is still unnecessary. |
| Full-MAC inventory topic + typed command services | ROS parameters for the entire mapping | Parameters can hold string arrays and are useful for launch defaults, but they do not model device liveness and make an acknowledged multi-object mapping transaction awkward. |
| Local custom services | JSON command topic with request IDs | A command topic is acceptable only if generating local services becomes operationally impossible. It must then include correlation IDs, timeout, idempotency, and an acknowledgement topic. |
| Existing raw rosbridge client | `roslibjs` | Add `roslibjs` only if the frontend expands into broad ROS graph introspection/actions and maintaining the small protocol client is demonstrably more expensive. It brings no needed capability for this milestone. |
| OpenSim API enumeration | Parse `.osim` XML in browser or Python XML | XML parsing is acceptable only for an offline recovery/inspection tool when OpenSim cannot load. It must not define the selectable runtime model vocabulary. |
| Canonical body/component path | Display name or array index | Display names are for UI only. Array indices and model ordering are not persistence identities. |
| Dynamic subscriptions inside one OpenSim node | Restart one node per mapping | Process restart may be retained as a recovery path, not the normal Apply action. Runtime subscription replacement is simpler and preserves status/service continuity. |

## What NOT to Add

| Avoid | Why | Use instead |
|-------|-----|-------------|
| SQLite, IndexedDB wrapper, Supabase, or another database | The data is a small local map keyed by model hash and MAC. A database adds migrations, ownership, and deployment work with no milestone value. | Zustand `persist`/`localStorage`; optionally stdlib atomic JSON later. |
| `roslibjs` | The project already implements the required rosbridge operations and session-safety behavior. Replacing it creates regression risk without adding a needed feature. | Extend `RosbridgeDataSource.ts`. |
| ROS 2 dynamic types/introspection subscription packages | Every dynamic topic is still `sensor_msgs/msg/Imu`; only topic names/count vary. Humble can create ordinary subscriptions at runtime. | `create_subscription`/`destroy_subscription`. |
| `message_filters` solely for mapping | The current solver already owns freshness/calibration behavior; variable sensor sets need an explicit keyed freshness window, not a fixed compile-time synchronizer graph. | A bounded MAC-keyed latest-sample barrier with source timestamp/skew checks. |
| A second `.osim` parser | It can disagree with what OpenSim actually loads and cannot resolve runtime component/frame semantics safely. | OpenSim `Model`, `BodySet`, and Component APIs. |
| Upgrade to OpenSim 4.6/C++ for v1.6 | v1.5 deliberately selected and validated the 4.5.2 Python path. Multi-device collection generalization does not require a solver-platform migration. | Generalize the existing 4.5.2 adapter. |
| MQTT, mDNS/Bonjour, ZeroMQ, WebRTC, or a ROS discovery server | ESP-NOW discovery already occurs at the Master, and ROS DDS discovery already exists. These introduce a second discovery truth. | Publish the Master's MAC-keyed inventory through ROS. |
| IP address as device identity | DHCP order changes, especially in the current Windows/WSL relay topology. | Full ESP-NOW interface MAC. |
| 32-bit `slave_id` as device identity | It truncates the hardware identity even though the full source MAC is available. | Canonical 48-bit MAC string/bytes. |
| `FastLED`, NeoPixel, or a timer library for Identify | Identify is one onboard LED and a deadline. Extra firmware libraries enlarge the compatibility surface. | `LED_BUILTIN`/board pin plus `millis()` or an existing FreeRTOS timer. |
| Persisting the active mapping only in ROS parameters | ROS parameter lifetime is tied to the node unless the application implements persistence. | Studio persistence keyed by backend-provided model hash, followed by acknowledged reapply. |
| One topic subscription per device in the browser | It sends high-rate sensor data through JSON and makes UI cost scale with sensor count. | Browser subscribes to inventory/health/status; OpenSim subscribes to native IMU topics inside ROS. |

## Stack Patterns by Variant

**If the Master can forward every peer sample with its MAC over the existing host connection:**

- Use one hardware ingress plus a MAC-keyed fan-out in `esp32_bridge_node.py`.
- Keep Windows/WSL relay topology constant as sensor count grows.
- This is the preferred operational shape, subject to a phase-specific transport contract and throughput test.

**If each Slave must retain an independent TCP/UDP sample stream:**

- Generalize `stepesp_tcp_udp_relay.py` and the PowerShell launcher to an endpoint table.
- Correlate each endpoint to the full MAC from a firmware handshake/inventory record before publishing.
- Never persist or map by discovered IP.

**If mappings must be shared among multiple Studio browsers:**

- Move the same versioned mapping document to the backend.
- Use Python stdlib JSON with write-temp, `fsync`, and atomic `os.replace()` under a configurable WSL path.
- Keep the browser cache as a convenience only; still do not add SQLite until concurrent writers or query requirements exist.

**If a loaded model has explicit `<body>_imu` frames:**

- Present body segment labels but report the resolved IMU frame path in model metadata.
- Track that frame after validating it belongs to the selected body.

**If a model has bodies but no explicit IMU frames:**

- Use the body `PhysicalFrame` as the IK observation target after the existing mounting-offset calibration transforms device orientation into body orientation.
- Fail closed if the current 4.5.2 binding cannot construct the required reference labels for that path; do not create an unpersisted, silently modified model in the browser.

## Version Compatibility

| Package/platform | Compatible with | Notes |
|------------------|-----------------|-------|
| React 18.3.1 | Zustand 4.5.7; TypeScript 5.9.3 resolved | Current lockfile. No React upgrade is required. |
| Zustand 4.5.7 | `persist` middleware and default `localStorage` JSON storage | Use `version`, `migrate`, and `partialize` from the included middleware. |
| Vite 5.4.21 resolved | Current Node environment and existing build | Workspace `#` path remains a reason to use the existing build/preview launch pattern. |
| ROS 2 Humble | Ubuntu 22.04, Python 3.10.12 | Keep generated interfaces and backend built/sourced in the same Humble overlay. |
| rosbridge server 2.0.7 | Rosbridge v2 JSON operations | Custom local service types must be installed and sourced before rosbridge starts. Give every dynamic browser subscription a unique ID and unsubscribe it explicitly. |
| OpenSim 4.5.2 Python | Existing `rehab-opensim` micromamba environment and WSL runner | Do not import it into native Windows Python. Model paths are WSL paths and must be consumed by the backend. |
| Arduino ESP32 core 3.3.10 | Current XIAO ESP32S3 build | Update both sketches together. Do not copy callback signatures from older Arduino core examples. |
| Firmware command/status v2 | Current packet-size/version checks | Adding Identify fields/commands requires a deliberate compatible extension or version bump; mixed firmware must surface as incompatible. |
| MAC topic slug | ROS name grammar | Colons are metadata only; replace them with underscores for topic path tokens and preserve reversible canonicalization. |

## Validation Gates for Roadmap

1. Verify the Master publishes its actual ESP-NOW interface MAC and that each Slave inventory MAC exactly matches the receive callback's six-byte source address.
2. Connect at least two Slaves whose DHCP addresses change and prove mappings restore by MAC, not IP or row order.
3. Load two `.osim` files with the same filename but different bytes and prove they receive different `model_id` values.
4. Enumerate a model with explicit `_imu` frames and one without them; record the selected segment path and resolved tracking frame.
5. Apply a mapping while running and prove old subscriptions are destroyed, new subscriptions are active once, calibration is invalidated, and no obsolete callback updates state.
6. Reject duplicate segment assignment, unknown MAC, stale `model_id`, missing frame, and incomplete required mapping as one atomic failure.
7. Restart rosbridge/backend and prove the Studio waits for model metadata before reapplying persisted mappings.
8. Issue Identify to Master, each Slave, an offline MAC, and an unknown MAC; prove the LED timer never blocks sampling and results distinguish acknowledged, sent-only, stale, and failed.
9. Run the multi-sensor path entirely under the existing Windows/WSL/Humble/OpenSim 4.5.2 launcher before considering any dependency upgrade.

## Sources

### Repository evidence

- `rehab-robotics-studio/package.json` and `package-lock.json` - React, Zustand, TypeScript, Vite, and YAML versions.
- `backend/package.xml`, `backend/setup.py`, and `rehab_robotics_interfaces/CMakeLists.txt` - current Humble Python package and local ROS interface generator boundary.
- `backend/rehab_robotics_bridge/esp32_bridge_node.py` - fixed Master/Slave health, existing control queue, `sensor_msgs/Imu`, and JSON status topics.
- `backend/rehab_robotics_bridge/opensim_node.py` - two fixed subscriptions and two sensor states.
- `backend/rehab_robotics_bridge/opensim/opensim_orientation_ik.py` - OpenSim 4.5.2 decision and two-column quaternion table.
- `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` - direct rosbridge operations and fixed pair subscriptions.
- `firmware/step_node/step_node.ino` and `firmware/step_node_slave/step_node_slave.ino` - full peer MAC slots, unicast peer registration, versioned packets, lower-32-bit `slave_id`, and command enum.
- `logs/arduino_build_master_current/build.options.json` - Arduino ESP32 core 3.3.10.
- Live WSL inspection on 2026-07-30 - Python 3.10.12, `ros-humble-rosbridge-server` 2.0.7, and OpenSim `4.5.2-2025-05-03-6a4c6ec41`.

### Primary documentation

- Zustand persist middleware (Context7 `/pmndrs/zustand`, official repository docs): https://github.com/pmndrs/zustand/blob/main/docs/reference/integrations/persisting-store-data.md
- ROS 2 Humble `rclpy` API: https://docs.ros.org/en/ros2_packages/humble/api/rclpy/index.html
- ROS 2 Humble parameter lifetime and runtime parameter behavior: https://docs.ros.org/en/humble/Concepts/Basic/About-Parameters.html
- Rosbridge v2 protocol, including subscription IDs, unsubscribe, and service calls: https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/ROSBRIDGE_PROTOCOL.md
- OpenSim 4.5 Model API (`Model(filename)`, `getBodySet()`, component model): https://opensim-org.github.io/opensim-moco-site/docs/1.3.0/html_user/classOpenSim_1_1Model.html
- OpenSense model/frame naming and sensor-to-body mapping: https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084203/OpenSense+-+Kinematics+with+IMU+Data
- Espressif ESP-NOW API (`esp_now_send(peer_addr, ...)`, peer MAC/interface, acknowledgement limitation): https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/network/esp_now.html
- Arduino-ESP32 ESP-NOW peer API: https://docs.espressif.com/projects/arduino-esp32/en/latest/api/espnow.html

---
*Stack research for: Rehab Robotics Studio v1.6 Multi-Sensor Bone Mapping*
*Researched: 2026-07-30*
