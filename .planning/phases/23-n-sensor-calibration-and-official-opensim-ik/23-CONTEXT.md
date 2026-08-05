# Phase 23: N-Sensor Calibration and Official OpenSim IK - Context

**Gathered:** 2026-08-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Applied mappings drive provenance-bound calibration and valid synchronized N-sensor OpenSim IK solves. The opensim_node subscribes to `/rehab/mapping/current`, builds MAC-keyed subscriptions for every assigned device, manages calibration artifacts tied to exact model+revision identity, enforces sync-skew bounds, and gates joint-state publication on all-valid-fresh inputs. Does not include the Studio mapping UI (Phase 24) or hardware promotion gate (Phase 25).

</domain>

<decisions>
## Implementation Decisions

### Subscription Lifecycle (IK-01)
- **D-01:** On each `/rehab/mapping/current` update, `opensim_node` compares the incoming device-to-Frame assignment list against the active subscription dict. Subscriptions for removed MACs are explicitly destroyed (`node.destroy_subscription(sub)`). New MACs get new subscribers to `/esp/raw/mac_<12hex>`. No orphan subscribers after remap.
- **D-02:** Input dict keyed by `device_id` (canonical `esp32:aabbccddeeff`). Each entry holds: subscription handle, latest frame payload, last_seen_ts, post_reconnect_fresh (bool). On subscription destroy, entry removed atomically under a threading.Lock.
- **D-03:** Deterministic input ordering: alphabetical sort by `device_id` string. This is the canonical order passed to the OpenSim solver. Order is locked on Apply and stored in calibration artifact.

### Calibration Artifacts (IK-02)
- **D-04:** Calibration artifact file: `~/.ros/rehab_robotics/calibration_<model_hash[:8]>_rev<applied_revision>.json`. Schema: `{schema_version: "calib.v1", model_hash, applied_revision, device_order: [device_id, ...], frame_assignments: {device_id: {segment, frame}}, solver_profile, calibrated_at_iso8601, reference_pose: {device_id: {qw,qx,qy,qz}}}`.
- **D-05:** Artifact is invalidated (and calibration state reset to `uncalibrated`) when: model_hash changes, applied_revision changes, or device-to-Frame assignment set changes. Detection via comparing current mapping state against loaded artifact.
- **D-06:** Calibration capture collects reference poses (one quaternion per assigned device) at the moment the operator triggers capture. Stored in artifact. The calibration service (`/rehab/calibration/capture`) already exists or is created here; it publishes `/rehab/calibration/status` (String JSON: `{state: "capturing"|"calibrated"|"uncalibrated", revision, model_hash}`).

### Sync-Skew Enforcement (IK-03)
- **D-07:** `sync_skew_ms` ROS param (default 50). Each IK solve cycle checks `abs(device_ts - reference_ts) <= sync_skew_ms` for all required inputs. Reference timestamp is the median of all input timestamps in the current batch.
- **D-08:** If any required input exceeds skew bound or `post_reconnect_fresh == False` → suppress IK output for that cycle. Acquisition and recording continue unaffected. `/rehab/opensim/input_validity` (String JSON) published each cycle with per-device validity flags.
- **D-09:** `post_reconnect_fresh` set to `False` on fleet registry reconnect event; set to `True` on first frame received after reconnect.

### IK Engine (IK-04)
- **D-10:** Existing `opensim_orientation_ik.py` adapter is reused. It already accepts a list of (frame_path, quaternion) pairs. Phase 23 wires it to receive the mapped N-sensor inputs in deterministic order from D-03.
- **D-11:** IK output topic `/rehab/opensim/joint_states` (existing) extended with metadata: `{mapping_revision, calibration_identity (calib artifact filename or null), input_validity_mask, solver_status, visualizer_provenance}`.
- **D-12:** Solver profile from `solver_profile` ROS param (default `"lower_body"`). Passed through to artifact and IK adapter. Phase 22 deferred hard-block enforcement to Phase 23 — enforce here: Apply validation in mapping_node upgraded to hard-block `solver_insufficient` if required frame count not met for current profile.

