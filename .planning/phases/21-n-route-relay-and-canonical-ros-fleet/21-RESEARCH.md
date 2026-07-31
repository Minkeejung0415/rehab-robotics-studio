# Phase 21: N-Route Relay and Canonical ROS Fleet - Research

**Researched:** 2026-07-31
**Domain:** Multi-device Windows TCP/UDP relay + ROS 2 fleet publishers/registry
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Multi-slave discovery & route binding
- Route all verified slave self-identities discovered on the STEP_ESP32 AP, capped at the firmware peer slot limit (6).
- Fail closed on duplicate MAC; if a known route later reports a different stable identity, retain the original as offline and register the new identity as a distinct device (Phase 20 rule).
- Master at 192.168.4.1 and the Windows STA remain required; slaves are N additional TCP/UDP routes.
- Bind each relay session to canonical `esp32:aabbccddeeff` identity and refresh IP without changing the canonical topic token.

#### Canonical topics & legacy aliases
- Canonical topics use Phase 20 `device_topic_token`: `/esp/raw/mac_<12hex>` and `/esp/status/mac_<12hex>`.
- Keep `/esp/raw/master`, `/esp/raw/slave`, `/esp/status/master`, `/esp/status/slave` as explicit aliases bound to configured identities, carrying the same payload as the canonical topics (FLEET-02 / COMP-01).
- Alias binding is owned by launch/bridge parameters (`alias_master_device_id` / `alias_slave_device_id`, or first verified role identities) — never “whoever connected first.”
- Publish one aggregate `/esp/fleet/registry` (String/JSON) listing all known MACs and layered states (FLEET-01).

#### Failure isolation & diagnostics
- Isolate failures per identity: a failed/stale/reconnecting route must not stop acquisition, health, Identify, or recording for other devices (FLEET-03).
- Keep per-route bounded UDP queues (maxsize=256, drop-oldest) and expose drop_count (and reconnect diagnostics) in health/registry.
- Auto-reconnect only the affected route; registry marks reconnecting/stale without a global relay restart.
- Retain offline/stale MAC rows with last-seen; do not drop from registry solely because TCP died (explicit forget is later-phase).

#### Fleet process model & registry visibility
- Prefer one fleet manager / multi-session bridge owning all identity routes and the registry; avoid N+1 independent bridge processes as the primary model.
- Each registry row exposes distinct layered fields: discovery, command, route, orientation freshness, synchronization, rate, plus drops/reconnects — not a single collapsed connection_state.
- Phase 21 is backend/ROS contracts first; full multi-row mapping UI is Phase 24. A minimal HealthPanel/debug surface for registry JSON is allowed if cheap.
- Keep `/esp/status/pair` publishing when aliases are bound for COMP-01; registry is authoritative for N>2.

### Claude's Discretion
- Exact JSON schema field names and schema version string for registry/health extensions, provided layered states and drop/reconnect diagnostics remain visible.
- Exact listen-port allocation scheme for N slave TCP relays (contiguous ports vs dynamic map), provided each device has an isolated route.
- Whether legacy single-role bridge entrypoints remain thin wrappers or are folded into the fleet manager, provided aliases and isolation semantics hold.

### Deferred Ideas (OUT OF SCOPE)
- Model catalog, mapping store, Apply transactions — Phase 22.
- N-sensor calibration and official OpenSim IK — Phase 23.
- Dedicated Studio mapping workspace (segment selectors, Draft/Saved/Applied) — Phase 24.
- Hardware capacity promotion gate / default dynamic mode — Phase 25.
- Explicit “forget device” UX — later than Phase 21 registry retention rule.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ID-02 | Same canonical identity and data topic across DHCP, reconnect, discovery-order; role/IP/transport MAC remain metadata | `SessionIdentityRegistry` already rebinds endpoints by `device_id`; Phase 21 must instantiate publishers via `device_topic_token` and remap `UdpRouter` IP keys without changing topic tokens |
| FLEET-01 | MAC-keyed fleet registry with layered discovery/command/route/orientation/sync/rate states | Publish `/esp/fleet/registry` from one fleet manager; extend health with layered fields + drops/reconnects |
| FLEET-02 | Canonical per-MAC IMU/health + explicit Master/Slave aliases | Canonical `/esp/raw|status/mac_*` (+ recommended `/esp32/mac_*/{imu,raw}`); aliases bound by `alias_*_device_id` params, same payload |
| FLEET-03 | Per-route failure isolation; bounded queue/drop/reconnect diagnostics visible | Per-route supervised tasks (not one fatal `gather`); expose `drop_count` on existing maxsize=256 drop-oldest queues |
</phase_requirements>

