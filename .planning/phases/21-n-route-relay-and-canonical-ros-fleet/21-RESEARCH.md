# Phase 21 Research: N-Route Relay and Canonical ROS Fleet

**Researched:** 2026-07-31  
**Status:** Complete  
**Domain:** STEP_ESP32 wireless relay, Windows launcher, ROS 2 bridge fleet publishing  
**Constraint:** Agent work stays offline from STEP_ESP32 Wi-Fi; hardware acquisition remains operator-run.

## Executive Summary

Phase 20 already binds verified full-MAC self identity, keeps role/IP/transport as metadata, and ships a pure `device_topic_token()` helper without creating per-MAC publishers. Phase 21 must turn that foundation into N verified slave routes (≤6 peer slots), one identity-keyed fleet manager publishing `/esp/raw|status/mac_<12hex>` plus `/esp/fleet/registry`, and explicit Master/Slave aliases that never mean “whoever connected first.” The relay already isolates UDP per source IP with Queue(maxsize=256) drop-oldest, but only accepts one `--slave-host`. The launcher currently fails closed when more than one verified slave is discovered. Extending both, then replacing the dual `esp32_bridge_node` process model with one multi-session fleet owner, is the critical path.

## Current System Seams

### Relay — `scripts/stepesp_tcp_udp_relay.py`

| Seam | Current behavior | Phase 21 gap |
|------|------------------|--------------|
| `StepEspRelay` | One TCP control + UDP forward session per ESP host; binds only verified `record=self` | Needs N slave sessions, each with expected device_id |
| `SessionIdentityRegistry` | MAC-keyed; IP refresh updates `current_endpoint` without changing device_id; displaced endpoint clears old route | Preserve; expose offline retention when endpoint dies |
| `UdpRouter` | `dict[host → Queue(maxsize=256)]`, drop-oldest on full, demux by source IP | Add per-route `drop_count`; support dynamic host remapping on DHCP |
| CLI | `--slave-host` singular + `--slave-listen-port` | Multi-slave args (repeatable hosts / JSON / paired lists) |
| Isolation | Malformed inventory on one route must not poison another (tested) | Prove N-route reconnect and drop counters independently |

### Launcher — `scripts/start_stepesp_wireless.ps1`

| Seam | Current behavior | Phase 21 gap |
|------|------------------|--------------|
| Discovery | Ping candidates → identity probe → verified slave self only | Collect **all** verified slaves ≤6 |
| Ambiguity | `Count -gt 1` throws unless `-ExpectedSlaveDeviceId` | Route all verified; fail closed only on duplicate MAC / master collision |
| Relay spawn | One master + one slave CLI pair | Pass N slave hosts, expected IDs, listen ports |
| ROS bridges | Two WSL `esp32_bridge_node` processes (`node_id:=master|slave`) | Prefer one fleet manager process (CONTEXT) |
| Ports | Master listen 5002, slave 5003, UDP 55001 | Contiguous slave listen ports from 5003 (discretion) |

### Bridge — `backend/rehab_robotics_bridge/esp32_bridge_node.py`

| Seam | Current behavior | Phase 21 gap |
|------|------------------|--------------|
| Publishers | `/esp/raw/{node_id}`, `/esp/status/{node_id}`, `/esp32/{node_id}/imu|raw`, Identify service | Add `/esp/raw|status/mac_<12hex>` via `device_topic_token` |
| Identity bind | Complete verified self only; different self at same route raises and retains prior | Multi-session: offline old MAC, register new MAC as distinct |
| Pair health | Master node publishes `/esp/status/pair` from slave health subscription | Keep when aliases bound; registry authoritative for N>2 |
| `device_topic_token` | Pure helper `mac_<12hex>`; Phase 20 tests forbid publisher lifecycle | Create/cache/publish/destroy lifecycle owned here |
| Process model | One session per process; launcher starts two | Fleet manager owns all sessions + registry |

### Aggregator — `imu_aggregator_node.py`

