---
phase: 21-n-route-relay-and-canonical-ros-fleet
plan: "04"
subsystem: ros-fleet
tags: [fleet, isolation, drop_count, reconnect, diagnostics, FLEET-03]

requires:
  - phase: 21-n-route-relay-and-canonical-ros-fleet
    provides: N-route relay + wireless discovery (21-01)
  - phase: 21-n-route-relay-and-canonical-ros-fleet
    provides: fleet_bridge_node canonical mac_ topics + registry (21-02)
  - phase: 21-n-route-relay-and-canonical-ros-fleet
    provides: Master/Slave aliases + single fleet launch (21-03)
provides:
  - Per-route UdpRouter drop_count on drop-oldest overflow
  - Registry/health drop and reconnect diagnostics (reconnecting/offline retention)
  - run_isolated_session_tasks supervisor (sibling failures never cancel peers)
  - Deterministic isolation suite without STEP_ESP32 Wi-Fi
affects:
  - Phase 21 verification
  - Phase 24 mapping UI (consumes drops/reconnects on registry rows)

tech-stack:
  added: []
  patterns:
    - "UdpRouter.drop_counts[host] increments only on drop-oldest for that IP"
    - "FleetRegistryStore mark_reconnecting/record_udp_drops/note_reconnect"
    - "run_isolated_session_tasks + gather(return_exceptions=True); CancelledError re-raised"

key-files:
  created: []
  modified:
    - scripts/stepesp_tcp_udp_relay.py
    - backend/rehab_robotics_bridge/fleet_bridge_node.py
    - backend/rehab_robotics_bridge/esp32_bridge_node.py
    - backend/test/test_stepesp_udp_relay.py
    - backend/test/test_fleet_bridge.py
    - backend/test/test_esp32_controls.py
    - docs/stepesp-wireless-setup.md

key-decisions:
  - "Relay asserts drop_count directly; fleet registry carries session reconnect + applied drop counters"
  - "oe_esp32.health.v1 gains additive drop_count + nested drops without schema bump"
  - "note_reconnect only after reconnect_generation>=1 so initial configure→bind is not a reconnect"
  - "Isolated supervisor is the acquisition/recording cancel boundary (no fatal sibling gather)"

patterns-established:
  - "Pattern: per-host drop_counts move with remap_host alongside the queue"
  - "Pattern: on_session_reconnecting removes only that device from _online_devices"
  - "Pattern: Identify remains MAC-targeted on healthy sessions during partial outage"

requirements-completed: [FLEET-03, FLEET-01, ID-02]

duration: 35min
completed: 2026-07-31
---

# Phase 21 Plan 04: Isolation Diagnostics + Deterministic Tests Summary

**Per-route UDP `drop_count`, registry/health reconnect diagnostics, and an isolated session supervisor proven by offline multi-route tests (no STEP_ESP32 Wi-Fi).**

## Performance

- **Duration:** 35 min
- **Started:** 2026-07-31T18:48:00Z
- **Completed:** 2026-07-31T19:23:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- `UdpRouter` increments per-host `drop_count` on drop-oldest overflow and preserves counts across DHCP `remap_host`.
- Registry rows expose `drops.udp_drop_count` / `reconnects.*` with `reconnecting`/`offline` retention; health adds additive `drop_count`/`drops`.
- `run_isolated_session_tasks` prevents sibling cancel; fleet supervisor marks only the failed route reconnecting.
- Deterministic suite covers isolation, DHCP topic stability, Identify-during-partial-outage, and offline retention.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED:** `bee9320` — test(21-04): add failing drop_count and reconnect diagnostics contracts
2. **Task 1 GREEN:** `8eaf8db` — feat(21-04): expose per-route drop_count and reconnect diagnostics
3. **Task 2 RED:** `22aca15` — test(21-04): add failing multi-route isolation suite
4. **Task 2 GREEN:** `34e606f` — feat(21-04): isolate session failures and document fleet diagnostics

**Plan metadata:** (see final docs commit)

## Files Created/Modified

- `scripts/stepesp_tcp_udp_relay.py` — per-host `drop_counts` + `drop_count()` API
- `backend/rehab_robotics_bridge/fleet_bridge_node.py` — reconnect/drop APIs + isolated supervisor
- `backend/rehab_robotics_bridge/esp32_bridge_node.py` — additive health drop fields
- `backend/test/test_stepesp_udp_relay.py` — drop_count + sibling overflow isolation
- `backend/test/test_fleet_bridge.py` — diagnostics + failure isolation contracts
- `backend/test/test_esp32_controls.py` — Identify while sibling reconnecting
- `docs/stepesp-wireless-setup.md` — diagnostic field names; live Soft-AP still operator-run

## Decisions Made

- Relay counters are authoritative for UDP drops; fleet applies them via `record_udp_drops` / `apply_udp_drop_count`.
- Health keeps `oe_esp32.health.v1` with additive fields (`drop_count`, nested `drops`) rather than a new schema id.
- Reconnect count increments only after a prior connected generation (avoids counting first bind from configured offline).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Initial configure→bind must not count as reconnect**
- **Found during:** Task 1 GREEN
- **Issue:** `on_session_bound` auto-`note_reconnect` on any offline prior state would inflate `reconnect_count` on first bind (sessions start `mark_offline` at configure).
- **Fix:** Only call `note_reconnect` when `reconnect_generation >= 1` and route is offline/reconnecting/stale.
- **Files modified:** `backend/rehab_robotics_bridge/fleet_bridge_node.py`
- **Committed in:** `8eaf8db`

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** Correctness fix only; no scope creep.

## Issues Encountered

None beyond the reconnect-count false positive above.

## User Setup Required

None - no external service configuration required. Live STEP_ESP32 Soft-AP validation remains operator-run per docs.

## Next Phase Readiness

- Phase 21 plan wave complete for FLEET-03 observability/isolation; ready for phase-level verification.
- Live TCP session bodies inside `fleet_bridge_node._run_sessions` remain placeholders — streaming still uses Esp32BridgeNode/relay paths; isolation contract is enforced for future binding.

## Test Results

```text
python -m unittest backend.test.test_stepesp_udp_relay backend.test.test_fleet_bridge backend.test.test_esp32_controls -v
Ran 94 tests in 0.364s
OK
```

## Self-Check: PASSED

- Key artifacts present (relay, fleet/esp32 bridge, tests, docs, SUMMARY)
- Task commits present: bee9320, 8eaf8db, 22aca15, 34e606f

---
*Phase: 21-n-route-relay-and-canonical-ros-fleet*
*Completed: 2026-07-31*
