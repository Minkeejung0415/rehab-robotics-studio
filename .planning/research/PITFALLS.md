# Pitfalls Research

**Domain:** Multi-sensor ESP-NOW discovery, stable hardware identity, per-model OpenSim mapping, and dynamic ROS 2 routing
**Researched:** 2026-07-30
**Confidence:** HIGH for failure modes and repository integration risks; MEDIUM for hardware-specific LED behavior, maximum peer load, and runtime creation of OpenSim IMU frames until exercised on the pinned hardware/runtime

## Critical Pitfalls

### Pitfall 1: Truncated or Mutable Device Identity

**What goes wrong:**
A saved segment assignment, ROS route, or Identify command points at the wrong physical IMU. Two devices can collapse into one row when the current 32-bit `slave_id` collides, while DHCP address, ESP-NOW slot, discovery order, and Master/Slave role can all change without the hardware changing.

**Why it happens:**
The current pair-oriented path already exposes convenient role names, IPs, and a truncated ID. Reusing those values is easier than carrying a verified six-byte identity through firmware, relay, ROS, rosbridge, persistence, and UI schemas.

**How to avoid:**
Use one normalized full 48-bit hardware identity at every persistence and routing boundary, with an explicit distinction between stable base MAC and the interface MAC used for ESP-NOW transport. Reject malformed, all-zero, broadcast, duplicate, or changing identities. Keep IP, role, connection state, and segment assignment as mutable metadata. Derive ROS-safe topic tokens reversibly from the canonical MAC, never from a role or model segment.

**Warning signs:**
- IDs contain only eight hexadecimal digits.
- Maps or React rows are keyed by `master`, `slave`, array index, slot, or IP.
- A route is accepted before an identity handshake completes.
- A device changes identity when DHCP order changes.
- Two full MACs share a persistence key or topic.

**Phase to address:**
Phase 1: Identity and Targeted Identify establishes the full-MAC protocol and normalization contract. Phase 2 must enforce that contract in relay routes and canonical ROS topics.

---

### Pitfall 2: Reconnect Rebinds by Discovery Order

**What goes wrong:**
After a power cycle or DHCP reorder, a returning sensor appears as a new row, inherits another device's route, or takes over the legacy `/esp32/slave/*` alias. Saved placement is lost or silently attached to the wrong limb.

**Why it happens:**
The current startup path assumes one Slave, and "first discovered" works in a two-device demo. Dynamic discovery then gets implemented as an append-only array whose indices and IPs become accidental identity.

**How to avoid:**
Reconcile every live update into a MAC-keyed registry. Preserve known offline rows and route records, update the same record when that MAC returns, and flush pre-disconnect samples before declaring the route ready. A different MAC at the old IP is a new unassigned device. Sort presentation deterministically without making sort order semantic. Persist one explicit `legacy_slave_id`; never recalculate it from discovery order.

**Warning signs:**
- Rows jump as heartbeats arrive.
- Offline rows disappear automatically.
- Route keys are local ports or source IPs without a confirmed MAC.
- Reconnect increments mapping revision despite no configuration change.
- The legacy Slave alias changes after a restart.

**Phase to address:**
Phase 2: N-Route Relay and Canonical ROS Fleet Topics. Verify the full behavior again in Phase 5 UI tests and Phase 6 hardware reconnect tests.

---

### Pitfall 3: Non-Transactional Mapping and Stale Model Revisions

**What goes wrong:**
Some OpenSim subscriptions switch to a new mapping while others remain on the old one, a browser tab overwrites a newer configuration, or a mapping created for one `.osim` revision is silently applied to different model contents. The system can display "applied" while the solver still uses a mixed or prior route set.

**Why it happens:**
Incremental row mutations are easy to send, filenames look like stable model identifiers, and live solver objects are tempting to mutate during validation. Browser persistence can also be mistaken for backend authority.

**How to avoid:**
Compute `model_id` from the exact `.osim` bytes. Send the complete candidate with an `expected_revision`; validate model ID, device IDs, segment paths, frame resolution, route readiness, uniqueness, and solver requirements before mutation. Stage subscriptions, model frames, solver, and visualizer off to the side, then swap one applied revision atomically. On any failure retain the prior applied mapping and calibration only if both still match. Persist with write-temp, flush, and atomic replace; preserve corrupt data for recovery. Studio must wait for authoritative backend status before showing a revision as applied.

