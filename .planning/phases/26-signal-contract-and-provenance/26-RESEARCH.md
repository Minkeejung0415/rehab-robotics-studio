# Phase 26: Signal Contract and Provenance - Research

**Researched:** 2026-08-16
**Domain:** Versioned per-sample IMU identity, timing, capability, validity, unit, and applied-mapping provenance contract
**Confidence:** HIGH for repository integration and fail-closed contract design; MEDIUM for hardware-origin timing and magnetometer calibration availability

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Sample identity and time
- Every sample is keyed by normalized full MAC, never role, connection order, IP address, or a shortened label.
- Preserve acquisition timestamp and sequence when supplied; also attach a reconnect epoch so sequence/time resets cannot silently join sessions.
- Capability and validity metadata travels with the canonical sample rather than being inferred by the rendering layer.
- Missing or malformed required identity/timing fields fail closed and surface an explicit validation reason.

### Raw and physical units
- Raw signed counts for ax/ay/az, gx/gy/gz, and mx/my/mz are lossless authoritative values.
- Acceleration SI uses m/s^2 and angular-rate SI uses rad/s only when the declared range/sensitivity contract validates.
- Magnetometer SI uses microtesla only when sensitivity and calibration provenance validate; otherwise raw counts remain available and SI is explicitly unavailable.
- Conversion helpers are deterministic shared-contract logic with cross-language fixtures, not ad hoc UI formulas.

### Mapping provenance
- Labels use only the authoritative applied mapping snapshot: applied revision, exact segment, and exact model frame.
- Unsaved and saved drafts cannot relabel current or buffered samples.
- Applying a new mapping creates a new provenance epoch; historical samples keep their original labels and revision.
- Unassigned sources remain explicitly unassigned rather than inheriting a role-based body part.

### Quaternion capability and validity
- Quaternion channels are advertised only when the source declares quaternion capability and the current value passes finite/norm validity checks.
- Missing, stale, zero-norm, or malformed quaternion input is unavailable and never replaced with an identity quaternion.
- Capability absence and transient invalidity are distinct machine-readable states.
- Later consumers may display or suppress quaternion channels but cannot manufacture orientation data.

### the agent's Discretion
- Exact type/module names, schema versioning mechanism, error-code naming, and internal normalization layout may follow established repository patterns.

