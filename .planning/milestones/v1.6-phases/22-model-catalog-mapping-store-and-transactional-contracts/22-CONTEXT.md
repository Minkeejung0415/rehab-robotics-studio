# Phase 22: Model Catalog, Mapping Store, and Transactional Contracts - Context

**Gathered:** 2026-08-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Operators can create, save, restore, and atomically apply a valid mapping that assigns each known fleet device to an exact non-Ground segment Frame in the loaded OpenSim model, persisted under a content-addressed (SHA-256) model identity with revision and atomicity contracts. Does not include N-sensor calibration, IK solving, or UI (Phases 23–24). Backend and ROS services only.

</domain>

<decisions>
## Implementation Decisions

### Model Identification
- **D-01:** The loaded `.osim` model is identified by SHA-256 hash of its raw bytes (not filename or path). Hash is computed at load time by `model_catalog_node.py`.
- **D-02:** A new `model_catalog_node.py` reads the `opensim_model_path` ROS parameter, computes the hash, enumerates compatible Frames, and publishes `/rehab/model/catalog` (JSON: `model_hash`, `model_path`, `frame_list`). It does not duplicate opensim_node's solve responsibilities.
- **D-03:** Compatible Frames are non-Ground `PhysicalFrame` objects from the model enumerated via the OpenSim Python API, following the pattern in `opensim_adapter.py`. Frame list contains `{segment, frame}` pairs. Frames that are not a `Body` or `PhysicalOffsetFrame` with a compatible attachment point are excluded.

### Frame Validation
- **D-04:** Missing, ambiguous, or unsupported Frame requests fail closed — service returns `invalid_frame` outcome with the reason string. No fuzzy matching. No source model mutation.
- **D-05:** Assignment choices are validated against the frame_list at the time of SetAssignment and again at Apply. A stale frame (model was swapped between SetAssignment and Apply) causes Apply to fail with `model_changed`.

### Mapping Persistence
- **D-06:** Mapping store persisted as JSON at `~/.ros/rehab_robotics/mapping_store.json` (created if missing). Schema version `map.v1`. Contents: `{schema_version, model_hash, revision, assignments: {device_id: {segment, frame, state}}, applied_revision, backup_revision}`.
- **D-07:** Atomic write via temp file + `os.replace()`. On write, previous file backed up to `mapping_store.json.bak`. Corruption recovery: if main file is invalid JSON, load from `.bak`; if both corrupt, start fresh with revision 0.
- **D-08:** Each model_hash has its own revision counter (monotonic integer, starts at 1). Switching to a different model_hash resets to revision 0 for that hash (no cross-model revision aliasing).

### Assignment States
- **D-09:** Each known fleet device has one of three states: `assigned` (mapped to exactly one frame), `not_used` (explicit exclusion), or `unassigned` (no decision yet). Unassigned devices make the mapping incomplete and block Apply unless all active-session devices have a decision.
- **D-10:** Duplicate segment-frame assignments are rejected at SetAssignment time with `duplicate_frame` outcome. Unknown device IDs (not in current fleet registry) are accepted with a warning but remain `unassigned` by default until a fleet session confirms them.
- **D-11:** `mapping_node.py` publishes `/rehab/mapping/current` (JSON) whenever assignment state changes. This is the authoritative mapping state topic.

### Apply Contracts
- **D-12:** Apply validates the complete candidate: every device in the current fleet session has an `assigned` or `not_used` state; no duplicate frames; all frames exist in current frame_list; revision matches expected_revision parameter. Staged in memory before atomic JSON swap.
- **D-13:** Apply atomically swaps on success (persists `applied_revision = revision`). On any failure, previous `applied_revision` is preserved — no partial write. Returns `applied` or one of: `model_changed`, `revision_mismatch`, `incomplete`, `duplicate_frame`, `invalid_frame`, `blocked`.
- **D-14:** Revision mismatch: caller passes `expected_revision`; if stored `revision != expected_revision`, Apply returns `revision_mismatch` immediately without staging.

### Apply Interlock
- **D-15:** `mapping_node` subscribes to `/esp/recording/status` and `/rehab/calibration/status` (or equivalent). While `recording_active=True` or `calibration_active=True`, Apply returns `blocked` with explicit reason string. Does not stop or alter the active session.
- **D-16:** SetAssignment (draft edits) is NOT blocked during recording/calibration — only Apply is blocked.

### Reconnect Re-attach
- **D-17:** On fleet session bind (`/esp/fleet/registry` update or direct event from fleet_bridge_node), `mapping_node` checks whether the newly bound device_id is in the current mapping under the current model_hash + applied_revision. If yes → state remains `assigned` (auto-reattach). If a different device_id appears at a route previously mapped → it registers as `unassigned` in the current draft.
- **D-18:** `mapping_node` subscribes to `/esp/fleet/registry` to track fleet session events. No direct coupling to `fleet_bridge_node` internals.

### Solver Sufficiency
- **D-19:** MAP-02 solver-sufficiency check: the selected solver profile (from opensim_node param) defines the minimum required frames. Apply validates that at least the required frames are covered by `assigned` devices. Default profile: at least one device assigned to a lower-body segment Frame.
- **D-20:** Solver profile validation is best-effort for Phase 22 (warning in Apply response if profile not met, not a hard block). Phase 23 will harden this when the actual IK solver contracts are wired.

