# Phase 9: Range-Correct Measurement Contract - Research

**Researched:** 2026-07-23
**Domain:** ICM-20948 range acknowledgement, raw ROS JSON metadata, ROS `sensor_msgs/Imu` SI conversion, and rosbridge trust validation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Conversion Ownership
- Preserve integer sensor counts as the canonical values on `/esp/raw/master` and `/esp/raw/slave`.
- Add explicit scale and range metadata rather than replacing raw counts with physical values.
- Use one shared backend definition for mapping supported ranges to scale factors; the GUI converts transmitted counts using the metadata instead of fixed constants.
- Treat the last firmware-acknowledged range stored independently by each bridge node as the source of truth.
- Scale master and slave independently before relative-angle or differential calculations.

### Metadata and Compatibility
- Add a `sensor_config` object to every raw frame containing `accel_range_g`, `gyro_range_dps`, accelerometer and gyroscope LSB sensitivities, and declared units.
- Keep the additive JSON contract under `oe_esp32.raw.v1`; existing consumers may ignore unknown fields.
- Treat live frames without valid scale metadata as untrusted: do not silently assume the default range or emit misleading physical GUI frames.
- Preserve the last confirmed range after an unsupported or rejected request and surface the rejection; never clamp or optimistically update scaling.

### Operator Feedback and Proof
- Reuse the existing confirmed-range controls and physical readouts; do not add a separate scale diagnostics panel.
- Emit one actionable warning per connection when scale context is missing and suppress misleading physical frames until valid metadata arrives.
- Parameterize every supported accelerometer and gyroscope range for both master and slave.
- Compare backend SI output with GUI conversion for identical raw counts and confirmed ranges.
- Do not redesign firmware framing in this phase; sequence and device-time transport are Phase 10.

### the agent's Discretion
- Exact helper/module placement for shared range tables and validation.
- Exact warning wording and whether the one-per-connection latch lives in the data source or system-status integration.
- Test fixture organization, provided every supported range and both device roles are covered.

### Deferred Ideas (OUT OF SCOPE)
- Firmware device timestamps and sequences are Phase 10.
- Physical E-STOP integration, graph persistence, packaging, stale aggregator/documentation, and broad performance optimization remain outside v1.3.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | An operator receives acceleration and angular velocity converted with each device's confirmed active accelerometer and gyroscope ranges. | The shared backend tables, acknowledgement-gated state, native ROS conversion, independent GUI conversion, and parameterized test matrix below define the implementation. [VERIFIED: codebase `esp32_bridge_node.py`, firmware range tables, `RosbridgeDataSource.ts`] |
| DATA-02 | Published raw and live acquisition data carries sufficient range or unit metadata for backend and GUI consumers to interpret samples consistently. | The additive `sensor_config` contract, validation boundary, filtered-envelope preservation, and shared cross-language fixtures below define the proof. [VERIFIED: codebase `pipeline.py`, `RosbridgeDataSource.ts`] |
</phase_requirements>

## Summary

The defect is not in firmware range conversion: both firmware images already program four ICM-20948 presets and use range-sensitive values for VQF input. The break occurs after transport. `Esp32BridgeNode._publish_frame` always uses fixed ±2 g/±250 dps constants, and `RosbridgeDataSource.frameFromRaw` repeats those same defaults. Raw JSON contains no scale context. At ±8 g, 4096 counts is therefore reported as 2.4516625 m/s² rather than 9.80665 m/s²; at ±2000 dps, 4096 counts is reported as 31.25 dps rather than 250 dps. [VERIFIED: codebase `firmware/step_node*/step_node*.ino`, `esp32_bridge_node.py:63-70,718-778`, `RosbridgeDataSource.ts:36-55`; debug probe `acquisition-integrity-2-7.md`]

Range state must be explicitly confirmed before it can label or scale a frame. The current bridge initializes `_accel_range_g` and `_gyro_range_dps` from ROS parameters but does not confirm them during handshake. The GUI calls `/esp_master/set_parameters`, while the launch file names the nodes `esp_bridge_master` and `esp_bridge_slave`; the current service path therefore does not match the launch topology. The master firmware also returns `OK CFG` after applying its own range and merely broadcasts the slave change without a slave acknowledgement, so the master reply cannot establish slave truth. [VERIFIED: codebase `esp32_bridge_node.py:135-189,304-370,470-597`, `rehab_robotics.launch.py:39-45,78-81`, `RosbridgeDataSource.ts:228-248`, firmware `handleCfgLine`/`espNowRelayCfg`]

