# Phase 23: N-Sensor Calibration and Official OpenSim IK - Research

**Researched:** 2026-08-05
**Domain:** ROS 2 Python backend — dynamic subscription management, calibration artifact persistence, sync-skew enforcement, OpenSim IK integration
**Confidence:** HIGH (all findings are from direct codebase inspection; no external libraries are being added)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Subscription Lifecycle (IK-01)**
- D-01: On each `/rehab/mapping/current` update, `opensim_node` compares incoming device-to-Frame list against active subscription dict. Subscriptions for removed MACs are explicitly destroyed (`node.destroy_subscription(sub)`). New MACs get new subscribers to `/esp/raw/mac_<12hex>`. No orphan subscribers after remap.
- D-02: Input dict keyed by `device_id` (canonical `esp32:aabbccddeeff`). Each entry holds: subscription handle, latest frame payload, last_seen_ts, post_reconnect_fresh (bool). On subscription destroy, entry removed atomically under a threading.Lock.
- D-03: Deterministic input ordering: alphabetical sort by `device_id` string. This is the canonical order passed to the OpenSim solver. Order is locked on Apply and stored in calibration artifact.

**Calibration Artifacts (IK-02)**
- D-04: Calibration artifact file: `~/.ros/rehab_robotics/calibration_<model_hash[:8]>_rev<applied_revision>.json`. Schema: `{schema_version: "calib.v1", model_hash, applied_revision, device_order: [device_id, ...], frame_assignments: {device_id: {segment, frame}}, solver_profile, calibrated_at_iso8601, reference_pose: {device_id: {qw,qx,qy,qz}}}`.
- D-05: Artifact is invalidated (calibration state reset to `uncalibrated`) when: model_hash changes, applied_revision changes, or device-to-Frame assignment set changes.
- D-06: Calibration capture collects reference poses (one quaternion per assigned device) at the moment the operator triggers capture. Stored in artifact. The calibration service (`/rehab/calibration/capture`) already exists or is created here; it publishes `/rehab/calibration/status` (String JSON: `{state: "capturing"|"calibrated"|"uncalibrated", revision, model_hash}`).

**Sync-Skew Enforcement (IK-03)**
- D-07: `sync_skew_ms` ROS param (default 50). Each IK solve cycle checks `abs(device_ts - reference_ts) <= sync_skew_ms` for all required inputs. Reference timestamp is the median of all input timestamps in the current batch.
- D-08: If any required input exceeds skew bound or `post_reconnect_fresh == False` → suppress IK output for that cycle. Acquisition and recording continue unaffected. `/rehab/opensim/input_validity` (String JSON) published each cycle with per-device validity flags.
- D-09: `post_reconnect_fresh` set to `False` on fleet registry reconnect event; set to `True` on first frame received after reconnect.

**IK Engine (IK-04)**
- D-10: Existing `opensim_orientation_ik.py` adapter is reused. It already accepts a list of (frame_path, quaternion) pairs. Phase 23 wires it to receive the mapped N-sensor inputs in deterministic order from D-03.
- D-11: IK output topic `/rehab/opensim/joint_states` (existing) extended with metadata: `{mapping_revision, calibration_identity (calib artifact filename or null), input_validity_mask, solver_status, visualizer_provenance}`.
- D-12: Solver profile from `solver_profile` ROS param (default `"lower_body"`). Passed through to artifact and IK adapter. Phase 22 deferred hard-block enforcement to Phase 23 — enforce here: Apply validation in mapping_node upgraded to hard-block `solver_insufficient` if required frame count not met for current profile.

**Node Architecture**
- D-13: Extend `opensim_node.py` (not a new node). New responsibilities added: subscribe to `/rehab/mapping/current`, manage N-sensor input subscriptions, load/validate calibration artifact, enforce skew gate, publish `/rehab/calibration/status` and `/rehab/opensim/input_validity`.
- D-14: All subscription management under `self._input_lock = threading.Lock()`. Remap is safe to call from ROS callback thread.

### Claude's Discretion
- Exact `/rehab/calibration/capture` service request/response fields (suggest: empty request → {outcome: "captured"|"no_mapping"|"already_capturing", artifact_path}).
- Whether `CalibrateMapping.srv` is a new interface or reuses `std_srvs/Trigger`.
- Whether `/rehab/opensim/input_validity` carries per-device skew values or just bool validity mask per device.

### Deferred Ideas (OUT OF SCOPE)
- Studio mapping workspace (segment selectors, Draft/Saved/Applied states) — Phase 24.
- Hardware promotion gate — Phase 25.
- Partial-sensor IK (degraded profile) — future milestone.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| IK-01 | Applied mapping creates and tears down deterministic MAC-keyed subscriptions and one ordered N-sensor orientation input set without leaking subscriptions, callbacks, or queues across remaps. | Subscription dict under threading.Lock (mirrors `_active_writers` in fleet_bridge_node). `destroy_subscription()` is the authoritative cleanup API on `rclpy.node.Node`. |
| IK-02 | Calibration artifacts bound to model hash, applied mapping revision, exact device-to-Frame assignments, and solver profile; invalidated by any semantic change. | New calib.v1 JSON file distinct from existing in-memory `CalibrationArtifact`. Atomic write pattern confirmed in mapping_node.py (tmp + os.replace). |
| IK-03 | Joint-state publication only when every required mapped input is valid, fresh, post-reconnect, and within configured sync-skew bound; degraded input suppresses new IK output without stopping acquisition or recording. | Skew gate is a pure arithmetic filter in the solve loop. Existing `_solve_and_publish_ik` is the correct extension point. |
| IK-04 | Official OpenSim orientation IK consumes mapped N-sensor set in deterministic order and reports mapping revision, calibration identity, input validity, solver status, and visualizer provenance. | `OpenSimOrientationIkSolver.solve()` currently hardcoded to master/slave keyword args — needs generalization. See Pitfall 1. |
</phase_requirements>

