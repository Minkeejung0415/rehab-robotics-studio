---
phase: 9
slug: range-correct-measurement-contract
status: draft
shadcn_initialized: false
preset: none
created: 2026-07-23
---

# Phase 9 — UI Design Contract

> Visual and interaction contract for the range-correct measurement change. This phase is a narrow correction to the existing industrial UI, not a redesign.

---

## Scope and Non-Goals

The operator continues to use the existing `ACCEL` and `GYRO` controls in the ESP32 IMU block and the existing physical readouts. Phase 9 adds no panel, diagnostics card, modal, toast, badge, icon, or navigation path.

The only new operator-facing state is one actionable `WARN` entry in the existing System Log per rosbridge connection when a live raw frame cannot be trusted because its scale metadata is missing or invalid. Untrusted frames must not update physical readouts or mark the ESP32 stream as active.

Out of scope: firmware timestamps and sequence framing, connection recovery redesign, health-expiry behavior, graph layout changes, new range controls, and display of scale metadata as a diagnostics surface.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | Existing hand-authored React/CSS design system; no shadcn |
| Preset | Not applicable |
| Component library | Existing local React components and native controls; no third-party component library |
| Icon library | None; add no icon for this phase |
| Font | `'Segoe UI', system-ui, -apple-system, sans-serif`; `ui-monospace, 'Cascadia Code', monospace` for controls, status, logs, and physical readouts |

Source: existing `app.css`, `theme/tokens.ts`, `BlockNode.tsx`, and `LogsPanel.tsx`. Preserve square corners, 1px borders, compact density, dark test-bench surfaces, and text-first status communication.

---

## Spacing Scale

Declared values for any Phase 9 additions (must be multiples of 4):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Inline gaps inside an existing compact row |
| sm | 8px | Existing block-control and log-container inset |
| md | 16px | Default grouped-content separation if required |
| lg | 24px | Existing major control/readout separation only |
| xl | 32px | Reserved; no Phase 9 layout requires it |
| 2xl | 48px | Reserved; no Phase 9 layout requires it |
| 3xl | 64px | Reserved; no Phase 9 layout requires it |

Exceptions: preserve inherited legacy component measurements such as 5px control gaps, 6px log-row gaps, 7px control padding, and 10px panel padding. Phase 9 introduces no new layout, so it must not normalize or duplicate those values in new selectors.

---

## Typography

Phase 9 may use exactly these four existing sizes and two weights (`400` and `700`). Do not introduce a new type style.

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Metadata / log row | 10px | 400 | 1.4 |
| Body / control feedback | 12px | 400 | 1.5 |
| Section heading | 13px | 700 | 1.2 |
| Physical readout | 22px | 400 | 1.2 |

The `WARN` level label may use 10px at 700 as an emphasis variant. Warning and error copy remains sentence case; existing control labels (`ACCEL`, `GYRO`, `APPLYING`) remain uppercase.

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `#15181a` | Application and canvas background; unchanged |
| Secondary (30%) | `#1a1f23` | Existing block, log, and control surfaces; existing panel alternate `#16191b` remains unchanged |
| Accent (10%) | `#e0a64a` | `WARN` level text and existing `APPLYING` range-control state only |
| Destructive | `#ec5a5a` | Existing fault/error semantics and rejected range-command log entries only; Phase 9 adds no destructive action |

Accent reserved for: the single scale-metadata warning in the System Log and the existing pending range-control state. Do not apply amber to valid measurements, normal controls, all interactive elements, or entire panels.

The existing blue `#4a90d6` selection/focus treatment and green `#46c47a` confirmed/healthy treatment remain unchanged; they are not repurposed by Phase 9. Every state must include text (`WARN`, `ERROR`, `APPLYING`, or the existing status value) and must not rely on color alone.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA | `Reconnect ROS` — reuse the existing recovery button only; do not add a second CTA |
| Empty state heading | `Measurements unavailable` — use only if an existing physical readout already supports an unavailable state; do not create a new empty-state panel |
| Empty state body | `Scale metadata has not been confirmed. Confirm ACCEL and GYRO ranges, then reconnect ROS.` |
| Warning state | `Live IMU measurements paused: scale metadata is missing or invalid for {device list}. Confirm ACCEL and GYRO ranges, then reconnect ROS.` |
| Error state | `Range change rejected. Keeping confirmed {range} {unit}. Check the device and try again.` |
| Destructive confirmation | None — Phase 9 introduces no destructive action or confirmation |

Copy rules:

- `{device list}` is `MASTER`, `SLAVE`, or `MASTER and SLAVE` when known. Never expose `undefined`, raw JSON, or an exception string as the device label.
- `{unit}` is `g` for acceleration range and `dps` for gyroscope range.
- The warning is emitted at most once for each rosbridge connection, regardless of how many invalid frames arrive. A new WebSocket connection resets the latch.
- Preserve a specific firmware rejection reason after the normalized error sentence when one is available; do not replace an actionable device reason with generic failure copy.
- Do not announce a successful range change until firmware acknowledgement has committed the confirmed value.

---

## Visual and Interaction Contract

### Existing Surfaces

