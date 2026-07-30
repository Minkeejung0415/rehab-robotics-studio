---
phase: 20-full-identity-and-confirmed-identify
plan: "02"
subsystem: routing
tags: [python, powershell, esp32, identity, tcp, udp, tdd]

requires:
  - phase: 20-01
    provides: Versioned full-MAC firmware identity inventory and correlated Identify terminal replies
provides:
  - Strict bounded id-v1 relay handshake that binds only a verified session-self record
  - Stable full-MAC session registry with endpoint rebinding and changed-identity quarantine
  - Identity-probed legacy Master/Slave launcher with exact expected-ID selection and ambiguity failure
  - Byte-transparent Identify forwarding and independent bounded UDP route workers
affects: [20-03-ros-identify, 20-04-hardware-led-verification, phase-21-fleet-routing]

tech-stack:
  added: []
  patterns:
    - Complete counted self/peer/end inventories gate verified route ownership
    - Stable canonical identity remains separate from role alias, endpoint, and transport MAC metadata
    - Ping discovers candidates while verified self identity alone selects a route

key-files:
  created:
    - scripts/stepesp_tcp_udp_relay.py
    - backend/test/test_stepesp_udp_relay.py
  modified:
    - scripts/start_stepesp_wireless.ps1

key-decisions:
  - "Only IDENTITY_OK protocol=id-v1 record=self can bind a relay route; counted peer rows remain inventory and never satisfy expected identity."
  - "Wireless auto-discovery accepts exactly one verified Slave self identity unless an exact canonical expected ID is supplied."
  - "Master/Slave node aliases, mutable endpoints, and verified canonical identities are passed as distinct launch values."

patterns-established:
  - "Identity gate: issue IDENTITY?, bound the response, require self then advertised peers then matching end."
  - "Reconnect semantics: same full MAC updates endpoint metadata; a different full MAC displaces but never mutates the prior identity."

requirements-completed: [ID-01, ID-03]

duration: 11min
completed: 2026-07-30
---

# Phase 20 Plan 02: Identity-Confirmed Relay and Launcher Summary

**Strict full-MAC relay sessions and wireless route selection using complete firmware identity inventories instead of DHCP order**

## Performance

- **Duration:** 11 min
- **Started:** 2026-07-30T20:05:47Z
- **Completed:** 2026-07-30T20:16:56Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added bounded token-safe parsing for canonical full identities, display/base/STA/AP/ESP-NOW metadata, roles, capabilities, verification state, and counted peer inventories.
- Relay sessions now issue `IDENTITY?`, bind only a complete verified self record, retain peers as inventory, preserve same-device endpoint rebinding, and quarantine changed identities.
- Identify terminal lines remain byte-identical through the relay, while per-route bounded queues keep a stalled route from blocking a live route.
- The wireless launcher probes the fixed Master and every discovered Slave candidate, filters by exact verified self identity, and fails closed with all discovered IDs when selection is ambiguous.
- Existing two-route ports, role aliases, rosbridge, OpenSim, processing observer, recording controls, and GUI startup remain in place.

## Task Commits

Each TDD task has a RED test commit followed by a GREEN implementation commit:

1. **Task 1: Make relay sessions identity-confirmed and control-transparent**
   - `431bb60` — RED: failing relay identity, reconnect, transparency, and isolation contracts
   - `b89dadd` — GREEN: strict identity inventory parser, session registry, relay gate, and transparent forwarding
2. **Task 2: Select wireless routes by verified identity instead of DHCP order**
   - `6ba45a0` — RED: failing launcher identity-probe and metadata-separation contracts
   - `ba2c575` — GREEN: complete candidate probes, exact expected-ID selection, and verified launch arguments

## Files Created/Modified

- `scripts/stepesp_tcp_udp_relay.py` — Strict id-v1 parsing, verified session metadata, endpoint rebinding registry, identity-gated relay connections, control transparency, and existing bounded UDP routing.
- `scripts/start_stepesp_wireless.ps1` — Canonical expected-ID parameters, bounded TCP identity probes, all-candidate selection, ambiguity reporting, and separate relay/ROS identity arguments.
- `backend/test/test_stepesp_udp_relay.py` — Hardware-free identity, inventory, reconnect, collision, legacy, Identify, isolation, and launcher preservation contracts.

## Verification

- `python -m unittest backend.test.test_stepesp_udp_relay -v` — PASS, 18 tests.
- `python -m py_compile scripts/stepesp_tcp_udp_relay.py backend/test/test_stepesp_udp_relay.py` — PASS.
- `[scriptblock]::Create((Get-Content -Raw scripts/start_stepesp_wireless.ps1))` — PASS.
- Launcher contract checks — PASS: no `$responsiveStations[0]`; verified Master/Slave IDs are separate from role aliases and endpoints.
- TDD history — PASS: `431bb60 -> b89dadd` and `6ba45a0 -> ba2c575`.

## Decisions Made

- Kept Phase 20 at two compatibility routes while introducing a stable full-MAC registry seam for Phase 21 rather than expanding this plan into N-route lifecycle ownership.
- Allowed an old relay endpoint to continue only as explicitly `unsupported`/unverified when no expected identity is configured; an expected identity always fails closed without id-v1.
- Used the firmware session-self record for route binding and retained unverified legacy peer rows only as inventory metadata.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Repaired malformed SDK tracking updates**
- **Found during:** Plan close-out
- **Issue:** The state SDK appended the metric below the prior-milestone section, left the frontmatter percentage and completed-plan count stale, and removed ROADMAP table spacing/placeholders.
- **Fix:** Moved the metric into the current milestone table, synchronized the 33% / 2-plan counters, and restored the ROADMAP row format.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** State reports plan 3 of 6 with 2 completed plans and 33%; ROADMAP reports 2/6 In Progress.
- **Committed in:** Plan metadata commit.

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** Tracking-only correction; relay, launcher, and test scope were unchanged.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Optional expected identities may be supplied as exact `esp32:aabbccddeeff` launcher parameters.

## Known Stubs

None.

## Next Phase Readiness

- Ready for `20-03-PLAN.md` to consume verified identity separately from the legacy Master/Slave aliases and expose correlated Identify through ROS.
- No physical hardware behavior is claimed by this plan; LED/electrical and route/MAC relationship acceptance remains assigned to the dedicated Phase 20 hardware verification plan.

## Self-Check: PASSED

- All three plan-owned implementation/test files and this summary exist.
- All four RED/GREEN task commits are present in Git history.
- The final 18-test suite, Python compile checks, PowerShell parse, and launcher preservation contracts passed.

---
*Phase: 20-full-identity-and-confirmed-identify*
*Completed: 2026-07-30*