Legacy YAML spawner that partially constructs `Esp32BridgeNode` without Phase 20 identity/health contracts. **Do not** use as the Phase 21 primary model. Prefer a purpose-built fleet manager; leave aggregator alone or document as obsolete.

### Firmware constraint

Master `MAX_SLAVE_STATUS_SLOTS = 6` caps verified peer inventory. Host must not invent routes beyond verified self-identity TCP endpoints; inventory peers are not session identity (Phase 20 rule).

## Extension Design: N Verified Slaves

### Relay CLI (recommended)

```text
--esp-host / --expected-device-id / --listen-port          # master
--slave-route HOST:LISTEN_PORT:EXPECTED_DEVICE_ID         # repeatable, ≤6
```

Alternative equivalent: parallel lists `--slave-host` (repeatable) + `--slave-listen-port` + `--slave-expected-device-id` with equal lengths. Fail closed if lengths mismatch, duplicate hosts, duplicate listen ports, duplicate device_ids, or slave count > 6.

### Launcher discovery

1. Probe all STEP_ESP32 STA candidates (exclude Windows STA and master `192.168.4.1`).
2. Keep every probe whose verified self `role=slave` and device_id ≠ master.
3. Fail closed on duplicate MAC across candidates.
4. Cap at 6; if more verified slaves appear, fail closed with explicit reason (firmware slot limit).
5. Optional `-ExpectedSlaveDeviceIds` filter remains for operator pin-down; absence means “route all verified.”
6. Allocate listen ports: `SlaveRelayPort + index` (5003, 5004, …).
7. Start one relay with all routes; start one fleet bridge with route table + alias params.

### Identity / DHCP

- Canonical topic token = `device_topic_token(device_id)` → never derived from IP or discovery order.
- When DHCP changes IP: update relay route host map and session `current_endpoint`; publishers stay on `mac_<12hex>`.
- When a known route reports a different verified self: mark previous MAC offline (endpoint cleared), bind new MAC as distinct device (CONTEXT / Phase 20).

## Fleet Registry Schema Proposal

**Topic:** `/esp/fleet/registry` (`std_msgs/String` JSON)  
**Schema:** `oe_esp32.fleet_registry.v1` (discretion)

```json
{
  "schema": "oe_esp32.fleet_registry.v1",
  "updated_at_us": 0,
  "alias_master_device_id": "esp32:aabbccddeeff",
  "alias_slave_device_id": "esp32:112233445566",
  "devices": [
    {
      "device_id": "esp32:aabbccddeeff",
      "display_mac": "AA:BB:CC:DD:EE:FF",
      "topic_token": "mac_aabbccddeeff",
      "role": "master",
      "discovery": "present",
      "command": "ready",
      "route": "up",
      "orientation_freshness": "fresh",
      "synchronization": "in_skew",
      "rate": "nominal",
      "endpoint": {"host": "192.168.4.1", "esp_port": 5000, "listen_port": 5002},
      "drop_count": 0,
      "reconnect_count": 0,
      "last_seen_us": 0,
      "last_frame_age_ms": 0.0
    }
  ]
}
```

**Layered states (FLEET-01 — not a single `connection_state`):**

| Field | Example values |
|-------|----------------|
| `discovery` | `present`, `missing`, `unverified` |
| `command` | `ready`, `handshake`, `degraded`, `unavailable` |
| `route` | `up`, `reconnecting`, `stale`, `offline` |
| `orientation_freshness` | `fresh`, `stale`, `none` |
| `synchronization` | `in_skew`, `out_of_skew`, `unknown` |
| `rate` | `nominal`, `low`, `none` |

Health topic `/esp/status/mac_<12hex>` should extend `oe_esp32.health.v1` (or `.v2` if additive break needed) with `drop_count`, `reconnect_count`, and the same layered fields so registry and per-device health stay aligned.

## Failure Isolation / Queue Drop Patterns

