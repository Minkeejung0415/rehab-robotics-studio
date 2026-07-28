---
phase: 19
slug: studio-controls-live-angle
status: approved
shadcn_initialized: false
preset: none
created: 2026-07-28
reviewed: 2026-07-28
---

# Phase 19 — UI Design Contract

> Visual and interaction contract for the Studio visualizer control and trustworthy live OpenSim knee-angle display. This phase completes the existing operator workflow; it is not a visual redesign.

---

## Scope and Non-Goals

Phase 19 adds one toolbar action, completes the existing OpenSim health surface, and replaces every default product knee placeholder/fake-zero path with calibrated, valid, fresh OpenSim IK data from `/opensim/joint_states`.

The operator workflow is:

1. Select `Open visualizer`.
2. Stand still with knees extended and select `Calibrate`.
3. Wait for `CALIBRATED` and a valid IK solution.
4. Read the live `knee_angle_r` value in degrees in the existing Front Panel and Joint Angle Display.

Out of scope: an embedded Studio 3D renderer, new navigation, a calibration wizard or modal, additional OpenSim coordinates, clinical accuracy claims, cross-session calibration storage, process launch from browser code, and any fallback to custom relative-quaternion math.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | Existing hand-authored React/CSS design system; no shadcn |
| Preset | Not applicable |
| Component library | Existing local React components and native controls; no third-party component library |
| Icon library | None; the new action is text-only |
| Font | `'Segoe UI', system-ui, -apple-system, sans-serif`; `ui-monospace, 'Cascadia Code', monospace` for status, logs, and numeric readouts |

Source: existing `Toolbar.tsx`, `HealthPanel.tsx`, `MotorPanel.tsx`, `BlockNode.tsx`, `Toast.tsx`, `app.css`, and `theme/tokens.ts`.

Preserve the existing square-cornered, compact, dark test-bench language: native buttons, 1px borders, restrained color, monospaced telemetry, and text-first state communication. Do not introduce cards, rounded controls, gradients, icon-only buttons, animation, a spinner package, or a registry component.

---

## Spacing Scale

Declared values for Phase 19 additions (must be multiples of 4):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Inline status/value gaps |
| sm | 8px | Toolbar gaps, compact row gaps, readout inset |
| md | 16px | Grouped content separation |
| lg | 24px | Major panel or toast offset |
| xl | 32px | Reserved; no new Phase 19 layout requires it |
| 2xl | 48px | Reserved; existing chart height only |
| 3xl | 64px | Reserved; no new Phase 19 layout requires it |

No spacing exceptions are permitted in Phase 19. All margins, padding, gaps, and separator offsets must use only `4px`, `8px`, `16px`, `24px`, `32px`, `48px`, or `64px`: use `4px` or `8px` for compact internal gaps/padding, `8px` for panel padding, and `24px` for separator spacing. Existing control and row heights remain unchanged because they are component dimensions, not spacing tokens. Phase 19 adds no icon-only target.

The `Open visualizer` button uses the existing `.btn` height and horizontal padding. It sits directly after `Clear cal` and directly before `Save`, with the normal 8px toolbar gap and no additional separator.

---

## Typography

Phase 19 additions use exactly these four existing sizes and two weights (`400` and `700`). Existing unrelated `600` styles remain untouched; do not create a new Phase 19 `600` style.

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Metadata / badge / log row | 10px | 400 | 1.4 |
| Body / button / health value | 12px | 400 | 1.5 |
| Section heading | 13px | 700 | 1.2 |
| Live angle display | 22px | 400 | 1.2 |

Use the sans font for buttons and headings. Use the monospace font for the live angle, JointState/IK values, status badges, and System Log. Display valid knee angles to one decimal place as `{value} deg`; display no degree unit beside the unavailable em dash.

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `#15181a` | Application/canvas background and empty readout background |
| Secondary (30%) | `#1a1f23` | Toolbar, blocks, log, and control surfaces; retain `#16191b` panel alternate |
| Accent (10%) | `#7e6fe0` | Valid OpenSim knee value and its live chart stroke only |
| Destructive | `#ec5a5a` | Visualizer/IK failure text and existing fault semantics only |