### Node Architecture
- **D-13:** Extend `opensim_node.py` (not a new node). New responsibilities added: subscribe to `/rehab/mapping/current`, manage N-sensor input subscriptions, load/validate calibration artifact, enforce skew gate, publish `/rehab/calibration/status` and `/rehab/opensim/input_validity`.
- **D-14:** All subscription management under `self._input_lock = threading.Lock()`. Remap is safe to call from ROS callback thread.

### Claude's Discretion
- Exact `/rehab/calibration/capture` service request/response fields (suggest: empty request → {outcome: "captured"|"no_mapping"|"already_capturing", artifact_path}).
- Whether `CalibrateMapping.srv` is a new interface or reuses `std_srvs/Trigger`.
- Whether `/rehab/opensim/input_validity` carries per-device skew values or just bool validity mask per device.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### OpenSim IK Engine
- `backend/rehab_robotics_bridge/opensim_orientation_ik.py` — existing IK solver to wire
- `backend/rehab_robotics_bridge/opensim_node.py` — node to extend
- `backend/rehab_robotics_bridge/opensim_adapter.py` — OpenSim Python API patterns
- `docs/opensim-ik-contracts.md` — IK output contracts (do not violate)

### Mapping Integration
- `backend/rehab_robotics_bridge/mapping_node.py` — `/rehab/mapping/current` publisher (Phase 22)
- `.planning/phases/22-model-catalog-mapping-store-and-transactional-contracts/22-CONTEXT.md` — mapping decisions D-06 through D-20
- `.planning/phases/22-model-catalog-mapping-store-and-transactional-contracts/22-05-SUMMARY.md` — test patterns

### Fleet Events
- `backend/rehab_robotics_bridge/fleet_bridge_node.py` — `/esp/fleet/registry` for reconnect events
- `.planning/phases/21-n-route-relay-and-canonical-ros-fleet/21-CONTEXT.md` — device_id canonical form

### Requirements
- `.planning/REQUIREMENTS.md` §IK-01–04

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `opensim_orientation_ik.py` — accepts `[(frame_path, (qw,qx,qy,qz)), ...]` list; returns joint angles dict; use as-is.
- `opensim_node.py` — existing single-sensor node; extend rather than rewrite.
- `test_fleet_bridge.py: _install_ros_stubs()` — reuse for opensim_node extension tests.

### Established Patterns
- Subscription dict pattern: `self._mac_subs: dict[str, Subscription]` managed under `threading.Lock` — mirrors `_active_writers` in fleet_bridge_node.
- Artifact atomic write: same `tmp + os.replace()` as mapping_node.py.
- Service handler: `def _on_calibrate(self, req, res): ...; return res`.

### Integration Points
- `opensim_node` subscribes to `/rehab/mapping/current` (from mapping_node).
- On mapping update: destroy old MAC subs, create new MAC subs → deterministic N-input routing.
- `/rehab/calibration/status` feeds mapping_node Apply interlock (D-15 Phase 22).
- `/rehab/opensim/joint_states` extended with new metadata fields.

</code_context>

<specifics>
## Specific Ideas

- IK output must carry `mapping_revision` and `calibration_identity` so visualizer can trace provenance (IK-04).
- `post_reconnect_fresh` guard prevents stale-at-startup solves without requiring explicit operator reset.
- Calibration artifact filename encodes model_hash prefix + revision for human-readable traceability.

</specifics>

<deferred>
## Deferred Ideas

- Studio mapping workspace (segment selectors, Draft/Saved/Applied states) — Phase 24.
- Hardware promotion gate — Phase 25.
- Partial-sensor IK (degraded profile) — future milestone.

</deferred>

---

*Phase: 23-n-sensor-calibration-and-official-opensim-ik*
*Context gathered: 2026-08-05*
