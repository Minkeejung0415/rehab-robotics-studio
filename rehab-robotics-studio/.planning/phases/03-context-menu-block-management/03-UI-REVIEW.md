# Phase 3 — UI Review

**Audited:** 2026-07-13
**Baseline:** `03-UI-SPEC.md`
**Screenshots:** not captured (no reachable local dev/preview server; code-only audit). Playwright QA reported 10/10 browser checklist separately — treated as interaction evidence, not visual pixel proof.
**Stance:** Advisory / non-blocking

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | Exact menu labels + empty-state copy; silent empty-name revert matches contract |
| 2. Visuals | 4/4 | Sharp LabVIEW menu chrome, portal overlay, clear hierarchy vs canvas |
| 3. Color | 3/4 | Accent reserved correctly for selection + menu focus; Name input lacks focused accent border |
| 4. Typography | 4/4 | Menu/body 12px/400; panel heading mono 11px/700; no new 500/600 weights |
| 5. Spacing | 3/4 | Menu 4/10/28/160 contract met; Name field still shares `6px 7px` vs preferred `6px 8px` |
| 6. Experience Design | 4/4 | Select-before-open, clamp, Escape/outside dismiss, live rename, empty-blur revert |

**Overall: 22/24**

---

## Top 3 Priority Fixes

1. **Focused Name input missing accent border** — Focused rename does not read as the declared accent affordance — add `.param-field input:focus-visible { border-color: #4a90d6; }` (or Name-specific rule).
2. **Name input padding `6px 7px` vs preferred `6px 8px`** — Minor 4-point scale drift vs UI-SPEC exception table — bump Name (or shared `.param-field input`) padding to `6px 8px`.
3. **No captured desktop/mobile screenshots this pass** — Visual regression still relies on Playwright checklist — optional follow-up capture under `.planning/ui-reviews/` when preview is up.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

**Contract match:**
- Block menu: `Duplicate` · `Rename` · separator · `Delete` — `GraphCanvas.tsx` items + `separatorBefore` / `danger` on Delete.
- Wire: `Delete` only (danger).
- Canvas: `Select All`.
- Properties empty: exact string `Select a block to inspect its parameters and terminal contract.`
- Label: `Name` via param-field pattern; replaces static `<h2>`.
- Duplicate naming: `` `${src.name} copy` `` in `graphStore.duplicateNode`.
- Empty name: silent blur revert (explicitly allowed); no incorrect toast/modal copy.

**No BLOCKERs.** No generic Submit/OK/Cancel CTAs introduced for this phase.

### Pillar 2: Visuals (4/4)

- Hand-rolled `position: fixed` portal (`ContextMenu.tsx` → `document.body`), `border-radius: 0`, `z-index: 1000`, min-width 160px — matches interaction + shell contract.
- Text-only items (no icon library) — matches Design System.
- Destructive Delete visually separated via `.is-danger` + separator before block Delete.
- Keyboard focus ring: inset 2px left accent bar on `:focus-visible` — clear without clutter.
- Focal point remains canvas selection chrome (`#4a90d6`); menu is ephemeral overlay.

### Pillar 3: Color (3/4)

| Token use | Spec | Implemented |
|-----------|------|-------------|
| Menu surface | `#1a1f23` | `.context-menu` background ✓ |
| Item text | `#dfe6ea` | `.context-menu-item` ✓ |
| Hover | `#1c2226` | ✓ |
| Destructive | `#ec5a5a` / hover `#3a2020` + `#ffd9d9` | ✓ |
| Separator | `#23292d` | ✓ |
| Border | `#30383d` | ✓ |
| Shadow | `0 8px 18px rgba(0,0,0,0.25)` | ✓ |
| Accent reserved | selection + menu focus + **focused rename border** | selection + menu focus ✓; **rename focus border missing** |

**WARNING:** Accent is not applied to focused Name/`param-field` input border. Default remains `#30383d` with no `:focus` / `:focus-visible` override in `app.css`.

Accent not leaked onto Duplicate/Rename/Select All labels — correct.

### Pillar 4: Typography (4/4)

Phase 3 additions:
- `.context-menu-item`: `font-size: 12px` (Body role), inherits Segoe stack via `button { font: inherit }`.
- Name field: reuses `.param-field` at 12px / regular weight (editable path per “prefer sans 12px”).
- `PROPERTIES` panel heading unchanged at mono 11px / 700 (Display role).

No Phase 3 introduction of font-weight 500/600 on new menu/name UI.

### Pillar 5: Spacing (3/4)

| Spec | Implemented |
|------|-------------|
| Menu panel padding 4px | ✓ |
| Item height 28px | ✓ |
| Item horizontal padding 10px | ✓ |
| Separator margin 4px | ✓ |
| Viewport clamp inset 4px | `ContextMenu` `pad = 4` ✓ |
| Duplicate offset +40/+40 | `graphStore` ✓ |
| Name input padding 6×8 | **Shared `.param-field input` is `6px 7px`** — WARNING |

Menu spacing contract is solid; only the preferred Name padding alignment is off by 1px horizontal.

### Pillar 6: Experience Design (4/4)

Coverage vs Interaction Contract:
- Right-click select-before-open on block/wire ✓
- `preventDefault` on block/wire (and canvas when target matches) ✓
- Close: Escape, outside `pointerdown`, action, scroll/resize ✓
- Rename → select + double-rAF focus `#block-name-input` ✓
- Live `renameNode` on keystroke ✓
- Empty blur restores `lastNonEmptyRef` ✓
- No delete confirmation modal (required) ✓
- Multi-select Select All + keyboard batch delete (Plan 01) supports menu flow ✓

External evidence: Playwright QA **10/10** checklist passed (per orchestrator). No loading/skeleton needed for sync store actions.

**No BLOCKERs.**

---

## Registry Safety

Skipped — `components.json` absent; UI-SPEC lists no third-party registries (`shadcn_initialized: false`).

Registry audit: 0 third-party blocks checked, no flags.

---

## Files Audited

- `.planning/phases/03-context-menu-block-management/03-UI-SPEC.md`
- `.planning/phases/03-context-menu-block-management/03-CONTEXT.md`
- `.planning/phases/03-context-menu-block-management/03-01-SUMMARY.md`
- `.planning/phases/03-context-menu-block-management/03-02-SUMMARY.md`
- `src/components/common/ContextMenu.tsx`
- `src/components/canvas/GraphCanvas.tsx`
- `src/components/canvas/BlockNode.tsx`
- `src/components/canvas/Wire.tsx`
- `src/components/properties/PropertiesPanel.tsx`
- `src/state/graphStore.ts` (duplicate/rename/selectAll contracts)
- `src/styles/app.css` (`.context-menu*`, `.param-field`, `.block-node.is-selected`)