**Warning signs:**
- Mapping is keyed by model filename or path alone.
- Apply consists of multiple per-row service calls.
- `applied=true` is set from a service response before status confirms the revision.
- Failed Apply leaves a partially changed subscription set.
- Two browser tabs can save without revision conflict.
- Model bytes change but the old mapping auto-applies.

**Phase to address:**
Phase 3: Model Catalog and Persistent Mapping Contracts. Phase 5 must preserve draft-versus-authoritative revision semantics in Studio.

---

### Pitfall 4: Duplicate, Implicitly Unmapped, or Unresolvable Sensors

**What goes wrong:**
Two IMUs feed one segment, an untouched selector is treated as a deliberate exclusion, or a body display name resolves to the wrong/missing OpenSim Frame. Calibration and IK may remain numerically plausible while using an ambiguous orientation set.

**Why it happens:**
Client-only validation, first/last-wins dictionaries, hard-coded anatomy lists, and fuzzy component-name matching make a demo appear complete. The UI's body vocabulary is also easily confused with the exact Frame labels OpenSense consumes.

**How to avoid:**
Represent every device decision explicitly as assigned, Not used, or Unassigned. Unassigned is incomplete. Enforce one included sensor per canonical segment path both continuously in Studio and authoritatively in the backend. Build choices from the loaded model's `BodySet`, persist absolute component paths, and resolve an exact compatible IMU frame before Apply. Reject ambiguity and unsupported bodies; do not silently fall back to a similarly named joint or frame. Validate a declared solver minimum instead of inferring biomechanical sufficiency from sensor count alone.

**Warning signs:**
- Duplicate selectors are merely disabled in the browser but accepted by the service.
- Mapping dictionaries silently overwrite an earlier device.
- Empty selection means both "not decided" and "spare."
- Segment values are display names or hard-coded anatomy.
- Apply succeeds with an unresolved or ambiguously attached IMU frame.

**Phase to address:**
Phase 3: Model Catalog and Persistent Mapping Contracts. Phase 5 adds immediate operator feedback but does not replace backend validation.

---

### Pitfall 5: Solving with Stale or Unsynchronized Samples

**What goes wrong:**
OpenSim receives the newest value from each sensor even though those values represent different moments, include data from before a reconnect, or contain a sensor that has stopped updating. Joint output can look smooth and plausible while representing no real simultaneous pose.

**Why it happens:**
"Latest N" is simple, ROS arrival alone looks like liveness, and holding the last result keeps the UI visually active. Variable sensor count makes a fixed synchronizer awkward, encouraging removal of synchronization checks.

**How to avoid:**
Maintain one bounded latest-sample record per applied MAC with source timestamp, monotonic arrival time, and connection generation. Solve only from a complete immutable set in deterministic frame order when every mapped sensor is live, quaternion-valid, fresh, within maximum source-time skew, and advanced since the prior solve. On reconnect, increment generation and flush old samples. Stamp output conservatively from contributing source time. If any required input fails, close the JointState gate while keeping acquisition, recording, health, and Identify operational.

**Warning signs:**
- Readiness means only "a sample exists."
- Source timestamps or skew are not measured.
- A reconnect can immediately reuse cached orientation.
- JointState continues with a fresh publish timestamp after one sensor stops.
- Queues grow while the solver falls behind.

**Phase to address:**
Phase 4: N-Sensor Calibration, Official IK, and Visualizer. Phase 2 must supply per-device connection generations and trustworthy freshness metadata.

---

### Pitfall 6: Calibration Survives a Semantic Mapping Change

**What goes wrong:**
Mounting offsets captured for one model, device set, body assignment, frame convention, or solver profile are reused after remapping. The pipeline is "calibrated" but transforms orientations under a different semantic contract.

**Why it happens:**
Calibration is treated as a global boolean or two fixed quaternions. A reconnect and a remap are both represented as generic state changes, so invalidation becomes either too weak or unnecessarily aggressive.

