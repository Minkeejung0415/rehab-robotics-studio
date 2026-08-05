# Phase 25: Multi-Device Compatibility and Promotion Gate - Context

**Gathered:** 2026-08-05
**Status:** Ready for planning

<domain>
## Phase Boundary

The dynamic N-sensor multi-device workflow (fleet_bridge, mapping, N-sensor calibration, IK) must coexist safely with the legacy two-sensor workflow. Phase 25 adds deterministic acceptance tests for all edge cases identified across Phases 20-24, verifies the legacy compatibility path continues to pass, creates a hardware acceptance evidence template, and — only when evidence is complete — promotes dynamic mode to the default launch configuration. Does not include new hardware features or new sensor types.

</domain>

<decisions>
## Implementation Decisions

### Rollback / Legacy Mode (COMP-01)
- **D-01:** "Rollback mode" is `use_fleet_bridge:=false` (the existing default in `rehab_robotics.launch.py`). No new launch parameter is needed — the flag already gates the legacy `esp32_bridge_node` path vs. the new `fleet_bridge_node` path. Document this explicitly in the acceptance report.
- **D-02:** Legacy workflow contracts are verified by a new `backend/test/test_compat_legacy.py`. This file exercises the same contracts as Phase 15–19 tests (recording, calibration, joint-state, pair health, frequency/range) but instantiates nodes with `use_fleet_bridge=false`-equivalent constructor args (no fleet_bridge, no mapping, fixed master/slave topics). This proves legacy mode does not regress.
- **D-03:** The full existing test suite must pass before Phase 25 is considered done. The verification step runs `python -m pytest backend/test/` (or equivalent) and confirms all existing 18+ test files exit 0. Any pre-existing failures that pre-date Phase 25 are documented in the acceptance report's Compatibility Evidence section.

### Acceptance Tests (COMP-02)
- **D-04:** All COMP-02 deterministic edge-case tests live in a single new file: `backend/test/test_acceptance.py`. Organized into test classes:
  - `FullMacCollisionTests` — two devices with same low-32 bits get distinct canonical IDs
  - `ArbitraryDiscoveryOrderTests` — registry stable regardless of first-seen order
  - `DhcpReconnectTests` — identity stable across IP change and TCP reconnect
  - `IdentifyFailureTests` — Identify timeout, offline, rejected all handled without side effects
  - `PartialApplyRollbackTests` — Apply with stale revision leaves previous applied_revision intact
  - `CorruptPersistenceTests` — corrupted mapping_store.json triggers atomic recovery (empty/backup)
  - `StaleSkewedSampleTests` — stale IMU sample or skewed pair suppresses IK output; acquisition continues
  - `InterlockTests` — Apply blocked during recording; recording not stopped
  - `RepeatedResourceCleanupTests` — repeated remap creates and destroys N subscriptions without leak
- **D-05:** Test stubs and offline-node patterns follow the established pattern from `test_opensim_node.py` and `test_mapping_node.py` (stub `rclpy`, inject mock messages, assert outcomes). No live ROS required.
- **D-06:** The CROSS_LAYER_* constants from `test_stepesp_firmware_topology.py` are imported (not duplicated) in `test_acceptance.py` to maintain one canonical identity matrix across all layers.

### Hardware Acceptance Document (COMP-03)
- **D-07:** Hardware acceptance evidence is stored at `docs/hardware-acceptance-report.md`. This is a structured Markdown document with the following sections:
  1. **Fleet configuration tested** — number of devices, device IDs, roles, firmware version
  2. **Identify safety** — confirm Identify works for each device without disrupting others
  3. **Acquisition continuity** — Master + N-1 Slave acquisition at target Hz with no data loss
  4. **Recording continuity** — full record/stop cycle with N sensors; verify no dropped frames at device reconnect
  5. **Reconnect under load** — physically power-cycle one Slave; confirm recovery and re-attachment
  6. **Radio/relay load** — measured throughput at full fleet size; compare to single-device baseline
  7. **OpenSim solve latency** — wall-clock latency from IMU frame to `/rehab/opensim/joint_states` for N sensors
  8. **Compatibility aliases** — confirm `/esp32/master/imu` and `/esp32/slave/imu` still publish matching data
