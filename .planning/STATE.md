---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: Multi-Sensor Bone Mapping
status: verifying
stopped_at: Completed 21-04-PLAN.md
last_updated: "2026-07-31T18:58:23.679Z"
last_activity: 2026-07-31
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 10
  completed_plans: 10
  percent: 33
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-07-30)

**Core value:** Reliable live ESP32 motion data must flow through a reproducible ROS 2 pipeline into usable filtered, biomechanical, and recorded outputs.
**Current focus:** Phase 21 — N-Route Relay and Canonical ROS Fleet

## Current Position

Phase: 21 (N-Route Relay and Canonical ROS Fleet) — EXECUTING
Plan: 4 of 4
Status: Phase complete — ready for verification
Last activity: 2026-07-31

Progress: [██████████] 100%

## Performance Metrics

**Current milestone:**

  - Plans completed: 9
- Phases completed: 1/6

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 20 P01 | 21 min | 2 tasks | 3 files |
| Phase 20 P02 | 15 min | 2 tasks | 3 files |
| Phase 20 P03 | 35 min | 2 tasks | 4 files |
| Phase 20 P05 | 8 min | 2 tasks | 4 files |
| Phase 20 P06 | 2 min | 1 tasks | 1 files |
| Phase 21 P01 | 25 min | 2 tasks | 4 files |
| Phase 21 P02 | 35 min | 2 tasks | 4 files |
| Phase 21 P03 | 40 min | 2 tasks | 8 files |

**Prior milestone reference:**

- v1.5 Phases 16-19 complete
- Existing phase artifacts remain preserved

| Phase 21 P04 | 35min | 2 tasks | 7 files |

## Accumulated Context

### Decisions

Decisions are logged in `PROJECT.md`. Current milestone decisions:

- Stable full 48-bit MAC identity is distinct from role, IP, route, and transport metadata.
- The backend is authoritative for exact-model-hash mapping revisions; browser state is draft-only.
- Mapping Apply is whole-candidate, optimistic-revision, atomic, and interlocked with capture/recording/finalization.
- Official OpenSim IK consumes only a complete, fresh, synchronized mapped input set.
- Legacy two-sensor aliases and rollback mode remain until hardware acceptance supports promotion.
- [Phase 20]: Identity uses the full six-byte eFuse/base MAC while interface MACs, route, role, slot, and deprecated slave_id remain metadata. — Prevents low-32 collisions and mutable route metadata from becoming identity.
- [Phase 20]: Identify confirmation is emitted only after target loop code starts the bounded LED action; ESP-NOW send completion is never confirmation. — Preserves application-level correlation and avoids false success.
- [Phase 20]: Relay routes bind only from a complete verified id-v1 self record; peer rows remain inventory. — Prevents peer inventory, role aliases, mutable endpoints, and low-32 collisions from becoming session identity.
- [Phase 20]: Wireless discovery accepts one verified Slave self identity or an exact expected canonical ID. — Ensures ping response order cannot select a physical device and ambiguous discovery fails closed.
- [Phase 20]: Only a complete verified record=self row binds the bridge; peer rows remain bounded inventory and cannot satisfy expected_device_id. — Prevents peer inventory from masquerading as the serial device identity.
- [Phase 20]: Existing Master/Slave publishers remain the only Phase 20 data publishers; device_topic_token is a pure Phase 21 foundation helper. — Preserves fixed role-topic compatibility until canonical fleet routing is introduced.
- [Phase 20]: sent_unconfirmed remains observable and non-success; only a correlated confirmed reply updates last-confirmed state. — Prevents transport acceptance from being reported as physical Identify confirmation.
- [Phase 20]: Cross-layer identity regression shares one named adversarial matrix across firmware, relay, and bridge.
- [Phase 20]: Phase 20 permits only the pure mac_<12hex> token helper; per-MAC publisher lifecycle remains Phase 21.
- [Phase 20]: Physical Identify evidence remains pending HUMAN-UAT, while Phase 25 owns capacity and promotion.
- [Phase 21]: Chose repeatable `--slave-route HOST:LISTEN_PORT:EXPECTED_DEVICE_ID` over parallel host/port/id lists for unambiguous N-route CLI.
- [Phase 21]: Left dual ROS bridge spawn on first slave transitional; relay already receives all N routes (fleet consolidation in 21-02/03).
- [Phase 21]: Contiguous listen ports = SlaveRelayPort + index (default 5003..).
- [Phase 21]: Primary entry is fleet_bridge_node; esp32_bridge_node remains thin single-session wrapper.
- [Phase 21]: Registry schema oe_esp32.fleet_registry.v1 with layered discovery/command/route/freshness/sync/rate.
- [Phase 21]: Alias republish and pair health deferred to plan 21-03.
- [Phase 21]: Fleet String aliases mirror /esp/raw|status only; typed /esp32/{master,slave}/imu stay OpenSim consumers (no /esp32/mac_ invent).
- [Phase 21]: Empty alias params resolve from first verified master/slave role — never TCP connect order.
- [Phase 21]: Wireless launcher starts one fleet_bridge_node with routes_json + alias_* params.
- [Phase 21]: Relay drop_count is per-host; fleet registry/health expose drops+reconnects without counting initial configure bind as reconnect.
- [Phase 21]: run_isolated_session_tasks is the cancel boundary so sibling session failures never stop acquisition/health/Identify/recording peers.

### Pending Todos

None recorded.

### Blockers/Concerns

- Phase 20 must verify board-revision LED pin/active level and base/AP/STA/ESP-NOW MAC relationships.
- Phase 21 must select the multi-peer high-rate transport from measured throughput and failure-isolation evidence.
- Phase 22 must prove pinned OpenSim 4.5.2 runtime Frame behavior or require model-authored Frames.
- Phase 25 must establish the supported fleet size/rate and default-mode decision from physical hardware evidence.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Block Deployment | DEPLOY-01 through DEPLOY-04 | Parked | v1.2 |
| Acquisition Integrity | Remaining unfinished scope | Preserved | v1.3 |
| Clinical validation | External-reference accuracy claims | Out of scope | v1.6 |
| Embedded Studio 3D | In-app solved-model renderer | Out of scope | v1.6 |
| Partial-sensor IK | Degraded/profile-defined solving | Future | v1.6 |

## Session Continuity

Last session: 2026-07-31T18:58:23.666Z
Stopped at: Completed 21-04-PLAN.md
Resume file: None