**How to avoid:**
Bind every calibration artifact to `model_id`, applied mapping revision, exact device-to-frame set, convention version, known pose, source interval, and per-device quality metrics. Applying any different model/mapping/frame/profile invalidates calibration and closes IK until explicit recapture. A brief dropout of the same MAC under the unchanged revision may retain the artifact, but output remains gated until fresh synchronized input returns. Capture complete sensor sets transactionally; one moving, stale, or dispersed sensor fails the candidate.

**Warning signs:**
- Calibration state is just `true/false`.
- Artifacts contain `master` and `slave` fields rather than a revision-bound map.
- Apply does not immediately change state to Uncalibrated.
- Model reload preserves calibration without comparing hashes.
- Failed multi-sensor capture partially updates offsets.

**Phase to address:**
Phase 4: N-Sensor Calibration, Official IK, and Visualizer, using Phase 3's authoritative revisions.

---

### Pitfall 7: Identify Reports Link-Layer Send as Physical Confirmation

**What goes wrong:**
Studio tells the operator that the selected unit blinked even though the application never received or executed the command. Worse, a broadcast or incorrectly targeted command blinks another strapped device.

**Why it happens:**
The ESP-NOW send callback is readily available and looks like an acknowledgement. Blocking LED code is also an easy implementation for a short demo.

**How to avoid:**
Target one verified full MAC, include a unique command ID, and require the Slave to echo that ID and result through application status before the Master and ROS service report confirmation. Distinguish confirmed, sent-unconfirmed, timeout, offline, unsupported, and rejected. Serialize or independently correlate requests. Bound duration, implement LED state with a non-blocking deadline, restore prior state, and advertise Identify only when the board's LED pin and active level are verified safe. Do not guess a pin or broadcast.

**Warning signs:**
- Service success is returned directly from `esp_now_send`.
- No command ID crosses firmware and service boundaries.
- Identify uses `delay()` in a callback or acquisition loop.
- Multiple rows can start indistinguishable Identify requests.
- Firmware always advertises Identify despite unknown LED wiring.

**Phase to address:**
Phase 1: Identity and Targeted Identify. Phase 6 must verify physical LED behavior and unchanged acquisition/recording timing.

---

### Pitfall 8: Backward-Compatible Aliases Become a Second Source of Truth

**What goes wrong:**
Legacy Master/Slave topics point to arbitrary devices, alias data diverges from canonical per-MAC topics, or role names leak back into mapping and persistence. Existing pair workflows may pass while fleet mode routes a different sensor.

**Why it happens:**
Compatibility is implemented by maintaining two independent pipelines or by selecting the first current Slave on every launch. Once both paths mutate state, their behavior drifts.

**How to avoid:**
Publish canonical per-MAC data once and derive legacy aliases from that same accepted stream. Bind `/esp32/slave/*`, `/esp/raw/slave`, and pair health to an explicit persisted `legacy_slave_id`. Keep legacy launch mode as a rollback path during migration, add schemas and fields additively, and retain old firmware packet parsing with strict version/size checks. Do not remove fixed contracts until discovery, reconnect, mapping restore, calibration/IK, recording, and Studio regression all pass in fleet mode.

**Warning signs:**
- Canonical and alias publishers parse hardware independently.
- Alias selection uses list position.
- `body_segment` remains authoritative in the acquisition bridge.
- Old firmware is parsed as the new packet layout.
- Legacy tests are removed before fleet hardware acceptance.

**Phase to address:**
Phase 2: N-Route Relay and Canonical ROS Fleet Topics, with removal gates exercised in Phase 6.

---

### Pitfall 9: Mapping Changes Cross Recording or Finalization Boundaries

**What goes wrong:**
One SD session contains samples whose same device IDs represent different body mappings, or an Apply operation interferes with a recording stop/finalization handshake. The GUI may imply that recording succeeded even when finalization failed.

**Why it happens:**
Mapping is treated as ordinary live UI state, and Run, recording, calibration, and solver state are collapsed into one global busy flag. A convenient "apply now" action may silently stop recording.