## Summary

Phase 20 delivered verified full-MAC identity, Identify, and a pure `device_topic_token()` helper, but left data publishers on fixed role topics and kept the wireless launcher fail-closed when more than one verified slave is discovered. Phase 21 turns that foundation into an N-route system: discover up to six verified slaves, bind each TCP/UDP session to `esp32:<12hex>`, publish canonical per-MAC streams, keep explicit Master/Slave aliases, and expose a single MAC-keyed `/esp/fleet/registry` with layered readiness and drop/reconnect diagnostics.

The largest implementation gaps are not identity parsing (already solid) but lifecycle ownership: the relay CLI still takes one optional `--slave-host`; `UdpRouter` drops silently without counters and keys queues only by construction-time IP; the launcher starts two independent `esp32_bridge_node` processes; and Phase 20 tests intentionally assert that no `/esp/.../mac_*` publishers exist yet. Do not extend `imu_aggregator_node` — it partially constructs bridges without Phase 20 identity contracts. Milestone architecture research names the target shape (`esp32_fleet_bridge`); locked CONTEXT overrides the fleet topic to `/esp/fleet/registry` (not `/esp/status/fleet`) and defers mapping/OpenSim dynamic mode.

**Primary recommendation:** Extend the Windows relay for N identity-bound slave routes with contiguous WSL listen ports and per-queue `drop_count`; add one `esp32_fleet_node` that owns sessions keyed by `device_id`, publishes canonical + alias + registry topics from the same accepted streams; keep `esp32_bridge_node` as a thin single-session wrapper for USB/legacy rollback.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Multi-slave Soft-AP discovery | Host tooling (Windows PowerShell) | Firmware peer inventory | Launcher probes TCP `IDENTITY?` on candidate IPs; firmware peer rows are inventory only, never session identity |
| Identity-bound TCP/UDP relay | Host process (`stepesp_tcp_udp_relay.py`) | — | Soft AP cannot route UDP into WSL NAT; Windows owns ESP sockets and demux by source IP |
| Canonical/alias ROS publishers | API / Backend (ROS 2 fleet node) | Host relay | Relay routes bytes; ROS owns topic namespaces, health JSON, Identify/recording services |
| Fleet registry snapshot | API / Backend | Host relay diagnostics | Registry is operator-facing ROS contract; relay supplies route/drop/reconnect facts |
| Legacy pair health | API / Backend | — | COMP-01 alias view derived from bound master+slave identities |
| Failure isolation | Host relay + Backend sessions | — | Per-route asyncio tasks/queues and per-session reconnect loops; no shared cancel |
| Mapping / OpenSim N-IK / Studio rows | Deferred | — | Phases 22–24; Phase 21 must not invent mapping services |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python asyncio + stdlib `socket` | 3.10 (WSL / existing bridge) | N-route relay supervision, per-route queues | Already owns `StepEspRelay` / `UdpRouter` [VERIFIED: codebase `scripts/stepesp_tcp_udp_relay.py`] |
| ROS 2 Humble + `rclpy` | project install | Publishers, timers, services | Existing bridge/entry points [VERIFIED: `backend/setup.py`, launch files] |
| `std_msgs/String`, `sensor_msgs/Imu`, `std_msgs/Float32MultiArray` | ROS distro | Canonical raw/status JSON, typed IMU/raw | Existing publisher types; no new msg packages required for Phase 21 [VERIFIED: `esp32_bridge_node.py`] |
| `rehab_robotics_interfaces/IdentifyDevice` | local package | Targeted Identify | Phase 20 service; fleet node forwards, does not redesign [VERIFIED: bridge imports] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `unittest` / `IsolatedAsyncioTestCase` | stdlib | Relay/router isolation tests | Extend `test_stepesp_udp_relay.py` |
| pytest (existing backend tests) | project | Bridge/fleet unit tests | Extend `test_esp32_controls.py`; add fleet node tests |
| PowerShell 5.1+/7 | Windows host | Wireless launcher discovery | Extend `start_stepesp_wireless.ps1` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| One `esp32_fleet_node` | N× `esp32_bridge_node` processes | Violates locked “prefer one fleet manager”; harder registry aggregation and alias binding |
| Contiguous listen ports 5003..5008 | Dynamic OS-assigned ports + side channel | Dynamic needs a registry API from relay→WSL; contiguous matches today’s 5002/5003 contract |
| `/esp/fleet/registry` (locked) | `/esp/status/fleet` from older architecture notes | CONTEXT locks `/esp/fleet/registry` |
| Phase 21 mapping services | ARCHITECTURE draft `SetSensorMapping` etc. | Deferred to Phase 22 |
| Extending `imu_aggregator_node` | New fleet node | Aggregator lacks Phase 20 identity/health construction — do not use as primary model |

