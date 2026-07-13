# Phase 4: Runtime Feedback + Deploy Polish - Research

**Researched:** 2026-07-13
**Domain:** Zustand cross-store runtime badges, toolbar recording toggle, hand-rolled toast
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Run/Stop Block Status Badges (RT-01)
- On Run, every block on the canvas gets status `"running"`
- On Pause, badges stay `"running"` (RUNTIME pill shows paused)
- On Stop / E-STOP / Reset, all badges return to `"idle"`
- Update badges synchronously via a graphStore bulk setter called from runtime actions

#### Recording Toggle + Deploy Toast (RT-02, DEP-01)
- Toolbar Rec button after Stop (before Validate); label toggles `● Rec` / `○ Rec`
- Disable Rec when estopped/faulted (same as Run/Deploy)
- Hand-rolled top-center toast via portal (~2.5s auto-dismiss), plus existing deploy log
- Toast copy: `Deploy (mock) started — graph would be pushed to Jetson`

#### Feedback Polish & Edge Cases
- Single toast at a time — replace previous if still visible
- Auto-dismiss ~2.5s; also click-to-dismiss
- Rec button shows pressed/active chrome when recording On (align with strip red fault-level light)
- Out of scope: real deploy, animated wire flow, per-block progress %

### Claude's Discretion (locked by UI-SPEC pre-population)
- graphStore API name: `setAllNodeStatuses`
- Toast component file: `src/components/common/Toast.tsx` (same folder as ContextMenu)
- `run()` from paused path re-asserts running badges (via `resume()` and/or shared helper)
- CSS tokens within existing LabVIEW chrome — no new deps

### Deferred Ideas (OUT OF SCOPE)
- Real Jetson deploy / hardware push
- Animated data flow on wires (VIS-01)
- Per-block progress or warning/error simulation during run
- Tabbed workspace layout (Phase 5)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RT-01 | Block status badges update to "running" when execution starts and back to "idle" when stopped | `setAllNodeStatuses` on graphStore; call from runtimeStore `run`/`resume` → `'running'`; `stop`/`estop`/`reset` → `'idle'`; `pause` does not touch badges; BlockNode already renders `node.status` via `statusColor` |
| RT-02 | Toolbar Rec toggles Recording status-strip indicator | Insert Rec after Stop; `systemStore.setRecording(!on)` already drives strip `On`/`Off` + `fault`/`idle` levels; disabled when `estopped`/`fault` |
| DEP-01 | Deploy Mock shows brief toast/banner plus existing log | Hand-roll `Toast` portal (ContextMenu pattern); extend `actions.deployMock` or Toolbar click to show toast; keep log string unchanged |
</phase_requirements>

## Summary

Phase 4 closes the last mock-frontend interaction gaps: live block status badges during Run/Stop, a Recording toolbar control wired to the existing status-strip light, and a Deploy Mock confirmation toast. Almost all store methods already exist (`run`/`pause`/`stop`/`estop`/`reset`, `setRecording`, `deployMock` log). The missing pieces are (1) a bulk node-status writer and calls from the runtime state machine, (2) a Rec button in the toolbar, and (3) a hand-rolled portal toast.

**Primary recommendation:** Add `setAllNodeStatuses(status: BlockStatus)` to `graphStore`; invoke it from `runtimeStore` methods (not from Toolbar buttons directly) so every entry path — including `resume` after pause and E-STOP — stays consistent. Mount Rec in `Toolbar` after Stop. Add `Toast.tsx` under `common/` with `createPortal` to `document.body`, z-index 1100, and a small host state either in Toolbar or a thin toast module that `deployMock` / Toolbar can trigger. No npm installs.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Bulk node status mutation | Browser / Client (Zustand graphStore) | — | `BlockInstance.status` lives on graph nodes |
| Runtime → badge sync | Browser / Client (Zustand runtimeStore) | graphStore via getState() | Same cross-store pattern as runtime → systemStore logs |
| RUNTIME pill UI | Browser / Client (Toolbar) | runtimeStore.state | Already wired; unchanged |
| Recording toggle UI | Browser / Client (Toolbar) | systemStore.setRecording | Store method exists; button missing |
| Recording strip light | Browser / Client (StatusStrip) | systemStore.status.recording | Already renders; no StatusStrip changes |
| Deploy log | Browser / Client (actions.deployMock) | systemStore.addLog | Keep existing message |
| Deploy toast overlay | Browser / Client (Toast + host) | actions or Toolbar | Portal overlay; no server |
| Badge paint | Browser / Client (BlockNode) | statusColor tokens | Already renders `node.status` — no BlockNode API change |

## Standard Stack

