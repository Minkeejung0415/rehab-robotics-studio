# Phase 24: Rosbridge and Studio Mapping Workspace - Context

**Gathered:** 2026-08-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Operators manage the authoritative fleet mapping through stable, actionable device rows in a dedicated Studio Mapping Workspace tab. The Studio subscribes to `/rehab/model/catalog`, `/rehab/mapping/current`, `/esp/fleet/registry`, `/rehab/calibration/status`, and `/rehab/opensim/input_validity` via rosbridge. Operators draft per-device segment assignments locally, submit them via the `SetAssignment` service, then apply atomically via `ApplyMapping`. The backend mapping state is the single source of truth; browser state is draft-only. Does not include hardware promotion gate (Phase 25).

</domain>

<decisions>
## Implementation Decisions

### Tab and Shell (UI-01)
- **D-01:** Add a third tab `'mapping'` to `App.tsx` tab strip alongside `'diagram'` and `'panel'`. When active, renders `<MappingWorkspace />` at full height inside the existing workspace layout.
- **D-02:** `MappingWorkspace` lives at `rehab-robotics-studio/src/components/mapping/MappingWorkspace.tsx`. No sub-folder nesting beyond `mapping/`.

### Zustand Store (UI-01, UI-04)
- **D-03:** New store `rehab-robotics-studio/src/state/mappingStore.ts` using the existing `create` from zustand pattern. Holds all mapping UI state.
- **D-04:** Store shape:
  ```ts
  interface MappingRow {
    deviceId: string;           // canonical "esp32:aabbccddeeff"
    role: string;               // "master" | "slave" | "unknown"
    connectionState: string;    // from fleet registry: "connected" | "disconnected" | ...
    routeState: string;         // from fleet registry
    rateHz: number | null;
    dropCount: number;
    // from /rehab/mapping/current assignments:
    backendSegment: string;
    backendFrame: string;
    backendState: 'assigned' | 'not_used' | 'unassigned';
    // local draft (not yet submitted via SetAssignment):
    draftSegment: string | null;   // null = no local change
    draftFrame: string | null;
    draftNotUsed: boolean | null;  // null = no local change
    // computed row-level mapping status:
    mappingStatus: 'unassigned' | 'draft' | 'saved' | 'applied' | 'runtime_ready';
    // IK validity (from /rehab/opensim/input_validity):
    ikValid: boolean | null;
    // busy flag for per-row Identify:
    identifyBusy: boolean;
    identifyResult: string | null;
  }

  interface MappingStore {
    rows: Record<string, MappingRow>;           // keyed by deviceId
    catalogModelHash: string | null;
    catalogFrameList: Array<{path: string; name: string}>;
    catalogModelPath: string | null;
    mappingRevision: number;
    appliedRevision: number;
    mappingModelHash: string | null;
    applyStatus: 'idle' | 'applying' | 'error';
    applyError: string | null;
    // actions:
    updateFromFleetRegistry(devices: unknown[]): void;
    updateFromMappingCurrent(state: unknown): void;
    updateFromCatalog(catalog: unknown): void;
    updateInputValidity(validity: unknown): void;
    setDraftSegment(deviceId: string, segment: string, frame: string): void;
    setDraftNotUsed(deviceId: string, notUsed: boolean): void;
    setIdentifyBusy(deviceId: string, busy: boolean): void;
    setIdentifyResult(deviceId: string, result: string | null): void;
    setApplyStatus(status: 'idle' | 'applying' | 'error', error?: string | null): void;
    clearDraft(deviceId: string): void;
    clearAllDrafts(): void;
  }
  ```

