# Phase 21: N-Route Relay and Canonical ROS Fleet - Context

**Gathered:** 2026-07-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Operators can observe and use every known IMU through failure-isolated, identity-keyed ROS routes. Deliver multi-slave discovery and relay routing, canonical per-MAC IMU/health publishers, legacy Master/Slave aliases bound to explicit identities, a MAC-keyed fleet registry with layered readiness states, and per-route failure isolation with bounded queue/drop/reconnect diagnostics. Do not build model mapping persistence, N-sensor IK, or the Studio mapping workspace (Phases 22-24).

</domain>

<decisions>
## Implementation Decisions

### Multi-slave discovery & route binding
- Route all verified slave self-identities discovered on the STEP_ESP32 AP, capped at the firmware peer slot limit (6).
- Fail closed on duplicate MAC; if a known route later reports a different stable identity, retain the original as offline and register the new identity as a distinct device (Phase 20 rule).
- Master at 192.168.4.1 and the Windows STA remain required; slaves are N additional TCP/UDP routes.
- Bind each relay session to canonical `esp32:aabbccddeeff` identity and refresh IP without changing the canonical topic token.

### Canonical topics & legacy aliases
- Canonical topics use Phase 20 `device_topic_token`: `/esp/raw/mac_<12hex>` and `/esp/status/mac_<12hex>`.
- Keep `/esp/raw/master`, `/esp/raw/slave`, `/esp/status/master`, `/esp/status/slave` as explicit aliases bound to configured identities, carrying the same payload as the canonical topics (FLEET-02 / COMP-01).
- Alias binding is owned by launch/bridge parameters (`alias_master_device_id` / `alias_slave_device_id`, or first verified role identities) — never “whoever connected first.”
- Publish one aggregate `/esp/fleet/registry` (String/JSON) listing all known MACs and layered states (FLEET-01).

### Failure isolation & diagnostics
- Isolate failures per identity: a failed/stale/reconnecting route must not stop acquisition, health, Identify, or recording for other devices (FLEET-03).
- Keep per-route bounded UDP queues (maxsize=256, drop-oldest) and expose drop_count (and reconnect diagnostics) in health/registry.
- Auto-reconnect only the affected route; registry marks reconnecting/stale without a global relay restart.
- Retain offline/stale MAC rows with last-seen; do not drop from registry solely because TCP died (explicit forget is later-phase).

### Fleet process model & registry visibility
- Prefer one fleet manager / multi-session bridge owning all identity routes and the registry; avoid N+1 independent bridge processes as the primary model.
- Each registry row exposes distinct layered fields: discovery, command, route, orientation freshness, synchronization, rate, plus drops/reconnects — not a single collapsed connection_state.
- Phase 21 is backend/ROS contracts first; full multi-row mapping UI is Phase 24. A minimal HealthPanel/debug surface for registry JSON is allowed if cheap.
- Keep `/esp/status/pair` publishing when aliases are bound for COMP-01; registry is authoritative for N>2.

### Claude's Discretion
- Exact JSON schema field names and schema version string for registry/health extensions, provided layered states and drop/reconnect diagnostics remain visible.
- Exact listen-port allocation scheme for N slave TCP relays (contiguous ports vs dynamic map), provided each device has an isolated route.
- Whether legacy single-role bridge entrypoints remain thin wrappers or are folded into the fleet manager, provided aliases and isolation semantics hold.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/stepesp_tcp_udp_relay.py` — identity-bound sessions, UdpRouter with per-host Queue(maxsize=256) drop-oldest, currently one optional `--slave-host`.
- `scripts/start_stepesp_wireless.ps1` — discovers candidates, currently fails closed if >1 verified slave without `-ExpectedSlaveDeviceId`.
- `backend/rehab_robotics_bridge/esp32_bridge_node.py` — role publishers `/esp/raw/{node_id}`, pair health, Identify service; Phase 20 `device_topic_token` helper reserved for Phase 21 publishers.
- Firmware master already tracks up to `MAX_SLAVE_STATUS_SLOTS` (6) peers with identity inventory.

### Established Patterns
- Identity bind only from verified `record=self` id-v1 rows; peer inventory is not session identity.
- Fail closed on ambiguous or incomplete identity; reason-coded health.
- Acquisition/recording must not block on diagnostics or Identify.

### Integration Points
- Extend wireless launcher + relay for N verified slaves.
- Extend or replace bridge with multi-session fleet manager publishing canonical + alias + registry topics.
- Preserve pair health and fixed Master/Slave aliases for compatibility.
- Deterministic tests for multi-route isolation, DHCP/IP refresh without topic change, and drop counters.

</code_context>

<specifics>
## Specific Ideas

User wants new sensors to appear and later assign body parts (Phase 24 panel). Phase 21 must make every connected/known device independently routable and observable so that panel has real fleet data. Stay on ubcvisitor for agent work; STEP_ESP32 acquisition remains an operator-run path.

</specifics>

<deferred>
## Deferred Ideas

- Model catalog, mapping store, Apply transactions — Phase 22.
- N-sensor calibration and official OpenSim IK — Phase 23.
- Dedicated Studio mapping workspace (segment selectors, Draft/Saved/Applied) — Phase 24.
- Hardware capacity promotion gate / default dynamic mode — Phase 25.
- Explicit “forget device” UX — later than Phase 21 registry retention rule.

</deferred>
