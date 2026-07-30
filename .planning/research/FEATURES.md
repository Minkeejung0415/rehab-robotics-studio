# Feature Research: Multi-Sensor ESP-NOW / OpenSim Bone Mapping

**Domain:** Operator-controlled wearable IMU discovery, physical identification, and model-aware routing for a rehabilitation robotics lab
**Milestone:** v1.6 Multi-Sensor Bone Mapping
**Researched:** 2026-07-30
**Confidence:** HIGH for operator workflow and OpenSense mapping semantics; MEDIUM for exact Identify acknowledgement and generated-frame details until the plugin protocol and target hardware are exercised

## Recommended Product Contract

Treat the mapping panel as a configuration and preflight surface for a lab instrument, not as a generic IoT device dashboard. Its job is to answer five questions without ambiguity:

1. Which physical ESPs does the Master currently see?
2. Which stable hardware identity belongs to the unit in the operator's hand?
3. Which loaded-model body segment is each included unit attached to?
4. Is the saved mapping valid, applied, and currently ready for calibration/IK?
5. If it is not ready, exactly which device, model reference, route, or command failed?

The recommended operator flow is:

1. Load an `.osim` model. Studio displays the exact model name/path, content fingerprint, and model-derived body segments.
2. Power the Master and Slaves. A stable row appears for the Master and every ESP-NOW Slave; rows do not reorder or disappear during a dropout.
3. Use **Identify** on one online row at a time. The selected physical unit blinks for a short bounded interval, and Studio reports confirmed, timed out, unsupported, or offline.
4. For every discovered device, deliberately choose a model body or **Not used**. Plain **Unassigned** remains an incomplete state.
5. Review preflight. Duplicate bodies, unresolved model references, missing routes, invalid identities, and undecided devices are named before Apply.
6. Use the primary **Save & Apply** action. The backend revalidates the full mapping and either activates one new revision atomically or keeps the previous applied revision.
7. Calibrate only when every included sensor is online, streaming a fresh valid quaternion, time-synchronized, and routed to the exact applied model frame.
8. On a temporary dropout, preserve the MAC-to-segment mapping but stop new calibrated IK output. On return, reattach the same MAC automatically and resume only after fresh input passes readiness checks.

Three states must remain visibly distinct:

- **Draft:** what the operator is editing.
- **Saved:** a versioned mapping persisted for the exact model fingerprint.
- **Applied:** the backend-confirmed revision currently controlling ROS/OpenSim routing.

Editing or saving a draft must not silently change live routing. An Apply failure must not leave half of the sensors on the new mapping.

## Feature Landscape

### Table Stakes (Users Expect These)

Missing any P1 item below makes multi-sensor placement ambiguous, non-reproducible, or unsafe to use for calibration and IK.