### Row Identity and Lifecycle (UI-04)
- **D-05:** Rows are **never removed** from the store. A device discovered in the fleet registry that later goes offline keeps its row with `connectionState: 'disconnected'`. An "offline saved device" row (known from `/rehab/mapping/current` but not in the live fleet registry) also stays.
- **D-06:** Row `deviceId` is the canonical identity key. Rows are upserted, never replaced wholesale. `updateFromFleetRegistry` creates rows for new device_ids; `updateFromMappingCurrent` fills in backend assignment fields; neither clears the other's data.
- **D-07:** `mappingStatus` is computed per-row on each store update:
  - `runtime_ready` = backendState=="assigned" and appliedRevision==mappingRevision and ikValid==true
  - `applied` = backendState=="assigned" and appliedRevision==mappingRevision
  - `saved` = backendState!="unassigned" and draftSegment==null and draftNotUsed==null
  - `draft` = draftSegment!=null or draftNotUsed!=null
  - `unassigned` = backendState=="unassigned" and no draft

### Rosbridge Subscriptions (UI-01, UI-04)
- **D-08:** Extend `RosbridgeDataSource` constructor with new optional callbacks:
  ```ts
  onModelCatalog?: (catalog: ModelCatalogSnapshot) => void;
  onMappingCurrent?: (state: MappingCurrentSnapshot) => void;
  onFleetRegistry?: (registry: FleetRegistrySnapshot) => void;
  onCalibrationStatus?: (status: NCalibrationStatusSnapshot) => void;
  onInputValidity?: (validity: InputValiditySnapshot) => void;
  ```
  All added at the end of the constructor to preserve existing parameter order.
- **D-09:** New subscription topics added to the `subscriptions` array in `socket.onopen`:
  - `['/rehab/model/catalog', 'std_msgs/msg/String']`
  - `['/rehab/mapping/current', 'std_msgs/msg/String']`
  - `['/esp/fleet/registry', 'std_msgs/msg/String']` (already published by backend; Studio adds its own subscription)
  - `['/rehab/calibration/status', 'std_msgs/msg/String']`
  - `['/rehab/opensim/input_validity', 'std_msgs/msg/String']`
- **D-10:** Parse and dispatch in `handleMessage()` with lightweight guard functions (`parseMappingCurrent`, `parseFleetRegistry`, `parseModelCatalog`, `parseNCalibrationStatus`, `parseInputValidity`). Invalid payloads silently drop — never throw.

### Rosbridge Service Calls (UI-02, UI-03)
- **D-11:** Add three new service call methods to `RosbridgeDataSource`:
  - `callSetAssignment(deviceId, segment, frame, state)`: calls `/rehab/mapping/set_assignment`, type `rehab_robotics_interfaces/srv/SetAssignment`. Returns `{success, outcome, detail}`.
  - `callApplyMapping(expectedRevision)`: calls `/rehab/mapping/apply`, type `rehab_robotics_interfaces/srv/ApplyMapping`. Returns `{success, outcome, appliedRevision, detail}`.
  - `callResetMapping(modelHash)`: calls `/rehab/mapping/reset`, type `rehab_robotics_interfaces/srv/ResetMapping`. Returns `{success, outcome}`.
  - (GetMappingState is not needed for UI; Studio reads state from the `/rehab/mapping/current` subscription.)
- **D-12:** Export these from `appDataSource.ts` as `callMappingSetAssignment`, `callMappingApply`, `callMappingReset` — same pattern as `setHardwareRecording`.

### Draft-to-Apply Flow (UI-03)
- **D-13:** Draft state is **local-only** (`draftSegment`/`draftNotUsed` in mappingStore). SetAssignment is called when the operator clicks a **per-row "Save" button** (not on every selector change). This prevents flooding the backend with calls on every keystroke and makes the Draft→Saved transition explicit and observable.
- **D-14:** On per-row "Save":
  1. Call `callMappingSetAssignment(deviceId, segment, frame, state)`.
  2. If `outcome == "ok"` → `clearDraft(deviceId)` (draft cleared; row shows Saved based on backend data flowing through the subscription).
  3. If `outcome != "ok"` → show the `detail` as a per-row error; draft remains.
