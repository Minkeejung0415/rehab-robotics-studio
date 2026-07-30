# Phase 20: Full Identity and Confirmed Identify - Pattern Map

**Mapped:** 2026-07-30  
**Files analyzed:** 10 likely new/modified files  
**Analogs found:** 9 / 10

## Scope Translation

Phase 20 must satisfy:

- **ID-01:** carry a verified full 48-bit base identity for the Master and every discovered Slave, with role, IP, STA/AP, and ESP-NOW transport MAC kept as separate metadata.
- **ID-02:** use `esp32:aabbccddeeff` as the stable identity/topic key instead of DHCP address, discovery slot, role, or the deprecated low-32-bit `slave_id`.
- **ID-03:** target exactly one full MAC, clamp Identify to 1-5 seconds (3-second default), require an application ACK correlated by command ID, and report confirmed, sent-unconfirmed, timeout, offline, unsupported, rejected, and invalid-target outcomes without blocking acquisition or recording.

The likely implementation surface is both firmware roles, the Windows TCP/UDP relay, the ROS bridge and typed service contract, and their existing hardware-free contract tests. Phase 21 still owns the N-route fleet lifecycle; Phase 20 should establish identity-confirmed route/topic keys and additive compatibility seams without building the full fleet manager.

## File Classification

| New/Modified File | Requirement | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|---|
| `firmware/step_node/step_node.ino` | ID-01, ID-03 | controller | event-driven + request-response | Existing `SlaveStatusPacket`, `SlaveStatusSlot`, ESP-NOW receive/send, and `handleLine()` in the same file | exact |
| `firmware/step_node_slave/step_node_slave.ino` | ID-01, ID-03 | controller | event-driven + streaming | Existing versioned command/status packets and deferred recording flags in the same file | exact |
| `scripts/stepesp_tcp_udp_relay.py` | ID-01, ID-02, ID-03 | service/route | streaming + request-response | Existing `StepEspRelay` session ownership and `UdpRouter` isolation | role-match |
| `backend/rehab_robotics_bridge/esp32_bridge_node.py` | ID-01, ID-02, ID-03 | provider/service | streaming + request-response | Existing acknowledged control service, health JSON, and mixed control/binary parser | exact |
| `rehab_robotics_interfaces/srv/IdentifyDevice.srv` (new, inferred) | ID-03 | model | request-response | No existing custom service; closest schema style is `msg/ProcessingBlockUpdate.msg` | no analog |
| `rehab_robotics_interfaces/CMakeLists.txt` | ID-03 | config | transform/build | Existing `rosidl_generate_interfaces(...)` block | exact |
| `scripts/start_stepesp_wireless.ps1` | ID-02 | config/route | batch + request-response | Existing DHCP scan and fixed Master/Slave relay launch | partial |
| `backend/test/test_stepesp_firmware_topology.py` | ID-01, ID-03 | test | batch/static analysis | Existing paired-firmware source contract tests | exact |
| `backend/test/test_esp32_controls.py` | ID-01, ID-03 | test | request-response | Existing ROS-free bridge import, ACK, timeout, and state-retention tests | exact |
| `backend/test/test_stepesp_udp_relay.py` | ID-02, ID-03 | test | streaming + request-response | Existing `IsolatedAsyncioTestCase` relay/router fixture | exact |

`backend/package.xml` already depends on `rehab_robotics_interfaces` (line 18), and `rehab_robotics_interfaces/package.xml` already declares the ROSIDL generator/runtime. A primitive-only Identify service should not require new package dependencies.

## Pattern Assignments

### `firmware/step_node/step_node.ino` (controller, event-driven/request-response)

**Analog:** existing packet definitions and MAC-keyed peer slots in this file.

**Versioned packed packet pattern** (lines 669-690):

```cpp
#pragma pack(push, 1)
struct CmdPacket {
  uint8_t magic;
  uint8_t cmd;
  uint8_t version;
  uint8_t flags;
  int64_t start_at_time_us;
  int64_t stop_at_time_us;
  char session_id[CMD_SESSION_ID_LEN + 1];
};
#pragma pack(pop)
```

Copy this style for additive `IdentityPacket`, `IdentifyRequestPacket`, and `IdentifyAckPacket`: packed structs, dedicated magic/type, explicit version, and explicit `packet_size`. Use fixed-width fields and copy the full six MAC bytes; do not serialize identity through `uint32_t slave_id`.