### Core (already installed — no installs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | ^18.3.1 (installed 18.3.x) | Toast portal, Toolbar buttons, effects for dismiss timer | Existing [VERIFIED: package.json] |
| react-dom | ^18.3.1 | `createPortal` for toast (same as ContextMenu) | Existing [CITED: react.dev/reference/react-dom/createPortal] |
| Zustand | ^4.5.5 | graphStore + runtimeStore + systemStore | Existing cross-store via `.getState()` |
| TypeScript | ^5.6.3 | Typed BlockStatus / RuntimeState | Existing |
| Vite | ^5.4.11 | Dev/build | Existing |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| playwright (dev) | ^1.61.1 | Optional phase-gate browser scripts (already present) | Browser checklist only — do not add Vitest/Jest |
| — | — | Toast / Rec chrome | Hand-roll CSS in `app.css` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled Toast | `react-hot-toast` / Radix Toast | Better a11y defaults, but CONTEXT forbids new deps |
| Badge updates in Toolbar onClick | Updates inside runtimeStore methods | Toolbar-only misses estop/reset/resume consistency |
| Imperative toast DOM | React portal component | Portal matches ContextMenu; stays in React tree |
| Per-node status animation | Pulse / progress % | Deferred (out of scope) |

**Installation:**

```bash
# No new packages — do not run npm install for this phase
```

**Version verification:** Read `package.json` on 2026-07-13 → react/react-dom ^18.3.1, zustand ^4.5.5, typescript ^5.6.3, vite ^5.4.11, playwright ^1.61.1 (dev only). No test runner (Vitest/Jest) — keep it that way.

## Package Legitimacy Audit

> No external packages are installed in this phase. Section is not applicable.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — | — | — | — | — | — | N/A |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Toolbar Run/Pause/Stop/E-STOP/Reset
        |
        v
  runtimeStore.run / pause / resume / stop / estop / reset
        |
        +-- mockDataSource start/pause/stop (existing)
        +-- systemStore logs / motor / fault (existing)
        +-- NEW: useGraphStore.getState().setAllNodeStatuses('running'|'idle')
                    |
                    v
              nodes[].status  -->  BlockNode .status-badge (existing paint)

Toolbar Rec
        |
        v
  systemStore.setRecording(!current)  -->  StatusStrip Recording light (existing)

Toolbar Deploy Mock
        |
        +-- actions.deployMock() --> addLog (existing string)
        +-- showToast(message)   --> Toast portal (NEW) --> auto-dismiss 2500ms
```

### Pattern 1: Bulk status setter (graphStore)

```
setAllNodeStatuses(status: BlockStatus):
  set(s => ({ nodes: s.nodes.map(n => n.status === status ? n : { ...n, status }) }))
```

- Empty canvas: map over `[]` → no-op (OK).
- Prefer immutable map; optional identity skip when status already matches (Claude discretion — either fine).
- Do **not** change selection, edges, or params.
- New nodes from `addNode` / `duplicateNode` already start `status: 'idle'` — if added while running, they stay idle until next Run (acceptable; no live re-scan required this phase).

### Pattern 2: Runtime → graph sync

Call sites (all inside `runtimeStore.ts`):

| Method | Badge call | Notes |
|--------|------------|-------|
| `run` (idle → running) | `setAllNodeStatuses('running')` | After successful transition |
| `resume` (paused → running) | `setAllNodeStatuses('running')` | Re-assert per UI-SPEC / discretion |
| `run` when `state === 'paused'` | delegates to `resume()` | Badges handled in resume |
| `pause` | **none** | Badges stay running |
| `stop` | `setAllNodeStatuses('idle')` | After successful idle transition |
| `estop` | `setAllNodeStatuses('idle')` | Always (estop has no can-guard) |
| `reset` | `setAllNodeStatuses('idle')` | After successful reset from estopped/fault |
| `raiseFault` | optional idle | Not in CONTEXT success path; recommend idle for consistency (Claude discretion: set idle) |

Import: `useGraphStore.getState().setAllNodeStatuses(...)` — mirror existing `useSystemStore.getState()` usage in runtimeStore. Avoid circular imports: graphStore must not import runtimeStore (it does not today).

### Pattern 3: Rec button (Toolbar)

Order locked by UI-SPEC:

`Run · Pause · Stop · Rec · sep · Validate · Deploy · …`

- Label: recording Off → `○ Rec`; On → `● Rec`
- `title="Toggle recording"`
- Subscribe: `useSystemStore(s => s.status.recording.value === 'On')` or derive from value
- onClick: `setRecording(!isRecording)`
- `disabled={blocked}` where `blocked = state === 'estopped' || state === 'fault'`
- Active chrome: when On, add class e.g. `btn-rec-on` (or reuse `.btn-estop` colors without the armed variant) — bg `#3a2020`, text `#ffd9d9`, border `#7a3030` / `#ec5a5a` per UI-SPEC

### Pattern 4: Hand-rolled Toast (DEP-01)