**How to avoid:**
Keep acquisition and SD recording semantics independent from mapping. Allow draft editing and saving during acquisition, but block Apply during calibration capture and during active recording/finalization. Never auto-stop recording to satisfy Apply. Report the required operator action explicitly. After a quiescent Apply, pause IK atomically, invalidate calibration, and require explicit recapture. Record the applied model hash, mapping revision, device-to-frame entries, and calibration ID in session provenance when that feature is added.

**Warning signs:**
- Apply service can run while `recording` or `finalizing`.
- Mapping code calls recording stop internally.
- A session has no mapping/model revision metadata.
- Recording finalization failure is hidden by a successful mapping status.
- Old JointState is restamped after Apply.

**Phase to address:**
Phase 3: Mapping services define the interlock contract; Phase 5 exposes it clearly in Studio; Phase 6 verifies multi-device recording start/stop/finalization.

---

### Pitfall 10: Dynamic Subscriptions and Queues Grow Without Bounds

**What goes wrong:**
Repeated Apply/reconnect cycles create duplicate callbacks, obsolete subscriptions keep updating state, browser reconnects leak rosbridge subscriptions, or per-device queues accumulate latency until output trails motion.

**Why it happens:**
Dynamic collections make creation straightforward but cleanup easy to omit. Queueing every sensor event seems lossless, and browser subscriptions may be keyed only by topic rather than unique request IDs.

**How to avoid:**
Bound the supported fleet to the tested current capacity while keeping code collection-based. Own exactly one route/session/publisher set per MAC and one OpenSim subscription per applied sensor. Stage new handles, atomically swap, then explicitly destroy old handles and invalidate their generation. Use bounded per-route UDP queues with drop counters and a latest-complete-orientation-set strategy rather than an unbounded work queue. Give every browser subscription a unique ID and unsubscribe it on reconnect/disposal. Cap arrays, strings, and issue counts at rosbridge JSON boundaries.

**Warning signs:**
- Callback count rises after every Apply.
- A removed MAC still changes solver readiness.
- Memory or solve lag grows during a long session.
- Browser reconnect duplicates status updates.
- No per-route drop metrics or maximum queue sizes exist.

**Phase to address:**
Phase 2 for route/session/alias bounds, Phase 4 for orientation aggregation, and Phase 5 for rosbridge lifecycle cleanup.

---

### Pitfall 11: Deterministic Tests Cover Only the Happy Two-Sensor Path

**What goes wrong:**
The feature appears complete with one Master and one Slave but fails under device reorder, low-32-bit collisions, stale inputs, Apply rollback, corrupt persistence, mixed firmware, or three-plus sensor ordering. Hardware scarcity hides contract regressions until a lab session.

**Why it happens:**
End-to-end hardware tests are slow and the Jetson may be disconnected, while mocks often preserve the same fixed ordering and assumptions as production code.

**How to avoid:**
Build deterministic fixtures at each contract boundary: identity normalization and collisions; arbitrary registry order; route rebind by MAC; targeted Identify ACK/timeout; existing and missing model IMU frames; exact model hash changes; complete/incomplete/duplicate mappings; optimistic revision conflict; staged Apply failure and rollback; corrupt mapping store; stale/skew/reconnect generation gates; deterministic N-column labels; calibration invalidation; alias stability; subscription cleanup; and recording/finalization interlocks. Retain two-sensor numerical regression tests, then add 0/1/3+/capacity cases. Use fake registry, adapter, solver, clocks, and temporary persistence paths. Reserve hardware acceptance for electrical LED safety, actual MAC/interface relationships, peer load, radio timing, and stream throughput.

**Warning signs:**
- Tests always return devices in Master-then-Slave order.
- Assertions inspect only row count, not identity association.
- No fake clock controls freshness/skew.
- Apply failure is tested only before staging starts.
- No test checks subscriber count after repeated remaps.
- Dynamic mode becomes default before the failure matrix passes.

