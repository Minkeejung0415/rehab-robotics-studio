---
phase: 21-n-route-relay-and-canonical-ros-fleet
verified: 2026-08-05T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 2/5
  gaps_closed:
    - "Each device publishes canonical per-MAC IMU/health on stable topics after DHCP/reconnect/ordering changes; fixed Master/Slave aliases remain explicitly identity-bound with matching payloads (SC2 / FLEET-02 / ID-02)"
    - "Operator can see Master and every current/previously known Slave in one MAC-keyed fleet registry with distinct layered discovery/command/route/freshness/synchronization/rate states (SC1 / FLEET-01)"
    - "Failed/stale/reconnecting route does not stop acquisition, health, Identify, or recording for others; bounded queue/drop/reconnect diagnostics remain visible (SC3 / FLEET-03)"
  gaps_remaining: []
  regressions: []
---

# Phase 21: N-Route Relay and Canonical ROS Fleet Verification Report

**Phase Goal:** Operators can observe and use every known IMU through failure-isolated, identity-keyed ROS routes.
**Verified:** 2026-08-05T00:00:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure plans 21-05 and 21-06

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ------- | ---------- | -------------- |
| 1 | Operator can see Master and every current/previously known Slave in one MAC-keyed fleet registry with distinct discovery, command, route, orientation freshness, synchronization, and rate states (SC1 / FLEET-01). | VERIFIED | `_connect_and_stream_route` calls `self._manager.on_session_bound` inside `_fleet_handshake` after `expected_device_id` verification (fleet_bridge_node.py lines 895–905). Registry row transitions from `route=offline` to `route=connected` on bind. `FleetLiveSessionContractTest.test_fleet_handshake_binds_session_on_valid_identity` exercises this path with a mock TCP server and asserts `session._bound_device_id` and `registry row route == 'connected'`. |
| 2 | Each device publishes canonical per-MAC IMU/health on stable topics after DHCP/reconnect/ordering changes; fixed Master/Slave aliases remain explicitly identity-bound with matching payloads (SC2 / FLEET-02 / ID-02). | VERIFIED | `_read_fleet_frames` calls `_publish_fleet_frame` per OE frame (line 1020). `_publish_fleet_frame` calls `self._manager.publish_session_raw` (line 1062) and publishes typed `sensor_msgs/Imu` on `/esp32/master/imu` or `/esp32/slave/imu` when the session's role matches an alias (lines 1066–1090). Publishers created unconditionally in `__init__` (lines 787–788). `test_fleet_frame_publish_calls_session_raw_publish` and `test_imu_publishers_created_for_master_and_slave_roles` verify both paths. |
| 3 | Failed/stale/reconnecting route does not stop acquisition, health, Identify, or recording for others; bounded queue/drop/reconnect diagnostics remain visible (SC3 / FLEET-03). | VERIFIED | `_connect_and_stream_route` wraps real session coroutines (not sleep placeholders) inside `run_isolated_session_tasks` (lines 860–866). On TCP disconnect, `on_session_reconnecting` is called (lines 1127–1130) and `apply_udp_drop_count` propagates relay drop_count before reconnect (lines 1124–1126). Sibling isolation verified by `test_session_reconnecting_does_not_cancel_siblings` and `test_apply_udp_drop_count_called_on_reconnect`. `IdentifyDevice` service created on `/esp32/fleet/identify` (line 791); `test_identify_fleet_device_returns_offline_when_no_writer` confirms the offline guard. |
| 4 | Windows relay accepts Master + every verified Slave <=6 on isolated TCP listen ports / shared UDP demux; IP refresh keeps canonical device_id; duplicate MAC fails closed. | VERIFIED | Unchanged from initial verification. `MAX_SLAVE_ROUTES=6`, `--slave-route`, `parse_slave_routes`, `remap_relay_endpoint` / `UdpRouter.remap_host`, fail-closed duplicates in `stepesp_tcp_udp_relay.py`. Covered by `test_stepesp_udp_relay` (94-suite green). |
| 5 | Deterministic offline tests prove multi-route relay, registry/alias contracts, drop counters, and isolation supervisor without STEP_ESP32 Wi-Fi. | VERIFIED | Full suite: `python -m unittest backend.test.test_fleet_bridge backend.test.test_stepesp_udp_relay backend.test.test_esp32_controls -v` — **100 OK, 0 failures, 0 errors** (0.740s). `FleetLiveSessionContractTest` contributes 6 new tests (total 35 in test_fleet_bridge.py). |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | ----------- | ------ | ------- |
| `backend/rehab_robotics_bridge/fleet_bridge_node.py` | Live per-route TCP session loop with identity bind, frame publish, Identify service, reconnect, drop_count propagation | VERIFIED | `_connect_and_stream_route`, `_fleet_handshake`, `_read_fleet_frames`, `_publish_fleet_frame`, `_identify_fleet_device`, `_send_fleet_identify_command` all present and substantive. AST parses cleanly. Placeholder comment absent (grep count = 0). |
| `backend/test/test_fleet_bridge.py` | `FleetLiveSessionContractTest` with >= 6 test methods | VERIFIED | Class present (grep count = 1). 6 test methods covering session bind, disconnect isolation, Identify offline guard, Imu publisher existence, frame publish, and drop_count propagation. 35 total test methods in file. |
| `scripts/stepesp_tcp_udp_relay.py` | N-slave identity-bound relay, remap, drop_count | VERIFIED | Unchanged from initial verification. |
| `backend/rehab_robotics_bridge/esp32_bridge_node.py` | Shared helpers; health drop fields; single-session wrapper | VERIFIED | Unchanged from initial verification. |
| `backend/setup.py` | `fleet_bridge_node` console_script | VERIFIED | Unchanged from initial verification. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `FleetBridgeNode._run_sessions` | `_connect_and_stream_route` | `run_isolated_session_tasks` with lambda factories | WIRED | Lines 860–866: `[lambda i=index: self._connect_and_stream_route(i) for index in range(len(self._sessions))]` |
| `_connect_and_stream_route` | `FleetSessionManager.on_session_bound` | `_fleet_handshake` calls `self.on_session_bound` after identity verification | WIRED | Lines 900–905: after `reported == session.expected_device_id` guard |
| `_read_fleet_frames` | `self._manager.publish_session_raw` | `_publish_fleet_frame` call per decoded OE frame | WIRED | Line 1062: `self._manager.publish_session_raw(session, raw_json)` |
| `FleetBridgeNode.__init__` | `/esp32/master/imu` and `/esp32/slave/imu` | `self.create_publisher(Imu, ...)` | WIRED | Lines 787–788: unconditional publisher creation for both roles |
| `FleetBridgeNode.__init__` | `IdentifyDevice` service on `/esp32/fleet/identify` | `self.create_service(IdentifyDevice, ...)` | WIRED | Line 791 |
| `_connect_and_stream_route` (on disconnect) | `on_session_reconnecting` | exception handler calls manager method | WIRED | Lines 1127–1130: `self._manager.on_session_reconnecting(session, last_seen_us=...)` |
| `_connect_and_stream_route` (on disconnect) | `apply_udp_drop_count` | relay drop_count fetched from registry and applied before reconnect | WIRED | Lines 1124–1126: `self._manager.apply_udp_drop_count(device_id, relay_state.udp_drop_count)` |
| `start_stepesp_wireless.ps1` | `stepesp_tcp_udp_relay.py` | `--slave-route` per verified slave | WIRED | Unchanged from initial verification |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `FleetBridgeNode` registry timer | `devices[]` layered states | `routes_json` seed + live `on_session_bound` / `on_session_reconnecting` calls from `_connect_and_stream_route` | Yes — bind transitions rows to `route=connected` | FLOWING |
| Canonical `/esp/raw/mac_*` | session raw String | `_publish_fleet_frame` -> `publish_session_raw` called per decoded OE frame | Yes — real OE binary frame decoded | FLOWING |
| Alias `/esp/raw/master` / `/esp/raw/slave` | mirrored payload | same as canonical via `publish_session_raw` alias mirror | Yes | FLOWING |
| `/esp32/master/imu` / `/esp32/slave/imu` | `sensor_msgs/Imu` | `_publish_fleet_frame` decodes OE channels for quat + accel + gyro and calls `imu_pub.publish(imu_msg)` | Yes — real channel decode with ACC_SCALE / GYR_SCALE / QUAT_SCALE | FLOWING |
| Relay UDP demux | per-host queues | ESP UDP -> localhost TCP | Yes (relay path) | FLOWING (unchanged) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| fleet_bridge_node.py AST validity | `python -c "import ast; ast.parse(open('backend/rehab_robotics_bridge/fleet_bridge_node.py').read()); print('AST OK')"` | `AST OK` | PASS |
| Placeholder comment absent | `grep -c "Placeholder until live TCP" backend/rehab_robotics_bridge/fleet_bridge_node.py` | `0` | PASS |
| `_connect_and_stream_route` present (definition + call) | `grep -c "_connect_and_stream_route" backend/rehab_robotics_bridge/fleet_bridge_node.py` | `2` | PASS |
| `IdentifyDevice` wired (import + service + handler + coroutine) | `grep -c "IdentifyDevice" backend/rehab_robotics_bridge/fleet_bridge_node.py` | `4` | PASS |
| Imu publisher topics present | count of `/esp32/master/imu` and `/esp32/slave/imu` occurrences | `2` | PASS |
| `FleetLiveSessionContractTest` class present | `grep -c "FleetLiveSessionContractTest" backend/test/test_fleet_bridge.py` | `1` | PASS |
| Full test suite (100 tests, 0 failures) | `python -m unittest backend.test.test_fleet_bridge backend.test.test_stepesp_udp_relay backend.test.test_esp32_controls -v` | `Ran 100 tests in 0.740s — OK` | PASS |