- **D-08:** The file ships with evidence sections pre-filled with "PENDING HARDWARE TEST" placeholders. Each section has a `STATUS: PENDING | PASS | FAIL` marker. The promotion gate (D-09) reads these markers.
- **D-09:** A Python script `scripts/acceptance_gate.py` reads `docs/hardware-acceptance-report.md` and returns exit 0 if ALL sections have `STATUS: PASS`, exit 1 otherwise. This script is the machine-checkable gate.

### Promotion Gate (COMP-03 / SC-4)
- **D-10:** The promotion gate is the switch from `default_value='false'` to `default_value='true'` on the `use_fleet_bridge` argument in `rehab_robotics.launch.py`. This change is gated on `scripts/acceptance_gate.py` exiting 0.
- **D-11:** Phase 25 creates the `docs/hardware-acceptance-report.md` template and `scripts/acceptance_gate.py`. The final plan task runs `acceptance_gate.py`; if it exits 0 (all sections PASS), it updates the `use_fleet_bridge` default in the launch file. If it exits 1 (sections still PENDING/FAIL), the launch default remains `false` and the VERIFICATION.md notes the gate is open. This is the correct outcome for an automated run — the gate requires physical hardware evidence the CI pipeline cannot provide.
- **D-12:** The ROADMAP.md Phase 25 note will indicate the gate status: "Gate OPEN — hardware evidence pending" or "Gate CLOSED — dynamic mode is default". Phase 25 is considered complete once the test suite (COMP-01 + COMP-02) is green and the acceptance template + gate script exist, regardless of whether physical evidence has been gathered.

### Plan Structure
- **D-13:** 3 plans in 2 waves:
  - Wave 1 (parallel):
    - `25-01`: `test_compat_legacy.py` — legacy workflow verification tests (COMP-01)
    - `25-02`: `test_acceptance.py` — all 9 COMP-02 acceptance test classes
  - Wave 2 (blocked on Wave 1):
    - `25-03`: `docs/hardware-acceptance-report.md` + `scripts/acceptance_gate.py` + conditional `use_fleet_bridge` default flip (COMP-03 + SC-4)

</decisions>

<canonical_refs>
## Canonical References

Downstream agents MUST read these before planning or implementing.