**Phase to address:**
Every phase adds deterministic contract tests for its boundary. Phase 6: Hardware Compatibility and Failure Matrix is the promotion gate.

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Reuse 32-bit `slave_id`, IP, role, or array index as identity | Avoids schema changes | Wrong-device mapping and commands after collision/reconnect | Never |
| Keep fixed Master/Slave dictionaries and add `slave2` fields | Small diff for one extra sensor | Repeated rewrites, nondeterministic solver/table logic | Never for v1.6 |
| Persist only in Studio `localStorage` | Fast browser demo | Backend cannot recover authoritatively; tabs/workstations diverge | Only as a non-authoritative draft cache after backend revisions exist |
| Apply row-by-row | Simple service shape | Partial live mapping and unrollbackable failures | Never |
| Key model mappings by filename | Human-readable | Silent reuse across changed or same-named model contents | Never |
| Use "latest available" orientations | Low implementation effort | Plausible but temporally invalid biomechanics | Never for product IK |
| Keep old subscriptions after remap | Avoids lifecycle code | Duplicate callbacks and stale state mutation | Never |
| Auto-delete offline rows | Cleaner table | Loses placement and reconnect continuity | Never; use explicit Forget with reference checks |
| Auto-select first Slave for compatibility | Preserves pair UI quickly | Alias changes with discovery order | Only in an isolated test fixture, never runtime |
| Unbounded queues to avoid drops | Appears lossless | Increasing latency and memory use | Never; newest complete state is more valuable |
| Generate or rewrite `.osim` frames silently | Makes more bodies selectable | Breaks source reproducibility and model fingerprint | Never; runtime-only deterministic frame or explicit derived export |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Firmware to relay | Treat current IP or truncated status ID as route identity | Require bounded `IDENTITY?` response with full verified identity before route readiness |
| ESP-NOW Identify | Treat MAC-layer send callback as application success | Correlate a command ID echoed by device status and return reason-coded timeout/failure |
| Mixed firmware versions | Parse new fields by size assumption | Check explicit version and exact packet size; accept known old/new layouts additively |
| Relay to ROS fleet bridge | Let one failed connection cancel all session tasks | Isolate one task/queue per route and publish per-device failures |
| ROS aliases | Maintain separate canonical and legacy parsing pipelines | Republish aliases from one canonical per-MAC accepted stream |
| Rosbridge | Omit unique subscription/service IDs or cleanup | Correlate every call, cap payloads, and unsubscribe explicitly |
| OpenSim catalog | Treat BodySet display name as solver frame | Persist component path and resolve a verified IMU `PhysicalFrame` |
| OpenSim runtime frames | Add frames after system initialization or silently choose a joint frame | Stage deterministic frames before `initSystem`; fail closed if pinned bindings cannot do so safely |
| Mapping persistence | Overwrite corrupt JSON on startup | Preserve/quarantine it, expose error, recover from bounded backup or reviewed save |
| Calibration | Reuse offsets by device alone | Bind artifact to model, mapping revision, exact frame set, and convention |
| Recording | Let Apply force Stop or imply finalization success | Block Apply while recording/finalizing and preserve independent recording status |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| 100 Hz health/status per Slave mixed with sample traffic | ESP-NOW send errors, radio congestion, delayed ACKs | Measure airtime; reduce health rate separately from orientation sampling if needed | Validate at Master plus six current status slots |
| One unbounded UDP queue per route | Growing latency and memory, old samples processed after reconnect | Fixed queue size, newest-data policy, per-route drop counters | During a slow consumer, reconnect storm, or high-rate multi-device run |
| Queue every complete orientation set | IK output age grows although inputs are current | Retain only newest complete set and solve at configured bounded rate | When N-sensor OpenSim solve time exceeds input period |
| Browser subscribes to every high-rate raw/IMU topic | UI churn and rosbridge JSON load scale with sensor count | Mapping UI consumes bounded fleet/mapping health snapshots | As additional Slaves are enabled |
| Recreating routes/subscriptions without teardown | Duplicate updates and rising memory/CPU | Explicit lifecycle ownership, destroy/unsubscribe, generation guards | After repeated Apply/reconnect cycles |
| Rendering raw sample history in mapping state | React rerenders overwhelm setup UI | Keep device health/state normalized; graph pipeline remains separate | At normal 100 Hz rates even with a small fleet |