**Exact peer identity and unicast pattern** (lines 760-797):

```cpp
memcpy(peer.peer_addr, s->mac, 6);
peer.channel = ESPNOW_WIFI_CHANNEL;
peer.ifidx = wifi_soft_ap ? WIFI_IF_AP : WIFI_IF_STA;
peer.encrypt = false;
...
if (g_slave_status[i].used &&
    memcmp(g_slave_status[i].mac, info->src_addr,
           sizeof(g_slave_status[i].mac)) == 0) {
  slot = i;
}
```

Identify routing should resolve one slot by all six bytes and call `esp_now_send()` for that slot only. Do not reuse `espNowSendToSlaves()` because it intentionally fans out to every active peer.

**Current guarded receive pattern to tighten** (lines 819-825):

```cpp
if (len >= (int)sizeof(SlaveStatusPacket) && data[0] == SLAVE_STATUS_MAGIC) {
  const SlaveStatusPacket *status = (const SlaveStatusPacket *)data;
  if (status->version == SLAVE_STATUS_VERSION &&
      status->packet_size == sizeof(SlaveStatusPacket))
    rememberSlaveStatus(info, status);
}
```

For the new schema, use `len == sizeof(Packet)` as well as matching `version` and `packet_size`. The phase decision requires exact-size rejection; the existing `len >=` is not sufficient for new identity/Identify packets.

**Status projection pattern** (lines 1928-1945):

```cpp
const SlaveStatusPacket &s = g_slave_status[i].status;
Serial.printf(
  "SLAVE_STATUS slot=%d slave_id=%08lx "
  "mac=%02X:%02X:%02X:%02X:%02X:%02X age_ms=%lu ",
  i, (unsigned long)s.slave_id,
  g_slave_status[i].mac[0], g_slave_status[i].mac[1],
  g_slave_status[i].mac[2], g_slave_status[i].mac[3],
  g_slave_status[i].mac[4], g_slave_status[i].mac[5],
  (unsigned long)age_ms);
```

Extend this additively with canonical `device_id`, display/base MAC, STA/AP/ESP-NOW transport MAC, role, packet schema version, and `identify_supported`. Keep `slave_id` only as explicitly deprecated diagnostic metadata.

**Non-blocking loop seam** (lines 2796-2799, 2847-2887):

```cpp
void loop() {
  pollSerialCommands();
  recMaybeScheduledStop();
  recMaybeFinalizeTimeout();
  ...
  maybeRepeatStatus();
  ...
  sendEspNowSync();
  logSd();
  queueStreamRecord();
}
```

Add `identifyTick()` beside the other deadline checks. It may update LED cadence/deadline and restore the saved application-owned LED state, but must not use `delay()`, stop streaming, change SD state, or enter the sample-rate gate.

### `firmware/step_node_slave/step_node_slave.ino` (controller, event-driven/streaming)

**Analog:** existing exact-size packet dispatch, status publication, and callback-to-loop deferral.

**Exact-size dispatch pattern** (lines 761-800):

```cpp
if (len == (int)sizeof(FreqCmdPacket) &&
    data[0] == CMD_MAGIC && data[1] == CMD_SET_FREQ) {
  ...
}
if (len == (int)sizeof(CfgCmdPacket) &&
    data[0] == CMD_MAGIC && data[1] == CMD_SET_CFG) {
  ...
}
if ((len == 2 || len == (int)sizeof(CmdPacket)) &&
    data[0] == CMD_MAGIC) {
  const CmdPacket *cmd =
      len == (int)sizeof(CmdPacket) ? (const CmdPacket *)data : nullptr;
  ...
}
```

New Identify packets should not inherit the legacy `len == 2` compatibility branch. Validate exact length, version, packet size, full target MAC, duration, capability, and command ID before mutating state.

**Callback-to-loop deferral pattern** (lines 831-850 and 2616-2650):

```cpp
case CMD_REC_START:
  ...
  g_espnow_rec_start_pending = true;
  break;
```

```cpp
if (g_espnow_rec_start_pending) {
  g_espnow_rec_start_pending = false;
  ...
  const bool ok = sdRecordStart(nullptr, g_espnow_requested_session);
}
```

Use the same shape for Identify: callback validates/copies a bounded request into pending state; normal `loop()` starts the LED action and only then sends the application ACK. This keeps callbacks short and makes “confirmed” mean that the target actually started Identify.

