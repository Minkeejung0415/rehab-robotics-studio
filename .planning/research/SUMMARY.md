# Project Research Summary

**Project:** Rehab Robotics Studio — v1.6 Multi-Sensor Bone Mapping
**Domain:** Local multi-ESP-NOW wearable IMU discovery, model-aware sensor placement, and dynamic ROS 2/OpenSim orientation IK
**Researched:** 2026-07-30
**Confidence:** HIGH overall; MEDIUM where physical hardware, multi-peer transport, and pinned OpenSim runtime-frame behavior still require validation

## Executive Summary

Rehab Robotics Studio v1.6 is a lab-instrument configuration and preflight milestone, not a generic IoT dashboard. Experts build this kind of system by separating immutable hardware identity from mutable role, IP route, model assignment, and liveness; by keeping acquisition independent from mapping and recording; and by allowing OpenSim to consume only a complete, fresh, synchronized orientation set. The present repository already has the right core stack and a working two-sensor OpenSim path, but fixed `master`/`slave` assumptions collapse the Master plus multiple ESP-NOW peers at the relay, ROS, Studio, calibration, and solver boundaries.

The recommended approach is an additive six-phase generalization. Carry a verified full 48-bit device identity through firmware, the Windows relay, ROS, rosbridge, persistence, and Studio. Publish canonical per-MAC acquisition topics while retaining explicit legacy pair aliases. Make the OpenSim backend authoritative for the loaded model hash, model-derived segment/frame catalog, desired and applied mapping revisions, calibration provenance, dynamic subscriptions, and IK validity. Studio owns only an editable draft and request state. Mapping changes are full-candidate, optimistic-revision transactions: stage the new routes and solver, swap once, and retain the last known-good applied revision on failure.

The principal risks are wrong-device identity after DHCP/reconnect, false Identify confirmation, partial Apply, stale or skewed N-sensor solves, invalid calibration reuse, recording crossed by a mapping change, and leaked dynamic subscriptions or queues. Mitigate them with application-level Identify acknowledgement, SHA-256 model identity, exact component/frame paths, backend validation, recording/calibration interlocks, bounded generation-aware freshness gates, explicit lifecycle teardown, legacy compatibility gates, deterministic failure fixtures in every phase, and a final multi-device hardware matrix before dynamic mode becomes the default.

## Key Findings

### Recommended Stack

Extend the existing stack in place. No database, frontend framework, `roslibjs`, ROS dynamic-type package, separate `.osim` parser, new ESP-NOW/LED library, or OpenSim upgrade is needed. The material stack changes are local contracts and collection-based refactors, not third-party dependencies.

**Core technologies:**

- **React 18.3.1 + TypeScript 5.9.3:** stable MAC-keyed mapping rows, discriminated device/mapping states, strict transport parsers, and conflict/preflight UX.
- **Zustand 4.5.7:** normalized live UI state and optional versioned draft cache. It must not be the authority for applied routing.
- **ROS 2 Humble + Python 3.10 + `rclpy`:** one fleet bridge, versioned state snapshots, confirmed command services, and runtime-created/destroyed `sensor_msgs/msg/Imu` subscriptions.
- **rosbridge server 2.0.7:** retain the existing raw WebSocket client, correlated service calls, unique subscription IDs, and explicit unsubscribe lifecycle.
- **OpenSim Python 4.5.2:** authoritative `.osim` load, SHA-256 model identity, `BodySet`/Frame catalog, calibration, one N-column official orientation IK solve, and native visualizer integration.
- **Arduino ESP32 core 3.3.10 / existing firmware 1.8.0:** add full identity, peer inventory, bounded Identify request/ack, exact packet version/size handling, and non-blocking LED deadlines.
- **Python standard library JSON/filesystem primitives:** backend mapping persistence with write-temp, flush, atomic replace, bounded backup, and corruption quarantine.

**Required local interfaces and schemas:**