## Security and Safety Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Accepting malformed or unbounded identity/status JSON | Browser/backend memory growth or invalid routing state | Strict schema parsing, normalized identifiers, and bounded arrays/strings/issues |
| Trusting a changed identity on an established route | One physical endpoint can take over another device's logical mapping | Close/quarantine the route and create a new unassigned identity record |
| Guessing an onboard LED pin or active level | Electrical conflict with SD/SPI/DIO or persistent incorrect output | Board-specific compile-time configuration and capability advertisement |
| Blocking in ESP-NOW callbacks for Identify | Sampling, synchronization, recording, or watchdog failure | Non-blocking deadline state in the main loop |
| Executing data from mapping/persistence payloads | User-provided content crosses a privileged backend/browser boundary | Treat mappings as closed data schemas; never execute code or model text from them |
| Silent partial-sensor output after failure | Misleading biomechanical data presented as current | Fail closed: suppress new JointState and publish reason-coded health |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| One generic Online badge | Operator cannot distinguish ESP-NOW visibility, transport, ROS topic, freshness, or sync | Layered readiness with one actionable reason per device |
| Rows reorder or vanish during dropout | Physical placement errors while strapping/power-cycling sensors | MAC-keyed stable rows retained as stale/offline |
| MAC hidden behind a friendly label | Visually identical devices can be confused | Optional label plus always-visible canonical/short MAC |
| Unassigned silently means excluded | Forgotten sensors look intentionally omitted | Separate Unassigned from explicit Not used |
| Save and Apply are conflated | Operator cannot tell whether live routing changed | Show Draft, Saved, Applied, and Runtime Ready separately |
| Identify success lacks confirmation detail | Operator trusts the wrong physical unit | Show confirmed, sent-unconfirmed, timeout, offline, unsupported, or rejected |
| Apply failure replaces the live view | Operator loses track of the last known-good route | Keep prior applied revision visible and show candidate failure separately |
| Stale IK number remains on screen as current | Plausible but invalid pose may be trusted | Mark output invalid/stale and stop new JointState publication |
| Apply silently stops recording | Session semantics and finalization become unclear | Block with explicit "Stop/finalize recording before Apply" guidance |

## "Looks Done But Isn't" Checklist