**Installation:** No new third-party packages. Register a new console script only:

```text
# backend/setup.py entry_points addition
esp32_fleet_node = rehab_robotics_bridge.esp32_fleet_node:main
```

**Version verification:** Existing stack only — no registry package installs. [ASSUMED] operator WSL image remains ROS 2 Humble + Python 3.10 as documented in `docs/stepesp-wireless-setup.md`.

## Package Legitimacy Audit

> No external packages are recommended for install in Phase 21.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | — | N/A — reuse in-repo Python/ROS stack |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```text
STEP_ESP32 Soft AP
  Master 192.168.4.1 ──TCP:5000──┐
  Slave_1 .. Slave_N (DHCP) ─────┼──► Windows stepesp_tcp_udp_relay
  Windows STA (excluded)         │      - SessionIdentityRegistry (device_id → endpoint)
                                 │      - UdpRouter :55001 (IP → Queue(256), drop_count)
                                 │      - listen :5002 (master), :5003..:5008 (slaves)
                                 ▼
                         WSL ROS 2 esp32_fleet_node (ONE process)
                           - sessions[device_id]
                           - publish /esp32/mac_*/{imu,raw}
                           - publish /esp/raw|status/mac_*
                           - alias → /esp/raw|status/{master,slave} + /esp32/{master,slave}/*
                           - /esp/fleet/registry (layered JSON)
                           - /esp/status/pair when aliases bound
                           - Identify/recording on master session
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              rosbridge     opensim_bridge   rosbag
              (aliases)     (still alias     (canonical OK)
                             IMU topics)
```

### Recommended Project Structure

```text
scripts/
  stepesp_tcp_udp_relay.py      # N slave hosts, IP remap, drop_count
  start_stepesp_wireless.ps1    # discover ≤6 verified slaves; launch one fleet node
backend/rehab_robotics_bridge/
  esp32_bridge_node.py          # thin single-session wrapper (USB/legacy)
  esp32_device_session.py       # extracted handshake/stream/publish helpers (recommended)
  esp32_fleet_node.py           # NEW multi-session owner + registry + aliases
backend/test/
  test_stepesp_udp_relay.py     # N-route, drop_count, IP remap, isolation
  test_esp32_controls.py        # update Phase-20 “no mac publishers” guards
  test_esp32_fleet_node.py      # NEW registry/alias/isolation contracts
backend/setup.py                # add esp32_fleet_node entry point
```

### Pattern 1: Identity-keyed session, IP as mutable metadata
**What:** Bind publishers and registry rows to `device_id` / `device_topic_token`; treat DHCP IP and listen port as `route` metadata that can refresh.
**When to use:** Every reconnect, discovery reorder, or Soft-AP DHCP churn.
**Example:**
```python
# Source: backend/rehab_robotics_bridge/esp32_bridge_node.py (Phase 20 helpers)
token = device_topic_token('esp32:aabbccddeeff')  # -> mac_aabbccddeeff
raw_topic = f'/esp/raw/{token}'
status_topic = f'/esp/status/{token}'
imu_topic = f'/esp32/{token}/imu'  # recommended companion to locked JSON topics
```

### Pattern 2: Alias republish from one accepted stream
**What:** Publish once to canonical topics; if `device_id` matches `alias_master_device_id` / `alias_slave_device_id`, also publish identical payloads to role topics.
**When to use:** Always for COMP-01 / FLEET-02 — never a second parser.

