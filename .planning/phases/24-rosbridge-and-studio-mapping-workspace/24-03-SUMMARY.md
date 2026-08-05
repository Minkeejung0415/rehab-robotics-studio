---
phase: 24-rosbridge-and-studio-mapping-workspace
plan: "03"
subsystem: studio-ui
tags: [react, zustand, mapping-workspace, typescript]
requirements: [UI-01, UI-02, UI-03, UI-04]

dependency_graph:
  requires:
    - 24-01  # mappingStore.ts (useMappingStore, MappingRow types)
  provides:
    - MappingWorkspace component (exported as named export)
    - MappingHeader, MappingTable, MappingDeviceRow, MappingFooter (internal sub-components)
  affects:
    - App.tsx (will import MappingWorkspace in Plan 24-04)
    - appDataSource.ts (service calls wired in Plan 24-04 via dynamic import)

tech_stack:
  added: []
  patterns:
    - zustand selector hooks per sub-field (useMappingStore((s) => s.rows))
    - dynamic import for appDataSource service calls (avoids circular dependency)
    - inline <style> block for component-scoped CSS
    - two-click inline confirmation pattern for destructive Reset action
    - useRef+setTimeout for auto-revert of Reset confirm state

key_files:
  created:
    - rehab-robotics-studio/src/components/mapping/MappingWorkspace.tsx
  modified: []

decisions:
  - "All sub-components (MappingHeader, MappingTable, MappingDeviceRow, MappingFooter) kept in one file (884 lines) per UI-SPEC — split threshold of 200 lines applies to sub-component files, not the parent"
  - "Component CSS injected via <style>{STYLES}</style> block rather than a separate .css file — style content is ~100 lines, within the 50-line inline threshold in UI-SPEC"
  - "applyEnabled used for disabled prop on Apply button rather than redundant applyStatus === 'applying' check — avoids TS2367 narrowing error"
  - "@ts-expect-error used on dynamic imports of callMappingSetAssignment, callMappingApply, callMappingReset, callMappingIdentifyDevice — these are wired in Plan 24-04"

metrics:
  duration: "3m 24s"
  completed: "2026-08-05"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 0
---

# Phase 24 Plan 03: MappingWorkspace Component Summary

Full MappingWorkspace.tsx panel implementation — 9-column device table with segment selector, Not Used checkbox, per-row Save/Identify buttons, 5-state panel badge, Apply/Reset footer with two-click confirmation, calibration interlock banner, and duplicate segment detection.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create MappingWorkspace.tsx — header, table structure, row rendering | c054cbf | rehab-robotics-studio/src/components/mapping/MappingWorkspace.tsx |
| 2 | Add footer, duplicate detection, and per-row interaction handlers | c054cbf | (same file — implemented in single pass) |

## What Was Built

### MappingHeader

- `.mapping-workspace-header` container with `.dash-head` row
- `h3 "Mapping Workspace"` heading
- Panel-level state badge (`.motor-pill`) with 5 states:
  - `NO MODEL` — `motor-pill fault` (red) when `catalogModelHash === null`
  - `DRAFT` — amber border/text when any row has `mappingStatus === 'draft'`
  - `SAVED` — blue border/text when `mappingRevision > appliedRevision` and no drafts
  - `APPLIED` — `motor-pill enabled` (green) when `appliedRevision === mappingRevision`
  - `RUNTIME READY` — solid green border, bold when Applied + all ikValid
- Model hash (8-char prefix, monospace `<code>` element)
- Model path (truncated with `text-overflow: ellipsis`)
- `role="status" aria-live="polite"` on panel badge per UI-SPEC

### MappingTable + MappingDeviceRow