- [ ] **Stable identity:** Every layer uses all 48 MAC bits; collision, malformed ID, interface-MAC difference, and DHCP reorder cases pass.
- [ ] **Reconnect:** Same MAC updates the same row/topic/mapping; different MAC at the old IP remains new and Unassigned.
- [ ] **Canonical topics:** Per-MAC streams and legacy aliases carry identical accepted data, and `legacy_slave_id` is explicit.
- [ ] **Identify:** Success requires application ACK; timeout, unsupported LED, offline target, and non-blocking acquisition are verified.
- [ ] **Model identity:** Same name/different bytes yields a different hash and no silent mapping/calibration reuse.
- [ ] **Mapping validation:** Unassigned versus Not used, duplicate segments, unknown devices, missing frames, and solver minimum are authoritative backend checks.
- [ ] **Transactional Apply:** Failure at every staging step leaves the prior mapping/subscriptions/solver intact and does not advance applied revision.
- [ ] **Recording interlock:** Apply is blocked during recording and finalization without stopping or altering the session.
- [ ] **Calibration:** Artifact provenance includes model/mapping/frame set and invalidates exactly on semantic changes.
- [ ] **Freshness:** One stale, skewed, invalid, or pre-reconnect sample closes IK output while health/acquisition continue.
- [ ] **Bounded lifecycle:** Repeated Apply/reconnect does not grow subscription, task, queue, callback, or browser listener counts.
- [ ] **Determinism:** N-sensor table labels, UI ordering, mapping serialization, and alias selection are stable across arbitrary input order.
- [ ] **Promotion gate:** Legacy pair, multi-sensor recording/finalization, dynamic IK, corrupt-state recovery, and the hardware failure matrix pass before dynamic mode becomes default.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong identity persisted | HIGH | Stop IK/recording use, migrate only entries with independently verified full MACs, require Identify/placement review, then recalibrate |
| Route rebound to wrong device | MEDIUM | Quarantine route, re-run identity handshake, attach route to correct MAC, flush cached samples, and re-enter readiness |
| Partial or failed Apply | LOW if transactional; HIGH otherwise | Retain/restore last applied revision, destroy staged handles, publish failure stage, correct candidate, retry |
| Mapping store corruption | MEDIUM | Preserve corrupt file, inspect/restore bounded backup, load empty explicit state if needed, then save a reviewed mapping |
| Stale model mapping | MEDIUM | Load new catalog, mark missing paths unresolved, review assignments, apply a new revision, and recalibrate |
| Stale/unsynchronized solve | LOW | Close output gate, flush offending generation, wait for a complete fresh bounded-skew set |
| Incorrect calibration reuse | HIGH | Invalidate artifact, verify model/mapping/frame convention, perform explicit known-pose recapture, and discard affected output |
| Identify false positive | MEDIUM | Downgrade result to unconfirmed, verify command correlation/LED configuration, and repeat physical identification before mapping |
| Subscription leak | MEDIUM | Stop dynamic mode, enumerate owners/handles, destroy obsolete subscriptions/tasks, add generation guards and repeat-cycle tests |
| Recording crossed a mapping change | HIGH | Quarantine the session from biomechanical interpretation; recover SD data separately and repeat under one recorded mapping revision |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Full-MAC truncation/mutable identity | Phase 1, reinforced Phase 2 | Two devices sharing low 32 bits remain distinct end to end; malformed/changed identities are rejected |
| Reconnect and device reordering | Phase 2 | Arbitrary DHCP/discovery order and power-cycle preserve row, topic, route identity, and legacy alias |
| Transactional mapping revision/model hash | Phase 3 | Changed bytes produce new model ID; stale revision and staged failure leave prior Apply intact |
| Duplicate/unmapped/unresolvable sensors | Phase 3, surfaced Phase 5 | Backend rejects forged duplicate/incomplete candidates and missing/ambiguous frames |
| Stale/unsynchronized samples | Phase 4 | Fake clock/skew/reconnect cases stop JointState while other streams continue |
| Calibration invalidation | Phase 4 | Model/mapping/frame/profile change clears calibration; same-MAC dropout alone does not mutate artifact |
| Identify acknowledgement and LED safety | Phase 1, hardware Phase 6 | Lost ACK never reports confirmed; blink is targeted, bounded, non-blocking, and electrically verified |
| Backward-compatible aliases | Phase 2, removal gate Phase 6 | Canonical and alias streams match; explicit legacy Slave remains stable across reorder |
| Recording/finalization interlocks | Phase 3 contract, Phase 5 UX, Phase 6 acceptance | Apply is rejected while recording/finalizing; recording is never auto-stopped |
| Bounded dynamic subscriptions/queues | Phases 2, 4, and 5 | Repeated Apply/reconnect keeps handle/listener counts bounded and reports controlled drops |
| Deterministic test matrix | Each phase, promotion Phase 6 | Unit/fixture coverage plus multi-device hardware failure matrix passes before default switch |

## Sources

- `.planning/PROJECT.md` - v1.6 scope, safety constraints, full-device discovery, Identify, per-model persistence, uniqueness, and dynamic OpenSim routing.
- `.planning/research/STACK.md` - recommended versions, typed command boundaries, full-MAC topic scheme, atomic Apply, freshness barrier, compatibility requirements, and validation gates.
- `.planning/research/FEATURES.md` - operator workflow, table stakes, anti-features, state semantics, acceptance behaviors, recording/calibration guards, and deterministic verification scope.
- `.planning/research/ARCHITECTURE.md` - authoritative state ownership, firmware/relay/ROS/OpenSim/Studio boundaries, six-phase build order, failure containment, migration gates, and scaling limits.
- Primary documentation cited and evaluated in the source research: Espressif ESP-NOW addressing/send semantics, ROS 2 Humble interface semantics, rosbridge v2 correlation/subscription lifecycle, and OpenSim/OpenSense model Frame and orientation-IK guidance.

---
*Pitfalls research for: Rehab Robotics Studio v1.6 Multi-Sensor Bone Mapping*
*Researched: 2026-07-30*
