---
phase: 21-n-route-relay-and-canonical-ros-fleet
plan: "01"
subsystem: infra
tags: [stepesp, relay, udp, identity, powershell, multi-slave]

requires:
  - phase: 20-full-identity-and-confirmed-identify
    provides: verified id-v1 self bind, SessionIdentityRegistry, dual-route UdpRouter
provides:
  - Repeatable --slave-route CLI for Master + N≤6 identity-bound slaves
  - UdpRouter host remap preserving canonical device_id across IP refresh
  - Wireless launcher route-all-verified discovery with contiguous listen ports
affects:
  - 21-02 canonical ROS fleet publishers
  - 21-03 fleet process / bridge consolidation
  - 21-04 drop_count and reconnect diagnostics

tech-stack:
  added: []
  patterns:
    - "Repeatable --slave-route HOST:LISTEN_PORT:EXPECTED_DEVICE_ID (cap 6)"
    - "remap_relay_endpoint + UdpRouter.remap_host for DHCP refresh"
    - "Launcher route-all-verified with optional ExpectedSlaveDeviceIds filter"

key-files:
  created: []
  modified:
    - scripts/stepesp_tcp_udp_relay.py
    - scripts/start_stepesp_wireless.ps1
    - backend/test/test_stepesp_udp_relay.py
    - docs/stepesp-wireless-setup.md

key-decisions:
  - "Chose repeatable --slave-route over parallel host/port/id lists for unambiguous N-route CLI"
  - "Left dual ROS bridge spawn on first slave transitional; relay already receives all N routes"
  - "Contiguous listen ports = SlaveRelayPort + index (default 5003..)"

patterns-established:
  - "Pattern: fail closed on duplicate MAC, >6 slaves, or slave identity equal to master"
  - "Pattern: IP/endpoint refresh remaps UDP queues without changing device_id registry key"

requirements-completed: [ID-02, FLEET-03]

duration: 25min
completed: 2026-07-31
---

# Phase 21 Plan 01: Multi-Slave Relay + Launcher Discovery Summary

**Windows relay and wireless launcher now route Master plus every verified slave (≤6) on identity-stable TCP/UDP paths with DHCP remap and fail-closed duplicates.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-31T18:14:34Z
- **Completed:** 2026-07-31T18:40:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Repeatable `--slave-route` CLI builds Master + N≤6 identity-bound `StepEspRelay` sessions with isolated UDP demux (maxsize=256 drop-oldest).
- `remap_relay_endpoint` refreshes ESP IP/host keys while keeping canonical `esp32:<12hex>` registry keys; displaced MACs go offline.
- Wireless launcher routes all verified slaves (optional `-ExpectedSlaveDeviceIds` / singular `-ExpectedSlaveDeviceId` filter), allocates contiguous listen ports, and passes every route to the relay.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED:** `bc3de78` — test(21-01): add failing N-route relay contracts
2. **Task 1 GREEN:** `3a29794` — feat(21-01): implement N-route identity-bound relay
3. **Task 2 RED:** `ad25a71` — test(21-01): add failing N-slave launcher contracts
4. **Task 2 GREEN:** `f53ce42` — feat(21-01): route all verified slaves in wireless launcher

**Plan metadata:** `f732024` (docs: complete plan)

## Files Created/Modified

- `scripts/stepesp_tcp_udp_relay.py` — N-route CLI, `parse_slave_routes`, `UdpRouter.remap_host`, `remap_relay_endpoint`
- `scripts/start_stepesp_wireless.ps1` — route-all-verified discovery, `--slave-route` args, fail-closed overflow/duplicates
- `backend/test/test_stepesp_udp_relay.py` — multi-route CLI/demux/remap + launcher source contracts
- `docs/stepesp-wireless-setup.md` — N-slave discovery and filter documentation

## Decisions Made

- Prefer `--slave-route HOST:LISTEN_PORT:EXPECTED_DEVICE_ID` (research-aligned) while keeping singular `--slave-host` compatibility.
- Leave master/slave ROS bridge spawn on the first verified slave until plans 02–03; relay already owns all N routes.
- Contiguous listen-port allocation from `SlaveRelayPort` (Claude's discretion, locked CONTEXT).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Launcher contract strings adapted to list-style ArgumentList**
- **Found during:** Task 2
- **Issue:** Relay spawn moved from a single concatenated arg string to a PowerShell argument list, so older `--esp-host $MasterHost` substrings no longer appear.
- **Fix:** Updated launcher source contracts to assert list-form tokens (`'--esp-host', $MasterHost`) while preserving identity-binding intent.
- **Files modified:** `backend/test/test_stepesp_udp_relay.py`
- **Verification:** `python -m unittest backend.test.test_stepesp_udp_relay -v` → 28 OK
- **Committed in:** `f53ce42`

---

**Total deviations:** 1 auto-fixed (Rule 2)
**Impact on plan:** Contract assertion shape only; no behavior scope creep.

## Issues Encountered

None blocking. Workspace path with `#`/apostrophe/comma required short-path (`#REHAB~1`) for shell operations.

## User Setup Required

None - no external service configuration required. Hardware STEP_ESP32 acquisition remains operator-run (stay on ubcvisitor for agent work).

## Next Phase Readiness

Plan 21-02 can consume identity-stable multi-route relay sessions for canonical ROS publishers. Drop_count exposure remains plan 21-04. Fleet bridge consolidation remains plans 21-02/03.

## TDD Gate Compliance

- RED commits: `bc3de78`, `ad25a71`
- GREEN commits: `3a29794`, `f53ce42`

## Self-Check: PASSED

- FOUND: `.planning/phases/21-n-route-relay-and-canonical-ros-fleet/21-01-SUMMARY.md`
- FOUND commits via `git log`: `bc3de78`, `3a29794`, `ad25a71`, `f53ce42`
- FOUND: modified key files exist on disk

---
*Phase: 21-n-route-relay-and-canonical-ros-fleet*
*Completed: 2026-07-31*
