---
phase: 21-n-route-relay-and-canonical-ros-fleet
plan: "05"
subsystem: backend/fleet-bridge
tags: [fleet, tcp-session, imu, identify-device, reconnect]
dependency_graph:
  requires: [21-04]
  provides: [fleet-tcp-session-loop, typed-imu-publishers, identify-service]
  affects: [fleet_bridge_node, registry-live-states, opensim-imu-consumers]
tech_stack:
  added: []
  patterns:
    - asyncio per-route reconnect loop with exponential backoff
    - OE binary frame reader with control text interleave scanner
    - asyncio.run_coroutine_threadsafe for ROS service -> asyncio bridge
    - Queue-based IDENTIFY reply routing with drop-oldest eviction
key_files:
  created: []
  modified:
    - backend/rehab_robotics_bridge/fleet_bridge_node.py
decisions:
  - ACC_SCALE and GYR_SCALE defined locally in fleet_bridge_node (not re-imported) to prevent circular import risk
  - Imu publishers created unconditionally for both master and slave roles; publish only fires when alias is bound
  - _read_fleet_frames loops forever while rclpy.ok() so reconnect lifecycle is owned by _connect_and_stream_route
  - reader._buffer peeked directly for SENSORS line to avoid blocking with wait_for on an optional line
metrics:
  duration: ~25 minutes
  completed: 2026-08-05
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 21 Plan 05: Wire Live TCP Session Loop Summary

Live per-route TCP session loop with IDENTITY handshake, OE frame streaming, typed Imu publish, and IdentifyDevice service wired into fleet_bridge_node.

## What Was Built

The asyncio.sleep placeholder in `FleetBridgeNode._run_sessions` was replaced with a real per-route TCP connection lifecycle. Each configured relay route now independently TCP-connects to its relay listen port, performs the IDENTITY?/REDPITAYA/START handshake, verifies the reported device_id against the configured expected_device_id, calls `on_session_bound` to update the registry, streams OE binary frames, and reconnects with exponential backoff on failure — without cancelling sibling sessions.

### New coroutines and methods added to FleetBridgeNode

| Symbol | Purpose |
|--------|---------|
| `_run_sessions` | Replaced placeholder body; now delegates to `_connect_and_stream_route` via `run_isolated_session_tasks` |
| `_fleet_handshake` | IDENTITY?/REDPITAYA/START sequence with `expected_device_id` verification before `on_session_bound` |
| `_read_fleet_frames` | OE binary frame reader with control text scanner; routes IDENTIFY_ACK/ERR to per-session queue |
| `_publish_fleet_frame` | Decodes OE payload; calls `publish_session_raw`; publishes typed `sensor_msgs/Imu` for alias-bound sessions |
| `_connect_and_stream_route` | Per-route reconnect loop with exponential backoff, `on_session_reconnecting`, and `apply_udp_drop_count` |
| `_identify_fleet_device` | ROS service handler; routes IdentifyDevice request to correct per-session asyncio writer |
| `_send_fleet_identify_command` | Async command sender; drains identify_queue for correlated IDENTIFY_ACK/ERR reply |

### Per-session state added to `__init__`

- `_active_writers`: list of per-session `asyncio.StreamWriter | None`
- `_session_locks`: list of per-session `asyncio.Lock | None` (serializes IDENTIFY command writes)
- `_identify_queues`: list of per-session `asyncio.Queue | None` (maxsize=256, drop-oldest)
- `_imu_pubs`: dict keyed by role ('master'/'slave') for `/esp32/master/imu` and `/esp32/slave/imu`

### ROS parameters declared

- `reconnect_delay_s` (default 5.0)
- `handshake_timeout_s` (default 15.0)
- `identify_timeout_s` (default 3.0)

## Verification Results

```
AST check: PASSED
Placeholder 'Placeholder until live TCP sessions bind': 0 occurrences
_connect_and_stream_route occurrences: 2 (definition + call site)
IdentifyDevice occurrences: 4 (import, service create, handler def, send coroutine)
/esp32/master/imu + /esp32/slave/imu: 2 occurrences

Test suite: Ran 94 tests in 0.430s — OK, 0 failures
```

## Deviations from Plan

None - plan executed exactly as written.

## Threat Mitigations Applied

All STRIDE mitigations from the plan threat register were applied:

| Threat | Mitigation |
|--------|-----------|
| T-21-05-01 Spoofing | `parse_identity_self` + `expected_device_id` check in `_fleet_handshake` before `on_session_bound`; mismatch raises RuntimeError and triggers reconnect |
| T-21-05-03 DoS: malformed IDENTIFY_ACK flooding | Queue maxsize=256 with drop-oldest; `parse_identify_reply` rejects uncorrelated lines silently |
| T-21-05-05 EoP: IdentifyDevice without connected session | `_active_writers[index] is None` check returns 'offline' before any hardware I/O |

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wire live TCP session loop and typed Imu publishers | f6ea260 | backend/rehab_robotics_bridge/fleet_bridge_node.py |

## Self-Check: PASSED

- fleet_bridge_node.py modified: FOUND
- Commit f6ea260 exists: FOUND
- AST parses cleanly: PASSED
- Placeholder string absent: CONFIRMED
- 94 tests pass: CONFIRMED