Accent reserved for: a valid, fresh `knee_angle_r` numeric value and the live knee chart stroke. Do not apply purple to the visualizer button, waiting copy, HealthPanel headings, all controls, or entire panels.

Retain existing semantic colors:

- `#46c47a` for confirmed `CALIBRATED`, valid/live IK, and visualizer `Open`.
- `#e0a64a` for `CAPTURING`, invalid IK, and stale/waiting attention states.
- `#ec5a5a` for visualizer `Failed`/`Unavailable` reasons and OpenSim runtime errors.
- `#4a90d6` for existing selection/focus treatment only.
- `#8b969c` and `#5e686d` for waiting and secondary copy.

Every state includes explicit text and must remain distinguishable without color.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA | `Open visualizer` |
| Busy CTA | `Opening…` |
| Empty state heading | `Waiting for calibrated IK` |
| Empty state body | `Stand still with knees extended, select Calibrate, and wait for a valid IK solution.` |
| Error state | `OpenSim visualizer could not open: {reason}. Check the OpenSim runtime, then retry.` |
| Destructive confirmation | `Clear cal`: no modal; clear immediately, then show `Calibration cleared. Calibrate again before using IK angles.` |

Additional locked copy:

| Situation | Visible copy |
|-----------|--------------|
| Product angle unavailable | Numeric readout: `—`; adjacent status: `Waiting for calibrated IK` |
| Calibration `CAPTURING` | `Hold the standing, knees-extended pose until capture finishes.` |
| IK invalid | `IK invalid — {reason}` |
| JointState stale | `JointState stale — no fresh angle for 2.0 s` |
| Visualizer request in flight | Button: `Opening…`; HealthPanel: `Opening…` |
| Visualizer open | HealthPanel: `Open` |
| Visualizer unavailable before/after request | `Unavailable — {reason}` |
| Visualizer request failed | `Failed — {reason}` |

Copy rules:

- Normalize backend reason codes for display by replacing underscores with spaces and sentence-casing when no curated message exists. Never show `undefined`, `[object Object]`, raw JSON, a stack trace, or an empty reason.
- Preserve the specific backend reason after the fixed visualizer failure lead-in.
- Use `OpenSim IK`, not generic `angle solver`, for product-path status.
- Use `knee_angle_r` only in technical diagnostics/contract tests. User-facing labels remain `Knee` or `OpenSim knee angle`.
- Do not use celebratory success copy. Successful state is visible in HealthPanel and may produce one INFO transition log.

---

## Information Architecture

No new page, panel, dialog, or navigation item is added.

| Existing surface | Phase 19 contract |
|------------------|-------------------|
| Toolbar | Add `Open visualizer` after `Clear cal` and before `Save`; keep OpenSim actions contiguous. |
| Front Panel → `OpenSim Live Link` | Expand the existing key/value rows to expose visualizer state/reason, calibration state/reason, IK validity/reason, input age, calibration identity, and product-angle freshness. |
| Front Panel → `Motor / Joint` | Replace the fake-zero knee row with the gated product knee value or the unavailable placeholder. Suppress/pause the knee chart when unavailable. |
| Diagram → `OpenSim IK (Waiting)` | Promote the default product block to the live OpenSim IK source while preserving its position and ports; it emits only a valid, fresh product angle. |
| Diagram → `Joint Angle Display` | Show the same gated product value as the Front Panel or the same em-dash/waiting state. |
| System Log | Record visualizer, calibration, IK-validity, and stale/fresh transitions only; never log per JointState frame. |

The visual hierarchy remains: toolbar action first, persistent OpenSim truth in HealthPanel, primary numeric readout in the existing Motor/Joint and diagram display surfaces, detailed transition history in System Log.

---

## Component Inventory