- Versioned full fleet, model catalog, mapping, and solver snapshots on existing `std_msgs/msg/String` JSON topics.
- Typed local ROS services for Identify, setting a complete desired mapping, and applying an expected revision atomically.
- Canonical per-device acquisition topics such as `/esp32/mac_aabbccddeeff/imu`; body segment names never belong in acquisition topic names.
- A canonical device key such as `esp32:aabbccddeeff`, plus display MAC `AA:BB:CC:DD:EE:FF`. Preserve stable base MAC and ESP-NOW/AP/STA transport MACs separately until their actual-board relationship is verified.

#### Stack Deltas and Resolved Research Tensions

1. **Persistence authority:** [STACK.md](./STACK.md) proposes Zustand `persist`/`localStorage`, while [FEATURES.md](./FEATURES.md) and [ARCHITECTURE.md](./ARCHITECTURE.md) require restart-safe, multi-tab-consistent backend authority. Adopt the backend `MappingStore` as the source of truth. Browser persistence, if retained, is only a non-authoritative draft convenience and can never prove that a mapping is applied.
2. **Stable versus transport MAC:** persist one verified full stable hardware/base MAC as `device_id`; expose the current ESP-NOW interface MAC separately for peer targeting and diagnostics. Hardware acceptance must confirm whether they coincide on deployed boards.
3. **Missing model IMU frames:** prefer exact model-authored `<body>_imu` Frames. Runtime-only deterministic frames are acceptable only after a Phase 3 spike proves safe creation/connection before `initSystem()` under OpenSim 4.5.2. Until then, fail closed with `sensor_ready=false`; never silently rewrite the source model or choose a similarly named joint/frame.
4. **High-rate Slave transport:** the preferred shape is one Master host stream carrying peer MAC with every sample and ROS fan-out by MAC. If firmware forwarding cannot preserve acquisition timing, retain independent Slave TCP/UDP streams and generalize the relay to N identity-confirmed routes. Decide this in Phase 2 through throughput evidence.
5. **Compatibility:** keep fixed Master/Slave topics, pair status, launch parameters, services, and `JointState` contract as aliases/rollback paths for v1.6. Bind the legacy Slave alias to an explicit persisted `legacy_slave_id`, never discovery order.

### Expected Features

The table stakes form one safety contract. A frontend-only mapping table is insufficient because discovery, identity, routes, model frames, calibration, and solve validity are authoritative upstream.

**Must have (table stakes):**

- **Master plus every visible Slave:** one stable MAC-keyed registry with separate ESP-NOW visibility, transport readiness, ROS topic readiness, orientation freshness, synchronization, rate, and actionable errors.
- **Stable full identity and rows:** use all 48 MAC bits; retain saved/offline rows; same-MAC reconnect updates in place; a different MAC at the old IP is a new Unassigned sensor.
- **Targeted Identify:** exactly one verified MAC, bounded non-blocking blink, command correlation, and distinct confirmed, sent-unconfirmed, timeout, offline, unsupported, and rejected outcomes.
- **Authoritative model catalog:** load through OpenSim, hash exact bytes, enumerate `BodySet` component paths excluding Ground, and resolve an exact compatible IMU Frame.
- **Explicit placement decisions:** every known device is Assigned, Not used, or Unassigned; Unassigned remains incomplete. Master participates as a wearable orientation source.
- **Uniqueness and solver preflight:** reject duplicate segments in Studio and backend; validate exact frame resolution, identity, route, at least one included sensor, and a declared solver/profile minimum.
- **Draft, Saved, Applied, Runtime Ready:** keep these four facts distinct. Saving does not change live routing, and an Apply response is not authoritative until the backend publishes the matching revision.
- **Per-model durable mapping:** backend persistence keyed by exact model hash and full device ID, with schema/revision, atomic writes, backup, corruption handling, reconnect reattachment, and no cross-hash auto-apply.
- **Transactional Apply:** submit and validate the whole candidate, stage all subscriptions/model frames/solver/visualizer, atomically swap, or leave the previous revision intact.
- **Quiescent interlocks:** allow draft editing/saving during acquisition, but block Apply during calibration capture, SD recording, and recording finalization. Never auto-stop recording.
- **Dynamic OpenSim path:** applied device-to-frame mappings drive MAC-keyed subscriptions, N-sensor calibration artifacts, deterministic N-column quaternion tables, official OpenSim IK, health, and visualizer labels.
- **Freshness and calibration hard gates:** one stale, invalid, skewed, missing, or pre-reconnect input suppresses new `JointState` while acquisition, recording, health, and Identify continue. Semantic model/mapping/frame/profile changes invalidate calibration.
- **Reason-coded observability and deterministic verification:** layered per-device/global errors, bounded payloads/queues, and fixture coverage for arbitrary order, collisions, reconnect, rollback, corrupt persistence, skew, cleanup, and recording interlocks.

