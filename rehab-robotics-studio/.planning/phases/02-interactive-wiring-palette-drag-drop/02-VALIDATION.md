---
phase: 2
slug: interactive-wiring-palette-drag-drop
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-13
---

# Phase 2 - Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | None; dependency additions are out of scope |
| Config file | none |
| Quick run command | `npm run typecheck` |
| Full suite command | `npm run build` |
| Estimated runtime | under 30 seconds |

## Sampling Rate

- After every task commit: run `npm run typecheck`.
- Before phase verification: run `npm run build` and browser checks against `npm run preview`.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 02-01-01 | 01 | 1 | GRAPH-03 | Type/build + browser | `npm run typecheck` | pending |
| 02-01-02 | 01 | 1 | GRAPH-04 | Type/build + browser | `npm run typecheck` | pending |
| 02-01-03 | 01 | 1 | GRAPH-03, GRAPH-04 | End-to-end browser | `npm run build` | pending |

## Manual Verifications

| Behavior | Requirement | Test Instructions |
|----------|-------------|-------------------|
| Compatible port wiring | GRAPH-03 | Drag an output terminal to a same-type input and confirm a permanent wire appears. |
| Wire cancellation | GRAPH-03 | Start a wire then release over canvas background and press Escape in a second attempt; both previews disappear without a new edge. |
| Palette placement | GRAPH-04 | Drag a palette block into the canvas and confirm it appears near the drop point, is selected, and retains its definition. |