### Probe Execution

| Probe | Command | Result | Status |
| ----- | ------- | ------ | ------ |
| — | — | No phase-declared `scripts/*/tests/probe-*.sh` | SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| ID-02 | 21-01..05 | Canonical identity/topic stable across DHCP/reconnect/order | SATISFIED | `_fleet_handshake` binds only after `expected_device_id` match; canonical topic from `device_topic_token` is set at bind and never changes on reconnect. `test_fleet_handshake_binds_session_on_valid_identity` exercises this. |
| FLEET-01 | 21-02, 21-04, 21-05 | MAC-keyed layered registry with live state transitions | SATISFIED | `on_session_bound` / `on_session_reconnecting` called from `_connect_and_stream_route` lifecycle; registry rows advance from `route=offline` to `route=connected` on bind. |
| FLEET-02 | 21-02, 21-03, 21-05 | Canonical + explicit Master/Slave aliases + typed Imu | SATISFIED | `publish_session_raw` mirrors to alias topics; `/esp32/master/imu` and `/esp32/slave/imu` publishers created in `__init__` and publish per-frame from `_publish_fleet_frame`. |
| FLEET-03 | 21-01, 21-04, 21-05 | Failure isolation + diagnostics | SATISFIED | `run_isolated_session_tasks` wraps real `_connect_and_stream_route` coroutines. `on_session_reconnecting` + `apply_udp_drop_count` called on disconnect. `IdentifyDevice` service routes to per-session writer and returns `offline` when writer is `None`. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `fleet_bridge_node.py` | 856–858 | `asyncio.sleep(1.0)` in no-sessions guard branch | Info | Legitimate idle path when `self._sessions` is empty (no routes configured); not a placeholder — the real session loop is the `run_isolated_session_tasks` block at lines 860–866. |