---

## Summary

Phase 23 adds N-sensor dynamic subscription management, file-persisted calibration artifacts, sync-skew enforcement, and extended IK metadata to the existing `OpenSimBridgeNode`. The work is purely a backend extension of existing code: no new packages, no new ROS node process, and no new message types beyond what `std_srvs/Trigger` and `std_msgs/String` already provide (with one discretion decision on whether a custom service is worth adding).

The primary technical challenge is the generalization of the IK solver API. The existing `OpenSimOrientationIkSolver.solve()` method accepts exactly two positional keyword args (`master_xyzw`, `slave_xyzw`) and internally uses two hardcoded frame labels. Phase 23 must generalize this to accept an ordered list of `(frame_name, xyzw)` pairs — one per mapped sensor — while keeping the existing 2-sensor test suite passing. The `OrientationIkSolver` Protocol in `orientation_ik.py` must be extended or a new variant defined; the planner must decide whether to extend in place (changing the Protocol's `solve()` signature) or to add a parallel `solve_n()` path, keeping the existing 2-arg path for backward compatibility.

The calibration artifact on disk (`calib.v1`) is a new concern: it is a persistent file that survives process restarts, unlike the in-memory `CalibrationArtifact` dataclass from Phase 17. The node must load, validate, and invalidate this file at startup and on every mapping update. The atomic-write pattern (`tmp + os.replace()`) is already established in `mapping_node.py` and must be replicated exactly.

**Primary recommendation:** Extend `OpenSimBridgeNode` with a `_remap_inputs()` method that is the single entry point for all subscription lifecycle changes (called from the `/rehab/mapping/current` callback). Keep the existing master/slave codepath intact as a fallback for tests. All new code paths must be exercisable without ROS or OpenSim using the `_install_ros_stubs()` pattern from `test_opensim_node.py`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Dynamic MAC-keyed IMU subscriptions | Backend (opensim_node) | — | ROS subscription lifecycle is a node responsibility; no client/UI involvement |
| Calibration artifact persistence | Backend (opensim_node) | Filesystem | Node owns the calib.v1 JSON; filesystem is the durable store |
| Sync-skew gating | Backend (opensim_node) | — | Pure arithmetic on timestamps; runs in the IK solve loop before solver call |
| IK solve | Backend (OpenSimOrientationIkSolver) | — | OpenSim Python API is a single-process concern; not distributable |
| Mapping current subscription | Backend (opensim_node consuming mapping_node output) | — | opensim_node is a downstream consumer; mapping_node remains authoritative |
| Reconnect fresh-guard | Backend (opensim_node consuming fleet registry) | — | fleet_bridge_node emits reconnect events; opensim_node sets per-device flag |
| Calibration status publication | Backend (opensim_node) | — | `/rehab/calibration/status` feeds mapping_node's Apply interlock (D-15 Phase 22) |
| Input validity publication | Backend (opensim_node) | — | Per-device skew diagnostics; consumed by Studio UI (Phase 24) |
| Solver-sufficiency hard-block | Backend (mapping_node apply_candidate) | — | D-12: mapping_node must enforce minimum assigned-device count for profile |

---

## Standard Stack

### Core (no new packages — all internal)

| Component | Location | Purpose | Why Standard |
|-----------|----------|---------|--------------|
| `OpenSimBridgeNode` | `backend/rehab_robotics_bridge/opensim_node.py` | Node to extend | D-13: extend, not replace |
| `OpenSimOrientationIkSolver` | `backend/rehab_robotics_bridge/opensim/opensim_orientation_ik.py` | IK solver | D-10: reuse as-is (with API generalization) |
| `CalibrationController` | `backend/rehab_robotics_bridge/opensim/calibration.py` | In-memory capture state machine | Existing; Phase 23 adds file-persistence layer alongside it |
| `threading.Lock` | Python stdlib | Subscription dict protection | D-14: established pattern in fleet_bridge_node._active_writers |
| `os.replace()` + tmp file | Python stdlib | Atomic artifact write | D-04: established pattern in mapping_node._save() |
| `statistics.median` | Python stdlib | Reference timestamp for skew gate | D-07: compute median of N device timestamps |
| `std_srvs/Trigger` | ROS 2 | Calibration capture/clear service | Existing services already use this type; Claude's Discretion: may keep Trigger |
| `std_msgs/String` | ROS 2 | All JSON status topics | Existing pattern throughout codebase |

### Supporting

| Component | Location | Purpose | When to Use |
|-----------|----------|---------|-------------|
| `FakeOrientationIkSolver` | `orientation_ik.py` | Offline test double | All test classes that don't need real OpenSim |
| `_install_ros_stubs()` | `test_opensim_node.py` | ROS-free test infrastructure | Every new test class in `test_opensim_node.py` |
| `ik_contracts.py` | `opensim/ik_contracts.py` | Frozen topic/service name constants | Do not hardcode strings; always import constants |

**Installation:** No new packages. All dependencies are stdlib or already present in the ROS 2 workspace.

---

## Package Legitimacy Audit

No external packages are added in this phase. All code changes are to existing first-party Python files within the ROS 2 workspace. This section is intentionally minimal.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| _(none)_ | — | — | — | — | — | N/A |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
/rehab/mapping/current (String JSON)
        |
        v
OpenSimBridgeNode._on_mapping_current()
        |
        +--[compare device list]--+
        |                         |
        v                         v
destroy old MAC subs         create new MAC subs
(for removed devices)        (/esp/raw/mac_<12hex>)
        |                         |
        +----------+--------------+
                   |
                   | (per-device IMU callback fires)
                   v
        _on_mac_imu(device_id, msg)
                   |
                   +--[set post_reconnect_fresh=True on first frame]
                   |
                   +--[update _input_states[device_id].last_xyzw, last_seen_ts]
                   |
                   v
        _solve_and_publish_ik()
                   |
              [skew gate]
              abs(ts - median) <= sync_skew_ms AND post_reconnect_fresh?
                   |              |
                  YES             NO
                   |              +---> suppress, publish input_validity w/ failures
                   v
           calib artifact loaded AND state==CALIBRATED?
                   |              |
                  YES             NO
                   |              +---> IkSolution(solution_valid=False)
                   v
        OpenSimOrientationIkSolver.solve_n(
            inputs=[(frame, xyzw), ...],  # N-sensor, alphabetical device_id order
            calibration=calib_artifact,
            source_timestamp_ns=min(all_ts),
        )
                   |
                   v
        _maybe_publish_joint_states()
           (with extended metadata: mapping_revision, calibration_identity, ...)
                   |
                   v
        /rehab/opensim/joint_states  +  /rehab/opensim/input_validity
```

```
/esp/fleet/registry (String JSON)
        |
        v
OpenSimBridgeNode._on_fleet_registry()
        |
        +--[for each device with route_state == 'reconnecting']
        |
        v
   _input_states[device_id].post_reconnect_fresh = False
```

```
/rehab/calibration/capture (Trigger service)
        |
        v
_on_calibration_capture()
        |
        +--[all N inputs live AND calibration_state != CAPTURING?]
        |
        v
   capture reference poses from _input_states[].last_xyzw
   write calib.v1 JSON artifact atomically
   set calibration_state = CALIBRATED
   publish /rehab/calibration/status
```

### Recommended Project Structure

The phase adds no new files beyond the test file. All changes are extensions of existing files:

```
backend/
├── rehab_robotics_bridge/
│   ├── opensim_node.py              # EXTEND: +_remap_inputs(), +_on_mapping_current(),
│   │                                #          +_on_fleet_registry(), +_skew_gate(),
│   │                                #          +_load_calib_artifact(), +new params
│   ├── opensim/
│   │   ├── opensim_orientation_ik.py # EXTEND: generalize solve() to accept N-sensor list
│   │   ├── orientation_ik.py         # EXTEND: update OrientationIkSolver Protocol
│   │   └── ik_contracts.py           # EXTEND: add new topic constants for Phase 23
│   └── mapping_node.py              # EXTEND: hard-block solver_insufficient in apply_candidate
└── test/
    └── test_opensim_node.py         # EXTEND: new test classes for Phase 23 contracts
```

### Pattern 1: Dynamic MAC Subscription Lifecycle (IK-01)

**What:** On each `/rehab/mapping/current` update, diff the new device list against `self._mac_subs`. Destroy stale subscriptions, create new ones, all under `self._input_lock`.

**When to use:** Whenever the applied mapping changes. The lock must be held for the entire diff-and-replace operation so that IMU callbacks cannot fire against a partially-updated state.

**Example:**
```python
# Source: codebase inspection — fleet_bridge_node._active_writers pattern
def _remap_inputs(self, new_assignments: dict[str, dict]) -> None:
    """Called from _on_mapping_current, always under self._input_lock."""
    # new_assignments: {device_id: {segment, frame, state}} for state=="assigned" only
    new_device_ids = {
        did for did, entry in new_assignments.items()
        if entry.get("state") == "assigned"
    }
    old_device_ids = set(self._mac_subs.keys())

    # Destroy subscriptions for removed devices
    for did in old_device_ids - new_device_ids:
        sub = self._mac_subs.pop(did, None)
        if sub is not None:
            self.destroy_subscription(sub)
        self._input_states.pop(did, None)

    # Create subscriptions for new devices
    for did in new_device_ids - old_device_ids:
        topic = f"/esp/raw/{device_topic_token(did)}"
        sub = self.create_subscription(
            String,
            topic,
            lambda msg, d=did: self._on_mac_imu(d, msg),
            _IMU_QOS,
        )
        self._mac_subs[did] = sub
        self._input_states[did] = _MappedInputState(
            device_id=did,
            frame=new_assignments[did]["frame"],
            post_reconnect_fresh=False,  # guard until first frame after (re)subscribe
        )

    # Update device_order (sorted by device_id for determinism D-03)
    self._device_order = sorted(new_device_ids)
```

**Key rule:** `device_topic_token(did)` is the same function already imported from `esp32_bridge_node` and used in `fleet_bridge_node`. Produces `mac_<12hex>` from `esp32:<12hex>`.

### Pattern 2: Calibration Artifact Load and Invalidation (IK-02)

**What:** At startup and on every mapping update, compute the expected artifact filename. If it exists and passes schema validation, load it and set state = CALIBRATED. If it does not exist or does not match, set state = UNCALIBRATED.

**Example:**
```python
# Source: codebase inspection — mapping_node._save() atomic write pattern
def _calib_artifact_path(self, model_hash: str, applied_revision: int) -> Path:
    name = f"calibration_{model_hash[:8]}_rev{applied_revision}.json"
    return Path.home() / ".ros" / "rehab_robotics" / name

def _write_calib_artifact(self, artifact: dict) -> Path:
    path = self._calib_artifact_path(
        artifact["model_hash"], artifact["applied_revision"]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(artifact, sort_keys=True, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path

def _load_calib_artifact(self, model_hash: str, applied_revision: int) -> dict | None:
    path = self._calib_artifact_path(model_hash, applied_revision)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version") != "calib.v1":
            return None
        if data.get("model_hash") != model_hash:
            return None
        if data.get("applied_revision") != applied_revision:
            return None
        return data
    except Exception:
        return None
```

**Key rule:** Artifact invalidation (D-05) is triggered by comparing `model_hash + applied_revision + set(device_ids)` against the loaded artifact. Any mismatch clears the artifact and resets to UNCALIBRATED.

### Pattern 3: Sync-Skew Gate (IK-03)

**What:** Before each IK solve, compute median timestamp across all N device inputs. Suppress solve if any device exceeds `sync_skew_ms` from median, or if any device's `post_reconnect_fresh` is False.

**Example:**
```python
# Source: codebase inspection — D-07/D-08 design decisions
import statistics

def _check_sync_skew(self) -> tuple[bool, dict[str, bool]]:
    """Returns (all_valid, per_device_validity).
    Timestamps are ROS source timestamps in nanoseconds.
    sync_skew_ms is the ROS param (default 50).
    """
    timestamps = {}
    for did in self._device_order:
        state = self._input_states.get(did)
        if state is None or state.last_source_timestamp_ns is None:
            return False, {d: False for d in self._device_order}
        if not state.post_reconnect_fresh:
            return False, {d: d != did for d in self._device_order}
        timestamps[did] = state.last_source_timestamp_ns

    ts_list = list(timestamps.values())
    ref_ns = int(statistics.median(ts_list))
    skew_ns = int(self._sync_skew_ms * 1_000_000)

    validity = {
        did: abs(timestamps[did] - ref_ns) <= skew_ns
        for did in self._device_order
    }
    return all(validity.values()), validity
```

**Key rule:** Use `statistics.median` from stdlib — no external dependency. Reference is the median, not the minimum. Skew in milliseconds → nanoseconds conversion: multiply by 1,000,000.

### Pattern 4: IK Solver N-Sensor Generalization (IK-04)

**What:** `OpenSimOrientationIkSolver.solve()` is currently hardcoded to exactly two sensors (master/slave keywords). Phase 23 must generalize to N sensors. The cleanest path is adding a `solve_n()` method that accepts an ordered list of `(frame_name, xyzw)` pairs. The existing `solve()` method becomes a thin wrapper around `solve_n()` for backward compatibility.

**Existing signature (current):**
```python
# From orientation_ik.py — OrientationIkSolver Protocol
def solve(
    self,
    *,
    master_xyzw: Sequence[float],
    slave_xyzw: Sequence[float],
    calibration: CalibrationArtifact | None,
    source_timestamp_ns: int | None,
    input_age_s: float | None,
    joint_names: Sequence[str],
) -> IkSolution: ...
```

**Proposed generalization approach:**
```python
# New method on OrientationIkSolver Protocol
def solve_n(
    self,
    *,
    inputs: list[tuple[str, Sequence[float]]],  # [(frame_name, xyzw), ...] in device_order
    calibration_artifact: dict | None,           # calib.v1 dict (not the old CalibrationArtifact dataclass)
    source_timestamp_ns: int | None,
    input_age_s: float | None,
    joint_names: Sequence[str],
) -> IkSolution: ...
```

**Key architectural decision for planner:** The `CalibrationArtifact` dataclass (from `calibration.py`) stores only `master_xyzw` and `slave_xyzw`. The new calib.v1 file stores a per-device reference pose dict keyed by `device_id`. The solver's mounting-offset correction in `apply_mounting_offsets()` must be updated to iterate over N sensors. This means:
- `apply_mounting_offsets()` must accept `inputs: list[(frame, xyzw)]` + `reference_poses: dict[device_id, xyzw]`
- The `_make_quat_table()` in `OpenSimOrientationIkSolver` must accept a variable-length list of `(frame, wxyz)` pairs, not hardcoded `column_labels = [master_frame, slave_frame]`

**Backward compatibility test preservation strategy:** Keep existing `solve()` on `FakeOrientationIkSolver` and `UnavailableOrientationIkSolver`. Existing tests call `solve(master_xyzw=..., slave_xyzw=...)` — these must continue to pass. Only `opensim_node.py` will call `solve_n()` after Phase 23.

### Anti-Patterns to Avoid

- **Orphan subscriptions:** Never allow `_mac_subs` to be modified without holding `self._input_lock`. A missing `destroy_subscription()` call creates a subscription that fires into a stale `_input_states` entry.
- **Thread-unsafe remap:** The `/rehab/mapping/current` callback fires from the ROS executor thread. The lock must cover the entire diff-and-replace, including the `_device_order` update. Do not release the lock between "destroy old" and "create new".
- **Fabricated wall-clock stamps:** The existing `_source_timestamp_ns()` function enforces this. The Phase 23 skew gate uses source timestamps only, never `time.monotonic()` as a substitute for missing source timestamps.
- **Stale calib artifact after mapping change:** D-05 is easy to implement incorrectly by checking only `model_hash` and missing `applied_revision` or `set(device_ids)`. All three invalidation conditions must be checked on every mapping update.
- **CalibrationArtifact vs calib.v1 confusion:** The existing `CalibrationArtifact` dataclass is an in-memory object for the 2-sensor case. The new calib.v1 is a file-persisted dict for the N-sensor case. Do not conflate them. The node will manage both during transition: the existing `self._calibration` (`CalibrationController`) is for the legacy 2-sensor path; the new `self._calib_v1` is the file-backed N-sensor artifact.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file write | Custom file-swap logic | `tmp.write_text() + tmp.replace(dest)` | Already proven in mapping_node._save(); `os.replace()` is atomic on POSIX and best-effort on Windows |
| Median timestamp | Custom sort+index | `statistics.median()` | Stdlib; handles even N correctly; already in the project's Python version |
| MAC topic name | String formatting | `device_topic_token(device_id)` from `esp32_bridge_node` | Already imported in fleet_bridge_node; produces `/mac_<12hex>` consistently |
| Quaternion normalization | Manual sqrt | `ros_xyzw_to_opensim_rotation()` from `opensim_adapter` | Already validates and normalizes; throws on degenerate input |
| ROS stub infrastructure | New test stubs | `_install_ros_stubs()` from `test_opensim_node.py` | 100-line stub already handles all needed message/service types |

**Key insight:** The codebase has well-established utility functions for every low-level operation needed in this phase. The risk of hand-rolling is not complexity but correctness: the existing functions have been validated in prior phases.

---

## Common Pitfalls

### Pitfall 1: `_make_quat_table` Hardcoded to Exactly Two Columns
**What goes wrong:** `OpenSimOrientationIkSolver._make_quat_table()` creates a `TimeSeriesTableQuaternion` with exactly 2 columns (`master_frame`, `slave_frame`) and a `RowVectorQuaternion(2)`. For N sensors, this will fail or produce wrong results silently because the OpenSim binding uses `RowVectorQuaternion(N)` and column labels must match.
**Why it happens:** The solver was designed for a fixed pair; N-sensor generalization was explicitly deferred to Phase 23.
**How to avoid:** In `_make_quat_table()`, accept `inputs: list[tuple[str, tuple]]` instead of separate `master_wxyz`/`slave_wxyz`. Construct `RowVectorQuaternion(len(inputs))` and set each column via `row.updElt(0, i)`. Update `_update_orientation_targets()` similarly.
**Warning signs:** Test passes with N=2 but silently uses only first/last columns for N>2.

### Pitfall 2: `post_reconnect_fresh` Race Condition
**What goes wrong:** The fleet registry callback sets `post_reconnect_fresh = False`. The very next IMU callback fires before the flag is read in `_solve_and_publish_ik()`, setting the flag to `True` and immediately allowing a solve. If the solve loop does not read the flag under the lock, this race is possible.
**Why it happens:** ROS callbacks fire from the executor thread; the solve loop also runs in the callback thread but `post_reconnect_fresh` is written by two different callbacks.
**How to avoid:** Read `post_reconnect_fresh` and update it to `True` (on first frame) atomically under `self._input_lock` inside `_on_mac_imu()`. Do not read it again in `_solve_and_publish_ik()` without the lock.
**Warning signs:** Test coverage gap — need a test that calls `_on_fleet_registry()` then immediately calls `_on_mac_imu()` and verifies the solve was suppressed.

### Pitfall 3: Calibration Artifact Filename Collision Across Different Models
**What goes wrong:** `model_hash[:8]` is only 8 hex chars (32 bits). Two different models could produce the same prefix, causing one model's artifact to be loaded for another.
**Why it happens:** D-04 specifies `model_hash[:8]` — this is intentional for human readability, not cryptographic uniqueness. The full `model_hash` validation is inside the artifact JSON itself.
**How to avoid:** `_load_calib_artifact()` must always validate `artifact["model_hash"] == full_model_hash`, not just check that the file exists. The filename prefix is for discoverability only.
**Warning signs:** Missing validation of `model_hash` full value after loading by filename.

### Pitfall 4: `solver_insufficient` Hard-Block in mapping_node Not Implemented
**What goes wrong:** D-12 specifies that Phase 22 deferred the hard-block to Phase 23. The current `apply_candidate()` in `mapping_node.py` only emits a warning detail `"solver_insufficient: no devices assigned"` when `assigned_count == 0`. For `solver_profile == "lower_body"`, the minimum is likely 2 sensors (femur + tibia), not 0.
**Why it happens:** Phase 22 intentionally soft-blocked only the zero-assigned case as best-effort. Phase 23 must upgrade this to a hard block with profile-aware minimums.
**How to avoid:** Phase 23 must add a `solver_profile` parameter to `MappingStore.apply_candidate()` and/or pass the profile down from the ROS param. The mapping_node needs to know the minimum required count per profile.
**Warning signs:** `apply_candidate()` returns `"applied"` for a 1-sensor mapping when the profile requires 2+.

### Pitfall 5: Existing Tests Assert Exactly 2 Subscriptions
**What goes wrong:** `test_locked_defaults_create_exactly_two_native_imu_subscriptions` (in `test_opensim_node.py`) asserts `len(node.subscriptions) == 2`. After Phase 23, the node also subscribes to `/rehab/mapping/current` and `/esp/fleet/registry`, making the count 4 at startup (before any mapping arrives). The test will fail.
**Why it happens:** The test counts total subscriptions, not just IMU subscriptions.
**How to avoid:** Update the test to check by topic name, not count. Or change it to `assertGreaterEqual(len(node.subscriptions), 2)` and verify the two IMU topics are present by name. Do not delete the test; update it.
**Warning signs:** CI fails on existing test immediately after adding the two new subscriptions.

### Pitfall 6: Calibration Capture When No Mapping Applied
**What goes wrong:** Operator calls `/rehab/calibration/capture` before any mapping has been applied. `self._device_order` is empty or does not match the loaded artifact. The capture collects zero samples and writes a zero-entry artifact.
**Why it happens:** Service handler does not check for a valid applied mapping before initiating capture.
**How to avoid:** Pre-condition check in `_on_calibration_capture()`: if `self._device_order` is empty or `self._applied_mapping_revision == 0`, return `outcome: "no_mapping"` immediately.
**Warning signs:** Artifact file created with empty `device_order` list.

---

## Code Examples

### Existing Subscriber Stub Pattern (for tests)

```python
# Source: backend/test/test_opensim_node.py — _StubNode.create_subscription
def create_subscription(self, message_type, topic, callback, qos):
    subscription = types.SimpleNamespace(
        message_type=message_type,
        topic=topic,
        callback=callback,
        qos=qos,
    )
    self.subscriptions.append(subscription)
    return subscription
```

The stub stores subscription objects in `self.subscriptions`. Phase 23 tests must also stub `destroy_subscription(sub)` on `_StubNode`:

```python
# MUST add to _StubNode for Phase 23 tests
def destroy_subscription(self, subscription):
    if subscription in self.subscriptions:
        self.subscriptions.remove(subscription)
```

### Mapping Current Payload Format

```python
# Source: mapping_node._publish_current() — the actual schema published
{
    "schema": "rehab.mapping_current.1",
    "schema_version": "map.v1",
    "model_hash": "<sha256 hex>",
    "revision": 3,
    "assignments": {
        "esp32:aabbccddeeff": {"segment": "femur_r", "frame": "femur_r_imu", "state": "assigned"},
        "esp32:112233445566": {"segment": "tibia_r", "frame": "tibia_r_imu", "state": "assigned"},
    },
    "applied_revision": 3,
    "backup_revision": 2,
}
```

Phase 23 uses `data["assignments"]` filtered to `state=="assigned"` to build `_device_order`.

### Fleet Registry Reconnect Detection

```python
# Source: fleet_bridge_node — reconnect detection pattern
# The fleet registry JSON contains per-device "route" field.
# When route is "reconnecting", set post_reconnect_fresh = False.
def _on_fleet_registry(self, msg: String) -> None:
    try:
        data = json.loads(msg.data)
    except Exception:
        return
    devices = data.get("devices", [])
    with self._input_lock:
        for device in devices:
            did = device.get("device_id", "")
            route = device.get("route", {})
            route_state = route.get("state", "") if isinstance(route, dict) else str(route)
            if route_state == "reconnecting" and did in self._input_states:
                self._input_states[did].post_reconnect_fresh = False
```

**Note:** The fleet registry `route` field is a nested object in `oe_esp32.fleet_registry.v1`. Inspection of `build_fleet_registry()` in `fleet_bridge_node.py` shows `'route': {'state': state.route, ...}` structure.

### calib.v1 Schema

```python
# D-04 schema (to be written atomically to filesystem)
artifact = {
    "schema_version": "calib.v1",
    "model_hash": "<full sha256 hex>",
    "applied_revision": 3,
    "device_order": ["esp32:112233445566", "esp32:aabbccddeeff"],  # sorted alphabetically
    "frame_assignments": {
        "esp32:112233445566": {"segment": "tibia_r", "frame": "tibia_r_imu"},
        "esp32:aabbccddeeff": {"segment": "femur_r", "frame": "femur_r_imu"},
    },
    "solver_profile": "lower_body",
    "calibrated_at_iso8601": "2026-08-05T14:23:00Z",
    "reference_pose": {
        "esp32:112233445566": {"qw": 0.99, "qx": 0.01, "qy": 0.0, "qz": 0.0},
        "esp32:aabbccddeeff": {"qw": 0.98, "qx": 0.02, "qy": 0.01, "qz": 0.0},
    },
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed 2-sensor solve (master/slave keyword args) | N-sensor solve (ordered list of frame+quat) | Phase 23 | Solver API generalization required |
| In-memory CalibrationArtifact only | calib.v1 JSON file on disk (survives restart) | Phase 23 | Persistence and invalidation logic added |
| No subscription management | Dynamic MAC-keyed subscriptions under Lock | Phase 23 | Enables live remapping without node restart |
| No sync-skew check | Per-device timestamp skew gate vs. median | Phase 23 | Prevents stale/desynced inputs reaching solver |

**Still current:**
- `OrientationIkSolver` Protocol (orientation_ik.py) — must be extended but structure preserved
- `may_publish_joint_states()` gate from `ik_contracts.py` — remains the calibration half of the gate
- `_install_ros_stubs()` pattern — remains the standard for offline test isolation

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `device_topic_token()` produces `/mac_<12hex>` for canonical `esp32:<12hex>` device_ids | Pattern 1 | Subscription would target wrong topic; no frames received |
| A2 | The fleet registry's per-device route field is structured as `{"state": "reconnecting", ...}` (nested object, not flat string) | Code Examples | `_on_fleet_registry` reads wrong field; post_reconnect_fresh never set to False |
| A3 | `statistics.median` is available in the Python version used in the ROS 2 WSL environment | Pattern 3 | ImportError at runtime (extremely unlikely; stdlib since Python 3.4) |
| A4 | `solver_profile == "lower_body"` requires minimum 2 assigned sensors for hard-block in D-12 | Pitfall 4 | Minimum count may be 1 or 3; confirm with project constraints |
| A5 | OpenSim `RowVectorQuaternion(N)` constructor accepts an integer N for variable column count | Pitfall 1 | Table construction fails for N != 2; falls back to 2-column path |

**Note on A2:** The fleet registry JSON structure was read from `build_fleet_registry()` in `fleet_bridge_node.py`. The `route` field in each device entry is the value of `state.route` (a string like `"reconnecting"`), not a nested object. It appears as `'route': state.route` in the dict passed directly to the output. [ASSUMED] — verify against the actual JSON before writing the callback.

**Correction to A2:** On further inspection of `build_fleet_registry()`:
```python
'route': {
    'state': state.route,
    ...
}
```
The route IS a nested dict. The test should check `device.get("route", {}).get("state", "")`. [VERIFIED: codebase inspection of fleet_bridge_node.py build_fleet_registry function]

---

## Open Questions (RESOLVED)

1. **Solver-sufficiency minimum count for `lower_body` profile**
   - RESOLVED: Plan 23-04. Minimum is 2 (`{"lower_body": 2}`). `SOLVER_PROFILE_MIN_SENSORS` dict defined in `ik_contracts.py`; Apply returns `solver_insufficient` if `assigned_count < 2`.

2. **Whether `/rehab/calibration/capture` should reuse `std_srvs/Trigger` or a custom service**
   - RESOLVED: Plan 23-02. Reuse `std_srvs/Trigger`. Encode `{outcome, artifact_path}` as JSON in `res.message`. No new `.srv` interface file needed.

3. **Whether `/rehab/opensim/input_validity` carries per-device skew values or just bool flags**
   - RESOLVED: Plan 23-03. Carry both: `{device_id: {valid: bool, skew_ms: float | null, post_reconnect_fresh: bool}}`. Richer data is free; stripping in Phase 24 is simpler than adding later.

4. **Topic namespace for Phase 23 new topics**
   - RESOLVED: Plan 23-04. Extended output uses `/rehab/opensim/joint_states_metadata` (new JSON String topic). Existing `JOINT_STATES_TOPIC = /opensim/joint_states` is preserved unchanged (backward compat). New Phase 23 topics use `/rehab/` prefix as specified in CONTEXT.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python stdlib `statistics` | Sync-skew median | ✓ | stdlib (Python 3.4+) | None needed |
| Python stdlib `os.replace` | Atomic artifact write | ✓ | stdlib | None needed |
| ROS 2 `rclpy.node.Node.destroy_subscription` | IK-01 subscription teardown | ✓ (stubbed in tests) | — | Stub in `_StubNode` |
| `opensim` Python module | Live IK solves | ✓ (WSL OpenSim 4.5.2) | 4.5.2 | `UnavailableOrientationIkSolver` (existing) |
| `device_topic_token()` from `esp32_bridge_node` | MAC topic naming | ✓ (already imported in fleet_bridge_node) | — | None needed |

**Missing dependencies with no fallback:** None. All required capabilities are either stdlib, already in the codebase, or have existing graceful-degradation paths.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Python `unittest` (stdlib) |
| Config file | none — invoked via `python -m unittest` |
| Quick run command | `python -m unittest backend.test.test_opensim_node -v` |
| Full suite command | `python -m unittest discover -s backend/test -p "test_*.py" -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IK-01 | Remap destroys old subs and creates new subs without orphans | unit | `python -m unittest backend.test.test_opensim_node.OpenSimNodeRemapTests -v` | ❌ Wave 0 |
| IK-01 | Remap is idempotent (same mapping applied twice = no-op) | unit | `python -m unittest backend.test.test_opensim_node.OpenSimNodeRemapTests.test_remap_idempotent -v` | ❌ Wave 0 |
| IK-01 | Alphabetical device_order is stable regardless of dict insertion order | unit | `python -m unittest backend.test.test_opensim_node.OpenSimNodeRemapTests.test_device_order_alphabetical -v` | ❌ Wave 0 |
| IK-02 | Artifact loaded at startup if file exists and matches | unit | `python -m unittest backend.test.test_opensim_node.CalibrationArtifactTests.test_load_on_startup -v` | ❌ Wave 0 |
| IK-02 | Artifact invalidated on model_hash change | unit | `python -m unittest backend.test.test_opensim_node.CalibrationArtifactTests.test_invalidate_on_hash_change -v` | ❌ Wave 0 |
| IK-02 | Artifact invalidated on applied_revision change | unit | `python -m unittest backend.test.test_opensim_node.CalibrationArtifactTests.test_invalidate_on_revision_change -v` | ❌ Wave 0 |
| IK-02 | Artifact invalidated on device set change | unit | `python -m unittest backend.test.test_opensim_node.CalibrationArtifactTests.test_invalidate_on_device_set_change -v` | ❌ Wave 0 |
| IK-02 | Capture blocked when no mapping applied | unit | `python -m unittest backend.test.test_opensim_node.CalibrationArtifactTests.test_capture_blocked_no_mapping -v` | ❌ Wave 0 |
| IK-03 | IK suppressed when any device exceeds skew bound | unit | `python -m unittest backend.test.test_opensim_node.SyncSkewTests.test_skew_suppresses_solve -v` | ❌ Wave 0 |
| IK-03 | IK suppressed when post_reconnect_fresh == False | unit | `python -m unittest backend.test.test_opensim_node.SyncSkewTests.test_reconnect_guard_suppresses_solve -v` | ❌ Wave 0 |
| IK-03 | /rehab/opensim/input_validity published every cycle | unit | `python -m unittest backend.test.test_opensim_node.SyncSkewTests.test_input_validity_published -v` | ❌ Wave 0 |
| IK-04 | IK output carries mapping_revision and calibration_identity | unit | `python -m unittest backend.test.test_opensim_node.IkMetadataTests.test_joint_states_carries_metadata -v` | ❌ Wave 0 |
| IK-04 | Existing 2-sensor tests remain green | regression | `python -m unittest backend.test.test_opensim_node.OpenSimNodeForwardingTests -v` | ✅ Exists |
| MAP-02 | solver_insufficient hard-blocks apply for under-count mapping | unit | `python -m unittest backend.test.test_mapping_node.MappingStoreTest.test_apply_solver_insufficient_hard_block -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m unittest backend.test.test_opensim_node -v`
- **Per wave merge:** `python -m unittest discover -s backend/test -p "test_*.py" -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

The following test infrastructure must be created before implementation:

- [ ] `backend/test/test_opensim_node.py` — ADD new test classes:
  - `OpenSimNodeRemapTests` — covers IK-01 subscription lifecycle (no ROS, no OpenSim)
  - `CalibrationArtifactTests` — covers IK-02 file artifact load/invalidate (uses `tempfile.TemporaryDirectory`)
  - `SyncSkewTests` — covers IK-03 sync-skew gate logic
  - `IkMetadataTests` — covers IK-04 metadata fields in joint_states output
- [ ] `_StubNode.destroy_subscription(sub)` method — add to existing `_StubNode` stub class in `test_opensim_node.py`
- [ ] New ROS stub entries for `/rehab/mapping/current` subscriber (`std_msgs/String`) — already stubbed in existing `_install_ros_stubs()`; confirm no additional message types needed
- [ ] `backend/test/test_mapping_node.py` — ADD one new test:
  - `MappingStoreTest.test_apply_solver_insufficient_hard_block` — covers D-12 hard-block

*(Existing test infrastructure: `_install_ros_stubs()` + `_StubNode` + `_FakeAdapter` + `_Clock` + all existing message stubs are sufficient for Phase 23 with the `destroy_subscription` addition.)*

---

## Security Domain

Security enforcement is not explicitly disabled in `.planning/config.json`. Reviewing applicable ASVS categories for this phase:

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user authentication in this backend layer |
| V3 Session Management | no | No user sessions |
| V4 Access Control | no | Single-operator embedded backend |
| V5 Input Validation | yes | All JSON parsed with `json.loads()` + explicit field access; invalid JSON caught and logged |
| V6 Cryptography | no | model_hash is SHA-256 for provenance, not for security; no secrets involved |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed `/rehab/mapping/current` JSON | Tampering | `json.loads()` in try/except; return without action on parse failure |
| calib.v1 file corruption or tamper | Tampering | Schema version check + model_hash full validation on load; corrupt = treat as missing |
| Artifact filename path traversal | Tampering | All paths constructed from `model_hash[:8]` (hex chars only) + int revision; no user-supplied path |
| Stale reconnect causing bad IK output | Spoofing | `post_reconnect_fresh` guard (D-09) prevents pre-reconnect stale data from reaching solver |

---

## Sources

### Primary (HIGH confidence — codebase inspection)

- `backend/rehab_robotics_bridge/opensim_node.py` — full node code inspected; subscription lifecycle, IK solve loop, calibration status publish
- `backend/rehab_robotics_bridge/opensim/opensim_orientation_ik.py` — full solver inspected; `_make_quat_table`, `solve()`, `_update_orientation_targets` are the extension points
- `backend/rehab_robotics_bridge/opensim/orientation_ik.py` — Protocol definition, `FakeOrientationIkSolver`, `apply_mounting_offsets`
- `backend/rehab_robotics_bridge/opensim/calibration.py` — `CalibrationController`, `CalibrationArtifact` — existing in-memory 2-sensor calibration
- `backend/rehab_robotics_bridge/mapping_node.py` — `_publish_current()` JSON schema; `apply_candidate()` solver-sufficiency soft warning; atomic write pattern
- `backend/rehab_robotics_bridge/fleet_bridge_node.py` — `reconnect_count`, `mark_reconnecting()`, `build_fleet_registry()` route field structure; `_active_writers` threading pattern
- `backend/rehab_robotics_bridge/opensim/ik_contracts.py` — all frozen topic/service constants
- `backend/test/test_opensim_node.py` — full `_install_ros_stubs()` and `_StubNode` implementation; existing test classes
- `backend/test/test_mapping_node.py` — `_StubNode` inheriting pattern; `sys.modules[]` assignment trick
- `.planning/phases/23-n-sensor-calibration-and-official-opensim-ik/23-CONTEXT.md` — all D-01 through D-14 decisions
- `.planning/REQUIREMENTS.md` — IK-01 through IK-04 requirements
- `docs/opensim-ik-contracts.md` — locked topic names and hard calibration gate

### Secondary (MEDIUM confidence)
- `.planning/phases/22-model-catalog-mapping-store-and-transactional-contracts/22-05-SUMMARY.md` — test patterns and `_StubNode` registration trick

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all tools are existing stdlib or codebase modules; zero new dependencies
- Architecture: HIGH — all extension points verified by direct code inspection; no speculative APIs
- Pitfalls: HIGH — Pitfall 1 and 5 are directly observable from code; Pitfall 4 confirmed by reading `apply_candidate()` source
- IK solver generalization: MEDIUM — the `RowVectorQuaternion(N)` behavior with N > 2 is [ASSUMED] until tested; the 4.5.x SWIG binding has a track record of surprises (see existing `_make_quat_table` fallback chains)

**Research date:** 2026-08-05
**Valid until:** 2026-09-05 (stable internal codebase — only stale if Phase 22 artifacts change)