| Feature | Requirement-ready behavior | Why expected | Complexity | Dependencies / safe default |
|---------|----------------------------|--------------|------------|-----------------------------|
| Master plus all Slave discovery | Maintain one device registry containing the assignable Master and every Slave reported by the ESP-NOW acquisition path. A row reports role, canonical MAC, online/last-seen state, stream readiness, sync, quaternion/IMU health, rate, and actionable error. | The Master is also a wearable sensor; a two-row `master/slave` abstraction loses the actual topology. | HIGH | Requires a versioned multi-device status schema from firmware/bridge through rosbridge. Master first; Slaves sorted by canonical MAC. |
| Discovery separate from stream readiness | Represent at least `seen_by_master`, `transport_ready`, `ros_topic_ready`, and `orientation_fresh` as separate facts. A discovered Slave may be saved/mapped but cannot make calibration ready until its data route exists. | Current firmware can see several ESP-NOW peers while the relay/ROS launch still provisions only one Slave stream. Calling such a device “online” would be misleading. | HIGH | Safe state is `DISCOVERED / NOT ROUTED`, not a generic green Online badge. |
| Full stable hardware identity | Use one canonical six-byte hardware MAC as the persistence key and show it in every device row and error. Normalize case/separators at the boundary. Never use DHCP IP, ESP-NOW slot, discovery order, ROS role, or the current 32-bit `slave_id` as identity. | IPs and slots change; a truncated ID can collide. The mapping must survive reconnect and route commands to the intended unit. | MEDIUM | Expose the full Master identity too. Keep current transport MAC separately if it can differ from the persisted hardware MAC. Reject missing, malformed, or duplicate identities. |
| Stable, non-jumping device rows | Once known in the current model/session, retain a row through stale/offline transitions and on reconnect; update it in place by MAC. Do not delete a saved row merely because firmware's live peer timeout expires. | The operator may be fastening and power-cycling sensors while mapping. Reordering makes physical placement error-prone. | MEDIUM | Offline rows remain visible and editable. Purge is an explicit mapping-management action, never a liveness side effect. |
| Targeted Identify action | **Identify** addresses exactly one canonical MAC. Only online/routable devices enable the action. The button becomes busy, prevents a second concurrent Identify, and reports device-confirmed success or a reason-coded timeout/rejection. The LED returns to its normal state automatically. | Printed MACs are hard to match to strapped devices. A temporary physical signal is standard lab setup behavior. | MEDIUM/HIGH | Use the firmware/plugin's bounded blink command; default to about 3 seconds only if duration is configurable. Never broadcast Identify. ESP-NOW MAC-layer send success alone is not application confirmation. |
| Model load and content identity | Load the selected `.osim` through OpenSim, compute a stable content fingerprint, and expose load state, path/name, and exact fingerprint. A parse/load failure leaves the mapping non-applicable. | Persistence must follow the actual model, not an ambiguous filename. Same path with changed contents may have a different body set. | MEDIUM | Recommended model key: SHA-256 of file bytes plus a mapping schema version; keep path/name as display metadata. |
| Model-derived segment vocabulary | Populate choices from the loaded model's `BodySet` using stable component paths such as `/bodyset/femur_r`; exclude Ground and never ship a hard-coded pelvis/femur/tibia list. Display friendly names but persist exact component paths. | OpenSense associates sensors with model body segments/IMU Frames. Custom models must work without a GUI release. | MEDIUM | Re-introspect on model reload. Empty BodySet or duplicate/unresolvable component paths is a blocking model error. |
| Deterministic model IMU-frame resolution | For an assigned body, prefer an existing exact `<body>_imu` Frame attached to that body. If none exists, create a deterministic runtime-only identity-offset IMU Frame before `initSystem`, clearly mark it as generated, and never rewrite the user's `.osim` file silently. Ambiguity or a frame attached to the wrong body blocks Apply. | The UI vocabulary is body segments, while OpenSense/IK consumes model Frames and orientation-table labels. | HIGH | Calibration estimates mounting rotation. A generated frame's translation is at the body origin, which is adequate for orientation IK but should be visible because it affects triad placement. |
| Explicit include / not-used decision | Each discovered or restored device is either assigned to one body, explicitly **Not used**, or still **Unassigned**. Unassigned is incomplete; Not used is a deliberate valid exclusion. | Requiring every powered spare sensor to participate is impractical, while treating an untouched selector as exclusion hides mistakes. | LOW | New devices default to Unassigned. A saved excluded device restores as Not used. |
| One sensor per segment validation | The same model body/component path may appear at most once among included devices. Both conflicting rows are marked and Apply is blocked; there is no first/last-wins behavior. | Two orientation sources for one model segment are ambiguous for calibration and IK. | LOW | Validate continuously in Studio and authoritatively again in the backend. |
| Complete mapping and solver preflight | Apply is allowed only when a model is loaded, identities are valid, every device is assigned or Not used, included segments are unique/resolvable, at least one sensor is included, and the selected solver/profile accepts the sensor set. | A mapping can be structurally valid yet insufficient for the requested IK coordinates. | HIGH | Minimum sensor count is a solver/profile rule, not a hard-coded GUI number. The present knee workflow requires its expected femur/tibia observations until the solver is generalized. |
| Save, Apply, and Save & Apply semantics | **Save draft** persists without affecting routing. **Apply** activates a validated saved/draft revision. The primary action should be **Save & Apply**. UI always shows unsaved changes and whether saved revision equals applied revision. | Operators need offline preparation and must know what the running pipeline is actually using. | MEDIUM | Do not label a browser-only edit “saved” or “applied.” |
| Per-model durable persistence | Store a versioned mapping record keyed by model fingerprint, with canonical MAC, body component path, resolved/generated IMU frame, include/exclude decision, optional label, last-seen role, revision, and timestamps. Persist in the backend/project profile, not only browser `localStorage`. | The mapping controls ROS/OpenSim and must survive browser reload, app restart, and network loss consistently. | MEDIUM | Atomic write/rename; reject or quarantine corrupt/unknown schemas and remain explicitly unconfigured. Do not overwrite the prior good record on failed validation. |
| Exact restore and reconnect reattachment | Loading an exact model fingerprint restores its last saved draft. A returning device with the same canonical MAC updates the existing row and reattaches to its saved body automatically. A role/topology change is shown for review rather than silently discarded. | This is the practical value of stable identities: no remapping after routine power cycles. | MEDIUM | Restore mapping, not stale live health. Do not auto-apply a record to a changed model fingerprint. |
| Atomic backend Apply | The backend revalidates model fingerprint, registry, frame resolution, uniqueness, route topics, and mapping revision; builds replacement subscriptions/routes; then swaps the entire active mapping. Response returns an applied revision and per-device resolved topic/frame. | Client-only validation can race device/model changes; partial activation creates mixed biomechanics. | HIGH | On failure, leave the previous applied revision active and report the exact failed stage. Never advertise the draft as applied. |
| Quiescent apply boundary | Save remains available while acquiring. Apply is blocked during calibration capture and active SD recording/finalization; it never stops recording automatically. If calibrated IK is idle/live but not recording, applying a changed revision pauses output, clears calibration, applies atomically, and requires recalibration. | Mapping changes mid-capture or mid-session destroy provenance and can mix body labels. Recording independence must remain intact. | MEDIUM | No hot remap while recording. Show “Stop/finalize recording before applying mapping,” not a hidden forced stop. |
| Dynamic ROS/OpenSim routes by hardware identity | Each applied entry resolves to a unique, collision-free ROS IMU topic and exact OpenSim Frame. Topic/route names are derived from a sanitized hardware ID or authoritative registry ID, never `slave`, slot, or current IP. | The current fixed `/esp32/master/imu` and `/esp32/slave/imu` contract cannot represent several Slaves or stable reconnection. | HIGH | Publish the MAC and mapping revision in status/metadata even when the topic uses a safe compact token. Keep raw acquisition identity independent of body assignment. |
| Calibration/IK hard gate on applied readiness | Calibration requires the applied revision and every included sensor to be online, routed, synchronized, fresh, and quaternion-valid. New joint states stop immediately when any required input becomes stale/offline or the applied mapping changes. | A saved map is not proof that live observations exist. OpenSense assumes synchronized, processed orientations. | HIGH | Health continues publishing while blocked. Never replay last-good output with a current timestamp. |
| Offline and degraded behavior | A mapped sensor going stale/offline changes runtime state to `DEGRADED`/`WAITING_FOR_SENSOR`, names the MAC and segment, and suppresses new IK output. The mapping remains saved/applied. Reconnect flushes old input and waits for fresh monotonic, synchronized samples before readiness returns. | Operators need continuity of configuration without continuity of stale estimates. | MEDIUM | No implicit partial-sensor IK unless a separately validated solver profile declares it observable. |
| Calibration invalidation rules | Changing model fingerprint, included device set, MAC-to-body assignment, resolved frame, quaternion/frame convention, or solver profile invalidates calibration. A brief transport dropout of the same MAC under the same applied revision may retain calibration but cannot produce output while stale. | Mounting offsets belong to a specific model/mapping. Connectivity loss alone does not prove remounting, but a configuration change does. | MEDIUM | On reconnect, remind the operator to recalibrate if a sensor was physically moved. Never auto-calibrate. |
| Reason-coded, layered errors | Surface global mapping readiness and per-device errors separately. Distinguish identity invalid, ESP-NOW stale, transport unavailable, ROS topic missing, Identify unsupported/timeout, model load failure, segment/frame missing, duplicate segment, incomplete decision, persistence failure, Apply rejection, quaternion invalid, sync missing, and IK blocked. | “Pair waiting” or one red fault cannot guide a multi-device lab setup. | MEDIUM | Preserve last good applied mapping and logs. Error text includes MAC/segment but never secrets. |
| Deterministic local verification | Fixture tests cover arbitrary device order, Master assignment, 0/1/many Slaves, duplicate/truncated IDs, reconnect by MAC, stale retention, targeted Identify success/timeout, model body extraction, generated/existing frames, duplicate/incomplete validation, persistence corruption, changed model fingerprint, atomic Apply rollback, and offline IK gating. | Jetson/hardware availability is limited; most contract failures are deterministic. | HIGH | Include a fake registry and fake `.osim` models. Hardware acceptance separately verifies LED, full identity, multi-peer limits, and stream readiness. |