- **D-15:** On "Apply" button click:
  1. `setApplyStatus('applying')`.
  2. Call `callMappingApply(mappingRevision)` (current revision from store).
  3. Outcome `"applied"` → `setApplyStatus('idle')`, `clearAllDrafts()`. Backend will re-publish `/rehab/mapping/current` with updated `applied_revision`.
  4. Outcome `"stale_revision"` → show error: "Mapping changed since last refresh — refresh and retry".
  5. Outcome `"recording_active"` or `"calibration_active"` → show interlock message.
  6. Any other outcome or timeout → `setApplyStatus('error', detail)`.
- **D-16:** Segment selector is a `<select>` populated from `catalogFrameList` (from `mappingStore`). An empty entry labeled "— Select segment —" represents `unassigned`. A separate "Not used" checkbox sets `draftNotUsed=true` and clears `draftSegment`. If `catalogFrameList` is empty, the selector shows "Model not loaded" and is disabled.

### Per-Row Identify (UI-02)
- **D-17:** Each row has a "Identify" button that calls the existing `IdentifyDevice` service (same path used in Phase 20/21) via `rosbridgeDataSource.callIdentifyDevice(deviceId)`. This reuses the existing IdentifyDevice service call infrastructure on `RosbridgeDataSource` if it exists, or adds a new `callIdentifyDevice(deviceId, timeoutMs)` method following the same `callService` pattern.
- **D-18:** `setIdentifyBusy(deviceId, true)` while in flight; `setIdentifyResult(deviceId, outcome)` on completion. Outcome is shown inline in the row for 5 s, then cleared.

### State Badges (UI-03)
- **D-19:** Overall mapping panel header badge:
  - **No model**: catalog not loaded
  - **Draft**: any row has `mappingStatus=="draft"`
  - **Saved**: no drafts, `mappingRevision > appliedRevision`
  - **Applied**: `appliedRevision == mappingRevision` and all assigned rows are applied
  - **Runtime Ready**: Applied + all assigned devices have `ikValid==true`
- **D-20:** Per-row badge displayed in a "Status" column. Color coding: draft=amber, saved=blue, applied=green, runtime_ready=bright-green, unassigned=gray.

### Conflict Feedback (UI-03)
- **D-21:** Duplicate segment detection is **local** (client-side): if two rows have the same `draftSegment` (or same saved `backendSegment` after clearing draft), show an inline warning. This is immediate feedback before Save.
- **D-22:** Backend validation errors (from SetAssignment `outcome != "ok"` or ApplyMapping errors) are displayed as per-row or panel-level error messages from the `detail` field.

### Reload / Reconnect Safety (UI-04)
- **D-23:** On rosbridge reconnect (`onConnectionChange(true)`):
  1. Do NOT clear `mappingStore.rows` — preserve row identity.
  2. Re-subscribe normally; the latched `/rehab/mapping/current` topic will replay the last state.
  3. `updateFromMappingCurrent` is idempotent: fields are overwritten from backend, drafts remain.
- **D-24:** On rosbridge disconnect (`onConnectionChange(false)`):
  1. Set all rows' `connectionState` to `'disconnected'`.
  2. Rows remain visible with "Offline" badge.
  3. Do NOT clear `draftAssignments` — operator's unsaved work is preserved.

### Wire-up in appDataSource.ts
- **D-25:** `rosbridgeDataSource` constructor call in `appDataSource.ts` extended with the new callbacks:
  ```ts
  onModelCatalog: (catalog) => useMappingStore.getState().updateFromCatalog(catalog),
  onMappingCurrent: (state) => useMappingStore.getState().updateFromMappingCurrent(state),
  onFleetRegistry: (registry) => useMappingStore.getState().updateFromFleetRegistry(registry.devices ?? []),
  onCalibrationStatus: (status) => { /* store calibration interlock state in mappingStore or systemStore */ },
  onInputValidity: (validity) => useMappingStore.getState().updateInputValidity(validity),
  ```

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Studio Codebase
- `rehab-robotics-studio/src/App.tsx` — tab strip to extend with Mapping tab
- `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` — extend with new subscriptions + service calls
- `rehab-robotics-studio/src/data/appDataSource.ts` — wiring singleton to extend
- `rehab-robotics-studio/src/state/systemStore.ts` — Zustand store pattern to follow
- `rehab-robotics-studio/src/state/runtimeStore.ts` — Zustand store pattern to follow
- `rehab-robotics-studio/src/components/dashboard/HealthPanel.tsx` — component pattern to follow

