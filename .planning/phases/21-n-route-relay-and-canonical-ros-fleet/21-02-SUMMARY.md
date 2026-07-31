---
phase: 21-n-route-relay-and-canonical-ros-fleet
plan: "02"
subsystem: ros-fleet
tags: [fleet, registry, mac-topics, device_topic_token, ros2, identity]

requires:
  - phase: 21-n-route-relay-and-canonical-ros-fleet
    provides: N-route identity-bound relay + wireless launcher (21-01)
  - phase: 20-full-identity-and-confirmed-identify
    provides: device_topic_token, normalize_device_id, verified self bind
provides:
  - fleet_bridge_node multi-session owner with /esp/fleet/registry
  - Canonical /esp/raw|status/mac_<12hex> publisher lifecycle after verified bind
  - oe_esp32.fleet_registry.v1 layered readiness rows with offline retention
affects:
  - 21-03 legacy Master/Slave aliases and pair health
  - 21-04 drop_count / reconnect isolation hardening
  - Phase 24 mapping UI (consumes registry)

tech-stack:
  added: []
  patterns:
    - "FleetSessionManager owns N sessions + shared registry without N+1 bridge processes"
    - "Canonical topics solely from device_topic_token; role/IP are registry metadata"
    - "Offline/stale MAC rows retained with last_seen_us (D-21-12)"

key-files:
  created:
    - backend/rehab_robotics_bridge/fleet_bridge_node.py
    - backend/test/test_fleet_bridge.py
  modified:
    - backend/setup.py
    - backend/test/test_esp32_controls.py

key-decisions:
  - "Primary entry is fleet_bridge_node; esp32_bridge_node remains thin single-session wrapper"
  - "Registry schema id oe_esp32.fleet_registry.v1 with layered discovery/command/route/freshness/sync/rate"
  - "Alias republish and pair health deferred to plan 21-03"

patterns-established:
  - "Pattern: create publishers only after verified self matches expected_device_id"
  - "Pattern: identity change marks prior MAC offline and registers the new MAC"

requirements-completed: [ID-02, FLEET-01, FLEET-02]

duration: 35min
completed: 2026-07-31
---

# Phase 21 Plan 02: Fleet Registry + Canonical MAC Topics Summary

**One fleet_bridge_node process publishes identity-stable `/esp/raw|status/mac_<12hex>` topics and a layered `oe_esp32.fleet_registry.v1` snapshot on `/esp/fleet/registry`, retaining offline MACs.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-07-31T18:22:00Z
- **Completed:** 2026-07-31T18:57:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Canonical topic paths reuse Phase 20 `device_topic_token` (collision-safe across low-32 MAC collisions).
- `FleetRegistryStore` / `build_fleet_registry` emit layered discovery/command/route/orientation_freshness/synchronization/rate (+ drops/reconnects placeholders) keyed by `device_id`.
- `FleetSessionManager` + `FleetBridgeNode` own Master+Slave route tables from `routes_json`; publishers bind only after verified self; identity swaps keep prior MAC offline.
- `esp32_bridge_node` stays importable/runnable as the single-session debug entry; `fleet_bridge_node` registered in `setup.py`.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED:** `5c580c8` — test(21-02): add failing fleet registry and canonical topic contracts
2. **Task 1+2 GREEN:** `cbfb48e` — feat(21-02): implement fleet registry and multi-session canonical publishers

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `backend/rehab_robotics_bridge/fleet_bridge_node.py` — registry builder, session manager, ROS entry point
- `backend/test/test_fleet_bridge.py` — deterministic registry/topic/session contracts (no ROS master / STEP_ESP32)
- `backend/setup.py` — `fleet_bridge_node` console_script
- `backend/test/test_esp32_controls.py` — Phase 20 guard updated for Phase 21 fleet lifecycle; still bans `/esp32/mac_`

## Decisions Made

- Prefer `fleet_bridge_node` naming from the plan (vs research `esp32_fleet_node`) for the console entry.
- Extract ROS-free `FleetSessionManager` so multi-session/registry contracts unit-test without constructing `rclpy.node.Node`.
- Leave Master/Slave alias republish and `/esp/status/pair` to plan 21-03; leave drop_count hardening to 21-04.
- Live TCP stream loops remain on `Esp32BridgeNode` / relay; fleet node owns registry + canonical publisher lifecycle in this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Register module in sys.modules before dataclass exec**
- **Found during:** Task 1 GREEN
- **Issue:** `importlib` file load left `sys.modules[name]` unset, so `@dataclass` crashed before any assertion ran.
- **Fix:** `sys.modules[spec.name] = module` before `exec_module` in `test_fleet_bridge._load_fleet_module`.
- **Files modified:** `backend/test/test_fleet_bridge.py`
- **Verification:** `python -m unittest backend.test.test_fleet_bridge backend.test.test_esp32_controls -v` → 44 OK
- **Committed in:** `cbfb48e`

**2. [Rule 3 - Blocking] Combined Task 1+2 GREEN in one feat commit**
- **Found during:** Task 2
- **Issue:** Shared RED suite already asserted Task 2 entry-point/setup/session-manager behaviors, so a separate empty Task 2 GREEN commit was not possible without artificial splits.
- **Fix:** Delivered Task 2 (`FleetSessionManager`, `FleetBridgeNode`, `setup.py` entry) in the same GREEN commit as Task 1; documented here.
- **Files modified:** `backend/rehab_robotics_bridge/fleet_bridge_node.py`, `backend/setup.py`
- **Verification:** same 44 OK suite
- **Committed in:** `cbfb48e`

---

**Total deviations:** 2 auto-fixed (Rule 2 ×1, Rule 3 ×1)
**Impact on plan:** Correctness-only; no scope creep into aliases (21-03) or drop isolation (21-04).

## Issues Encountered

Workspace path with `#`/apostrophe required running shell commands from `C:\Users\justi\AppData\Local\Temp` via Python `pathlib` chdir (same constraint as 21-01).

## User Setup Required

None - no external service configuration required. Stay offline / ubcvisitor for agent work; STEP_ESP32 acquisition remains operator-run.

## Next Phase Readiness

Plan 21-03 can bind legacy Master/Slave aliases and pair health onto verified identities. Plan 21-04 can expose drop/reconnect counters and harden sibling-session isolation. Canonical topics and registry schema are ready for consumers.

## TDD Gate Compliance

1. RED commit present: `5c580c8` test(21-02)
2. GREEN commit present: `cbfb48e` feat(21-02)
3. Combined Task 1+2 GREEN noted under deviations

## Self-Check: PASSED

- FOUND: `backend/rehab_robotics_bridge/fleet_bridge_node.py`
- FOUND: `backend/test/test_fleet_bridge.py`
- FOUND: `5c580c8`
- FOUND: `cbfb48e`
- VERIFY: `python -m unittest backend.test.test_fleet_bridge backend.test.test_esp32_controls -v` → Ran 44 tests, OK