### Pattern 3: Supervised per-route tasks
**What:** Each relay session and each ROS device session runs in its own reconnect loop; top-level supervisor must not cancel siblings on one failure.
**When to use:** FLEET-03 isolation.
**Anti-pattern today:** `await asyncio.gather(router.serve(), *tasks)` in `run_relays` — one hard failure cancels remaining tasks. [VERIFIED: `scripts/stepesp_tcp_udp_relay.py` `run_relays`]

### Pattern 4: Multi-slave CLI (recommended)
```text
--esp-host / --expected-device-id / --listen-port          # master
--slave-route HOST:LISTEN_PORT:EXPECTED_DEVICE_ID         # repeatable, ≤6
```
Fail closed if duplicate hosts/ports/device_ids, or slave count > 6.

### Anti-Patterns to Avoid
- **N+1 bridge processes as primary model:** Locked preference is one fleet manager.
- **First-connected alias binding:** Use parameters or first *verified role* identities only as explicit fallback — never discovery order alone without recording chosen IDs.
- **Collapsing layered readiness into `connection_state`:** Keep discovery/command/route/freshness/sync/rate distinct.
- **Importing Phase 22 mapping services or OpenSim `mapping_mode:=dynamic`:** Out of scope; keep OpenSim on alias IMU topics for now.
- **Using peer inventory as session identity:** Peer rows inform discovery hints only; each slave route must verify `record=self`.
- **Extending `imu_aggregator_node`:** Incomplete Phase 20 construction — leave alone.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MAC normalization / topic tokens | New ad-hoc hex parsers | `normalize_device_id`, `display_mac`, `device_topic_token` | Already tested collision-safe helpers |
| Identity inventory parsing | Parallel id-v1 grammar | Existing relay + bridge parsers | Dual grammars diverge (Phase 20 pitfall) |
| Bounded UDP demux | Unbounded buffers / global queue | `UdpRouter` Queue(maxsize=256) drop-oldest + new `drop_count` | Isolation already proven in tests |
| Identify protocol | New service redesign | Existing `IdentifyDevice` + master session forward | Phase 20 outcomes matrix must stay |
| Fleet JSON over rosbridge | Custom ROS msg package for registry | `std_msgs/String` JSON (like health/pair) | Matches Studio/rosbridge; mapping msgs wait for Phase 22 |

**Key insight:** Phase 21 is composition and lifecycle — reuse Phase 20 identity contracts; do not reinvent parsers or Identify.

## Common Pitfalls

### Pitfall 1: Silent UDP drops without counters
**What goes wrong:** Queues already drop-oldest at 256 but operators cannot see loss. [VERIFIED: `UdpRouter.route_datagram`]
**Why it happens:** Drop path calls `get_nowait()` with no counter.
**How to avoid:** Increment per-host `drop_count` on drop; surface in registry and per-device health.
**Warning signs:** High rate with `last_frame_age_ms` spikes but `reconnect_count` flat.

### Pitfall 2: IP refresh without remapping `UdpRouter` keys
**What goes wrong:** Registry updates `current_endpoint` but datagrams arrive on a new IP and are ignored as “unknown source.”
**Why it happens:** `UdpRouter.queues` is built once from construction-time hosts. [VERIFIED: `UdpRouter.__init__`]
**How to avoid:** Add `remap_host(old_ip, new_ip)` atomically with `StepEspRelay.esp_host` update after verified same `device_id`.
**Warning signs:** Identity connected, TCP healthy, UDP frames discarded with unknown-source logs.

### Pitfall 3: One failed `gather` cancels the fleet
**What goes wrong:** One slave TCP error stops master acquisition.
**Why it happens:** Shared `asyncio.gather` without supervision/isolation.
**How to avoid:** Per-route `while True: try connect/serve except log/backoff`; gather only long-lived supervisors that never exit on child errors.
**Warning signs:** Single `connection error` log followed by all WSL bridges idle.

