---
phase: 21-n-route-relay-and-canonical-ros-fleet
verified: 2026-07-31T19:05:00Z
status: gaps_found
score: 2/5 must-haves verified
overrides_applied: 0
re_verification: false
gaps:
  - truth: "Each device publishes canonical per-MAC IMU and health data on stable topics after DHCP/reconnect, while Master/Slave aliases remain identity-bound with matching payloads"
    status: failed
    reason: "FleetBridgeNode._run_sessions is an explicit sleep placeholder that never TCP-connects, binds verified self, or publishes IMU/health. Wireless launcher replaced dual esp32_bridge_node with this hollow node, so /esp/raw|status/mac_* and alias topics never receive live payloads; Identify is also absent from fleet_bridge_node."
    artifacts:
      - path: "backend/rehab_robotics_bridge/fleet_bridge_node.py"
        issue: "_run_sessions loops on asyncio.sleep(1.0) with comment 'Placeholder until live TCP sessions bind here'; no socket connect, frame parse, on_session_bound, publish_session_*, or Identify service"
      - path: "scripts/start_stepesp_wireless.ps1"
        issue: "Default wireless path starts only fleet_bridge_node; dual esp32_bridge_node (previous live TCP publishers for /esp/raw/* and /esp32/*/imu) removed"
    missing:
      - "Wire per-route TCP sessions in fleet_bridge_node (reuse Esp32BridgeNode session loop or equivalent) so verified bind creates mac_ publishers and streams frames"
      - "Preserve IdentifyDevice service on the fleet path (MAC-targeted, non-blocking)"
      - "Ensure OpenSim /esp32/{master,slave}/imu consumers still receive typed IMU (fleet String aliases alone do not replace stream publishers)"
  - truth: "Operator can see Master and every current/previously known Slave in one MAC-keyed fleet registry with distinct layered discovery/command/route/freshness/synchronization/rate states"
    status: failed
    reason: "Registry schema and timer publish /esp/fleet/registry, but live sessions never call upsert_connected/on_session_bound — rows stay discovery=configured / route=offline regardless of actual Soft-AP peers."
    artifacts:
      - path: "backend/rehab_robotics_bridge/fleet_bridge_node.py"
        issue: "FleetSessionManager seeds configured/offline rows from routes_json; connected/fresh layered states only update when bind APIs are invoked, which the live node never does"
    missing:
      - "Drive registry route/command/freshness/rate from real session health and frame timing"
  - truth: "A failed/stale/reconnecting route does not stop acquisition, health, Identify, or recording for other devices, with visible queue/drop/reconnect diagnostics"
    status: failed
    reason: "UdpRouter drop_count and run_isolated_session_tasks are unit-proven, but the wireless fleet process performs no acquisition or Identify. Isolation of live streams cannot hold when streams and Identify are not owned by the fleet node."
    artifacts:
      - path: "backend/rehab_robotics_bridge/fleet_bridge_node.py"
        issue: "Isolation supervisor wraps placeholder sleep tasks; no per-device acquisition/Identify loop to isolate"
    missing:
      - "Attach isolated supervisor to real per-route TCP/acquire loops"
      - "Propagate relay drop_count into fleet registry/health on the live path (APIs exist; no producer wiring from relay→fleet)"
---

# Phase 21: N-Route Relay and Canonical ROS Fleet Verification Report