### Backend Contracts
- `backend/rehab_robotics_bridge/mapping_node.py` — service names, response fields, `/rehab/mapping/current` schema
- `backend/rehab_robotics_bridge/model_catalog_node.py` — `/rehab/model/catalog` schema
- `backend/rehab_robotics_bridge/fleet_bridge_node.py` — `/esp/fleet/registry` schema
- `rehab_robotics_interfaces/srv/SetAssignment.srv` — request: `{device_id, segment, frame, state}`; response: `{outcome, detail}`
- `rehab_robotics_interfaces/srv/ApplyMapping.srv` — request: `{expected_revision}`; response: `{outcome, applied_revision, detail}`
- `rehab_robotics_interfaces/srv/ResetMapping.srv` — request: `{model_hash}`; response: `{outcome}`
- `rehab_robotics_interfaces/srv/GetMappingState.srv` — response: `{state_json}` (not needed for UI)

### Requirements
- `.planning/REQUIREMENTS.md` §UI-01–04

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Patterns
- `callService()` on `RosbridgeDataSource` — generic rosbridge service call with generation-safe timeout; follow for all new service calls.
- `parseOpenSimStatus()` — guard function pattern for safe JSON parsing with field validation; follow for `parseMappingCurrent`, `parseFleetRegistry`, `parseModelCatalog`.
- `create<T>()` from zustand with typed interface — follow `systemStore.ts` for `mappingStore.ts`.
- `appDataSource.ts` exported function pattern — follow `setHardwareRecording` for `callMappingSetAssignment`, `callMappingApply`, `callMappingReset`.

### Integration Points
- `RosbridgeDataSource` constructor has 11 optional callbacks — append new mapping callbacks at positions 12–16.
- `appDataSource.ts` line 17 instantiates `rosbridgeDataSource` — add 5 new callbacks here.
- `App.tsx` `WorkspaceTab` type and tab strip — add `'mapping'` case.
- No existing `useMappingStore` import anywhere — safe to add new file.

### Existing Identify Infrastructure
- Check `RosbridgeDataSource` for an existing `callIdentifyDevice` method. If absent, add it following the same `callService` pattern with service `/rehab/identify/device`, type `rehab_robotics_interfaces/srv/IdentifyDevice`.

</code_context>

<specifics>
## Specific Ideas

- Per-row Identify result clears after 5 s using `setTimeout` in the store action (same pattern as Toast component).
- `catalogFrameList` should be displayed as `{name}` in the selector but `{path}` is sent to SetAssignment as `frame`.
- The fleet registry `/esp/fleet/registry` topic publishes the full devices list on any change — parse the `devices` array. Device id is under `device_id` field (canonical `esp32:...` form).
- `/rehab/mapping/current` includes `assignments` as a dict keyed by `device_id`, each with `{segment, frame, state}`. Also includes `revision` and `applied_revision`.
- `/rehab/calibration/status` JSON has `{state: "capturing"|"calibrated"|"uncalibrated", revision, model_hash}` — only needed to show whether Apply is interlocked; can feed a read-only `calibrationInterlocked: boolean` in mappingStore.
- `/rehab/opensim/input_validity` JSON has per-device validity flags — parse `{device_validities: {device_id: bool}}` for the `ikValid` field on each row.

</specifics>

<deferred>
## Deferred Ideas

- Hardware promotion gate (Phase 25).
- Model catalog load via a ROS service (currently only published by model_catalog_node on startup).
- Drag-and-drop segment reordering.
- Export/import mapping JSON from the Studio.
- Offline-mode map editing (no rosbridge connection).

</deferred>

---

*Phase: 24-rosbridge-and-studio-mapping-workspace*
*Context gathered: 2026-08-05*