**Should have after core validation:**

- Guided placement mode and a one-screen readiness matrix.
- Optional placement labels/notes that never hide or replace MAC identity.
- Applied mapping/calibration provenance in session metadata and bounded mapping audit history.
- Review-only model revision reconciliation and mapping profile import/export.
- Offline preconfiguration for known MACs while runtime readiness remains Waiting.

**Defer beyond v1.6:**

- Partial-sensor/degraded IK profiles until observability and accuracy are explicitly validated.
- Explicit derived-model export for generated Frames; never modify source `.osim` silently.
- Per-sensor orientation weights and advanced biomechanical placement calibration.
- Fleet management, OTA, battery analytics, cloud/remote operation, generic Wi-Fi provisioning, and unrelated neural/motor/EtherCAT functions.
- Clinical or biomechanical validity claims without an external-reference protocol.

### Architecture Approach

The architecture follows five rules: stable identity with mutable metadata; canonical acquisition separated from segment mapping; backend authority with Studio projection; desired versus applied configuration; and newest complete bounded-skew orientation sets. Device discovery flows from firmware identity through an identity-confirmed route registry into canonical ROS fleet topics. Mapping flows from an OpenSim-generated catalog and backend store through a full-candidate transaction into dynamic subscriptions, calibration, and one model-wide IK solve. Reconnect joins by exact device ID without changing mapping revision, while a different device remains Unassigned.

**Major components:**

1. **Master and Slave firmware** — report full base/transport identity, role/capabilities, peer visibility, and application-acknowledged non-blocking Identify without disturbing acquisition or recording.
2. **Windows STEP_ESP relay registry** — reconcile DHCP endpoints only after `IDENTITY?`, retain stable per-device local routes, isolate per-route failures/queues, and never own mapping.
3. **ROS `esp32_fleet_bridge`** — own device sessions, canonical per-MAC publishers, fleet/per-device health, Identify service forwarding, recording/control services, and canonical-to-legacy aliases.
4. **OpenSim bridge and modules** — own model hash/catalog, backend mapping store, desired/applied revisions, validation, transactional subscription/solver staging, calibration provenance, N-sensor freshness gates, IK validity, and native visualizer.
5. **rosbridge and React Studio** — consume bounded fleet/mapping/OpenSim snapshots, maintain an ephemeral draft, invoke correlated services, render stable rows and layered errors, and wait for authoritative revisions.

**Authoritative data flow:**

```text
Firmware full identity + peer status
  -> Relay device_id-to-current-route registry
  -> ROS fleet bridge canonical topics and health
  -> OpenSim backend mapping join by device_id

OpenSim-loaded model bytes
  -> SHA-256 model_id + BodySet/Frame catalog
  -> Backend desired mapping + atomic applied revision
  -> Dynamic per-MAC subscriptions + complete orientation set
  -> Revision-bound calibration + official N-sensor IK
  -> JointState/status/visualizer provenance

Studio draft
  -> Set complete candidate with expected revision
  -> Backend validation/persistence
  -> Apply staged transaction
  -> Authoritative mapping status returned to Studio
```

### Critical Pitfalls