### Pitfall 4: Ambiguous multi-slave launcher still fail-closed
**What goes wrong:** Second verified slave aborts the stack. [VERIFIED: `start_stepesp_wireless.ps1` “Slave route selection is ambiguous”]
**Why it happens:** Phase 20 intentionally required `-ExpectedSlaveDeviceId` for >1 slave.
**How to avoid:** Accept all verified slave self-identities up to 6; fail only on duplicate MAC, master/Windows collision, or capacity exceeded.
**Warning signs:** Operator with two slaves cannot start without picking one ID.

### Pitfall 5: Dual publish pipelines for aliases
**What goes wrong:** Canonical and `/esp/raw/slave` diverge.
**Why it happens:** Separate parse/publish paths per topic family.
**How to avoid:** Single accept → fan-out publish (Pattern 2).
**Warning signs:** Pair graph and MAC topic disagree after reconnect.

### Pitfall 6: Updating Phase 20 negative tests late
**What goes wrong:** CI still asserts `device_topic_token` is unused / no mac publishers. [VERIFIED: `test_esp32_controls.py::test_phase20_preserves_fixed_publishers...`]
**How to avoid:** Wave 0 / first implementation wave rewrites those guards into positive fleet publisher tests.

### Pitfall 7: Pulling mapping/OpenSim dynamic mode into this phase
**What goes wrong:** Scope explodes into Phases 22–23.
**How to avoid:** Launcher may start `esp32_fleet_node` but OpenSim continues `master_imu_topic`/`slave_imu_topic` aliases until mapping phases.

## Code Examples

### Canonical token (existing)
```python
# Source: backend/rehab_robotics_bridge/esp32_bridge_node.py
def device_topic_token(value: str) -> str:
    """Return the collision-safe topic token reserved for Phase 21 lifecycle use."""
    return f'mac_{normalize_device_id(value)[6:]}'
```

### Current drop-oldest without counter (gap)
```python
# Source: scripts/stepesp_tcp_udp_relay.py UdpRouter.route_datagram
if queue.full():
    queue.get_nowait()  # Phase 21: count this drop
queue.put_nowait(data)
```

### Recommended registry envelope (discretion)
```json
{
  "schema": "oe_esp32.fleet_registry.v1",
  "revision": 1,
  "timestamp_us": 0,
  "alias_master_device_id": "esp32:aabbccddeeff",
  "alias_slave_device_id": "esp32:1111ccddeeff",
  "devices": [
    {
      "device_id": "esp32:1111ccddeeff",
      "display_mac": "11:11:CC:DD:EE:FF",
      "topic_token": "mac_1111ccddeeff",
      "role": "slave",
      "endpoint": {"host": "192.168.4.3", "esp_port": 5000, "listen_port": 5004},
      "discovery": "present",
      "command": "ready",
      "route": "connected",
      "orientation_freshness": "fresh",
      "synchronization": "unknown",
      "rate": {"configured_hz": 100, "observed_hz": 99.8},
      "drops": {"udp_drop_count": 0, "queue_maxsize": 256},
      "reconnects": {"count": 0, "generation": 1},
      "last_seen_us": 0
    }
  ]
}
```
[ASSUMED] exact enum strings; planner may refine names as long as the six layered dimensions + drops/reconnects remain distinct.

### Contiguous listen-port allocation (discretion recommendation)
```text
master listen: 5002
slave[i] listen: 5003 + i   # i in 0..5  → 5003..5008
esp TCP: always 5000
udp: shared 55001
```

### Legacy entrypoint stance (discretion recommendation)
Keep `esp32_bridge_node` as a thin single-session wrapper around extracted `Esp32DeviceSession`. Add `esp32_fleet_node` as primary wireless path. Optional `-LegacyPairMode` is useful for COMP-01 rollback but not required if fleet node still publishes aliases.

## State of the Art

| Old Approach | Current Approach (Phase 21 target) | When Changed | Impact |
|--------------|-------------------------------------|--------------|--------|
| One optional `--slave-host` | N verified slave hosts (≤6) | Phase 21 | True multi-IMU Soft AP fleets |
| Two `esp32_bridge_node` processes | One `esp32_fleet_node` | Phase 21 | Unified registry + alias binding |
| Role topics only | Canonical `mac_*` + role aliases | Phase 21 | ID-02 topic stability |
| Ambiguous slave → hard fail | Accept all verified ≤6 | Phase 21 | Removes Phase 20 launcher gate |
| Silent UDP drops | Visible `drop_count` | Phase 21 | FLEET-03 diagnostics |