**Phase Goal:** Operators can observe and use every known IMU through failure-isolated, identity-keyed ROS routes.
**Verified:** 2026-07-31T19:05:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ------- | ---------- | -------------- |
| 1 | Operator can see Master and every current/previously known Slave in one MAC-keyed fleet registry with distinct discovery, command, route, orientation freshness, synchronization, and rate states (SC1 / FLEET-01). | ✗ FAILED | `build_fleet_registry` / `FleetRegistryStore` emit `oe_esp32.fleet_registry.v1` with required layered fields and offline retention (`fleet_bridge_node.py` ~163–230, 233–367). Unit tests cover schema, offline rows, and identity swap. **Live gap:** `FleetBridgeNode` only seeds `discovery=configured` / `route=offline` from `routes_json` and never transitions rows via TCP bind — operator cannot observe real connected fleet state. |
| 2 | Each device publishes canonical per-MAC IMU/health on stable topics after DHCP/reconnect/ordering changes; fixed Master/Slave aliases remain explicitly identity-bound with matching payloads (SC2 / FLEET-02 / ID-02). | ✗ FAILED | Helpers proven: `canonical_topic_paths` + `device_topic_token`, alias mirror via `publish_session_raw/health`, role-resolved aliases, pair health when bound (`fleet_bridge_node.py` 106–109, 543–603). Unit tests cover payload parity, DHCP topic stability, and role-not-order binding. **Live gap:** `_run_sessions` is a sleep placeholder (lines 800–836); wireless launcher starts only this node (`start_stepesp_wireless.ps1` ~544) after removing dual `esp32_bridge_node`. No live `/esp/raw/mac_*`, aliases, or Identify. OpenSim still expects `/esp32/{master,slave}/imu` which fleet explicitly does not mirror. |
| 3 | Failed/stale/reconnecting route does not stop acquisition, health, Identify, or recording for others; bounded queue/drop/reconnect diagnostics remain visible (SC3 / FLEET-03). | ✗ FAILED | Relay `UdpRouter.drop_counts` + drop-oldest maxsize=256 verified (`stepesp_tcp_udp_relay.py` ~701–760). `run_isolated_session_tasks` + registry `mark_reconnecting` / `record_udp_drops` unit-proven. **Live gap:** fleet owns no acquisition/Identify loops to isolate; wireless stack cannot satisfy “does not stop acquisition/Identify for others” when those paths are absent. |
| 4 | Windows relay accepts Master + every verified Slave ≤6 on isolated TCP listen ports / shared UDP demux; IP refresh keeps canonical device_id; duplicate MAC fails closed. | ✓ VERIFIED | `MAX_SLAVE_ROUTES=6`, `--slave-route`, `parse_slave_routes`, `remap_relay_endpoint` / `UdpRouter.remap_host`, fail-closed duplicates (`stepesp_tcp_udp_relay.py`). Launcher routes all verified slaves with contiguous ports and optional ExpectedSlaveDeviceIds (`start_stepesp_wireless.ps1`). Covered by `test_stepesp_udp_relay` (94-suite green). |
| 5 | Deterministic offline tests prove multi-route relay, registry/alias contracts, drop counters, and isolation supervisor without STEP_ESP32 Wi-Fi. | ✓ VERIFIED | `python -m unittest backend.test.test_stepesp_udp_relay backend.test.test_fleet_bridge backend.test.test_esp32_controls -v` → **94 OK**, 0 fail/error (~0.39s). |

**Score:** 2/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | ----------- | ------ | ------- |
| `scripts/stepesp_tcp_udp_relay.py` | N-slave identity-bound relay, remap, drop_count | ✓ VERIFIED | Substantive N-route CLI, registry remap, per-host drop_counts; wired by launcher. |
| `scripts/start_stepesp_wireless.ps1` | Discover/route all verified ≤6; fleet launch params | ⚠️ HOLLOW wiring | N-route relay args + `routes_json`/`alias_*` to `fleet_bridge_node` present; target process does not stream. |
| `backend/rehab_robotics_bridge/fleet_bridge_node.py` | Multi-session fleet manager + registry + aliases | ✗ STUB (live path) | Registry/alias/manager helpers substantive and tested; `FleetBridgeNode._run_sessions` is a sleep placeholder — live ownership missing. |
| `backend/rehab_robotics_bridge/esp32_bridge_node.py` | Shared helpers; health drop fields; single-session wrapper | ✓ VERIFIED | `device_topic_token`, health `drop_count`; still runnable for USB/legacy launch (`use_fleet_bridge:=false`). |
| `backend/setup.py` | `fleet_bridge_node` console_script | ✓ VERIFIED | Entry registered. |
| `backend/test/test_fleet_bridge.py` | Registry/alias/isolation contracts | ✓ VERIFIED | Substantive suite; exercises helpers via stubs, not live TCP. |
| `backend/test/test_stepesp_udp_relay.py` | N-route / drop / launcher contracts | ✓ VERIFIED | Includes fleet launcher source contracts (single `fleet_bridge_node`). |
| `backend/launch/rehab_robotics.launch.py` | Optional `use_fleet_bridge` | ✓ VERIFIED | Opt-in fleet; default dual `esp32_bridge_node` preserved for non-wireless. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `start_stepesp_wireless.ps1` | `stepesp_tcp_udp_relay.py` | `--slave-route` per verified slave | ✓ WIRED | Contiguous listen ports + expected IDs passed. |
| `start_stepesp_wireless.ps1` | `fleet_bridge_node` | `routes_json` + `alias_*` | ⚠️ PARTIAL | Process started; no live TCP consume of relay ports. |
| `device_topic_token` | `/esp/raw/mac_<12hex>` | `FleetDeviceSession.bind_verified_self` | ⚠️ PARTIAL | Publishers created only after bind; live node never binds. |
| Fleet sessions | `/esp/fleet/registry` | timer + `build_fleet_registry` | ⚠️ HOLLOW | Topic publishes static configured/offline snapshot. |
| `alias_master_device_id` | `/esp/raw/master` | `_mirror_alias_payload` | ⚠️ PARTIAL | Mirror helpers tested; no live publisher feed. |
| `UdpRouter.route_datagram` | `drop_count` | drop-oldest increment | ✓ WIRED | Per-host counters in relay. |
| Session reconnect loop | Sibling sessions | `run_isolated_session_tasks` | ⚠️ PARTIAL | Supervisor wired around placeholder sleeps, not real streams. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `FleetBridgeNode` registry timer | `devices[]` layered states | `routes_json` seed only | No live bind/health | ✗ DISCONNECTED |
| Canonical `/esp/raw/mac_*` | session raw String | `publish_session_raw` | Only when tests call helpers | ✗ DISCONNECTED (live) |
| Alias `/esp/raw/master\|slave` | mirrored payload | same as canonical | Same | ✗ DISCONNECTED (live) |
| Relay UDP demux | per-host queues | ESP UDP → localhost TCP | Yes (relay path) | ✓ FLOWING |
| OpenSim `/esp32/*/imu` | typed IMU | previously `esp32_bridge_node` | Not started on wireless | ✗ DISCONNECTED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Fleet + relay + controls unit suite | `python -m unittest backend.test.test_stepesp_udp_relay backend.test.test_fleet_bridge backend.test.test_esp32_controls -v` | 94 OK, 0 fail | ✓ PASS |
| Live fleet TCP bind | (not run — no Wi-Fi; source shows sleep placeholder) | N/A | ✗ FAIL (source) |