1. **Wrong or mutable identity** — carry a normalized full 48-bit base identity end to end, keep transport MAC/IP/role separate, quarantine malformed or changing identities, and test low-32-bit collisions.
2. **Reconnect by order or IP** — reconcile MAC-keyed records, preserve offline rows/routes, flush old generations, and use an explicit `legacy_slave_id`.
3. **Partial Apply or stale model mapping** — hash model bytes, use complete candidates and optimistic revisions, stage off-line, atomically swap, and keep the previous applied solver on every failure.
4. **Ambiguous placement/frame semantics** — distinguish Unassigned from Not used, reject duplicate segments and fuzzy frame matches, use absolute component paths, and enforce solver-specific minimums.
5. **Stale/skewed solve and calibration reuse** — require complete fresh monotonic bounded-skew sets, invalidate pre-reconnect cache generations, bind calibration to model/mapping/frame/profile provenance, and suppress rather than restamp stale output.
6. **False Identify or unsafe LED behavior** — application acknowledgement with command ID, reason-coded results, verified board pin/active level, bounded duration, and no blocking callback code.
7. **Recording crossed by mapping changes** — block Apply during recording/finalization/capture, never auto-stop, and keep recording result independent from mapping status.
8. **Unbounded dynamic lifecycle** — exactly one route/session/publisher per MAC and subscription per applied sensor; bounded queues/latest-set policy, explicit destroy/unsubscribe, generation guards, and repeated-cycle leak tests.

## Implications for Roadmap

Research supports six dependency-ordered phases. Each phase should ship deterministic contract tests with its implementation; hardware scarcity is not a reason to postpone state-machine, rollback, or freshness verification.

### Phase 1: Full Identity and Confirmed Identify

**Rationale:** Persistence, routing, reconnect, and physical placement are unsafe until every layer has one verified immutable identity.

**Delivers:** Full base/transport MAC schemas; canonical normalization; Master and Slave identity/peer status; targeted non-blocking Identify packet and application ACK; mixed-version/packet-size checks; board capability reporting.

**Addresses:** Stable hardware identity, Master inclusion, targeted Identify, reason-coded command outcomes.

**Avoids:** Truncated identity, broadcast/wrong-device blink, link-layer false success, blocking LED callbacks, and unsafe guessed LED pins.

**Verification:** Low-32-bit collision fixtures; malformed/changed MAC rejection; Master plus two Slave identities; per-device ACK/timeout/unsupported/offline; unchanged sample and recording timing.

### Phase 2: N-Route Relay and Canonical ROS Fleet

**Rationale:** Discovery must become an identity-keyed data plane before mapping or Studio work can be authoritative.

**Delivers:** N-route registry; reusable isolated device sessions; canonical per-MAC IMU/raw/status topics; full fleet snapshots; reconnect generations; per-route bounded queues/drop metrics; explicit legacy aliases and rollback mode; final choice of Master-demultiplexed versus independent Slave high-rate transport.

**Addresses:** All-device discovery, layered readiness, stable rows/topics, route health, same-MAC reconnect, independent failure containment.

**Avoids:** IP/order identity, arbitrary first Slave, one route cancelling all streams, alias divergence, unbounded queues, and stale pre-reconnect samples.

**Verification:** Master plus at least two Slaves in arbitrary DHCP order; same topic after power cycle; different MAC at old IP remains new; one failed route does not stop others; canonical and alias data match; existing pair/record/frequency/range tests pass.

### Phase 3: Model Catalog, Mapping Store, and Transactional Contracts

**Rationale:** OpenSim-derived vocabulary, exact model identity, backend persistence, and atomic mapping revisions are prerequisites for dynamic calibration and UI Apply semantics.

**Delivers:** Typed mapping services; SHA-256 model catalog; exact segment/frame metadata; backend atomic mapping store with backup/corruption quarantine; complete-candidate validation; optimistic revisions; desired/applied state; staged Apply scaffold with fake adapter/solver; recording/calibration interlock contract.

**Addresses:** Model-derived segment choices, Assigned/Not used/Unassigned decisions, uniqueness, solver preflight, durable exact-hash restore, Draft/Saved/Applied distinctions, rollback.

**Avoids:** Filename identity, browser-only authority, row-by-row partial Apply, duplicate/fuzzy frames, stale model reuse, corrupt-store overwrite, and mapping changes during recording/finalization.