**Deprecated/outdated:**
- Treating “>1 verified slave” as an error in wireless startup (Phase 20 temporary gate).
- Using `node_id` role as the only publisher key for wireless fleets.
- Architecture draft topic `/esp/status/fleet` — superseded by locked `/esp/fleet/registry`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Canonical typed IMU/raw topics should be `/esp32/mac_<12hex>/{imu,raw}` alongside locked `/esp/raw|status/mac_*` | Architecture Patterns | If planners only ship JSON topics, OpenSim/typed consumers lack canonical IMU until later |
| A2 | Registry schema id `oe_esp32.fleet_registry.v1` and layered enum strings | Code Examples | Naming only — low risk if fields remain layered |
| A3 | Contiguous listen ports 5003..5008 | Discretion recommendation | Port conflicts on busy hosts |
| A4 | WSL/runtime remains ROS 2 Humble + Python 3.10 | Standard Stack | Wrong version may change asyncio/`rclpy` APIs |
| A5 | No new pip/ROS interface packages required for Phase 21 | Package Audit | Typed FleetRegistry.msg would add build scope |
| A6 | Drop counts can reach ROS via a minimal stats signal (e.g. `RELAY_STATS` line) or equivalent | Open Questions | If omitted, FLEET-03 drop visibility may be logs-only |

## Open Questions

1. **Should `/esp32/mac_*/{imu,raw}` ship in the same wave as `/esp/raw|status/mac_*`?**
   - What we know: CONTEXT explicitly locks JSON raw/status; FLEET-02 also requires IMU; architecture research includes typed IMU topics.
   - What's unclear: Whether OpenSim must subscribe to canonical IMU in Phase 21 or may keep aliases until Phase 23.
   - Recommendation: Publish both canonical typed and JSON topics now; leave OpenSim on aliases for COMP-01 until mapping phases.

2. **How should relay expose drop/reconnect stats to the fleet node without a new IPC API?**
   - What we know: Today WSL only sees TCP streams; drop counts live in the Windows process.
   - What's unclear: Side-channel vs injecting periodic stats on the relayed control stream.
   - Recommendation: Prefer a minimal `RELAY_STATS` text line (or shared local stats port). CONTEXT requires drop visibility — plan for a signal, not logs alone.

3. **Synchronization layered field source**
   - What we know: Firmware has ESP-NOW sync; health today lacks an explicit sync dimension.
   - What's unclear: Exact signal for `synchronization` (master sync packets vs frame timestamp skew).
   - Recommendation: Publish `unknown` until a concrete firmware field is wired; do not block registry on inventing sync math.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 (Windows relay) | N-route relay | ✓ (project scripts) | 3.x host | — |
| ROS 2 + `rclpy` in WSL | Fleet node | ✓ (documented Ubuntu-22.04 install) | Humble [ASSUMED] | Legacy dual bridge only |
| STEP_ESP32 Soft AP hardware | Multi-slave acceptance | Operator-run | firmware `MAX_SLAVE_STATUS_SLOTS=6` | Deterministic unit/fixtures without radio |
| PowerShell launcher | Discovery/start | ✓ | existing script | Manual relay/ROS args |

**Missing dependencies with no fallback:**
- None for code/contract work; physical N-slave radio acceptance remains operator-run (CONTEXT: stay on ubcvisitor for agent work).

**Missing dependencies with fallback:**
- Live Soft AP during agent implementation → use fixtures/unit tests; hardware UAT separate.

## Validation Architecture