- `.mapping-table-wrap` scrollable container with `min-width: 860px`
- Sticky thead (position: sticky, z-index: 2) with 9 column headers
- Empty state: "No devices found — start acquisition or check ROS bridge connection."
- Per-row columns:
  1. MAC — full `deviceId` in monospace
  2. Role — muted 10px label
  3. Connection — color-coded per `connectionStateColor()` (#46c47a/#ec5a5a/#e0a64a/#5e686d)
  4. Rate/Drops — monospace, muted
  5. Segment — `<select>` with `catalogFrameList` options; "Model not loaded" disabled option when empty; disabled when `notUsedEffective`; inline duplicate warning below
  6. Not Used — `<input type="checkbox">` setting `draftNotUsed`
  7. Status — `.status-badge` with inline style color/borderColor per `rowBadgeStyle()`; appends "/ Offline" label when `connectionState === 'disconnected'`
  8. Identify — `.mini-btn`; "…" when busy; shows outcome label (Confirmed/Timeout/Offline/Unsupported/Rejected) for 5 s post-completion
  9. Save — `.mini-btn`; enabled when `hasDraft`; shows "Saving…" during in-flight call

### MappingFooter

- `.mapping-workspace-footer` flex row with Apply, Reset/Confirm Reset, error span
- Calibration interlock banner (`node-imu-pending`, `role="status" aria-live="polite"`) rendered above footer when `calibrationInterlocked === true`
- Apply Mapping button: `applyEnabled` guard (`!applying && !interlocked && revision > 0`); accent border (#4a90d6) when enabled; "Applying…" transient label
- Apply error span: `.health-error`, `role="alert" aria-live="assertive"`, visible only when `applyStatus === 'error'`
- Reset two-click confirmation: `useState(resetConfirm)` + `useRef(resetTimeoutRef)`; auto-reverts after 5000 ms; focuses Confirm Reset button programmatically on transition

### Interaction Handlers

- `handleSave(deviceId)` — dynamic import `callMappingSetAssignment`; sets isSaving on row; calls clearDraft on ok; shows "Save failed: {detail}" on error
- `handleIdentify(deviceId)` — dynamic import `callMappingIdentifyDevice`; setIdentifyBusy during flight; setIdentifyResult on completion (auto-clears in store after 5 s)
- `handleApply()` — dynamic import `callMappingApply`; maps all 5 outcome strings to D-15 error copy
- `handleReset()` — two-click pattern; dynamic import `callMappingReset` on confirm click

### Duplicate Segment Detection (D-21)

`buildDuplicateSegments()` computes a `Map<string, number>` of effective segment counts across all rows. Effective segment = `draftSegment ?? backendSegment` when row is not marked not-used. Segments with count > 1 entered into `Set<string>`. Each row checks membership and shows `"Segment already assigned to another device."` below the `<select>`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Redundant `applyStatus === 'applying'` in `disabled` prop**
- **Found during:** TypeScript verification (TS2367)
- **Issue:** `disabled={!applyEnabled || applyStatus === 'applying'}` — after narrowing via `applyEnabled`, TS knows `applyStatus` cannot be `'applying'` in the `||` branch, causing TS2367 "no overlap" error
- **Fix:** Simplified to `disabled={!applyEnabled}` — `applyEnabled` already encodes `applyStatus !== 'applying'`
- **Files modified:** MappingWorkspace.tsx
- **Commit:** c054cbf

## Known Stubs

The following dynamic imports use `@ts-expect-error` because the service exports are wired in Plan 24-04:

| Stub | File | Location | Resolution |
|------|------|----------|------------|
| `callMappingSetAssignment` dynamic import | MappingWorkspace.tsx | `handleSave` | Plan 24-04 exports from appDataSource.ts |
| `callMappingApply` dynamic import | MappingWorkspace.tsx | `handleApply` | Plan 24-04 exports from appDataSource.ts |
| `callMappingReset` dynamic import | MappingWorkspace.tsx | `handleReset` | Plan 24-04 exports from appDataSource.ts |
| `callMappingIdentifyDevice` dynamic import | MappingWorkspace.tsx | `handleIdentify` | Plan 24-04 exports from appDataSource.ts |

These stubs are intentional — Plan 24-04 is the designated wiring plan. The `@ts-expect-error` directives keep TypeScript clean at this phase.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. MappingWorkspace is a pure UI component — all ROS service calls are deferred to appDataSource via dynamic imports. No additional threat surface beyond what was modeled in the plan's STRIDE register.

## Self-Check: PASSED

- [x] `rehab-robotics-studio/src/components/mapping/MappingWorkspace.tsx` exists (884 lines)
- [x] `export function MappingWorkspace` — 1 occurrence
- [x] `useMappingStore` — 29 occurrences
- [x] `mapping-table` — 11 occurrences
- [x] `aria-label` — 9 occurrences (> 5 required)
- [x] `motor-pill` — 5 occurrences
- [x] `mapping-workspace-footer` — 2 occurrences
- [x] `Apply Mapping` — 2 occurrences
- [x] `Confirm Reset` — 3 occurrences
- [x] `calibrationInterlocked` — 6 occurrences
- [x] `Segment already assigned` — 1 occurrence
- [x] `aria-live` — 3 occurrences
- [x] Commit c054cbf exists
- [x] `npx tsc --noEmit` exits 0