Analog: Phase 3 `ContextMenu` portal.

| Spec | Value |
|------|-------|
| File | `src/components/common/Toast.tsx` |
| Portal target | `document.body` |
| Position | `fixed; top: 24px; left: 50%; transform: translateX(-50%)` |
| z-index | `1100` (menu is 1000) |
| Radius | `0` |
| Border | `1px solid #30383d` |
| Background | `#1a1f23` |
| Shadow | `0 8px 18px rgba(0, 0, 0, 0.25)` |
| Text | 12px / 400 mono (`colors.mono` / ui-monospace stack); color `#dfe6ea` |
| Copy | Exact: `Deploy (mock) started — graph would be pushed to Jetson` |
| role | `role="status"` + `aria-live="polite"` |
| Dismiss | 2500ms timer; click on toast dismisses; single instance (replace + restart timer) |
| Escape | Optional recommended; not required for acceptance |

**Host pattern (recommended):** Module-level or small Zustand-less event API is unnecessary — keep React state in `Toolbar` (or thin `ToastHost` in App):

```
const [toast, setToast] = useState<string | null>(null)
// Deploy: actions.deployMock(); setToast(LOCKED_COPY); restart timer via useEffect
// Render: toast && <Toast message={toast} onDismiss={() => setToast(null)} />
```

Alternatively export `showDeployToast` from a tiny `toastState` callback registry — prefer Toolbar-local state for fewer files (Claude discretion: Toolbar host is enough; App mount optional).

**Log vs toast copy:** Keep `actions.deployMock` log as `Deploy (mock) — graph would be pushed to Jetson` (unchanged). Toast uses the longer started wording from CONTEXT.

### Pattern 5: CSS additions

Append to `app.css` (no token file inventing):

- `.toast` — layout/chrome per UI-SPEC
- `.btn-rec-on` — Rec pressed chrome (fault family)

Do not restyle `.status-badge` (existing padding/colors stay).

## Current Code Insights (verified)

| File | Finding |
|------|---------|
| `runtimeStore.ts` | run/pause/resume/stop/estop/reset never touch `node.status` |
| `graphStore.ts` | Nodes have `status: 'idle'`; no bulk setter yet |
| `BlockNode.tsx` | Renders `.status-badge` with `statusColor[node.status]` — ready |
| `systemStore.ts` | `setRecording(on)` already sets strip On/Off + fault/idle |
| `StatusStrip.tsx` | Already maps `status.recording` — no change |
| `actions.deployMock` | Log only — toast is additional side effect |
| `Toolbar.tsx` | No Rec button; Deploy calls `actions.deployMock` only |
| `ContextMenu.tsx` | Portal + z-index 1000 precedent for Toast |
| `App.tsx` | Shell only — toast can live under Toolbar without App change |

## Open Questions (RESOLVED)

| # | Question | Resolution | Locked by |
|---|----------|------------|-----------|
| 1 | Bulk setter API name? | `setAllNodeStatuses(status: BlockStatus)` | UI-SPEC / CONTEXT discretion |
| 2 | Toast file location? | `src/components/common/Toast.tsx` | UI-SPEC |
| 3 | Does resume from Pause re-assert badges? | Yes — call `setAllNodeStatuses('running')` in `resume` | UI-SPEC interaction contract |
| 4 | Does Pause clear badges? | No — stay `'running'` | CONTEXT |
| 5 | Toast library? | None — hand-roll portal | CONTEXT (no new deps) |
| 6 | Rec placement? | After Stop, before Validate separator | CONTEXT / UI-SPEC |
| 7 | Toast duration / stacking? | 2500ms; single instance replace | CONTEXT / UI-SPEC |
| 8 | New test framework? | No — typecheck + build + browser | Project constraint + Nyquist Wave 0 |
| 9 | raiseFault badges? | Set all to `'idle'` (consistent with estop) | Claude discretion this research |
| 10 | Nodes added mid-run? | Remain idle until next Run | Acceptable; out of scope to auto-promote |

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | none — no Vitest/Jest; do not add. Playwright already in devDependencies for optional browser scripts only |
| Config file | none for unit tests |
| Quick run command | `npm run typecheck` |
| Full suite command | `npm run typecheck && npm run build` |
| Estimated runtime | ~30 seconds |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RT-01 | Run → all badges `running`; Stop/E-STOP/Reset → `idle`; Pause keeps `running` | typecheck + browser | `npm run typecheck` | ❌ Wave 0 (manual browser) |
| RT-02 | Rec toggles strip Recording On/Off; disabled when estopped/fault; pressed chrome when On | typecheck + browser | `npm run typecheck` | ❌ Wave 0 |
| DEP-01 | Deploy Mock shows toast + log; auto-dismiss ~2.5s; click dismiss; single instance | typecheck + browser | `npm run typecheck` | ❌ Wave 0 |
| Regression | Port wiring, palette drop, context menus, keyboard delete still work | browser | `npm run typecheck && npm run build` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `npm run typecheck`
- **Per wave / plan complete:** `npm run typecheck && npm run build`
- **Phase gate:** Full suite green + browser checklist before `/gsd:verify-work`
- **Max feedback latency:** 30 seconds for typecheck/build

