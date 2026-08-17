---
phase: 26-signal-contract-and-provenance
plan: 04
subsystem: frontend-data-ingress
tags: [typescript, rosbridge, provenance, validation, zustand]

requires:
  - phase: 26-02
    provides: Strict immutable TypeScript canonical signal parser
  - phase: 26-03
    provides: Verified per-MAC canonical backend envelopes and applied provenance
provides:
  - Strict dynamic per-MAC rosbridge subscriptions with isolated accept/reject callbacks
  - Immutable bounded applied mapping snapshot separate from draft editor assignments
  - Bounded deduplicable rejection metadata without raw payload leakage
affects: [26-05-signal-bus, 26-06-signal-panel, phase-29-viewer]

tech-stack:
  added: []
  patterns: [topic-derived identity validation, atomic boundary parsing, immutable applied snapshot, isolated accept-reject streams]

key-files:
  created: []
  modified:
    - rehab-robotics-studio/src/state/mappingStore.ts
    - rehab-robotics-studio/src/state/mappingStore.test.ts
    - rehab-robotics-studio/src/data/RosbridgeDataSource.ts
    - rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts

key-decisions:
  - "Mapping-current payloads are parsed atomically once, with draft and applied assignments validated independently and the applied snapshot deeply frozen."
  - "Canonical rosbridge topics are derived only from normalized full MAC registry identities; registry-provided topic aliases are ignored."
  - "Every rejection emits bounded count metadata, while should_announce suppresses repeated identical reason announcements per source."

patterns-established:
  - "Sample-owned provenance: accepted samples retain their own applied mapping and never consult mutable mapping store state."
  - "Transport isolation: canonical accepted and rejected events use distinct subscription sets and cannot cross-dispatch."

requirements-completed: [SIG-01, SIG-04, SIG-05]

duration: 9min
completed: 2026-08-16
---

# Phase 26 Plan 04: Canonical Rosbridge Ingress and Applied Mapping Summary

**Strict full-MAC rosbridge ingress now delivers immutable canonical samples while draft mapping and bounded applied provenance remain separate browser state.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-08-17T01:59:00Z
- **Completed:** 2026-08-17T02:08:03Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added an atomic mapping-current parser that independently validates bounded draft and applied assignments, safe revisions, and model hashes.
- Preserved editor-row draft behavior while exposing a separately named, deeply frozen `appliedAssignments` snapshot, including revision-zero unassigned state.
- Added deduplicated dynamic `/esp/raw/mac_<12hex>` subscriptions derived solely from validated fleet full MACs, with safe unsubscribe/reconnect behavior.
- Routed nested `sample_contract` payloads through `parseCanonicalSignalSample` and separated accepted samples from bounded, allowlisted rejection metadata.

## Task Commits

Each task was committed atomically through TDD RED/GREEN gates:

1. **Task 1 RED: Define separate applied mapping snapshot** - `d2c73f7` (test)
2. **Task 1 GREEN: Preserve applied mapping separately** - `7a2b1dc` (feat)
3. **Task 2 RED: Define strict canonical rosbridge ingress** - `ee80c6a` (test)
4. **Task 2 GREEN: Enforce canonical rosbridge ingress** - `bf2e693` (feat)

## Files Created/Modified

- `rehab-robotics-studio/src/state/mappingStore.ts` - Shared atomic mapping parser and immutable applied snapshot state.
- `rehab-robotics-studio/src/state/mappingStore.test.ts` - Divergent draft/applied, revision-zero, bounds, immutability, and atomic no-op coverage.
- `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` - Dynamic canonical subscriptions plus strict accept/reject dispatch.
- `rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts` - Topic spoofing, deduplication, provenance, malformed input, and unsubscribe coverage.

## Decisions Made

- Applied mapping state is copied and frozen at the parsing boundary; editor rows continue to represent draft assignments only.
- Dynamic topic names are always recomputed from validated full MAC identity and never trusted from fleet payload aliases.
- Rejection events expose only full MAC when safely derivable, an allowlisted reason, bounded receipt timestamp/count, and an announcement-deduplication flag.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Verification

- `npm exec -- tsx --test src/data/RosbridgeDataSource.test.ts src/data/signalContract.test.ts src/state/mappingStore.test.ts` - 106 tests passed.
- `npm run typecheck` - passed.

## Next Phase Readiness

- Plan 26-05 can expose these isolated canonical subscriptions through the application data facade and publish immutable latest-by-MAC state.
- No blockers or new threat flags were found.

## Self-Check: PASSED

- All four modified implementation/test files exist.
- All four TDD task commits are present in repository history.

---
*Phase: 26-signal-contract-and-provenance*
*Completed: 2026-08-16*