### Deferred Ideas (OUT OF SCOPE)
- Waveform layout and controls are Phase 29.
- Full-rate export and reconciliation are Phase 30.
- Full-body model, calibration, IK, and physical remap evidence are Phases 27, 31, and 32.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SIG-01 | Every viewer sample preserves full device MAC, acquisition timestamp or sequence, reconnect epoch, and channel-capability metadata. | Canonical sample envelope, explicit time-domain/origin fields, reconnect generation, strict MAC/topic agreement, and capability snapshot. [VERIFIED: `.planning/REQUIREMENTS.md`; codebase `fleet_bridge_node.py`] |
| SIG-02 | Operator can inspect lossless raw counts for ax/ay/az, gx/gy/gz, and mx/my/mz and switch accelerometer and gyroscope channels to validated SI values. | Signed-int16 raw truth plus the existing shared accel/gyro config validators and deterministic conversion helpers. [VERIFIED: codebase `measurement_contract.py`, `measurementContract.ts`] |
| SIG-03 | Operator can view mx/my/mz in validated microtesla using an explicit sensor-sensitivity and magnetometer-calibration contract. | Extend the shared measurement contract with magnetometer sensitivity and a calibration provenance discriminated union; SI remains unavailable until both validate. [VERIFIED: firmware `step_node*.ino`; CITED: https://invensense.tdk.com/wp-content/uploads/2024/03/eMD_Software_Guide_ICM20948.pdf] |
| SIG-04 | Viewer and export labels use only the authoritative applied mapping revision and exact segment/frame; an unsaved or saved draft never relabels live or historical samples. | Cache `applied_assignments`, not `assignments`, at sample ingestion and copy the exact snapshot into each accepted sample. [VERIFIED: codebase `mapping_node.py`, `mappingStore.ts`] |
| SIG-05 | Quaternion channels appear only when the source declares valid quaternion capability; missing or invalid orientation is never fabricated as an identity quaternion. | Separate declared capability from per-value validity and reject missing/non-finite/zero-or-out-of-tolerance norm without fallback. [VERIFIED: codebase `opensim_adapter.py`; CITED: https://docs.ros2.org/latest/api/sensor_msgs/msg/Imu.html] |
</phase_requirements>

## Summary

Phase 26 should create one immutable, versioned `CanonicalSignalSample` contract at the native per-MAC publication boundary, validate the same wire shape in Python and TypeScript, and attach all context needed by later viewer/export consumers at ingestion time. The raw signed counts remain authoritative; SI fields are derived only from a validated configuration snapshot; capability, transient validity, timing origin, reconnect generation, and applied mapping are explicit data rather than UI inference. [VERIFIED: codebase `fleet_bridge_node.py`, `measurement_contract.py`, `RosbridgeDataSource.ts`; VERIFIED: `26-CONTEXT.md`]

The present pipeline is close but not sufficient. Fleet JSON already carries full `device_id`, nine raw axes, quaternion counts, bridge-local `seq`, bridge monotonic `time_us`, and accel/gyro configuration. However, it does not attach reconnect generation, applied mapping, declared sensor capabilities, magnetometer calibration provenance, or time-domain labels. Firmware sequence is appended to `StreamRecord` but the fleet decoder discards it; no acquisition timestamp exists in that live record. The browser parser also converts absent/malformed values through `numeric(...)` to zero, falls back to `performance.now()`, always emits quaternion fields, and collapses the two role aliases into one derived `Frame`. [VERIFIED: codebase `fleet_bridge_node.py:1085-1154`, firmware `step_node*.ino` `StreamRecord`, `RosbridgeDataSource.ts:27-33,259-287`]

The applied-mapping seam requires a deliberate correction: backend `/rehab/mapping/current` publishes both draft `assignments` and immutable `applied_assignments`, but the current TypeScript snapshot/store parses only `assignments` into `backendSegment/backendFrame`. That is correct for the mapping editor but unsafe for signal labels. Signal normalization needs a distinct applied-snapshot cache and must copy its values into samples; it must never look up the current store when rendering historical data. [VERIFIED: codebase `mapping_node.py:421-442,737-743`, `mappingStore.ts:23-29,200-252`]

**Primary recommendation:** Add an additive nested `sample_contract` envelope to the existing `oe_esp32.raw.v1` JSON so legacy alias consumers continue to work, make the envelope the sole new viewer/export boundary, and accept a sample only after strict cross-language validation succeeds. [VERIFIED: compatibility behavior in `RosbridgeDataSource.ts`; recommendation is an architectural inference]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Source identity, raw values, time origin, sequence, reconnect epoch | API / Backend | Device firmware | Firmware supplies what it actually knows; backend canonicalizes full MAC and explicitly labels bridge-derived fallbacks. [VERIFIED: codebase] |
| Capability declaration | Device firmware | API / Backend | Capability must originate with source status/config and be snapshotted into the canonical sample, not inferred from nonzero data. [VERIFIED: firmware status fields; locked decision] |
| Accel/gyro/magnetometer conversion contract | API / Backend | Browser / Client | Pure backend logic defines/serializes the contract; TypeScript independently validates and deterministically reproduces conversions. [VERIFIED: existing cross-language pattern] |
| Applied mapping labels and mapping epoch | API / Backend | Browser / Client | Authoritative `applied_assignments` is backend-owned; browser retains the per-sample copy. [VERIFIED: `mapping_node.py`] |
| Wire validation and viewer normalization | Browser / Client | API / Backend | The browser validates untrusted rosbridge JSON and emits a canonical typed sample or an explicit rejection, while backend emits the canonical form. [VERIFIED: existing guard-parser pattern] |
| Historical label retention | Browser / Client | Recording backend (Phase 30) | Buffered samples own immutable provenance; a view must not perform a late join against mutable mapping state. [VERIFIED: locked decision] |

## Standard Stack

### Core

| Library / Module | Version | Purpose | Why Standard |
|------------------|---------|---------|--------------|
| Python stdlib dataclasses / `math` / `json` | Python 3.12.10 locally | Backend immutable contracts, finite/range/norm validation, deterministic serialization | The existing contract module is pure stdlib and testable without ROS. [VERIFIED: local environment; codebase] |
| TypeScript | Existing 5.6.3 constraint | Frontend interfaces, discriminated results, strict guard parsing | Already installed and used for explicit wire contracts. [VERIFIED: `package.json`] |
| Node `node:test` through `tsx` | Node 24.18.0; `tsx` 4.23.1 | Cross-language fixtures and frontend parser tests | This is the actual project test runner; Vitest is not installed. [VERIFIED: local environment; `package.json`; milestone Phase 24 summaries] |
| Python `unittest` / pytest collection | pytest 9.1.1 locally | Backend pure-contract and fleet publication tests | Existing tests use unittest classes and collect under pytest. [VERIFIED: local environment; `backend/test`] |
| ROS 2 `std_msgs/msg/String` per-MAC topics | Existing project contract | Carry additive canonical JSON without replacing legacy typed OpenSim topics | Current per-MAC and alias paths already publish identical JSON. [VERIFIED: `fleet_bridge_node.py`] |

### Supporting

| Library / Primitive | Version | Purpose | When to Use |
|---------------------|---------|---------|-------------|
| Existing shared JSON fixture pattern | Project-owned | Prove Python and TypeScript accept/reject and convert identical cases | Use for all SIG-01..05 partitions, including exact failure codes. [VERIFIED: `measurement_contract_cases.json`, `measurementContract.test.ts`] |
| Existing full-MAC normalization helpers | Project-owned | Canonical `esp32:<12 lowercase hex>` identity and `mac_<12hex>` topic token | Reuse at backend emission; mirror strict validation at browser ingress. [VERIFIED: `esp32_bridge_node.py`] |
| Existing `opensim_adapter` quaternion validator | Project-owned | Established finite/near-zero/norm error semantics | Extract/shared pure policy or align the new contract fixtures with it; do not invent a second tolerance silently. [VERIFIED: `opensim_adapter.py:78-100`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Additive nested contract in existing raw JSON | New ROS custom message/topic | A custom message gives compile-time ROS typing but expands interface generation and rosbridge deployment; additive JSON preserves the current compatibility path. [VERIFIED: current transport; inference] |
| Explicit hand-written validators | Add Zod or another schema package | A package would duplicate the established zero-dependency pure contract pattern and introduce an unnecessary install/audit. [VERIFIED: codebase; inference] |
| Per-sample applied snapshot | Late join to current mapping store | Late join is smaller on the wire but violates immutable historical labels after Apply/remap. [VERIFIED: locked decision] |

**Installation:** None. This phase should add no external packages. [VERIFIED: repository capabilities and phase scope]

## Architecture Patterns

### System Architecture Diagram

```text
Device stream/status
  | raw int16 channels, device seq when available, capability/status facts
  v
Fleet session decoder -- invalid frame --> reject counter + reason (no publication)
  | full MAC + explicitly labelled source/bridge time + reconnect generation
  v
Canonical sample builder <----- applied mapping cache from /rehab/mapping/current
  |                              (uses applied_assignments only)
  |-- validates measurement config / mag calibration / quaternion
  |-- snapshots capability, validity, SI availability, exact mapping provenance
  v
/esp/raw/mac_<12hex> std_msgs/String
  | additive legacy fields + sample_contract schema
  v
Rosbridge strict parser -- topic/MAC/schema mismatch --> reject metric + reason
  |
  +--> CanonicalSignalSample subscribers (later viewer/export)
  |
  +--> existing legacy alias Frame path remains unchanged
```

[VERIFIED: current project boundaries; recommended enrichment stages are an architectural inference]

### Recommended Project Structure

```text
backend/rehab_robotics_bridge/
├── measurement_contract.py       # extend config + deterministic SI helpers
├── signal_contract.py            # canonical sample builder/validator, no ROS imports
├── fleet_bridge_node.py           # attach session, capability, time, mapping snapshots
backend/test/
├── fixtures/signal_contract_cases.json
├── test_signal_contract.py
├── test_measurement_contract.py
└── test_fleet_bridge.py
rehab-robotics-studio/src/
├── types/signals.ts               # canonical sample interfaces; leave legacy Frame intact
├── data/measurementContract.ts    # matching config/SI validation
├── data/signalContract.ts         # strict unknown -> CanonicalSignalSample parser
├── data/signalContract.test.ts
├── data/RosbridgeDataSource.ts    # route canonical per-MAC payloads separately
└── state/mappingStore.ts          # retain separate applied snapshot for editor/status use
```

[VERIFIED: existing structure; new filenames are discretionary recommendations]

### Pattern 1: One Accepted Sample Owns Its Meaning

**What:** Build a frozen/logically immutable sample whose identity, clocks, epochs, raw values, validated configuration, capabilities, validity, and applied mapping are copied together. [VERIFIED: locked decisions]

**When to use:** At backend publication and again after browser wire validation. Never enrich during render/export. [VERIFIED: phase boundary]

**Recommended logical shape:** [ASSUMED]

```typescript
type AvailabilityReason =
  | 'available'
  | 'capability_absent'
  | 'stale'
  | 'missing'
  | 'malformed'
  | 'non_finite'
  | 'zero_norm'
  | 'norm_out_of_range'
  | 'config_invalid'
  | 'calibration_missing'
  | 'calibration_invalid';

interface CanonicalSignalSample {
  schema: 'rehab.signal_sample.1';
  deviceId: `esp32:${string}`;
  topicToken: `mac_${string}`;
  timing: {
    sequence: number;
    sequenceOrigin: 'device' | 'bridge_session';
    acquisitionTimeUs: number | null;
    acquisitionClock: string | null;
    bridgeMonotonicTimeUs: number;
  };
  epochs: {
    reconnect: number;
    appliedMapping: number;
  };
  raw: {
    accel: readonly [number, number, number];
    gyro: readonly [number, number, number];
    magnetometer: readonly [number, number, number];
    quaternion: readonly [number, number, number, number] | null;
  };
  capabilities: {
    accel: true;
    gyro: true;
    magnetometer: boolean;
    quaternion: boolean;
  };
  validity: {
    accel: AvailabilityReason;
    gyro: AvailabilityReason;
    magnetometer: AvailabilityReason;
    quaternion: AvailabilityReason;
  };
  conversion: ValidatedMeasurementContract;
  appliedMapping: {
    revision: number;
    state: 'assigned' | 'unassigned';
    segment: string | null;
    frame: string | null;
    modelHash: string | null;
  };
}
```

### Pattern 2: Capability and Validity Are Orthogonal

**What:** Capability describes whether a source declares a channel group; validity describes whether this particular sample is usable. A capable quaternion can be transiently `stale` or `zero_norm`; an incapable source is `capability_absent`. [VERIFIED: locked decision]

**When to use:** Magnetometer and quaternion groups. Raw magnetometer counts can remain present for inspection while SI availability is separately `calibration_missing`. [VERIFIED: SIG-03 and context]

### Pattern 3: Explicit Clock and Sequence Origins

**What:** Preserve a device acquisition timestamp/sequence when actually supplied. If only bridge receipt time or a session-local counter exists, retain it under an honest origin/domain field rather than relabelling it acquisition time. [CITED: https://design.ros2.org/articles/clock_and_time.html; VERIFIED: current fleet code]

**When to use:** Every sample. The uniqueness/order fence is `(deviceId, reconnectEpoch, sequenceOrigin, sequence)`; cross-device synchronization must not be inferred from bridge receipt times. [VERIFIED: locked decision; CITED: ROS clock design]

### Pattern 4: Applied Snapshot, Never Draft Join

**What:** On `/rehab/mapping/current`, validate and cache `applied_revision`, `applied_assignments`, and `model_hash`. Each sample copies the exact applied entry for its full MAC. If absent, write explicit `unassigned` with null segment/frame. [VERIFIED: `mapping_node.py` payload]

**When to use:** Backend canonical builder and frontend normalizer. `assignments`, `draftSegment`, and role/body aliases are forbidden label sources. [VERIFIED: locked decision]

### Pattern 5: Additive Compatibility Envelope

**What:** Keep existing `topic_schema: oe_esp32.raw.v1` and legacy fields for current panels, and add `sample_contract: { schema: rehab.signal_sample.1, ... }`. New consumers require and validate the nested contract; old consumers ignore it. [VERIFIED: existing exact-v1 legacy parser; recommendation is an inference]

**When to use:** During Phase 26 so later phases can migrate independently without breaking the alias-derived dashboard. Remove or version old fields only in a separately planned compatibility change. [VERIFIED: phase boundary]

### Anti-Patterns to Avoid

- **`numeric(value)` zero defaults:** Missing/malformed identity, timing, channel, or quaternion data must reject or become explicitly unavailable, never zero. [VERIFIED: current risk in `RosbridgeDataSource.ts`; locked decision]
- **`performance.now()` time fallback hidden as acquisition time:** Preserve it only as labelled browser receipt time if useful; it cannot replace required sample timing. [VERIFIED: current parser; locked decision]
- **Quaternion identity fallback:** `[1,0,0,0]` is a real orientation, not an absence marker. [CITED: https://docs.ros2.org/latest/api/sensor_msgs/msg/Imu.html]
- **Inferring magnetometer from nonzero axes:** A valid magnetic field can contain a zero component, while current firmware emits three zeroes when the sensor is unavailable. Use declared capability/status. [VERIFIED: firmware `step_node*.ino:3477-3509`]
- **Using `mappingRevision === appliedRevision` plus draft `assignments` as provenance:** The backend already exposes `applied_assignments`; use it directly. [VERIFIED: `mapping_node.py`, `mappingStore.ts`]
- **Late historical relabelling:** Never compute display/export labels by reading current mapping state after ingestion. [VERIFIED: locked decision]
- **Rounding/normalizing authoritative raw quaternion counts in storage:** Validate a derived normalized orientation separately; keep received components unchanged for provenance. [VERIFIED: raw-authority principle; quaternion recommendation]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Full-MAC parsing | Role/order/IP-based identity or permissive string cleanup | Existing `normalize_device_id`, `display_mac`, `device_topic_token` rules plus matching TS guard | Identity rules and topics already depend on this canonical form. [VERIFIED: codebase] |
| Accel/gyro conversion | Component-level UI formulas | Existing Python/TS measurement contract and shared fixture | Range/sensitivity consistency and exact constants are already tested. [VERIFIED: codebase] |
| Quaternion validation | UI truthiness or identity replacement | Align with existing `opensim_adapter` finite/near-zero/norm checks and shared fixtures | Avoids contradictory validity semantics between viewer and OpenSim. [VERIFIED: codebase] |
| Applied mapping history | Lookups against Zustand draft/current rows | Backend `applied_assignments` snapshot copied per sample | Draft and applied states are already separate in the authoritative store. [VERIFIED: codebase] |
| Schema validation dependency | New general-purpose validation package | Pure discriminated validators matching established TypeScript/Python patterns | No dependency is needed for the bounded schema. [VERIFIED: existing patterns; inference] |

**Key insight:** The difficult part is not numeric conversion; it is preserving the source and validity of every fact so a plausible default can never masquerade as measured data. [VERIFIED: requirements and observed gaps]

## Common Pitfalls

### Pitfall 1: Calling Bridge Receipt Time “Acquisition Time”

**What goes wrong:** Samples appear synchronized or continuous even though timestamps were assigned after network delivery. [VERIFIED: current `time.monotonic_ns()` publication]

**Why it happens:** `time_us` has no origin/domain label, and the browser treats it as the sample timestamp. [VERIFIED: codebase]

**How to avoid:** Split `acquisitionTimeUs` from `bridgeMonotonicTimeUs`; require an origin enum and nullable acquisition clock. Preserve firmware sequence when protocol work makes it available. [CITED: https://design.ros2.org/articles/clock_and_time.html]

**Warning signs:** Cross-device skew claims based only on receipt timestamps; reset sequence accepted without reconnect epoch. [VERIFIED: milestone research]

### Pitfall 2: Believing Firmware Sequence Is Already Preserved

**What goes wrong:** The backend emits `frame_index` as both `sample_index` and `seq`, while the device `StreamRecord.seq` bytes are skipped during header resynchronization. [VERIFIED: firmware `StreamRecord`; `fleet_bridge_node.py:1085-1140`]

**Why it happens:** The Open Ephys header describes only 14 int16 channels; the decoder consumes header plus channel payload, not the appended uint32. [VERIFIED: codebase]

**How to avoid:** Plan an explicit compatible stream framing update or label the current counter `bridge_session` and do not claim device sequence. Add byte-level fixture tests for old and extended frames. [VERIFIED: codebase; recommendation]

**Warning signs:** Device sequence gaps never appear even when firmware stream queue reports drops. [VERIFIED: firmware/backend separation]

### Pitfall 3: Capability Inferred from Values

**What goes wrong:** `mx=my=mz=0` can mean unavailable firmware fallback, and quaternion counts exist even when capability/staleness is not declared. [VERIFIED: firmware]

**Why it happens:** Capability/status flags exist in firmware diagnostics but not the live sample JSON contract. [VERIFIED: firmware and fleet payload]

**How to avoid:** Carry verified source status/config into the fleet session and snapshot capability per sample; use a separate transient validity result. [VERIFIED: requirements; recommendation]

**Warning signs:** Quaternion channels always appear; zero magnetometer axes are labelled microtesla. [VERIFIED: current browser type/payload]

### Pitfall 4: Magnetometer Scale Without Calibration Provenance

**What goes wrong:** Multiplying AK09916 counts by 0.15 produces scaled sensor-frame values but does not prove hard-/soft-iron calibration or its identity, so SIG-03 would be overstated. [VERIFIED: firmware scale; no calibration contract found in codebase]

**Why it happens:** Firmware contains `kMagUnitsPerLsb = 0.15f`, but no reviewed live calibration artifact/version/hash is attached. [VERIFIED: firmware grep]

**How to avoid:** Represent sensitivity and calibration as separately validated fields. Raw remains available when calibration is absent; `microtesla` conversion availability is false with `calibration_missing`. [VERIFIED: locked decision]

**Warning signs:** A unit label exists without calibration ID/hash, sensor model, axis convention, or coefficient snapshot. [VERIFIED: requirements]

### Pitfall 5: Draft Assignment Leaks into Samples

**What goes wrong:** Saving or editing a mapping changes current/historical labels before Apply. [VERIFIED: risk from current frontend `assignments` parsing]

**Why it happens:** The editor’s `backendSegment` reads `assignments`, while provenance requires `applied_assignments`. [VERIFIED: codebase]

**How to avoid:** Maintain two explicitly named caches/types; canonical samples accept only the applied cache. Add fixtures where revision advances but applied revision/assignments stay unchanged. [VERIFIED: backend state machine]

**Warning signs:** Label changes after SetAssignment, before successful Apply acknowledgement. [VERIFIED: locked decision]

### Pitfall 6: One Boolean “valid” Erases Diagnostics

**What goes wrong:** Consumers cannot distinguish unsupported, stale, malformed, bad norm, and missing calibration. [VERIFIED: requirements]

**How to avoid:** Use stable machine-readable reason codes with optional sanitized detail; test every rejection/availability partition cross-language. [VERIFIED: existing `ValidateResult` pattern]

## Code Examples

Verified patterns from repository and official sources:

### Fail-Closed TypeScript Parse Result

```typescript
// Source: existing rehab-robotics-studio/src/data/measurementContract.ts pattern
export type ValidateResult<T> =
  | { ok: true; value: T }
  | { ok: false; reason: string };

export function parseCanonicalSample(raw: unknown): ValidateResult<CanonicalSignalSample> {
  if (!isRecord(raw)) return { ok: false, reason: 'sample_not_object' };
  if (!isCanonicalMac(raw.device_id)) return { ok: false, reason: 'device_id_invalid' };
  // Validate integer/range/domain/config/capability/provenance partitions explicitly.
  return { ok: true, value: canonical };
}
```

[VERIFIED: codebase pattern; function body is recommended pseudocode]

### Quaternion Availability Without Fabrication

```python
# Source: backend/rehab_robotics_bridge/opensim_adapter.py validation pattern
def quaternion_validity(values, *, capable: bool, stale: bool, min_norm: float, max_norm: float):
    if not capable:
        return None, "capability_absent"
    if stale:
        return None, "stale"
    if values is None or len(values) != 4:
        return None, "missing"
    if not all(math.isfinite(float(v)) for v in values):
        return None, "non_finite"
    norm = math.sqrt(sum(float(v) * float(v) for v in values))
    if norm == 0.0:
        return None, "zero_norm"
    if not min_norm <= norm <= max_norm:
        return None, "norm_out_of_range"
    return tuple(values), "available"
```

[VERIFIED: existing error categories; exact tolerances remain a discretionary implementation decision]

### Applied Mapping Snapshot

```python
# Source: backend/rehab_robotics_bridge/mapping_node.py get_state_dict shape
entry = applied_snapshot["applied_assignments"].get(device_id)
mapping = {
    "revision": applied_snapshot["applied_revision"],
    "state": "assigned" if entry and entry.get("state") == "assigned" else "unassigned",
    "segment": entry.get("segment") if entry and entry.get("state") == "assigned" else None,
    "frame": entry.get("frame") if entry and entry.get("state") == "assigned" else None,
    "model_hash": applied_snapshot.get("model_hash") or None,
}
```

[VERIFIED: codebase payload; recommended sample-copy logic]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Role aliases `/esp/raw/master|slave` collapsed into one SI `Frame` | Separate canonical per-MAC raw topics already exist and should feed a dedicated signal contract | Phase 21 fleet work | Phase 26 can preserve full identity without breaking legacy panels. [VERIFIED: milestone/codebase] |
| One mutable mapping `assignments` view | Backend persists both draft `assignments` and immutable `applied_assignments` plus `applied_revision` | Phase 22/24 mapping work | Provenance can use authoritative applied state, but frontend parsing must expose it. [VERIFIED: milestone/codebase] |
| Implicit zero/fallback handling | Explicit discriminated unavailable/rejection reasons | Phase 26 target | Prevents plausible fabricated orientation, magnetometer, identity, or timing values. [VERIFIED: requirements] |
| Accel/gyro-only measurement config | Extend to explicit magnetometer sensitivity plus calibration provenance | Phase 26 target | Microtesla is gated; raw counts remain inspectable. [VERIFIED: requirements] |

**Deprecated/outdated:**

- `Frame.imu.quat` as the new viewer boundary: it requires a quaternion and has no MAC, raw counts, magnetometer, capabilities, validity, epochs, or mapping provenance. Keep it only for legacy graph/dashboard behavior. [VERIFIED: `signals.ts`]
- `numeric(...)` for safety- or biomechanics-relevant parsing: it converts absence/malformed input to zero. [VERIFIED: `RosbridgeDataSource.ts`]
- Draft `assignments` as applied labels: authoritative labels must use `applied_assignments`. [VERIFIED: context and backend schema]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The recommended public type/schema names (`CanonicalSignalSample`, `rehab.signal_sample.1`) will be adopted. [ASSUMED] | Architecture Patterns | Low; naming is explicitly at the agent's discretion. |
| A2 | An additive nested envelope is preferable to a new ROS custom message in this phase. [ASSUMED] | Standard Stack / Pattern 5 | Medium; a custom message would change plan/task boundaries and launch/interface work. |
| A3 | Exact quaternion norm thresholds can align with the existing OpenSim validator after fixture review. [ASSUMED] | Pattern 2 / Code Examples | Medium; wrong tolerances could suppress valid quantized values or accept corrupted ones. |

## Open Questions

1. **How will live source capability reach each fleet session?**
   - What we know: firmware diagnostics contain `icm_ok`, `mag_ok`, `filter`, and slave `quat_enabled`, while identity capability bits currently cover Identify only; fleet raw JSON carries none of these declarations. [VERIFIED: firmware and fleet code]
   - What's unclear: whether the preferred compatible change is an extended stream header, a verified status query at bind/config changes, or new identity capability bits. [VERIFIED: codebase gap]
   - Recommendation: make this a Wave 0 protocol decision and byte-level fixture; do not infer capability from channel contents. [VERIFIED: locked decision]

2. **Can acquisition time and device sequence be added without breaking old stream readers?**
   - What we know: device `seq` exists in `StreamRecord` but is not decoded; acquisition time is absent from live `StreamRecord`, though recording rows contain `time_us`. [VERIFIED: firmware/backend]
   - What's unclear: the exact backward-compatible framing/version negotiation. [VERIFIED: codebase gap]
   - Recommendation: preserve current bridge-session sequence/time with honest origins immediately, then add versioned device metadata only if byte framing can be proven against old/new fixtures. SIG-01 can fail closed without pretending bridge time is acquisition time. [VERIFIED: requirements; recommendation]

3. **What calibration artifact authorizes magnetometer SI?**
   - What we know: deployed firmware names AK09916 and uses 0.15 units/LSB; no hard-/soft-iron calibration contract was found in firmware, backend, or frontend. [VERIFIED: codebase]
   - What's unclear: coefficient source, axis convention, calibration procedure, persistence, ID/hash, validity dates/temperature scope. [VERIFIED: gap]
   - Recommendation: implement the schema and unavailable path now; enable microtesla only when an explicit validated artifact is supplied. Do not block raw magnetometer delivery. [VERIFIED: locked decision]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Backend contract/tests | ✓ | 3.12.10 | — |
| pytest | Focused backend collection | ✓ | 9.1.1 | stdlib `unittest` commands |
| Node.js | Frontend contract/tests | ✓ | 24.18.0 | — |
| npm | Frontend scripts | ✓ | 11.16.0 | — |
| Arduino CLI | Firmware protocol compilation if chosen | ✓ | 1.5.1 | Byte-level fixtures can validate contract work before hardware compile |
| ROS 2 CLI | Live integration smoke | ✗ | — | Pure ROS-stub unit tests; live smoke must run in configured ROS environment |
| OpenSim Python | Not required by Phase 26 contract | ✗ | — | Existing pure quaternion validator semantics and tests |

[VERIFIED: local command probes on 2026-08-16]

**Missing dependencies with no fallback:** None for contract implementation and unit validation. A live ROS smoke requires the project deployment environment but does not block pure contract planning. [VERIFIED: test architecture]

**Missing dependencies with fallback:** ROS 2 CLI (ROS-stub tests locally); OpenSim is outside this phase. [VERIFIED: local environment and scope]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Python `unittest` classes under pytest 9.1.1; Node `node:test` through `tsx` 4.23.1 [VERIFIED: codebase/local] |
| Config file | No dedicated pytest config; frontend command is defined in `rehab-robotics-studio/package.json` [VERIFIED: codebase] |
| Quick run command | `$env:PYTHONPATH='backend'; python -m pytest backend/test/test_signal_contract.py backend/test/test_measurement_contract.py backend/test/test_fleet_bridge.py -q; cd rehab-robotics-studio; npm exec -- tsx --test src/data/signalContract.test.ts src/data/measurementContract.test.ts src/state/mappingStore.test.ts` [ASSUMED: proposed new test files] |
| Full suite command | `$env:PYTHONPATH='backend'; python -m pytest backend/test -q; cd rehab-robotics-studio; npm test; npm run typecheck` [VERIFIED: current test infrastructure] |

Baseline evidence: existing focused backend measurement/fleet/mapping suite passes 80 tests plus 90 subtests; focused rosbridge/mapping frontend suite passes 64 tests on 2026-08-16. [VERIFIED: local test runs]

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SIG-01 | Full MAC/topic agreement, required sequence/time origin, reconnect epoch, capability snapshot; malformed required fields reject with exact reason | shared fixture + backend/frontend unit | `python -m pytest backend/test/test_signal_contract.py -k identity_time -q`; `npm exec -- tsx --test src/data/signalContract.test.ts` | ❌ Wave 0 |
| SIG-02 | Every int16 boundary count round-trips losslessly; all accel/gyro ranges convert identically in Python/TS; invalid config makes SI unavailable | shared fixture + unit | `python -m pytest backend/test/test_measurement_contract.py -q`; `npm exec -- tsx --test src/data/measurementContract.test.ts` | ✅ extend existing |
| SIG-03 | 0.15 sensitivity alone is insufficient; missing/invalid calibration yields raw + explicit SI unavailable; valid coefficient fixture yields expected µT | shared fixture + unit | `python -m pytest backend/test/test_signal_contract.py -k magnetometer -q`; frontend contract test | ❌ Wave 0 |
| SIG-04 | Save/draft does not change sample label; Apply changes only subsequent sample epoch; earlier sample retains exact segment/frame/revision; unassigned stays unassigned | backend state/integration + frontend unit | `python -m pytest backend/test/test_mapping_node.py backend/test/test_fleet_bridge.py -k applied -q`; frontend mapping/signal tests | ✅ extend existing |
| SIG-05 | Incapable vs capable-invalid are distinct; missing/nonfinite/zero/bad-norm reject availability; no identity fallback; valid component order retained | shared fixture + unit | `python -m pytest backend/test/test_signal_contract.py -k quaternion -q`; frontend contract test | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** Run the contract module and directly touched fleet/mapping/frontend tests. [VERIFIED: existing workflow pattern]
- **Per wave merge:** Run the full backend tests, frontend `npm test`, and TypeScript typecheck. [VERIFIED: existing scripts]
- **Phase gate:** Full suite green plus one deterministic end-to-end synthetic sequence covering baseline → draft/save → Apply → reconnect, with immutable before/after samples and explicit rejection counters. [VERIFIED: phase requirements; recommended acceptance]

### Wave 0 Gaps

- [ ] `backend/test/fixtures/signal_contract_cases.json` — shared accept/reject/conversion/provenance cases for SIG-01..05. [ASSUMED: proposed path]
- [ ] `backend/test/test_signal_contract.py` — pure backend builder/validator tests without ROS. [ASSUMED: proposed path]
- [ ] `rehab-robotics-studio/src/data/signalContract.test.ts` — consumes the same JSON fixture and asserts identical reason codes/results. [ASSUMED: proposed path]
- [ ] Byte-level old/new stream-frame fixture if firmware sequence/capability framing is extended. [ASSUMED: protocol decision dependent]
- [ ] Extend `mappingStore.test.ts` with payloads where `assignments` differs from `applied_assignments`. [VERIFIED: identified gap]
- [ ] Extend `test_fleet_bridge.py` with reconnect generation, applied snapshot, capability, and time-origin publication assertions. [VERIFIED: identified gap]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Device identity verification exists upstream; this phase does not introduce authentication. [VERIFIED: scope] |
| V3 Session Management | no | Reconnect epoch is data provenance, not an authenticated user session. [VERIFIED: scope] |
| V4 Access Control | no | No new commands or authorization surfaces are added. [VERIFIED: scope] |
| V5 Input Validation | yes | Strict allowlisted schema, canonical MAC/topic agreement, finite/integer/range/norm checks, bounded strings, and fail-closed discriminated results. [VERIFIED: requirements and existing pattern] |
| V6 Cryptography | no | No cryptographic primitive is required; calibration/model hashes are identifiers, not authenticity proofs. [VERIFIED: scope] |

### Known Threat Patterns for ROS JSON / Browser Boundary

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Payload MAC disagrees with subscribed topic | Spoofing | Derive expected full MAC from validated registry token and require exact payload equality before acceptance. [VERIFIED: milestone research] |
| NaN/Infinity, oversized numbers, negative epochs, or fractional counts | Tampering | Explicit finite integer/range validation; reject with bounded reason code. [VERIFIED: requirements] |
| Draft/current mapping injected as provenance | Tampering / Repudiation | Accept labels only from backend applied snapshot and copy revision/segment/frame per sample. [VERIFIED: locked decision] |
| Unbounded error detail or labels rendered/exported | Denial of Service / Injection | Stable allowlisted reason codes, bounded model/segment/frame strings, render as text, escape later CSV output. [VERIFIED: milestone security research] |
| Capability fabricated from channel contents | Spoofing | Require source declaration and distinguish absence from transient invalidity. [VERIFIED: locked decision] |

## Sources

### Primary (HIGH confidence)

- Repository `backend/rehab_robotics_bridge/fleet_bridge_node.py` — current per-MAC payload, receipt time, bridge sequence, reconnect registry, and publication seams.
- Repository `backend/rehab_robotics_bridge/measurement_contract.py` and frontend `measurementContract.ts` — established pure cross-language conversion/validation pattern.
- Repository `backend/rehab_robotics_bridge/mapping_node.py` and frontend `mappingStore.ts` — draft/applied state separation and current frontend applied-provenance gap.
- Repository firmware `step_node/step_node.ino` and `step_node_slave/step_node_slave.ino` — stream framing, sequence, magnetometer scale/status, fallback zeros, quaternion enable/status.
- Repository `backend/rehab_robotics_bridge/opensim_adapter.py` — established quaternion finite/near-zero/norm validation.
- [ROS Clock and Time design](https://design.ros2.org/articles/clock_and_time.html) — explicit clock domains and steady/system/ROS time distinctions.
- [ROS sensor_msgs/Imu definition](https://docs.ros2.org/latest/api/sensor_msgs/msg/Imu.html) — SI units and official unavailable-estimate convention.
- [REP 145 IMU conventions](https://ros.org/reps/rep-0145.html) — consistent sensor frames, magnetometer Tesla units, and separate raw/fused capability conventions.
- [TDK ICM-20948 software guide](https://invensense.tdk.com/wp-content/uploads/2024/03/eMD_Software_Guide_ICM20948.pdf) — ICM-20948 contains the AK09916-based magnetometer.

### Secondary (MEDIUM confidence)

- [Digi-Key mirror of AK09916 datasheet](https://www.digikey.hk/htmldatasheets/production/2044105/0/0/1/ak09916.html) — corroborates nominal 0.15 µT/LSB; deployed scale is independently verified in project firmware.
- `.planning/research/STACK.md`, `ARCHITECTURE.md`, and `PITFALLS.md` — milestone-level analysis cross-checked against live code.

### Tertiary (LOW confidence)

- None. Unresolved design choices are marked `[ASSUMED]` and listed in the Assumptions Log.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — no new dependency is needed; existing pure Python/TypeScript and test patterns are confirmed locally. [VERIFIED: codebase/local]
- Architecture: HIGH — canonical per-MAC, mapping, and rosbridge seams are present and inspected; additive envelope naming remains discretionary. [VERIFIED: codebase]
- Pitfalls: HIGH — identity/time/default/mapping/capability failures are directly observable in current code. [VERIFIED: codebase]
- Magnetometer SI readiness: MEDIUM — sensor/scale are present, but calibration provenance is not. [VERIFIED: firmware/codebase gap]
- Acquisition timing readiness: MEDIUM — firmware sequence exists but is not decoded, and acquisition timestamp is absent from the live stream record. [VERIFIED: codebase]

**Research date:** 2026-08-16
**Valid until:** 2026-09-15 (30 days; project contract is stable, but live firmware/protocol may change)