### Differentiators (Competitive Advantage)

These improve setup speed and experimental traceability after the table-stakes path is correct.

| Feature | Value proposition | Requirement-ready behavior | Complexity | Add when |
|---------|-------------------|----------------------------|------------|----------|
| Guided placement mode | Turns a dense device table into a repeatable instrumenting procedure. | Step through unresolved rows one at a time: Identify, attach, select body, confirm; show progress `n / total decided` and do not hide full MAC/status. | MEDIUM | After Identify and mapping state machines are stable. |
| One-screen readiness matrix | Lets an operator diagnose setup without reading ROS logs. | For each included MAC show ESP-NOW seen, data route, fresh quaternion, sync, body/frame, saved revision, applied revision, and calibration readiness with one failing reason per layer. | MEDIUM | P2 UI polish over authoritative backend states. |
| Placement labels and notes | Helps humans distinguish visually identical units without replacing stable identity. | Allow an optional label such as “Blue tape” or “Right shank strap”; always display MAC alongside it and persist label independently of body assignment. | LOW | After core persistence schema exists. |
| Model revision reconciliation | Reduces rework when a researcher edits or renames a model. | For a new fingerprint, offer a review-only migration when every saved body component path still exists uniquely; never auto-apply it. Produce added/removed/renamed-body differences. | MEDIUM/HIGH | Only after exact-fingerprint restore is proven. |
| Mapping provenance in session metadata | Makes later analysis reproducible. | Record model fingerprint, applied mapping revision, canonical MAC-to-body/frame entries, and calibration ID in ROS/session metadata without changing the reliable SD transport semantics. | MEDIUM | After applied revision is authoritative. |
| Import/export of mapping profiles | Supports moving a validated lab setup between workstations. | Export a versioned, human-readable profile with model fingerprint and no network secrets; import into review state and require revalidation/Apply. | MEDIUM | When more than one workstation needs the same setup. |
| Controlled preconfiguration with offline sensors | Lets a lab prepare a participant/model before all devices are powered. | Saved offline MAC rows can be assigned and validated structurally; runtime readiness remains Waiting until those exact devices return. | LOW/MEDIUM | Natural extension of saved/offline rows. |
| Mapping audit trail | Helps explain why a session's route changed. | Append who/when is unavailable locally, but always record timestamp, old/new revision, changed MAC-to-body entries, Apply result, and reason. Bound retention and allow export. | MEDIUM | After revisions and session metadata exist. |

