---
phase: 26-signal-contract-and-provenance
plan: 05
subsystem: frontend-data
tags: [react, typescript, useSyncExternalStore, canonical-signals, throttling]

requires:
  - phase: 26-04
    provides: Strict canonical rosbridge accepted/rejected callbacks with applied provenance
provides:
  - Narrow application-level canonical accepted and rejected subscription contracts
  - Immutable current-session latest canonical samples keyed by exact full MAC
  - Bounded rejection state published at the existing React render cadence
affects: [26-06, signal-viewer, provenance-ui, frontend-data]

tech-stack:
  added: []
  patterns: [separate high-rate ingestion from render publication, copy-on-publish immutable maps]

key-files:
  created:
    - rehab-robotics-studio/src/data/signalBus.test.ts
  modified:
    - rehab-robotics-studio/src/data/DataSource.ts
    - rehab-robotics-studio/src/data/appDataSource.ts
    - rehab-robotics-studio/src/data/signalBus.ts

key-decisions:
  - "Canonical accepted and rejected callbacks remain separate from legacy Frame subscriptions and are silent while mock fallback is active."
  - "SignalBus retains parser-owned immutable samples by exact full MAC and copies only snapshot maps at the bounded publication boundary."
  - "Rejection totals and per-source metadata are bounded; repeated source/reason signatures suppress announcements without suppressing counts."

patterns-established:
  - "Canonical facade: appDataSource forwards live rosbridge canonical callbacks without adding mock devices or touching acquisition lifecycle."
  - "Canonical snapshot: high-rate callbacks update internal maps while React receives frozen copied records at the existing ~30 fps cadence."

requirements-completed: [SIG-01, SIG-02, SIG-03, SIG-04, SIG-05]

duration: 5min
completed: 2026-08-16
---

# Phase 26 Plan 05: Canonical Signal Snapshot Summary

**Immutable full-MAC latest samples and bounded rejection truth now cross the existing high-rate/low-render-rate SignalBus boundary without affecting legacy acquisition paths.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-08-17T02:13:18Z
- **Completed:** 2026-08-17T02:18:31Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added distinct canonical accepted/rejected data-source contracts and application facade forwarding with explicit empty mock fallback behavior.
- Added immutable latest-by-full-MAC samples, accepted totals, bounded rejected totals, and per-source rejection metadata to `SignalSnapshot`.
- Preserved accepted values across rejections, accepted sequence resets at higher reconnect epochs, and kept canonical ingestion outside graph execution, recording, health, service, and OpenSim paths.
- Proved 100 high-rate accepts coalesce into one React notification at the existing animation-frame cadence.

## Task Commits

Each TDD task was committed through RED and GREEN gates:

1. **Task 1 RED: Define canonical data-source subscriptions** - `82400a1` (test)
2. **Task 1 GREEN: Expose canonical data-source subscriptions** - `a6bebf1` (feat)
3. **Task 2 RED: Define immutable canonical signal snapshot** - `8107356` (test)
4. **Task 2 GREEN: Publish canonical latest-by-MAC state** - `36a921b` (feat)

## Files Created/Modified

- `rehab-robotics-studio/src/data/DataSource.ts` - Canonical callback, unsubscribe, and bounded rejection metadata contracts.
- `rehab-robotics-studio/src/data/appDataSource.ts` - Live-only canonical accepted/rejected forwarding alongside unchanged legacy frame APIs.
- `rehab-robotics-studio/src/data/signalBus.ts` - Full-MAC current-session canonical state, bounded rejection state, and copy-on-publish snapshots.
- `rehab-robotics-studio/src/data/signalBus.test.ts` - Facade cleanup/isolation, high-rate throttling, immutability, rejection retention, deduplication, and reconnect coverage.

## Decisions Made

- Canonical callbacks are subscribed for the application lifetime but forward only while rosbridge is the active source, making fallback mode explicitly canonical-empty.
- Parser-owned frozen sample objects are retained across rejection publications; only containing maps and rejection state objects are copied/frozen on publish.
- A later acceptance clears only `last_update_rejected`; historical bounded rejection metadata remains available for persistent diagnostics.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected inconsistent SDK progress metadata**
- **Found during:** Plan close-out self-check
- **Issue:** `state.update-progress` updated the visible progress bar to 83% but wrote `percent: 0` in STATE frontmatter and left milestone totals at four plans.
- **Fix:** Aligned frontmatter and performance totals with five completed plans.
- **Files modified:** `.planning/STATE.md`
- **Verification:** `state.load` reports Plan 6 of 6 with five completed summaries and 83% visible progress.
- **Committed in:** `2be6cd7`

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** Tracking-only correction; implementation scope and runtime behavior are unchanged.

## Issues Encountered

None.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Verification

- `npm exec -- tsx --test src/data/signalBus.test.ts src/data/RosbridgeDataSource.test.ts` - 49 tests passed.
- `npm exec -- tsx --test src/data/signalBus.test.ts src/data/signalContract.test.ts` - 37 tests passed.
- `npm test` - 118 frontend tests passed.
- `npm run typecheck` - passed.

## Next Phase Readiness

- Plan 26-06 can render accepted source cards and persistent rejection notices directly from the immutable `useSignals()` snapshot.
- No blockers, stubs, new dependencies, or unplanned threat surfaces remain.

## Self-Check: PASSED

- All four created/modified plan files exist.
- All four TDD task commits are present in repository history.

---
*Phase: 26-signal-contract-and-provenance*
*Completed: 2026-08-16*