**Primary recommendation:** add a pure backend measurement-contract module, confirm each bridge node's initial and live ranges against its directly connected firmware, emit the resulting `sensor_config` on every raw frame, use it for native ROS SI conversion, and make rosbridge conversion fail closed before caching or emitting a GUI frame. [VERIFIED: codebase integration points above]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Firmware range programming and acknowledgement | Device firmware | API / Backend bridge | Firmware owns the hardware register change; the directly connected bridge stores state only after `OK CFG`. [VERIFIED: firmware `handleCfgLine`; bridge `_on_set_parameters`] |
| Supported range/sensitivity definition | API / Backend bridge | Device firmware | The backend needs one canonical table for raw metadata and native SI output; its values must exactly match both firmware tables. [VERIFIED: firmware `kAccLsbPerG`/`kGyrLsbPerDps`] |
| Raw JSON `sensor_config` | API / Backend bridge | ROS / rosbridge transport | `_publish_frame` is the sole raw-envelope writer; rosbridge transports the `std_msgs/String` payload unchanged. [VERIFIED: codebase `esp32_bridge_node.py:731-751`, `RosbridgeDataSource.ts:281-313`; CITED: https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/ROSBRIDGE_PROTOCOL.md] |
| `sensor_msgs/Imu` SI conversion | API / Backend bridge | ROS consumers | ROS requires acceleration in m/s² and angular velocity in rad/s. [CITED: https://docs.ros.org/lunar/api/sensor_msgs/html/msg/Imu.html] |
| Metadata validation and GUI conversion | Browser / Client | System Log store | `RosbridgeDataSource` is the raw-to-physical boundary; the Zustand store already owns persistent WARN rows and stream state. [VERIFIED: codebase `RosbridgeDataSource.ts`, `appDataSource.ts`, `systemStore.ts`] |
| Independent master/slave pair math | Browser / Client | — | `frameFromPair` currently performs inclination and gyro subtraction and must receive independently scaled valid device samples. [VERIFIED: codebase `RosbridgeDataSource.ts:118-146`] |

## Project Constraints (from AGENTS.md)

No `AGENTS.md` exists in the workspace, and neither `.codex/skills/` nor `.agents/skills/` exists. Preserve the dirty worktree and modify only Phase 9 files named by the eventual plan. [VERIFIED: filesystem and `git status`, 2026-07-23]

## Current Contract and Exact Gaps

| Layer | Exact file / symbol | Current behavior | Phase 9 action |
|-------|---------------------|------------------|----------------|
| Firmware master | `firmware/step_node/step_node.ino`: `g_acc_preset`, `g_gyr_preset`, `kAccLsbPerG`, `kGyrLsbPerDps`, `icmApplyRangePresets`, `imuRawToVqfPhysical`, `handleCfgLine`, `espNowRelayCfg` | Tables and local range programming are correct; slave relay is broadcast without a slave ACK. [VERIFIED: codebase] | Do not change sample framing. Use direct bridge-to-device acknowledgement for each role; firmware table edits are unnecessary unless tests expose drift. [VERIFIED: codebase] |
| Firmware slave | `firmware/step_node_slave/step_node_slave.ino`: same symbols plus ESP-NOW `CMD_SET_CFG` handler | Direct `CFG` returns `OK CFG`; relayed `CMD_SET_CFG` has no response to the host bridge. [VERIFIED: codebase] | Confirm through the slave bridge's direct TCP control path. [VERIFIED: codebase] |
| Backend table/state | `backend/rehab_robotics_bridge/esp32_bridge_node.py`: constants, `__init__`, `_handshake`, `_on_set_parameters`, `_store_confirmed_control_value` | Fixed scales; parameter defaults are treated as state before firmware confirmation. [VERIFIED: codebase] | Separate desired parameter values from nullable confirmed values; confirm desired ranges before START and update confirmed values only after exact ACK. [VERIFIED: codebase-supported recommendation] |
| Backend publication | `Esp32BridgeNode._publish_frame` | Raw counts are preserved, but no metadata is emitted; native IMU always uses default scales. [VERIFIED: codebase] | Build one validated config snapshot; attach it to raw JSON and use the same snapshot to populate `Imu`. Suppress physical/native publication if no confirmed config exists. [VERIFIED: codebase-supported recommendation] |
| Filtered JSON | `backend/rehab_robotics_bridge/pipeline.py`: `decode_raw`, `SampleFilter.filter_json` | Unknown additive fields survive because the sample dict is mutated in place, but metadata is not validated or tested. [VERIFIED: codebase] | Validate `sensor_config` with the backend helper and assert it survives raw→filtered unchanged. [VERIFIED: codebase-supported recommendation] |
| GUI conversion | `rehab-robotics-studio/src/data/RosbridgeDataSource.ts`: `RawEspMessage`, `numeric`, `frameFromRaw`, `frameFromPair`, `handleMessage` | Fixed constants; missing values become zero; raw messages are cached before trust is established. [VERIFIED: codebase] | Validate and convert the incoming device first; only cache and emit valid converted samples. Drop the invalid arrival without reusing a cached peer to create a new pair frame. [VERIFIED: codebase-supported recommendation] |
| Warning/status | `RosbridgeDataSource.start/stop/handleMessage`, `appDataSource.ts`, `systemStore.addLog/setEspStreamActive` | No metadata warning; any schema-valid frame can invoke `onFrameReceived`. Caches are not fully reset for a new socket. [VERIFIED: codebase] | Reset warning/cache/pair state per created WebSocket; add exactly one WARN callback; invoke first-frame behavior only after valid physical conversion. [VERIFIED: codebase-supported recommendation] |
| Controls | `RosbridgeDataSource.requestImuControl`, `BlockNode.ImuConfigurationControl`, launch `bridge()` | GUI target `/esp_master/set_parameters` disagrees with launched `/esp_bridge_master/set_parameters`; graph values already update only after reported success. [VERIFIED: codebase] | Use actual master/slave service names for range changes; require per-role ACK, preserve per-role confirmed state on rejection, and keep the graph commit after the coordinated success result. [VERIFIED: codebase-supported recommendation] |

## Standard Stack

### Core

| Library / facility | Version | Purpose | Why Standard |
|--------------------|---------|---------|--------------|
| Python standard library (`dataclasses`/mapping helpers, `math`) | Python 3.12.10 available | Immutable range definitions, validation, and conversion | No dependency is needed for a four-entry deterministic contract. [VERIFIED: environment and codebase] |
| ROS 2 `rclpy`, `sensor_msgs`, `std_msgs` | Declared in `backend/package.xml`; local ROS unavailable | Parameter ACK flow, raw String publication, native Imu publication | These are the existing production interfaces. [VERIFIED: `backend/package.xml`; environment] |
| TypeScript | 5.6.3 declared | Typed raw metadata and pure validation/conversion | Existing frontend compiler. [VERIFIED: `package.json`/lockfile] |
| Node `node:test` via `tsx` | Node 24.18.0; `tsx` 4.23.1 declared | Pure frontend contract tests | Existing test pattern; no new runner required. [VERIFIED: environment, `package.json`, deployment tests] |
| Zustand | 4.5.5 declared | Existing System Log and status callback sink | Reuse only; no new UI surface. [VERIFIED: `package.json`, `systemStore.ts`] |

### Supporting Constants

| Range | Firmware preset | Sensitivity |
|-------|-----------------|-------------|
| ±2 g / ±4 g / ±8 g / ±16 g | 0 / 1 / 2 / 3 | 16384 / 8192 / 4096 / 2048 count/g. [VERIFIED: both firmware tables; CITED: https://invensense.tdk.com/wp-content/uploads/2024/03/DS-000189-ICM-20948-v1.6.pdf] |
| ±250 / ±500 / ±1000 / ±2000 deg/s | 0 / 1 / 2 / 3 | 131.072 / 65.536 / 32.768 / 16.384 count/(deg/s). [VERIFIED: both firmware tables] |
| Standard gravity | — | 9.80665 m/s² per g. [VERIFIED: firmware and existing backend/frontend constants] |
| Degree-to-radian conversion | — | π/180. [VERIFIED: firmware and existing backend/frontend constants] |

**Installation:** none. Phase 9 requires no new package, registry component, ROS interface, or firmware library. [VERIFIED: codebase-supported recommendation]

## Package Legitimacy Audit

Not applicable: the recommended implementation installs no external package. `slopcheck 0.6.1` is available, but there are no candidate packages to audit. [VERIFIED: environment]

## Recommended Data Contract

Keep `topic_schema: "oe_esp32.raw.v1"` and add this object to every raw frame:

```json
{
  "sensor_config": {
    "accel_range_g": 8,
    "gyro_range_dps": 2000,
    "accel_lsb_per_g": 4096.0,
    "gyro_lsb_per_dps": 16.384,
    "units": {
      "raw": "count",
      "accel_range": "g",
      "gyro_range": "deg/s",
      "accel_sensitivity": "count/g",
      "gyro_sensitivity": "count/(deg/s)",
      "linear_acceleration": "m/s^2",
      "angular_velocity": "rad/s"
    }
  }
}
```

These exact tokens make the conversion unambiguous while remaining additive to v1. Existing consumers that ignore unknown JSON object fields continue to receive the integer `imu` fields. `SampleFilter.filter_json` will naturally retain the object, but must gain a regression assertion. [VERIFIED: codebase `pipeline.py`; codebase-supported recommendation]

Conversion formulas:

```text
accel_mps2 = raw_count / accel_lsb_per_g * 9.80665
gyro_rad_s = raw_count / gyro_lsb_per_dps * (π / 180)
```

[VERIFIED: firmware `imuRawToVqfPhysical`; CITED: ROS `sensor_msgs/Imu` units]

## Architecture Patterns

### System Architecture Diagram

```text
ACCEL/GYRO selector
        |
        v
pair range coordinator (existing UI, no new surface)
        |
        +--> /esp_bridge_master/set_parameters --> master firmware CFG --> exact ACK
        |                                                   |
        +--> /esp_bridge_slave/set_parameters  --> slave firmware CFG  --> exact ACK
                                                            |
                                                            v
                               per-bridge confirmed ranges (nullable until ACK)
                                                            |
ESP raw counts --> Esp32BridgeNode._publish_frame --> validated config snapshot
                                                  /                         \
                                      raw JSON counts + sensor_config      sensor_msgs/Imu SI
                                                  |
                             rosbridge std_msgs/String publish envelope
                                                  |
                                 validate incoming device before cache
                                      / invalid              \ valid
                           one WARN + drop                convert independently
                                                              |
                                              pair relative/differential math
                                                              |
                                               subscribers/readouts/Streaming
```

### Recommended Project Structure

```text
backend/
├── rehab_robotics_bridge/
│   ├── measurement_contract.py       # canonical tables, config builder/validator, SI helpers
│   ├── esp32_bridge_node.py          # ACK state, raw/native publication
│   └── pipeline.py                   # validate/preserve sensor_config
└── test/
    ├── fixtures/measurement_contract_cases.json
    ├── test_measurement_contract.py
    └── test_esp32_controls.py

rehab-robotics-studio/src/data/
├── measurementContract.ts            # raw metadata type, strict validator/converter
├── measurementContract.test.ts
├── RosbridgeDataSource.ts
└── RosbridgeDataSource.test.ts        # warning/cache/emission behavior
```

[VERIFIED: existing project layout; exact new helper placement is agent discretion]

### Pattern 1: One Config Snapshot Per Published Sample

Build `sensor_config` once from the bridge's confirmed values at the start of `_publish_frame`; use that same object for JSON and native SI conversion. Do not independently look up scales in separate publication branches. [VERIFIED: avoids current duplicated fixed-scale failure]

```python
# Source: project firmware tables + ROS Imu unit contract
config = measurement_config(self._confirmed_accel_range_g, self._confirmed_gyro_range_dps)
raw_json["sensor_config"] = config.as_json()
imu.linear_acceleration.x = accel_count_to_mps2(s16(0), config)
imu.angular_velocity.x = gyro_count_to_rad_s(s16(3), config)
```

### Pattern 2: Confirm Before Commit

Maintain desired ROS parameter values separately from confirmed values. During connection setup, send supported ACC and GYR `CFG` commands to that node before `START`; only exact `OK CFG ACC`/`OK CFG GYR` replies populate confirmed state. Live `_on_set_parameters` keeps the old confirmed value until the corresponding ACK. [VERIFIED: existing firmware accepts CFG before START and current callback stores only after success]

For the existing pair selector, send range requests to both `/esp_bridge_master/set_parameters` and `/esp_bridge_slave/set_parameters`. Report success only when both confirm. If one confirms and the other fails, attempt a compensating command back to the prior value on the changed node; if compensation also fails, log the device-specific divergence and continue scaling each raw role from its own confirmed metadata. Never invent a shared range. [VERIFIED: current topology; partial-failure handling is required to preserve truthful per-node state]

### Pattern 3: Validate Before Cache

Parse the topic role, validate `sensor_config`, and convert that device before assigning `masterRaw`/`slaveRaw`. On invalid input, warn once and return. This prevents an invalid slave arrival from triggering a new emission using a cached master or stale slave. [VERIFIED: current `handleMessage` caches before conversion]

```typescript
// Source: Phase 9 CONTEXT/UI-SPEC
const converted = frameFromRaw(raw);
if (!converted.ok) {
  warnScaleOnce(role);
  return;
}
cacheCurrentConnection(role, converted.frame);
emitSingleOrPair(role);
```

### Anti-Patterns to Avoid

- **Fixed fallback constants:** missing or invalid metadata must not select ±2 g/±250 dps. [VERIFIED: locked decision]
- **Clamping range or sensitivity:** firmware currently clamps presets internally, so the host must validate supported values before I/O and require the matching ACK instead of treating clamping as confirmation. [VERIFIED: firmware `constrain`; bridge mapper]
- **Using graph parameters as measurement truth:** graph values are operator-facing desired/confirmed pair state; each frame must carry the bridge's independently confirmed device state. [VERIFIED: locked decision]
- **Caching before validation:** it can combine untrusted current traffic with a trusted cached peer. [VERIFIED: current data-source flow]
- **Validating only positivity:** positive but inconsistent values such as `accel_range_g=8` with `accel_lsb_per_g=16384` must be rejected. [VERIFIED: UI-SPEC]
- **Changing `topic_schema` to v2:** the decision is an additive v1 object. [VERIFIED: locked decision]
- **Touching `time_us`, `seq`, `sample_index`, OE header layout, or quaternion filtering:** those belong to Phase 10. [VERIFIED: roadmap and locked deferral]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Units for native ROS IMU | A project-specific unit convention | `sensor_msgs/Imu` m/s² and rad/s contract | Downstream ROS consumers already rely on these units. [CITED: https://docs.ros.org/lunar/api/sensor_msgs/html/msg/Imu.html] |
| New transport schema or custom ROS message | A new binary frame or interface package | Add `sensor_config` to existing `std_msgs/String` JSON | This phase is additive and must not pull in Phase 10 framing. [VERIFIED: locked decision] |
| UI diagnostics | New panel/toast/badge | Existing System Log WARN and existing readouts/status | Explicitly locked by UI-SPEC. [VERIFIED: `09-UI-SPEC.md`] |
| Test runner | Vitest/Jest or a new Python dependency | Existing `node:test`/`tsx` and `unittest` | Both already work locally; pytest is absent. [VERIFIED: environment and baseline runs] |
| Cross-language expected values | Independent duplicated expected tables in tests | One checked-in JSON fixture consumed by Python and TypeScript | Directly proves backend/GUI numerical agreement. [VERIFIED: codebase-supported recommendation] |

## Common Pitfalls

### Pitfall 1: Treating Startup Defaults as Firmware ACK
**What goes wrong:** metadata claims a range before the connected device has confirmed it.  
**How to avoid:** confirmed fields start null; perform ACC and GYR confirmation before START/publication.  
**Warning sign:** `_publish_frame` can run while confirmed fields are null or were initialized only from `get_parameter`.  
[VERIFIED: current handshake and initialization]

### Pitfall 2: Master ACK Masquerades as Slave ACK
**What goes wrong:** the master returns `OK CFG` after a best-effort ESP-NOW broadcast, while the slave may not have applied it.  
**How to avoid:** call the directly connected slave bridge and require its own firmware response.  
**Warning sign:** only one parameter service appears in the browser request.  
[VERIFIED: firmware relay and launch topology]

### Pitfall 3: Service Name Drift
**What goes wrong:** `/esp_master/set_parameters` has no corresponding node in the current launch file.  
**How to avoid:** derive constants from launched names (`/esp_bridge_master/set_parameters`, `/esp_bridge_slave/set_parameters`) and assert them in a focused test.  
[VERIFIED: launch and frontend]

### Pitfall 4: Floating-Point Equality
**What goes wrong:** JSON-decoded sensitivities are compared with brittle exact arithmetic after calculation.  
**How to avoid:** accept only finite positive values and compare to the canonical expected sensitivity with a tight explicit tolerance (for example relative tolerance `1e-9`); emit canonical literal table values from Python.  
[VERIFIED: numerical representation risk; recommendation]

### Pitfall 5: Warning Flood or False Streaming
**What goes wrong:** every invalid frame logs, or the first invalid raw message activates the stream.  
**How to avoid:** reset a boolean latch on each newly created WebSocket; invalid frames neither cache, notify listeners, nor invoke `onFrameReceived`. Valid metadata later resumes automatically without a success toast.  
[VERIFIED: UI-SPEC]

### Pitfall 6: Accidentally Reusing Prior-Connection Pair State
**What goes wrong:** master from one socket generation is paired with slave from another.  
**How to avoid:** clear master/slave caches, warning latch, `receivedFrame`, and `RelativeAngleStabilizer` whenever a new WebSocket is created. Do not implement reconnection ownership/retry here; that remains Phase 11.  
[VERIFIED: UI-SPEC and roadmap]

### Pitfall 7: Testing Only Default Range
**What goes wrong:** ±2 g/±250 dps continues to pass even when dynamic lookup is unused.  
**How to avoid:** use a fixed count such as 4096 across every range and both roles; non-default expected values expose the bug immediately.  
[VERIFIED: debug counterexample]

## Code Examples

### Canonical Python Tables

```python
# Source: firmware/step_node/step_node.ino and step_node_slave/step_node_slave.ino
ACCEL_LSB_PER_G = {2: 16384.0, 4: 8192.0, 8: 4096.0, 16: 2048.0}
GYRO_LSB_PER_DPS = {250: 131.072, 500: 65.536, 1000: 32.768, 2000: 16.384}
```

### Deterministic Cross-Consumer Cases

For raw count 4096, expected acceleration is 2.4516625, 4.903325, 9.80665, and 19.6133 m/s² for 2, 4, 8, and 16 g. Expected angular velocity is approximately 0.545415391, 1.090830783, 2.181661565, and 4.363323130 rad/s for 250, 500, 1000, and 2000 deg/s. Store these cases with role `master` and `slave` in `measurement_contract_cases.json`; Python and TypeScript tests must read the same fixture. [VERIFIED: formulas and firmware table]

## State of the Art

| Old Approach | Current Phase 9 Approach | Impact |
|--------------|--------------------------|--------|
| Host assumes default full-scale constants | Per-frame confirmed range and sensitivity metadata | Non-default ranges become interpretable and auditable. [VERIFIED: current defect and locked design] |
| Browser converts any v1-shaped JSON with zero fallback | Browser validates metadata and drops untrusted physical frames | Misleading readouts and false Streaming state are prevented. [VERIFIED: UI-SPEC] |
| One master service path implies pair confirmation | Each bridge directly confirms its connected firmware | Master and slave remain independently truthful. [VERIFIED: current topology] |
| Separate backend and GUI expected values | Shared fixture proves both consumers against identical counts/config | DATA-01 and DATA-02 gain reproducible cross-consumer evidence. [VERIFIED: recommended validation design] |

**Deprecated/outdated:**
- Module constants `ACC_LSB_PER_G`, `GYR_LSB_PER_DPS`, `ACC_SCALE`, and `GYR_SCALE` as single default values in `esp32_bridge_node.py`. Replace with range-indexed contract helpers. [VERIFIED: current code]
- Frontend `ACC_SCALE` and `GYRO_SCALE` constants and `numeric(...)->0` for physical accel/gyro fields. Replace with strict metadata-driven conversion. [VERIFIED: current code]

## Assumptions Log

All implementation claims above were verified against the current filesystem or cited from official ROS/TDK/rosbridge documentation. No `[ASSUMED]` package or design claim is required. [VERIFIED: research record]

## Open Questions

1. **Partial pair-range failure wording**
   - What we know: each bridge must preserve its own confirmed state, the existing graph has one pair selector, and the UI-SPEC requires a normalized rejection message. [VERIFIED: CONTEXT/UI-SPEC/codebase]
   - Recommendation: implement compensation to the previous value and report device-specific detail; if compensation fails, explicitly log that MASTER and SLAVE confirmed ranges differ while continuing metadata-correct conversion. This needs no new UI. [VERIFIED: architecture recommendation]

No question blocks planning. [VERIFIED: research conclusion]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Backend helpers/tests | ✓ | 3.12.10 | — |
| Node.js | Frontend tests/build | ✓ | 24.18.0 | — |
| npm | Frontend scripts | ✓ | 11.16.0 | — |
| `tsx` | Frontend `node:test` execution | ✓ project-local | 4.23.1 declared | `npm exec -- tsx ...` |
| `unittest` | Backend focused tests | ✓ stdlib | Python 3.12 | — |
| pytest | Existing pytest-style pipeline functions | ✗ | — | Add Phase 9 tests as `unittest`; do not install a runner in this phase. |
| ROS 2 CLI/runtime | Live integration test | ✗ | — | Pure controlled bridge objects and contract helpers; target-hardware smoke test remains manual. |

**Missing dependencies with no fallback:** none for implementation and local contract tests. Live ROS/paired-hardware verification is unavailable on this machine and must remain a manual phase gate. [VERIFIED: environment; STATE blocker]

**Baseline:** four frontend `node:test` cases and seven focused backend control `unittest` cases passed on 2026-07-23. The two pure pipeline contract functions also passed through a direct import harness. [VERIFIED: local execution]

## Validation Architecture

### Test Framework

| Property | Backend | Frontend |
|----------|---------|----------|
| Framework | Python `unittest` (stdlib) | Node `node:test` through `tsx` 4.23.1 |
| Config file | None | `rehab-robotics-studio/package.json` |
| Quick run command | `python -m unittest backend.test.test_measurement_contract -v` | `npm exec -- tsx --test src/data/measurementContract.test.ts src/data/RosbridgeDataSource.test.ts` from `rehab-robotics-studio/` |
| Full suite command | `$env:PYTHONPATH='backend'; python -m unittest discover -s backend/test -p 'test_*.py' -v` | `npm test` after extending the script to include `src/data/*.test.ts` |

[VERIFIED: environment and existing test patterns]

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | Every accel/gyro range converts raw counts correctly in backend SI for master and slave | unit, table-driven | `python -m unittest backend.test.test_measurement_contract -v` | ❌ Wave 0 |
| DATA-01 | GUI produces the same SI values from the same shared cases after independent master/slave validation | unit, shared fixture | `npm exec -- tsx --test src/data/measurementContract.test.ts` | ❌ Wave 0 |
| DATA-01 | Rejected/unsupported request retains prior confirmed value; successful state changes only after ACK | controlled bridge + frontend service test | `python -m unittest backend.test.test_esp32_controls -v` and `npm exec -- tsx --test src/data/RosbridgeDataSource.test.ts` | ⚠️ existing file needs cases / ❌ frontend file |
| DATA-02 | Every raw JSON frame contains exact additive `sensor_config`; native Imu uses the same config | controlled `_publish_frame` unit | `python -m unittest backend.test.test_measurement_contract -v` | ❌ Wave 0 |
| DATA-02 | Filtered JSON preserves the validated config unchanged | unit | `python -m unittest backend.test.test_measurement_contract -v` | ❌ Wave 0 |
| DATA-02 | Missing/incomplete/unsupported/non-finite/inconsistent/wrong-unit metadata emits no frame, no first-frame callback, and one WARN per connection | data-source unit with fake WebSocket | `npm exec -- tsx --test src/data/RosbridgeDataSource.test.ts` | ❌ Wave 0 |
| DATA-02 | A later valid frame resumes; new connection resets warning, caches, and pair stabilizer | data-source unit with fake WebSocket | same command | ❌ Wave 0 |
| DATA-01/02 | Existing selectors remain ACK-driven and UI layout/readouts are unchanged | build + focused manual smoke | `npm run typecheck` plus manual UI-SPEC checklist | existing controls; new smoke case required |

### Required Test Matrix

- Roles: `master`, `slave`. [VERIFIED: requirement]
- Accelerometer ranges: `2`, `4`, `8`, `16` g. [VERIFIED: firmware/UI]
- Gyroscope ranges: `250`, `500`, `1000`, `2000` deg/s. [VERIFIED: firmware/UI]
- Metadata rejection partitions: absent object; missing field; unsupported range; zero/negative/NaN/Infinity sensitivity at pure-helper boundary; range/sensitivity mismatch; missing/wrong unit token. [VERIFIED: UI-SPEC]
- Pair ordering: valid master only; valid slave only; valid master+slave; invalid incoming master with cached valid slave; invalid incoming slave with cached valid master; reconnect then one role only. [VERIFIED: current cache/pair risks]
- ACK outcomes: both success; unsupported rejected before I/O; master reject; slave reject; partial success with compensation success; partial success with compensation failure. [VERIFIED: topology risk]

### Sampling Rate

- **Per task commit:** run the directly affected backend or frontend quick command. [VERIFIED: validation recommendation]
- **Per wave merge:** run backend discovery, frontend `npm test`, and `npm run typecheck`. [VERIFIED: existing scripts]
- **Phase gate:** all automated suites green, then inspect one raw message and one native `sensor_msgs/Imu` sample for a non-default range on each connected device when hardware is available. [VERIFIED: requirement and environment limitation]

### Wave 0 Gaps

- [ ] `backend/rehab_robotics_bridge/measurement_contract.py` — pure contract seam.
- [ ] `backend/test/fixtures/measurement_contract_cases.json` — shared Python/TypeScript cases.
- [ ] `backend/test/test_measurement_contract.py` — table, JSON, native SI, filtered preservation.
- [ ] `rehab-robotics-studio/src/data/measurementContract.ts` — pure browser validation/conversion seam.
- [ ] `rehab-robotics-studio/src/data/measurementContract.test.ts` — shared-fixture conversion/rejection cases.
- [ ] `rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts` — warning latch/cache/emission/service ACK behavior.
- [ ] Extend `rehab-robotics-studio/package.json` test script to include `src/data/*.test.ts`; install nothing.

### VALIDATION.md Acceptance Checklist

1. Raw counts remain integers and `topic_schema` remains `oe_esp32.raw.v1`. [VERIFIED: locked decision]
2. `sensor_config` is present and internally consistent on every accepted raw/filtered frame. [VERIFIED: DATA-02]
3. Native ROS and GUI results match the shared fixture for all ranges and both roles. [VERIFIED: DATA-01]
4. Invalid metadata causes zero subscriber emissions, zero `onFrameReceived` calls, and exactly one System Log WARN per connection. [VERIFIED: UI-SPEC]
5. Valid metadata later resumes without a success toast. [VERIFIED: UI-SPEC]
6. Rejected requests do not overwrite the rejecting node's last confirmed scale. [VERIFIED: locked decision]
7. No timestamp, sequence, OE framing, quaternion, recovery retry, or freshness behavior is changed. [VERIFIED: phase boundary]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No authentication boundary changes in Phase 9. [VERIFIED: scope] |
| V3 Session Management | no | WebSocket lifecycle redesign is Phase 11. [VERIFIED: roadmap] |
| V4 Access Control | no | Existing ROS parameter-service exposure is unchanged. [VERIFIED: scope] |
| V5 Input Validation | yes | Strict structural, finite-number, supported-enum, unit-token, and cross-field consistency validation before physical use. [VERIFIED: UI-SPEC] |
| V6 Cryptography | no | No cryptographic operation or secret is introduced. [VERIFIED: scope] |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed or spoofed `sensor_config` creates unsafe physical values | Tampering | Fail closed; validate all fields and range/sensitivity agreement before cache/emission. [VERIFIED: threat from raw external JSON boundary] |
| NaN/Infinity poisons pair math | Tampering / Denial of Service | `Number.isFinite`/`math.isfinite` and positive checks in pure validators. [VERIFIED: UI-SPEC] |
| Invalid-frame log flood | Denial of Service | One warning latch per WebSocket connection. [VERIFIED: UI-SPEC] |
| Stale peer sample crosses connection boundary | Tampering / data integrity | Clear caches and pair stabilizer when a new socket is created. [VERIFIED: UI-SPEC] |

## Sources

### Primary (HIGH confidence)

- Current codebase: `firmware/step_node/step_node.ino`, `firmware/step_node_slave/step_node_slave.ino` — supported presets, sensitivities, direct ACK and unacknowledged relay behavior.
- Current codebase: `backend/rehab_robotics_bridge/esp32_bridge_node.py`, `pipeline.py`, `backend/launch/rehab_robotics.launch.py` — confirmed state, publication, filter preservation, and service names.
- Current codebase: `rehab-robotics-studio/src/data/RosbridgeDataSource.ts`, `appDataSource.ts`, `BlockNode.tsx`, `systemStore.ts` — fixed conversion, pairing, controls, warnings, and stream activation.
- TDK InvenSense ICM-20948 datasheet v1.6: https://invensense.tdk.com/wp-content/uploads/2024/03/DS-000189-ICM-20948-v1.6.pdf — ranges and accelerometer sensitivity table.
- ROS `sensor_msgs/Imu`: https://docs.ros.org/lunar/api/sensor_msgs/html/msg/Imu.html — SI unit requirements.
- Official rosbridge protocol: https://github.com/RobotWebTools/rosbridge_suite/blob/ros2/ROSBRIDGE_PROTOCOL.md — JSON publish/subscribe and service envelope behavior.

### Secondary (MEDIUM confidence)

- `.planning/debug/acquisition-integrity-2-7.md` — reproducible fixed-scale counterexamples and current coverage gaps, cross-checked against source.

### Tertiary (LOW confidence)

- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — uses only installed/current project facilities; no dependency selection.
- Architecture: HIGH — exact writers, readers, ACKs, launch names, and pair math were traced in the current dirty worktree.
- Pitfalls: HIGH — each critical pitfall is either reproduced in the debug record or follows directly from the current writer-reader path.

**Research date:** 2026-07-23  
**Valid until:** 2026-08-22, or until the bridge, launch node names, raw schema, or firmware range tables change.
