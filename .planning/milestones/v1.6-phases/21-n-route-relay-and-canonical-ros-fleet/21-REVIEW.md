---
phase: 21-n-route-relay-and-canonical-ros-fleet
reviewed: 2026-07-31T19:05:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - scripts/start_stepesp_wireless.ps1
  - scripts/stepesp_tcp_udp_relay.py
  - backend/rehab_robotics_bridge/fleet_bridge_node.py
  - backend/rehab_robotics_bridge/esp32_bridge_node.py
  - backend/launch/rehab_robotics.launch.py
  - backend/test/test_fleet_bridge.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 21: Code Review Report

**Reviewed:** 2026-07-31T19:05:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Focused review of plans 21-01..04 (N-route relay, `fleet_bridge_node`, Master/Slave aliases, isolation diagnostics) with emphasis on launcher injection, fail-closed identity, per-route isolation, and regression of the wireless 1+1 path.

**Verdict:** Relay/discovery/identity contracts look solid and fail-closed. The wireless stack has a **critical architectural hole**: the launcher now starts only `fleet_bridge_node`, but that node’s session supervisor is still a sleep placeholder and never binds TCP streams, so aliases, canonical `mac_` topics, Identify, and OpenSim IMU inputs do not receive live data.

## Must-fix (CRITICAL)

1. **Wire live TCP (or restore an equivalent stream publisher) inside `fleet_bridge_node` before treating wireless fleet launch as complete** — or temporarily reintroduce streaming publishers for master + alias slave without re-breaking N-route relay. Until then, Soft-AP wireless acquisition/OpenSim/GUI raw topics are dead after 21-03.

## Critical Issues

### CR-01: Wireless fleet launch has no live stream publisher

**File:** `backend/rehab_robotics_bridge/fleet_bridge_node.py:800-836`
**Also:** `scripts/start_stepesp_wireless.ps1:544-549`

**Issue:** Plan 21-03 replaced dual `esp32_bridge_node` wireless spawns with a single `fleet_bridge_node`. `_run_sessions` still only `await asyncio.sleep(1.0)` and never connects, binds verified self, publishes `/esp/raw|status/mac_*`, mirrors aliases, serves Identify, or publishes typed `/esp32/{master,slave}/imu`. OpenSim is still launched against those IMU topics; the GUI still expects `/esp/raw/master` and `/esp/raw/slave`. Registry rows remain configured/offline forever. This breaks FLEET-01/02 observability and COMP-01 1+1 acquisition on the operator wireless path.

**Fix:**
```python
# In FleetBridgeNode._run_sessions, replace the sleep placeholder with a
# per-route session that:
# 1) TCP-connects to route host:port (WSL listen side of the relay)
# 2) verifies expected_device_id (fail closed)
# 3) calls manager.on_session_bound(...)
# 4) publishes canonical + alias payloads (and typed IMU if OpenSim still consumes)
# 5) on disconnect: manager.on_session_reconnecting(session); retry only that route
#
# Prefer extracting Esp32BridgeNode stream/publish helpers into a shared
# session class reused by fleet (research recommendation) rather than
# re-adding dual ros2 run esp32_bridge_node to the wireless launcher
# (tests intentionally forbid that regression).
```

Do **not** ship Soft-AP “complete stack” docs claiming live aliases/registry freshness until this is done.

## Warnings

### WR-01: Operator path params interpolated into `bash -lc` without full escaping

**File:** `scripts/start_stepesp_wireless.ps1:520-547`

**Issue:** Device IDs and `routes_json` are well constrained (canonical `esp32:` + JSON apostrophe escape). `$RosInstall`, `$OpenSimInstall`, `$OpenSimModel`, `$openSimRunner`, and `$bridgeLog` are still interpolated into bash command strings; some readiness checks quote paths, but `$rosEnvironment` / `$openSim` do not. A crafted `-OpenSimModel` / `-RosInstall` value can break out of the WSL command (operator-parameter injection). Not device-sourced, but the launcher is the trust boundary called out for Phase 21.

**Fix:** Pass paths as single-quoted bash literals after escaping `'` → `'\''` (same pattern as `$routesJsonBash`), or build argv arrays and avoid `bash -lc` string concatenation for operator-controlled paths.

### WR-02: Relay CLI allows routes without `expected_device_id`

**File:** `scripts/stepesp_tcp_udp_relay.py:801-823`, `869-868`

**Issue:** `_parse_slave_route_spec` permits empty device id (`HOST:PORT:` → `expected_device_id=None`). With `expected_device_id is None`, identity-unsupported endpoints continue as unverified legacy routes. The wireless launcher always supplies IDs, but a manual CLI invocation can open fail-open routes and weaken ID-02 for N-route ops.

**Fix:**
```python
if not device_raw:
    raise ValueError('slave route EXPECTED_DEVICE_ID is required')
expected = normalize_device_id(device_raw)
```
Keep singular `--slave-host` legacy only behind an explicit `--allow-unverified` flag if still needed.

### WR-03: Isolation supervisor is correct but not yet on the live acquisition path

**File:** `backend/rehab_robotics_bridge/fleet_bridge_node.py:35-72`, `800-836`

**Issue:** `run_isolated_session_tasks` correctly avoids sibling cancel and is covered by unit tests. Because session bodies are placeholders, FLEET-03 isolation is proven only for the future supervisor shape — not for live acquisition/Identify/recording. Relay `StepEspRelay.serve()` itself is resilient (per-client errors swallowed; `serve_forever` stays up), which is good, but ROS-side isolation remains unexercised in production until CR-01 is fixed.

**Fix:** When implementing CR-01, keep all per-route work inside `run_isolated_session_tasks` (or equivalent); never wrap live sessions in a fatal `asyncio.gather` without `return_exceptions` + per-task guards.

## Info

### IN-01: `Start-Process -ArgumentList` uses a joined string for the relay

**File:** `scripts/start_stepesp_wireless.ps1:506-517`

**Issue:** Args are built as a list then joined into one string for `Start-Process`. Windows `ProcessStartInfo.Arguments` can work, but array form is less fragile with the workspace path containing `#`, spaces, and `'`. Tests assert list-construction tokens in source, not runtime argv safety.

**Fix:** Prefer `Start-Process -FilePath python.exe -ArgumentList $relayArgList.ToArray()`.

### IN-02: Health `drop_count` on `esp32_bridge_node` is additive schema only

**File:** `backend/rehab_robotics_bridge/esp32_bridge_node.py:1010-1021`

**Issue:** Snapshot exposes `drop_count` / `drops`, but fleet wireless no longer runs this node; relay counters are the authoritative UDP drop source and must be plumbed through fleet once sessions are live (partially designed via `apply_udp_drop_count`).

**Fix:** On CR-01, periodically copy `UdpRouter.drop_count(host)` into `FleetSessionManager.apply_udp_drop_count` (side channel or control-plane message).

---

## Focus area notes (no separate finding)

| Area | Assessment |
|------|------------|
| Launcher command injection from device identity / routes_json | **Pass** — canonical ID regex; JSON wrapped in bash single quotes with `'` escaped; alias IDs from verified probes |
| Fail-closed identity (duplicates, >6, master==slave, role mismatch) | **Pass** in launcher + `parse_routes_json` + relay bind |
| N-route relay demux / DHCP remap / drop_count | **Pass** at unit-contract level |
| Regression of 1+1 wireless path | **Fail** — see CR-01 |

---

_Reviewed: 2026-07-31T19:05:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