**Verification:** Exact same-name/different-bytes hashes; existing and missing IMU-frame models; duplicates/incomplete/unknown IDs; stale expected revision; failure at every staging step; atomic file recovery; exact-hash restart restore; changed model cannot silently reuse mapping.

### Phase 4: N-Sensor Calibration and Official OpenSim IK

**Rationale:** The current two-value calibration and quaternion table cannot safely consume dynamic mappings; generalize only after authoritative revisions and canonical topics exist.

**Delivers:** MAC-keyed latest-sample cache with source time/arrival/generation; complete-set skew/freshness gate; deterministic orientation ordering; revision-bound N-sensor calibration artifact; N-column official OpenSim 4.5.2 IK; mapping provenance in status; visualizer labels; teardown of obsolete subscriptions.

**Addresses:** Dynamic mapped inputs, calibration, official IK, stale/offline gating, deterministic solver behavior, reconnect recovery.

**Avoids:** Plausible but unsynchronized poses, stale output restamping, unbounded solve queues, partial calibration updates, reused offsets after remap, duplicate callbacks.

**Verification:** Preserve two-sensor numerical tolerance; deterministic 3+ sensor labels; fake-clock stale/skew/generation cases; one missing input stops `JointState` only; mapping/model/frame/profile changes invalidate calibration; repeated remap keeps handle counts bounded; profile solve latency as N grows.

### Phase 5: Rosbridge and Studio Mapping Workspace

**Rationale:** The UI should project stable backend contracts, not drive architecture decisions ahead of them.

**Delivers:** Strict bounded JSON parsers; fleet/mapping subscriptions; correlated Identify/set/apply calls; stable device rows; model-derived selectors; immediate conflict/incomplete feedback; Draft/Saved/Applied/Runtime Ready display; request and stale-revision handling; explicit recording/capture guidance; subscription cleanup.

**Addresses:** Dedicated mapping panel, physical identification workflow, explicit Not used, reconnect visibility, reason-coded layered errors, authoritative revision display.

**Avoids:** React array-index identity, one generic Online state, local validation as authority, browser-only applied state, row disappearance, duplicate rosbridge listeners, and Apply silently stopping recording.

**Verification:** Arbitrary status order and dropout retention; Identify correlation to one row; local and forged-backend duplicate rejection; stale-revision multi-tab scenario; reload from backend; recording/capture interlocks; existing graph, Run/Rec/Calibrate/Clear/visualizer/live-angle regressions.

### Phase 6: Multi-Device Hardware Compatibility and Promotion Gate

**Rationale:** Electrical LED behavior, MAC-interface relationships, radio load, route throughput, and 3+ sensor OpenSim performance cannot be proven solely with fixtures.

**Delivers:** Supported fleet-size statement; measured peer/status/sample load; validated board LED configuration; dynamic and legacy startup acceptance; failure/recovery matrix; documented default-mode decision.

**Addresses:** Real multi-peer discovery, physical Identify, full acquisition/recording continuity, dynamic calibration/IK, reconnect, and operator readiness.

**Avoids:** Advertising theoretical peer capacity, promoting an unvalidated dynamic default, mixed-firmware surprises, radio congestion, and loss of the legacy recovery path.

**Verification:** Master plus the lab-required Slave maximum at supported rate; recording start/stop/finalization; DHCP reorder/reconnect; lost ACK; malformed/mixed firmware; relay restart; capacity overflow; stale sensor; corrupt mapping store; model mismatch; calibration/IK/visualizer; bounded CPU/memory/queue/solve latency.

### Phase Ordering Rationale

- Identity precedes routing because no route, mapping, persistence key, or physical command is safe without a verified full device ID.
- Canonical fleet routing precedes model mapping because discovery and stream readiness are upstream facts, not UI constructs.
- Model catalog and revisioned persistence precede dynamic OpenSim because calibration and solver objects must bind to an authoritative applied model/mapping revision.
- Dynamic OpenSim precedes Studio completion so the UI exposes actual backend capabilities and statuses rather than simulated applied state.
- Compatibility aliases remain throughout; Phase 6, not implementation completion, decides when dynamic mode becomes the startup default.
- Tests are part of every phase. Phase 6 is hardware acceptance and promotion, not the first time failures are exercised.