### Probe Execution

| Probe | Command | Result | Status |
| ----- | ------- | ------ | ------ |
| — | — | No phase-declared `scripts/*/tests/probe-*.sh` | SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| ID-02 | 21-01..04 | Canonical identity/topic stable across DHCP/reconnect/order | ✗ BLOCKED | Relay identity remap VERIFIED; ROS mac_ lifecycle not live. |
| FLEET-01 | 21-02, 21-04 | MAC-keyed layered registry | ✗ BLOCKED | Schema/helpers VERIFIED; live states hollow. |
| FLEET-02 | 21-02, 21-03 | Canonical + explicit Master/Slave aliases | ✗ BLOCKED | Alias contracts unit-tested; live publish absent. |
| FLEET-03 | 21-01, 21-04 | Failure isolation + diagnostics | ✗ BLOCKED | Relay drops + isolation supervisor unit-OK; live acquisition/Identify missing on fleet path. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `fleet_bridge_node.py` | ~813–815 | Explicit `Placeholder until live TCP sessions bind here` + `asyncio.sleep(1.0)` session loop | 🛑 BLOCKER | Wireless stack publishes no IMU/health; phase goal unmet |
| `fleet_bridge_node.py` | ~803–806 | Comment claims “Live TCP/UDP streaming continues to use Esp32BridgeNode” | 🛑 BLOCKER | Contradicted by launcher which no longer starts `esp32_bridge_node` |
| `fleet_bridge_node.py` | — | No `IdentifyDevice` / `create_service` | 🛑 BLOCKER | Phase 20 Identify regresses on default wireless path |
| `start_stepesp_wireless.ps1` | ~547 | OpenSim still uses `/esp32/master/imu` + `/esp32/slave/imu` | ⚠️ WARNING | Typed IMU topics have no publisher under fleet-only launch |

Debt-marker gate: no `TBD`/`FIXME`/`XXX` in phase-modified core files; the placeholder comment is an explicit unfinished-implementation marker treated as blocker.

### Human Verification Required

None recorded for status purposes — automated gaps block advancement. After gap closure, operator Soft-AP validation (multi-slave registry, alias parity, isolation under forced slave drop) should be harvested as human checks; Wi-Fi was not exercised per instructions.

### Gaps Summary

Phase 21 delivered a solid **offline contract layer**: N-route relay, launcher discovery, registry/alias/diagnostics helpers, and a green 94-test suite. The **goal is not achieved** because `fleet_bridge_node` does not own live TCP sessions. Replacing dual `esp32_bridge_node` with this placeholder in `start_stepesp_wireless.ps1` disconnects IMU/health/Identify/OpenSim typed topics on the default wireless path. Gap closure must wire real per-route sessions (bind → mac_ publishers → stream + Identify) under `run_isolated_session_tasks`, then re-verify SC1–SC3.

Recommended fix focus: `/gsd:plan-phase 21 --gaps` (or gap-closure plans) targeting live session ownership in `fleet_bridge_node.py` and wireless stack integrity — not Phase 22 mapping work.

---

_Verified: 2026-07-31T19:05:00Z_
_Verifier: Claude (gsd-verifier)_