### Anti-Features (Explicitly Do Not Build)

| Anti-feature | Why it seems attractive | Why problematic | Recommended alternative |
|--------------|-------------------------|-----------------|-------------------------|
| Identity by IP, DHCP order, ESP-NOW slot, or `slave1` | Easy to derive from the current launcher. | Every one can change across boots; the current start script already encounters nondeterministic DHCP order. | Persist the full canonical hardware MAC and keep network route as transient metadata. |
| Persisting the current 32-bit `slave_id` as MAC | The firmware already publishes it. | It is only the low 32 bits of `ESP.getEfuseMac()` and can collide; it cannot target a six-byte peer safely. | Expose and persist the full six-byte identity. |
| Auto-assigning bodies by discovery order or RSSI | Makes setup look automatic. | Power order and signal strength have no biomechanical meaning and can silently swap limbs. | Explicit Identify plus deliberate body selection. |
| Treating Master as controller-only | Matches the old pair UI. | The project explicitly uses the Master as an orientation source; excluding it loses a wearable sensor. | Put Master in the same assignment workflow with a role badge. |
| Broadcast “blink all” identification | Demonstrates that LEDs work. | Does not identify one physical unit and can confuse a strapped participant. | Target one MAC and serialize Identify requests. |
| Reporting ESP-NOW send callback as Identify success | The callback is readily available. | Espressif states that MAC-layer delivery does not guarantee application receipt. | Require device/application acknowledgement; otherwise report “sent, unconfirmed.” |
| Free-form arbitrary LED control | Appears flexible for diagnostics. | Creates persistent device state and firmware UI scope unrelated to mapping. | One bounded Identify command that auto-restores normal LED behavior. |
| Hard-coded anatomical segment list | Fast for the demo femur/tibia model. | Becomes stale or wrong for custom `.osim` files and violates the model-derived requirement. | Enumerate the loaded model's `BodySet` and persist component paths. |
| Silent `.osim` rewrite to add IMU frames | Avoids a compatibility warning. | Mutates research input, breaks fingerprints/reproducibility, and can damage hand-authored models. | Add deterministic runtime-only frames or provide an explicit separately saved derived model later. |
| Duplicate segment with an arbitrary winner | Allows Apply to proceed. | The chosen sensor may vary by object iteration/order and corrupt calibration. | Mark both conflicts and block Apply. |
| “Unassigned means ignored” | Reduces clicks. | An untouched selector becomes indistinguishable from a deliberate spare sensor. | Require explicit Not used. |
| LocalStorage-only mapping | Simple frontend implementation. | Different browsers or cleared storage disagree with the backend route; Apply state cannot be authoritative. | Backend/project-profile persistence with revisions and atomic writes. |
| Auto-applying mappings by filename only | Convenient after model reload. | Two different files can share a name/path, or a file can change in place. | Exact content fingerprint restore; review-only migration for changed models. |
| Hot mapping changes during recording/calibration | Fast correction of a setup mistake. | Produces mixed semantics inside one capture and may invalidate calibration while outputs continue. | Save draft; stop/finalize; Apply atomically; recalibrate. |
| Automatic partial-sensor IK after dropout | Keeps numbers on screen. | Requested coordinates may no longer be observable, yet the output can remain plausible. | Stop fresh output and report the missing MAC/segment unless a validated degraded profile exists. |
| Automatic recalibration or silent reuse after remapping | Makes reconnect look seamless. | Changes or misapplies the biomechanical reference without operator knowledge. | Preserve mapping across reconnect; invalidate calibration on mapping/model revision and require explicit capture. |
| Deleting offline devices automatically | Keeps the table short. | Erases saved placement during normal power cycling. | Retain known rows; provide explicit Forget only when not referenced by saved/applied mapping. |
| Generic Wi-Fi provisioning, OTA, battery fleet management, or cloud device accounts | Common in IoT dashboards. | Expands scope away from local ESP-NOW/OpenSim acquisition and adds security/operations burdens. | Limit v1.6 to discovery, identity, Identify, mapping, routing, and health. |

## State and Error Semantics

### Device state

Device liveness should be derived from authoritative timestamps/status, not inferred from whether a React row exists.

