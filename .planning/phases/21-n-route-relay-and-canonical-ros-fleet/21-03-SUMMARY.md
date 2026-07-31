---
phase: 21-n-route-relay-and-canonical-ros-fleet
plan: "03"
subsystem: ros-fleet
tags: [fleet, aliases, pair-health, launcher, routes_json, COMP-01]

requires:
  - phase: 21-n-route-relay-and-canonical-ros-fleet
    provides: fleet_bridge_node canonical mac_ topics + registry (21-02)
  - phase: 21-n-route-relay-and-canonical-ros-fleet
    provides: N-route relay + wireless discovery (21-01)
provides:
  - Identity-bound /esp/raw|status/{master,slave} aliases mirroring canonical payloads
  - /esp/status/pair when both aliases bound (oe_esp32.pair_health.v1)
  - Single fleet_bridge_node wireless launch with routes_json + alias_* params
affects:
  - 21-04 drop_count / reconnect isolation
  - Phase 24 mapping UI (consumes registry + aliases)

tech-stack:
  added: []
  patterns:
    - "Alias republish from one accepted canonical String stream (never second parser)"
    - "Empty alias params resolve to first verified master/slave role — not TCP order"
    - "Wireless default = one fleet_bridge_node; esp32_bridge_node remains USB/legacy"

key-files:
  created: []
  modified:
    - backend/rehab_robotics_bridge/fleet_bridge_node.py
    - backend/rehab_robotics_bridge/esp32_bridge_node.py
    - scripts/start_stepesp_wireless.ps1
    - backend/launch/rehab_robotics.launch.py
    - backend/test/test_fleet_bridge.py
    - backend/test/test_stepesp_udp_relay.py
    - docs/stepesp-wireless-setup.md
    - docs/stepesp-identity-identify.md

key-decisions:
  - "Fleet String aliases mirror /esp/raw|status only; typed /esp32/{master,slave}/imu stay OpenSim consumers (no /esp32/mac_ invent)"
  - "Launcher builds routes_json for master + all selected slaves with explicit alias device ids"
  - "Launch file adds use_fleet_bridge opt-in; default remains dual bridges for non-wireless paths"

patterns-established:
  - "Pattern: publish_session_raw/health mirrors aliases only while the bound device is online"
  - "Pattern: pair health gated on aliases_bound(); registry remains authoritative for N>2"

requirements-completed: [FLEET-02, ID-02]

duration: 40min
completed: 2026-07-31
---

# Phase 21 Plan 03: Master/Slave Aliases + Single Fleet Launch Summary

**Explicit identity-bound Master/Slave String aliases and pair health on fleet_bridge_node, with the wireless launcher starting one fleet process (routes_json + alias_* params) instead of dual role bridges.**

## Performance

- **Duration:** 40 min
- **Started:** 2026-07-31T18:37:22Z
- **Completed:** 2026-07-31T19:15:00Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- `FleetSessionManager` mirrors identical canonical payloads onto `/esp/raw|status/{master,slave}` for configured or role-resolved identities.
- `/esp/status/pair` (`oe_esp32.pair_health.v1`) publishes only when both aliases are bound; offline alias targets stop mirroring without tearing down siblings.
- Wireless launcher starts one `fleet_bridge_node` with full N-route `routes_json` and explicit `alias_master_device_id` / `alias_slave_device_id`.
- Docs and launch file document fleet aliases, registry, and optional `use_fleet_bridge` launch mode.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED:** `ff28a20` — test(21-03): add failing Master/Slave alias and pair health contracts
2. **Task 1 GREEN:** `5e539c6` — feat(21-03): identity-bound Master/Slave aliases and pair health
3. **Task 2 RED:** `ca5c1d4` — test(21-03): add failing single fleet launcher contracts
4. **Task 2 GREEN:** `c9392ef` — feat(21-03): launch one fleet_bridge_node with alias and route params

**Plan metadata:** (pending final docs commit)

## Files Created/Modified

- `backend/rehab_robotics_bridge/fleet_bridge_node.py` — alias publishers, role-default binding, pair health, publish helpers
- `backend/rehab_robotics_bridge/esp32_bridge_node.py` — note that USB/legacy owns pair when not in fleet mode
- `scripts/start_stepesp_wireless.ps1` — single fleet spawn with routes_json + aliases
- `backend/launch/rehab_robotics.launch.py` — `use_fleet_bridge` / alias / routes_json args
- `backend/test/test_fleet_bridge.py` — alias parity, role binding, offline isolation, pair health
- `backend/test/test_stepesp_udp_relay.py` — single-fleet launcher source contracts
- `docs/stepesp-wireless-setup.md` — fleet launch + registry verify
- `docs/stepesp-identity-identify.md` — Phase 21 alias/registry inspection

## Decisions Made

- Fleet mirrors JSON raw/status aliases only; typed OpenSim IMU topics remain `/esp32/{master,slave}/imu` consumers (no `/esp32/mac_` publishers in fleet).
- Empty alias params resolve from first verified master-role / slave-role session — never TCP connect order.
- Launch file keeps dual `esp32_bridge_node` as default for non-wireless; wireless script uses fleet exclusively.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Launcher contract allowed legacy pkill tokens**
- **Found during:** Task 2 GREEN
- **Issue:** Asserting `esp32_bridge_node` absent would fail on intentional `pkill -f '[e]sp32_bridge_node'` cleanup of leftover USB bridges.
- **Fix:** Contracts assert absence of `ros2 run rehab_robotics_bridge esp32_bridge_node` and exact one `ros2 run ... fleet_bridge_node`.
- **Files modified:** `backend/test/test_stepesp_udp_relay.py`
- **Verification:** `python -m unittest backend.test.test_stepesp_udp_relay -v` → OK
- **Committed in:** `c9392ef`

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** Necessary for correct launcher source contracts; no scope creep.

## Issues Encountered

None blocking. Live TCP streaming inside `fleet_bridge_node` remains the 21-02 placeholder (supervisor sleep); 21-04 hardens per-session isolation/diagnostics. Typed IMU alias mirroring is intentionally out of this plan's String alias surface.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for plan 21-04 (drop_count, reconnect diagnostics, failure isolation). Alias + registry contracts are in place for operator/GUI consumption; do not start Phase 24 UI work here.

## Self-Check: PASSED

- FOUND: `.planning/phases/21-n-route-relay-and-canonical-ros-fleet/21-03-SUMMARY.md`
- FOUND: `ff28a20`, `5e539c6`, `ca5c1d4`, `c9392ef`
- Verification: `python -m unittest backend.test.test_fleet_bridge backend.test.test_stepesp_udp_relay backend.test.test_esp32_controls -v` → 81 OK (+7 opensim launch OK)

---
*Phase: 21-n-route-relay-and-canonical-ros-fleet*
*Completed: 2026-07-31*