### Node Architecture
- **D-21:** New files: `backend/rehab_robotics_bridge/model_catalog_node.py` and `backend/rehab_robotics_bridge/mapping_node.py`. New ROS services (in `rehab_robotics_interfaces`): `SetAssignment.srv`, `ApplyMapping.srv`, `GetMappingState.srv`, `ResetMapping.srv`. No changes to `opensim_node.py`, `fleet_bridge_node.py`, or `esp32_bridge_node.py` data paths.
- **D-22:** `model_catalog_node` and `mapping_node` run as separate ROS nodes (launched alongside existing nodes). They can share the same Python process via a combined launch entry if resource-constrained, but are architecturally independent.

### Claude's Discretion
- Exact JSON field order and optional fields in `/rehab/model/catalog` and `/rehab/mapping/current` topic payloads.
- The precise PhysicalFrame subtype filter for "compatible IMU frames" — researcher/planner should enumerate what OpenSim 4.5.2 exposes and pick the tightest safe filter.
- Whether `mapping_node` listens to fleet events via the registry JSON topic or via a dedicated internal service — either is acceptable provided D-17's semantics hold.
- Test strategy: deterministic offline tests using mock ROS stubs (same pattern as `test_fleet_bridge.py`) are preferred; no live OpenSim or hardware required for unit tests.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### OpenSim Integration
- `backend/rehab_robotics_bridge/opensim_adapter.py` — existing OpenSim Python API wrapper; Frame/Body enumeration pattern
- `backend/rehab_robotics_bridge/opensim_node.py` — existing OpenSim IK node; model loading pattern
- `examples/opensim_quaternion_demo.osim` — reference model for Frame enumeration tests
- `docs/opensim-ik-contracts.md` — OpenSim IK contracts (do not violate)

### Fleet Identity
- `backend/rehab_robotics_bridge/fleet_bridge_node.py` — fleet registry and session bind events; `/esp/fleet/registry` topic
- `.planning/phases/21-n-route-relay-and-canonical-ros-fleet/21-CONTEXT.md` — fleet architecture decisions (alias, registry schema, device_id canonical form)
- `.planning/phases/21-n-route-relay-and-canonical-ros-fleet/21-05-SUMMARY.md` — live session loop summary

### Requirements
- `.planning/REQUIREMENTS.md` §MODEL-01–03, MAP-01–06 — all 9 requirements for this phase
- `.planning/ROADMAP.md` §Phase 22 — success criteria

### Existing Test Patterns
- `backend/test/test_fleet_bridge.py` — ROS stub + offline test pattern to replicate for mapping_node tests

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `opensim_adapter.py` — `opensim.Model(path)` loading; `getBodySet()`, `getFrameSet()` enumeration patterns to reuse for `enumerate_compatible_frames()`.
- `fleet_bridge_node.py: FleetRegistryStore` — registry JSON schema reference; subscribe to `/esp/fleet/registry` for device events.
- `backend/test/test_fleet_bridge.py: _install_ros_stubs()` — ROS stub loader for mapping_node tests (reuse without modification).

### Established Patterns
- SHA-256 of file bytes: `hashlib.sha256(Path(model_path).read_bytes()).hexdigest()` — use this verbatim.
- Atomic JSON write: `tmp = path.with_suffix('.tmp'); tmp.write_text(json.dumps(data)); tmp.replace(path)` — matches existing config patterns.
- ROS service handler signature: `def handler(self, request, response): ... return response` — match esp32_bridge_node pattern.
- Device ID canonical form: `esp32:aabbccddeeff` (12 hex lower, colon prefix) — Phase 20/21 decision; mapping_node must enforce.

### Integration Points
- `mapping_node` subscribes to `/esp/fleet/registry` (String/JSON) and `/rehab/model/catalog` (new, from model_catalog_node) — no internal imports across nodes.
- `mapping_node` publishes `/rehab/mapping/current` (String/JSON) consumed by Phase 24 Studio panel (rosbridge).
- `model_catalog_node` publishes `/rehab/model/catalog` consumed by `mapping_node` and Phase 24 UI.
- Both nodes added to `backend/launch/rehab_robotics.launch.py`.

</code_context>

<specifics>
## Specific Ideas

- The backend is authoritative for exact-model-hash mapping revisions; browser state is draft-only (from STATE.md architectural decision).
- Apply is whole-candidate, optimistic-revision, atomic, and interlocked with capture/recording/finalization (existing milestone-level decision).
- Phase 22 proves OpenSim 4.5.2 runtime Frame behavior or requires model-authored Frames (from STATE.md concern) — `enumerate_compatible_frames()` is the answer.

</specifics>

<deferred>
## Deferred Ideas

- N-sensor calibration using assigned frames — Phase 23.
- Studio UI mapping panel (segment selectors, Draft/Saved/Applied states) — Phase 24.
- Explicit "forget device" from fleet registry — later than Phase 22.
- Solver profile hardening (hard block on insufficient assignments) — Phase 23 when IK contracts are wired.
- Full hardware evidence for capacity and promotion — Phase 25.

</deferred>

---

*Phase: 22-model-catalog-mapping-store-and-transactional-contracts*
*Context gathered: 2026-08-05*