> `workflow.nyquist_validation` is absent in `.planning/config.json` → treat as enabled.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Python `unittest` (+ pytest-compatible collection under `backend/test`) |
| Config file | none dedicated — tests live under `backend/test/` |
| Quick run command | `python -m unittest backend.test.test_stepesp_udp_relay backend.test.test_esp32_controls -q` |
| Full suite command | `python -m unittest discover -s backend/test -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ID-02 | Same MAC keeps topic token after endpoint change | unit | existing reconnect registry test; extend with publisher token assert | ✅ (extend) |
| ID-02 | New MAC at old IP is distinct offline+new | unit | `test_new_full_mac_at_an_old_endpoint_is_a_distinct_identity` | ✅ |
| FLEET-01 | Registry JSON has layered fields + retained offline rows | unit | `test_esp32_fleet_node.py` | ❌ Wave 0 |
| FLEET-02 | Canonical publish + alias fan-out identical payload | unit | `test_esp32_fleet_node.py` | ❌ Wave 0 |
| FLEET-02 | `device_topic_token` used by publishers | unit | update `test_esp32_controls.py` negative → positive | ✅ file, ❌ assertions outdated |
| FLEET-03 | Stalled route does not block sibling UDP | unit | existing `test_stalled_route_does_not_block_another_route` | ✅ |
| FLEET-03 | Drop-oldest increments `drop_count` | unit | new relay test | ❌ Wave 0 |
| FLEET-03 | N-route launcher accepts ≤6 slaves; fails duplicate MAC | unit/static | extend launcher contract tests | ⚠️ partial (still expects ambiguous fail) |
| COMP-01 seam | `/esp/status/pair` still published when aliases bound | unit | fleet node test | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** quick unittest modules touched
- **Per wave merge:** full `backend/test` discover
- **Phase gate:** full suite green + operator Master+≥2 Slave wireless smoke (ROADMAP success criteria)

### Wave 0 Gaps
- [ ] `backend/test/test_esp32_fleet_node.py` — covers FLEET-01/02/03 registry, aliases, isolation
- [ ] Extend `test_stepesp_udp_relay.py` — N hosts CLI, `drop_count`, IP remap, remove “ambiguous must fail” as the only multi-slave contract
- [ ] Rewrite `test_esp32_controls.py::test_phase20_preserves_fixed_publishers...` for Phase 21 publisher lifecycle
- [ ] Optional static launcher checks: ≤6 cap, duplicate MAC fail-closed, single fleet executable launch

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Soft-AP lab network; no new auth |
| V3 Session Management | no | — |
| V4 Access Control | no | Localhost/WSL trust boundary unchanged |
| V5 Input Validation | yes | Existing id-v1 / MAC normalization; bound JSON registry size; reject duplicate/malformed device_id |
| V6 Cryptography | no | — |

### Known Threat Patterns for ESP Soft-AP + ROS bridge

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed identity / topic injection | Tampering | Fail closed on inventory parse; only verified `record=self` binds routes |
| Duplicate MAC spoof / collision | Spoofing | Fail closed on duplicate; quarantine identity-change on known route |
| Unbounded registry / health JSON | Denial of Service | Cap device rows at 1+6; bound strings; existing line byte limits |
| Cross-route cancellation | Denial of Service | Per-route supervision (FLEET-03) |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/21-n-route-relay-and-canonical-ros-fleet/21-CONTEXT.md` — locked decisions
- `.planning/ROADMAP.md` Phase 21 — success criteria / requirements IDs
- `.planning/REQUIREMENTS.md` — ID-02, FLEET-01..03
- `scripts/stepesp_tcp_udp_relay.py` — relay, registry, UdpRouter
- `scripts/start_stepesp_wireless.ps1` — discovery + ambiguous fail
- `backend/rehab_robotics_bridge/esp32_bridge_node.py` — publishers, pair health, `device_topic_token`
- `backend/test/test_stepesp_udp_relay.py`, `test_esp32_controls.py` — contracts/isolation
- `firmware/step_node/step_node.ino` — `MAX_SLAVE_STATUS_SLOTS 6`
- `.planning/phases/20-full-identity-and-confirmed-identify/20-VERIFICATION.md` — Phase 21 publisher boundary

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` — fleet node structure (topic name partially superseded by CONTEXT)
- `.planning/research/PITFALLS.md` / `SUMMARY.md` — alias/isolation pitfalls
- `docs/stepesp-wireless-setup.md` — operator stack topology

### Tertiary (LOW confidence)
- Exact `RELAY_STATS` IPC mechanism for drop_count export — design judgment [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — reuse verified in-repo ROS/Python stack; no new packages
- Architecture: HIGH — CONTEXT + codebase gaps + architecture research align; deferred mapping scoped out
- Pitfalls: HIGH — several failure modes already encoded as Phase 20 tests or explicit launcher throws

**Research date:** 2026-07-31
**Valid until:** 2026-08-30 (stable internal contracts; revisit if firmware peer capacity changes)