### Research Flags

Phases likely needing deeper research or a focused spike during planning:

- **Phase 1:** verify the safe XIAO ESP32S3 LED pin/active level and actual base/AP/STA/ESP-NOW MAC relationships on every deployed board revision.
- **Phase 2:** choose and benchmark the multi-peer high-rate sample transport; measure six-peer status airtime, relay throughput, and failure isolation.
- **Phase 3:** exercise deterministic runtime `PhysicalOffsetFrame` creation/connection before `initSystem()` in the pinned OpenSim 4.5.2 Python environment; fail closed if unreliable. Define solver/profile minimum sensor rules.
- **Phase 4:** measure official OpenSim IK accuracy and latency for three or more sensors, including the static-reference fallback.
- **Phase 6:** hardware research is intrinsic: tested capacity, electrical behavior, radio load, and timing are evidence gates.

Phases with standard patterns that can skip broad research-phase:

- **Phase 5:** React keyed rows, Zustand normalized state, rosbridge correlation, schema parsing, and explicit subscription cleanup are established repository patterns once backend contracts are fixed.
- **Phase 3 persistence mechanics:** atomic JSON write/replace, backup, schema versioning, and optimistic revision checks are standard; only OpenSim frame semantics need a spike.

## Requirement Recommendations for v1.6

Translate the research into atomic, testable requirements rather than one broad “multi-sensor mapping” requirement:

1. **ID/Fleet:** Every assignable Master/Slave has a unique verified full 48-bit stable ID; discovery, liveness, route readiness, and orientation freshness are distinct; reconnect preserves identity and canonical topic.
2. **Identify:** One target at a time receives a bounded non-blocking blink; success requires application ACK and reason-coded failure behavior.
3. **Model Catalog:** Exact `.osim` bytes define `model_id`; selectable segments and resolved sensor frames come only from the loaded OpenSim model; unsupported/ambiguous frames fail closed.
4. **Mapping Decisions:** Each known device is Assigned, Not used, or Unassigned; segment assignments are unique and meet declared solver rules.
5. **Persistence/Revisions:** Desired mappings persist authoritatively in the backend by model hash/device ID with schema, atomic recovery, and optimistic revision conflict handling.
6. **Apply/Interlocks:** Apply is a whole-candidate transaction that preserves the previous revision on failure and is blocked during calibration capture and recording/finalization without altering recording.
7. **Dynamic OpenSim:** Applied mappings construct deterministic N-sensor subscriptions, calibration artifacts, orientation tables, status, visualizer mappings, and official IK inputs.
8. **Runtime Validity:** IK publishes only from complete fresh valid bounded-skew input under matching calibration provenance; degraded input suppresses new output without stopping acquisition/recording/health.
9. **Studio UX:** Stable MAC rows and authoritative Draft/Saved/Applied/Runtime Ready states expose actionable per-layer errors and never treat browser state as applied truth.
10. **Compatibility/Promotion:** Canonical and legacy paths share accepted data; an explicit legacy Slave remains stable; dynamic mode becomes default only after deterministic and hardware acceptance matrices pass.

## Testing Implications

Testing should be layered around contract boundaries and include cleanup/resource assertions, not only visible outcomes.