**Full identity source and current truncation point** (lines 1233-1239):

```cpp
SlaveStatusPacket pkt = {};
pkt.magic = SLAVE_STATUS_MAGIC;
pkt.version = SLAVE_STATUS_VERSION;
pkt.packet_size = sizeof(SlaveStatusPacket);
const uint64_t mac = ESP.getEfuseMac();
pkt.slave_id = (uint32_t)(mac & 0xFFFFFFFFULL);
```

Preserve all 48 eFuse/base MAC bits in the new status schema. Keep base, STA, AP, and current ESP-NOW transport MAC in separate six-byte fields until actual hardware proves their relationship.

**Targeted status return path** (lines 1274-1284):

```cpp
if (g_master_peer_registered) {
  esp_now_send(g_master_mac, (uint8_t *)&pkt, sizeof(pkt));
} else {
  uint8_t bcast[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
  esp_now_send(bcast, (uint8_t *)&pkt, sizeof(pkt));
}
```

An Identify ACK should use the registered Master peer and include the request command ID, target full MAC, normalized outcome, applied duration, and packet schema version. Link-layer `onEspNowSent()` remains diagnostic only.

**Idempotency state required:** retain the last completed/active command ID and its terminal ACK. Replaying that command returns the same ACK without extending the LED deadline; a different accepted command may replace the current deadline.

### `scripts/stepesp_tcp_udp_relay.py` (service/route, streaming/request-response)

**Analog:** current one-session ownership plus isolated bounded UDP queues.

**Session ownership and cleanup pattern** (lines 20-29, 53-100):

```python
self._downstream_writer: asyncio.StreamWriter | None = None
self._write_lock = asyncio.Lock()
self._session_lock = asyncio.Lock()
self._udp_enabled = asyncio.Event()
...
async with self._session_lock:
    await self._handle_client_locked(downstream_reader, downstream_writer)
...
finally:
    esp_sock.close()
    self._downstream_writer = None
```

Attach verified identity metadata to this session (`device_id`, role, base/transport MACs, capabilities, current endpoint). Do not derive `device_id` from `self.name` or `esp_host`.

**Handshake gate pattern** (lines 109-150):

```python
if not self._udp_enabled.is_set():
    self._log(f'ESP -> WSL handshake: {data!r}')
...
await self._write_downstream(downstream_data)
if b'SENSORS:' in data:
    self._udp_enabled.set()
```

Issue `IDENTITY?` and strictly parse `IDENTITY_OK protocol=id-v1 ...` before enabling a route. A malformed identity, changed identity on a known session, or unsupported old firmware must remain explicit; do not silently bind by IP. Preserve old acquisition by exposing a legacy/unsupported identity state rather than pretending it is confirmed.

**Failure-isolated queue pattern** (lines 161-187):

```python
self.queues = {
    host: asyncio.Queue[bytes](maxsize=256) for host in routes
}
...
if queue.full():
    queue.get_nowait()
queue.put_nowait(data)
```

Phase 20 can retain the current two-session topology, but identity lookup must be separate from source-IP routing so a DHCP rebind updates endpoint metadata without changing the canonical `device_id`. Full N-route ownership remains Phase 21.

**Control transparency convention:** add `IDENTITY`, `IDENTIFY`, and their reason-coded terminal replies to the existing inline-control logging/forwarding prefix set at lines 121-125. Preserve bytes unchanged; the relay must not manufacture confirmation.

### `backend/rehab_robotics_bridge/esp32_bridge_node.py` (provider/service, streaming/request-response)

**Analog:** existing strict parsers, acknowledged services, health snapshots, and mixed control/binary handling.

**Pure control field parser** (lines 121-135):

```python
def parse_control_fields(line: str) -> dict[str, str]:
    return {
        key: value
        for field in line.split()
        if '=' in field
        for key, value in [field.split('=', 1)]
    }
```

Build strict identity helpers around this convention: normalize exactly 12 hex digits into `esp32:aabbccddeeff`, render `AA:BB:CC:DD:EE:FF`, reject malformed/partial values, and never infer missing upper bits from deprecated `slave_id`.

**Acknowledged service pattern** (lines 258-319):

```python
result = asyncio.run_coroutine_threadsafe(
    self._send_control_command(command, expected), self._loop
).result(timeout=8.0)
...
response.success, response.message = normalize_recording_reply(
    bool(request.data), result,
)
self._observe_control_response(result)
```