1. **Per-route UDP queue:** Keep maxsize=256 drop-oldest; increment `drop_count` on each discarded datagram.
2. **Per-route TCP reconnect:** Only the failed session reconnects; other sessions continue acquisition, Identify, health, recording.
3. **No global relay restart** on single-route failure; registry marks `route=reconnecting|stale|offline`.
4. **Offline retention:** Keep MAC rows with `last_seen_*`; do not delete solely because TCP died.
5. **Identify / control:** Target by full MAC; failure of one target must not cancel other sessions’ control loops.
6. **Alias pair health:** If alias slave is offline, pair health reports unavailable without stopping master stream.

## Test Seams

| File | Extend for |
|------|------------|
| `backend/test/test_stepesp_udp_relay.py` | N-route CLI parsing; 3+ host demux; drop_count on full queue; DHCP host remap keeps device_id; launcher routes all verified ≤6; duplicate MAC fail-closed |
| `backend/test/test_esp32_controls.py` | Lift Phase 20 “no mac_ publishers” bans; assert canonical + alias publish same payload; registry layered fields; alias params; isolation (kill one session, others publish) |
| New `backend/test/test_fleet_bridge.py` (if split helps) | Pure unit tests for registry builder, topic token wiring, reconnect isolation without ROS spin |
| Source-contract launcher asserts | Fleet entrypoint, alias params, contiguous ports, no dual-bridge default |

**Nyquist:** Every plan task must have an automated verify command under these suites. Hardware STEP_ESP32 is out of scope for agent verification.

## Risks

| Risk | Mitigation |
|------|------------|
| Windows path with `#` and apostrophe breaks naive shell/`cd` | Use LiteralPath / Python `os.listdir` root discovery; never unquoted paths in PowerShell |
| WSL dual-bridge → single fleet process | Update launcher + docs together; keep thin `esp32_bridge_node` for one-device debug |
| Source-IP UDP demux after DHCP | Relay must remape `UdpRouter.routes`/`queues` under MAC key or update host key atomically |
| drop_count currently missing | Add counter beside drop-oldest path; expose in health/registry |
| Agent cannot join STEP_ESP32 | Deterministic fixtures only; operator docs note live stack path |
| `imu_aggregator_node` incomplete construction | Do not extend; avoid regressing callers |
| Port exhaustion / collisions | Contiguous allocation from 5003; fail closed on collision |
| COMP-01 consumers | Keep `/esp/raw|status/master|slave` and `/esp/status/pair` when aliases bound |

## Architectural Responsibility Map

| Concern | Owner | Tier |
|---------|-------|------|
| Multi-slave discovery | `start_stepesp_wireless.ps1` | Host launcher |
| TCP/UDP N-route forward + drop queues | `stepesp_tcp_udp_relay.py` | Windows relay |
| Canonical + alias + registry publish | Fleet manager (new/extended bridge) | ROS 2 backend |
| Identity token | `device_topic_token` in bridge | Shared helper |
| Pair health compatibility | Fleet manager when aliases set | ROS 2 backend |
| Mapping UI / IK / model store | Phases 22–24 | Out of scope |

## Package Legitimacy Audit

No new npm/pip/cargo packages required. Reuse stdlib asyncio, existing rclpy/std_msgs, and PowerShell already in the stack.

## Out of Scope (explicit)

- Model catalog / mapping store / Apply (Phase 22)
- N-sensor calibration / official IK (Phase 23)
- Studio multi-row mapping workspace (Phase 24)
- Hardware capacity promotion / dynamic mode default (Phase 25)
- Explicit “forget device” UX
- Live STEP_ESP32 Wi-Fi acquisition during agent runs

## Discretion Choices Locked for Planning

1. Registry schema name: `oe_esp32.fleet_registry.v1`
2. Slave listen ports: contiguous from configured `SlaveRelayPort` (default 5003)
3. Primary process: one `fleet_bridge_node` entry point; retain `esp32_bridge_node` as thin single-session wrapper
4. Minimal registry JSON debug surface allowed only if cheap; full HealthPanel multi-row UI deferred to Phase 24
