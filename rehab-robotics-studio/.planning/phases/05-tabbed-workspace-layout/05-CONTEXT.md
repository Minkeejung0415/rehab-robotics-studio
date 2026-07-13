---
phase: 05-tabbed-workspace-layout
created: 2026-07-13
---

# Phase 5 Context: Tabbed Workspace Layout

## Goal

Add a LabVIEW-style tab bar below the Toolbar so users can switch between:
- **Block Diagram** — the graph editor (Library + Canvas + Properties)
- **Front Panel** — the live dashboard (Force, EMG, Motor, Logs)

## Why This Phase

The current layout renders both the graph workspace and dashboard as 4 side-by-side columns, hiding the Dashboard at narrow widths. A tabbed layout:
- Gives each view its full workspace width
- Matches LabVIEW's Block Diagram / Front Panel paradigm
- Fixes the narrow-screen dashboard-hidden problem

## What Exists

- `src/App.tsx` — 4-column workspace with BlockLibrary, GraphCanvas, PropertiesPanel, Dashboard
- `src/styles/app.css` — `.app-shell` grid (3 rows), `.workspace` grid (4 columns)
- `src/components/dashboard/Dashboard.tsx` — LIVE DASHBOARD aside component
- No tab state or tab UI exists anywhere

## Decisions (Auto-Resolved)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tab placement | Below Toolbar (own row in app-shell grid) | Matches LabVIEW chrome; clear separation from toolbar buttons |
| Tab state location | `useState` in App.tsx | Trivial 2-state value; no store needed |
| Default tab | Block Diagram | Users start in the editor, not the dashboard |
| Front Panel layout | Dashboard fills full workspace | Removes cramped 320px sidebar constraint |
| Diagram tab columns | 3 columns (Library, Canvas, Properties) | Dashboard moves to its own tab |
| Tab style | Dark border-bottom highlight on active | Consistent with existing dark chrome |

## Requirements

- **TAB-01**: A tab strip with "Block Diagram" and "Front Panel" tabs is visible below the Toolbar
- **TAB-02**: "Block Diagram" tab (default) shows BlockLibrary + GraphCanvas + PropertiesPanel
- **TAB-03**: "Front Panel" tab shows Dashboard in a full-width scrollable layout
- **TAB-04**: Active tab is visually distinguished (blue underline accent, bright text)
- **TAB-05**: No new dependencies — pure React state + CSS

## Success Criteria

1. Two tabs visible below Toolbar: "Block Diagram" (active by default) and "Front Panel"
2. Clicking "Block Diagram" shows Library + Canvas + Properties; clicking it again is a no-op
3. Clicking "Front Panel" hides graph workspace; Dashboard panels fill the space
4. Active tab has blue bottom border and bright color; inactive tab is muted
5. Runtime state, toolbar, status strip — all unchanged and still functional in both tabs
6. No regressions on Phase 1–4 interactions (keyboard delete, wiring, context menu, badges, Rec, toast)

## Constraints

- No new npm packages
- No Zustand store changes — UI-only state
- Preserve all existing class names and CSS (additive only)