Copy the thread-safe coroutine handoff, but map the Identify service response to a discriminated outcome instead of a single Boolean. Only `confirmed` is success; retain `sent_unconfirmed`, `timeout`, `offline`, `unsupported`, `rejected`, and `invalid_target`.

**Serialized command timeout pattern** (lines 554-575):

```python
async with lock:
    while not self._control_responses.empty():
        self._control_responses.get_nowait()
    writer.write((command + '\n').encode('ascii'))
    await writer.drain()
    deadline = asyncio.get_running_loop().time() + 6.0
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError(f'timed out waiting for {expected}')
        line = await asyncio.wait_for(
            self._control_responses.get(), timeout=remaining)
        if line.startswith(expected) or line.startswith(('REC ERR', 'ERROR ')):
            return line
```

Identify must additionally match the returned `command_id` and full target `device_id`; a terminal reply for another command cannot satisfy the request. Do not treat ESP-NOW send completion as the expected reply.

**Versioned health JSON pattern** (lines 452-480):

```python
return {
    'schema': 'oe_esp32.health.v1',
    'node_id': self._node_id,
    'timestamp_us': time.monotonic_ns() // 1000,
    'connection_state': self._connection_state,
    ...
}
```

Add an identity schema/snapshot with canonical ID plus separate role, IP route, base/STA/AP/ESP-NOW MACs, capability/version, and verification state. Keep `node_id` as a compatibility alias, not the primary key.

**Mixed stream parser pattern** (lines 792-823):

```python
control_offsets = [
    offset for prefix in CONTROL_RESPONSE_PREFIXES
    if (offset := buf.find(prefix)) >= 0
]
...
text = line.decode(errors='replace').strip()
self._observe_control_response(text)
...
await self._control_responses.put(text)
```

Add identity/Identify prefixes in both `CONTROL_RESPONSE_PREFIXES` and the queue-admission tuple. Add parser bounds so malformed text cannot become a canonical device record.

**ID-02 architectural gap:** publishers are currently created from `node_id` before any connection/identity handshake (lines 225-230). The planner must explicitly schedule identity resolution before creating the canonical publisher, or lazily create a per-device publisher after verified identity while retaining `/esp32/master/*` and `/esp32/slave/*` as compatibility aliases. Merely adding `device_id` to health JSON does not satisfy stable data-topic identity.

### `rehab_robotics_interfaces/srv/IdentifyDevice.srv` (model, request-response)

**Analog:** none. The repository currently has only `msg/ProcessingBlockUpdate.msg`; `std_srvs/SetBool` cannot carry a target MAC, command ID, duration, or reason-coded result.

Use primitive fields and keep correlation explicit. Recommended contract shape:

```text
string command_id
string target_device_id
uint32 duration_ms
---
string command_id
string target_device_id
string outcome
uint32 applied_duration_ms
string detail
```

Validation belongs in the bridge before hardware I/O: non-empty bounded command ID, exact canonical target, and 1000-5000 ms duration with 3000 ms default supplied by the caller/UI contract.

### `rehab_robotics_interfaces/CMakeLists.txt` (config, build transform)

**Analog:** current interface registration (lines 8-11):

```cmake
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/ProcessingBlockUpdate.msg"
  DEPENDENCIES std_msgs
)
```

Add `"srv/IdentifyDevice.srv"` inside the same call. No extra dependency is needed if the service uses only primitive ROS fields.

### `scripts/start_stepesp_wireless.ps1` (config/route, batch/request-response)

**Analog:** current DHCP scan and fixed role-based launch.

**Current anti-pattern to replace for identity confirmation** (lines 112-135):

```powershell
$resolvedSlaveHost = $SlaveHost
if ($SlaveHost -eq 'auto') {
  # DHCP assignment order is not stable...
  $responsiveStations = @(
    2..10 |
      ForEach-Object { "192.168.4.$_" } |
      Where-Object { ... ping.exe ... }
  )
  ...
  $resolvedSlaveHost = $responsiveStations[0]
}
```

Ping can discover candidate routes but cannot prove identity. Probe candidates with `IDENTITY?`, normalize the returned full base MAC, and bind expected devices by canonical ID. Do not accept “only responding IP” as identity.

**Compatibility launch seam** (lines 173, 185-187):