No `TBD`, `FIXME`, or `XXX` markers found in either modified file. No unreferenced debt markers.

### Human Verification Required

None. All SC1/SC2/SC3 truths are verified by deterministic offline tests using mock asyncio streams. Wi-Fi live validation (multi-slave registry display, alias parity under Soft-AP, forced slave disconnect and reconnect diagnostics) remains an operator validation item but does not block phase goal achievement — per original gap closure plan scope.

### Gaps Summary

No gaps. All three previously failing success criteria are now verified:

- **SC1 (FLEET-01):** Registry live-state transitions are wired. `_fleet_handshake` calls `on_session_bound` after identity verification; `_connect_and_stream_route` calls `on_session_reconnecting` on TCP disconnect.
- **SC2 (FLEET-02 / ID-02):** Live IMU/health publishing is wired. `_read_fleet_frames` decodes OE frames and calls `_publish_fleet_frame`, which publishes both canonical String payloads and typed `sensor_msgs/Imu` on `/esp32/master/imu` / `/esp32/slave/imu`.
- **SC3 (FLEET-03):** Failure isolation is wired around real acquisition coroutines, not sleep placeholders. `IdentifyDevice` service guards against offline sessions. Drop count is propagated from relay to registry before each reconnect attempt.

The previously passing items (SC4: relay + launcher multi-slave routing; SC5: deterministic offline test suite) remain verified and show no regressions. Total test count increased from 94 to 100.

---

_Verified: 2026-08-05T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