| State | Meaning | Operator actions |
|-------|---------|------------------|
| `DISCOVERED` | Master has a recent ESP-NOW status for this MAC, but a ROS orientation route is not ready. | Identify if command path is ready; assign/save; cannot calibrate. |
| `READY` | Identity valid, transport/ROS route ready, fresh valid orientation and sync present. | Identify, assign, and participate in Apply/calibration. |
| `STALE` | Previously live, but freshness threshold exceeded. | Mapping remains; Identify disabled if command reachability is unknown; IK gated. |
| `OFFLINE` | Backend has declared the device absent/disconnected. | Edit/save mapping; cannot Identify/calibrate. |
| `ERROR` | Identity collision/malformed status, route failure, or hardware health fault. | Show named reason and recovery guidance. |
| `NOT_USED` | Operator explicitly excluded this model/device combination. | Still show liveness and allow reassignment. |

Use firmware/backend timeout values as the authority. The current firmware regards Slave status as stale after 5 seconds; Studio should not invent a shorter conflicting offline timer. Hardware validation may tune the threshold, but the schema must publish the effective value.

### Mapping state

| State | Meaning | Allowed next actions |
|-------|---------|----------------------|
| `UNCONFIGURED` | No saved mapping for this model fingerprint. | Edit, Identify, Save. |
| `DRAFT_INCOMPLETE` | At least one device is undecided or required preflight data is unavailable. | Edit, Identify, Save draft; Apply disabled. |
| `DRAFT_CONFLICT` | Duplicate body, invalid identity, missing model/frame, or other blocking conflict. | Resolve conflict; Apply disabled. |
| `DRAFT_VALID` | Structurally valid and solver-compatible; live devices may still be offline. | Save, Apply, Save & Apply. |
| `SAVING` | Atomic persistence request in flight. | Disable duplicate save; do not change applied revision. |
| `APPLYING` | Backend is validating/building a replacement route. | Disable mapping edits and calibration; keep old applied revision authoritative until success. |
| `APPLIED_READY` | Saved/applied revisions match and all included live checks pass. | Calibrate or run IK. |
| `APPLIED_WAITING` | Mapping is applied but one or more included sensors are offline/unrouted/unfresh. | Fix named device path; mapping remains applied. |
| `APPLY_FAILED` | New draft was rejected; prior applied revision remains active if one existed. | Correct named cause and retry. |

### Error presentation

- A global banner answers whether mapping is **valid**, **saved**, **applied**, and **runtime ready**; these are four separate facts.
- Each row owns its identity, Identify, route, orientation, sync, and assignment errors.
- Error messages name canonical MAC and assigned body where applicable.
- Logs record transitions and Apply revision results, not every heartbeat.
- A transport reconnect must not clear a persistent Apply/model error.
- A malformed status/persistence payload is ignored safely and reported; it must not crash rosbridge acquisition.

## Feature Dependencies

```text
Firmware/bridge full-device registry
  (Master identity + full Slave MAC + last seen + role + health)
    -> stable Studio device rows
    -> targeted Identify by MAC
    -> transient route resolution per MAC

Loaded .osim model
    -> model content fingerprint
    -> BodySet component paths
    -> existing/generated IMU Frame resolution

Stable device registry + model-derived bodies
    -> explicit include/not-used decisions
    -> uniqueness/completeness/solver validation
    -> versioned per-model saved mapping
    -> atomic applied mapping revision

Applied revision + per-MAC ROS orientation routes
    -> fresh/synchronized readiness gate
    -> reference-pose calibration bound to mapping revision
    -> dynamic OpenSim orientation IK
    -> JointState/status/visualizer provenance

Same MAC reconnect + unchanged applied revision
    -> automatic row/route reattachment
    -> flush stale inputs
    -> resume readiness after fresh checks

Model or mapping revision change
    -> invalidate calibration
    -> suppress fresh IK
    -> require explicit recalibration
```

### Dependency Notes

- **Discovery is upstream of the GUI.** The current Master firmware already keeps up to six active Slave status slots keyed by the full ESP-NOW source MAC, but the backend collapses health to one fixed `slave`, the relay provisions one Slave, and Studio renders exactly two rows. A GUI-only phase cannot satisfy discovery.
- **Stable identity is upstream of persistence and commands.** The full canonical identity must be available before saving mappings or targeting Identify. Do not build persistence around the current truncated `slave_id`.
- **A discovered device is not necessarily a usable orientation input.** The registry must expose command reachability and streaming/ROS readiness independently.
- **Model bodies and OpenSim Frames are related but not interchangeable.** Operators select bodies; the backend must resolve or create the Frame label consumed by OpenSense/`OrientationsReference`.
- **Persistence precedes automatic reconnect.** Reattachment is a deterministic join of canonical MAC and exact model fingerprint, not a heuristic.
- **Apply precedes calibration.** Calibration artifacts must carry the applied mapping/model revision and are invalid under a different revision.
- **Dynamic OpenSim requires a collection-based calibration/solver.** Existing `master_xyzw`/`slave_xyzw` fields, two fixed subscriptions, and two-column tables must become identity-keyed collections before arbitrary mapped sensors can drive IK.
- **Health must remain independent of IK.** Device and mapping diagnostics continue even when OpenSim is unavailable or calibration is blocked.