```powershell
$relayArgs = "... --esp-host $MasterHost ... --slave-host $resolvedSlaveHost ..."
$master = "... -p node_id:=master -p host:=$wslGateway -p port:=$RelayPort ..."
$slave = "... -p node_id:=slave -p host:=$wslGateway -p port:=$SlaveRelayPort ..."
```

Preserve the fixed Master/Slave arguments as legacy aliases, but pass expected/verified canonical IDs separately. Do not rename role labels into MACs; role and identity are separate fields.

## Test Pattern Assignments

### `backend/test/test_stepesp_firmware_topology.py`

**Analog:** paired source-fixture checks (lines 9-25):

```python
MASTER_SOURCE = REPO_ROOT / 'firmware' / 'step_node' / 'step_node.ino'
SLAVE_SOURCE = REPO_ROOT / 'firmware' / 'step_node_slave' / 'step_node_slave.ino'

class StepEspFirmwareTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master = MASTER_SOURCE.read_text(encoding='utf-8')
        cls.slave = SLAVE_SOURCE.read_text(encoding='utf-8')
```

Extend this file for static contract invariants shared by both sketches:

- matching identity/Identify magic, version, packet-size, outcome, and capability constants;
- six-byte identity/target fields and no identity comparison through `slave_id`;
- exact-size/version checks on both receive paths;
- Master targeted unicast rather than Identify fan-out;
- `identifyTick()` present in both normal loops and no `delay()` in its function body;
- Identify does not assign `streaming`, SD recording state, sample rate, or acquisition timing;
- Slave callback defers work to loop-owned pending state.

### `backend/test/test_esp32_controls.py`

**Analog:** ROS-free dynamic import and explicit ACK assertions (lines 12-66, 69-81):

```python
def _load_bridge_module():
    ...
    sys.modules.setdefault('rclpy', rclpy)
    ...
    spec.loader.exec_module(module)
    return module

bridge = _load_bridge_module()
mapper = bridge.Esp32BridgeNode._control_command_for_parameter
```

```python
self.assertEqual(
    mapper('sample_rate_hz', 137),
    ('FREQ:137', 'OK FREQ:137', ''),
)
```

Add fixtures for canonical/display formatting, malformed/full-MAC validation, two MACs with identical low 32 bits, command-ID correlation, wrong-target rejection, duplicate ACK, lost ACK/timeout, offline, unsupported, rejected, invalid target, and no confirmed-state mutation on failure. Update the lightweight `rehab_robotics_interfaces.srv` stub when importing the new service.

Reuse the existing async Reader/Writer stubs (lines 154-196 and 275-338) to prove Identify control text can coexist with binary frames and that only a matching correlated ACK completes the request.

### `backend/test/test_stepesp_udp_relay.py`

**Analog:** script import plus isolated async route fixtures (lines 10-15, 32-69):

```python
SPEC = importlib.util.spec_from_file_location(
    'stepesp_tcp_udp_relay', RELAY_PATH)
relay_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(relay_module)

class StepEspUdpRelayTests(unittest.IsolatedAsyncioTestCase):
    ...
    workers = [
        asyncio.create_task(router._forward_route('192.168.4.1')),
        asyncio.create_task(router._forward_route('192.168.4.3')),
    ]
```

Extend with fake identity handshakes for:

- DHCP endpoint change preserving one canonical device key;
- different full MAC at the old IP becoming a distinct device;
- two full MACs sharing low 32 bits remaining distinct;
- identity changing mid-session being rejected/quarantined;
- malformed/unknown identity schema;
- Identify reply forwarded unchanged and correlated;
- one route timeout not blocking the other route.

## Shared Contract Patterns

### Canonical Identity

- Internal: `esp32:aabbccddeeff`.
- Display: `AA:BB:CC:DD:EE:FF`.
- Stable key: verified full 48-bit eFuse/base MAC.
- Separate metadata: role, DHCP/current route, STA MAC, AP MAC, ESP-NOW transport MAC, capability/version.
- Deprecated only: low-32-bit `slave_id`.
- A changed stable identity at a known route creates a distinct/offline/new-device transition; never mutate the old identity into the new one.

### Firmware Packet Validation

Apply to every new identity/Identify packet:

```text
magic matches
AND type matches
AND version is supported
AND received length == sizeof(packet)
AND packet_size == sizeof(packet)
AND target full MAC is valid
AND duration is bounded
```