| Component | Contract |
|-----------|----------|
| `Toolbar` visualizer button | Native `<button className="btn">`; label `Open visualizer`; `Opening…` while pending; `disabled` and `aria-busy="true"` only for the in-flight request. A prior failure/unavailable state never disables retry. |
| Existing `Toast` | Use only for visualizer request failure in this flow. Error toast uses fault border/text treatment and `role="alert"`/assertive announcement; it may auto-dismiss, because the same reason persists in HealthPanel and System Log. |
| `HealthPanel` OpenSim section | Compact `.kv-grid` rows, not a new card. Status values use text plus semantic color. Long reasons wrap; they do not truncate. |
| `MotorPanel` knee row | `Knee` label; one-decimal `{value} deg` only when gated live. Otherwise `—` plus `Waiting for calibrated IK`. |
| `MiniChart` knee series | Purple `joint_state` line only while valid/fresh; clear the prior series to an empty/no-trace state as soon as the angle gate closes. Never push placeholder zeros. |
| `BlockNode` angle body | Existing dark monospaced `.node-readout`; valid value at 22px or `—` with a 10px waiting label. Increase node height only if needed to prevent overlap; preserve node width and ports. |
| Status badges | Reuse `.status-badge`/semantic text treatments. Values: `WAITING`, `CAPTURING`, `LIVE`, `STALE`, `INVALID`, `FAILED`, `OPEN`. |

Do not add a modal, popover, tooltip dependency, progress bar, loading spinner, or duplicate retry button. The toolbar button itself is the visualizer retry.

---

## Visualizer Interaction Contract

The frontend invokes rosbridge service `/opensim/visualizer/open` using `std_srvs/Trigger`. Browser code must not call WSL, shell commands, OpenSim Python, or native process APIs.

| State | Button | HealthPanel | Feedback and transition |
|-------|--------|-------------|-------------------------|
| Idle / status unknown | `Open visualizer`, enabled | `Waiting` or the latest backend status | Activation sends one Trigger request. |
| Request pending | `Opening…`, disabled, `aria-busy="true"` | `Opening…` | Ignore duplicate pointer/keyboard activation. |
| Trigger accepted | Returns to `Open visualizer`, enabled | Backend status advances to `Opening…` then `Open` | One INFO log on transition; no success toast. |
| Already open | `Open visualizer`, enabled | `Open` | Activation may ask the backend to show/raise the native window; still one request at a time. |
| Runtime unavailable | `Open visualizer`, enabled for retry | `Unavailable — {reason}` in fault color | Failed activation shows the fixed error toast and one ERROR log. Reason persists. |
| Trigger failure / timeout | `Open visualizer`, enabled after settlement | `Failed — {reason}` | Toast + one ERROR log; a later successful backend state replaces the retained failure. |

Request timeout: 10 seconds. On timeout, treat the request as failed with reason `No response from the OpenSim service within 10 s`; restore the enabled label and retain the reason. A late status update may still replace the failure if the backend reports `Opening` or `Open`.

Keyboard and focus:

- The button is reachable in normal toolbar tab order between `Clear cal` and `Save`.
- `Enter` and `Space` activate it once.
- Focus remains on the same button across busy/success/failure label changes.
- Busy/disabled state is conveyed through the label and `aria-busy`, not opacity alone.

---

## Live Angle Data Contract

### Source and conversion

- Subscribe independently to `/opensim/status`, `/opensim/ik_status`, and `/opensim/joint_states`; do not infer one contract from another.
- Accept product position only from the `sensor_msgs/JointState` entry whose `name[index] === "knee_angle_r"` and whose paired `position[index]` is finite.
- Convert once at the GUI data-source boundary with `degrees = radians * 180 / Math.PI`.
- Preserve sign and show one decimal place. A true `0` radians is displayed as `0.0 deg` only when all gates below pass.
- Never read `/opensim/joint_angle`, `openSimStatus.joint_angle_deg`, relative quaternion helpers, or mock IK as product input.

### Required display gate

The product angle is visible only when all conditions are true at render time:

1. `/opensim/status.calibration.state === "CALIBRATED"`.
2. `/opensim/ik_status.solution_valid === true`.
3. The IK `calibration_id` is non-empty and equals the active calibration id.
4. A finite `knee_angle_r` position exists in a received `/opensim/joint_states` message.
5. The JointState source stamp is usable and not older than the last accepted source stamp.
6. Browser receipt age for the accepted JointState is at most `IK_ANGLE_STALE_MS = 2_000`.

Any gate closing immediately clears the displayable angle and live series. Do not retain the last number visually, dim it, interpolate it, or substitute `0`.

### Angle state matrix

| State | Numeric display | Adjacent/persistent status | Chart/data behavior |
|-------|-----------------|----------------------------|---------------------|
| No status yet / UNCALIBRATED | `—` | `Waiting for calibrated IK`; HealthPanel `Calibration required` | Empty chart; no zeros |
| CAPTURING | `—` | `Waiting for calibrated IK`; hold-pose instruction in HealthPanel | Empty chart |
| Calibration FAILED | `—` | `Waiting for calibrated IK`; calibration reason in fault color | Empty chart |
| CALIBRATED, IK invalid | `—` | `Waiting for calibrated IK`; `IK invalid — {reason}` in amber/fault according to backend availability | Empty chart |
| CALIBRATED, valid IK, no `knee_angle_r` | `—` | `Waiting for calibrated IK`; `knee_angle_r missing from JointState` | Empty chart |
| Valid fresh JointState | `{value} deg` | HealthPanel badge `LIVE`; expose source/input age | Append valid value only |
| Receipt age > 2,000 ms | `—` immediately | `Waiting for calibrated IK`; `JointState stale — no fresh angle for 2.0 s` | Clear trace; do not flat-line old value |
| Fresh valid data resumes | `{value} deg` | `LIVE` | Start a fresh series; do not bridge a line across the stale gap |
| Clear cal | `—` immediately | `Waiting for calibrated IK`; `Calibration required` | Clear trace and cached JointState |

Freshness uses monotonic/browser receipt time for the 2-second UI timeout so ROS and browser clock skew cannot make stale data appear live. Source stamps still enforce ordering and must not be rewritten to wall-clock time.

Log only transitions into/out of `LIVE`, `STALE`, and `INVALID`, plus visualizer state transitions. Coalesce repeated identical reasons. No JointState frame produces an individual log row.

---

## HealthPanel Contract

Keep the existing `OpenSim Live Link` section and add/replace rows in this order:

| Label | Value |
|-------|-------|
| Master quaternion | Existing sensor state |
| Slave quaternion | Existing sensor state |
| Calibration state | `UNCALIBRATED`, `CAPTURING`, `CALIBRATED`, or `FAILED` |
| Calibration reason | Specific reason or `—` |
| IK solution | `Valid`, `Invalid — {reason}`, or `Waiting` |
| IK input age | `{value.toFixed(2)} s` or `—` |
| Calibration ID | Active id or `—` |
| OpenSim knee angle | `{value} deg`, `Stale`, or `Waiting for calibrated IK` |
| Model | Existing model path or `Not loaded` |
| 3D visualizer | `Waiting`, `Opening…`, `Open`, `Unavailable — {reason}`, or `Failed — {reason}` |

Residuals may appear as compact secondary rows (`Residual RMS`, `Residual max`) when values are available; show `—` when absent. Do not treat absent residuals alone as a failure when `solution_valid` is true.

Visualizer failure reason remains visible until a later backend `Opening` or `Open` state replaces it. A toast dismissal does not clear the HealthPanel reason.

---

## Responsive and Layout Contract

- Preserve the existing desktop-first toolbar and Front Panel maximum width (`960px`).
- At widths where the toolbar cannot fit, allow the toolbar to scroll horizontally; do not wrap controls to a second row or reorder `Open visualizer`, `Clear cal`, and `Save`.
- HealthPanel remains a compact key/value grid. Long reasons wrap within the value column with `overflow-wrap: anywhere`.
- The unavailable label may wrap under the em dash on narrow panels; it must not overlap ports, chart, or neighboring values.
- No content shift is allowed when `Open visualizer` changes to `Opening…`: reserve sufficient button width for the longer label.

---