- **Firmware/parser fixtures:** known packet versions/sizes, full-MAC normalization/collisions, capability/ACK correlation, timeout, and non-blocking timing.
- **Relay/fleet fixtures:** arbitrary discovery order, identity changes, DHCP rebind, per-route failure, queue bounds/drops, stable aliases, and 0/1/3+/capacity cases.
- **Model/mapping fixtures:** fake `.osim` files with identical names/different bytes, existing/missing/ambiguous Frames, duplicate/incomplete candidates, revision conflicts, corrupt store/backup recovery, and staged rollback at every failure point.
- **OpenSim fixtures:** preserve current two-sensor numerical result, deterministic N-column labels, fake-clock age/skew/generation gates, calibration invalidation, stale-output suppression, subscription teardown, and solver-latency budgets.
- **Studio fixtures:** stable row identity/order, explicit Not used, layered state/error presentation, service correlation, stale-revision review, reconnect/reload, payload bounds, and unsubscribe/disposal.
- **Hardware acceptance:** physical LED safety and acknowledgement, actual MAC relationships, supported simultaneous peers, radio/relay throughput, recording/finalization, dropout/reconnect timing, and end-to-end dynamic IK/visualizer.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Repository versions and extension points were inspected; existing dependencies provide all required capabilities. Multi-peer sample transport remains MEDIUM until benchmarked. |
| Features | HIGH | Operator state semantics and safety behavior align across project requirements, ESP-NOW semantics, OpenSense expectations, and repository constraints. |
| Architecture | HIGH | Ownership boundaries, additive migration, canonical topic strategy, and six-phase dependency order are strongly supported by repository evidence. Runtime Frame generation is MEDIUM. |
| Pitfalls | HIGH | Failure modes follow directly from current pair assumptions and documented ESP-NOW/ROS/OpenSim behavior; hardware-specific limits remain MEDIUM. |

**Overall confidence:** HIGH for roadmap structure and contracts; MEDIUM for the few hardware/runtime decisions explicitly gated above.

### Gaps to Address

- **Persistence conflict:** confirm backend authoritative persistence as the milestone decision; treat Zustand persistence only as an optional draft cache.
- **Canonical identity semantics:** verify base, AP, STA, and observed ESP-NOW MAC relationships on actual boards and document which is persisted versus targeted.
- **Multi-peer sample transport:** choose Master-demultiplexed or N-route host ingress based on measured acquisition integrity and throughput.
- **Identify hardware:** establish safe LED pin, active level, capability advertisement, timeout, and application ACK packet contract.
- **OpenSim missing-frame behavior:** prove runtime-only frame creation in OpenSim 4.5.2 or require model-authored frames for v1.6.
- **Solver sufficiency:** define model/profile-specific required and optional sensor sets; the GUI must not infer biomechanical observability from a count.
- **Fleet capacity and rates:** validate the actual lab maximum, status cadence, radio airtime, relay queues, and OpenSim solve latency before publishing support claims.
- **Auto-restore semantics:** same-MAC reconnect under an unchanged applied revision should reattach automatically; exact-hash backend restart restore may reapply only after full validation and quiescent interlocks, and must never imply calibration validity.

## Sources

### Primary (HIGH confidence)

- Repository evidence in [STACK.md](./STACK.md), [FEATURES.md](./FEATURES.md), [ARCHITECTURE.md](./ARCHITECTURE.md), and [PITFALLS.md](./PITFALLS.md), including firmware, relay, ROS bridge, OpenSim, Studio, package-lock, build logs, and live WSL runtime inspection.
- Espressif ESP-NOW API — full peer MAC targeting, interface identity, peer behavior, and the limitation of MAC-layer send acknowledgement.
- ROS 2 Humble documentation — topics versus services, parameters, and `rclpy` runtime subscription lifecycle.
- Rosbridge v2 protocol — correlated service calls, subscription IDs, and unsubscribe semantics.
- OpenSim/OpenSense documentation and API guidance — IMUs as model Frames, `<bodyname>_imu` conventions, model/component enumeration, calibration, and orientation IK.
- Zustand persistence documentation — versioning, migration, and partialization for any non-authoritative browser draft cache.

### Secondary (MEDIUM confidence)

- OpenSense real-time architecture as precedent for variable sensor counts; useful architecturally but not a drop-in repository contract.
- Inferences about runtime-only `PhysicalOffsetFrame` creation and three-plus-sensor latency under the pinned OpenSim 4.5.2 Python binding, pending focused execution tests.

### Validation-Only Gaps

- XIAO ESP32S3 board-revision LED wiring/active level, actual MAC-interface relationships, maximum reliable peer load, current 100 Hz status airtime, and multi-device stream throughput.

---
*Research completed: 2026-07-30*
*Ready for roadmap: yes*