### Browser acceptance checklist (phase gate)

1. Click Run → every visible block `.status-badge` shows `running` (green via statusColor).
2. Click Pause → RUNTIME shows PAUSED; badges still `running`.
3. Click Run again (resume) → RUNTIME RUNNING; badges still/re-asserted `running`.
4. Click Stop → all badges `idle`.
5. Run then E-STOP → badges `idle`; Reset → badges `idle`, system re-armed.
6. Click `○ Rec` → label becomes `● Rec`, strip Recording shows On (fault-level red light); click again → Off / `○ Rec`.
7. With E-STOP engaged, Rec and Deploy and Run are disabled.
8. Click Deploy Mock → log line `Deploy (mock) — graph would be pushed to Jetson` appears AND toast shows `Deploy (mock) started — graph would be pushed to Jetson`.
9. Toast auto-dismisses ~2.5s; clicking toast dismisses immediately; second Deploy while visible replaces/restarts (no stack).
10. Phase 1–3 regression: select/delete, wiring, palette drop, context menu still work.

**Preview note:** Prefer `npm run build && npm run preview -- --host 127.0.0.1 --port 4173` when the folder path contains `#` (Vite dev can break).

### Wave 0 Gaps

- [ ] No unit test framework — **do not add** (phase forbids new deps; match Phases 1–3).
- [ ] Wave 0 = document manual/browser gates only; automated verify remains `npm run typecheck` / `npm run build`.
- [ ] Framework install: **none**.
- [ ] Optional later (out of phase): Vitest for `setAllNodeStatuses` pure store tests — only if a future phase allows a runner.

*(Existing infrastructure does not cover RT/DEP behaviors; Nyquist sampling = typecheck + build + browser checklist.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | N/A — no auth |
| V3 Session Management | no | N/A |
| V4 Access Control | no | Single-user desktop mock UI |
| V5 Input Validation | partial | Toast/Rec copy is locked constants — no free-form user HTML |
| V6 Cryptography | no | N/A |
| V7 Error Handling | partial | Deploy mock always succeeds visually; no error toast this phase |
| V8 Data Protection | no | In-memory graph/status only |
| V14 Config | no | No secrets |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Toast message injection | Tampering | Use locked constant string; React text children — never `dangerouslySetInnerHTML` |
| Spoofed "deploy" implying real hardware | Spoofing | Keep "(mock)" in toast and log copy; no network call |
| Accidental Rec while faulted | Elevation (UX) | Disable Rec when estopped/fault (same as Run/Deploy) |
| Overlay click-jacking / stuck toast | Denial of Service (UX) | Auto-dismiss 2500ms + click-to-dismiss; single instance |
| npm supply-chain via new toast lib | Tampering | No new packages — T-4-SC |

## Sources

### Primary (HIGH confidence)

- Codebase: `runtimeStore.ts`, `graphStore.ts`, `systemStore.ts`, `actions.ts`, `Toolbar.tsx`, `StatusStrip.tsx`, `BlockNode.tsx`, `ContextMenu.tsx`, `App.tsx`, `tokens.ts`, `app.css`, `types/blocks.ts` (`BlockStatus`)
- `.planning/phases/04-runtime-feedback-deploy-polish/04-CONTEXT.md` — locked decisions
- `.planning/phases/04-runtime-feedback-deploy-polish/04-UI-SPEC.md` — visual/interaction contract
- `.planning/REQUIREMENTS.md` — RT-01, RT-02, DEP-01
- `.planning/ROADMAP.md` — Phase 4 success criteria
- Prior: `03-RESEARCH.md`, `03-01-PLAN.md`, `03-02-PLAN.md` (portal + no-deps patterns)
- [CITED: https://react.dev/reference/react-dom/createPortal] — portal overlays
- [CITED: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Roles/status_role] — `role="status"` / live regions
- [VERIFIED: package.json] — no Vitest/Jest; playwright present as optional browser tooling

### Secondary (MEDIUM confidence)

- Phase 3 ContextMenu dismiss timer / portal patterns as implementation analog for Toast

### Tertiary (LOW confidence)

- None material

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; versions from package.json
- Architecture: HIGH — maps onto existing store split; BlockNode already paints status
- Pitfalls: HIGH — pause-must-not-clear-badges; resume must re-assert; toast vs log copy differ

**Research date:** 2026-07-13
**Valid until:** 2026-08-12 (30 days — stable React/Zustand APIs; project-local patterns dominate)