### Test Infrastructure
- `backend/test/test_opensim_node.py` — ROS stub pattern: `_install_ros_stubs()`, `_StubNode`, `_StubPublisher`
- `backend/test/test_mapping_node.py` — mapping node test pattern; `apply_candidate()` test structure
- `backend/test/test_stepesp_firmware_topology.py` — `CROSS_LAYER_*` identity constants (import these, don't copy)
- `backend/test/test_n_sensor_calibration.py` — `CalibrationArtifactStore` test pattern
- `backend/rehab_robotics_bridge/mapping_node.py` — `apply_candidate()` behavior, `SOLVER_PROFILE_MIN_SENSORS`
- `backend/rehab_robotics_bridge/opensim_node.py` — `_check_sync_skew()`, `_on_fleet_registry()`, subscription teardown

### Launch Infrastructure
- `backend/launch/rehab_robotics.launch.py` — `use_fleet_bridge` launch arg (D-01); existing legacy vs. fleet branch structure

### Backend Modules for Stub Construction
- `backend/rehab_robotics_bridge/fleet_bridge_node.py` — FleetBridgeNode constructor for test isolation
- `backend/rehab_robotics_bridge/opensim/n_sensor_calibration.py` — CalibrationArtifactStore

### Requirements
- `.planning/REQUIREMENTS.md` §COMP-01, COMP-02, COMP-03

</canonical_refs>

<code_context>
## Existing Code Insights

### ROS Stub Pattern (replicate exactly)
The offline-test pattern from Phase 20-23 uses `_install_ros_stubs()` at module level to register `rclpy`, `sensor_msgs`, etc. as fake modules. Follow this exact pattern in `test_acceptance.py` and `test_compat_legacy.py`:
```python
import sys, types

def _install_ros_stubs():
    if 'rclpy' not in sys.modules:
        rclpy = types.ModuleType('rclpy')
        # ... (follow test_opensim_node.py pattern exactly)
        sys.modules['rclpy'] = rclpy
    # ... register all needed stubs
_install_ros_stubs()
```

### Legacy Mode Configuration
Legacy mode constructor args (from launch analysis):
- Uses `esp32_bridge_node` (dual, fixed IP/port) instead of `fleet_bridge_node`
- No `mapping_node` or `model_catalog_node`
- Fixed `master_imu_topic = '/esp32/master/imu'`, `slave_imu_topic = '/esp32/slave/imu'`
- OpenSim bridge uses `master_frame` / `slave_frame` named topics directly

### Acceptance Gate Script Pattern
`scripts/acceptance_gate.py` uses only stdlib (no external deps):
```python
import re, sys
from pathlib import Path
report = Path(__file__).parent.parent / 'docs' / 'hardware-acceptance-report.md'
statuses = re.findall(r'STATUS:\s*(\w+)', report.read_text())
if not statuses or any(s != 'PASS' for s in statuses):
    print('Gate OPEN — not all sections PASS')
    sys.exit(1)
print('Gate CLOSED — all sections PASS')
sys.exit(0)
```

### Key Test Imports Needed
- From `test_stepesp_firmware_topology.py`: `CROSS_LAYER_SELF_ID`, `CROSS_LAYER_PEER_IDS`, `CROSS_LAYER_LOW32_COLLISION_IDS`, `CROSS_LAYER_IDENTIFY_OUTCOMES`
- From `backend.rehab_robotics_bridge.opensim.ik_contracts`: `SOLVER_PROFILE_MIN_SENSORS`

</code_context>

<specifics>
## Specific Ideas

- `test_compat_legacy.py`: The simplest legacy-compatibility proof is to instantiate `OpenSimBridgeNode` with `mapping_node=None` (or no mapping parameters) and verify the existing Phase 15-19 contracts still hold: calibration, joint state publication, stale timeout. This exercises the two-sensor path independently.
- `test_acceptance.py` `PartialApplyRollbackTests`: Requires applying a mapping at revision N, then calling `apply_candidate()` with revision N-1 (stale) and verifying `applied_revision` remains N.
- `test_acceptance.py` `RepeatedResourceCleanupTests`: Call `_on_mapping_current()` 20 times with alternating device lists, assert `len(_mac_inputs)` stays bounded (≤ devices_in_last_mapping).
- The acceptance report template should include a "Tested by / Date" field so evidence is traceable.
- `scripts/acceptance_gate.py` should also print which sections are still PENDING/FAIL for operator UX.
- Phase 25 does NOT change any behavior in production code — it is purely additive (tests + docs + gate script). The only optional production change is the `use_fleet_bridge` default flip, which is gated on the acceptance report.

</specifics>

<deferred>
## Deferred Ideas

- Automated hardware test runner (Python script that drives firmware and measures rates programmatically) — requires physical hardware and is out of scope for a CI-executable phase.
- Per-device rate histogram or recording integrity byte-count verification — future observability work.
- Fleet OTA, battery analytics — future phases.
- Profile-defined partial-sensor IK — explicitly out of scope per REQUIREMENTS.md.
- Mixing dynamic and legacy modes in the same launch (hybrid mode) — not needed; the two modes are mutually exclusive.

</deferred>

---

*Phase: 25-multi-device-compatibility-and-promotion-gate*
*Context gathered: 2026-08-05 (--auto)*