| Surface | Required Phase 9 behavior |
|---------|---------------------------|
| ESP32 IMU `ACCEL` selector | Keep options `2 g`, `4 g`, `8 g`, and `16 g`. Disable with the other IMU controls while a command is pending. Update the displayed/graph value only after firmware acknowledgement. |
| ESP32 IMU `GYRO` selector | Keep options `250 dps`, `500 dps`, `1000 dps`, and `2000 dps`. Disable with the other IMU controls while a command is pending. Update the displayed/graph value only after firmware acknowledgement. |
| `APPLYING` feedback | Preserve the existing inline amber text. Do not add a spinner, progress bar, toast, or modal. |
| Physical readouts | Preserve current components, units, precision, dimensions, and placement. Update them only from metadata-valid physical frames. Never substitute default scale constants, clamped ranges, zero-filled samples, or raw counts as physical values. |
| System Log | Reuse the existing `.log-row.level-warn` treatment for the one-per-connection warning. The row must contain the `WARN` label and actionable text. Do not show the same warning as a toast. |
| Status strip | `ESP32 stream` may become `Streaming` only after a metadata-valid physical frame reaches consumers. Invalid raw traffic must leave it at the existing non-active state (`Awaiting data`) and must not invoke first-valid-frame behavior. |
| Acquisition Health | No new row, badge, or scale status. Existing connection and recording health content remains unchanged. |

### Measurement Trust States

| State | Visual state | Interaction and data behavior |
|-------|--------------|-------------------------------|
| Connecting; no raw sample yet | Existing `ROS`/`ESP32 stream` awaiting states; no scale warning | Wait for a raw frame. Absence of a frame alone is not a metadata failure. |
| Metadata valid for every device used by the frame | Existing readouts update normally; stream may show `Streaming` | Convert each device independently from its own `sensor_config`, then perform pair/relative calculations. |
| `sensor_config` absent, incomplete, unsupported, non-finite, internally inconsistent, or uses undeclared units | One amber `WARN` log row for the current connection; no new panel | Drop the affected physical frame before it reaches subscribers. Do not trigger `onFrameReceived`, do not mark the stream active, and do not calculate pair-relative output with that frame. |
| Further invalid frames on the same connection | No additional warning rows | Continue suppressing untrusted physical frames; retain the warning latch. |
| Valid metadata arrives later on the same connection | Existing readouts resume updating and stream status becomes active on the first valid frame | Resume automatically without requiring dismissal and without a success toast. Conversion must use the newly validated metadata. |
| New rosbridge connection | Existing connection UI; no immediate warning | Reset the warning latch, cached raw master/slave samples, and pair-angle state so samples from separate connections cannot be combined. |
| Supported range request pending | Existing controls disabled; `APPLYING` shown | Retain the last confirmed range for conversion until acknowledgement. |
| Range request acknowledged | Selector/graph value changes to confirmed range; existing INFO log may report confirmation | Use the acknowledged range for subsequent frame metadata and scaling. |
| Range request rejected or unsupported | Selector returns to/retains last confirmed value; one existing ERROR log entry | Preserve the last confirmed range and scale. Never clamp, optimistically update, or reinterpret subsequent samples using the rejected value. |

### Metadata Validation Boundary

A GUI physical frame is trusted only when the raw message remains under `oe_esp32.raw.v1` and contains a valid `sensor_config` with:

- `accel_range_g` in `2`, `4`, `8`, or `16`;
- `gyro_range_dps` in `250`, `500`, `1000`, or `2000`;
- finite, positive accelerometer and gyroscope LSB sensitivities;
- declared raw-count and physical units sufficient to convert acceleration to `m/s²` and angular velocity to `rad/s`; and
- range and sensitivity values that agree with the shared supported-range definition.

Master and slave metadata is validated and applied independently. Any physical calculation involving both devices requires valid current-connection metadata for both; do not reuse a cached sample from a prior connection or an invalid device frame.

Quaternion handling and normalization are unchanged in this phase except that a quaternion carried by an otherwise untrusted raw frame must not be emitted as part of a physical GUI frame.

---

## Accessibility and Feedback

- Keep the existing native `select` controls and their current accessible names: `ESP32 accelerometer range` and `ESP32 gyroscope range`.
- Pending controls remain disabled until the request resolves; `APPLYING` provides a textual status in addition to amber color.
- The metadata warning appears in the persistent System Log with timestamp, `WARN` level text, and remediation. It must be readable without interpreting color.
- Do not use the 2.5-second toast for this acquisition-integrity warning; the operator may need the remediation text after the first invalid frame.
- Do not shift keyboard focus when warning, suppressing, resuming, acknowledging, or rejecting a range.
- Preserve existing responsive behavior and control dimensions. Phase 9 adds no touch-target or breakpoint exception.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | None | 2026-07-23 codebase inspection: `components.json` absent; shadcn not initialized |
| Third-party registries | None | 2026-07-23 codebase inspection: no registry configuration or registry component dependency present |

No registry code may be introduced for this phase.

---

## Decision Provenance

| Source | Decisions carried into this contract |
|--------|--------------------------------------|
| `09-CONTEXT.md` | Existing controls/readouts, acknowledgement-driven ranges, additive metadata, no default fallback, independent master/slave scaling, one warning per connection, no new diagnostics panel |
| `REQUIREMENTS.md` (`DATA-01`, `DATA-02`) | Range-correct physical conversion and sufficient metadata for consistent backend/GUI interpretation |
| `ROADMAP.md` | Operator-visible trust for supported non-default ranges and cross-consumer consistency |
| Existing UI | Manual industrial CSS, current typography/colors, System Log warning surface, native range selectors, existing stream status |

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