Unknown versions, oversize/undersize packets, malformed targets, and unsupported LED capability must produce visible reason-coded failures without partial interpretation.

### Host Control Lines

Follow the existing space-delimited `key=value` contract:

```text
IDENTITY_OK protocol=id-v1 device_id=esp32:aabbccddeeff role=slave ...
IDENTIFY_ACK protocol=identify-v1 command_id=<id> target=esp32:aabbccddeeff outcome=confirmed duration_ms=3000
IDENTIFY_ERR protocol=identify-v1 command_id=<id> target=esp32:aabbccddeeff outcome=rejected detail=<token>
```

Keep values token-safe because `parse_control_fields()` splits on spaces. Use stable machine codes in `outcome`/`detail`; human prose can be added at the ROS/UI boundary.

### Confirmed Identify State Machine

```text
host validates request
  -> Master resolves exact full-MAC peer (or explicit self)
  -> target validates version/size/target/capability/duration
  -> loop starts non-blocking LED action and saves prior LED state
  -> target sends application ACK with command_id
  -> Master/relay/bridge forward the exact correlated outcome
  -> loop expires deadline and restores prior LED state
```

ESP-NOW send completion is not confirmation. Duplicate command IDs replay their prior result without extending the deadline. A new accepted command may replace the active deadline.

### Compatibility

- Existing acquisition, recording, frequency, filter, CFG, Master/Slave status, and fixed topic aliases remain operational.
- Old firmware remains observable where possible and returns `unsupported` for Identify.
- New parsers fail closed on malformed or unknown versions.
- Phase 20 must not introduce N-route fleet ownership, model mapping, N-sensor IK, or Studio mapping-workspace state.

## No Analog Found

| File/Concern | Role | Data Flow | Reason |
|---|---|---|---|
| `rehab_robotics_interfaces/srv/IdentifyDevice.srv` | model | request-response | Repository has no custom service carrying correlation, target identity, duration, and a discriminated outcome. |
| Identity-derived canonical publisher lifecycle | provider | streaming | Current bridge constructs publishers from `master`/`slave` before connecting; no existing lazy identity-keyed publisher/alias pattern exists. Use research guidance and keep the Phase 21 fleet lifecycle boundary explicit. |
| Board LED capability/pin mapping | controller/config | event-driven | No verified LED pin/active-level contract is present in the analyzed sketches. Capability must default to unsupported until the exact board revision is verified; do not guess. |

## Dirty Worktree Overlap Risks

The implementation files are not on a clean baseline. Preserve all existing content and inspect current state immediately before editing:

| File | Current status | Overlap risk |
|---|---|---|
| `firmware/step_node/step_node.ino` | untracked | Entire current firmware file is user/worktree state; no Git baseline exists for safe replacement. |
| `firmware/step_node_slave/step_node_slave.ino` | untracked | Same; packet blocks and loop are direct Phase 20 edit zones. |
| `scripts/stepesp_tcp_udp_relay.py` | untracked | Same; session handshake and control-prefix blocks are direct edit zones. |
| `backend/rehab_robotics_bridge/esp32_bridge_node.py` | modified | Existing local edits are near handshake/control flow (diff hunks around current lines 612-718); merge rather than overwrite. |
| `backend/test/test_esp32_controls.py` | modified | Existing local edits are in confirmed-range tests around current lines 276-334. |
| `backend/test/test_stepesp_firmware_topology.py` | untracked | Extend the current fixture rather than recreating it. |
| `backend/test/test_stepesp_udp_relay.py` | untracked | Extend the current async route test rather than recreating it. |
| `rehab_robotics_interfaces/CMakeLists.txt` | untracked | Preserve the existing `ProcessingBlockUpdate.msg` registration. |
| `rehab_robotics_interfaces/package.xml` | untracked | No change expected for primitive-only service fields; preserve as-is. |
| `backend/package.xml` | modified | Already contains the interface dependency; avoid redundant dependency edits. |
| `scripts/start_stepesp_wireless.ps1` | clean | Lower overlap risk, but its fixed two-route behavior is operationally sensitive. |

## Metadata

**Analog search scope:** `firmware/step_node`, `firmware/step_node_slave`, `scripts`, `backend/rehab_robotics_bridge`, `backend/test`, `rehab_robotics_interfaces`, and the current Windows launch path.  
**Primary analog files read:** 9.  
**Pattern extraction date:** 2026-07-30.