## Acceptance-Oriented Behaviors

| Given | When | Then |
|-------|------|------|
| Master and three Slaves report in any order | status updates arrive | Four stable rows appear; Master is assignable; Slaves sort by canonical MAC and do not swap identities. |
| Two Slaves share the same low 32-bit `slave_id` but have different full MACs | discovery is processed | They remain distinct; no persistence key or route uses the truncated value. |
| A device status lacks a valid full identity | discovery is processed | Row/error reports `identity_invalid`; it cannot be assigned/applied/identified. |
| Master sees a Slave but no ROS IMU topic exists | mapping panel renders | Row says `Discovered / not routed`; assignment/save works, calibration readiness is blocked. |
| One online row is selected | Identify is pressed | Exactly that MAC receives the bounded command; button is busy until ACK/timeout and no second Identify starts concurrently. |
| ESP-NOW send callback succeeds but device ACK does not arrive | Identify timeout expires | UI reports `sent_unconfirmed` or `identify_timeout`, never Confirmed. |
| Device is offline | operator views its saved row | Mapping remains visible; Identify is disabled with an offline explanation. |
| Valid custom model loads | introspection completes | Segment choices equal its BodySet component paths and contain no hard-coded anatomy. |
| Body has exact attached `<body>_imu` frame | mapping resolves | Apply preview shows that existing frame path. |
| Body has no IMU frame | mapping resolves | Preview shows a deterministic runtime-generated frame; original `.osim` bytes/fingerprint remain unchanged. |
| `<body>_imu` exists but is attached to another body or is ambiguous | preflight runs | Apply is blocked with exact frame/body mismatch. |
| One row is untouched | all other rows are mapped | Mapping is `DRAFT_INCOMPLETE`; changing it to Not used makes that decision complete. |
| Two included MACs select the same body | second selection occurs | Both rows show conflict immediately and backend also rejects a forged Apply request. |
| All devices are decided but one included device is offline | Save is requested | Save succeeds structurally; applied runtime state remains Waiting and calibration is disabled. |
| A valid draft differs from active routing | Save draft is requested | Saved revision changes; applied revision and live routes do not. |
| Valid draft and quiescent system | Save & Apply is requested | Backend returns one applied revision and resolved per-MAC topic/frame list; UI shows saved/applied match. |
| Apply fails on one route after validation/build begins | backend responds | No partial new mapping becomes authoritative; prior applied revision remains and failure names the MAC/stage. |
| SD recording or finalization is active | Apply is requested | Apply is blocked; recording is not stopped or altered. Save draft remains available. |
| Calibration capture is active | Apply is requested | Apply is blocked until capture settles/clears. |
| A changed valid mapping is applied while not recording | backend commits | IK pauses atomically, calibration becomes Uncalibrated, old joint output is not restamped, and recalibration is required. |
| Browser reloads with same model bytes/path | Studio reconnects | Exact saved draft and applied revision status restore from backend, not browser-only state. |
| Model file is renamed but bytes are identical | it is loaded | Exact fingerprint can find the saved mapping; new display path is shown. |
| Model path is unchanged but bytes/body set changed | it is loaded | Old mapping is not auto-applied; Studio offers review/migration only. |
| Saved mapping references a removed body | changed model is reviewed | Entry is unresolved and Apply is blocked; no fuzzy anatomical match is selected automatically. |
| Persisted mapping file is corrupt or schema-unknown | backend starts | Prior runtime code does not execute payload; mapping is quarantined/rejected with explicit recovery error. |
| An included live sensor becomes stale | freshness timeout elapses | Runtime becomes Applied Waiting/Degraded, names MAC/body, and no new JointState is published. |
| Same MAC returns under unchanged applied mapping | fresh monotonic synchronized frames arrive | Existing row reattaches, stale queues are empty, and readiness may return without remapping or auto-calibration. |
| Returning hardware reports a changed Master/Slave role | registry reconciles | Mapping remains associated by MAC but role change is highlighted for review; no new device row is invented. |
| Different MAC appears where an offline mapped sensor was expected | discovery updates | It is a new Unassigned row; it never inherits the absent sensor's segment. |
| A sensor was physically remounted but MAC is unchanged | operator prepares next run | UI provides Clear/Recalibrate guidance; software does not claim to detect remounting. |
| OpenSim runtime/model fails after devices are discovered | status updates continue | Device discovery/Identify/mapping remain observable; Apply/calibration show model/runtime-specific failure. |

## MVP Definition for v1.6

### Launch With (P1)

