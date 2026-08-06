---
phase: 22-model-catalog-mapping-store-and-transactional-contracts
verified: 2026-08-05T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 22: Model Catalog, Mapping Store, and Transactional Contracts — Verification Report

**Phase Goal:** Operators can create, save, restore, and atomically apply a valid mapping against the exact loaded OpenSim model.
**Verified:** 2026-08-05
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The loaded `.osim` model is identified by SHA-256 hash of its exact bytes; assignment choices contain only exact non-Ground model segments and compatible sensor Frames | VERIFIED | `compute_model_hash()` uses `hashlib.sha256(path.read_bytes()).hexdigest()` (line 42); `enumerate_compatible_frames()` explicitly skips `name.lower() == "ground"` (line 92) and filters PhysicalOffsetFrame parents whose name is "ground" (line 146); 17/17 model catalog tests pass |
| 2 | Missing, ambiguous, or unsupported Frames fail closed with an actionable reason; no fuzzy selection or source-model modification | VERIFIED | `_build_and_publish_catalog` returns `error_reason` strings on every failure path; `apply_candidate` returns `invalid_frame` when assigned frame not in current `frame_list`; `set_assignment` returns `invalid_state`/`invalid_device_id`/`duplicate_frame`; `test_apply_fails_invalid_frame` passes; no setters (setUseVisualizer, initSystem) called — read-only test passes |
| 3 | Operator can mark every known device Assigned, Not used, or Unassigned; duplicate, unknown, incomplete, and solver-insufficient candidates are rejected authoritatively | VERIFIED | `_VALID_STATES = {"assigned", "not_used", "unassigned"}` enforced in `set_assignment`; duplicate (segment, frame) pair rejected with `duplicate_frame`; `apply_candidate` returns `incomplete` when any device is `unassigned`; solver-insufficiency recorded as warning detail (D-20 best-effort); 36/36 mapping tests pass |
| 4 | Desired mappings survive restart and corruption recovery under a versioned, revisioned, atomic backend store; same MAC reattaches under unchanged model/revision while different MAC remains Unassigned | VERIFIED | `_save()` uses `tmp = path.with_suffix('.tmp'); tmp.write_text(...); tmp.replace(path)` (lines 104/113/114); `.bak` written on every second+ save (line 108); `_load()` falls through to `.bak` then fresh data on corruption; `test_persistence_across_instantiation`, `test_backup_on_save`, `test_corruption_recovery_fresh_start` all pass; `_on_fleet_registry` keeps existing device state intact (D-17), registers new devices as `unassigned`; `test_reconnect_reattach_stays_assigned` and `test_new_device_from_fleet_registry_gets_unassigned` both pass |
| 5 | Apply validates and stages the complete candidate against the expected revision, atomically swaps only on success, preserves the previous applied revision on failure, and remains blocked during calibration capture, recording, or finalization | VERIFIED | `apply_candidate` checks `interlock_active` first (returns `blocked`), then `revision != expected_revision` (returns `revision_mismatch`), then completeness, then duplicate frames, then frame validity — `_data["applied_revision"]` only written on the success path (line 324); `test_apply_preserves_applied_revision_on_failure` passes for both store and node levels; `test_apply_blocked_recording` and `test_apply_blocked_calibration` both pass |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/rehab_robotics_bridge/model_catalog_node.py` | SHA-256 identity, frame enumeration, /rehab/model/catalog publisher | VERIFIED | 297 lines; full implementation; AST clean |
| `backend/rehab_robotics_bridge/mapping_node.py` | Assignment state machine, persistence, Apply + interlock, reconnect re-attach | VERIFIED | 686 lines; full implementation; AST clean |
| `backend/test/test_model_catalog_node.py` | Offline deterministic tests for MODEL-01/02/03 | VERIFIED | 17 tests; all pass |
| `backend/test/test_mapping_node.py` | Offline deterministic tests for MAP-01 through MAP-06 | VERIFIED | 36 tests; all pass |
| `rehab_robotics_interfaces/srv/SetAssignment.srv` | device_id, segment, frame, state → outcome, detail | VERIFIED | Fields match mapping_node handler signature exactly |
| `rehab_robotics_interfaces/srv/ApplyMapping.srv` | expected_revision → outcome, applied_revision, detail | VERIFIED | Fields match apply_candidate return contract |
| `rehab_robotics_interfaces/srv/GetMappingState.srv` | (empty request) → state_json | VERIFIED | Present; used in `_on_get_mapping_state` |
| `rehab_robotics_interfaces/srv/ResetMapping.srv` | model_hash → outcome | VERIFIED | Present; used in `_on_reset_mapping` |
| `backend/setup.py` | Entry points for model_catalog_node and mapping_node | VERIFIED | Lines 38-39: `'model_catalog_node = rehab_robotics_bridge.model_catalog_node:main'`, `'mapping_node = rehab_robotics_bridge.mapping_node:main'` |
| `backend/launch/rehab_robotics.launch.py` | Both nodes launched with enable flags | VERIFIED | `model_catalog` and `mapping` Node objects defined (lines 152-167); added to LaunchDescription return; guarded by `enable_model_catalog` and `enable_mapping_node` IfCondition flags |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `model_catalog_node` → `/rehab/model/catalog` | `mapping_node` | `_on_catalog` subscription | WIRED | `MappingNode._catalog_sub` subscribes to `MAPPING_CATALOG_TOPIC = "/rehab/model/catalog"`; callback calls `set_model_hash` and `set_frame_list` |
| `mapping_node` → `/esp/fleet/registry` | `_on_fleet_registry` | subscription + reconnect logic | WIRED | `_fleet_sub` subscribes at `FLEET_REGISTRY_TOPIC`; D-17 re-attach logic present and test-verified |
| `mapping_node` → `/esp/recording/status` | `_recording_active` flag | subscription | WIRED | `_recording_sub` subscribes; `_on_recording_status` sets `self._recording_active` |
| `mapping_node` → `/rehab/calibration/status` | `_calibration_active` flag | subscription | WIRED | `_calibration_sub` subscribes; `_on_calibration_status` sets `self._calibration_active` |
| `mapping_node` interlock → `apply_candidate` | `interlock_active` param | `_on_apply_mapping` | WIRED | Handler combines both flags before calling `apply_candidate(interlock_active=...)` |
| `setup.py` entry points → launch file executables | `model_catalog_node` / `mapping_node` | `executable=` fields | WIRED | Launch file uses `executable='model_catalog_node'` and `executable='mapping_node'` which match `setup.py` console_scripts keys exactly |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `model_catalog_node._catalog_publisher` | `frame_list` | `enumerate_compatible_frames(model_path, opensim_module)` — iterates `getBodySet()` + `getComponentsList()` on real file bytes | Yes — live OpenSim traversal; hash from `Path.read_bytes()` | FLOWING |
| `mapping_node._current_publisher` | `assignments`, `revision`, `applied_revision` | `MappingStore._data` populated by `set_assignment` / `apply_candidate` / `_load()` from persisted JSON | Yes — persisted store with atomic read/write | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `compute_model_hash` returns correct SHA-256 | `test_compute_model_hash_correct` | Passes against `hashlib.sha256(b"hello world").hexdigest()` | PASS |
| Ground body excluded from frame_list | `test_enumerate_compatible_frames_excludes_ground` | "ground" absent from result segments | PASS |
| `apply_candidate` blocked when interlock_active=True | `test_apply_blocked_when_interlock_active` | Returns `{"outcome": "blocked"}` | PASS |
| Atomic write produces `.bak` | `test_backup_on_save` | `.bak` exists after second save | PASS |
| Corruption recovery produces fresh state | `test_corruption_recovery_fresh_start` | revision=0, assignments={} after both files corrupted | PASS |
| Reconnect re-attach preserves assigned state | `test_reconnect_reattach_stays_assigned` | Device state stays "assigned" after fleet registry update | PASS |
| New device from fleet registry gets unassigned | `test_new_device_from_fleet_registry_gets_unassigned` | state="unassigned" for new MAC | PASS |

---

### Probe Execution

No conventional `probe-*.sh` files declared for Phase 22. Test suite serves as the deterministic executable contract.

| Test Suite | Command | Result | Status |
|------------|---------|--------|--------|
| `test_model_catalog_node.py` | `python test/test_model_catalog_node.py -v` | Ran 17 tests in 0.025s — OK | PASS |
| `test_mapping_node.py` | `python test/test_mapping_node.py -v` | Ran 36 tests in 0.209s — OK | PASS |

**Total: 53/53 tests pass.**

---

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| MODEL-01 | SHA-256 hash of raw bytes as model identity | SATISFIED | `hashlib.sha256(path.read_bytes()).hexdigest()` in `compute_model_hash`; 4 hash tests pass |
| MODEL-02 | Compatible non-Ground frames enumerated from model | SATISFIED | `enumerate_compatible_frames` filters ground bodies; 6 frame enumeration tests pass |
| MODEL-03 | Missing/ambiguous/unsupported frames fail closed | SATISFIED | `error_reason` published on every failure; `invalid_frame` returned on stale frame at Apply; no fuzzy match |
| MAP-01 | Assigned/Not used/Unassigned states; duplicate/invalid rejection | SATISFIED | `_VALID_STATES` enforced; duplicate_frame returned; 12 set_assignment tests pass |
| MAP-02 | Solver-sufficiency check (best-effort for Phase 22) | SATISFIED | Warning recorded in `detail` when zero devices assigned; D-20 defers hard block to Phase 23 |
| MAP-03 | Atomic persistence with versioned revision; .bak recovery | SATISFIED | `os.replace()` atomic write; `.bak` on every subsequent save; corruption recovery test passes |
| MAP-04 | Apply validates + stages + swaps atomically; preserves applied_revision on failure | SATISFIED | 7 apply-contract tests pass at both store and node level |
| MAP-05 | Apply blocked during recording/calibration | SATISFIED | `_recording_active`/`_calibration_active` flags; 4 interlock tests pass including state-field variants |
| MAP-06 | MAC reattach under unchanged mapping; different MAC unassigned | SATISFIED | `_on_fleet_registry` D-17 logic; 2 reconnect tests pass |

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| None | — | — | — |

No `TBD`, `FIXME`, `XXX`, `TODO`, `HACK`, or `PLACEHOLDER` markers found in either node file. No stub returns (`return null`, `return {}`, `return []`). No empty handlers. No hardcoded empty props passed to rendering paths.

---

### Human Verification Required

None. All success criteria are verifiable programmatically via the offline test suite. No UI, no real-time behavior, no external hardware, and no visual appearance requirements exist for Phase 22 (backend and ROS services only per 22-CONTEXT.md).

---

### Gaps Summary

No gaps found. All 5 success criteria are VERIFIED with direct codebase evidence and all 53 unit tests passing.

**One design note (not a gap):** The solver-sufficiency check (MAP-02/D-20) is implemented as a best-effort warning rather than a hard block. This is the explicitly correct behavior for Phase 22 — the CONTEXT.md and ROADMAP.md both state that hardening is deferred to Phase 23 when the actual IK solver contracts are wired. The warning path is tested implicitly through the `detail` field in `apply_candidate`.

---

_Verified: 2026-08-05_
_Verifier: Claude (gsd-verifier)_