## Accessibility and Feedback

- Native buttons retain keyboard activation and visible focus treatment. Add no pointer-only interaction.
- `Opening…`, `Waiting for calibrated IK`, `STALE`, `INVALID`, `FAILED`, and `OPEN` supply textual state; color is secondary.
- The valid angle and unavailable em dash must be programmatically distinguishable. Announce state transitions, not high-frequency numeric updates.
- Use a polite live region for `Opening`/`Open` and an assertive alert only for a visualizer request failure. Do not put the continuously changing angle itself in a live region.
- The error toast may auto-dismiss after the existing 2.5 seconds because the identical actionable reason persists in HealthPanel and System Log.
- Do not move focus on backend status updates, calibration transitions, angle stale/fresh transitions, or toast appearance.
- Keep the existing E-STOP and motor state visually dominant; the OpenSim accent must not compete with fault/safety semantics.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | None | 2026-07-28 codebase inspection: `components.json` absent; existing manual React/CSS design system retained |
| Third-party registries | None | 2026-07-28 codebase inspection: no registry configuration or registry dependency present |

No registry block or third-party UI package may be introduced for this phase.

---

## Verification Contract

Deterministic frontend tests must prove:

- Toolbar order is `Calibrate` → `Clear cal` → `Open visualizer` → `Save`.
- One activation sends one `/opensim/visualizer/open` Trigger request; pending state shows `Opening…` and suppresses duplicates.
- Success, failure, timeout, and retry restore the correct label and preserve/replace HealthPanel reason as specified.
- `/opensim/status`, `/opensim/ik_status`, and `/opensim/joint_states` are handled as distinct messages.
- Only `knee_angle_r` is selected; array order changes and extra coordinates do not change selection.
- `Math.PI / 2` radians renders as `90.0 deg`; `0` renders as `0.0 deg` only through the valid gate.
- UNCALIBRATED, CAPTURING, FAILED, invalid IK, calibration-id mismatch, missing coordinate, non-finite position, out-of-order stamp, and stale receipt all render `—` plus `Waiting for calibrated IK`.
- The last valid number and chart series are cleared when a gate closes; stale recovery starts a new trace.
- Transition logs are coalesced and no per-frame logs are emitted.

Production-preview verification must cover Toolbar → Open visualizer request → Calibrate → live-angle Front Panel/diagram display. The real WSL native-window check is `human_needed` when OpenSim/Simbody runtime support is unavailable.

---

## Decision Provenance

| Source | Decisions carried into this contract |
|--------|--------------------------------------|
| `19-CONTEXT.md` | Toolbar placement/labels, Trigger boundary, failure persistence/retry, three distinct subscriptions, `knee_angle_r`, radians-to-degrees conversion, calibration+validity gates, em-dash waiting state, stale hiding, transition-only logs, deterministic tests, operator flow |
| `REQUIREMENTS.md` (`VIS-01`, `VIS-02`, consumes `IK-06`) | Top-level visualizer action, visible availability/failure reason, standard JointState display path |
| `ROADMAP.md` | Studio-chrome experiment workflow and runnable wireless checklist |
| `STATE.md` | Official OpenSim IK only, hard calibration gate, native visualizer dependency constraints |
| Phase 18 contracts | `/opensim/joint_states`, `knee_angle_r`, source stamps, `rehab.opensim_ik_status.1`, validity/reason/residual/age/calibration identity |
| Existing UI | Manual industrial CSS, compact toolbar and dashboard patterns, toast/log feedback, semantic colors, monospaced readouts, no component registry |

Defaults selected under the agent’s discretion: `/opensim/visualizer/open` service name, 10-second service timeout, 2-second product-angle stale timeout, no success toast, purple joint-state accent, and state-specific HealthPanel copy.

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS
- [x] Dimension 2 Visuals: PASS
- [x] Dimension 3 Color: PASS
- [x] Dimension 4 Typography: PASS
- [x] Dimension 5 Spacing: PASS
- [x] Dimension 6 Registry Safety: PASS

**Approval:** approved — reviewed 2026-07-28