- [ ] Versioned collection-based device registry for Master plus all reported Slaves, with full canonical identities and separate liveness/route readiness.
- [ ] Stable Studio rows with role, MAC, health, last seen, Identify, body selector, and explicit Not used.
- [ ] Targeted bounded Identify with confirmed/timeout/offline/unsupported outcomes.
- [ ] `.osim` fingerprint, BodySet-derived segment choices, and deterministic existing/generated IMU-frame resolution.
- [ ] Continuous completeness, uniqueness, identity, model, route, and solver-profile validation.
- [ ] Backend per-model persistence with Draft/Saved/Applied revisions and exact-fingerprint restore.
- [ ] Transactional Save & Apply with prior-applied rollback behavior and recording/calibration apply guards.
- [ ] Dynamic per-MAC ROS orientation routes and collection-based OpenSim calibration/IK inputs.
- [ ] Offline/degraded gating, exact-MAC reconnect reattachment, calibration invalidation, and reason-coded health.
- [ ] Deterministic local fixture suite plus hardware acceptance for several simultaneous Slaves and physical LED confirmation.

### Add After Core Validation (P2)

- [ ] Guided placement workflow and readiness matrix after operators validate the raw table.
- [ ] Optional human labels/placement notes that never replace the MAC.
- [ ] Mapping/session provenance and bounded audit history.
- [ ] Review-only model revision reconciliation.
- [ ] Mapping profile import/export if the workflow spans multiple workstations.

### Future Consideration (P3)

- [ ] Explicitly validated degraded IK profiles for selected sensor-loss cases.
- [ ] Separate derived-model export that writes generated IMU Frames only on an explicit operator command.
- [ ] Per-sensor orientation weights or advanced placement calibration backed by validation data.
- [ ] Fleet management, OTA, battery analytics, or remote/cloud operation as separate products/milestones.

## Feature Prioritization Matrix

| Feature group | User value | Implementation cost | Priority |
|---------------|------------|---------------------|----------|
| Full multi-device registry and stable identity | HIGH | HIGH | P1 |
| Physical Identify by MAC | HIGH | MEDIUM/HIGH | P1 |
| Model/body/frame introspection | HIGH | HIGH | P1 |
| Mapping panel and validation | HIGH | MEDIUM | P1 |
| Versioned per-model persistence | HIGH | MEDIUM | P1 |
| Atomic Apply and dynamic ROS routes | HIGH | HIGH | P1 |
| Collection-based calibration/IK | HIGH | HIGH | P1 |
| Offline/reconnect/error semantics | HIGH | MEDIUM/HIGH | P1 |
| Deterministic tests and hardware acceptance | HIGH | HIGH | P1 |
| Guided placement/readiness matrix | MEDIUM/HIGH | MEDIUM | P2 |
| Provenance, audit, import/export | MEDIUM | MEDIUM | P2 |
| Model migration suggestions | MEDIUM | MEDIUM/HIGH | P2 |
| Partial-sensor IK | LOW until validated | HIGH | P3 |
| Generic device fleet features | OUT OF SCOPE | HIGH | — |

## Existing System vs Required Behavior

| Capability | Existing repository | Required v1.6 behavior |
|------------|---------------------|------------------------|
| Firmware peer view | Master stores up to six active `SlaveStatusSlot` entries keyed by full receive-source MAC; status text contains MAC and health. | Publish a stable, versioned collection including offline transition/timeout semantics and the Master's own full identity. |
| Host relay | One Master and at most one explicitly resolved Slave; multiple discovered stations cause launcher failure. | Provision/demultiplex every selected device without using IP as persistent identity. |
| ROS bridge health | One `node_id`, fixed topic names, and pair aggregation that accepts only `node_id == slave`. | Identity-keyed device registry and unique per-MAC raw/IMU/health routes. |
| Studio state/UI | `PairHealthSnapshot` with `master` and optional `slave`; fixed two-node health panel. | Collection-based rows, mapping draft/save/apply state, per-device errors, and exact reconnect reconciliation. |
| OpenSim inputs | `_ROLES = ("master", "slave")`, two fixed subscriptions, two-value calibration artifact, and two-column orientation table. | Applied identity-to-body/frame map drives a collection of subscriptions, offsets, status entries, and orientation labels. |
| Model mapping | Launch arguments hard-code `femur_r_imu` and `tibia_r_imu`. | BodySet-derived segment selection with exact model fingerprint and frame resolution. |
| Persistence | No authoritative per-model sensor map. | Atomic backend mapping store with schema/revisions and exact fingerprint restore. |

## Explicit Non-Goals and Acceptance Boundaries

- Do not redesign reliable SD recording or turn mapping into the acquisition/recording switch.
- Do not add generic neural acquisition, impedance, headstage, AUX/ADC, DAC/audio, motor, or EtherCAT functions.
- Do not add cloud accounts, remote device fleet administration, arbitrary Wi-Fi provisioning, OTA, or firmware flashing.
- Do not claim clinical/biomechanical validity from correct device mapping alone.
- Do not infer physical placement from motion, RSSI, order, or model anatomy.
- Do not support two included sensors on one segment in v1.6.
- Do not silently write the source `.osim`.
- Do not treat the native visualizer as proof that mapping/calibration is valid; authoritative status is the applied mapping and IK health contract.
- Do not auto-apply a mapping across a changed model fingerprint.
- Do not auto-calibrate after Apply/reconnect.
- Do not invent partial-sensor IK; suppress output unless a future solver profile proves the requested coordinates remain observable.
- Do not require all powered devices to participate; explicit Not used is supported.
- Hardware acceptance is required for the full six-byte identity, Master identity, maximum simultaneous peer count used by the lab, targeted LED acknowledgement, dropout timing, and multi-device stream routing. Local fixtures can validate all remaining state and persistence rules.

