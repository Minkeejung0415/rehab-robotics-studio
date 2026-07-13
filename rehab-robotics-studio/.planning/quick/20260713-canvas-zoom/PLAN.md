---
slug: canvas-zoom
date: 2026-07-13
---

# Quick Task: Canvas Zoom

## Goal
Add pinch-to-zoom / Ctrl+Wheel zoom and +/- button controls to the Block Diagram canvas.

## Approach
- `GraphCanvas.tsx`: add `zoom` state (0.25–2.0), wheel handler via useEffect (non-passive), zoom controls in heading row, two-div canvas-inner wrapper so scrollbar tracks zoomed content size, fix `toCanvasPoint` to divide by zoom.
- `BlockNode.tsx`: add `zoom` prop, divide client drag delta by zoom.
- `app.css`: `.zoom-controls` styles.

## Files
- `src/components/canvas/GraphCanvas.tsx`
- `src/components/canvas/BlockNode.tsx`
- `src/styles/app.css`