## Sources

### Authoritative ecosystem sources

- Espressif, **ESP-NOW — ESP32-S3 ESP-IDF Programming Guide v6.0.2**: source/destination MAC addressing, peer lists, channel constraints, send/receive callbacks, full peer MAC targeting, and the warning that MAC-layer send success does not guarantee application-layer receipt. https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/network/esp_now.html
- OpenSim, **OpenSense — Kinematics with IMU Data** (page updated/copyrighted through 2024): one or more sensors, explicit sensor-ID-to-body tracking, body-segment registration as IMU Frames, `<bodyname>_imu` naming, synchronized/fused orientation assumptions, calibration, and orientation IK. https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084203/OpenSense+-+Kinematics+with+IMU+Data
- OpenSim Core Python tutorial, **Loading and Modifying OpenSim Models**: loading a model and enumerating `model.getBodySet()` with stable names and absolute component paths. https://github.com/opensim-org/opensim-core/blob/main/Bindings/Python/tutorials/Tutorial%203%20-%20Loading%20and%20Modifying%20OpenSim%20Models.ipynb
- OpenSim API Guide, **Frames / PhysicalOffsetFrame**: a Body is a PhysicalFrame and a PhysicalOffsetFrame is a constant transform from a parent PhysicalFrame. https://github.com/opensim-org/opensim-core/blob/main/doc/APIGuide.md

### Live repository evidence

- `firmware/step_node/step_node.ino`: `MAX_SLAVE_STATUS_SLOTS = 6`; full ESP-NOW source MAC keys each `SlaveStatusSlot`; active status becomes stale at 5 seconds; current command set has no Identify opcode.
- `firmware/step_node_slave/step_node_slave.ino`: current `slave_id` is only the low 32 bits of `ESP.getEfuseMac()`; status includes IMU/quaternion/sync/rate fields.
- `backend/rehab_robotics_bridge/esp32_bridge_node.py`: one fixed `node_id`; pair health accepts only one `slave`; raw/IMU topics and frame IDs derive from role instead of hardware identity.
- `scripts/stepesp_tcp_udp_relay.py` and `scripts/start_stepesp_wireless.ps1`: the relay/startup path provisions one Master and one Slave and treats multiple responding stations as an error.
- `rehab-robotics-studio/src/types/health.ts`, `src/state/systemStore.ts`, and `src/components/dashboard/HealthPanel.tsx`: pair-shaped frontend types/store/UI render exactly Master and Slave.
- `backend/rehab_robotics_bridge/opensim_node.py`, `opensim/calibration.py`, and `opensim/opensim_orientation_ik.py`: current calibration, subscriptions, readiness, and orientation table are all hard-coded to `master` and `slave`.
- `examples/opensim_quaternion_demo.osim`: demonstrates exact `femur_r_imu` and `tibia_r_imu` PhysicalOffsetFrames attached to `/bodyset/femur_r` and `/bodyset/tibia_r`.

## Confidence and Open Decisions

- **HIGH:** Stable full identity, explicit physical identification, deliberate sensor-to-body association, model-derived body vocabulary, uniqueness, reference-pose calibration binding, and stale-output suppression follow directly from ESP-NOW/OpenSense documentation and the project requirements.
- **HIGH:** The current repository cannot satisfy this as a frontend-only change; fixed pair assumptions exist in firmware-to-host exposure, relay/launch, ROS status/topics, Studio types/UI, calibration, and IK.
- **MEDIUM:** The preferred model behavior is to use exact existing `<body>_imu` Frames and otherwise add runtime-only identity-offset Frames. This fits OpenSense semantics and avoids mutating research models, but must be verified against the installed OpenSim 4.5.2 Python bindings and visualizer.
- **MEDIUM:** Identify should use application acknowledgement. The live firmware inspected here has no Identify opcode, so the exact plugin-compatible command/reply and which LED is safe to blink must be confirmed before planning its transport contract.
- **Open decision:** Define the canonical persisted MAC as the full stable hardware/base MAC and separately expose the current ESP-NOW transport-interface MAC if they can differ. The route layer must be able to target the latter without changing the mapping key.
- **Open decision:** Confirm the lab's required maximum simultaneous Slaves. Firmware currently has six status slots, while Espressif's stack supports a larger peer list; roadmap scope should use the tested lab maximum, not advertise an unverified theoretical count.
- **Open decision:** Decide whether a role change for the same MAC (Slave reflashed as Master or vice versa) merely warns or requires explicit mapping reconfirmation. The safe default in this document is review before runtime readiness.

---
*Feature research for: v1.6 Multi-Sensor Bone Mapping*
*Researched: 2026-07-30*
