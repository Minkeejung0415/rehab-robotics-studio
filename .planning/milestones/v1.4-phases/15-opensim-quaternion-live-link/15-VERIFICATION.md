---
phase: 15-opensim-quaternion-live-link
verified: 2026-07-27T20:32:21Z
status: human_needed
score: 10/11 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run the packaged stack with a valid .osim model, importable OpenSim bindings, and simbody-visualizer on PATH; enable the deterministic publisher."
    expected: "The native window opens with labeled master/slave triads; master remains identity and slave shows a positive 90-degree Z rotation, with both roles live on /opensim/status."
    why_human: "The current verifier environment has neither the opensim module nor simbody-visualizer, so the production native-window adapter smoke is dependency-skipped."
  - test: "Run the stack against the paired master and slave ESP devices on the configured sensor_msgs/Imu topics."
    expected: "Each role updates independently, counters and freshness advance, disconnecting or pausing one stream makes only that role stale, and the other role remains live."
    why_human: "Connected ESP hardware is unavailable; deterministic ROS stand-ins prove the contract but not the physical-device/ROS graph integration."
---

# Phase 15: OpenSim Quaternion Live Link Verification Report

**Phase Goal:** Prove the complete live path from the existing ESP `sensor_msgs/Imu` quaternion topics through `opensim_bridge` into mapped OpenSim model-frame orientation updates.
**Verified:** 2026-07-27T20:32:21Z
**Status:** human_needed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

The five ROADMAP success criteria are the non-negotiable contract. LINK-01 through LINK-06 add six requirement-level truths. The score counts those eleven items once each.

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Launching the stack starts `opensim_bridge` with configurable master/slave IMU topics, model path, and frame mappings. | VERIFIED | `rehab_robotics.launch.py:32-40,73-88` declares and wires topics, frames, model, timeout, status, bridge enable, and default-off publisher; launch source contracts pass. |
| 2 | Known valid quaternions on both configured topics produce corresponding orientation updates in the adapter or native visualizer demonstration. | VERIFIED | `OpenSimPublisherBridgeIntegrationTests` passes exact `known_orientations()` message objects through both configured callbacks into the adapter, proving identity/+90Z matrices, mappings, counters, status, and independence. The ROADMAP criterion explicitly permits adapter proof. |
| 3 | ROS `(x,y,z,w)` ordering and the OpenSim rotation convention are documented and deterministically tested. | VERIFIED | `opensim_adapter.py:3-7,39-78`, docs lines 101-104, and identity/+90 X/Y/Z tests at `test_opensim_adapter.py:35-97`; normalization, antipodes, extreme finite values, non-finite, and near-zero cases also pass. |
| 4 | Missing runtime/model assets, invalid inputs, unknown mappings, and stale streams are visible through logs or status. | VERIFIED | Reason-coded adapter fallbacks at `opensim_adapter.py:394-435`; callback/status transitions at `opensim_node.py:144-248`; versioned JSON at lines 251-289; focused invalid, mapping, unavailable, and stale tests all pass. |
| 5 | The local verification path passes without connected ESP hardware. | VERIFIED | Focused suite: 43/43 passed. Full backend discovery: 73 passed, with only 3 explicit native-dependency skips. The deterministic publisher and callback integration require neither ESP devices nor a ROS daemon. |
| 6 | LINK-01: configurable master and slave native `Imu` topics. | VERIFIED | Node defaults/overrides create exactly two `Imu` subscriptions (`opensim_node.py:71-133`); launch and node parameter tests pass. |
| 7 | LINK-02: one documented ROS-to-OpenSim convention boundary. | VERIFIED | All callbacks call only `ros_xyzw_to_opensim_rotation` (`opensim_node.py:155`); the boundary lazily avoids OpenSim imports, validates, normalizes, produces scalar-first semantics, and returns an immutable active matrix. |
| 8 | LINK-03: each ESP input maps to a named OpenSim frame without source changes. | VERIFIED | Launch/node parameters carry `master_frame` and `slave_frame`; adapter resolves exact components through `getComponent` plus `Frame.safeDownCast` and rejects mismatches; override and unknown-frame tests pass. |
| 9 | LINK-04: valid orientations update corresponding frames in a running OpenSim model or native visualizer demonstration. | UNCERTAIN | Fake binding tests prove exact production API ordering, retained decoration mutation, per-role independence, and one `show(state)` per update. The supplied official `opensim==4.6` headless probe passed, but this verifier could not reproduce the production native-window smoke because both `opensim` and `simbody-visualizer` are absent locally; current native smoke is correctly skipped. Human decision is required. |
| 10 | LINK-05: runtime/model/input/mapping/stale failures are visible, not silent. | VERIFIED | Stable visualization reasons remain orthogonal to sensor state; valid input stays live in non-visual mode, invalid data does not refresh freshness, mapping failures affect one role, and stale timers keep publishing. Tests cover each state and transition logging. |
| 11 | LINK-06: a deterministic local publisher proves known messages reach the bridge and expected orientation update without ESP hardware. | VERIFIED | `known_orientations()` emits master identity and slave +90Z; packaged console entry exists; the exact returned `Imu` objects are fed into configured bridge callbacks in the cross-component test. |

**Score:** 10/11 truths verified; 1/11 is uncertain pending native/manual proof.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `backend/rehab_robotics_bridge/opensim_adapter.py` | Pure conversion boundary and optional native adapter | VERIFIED | 435 lines; substantive conversion, unavailable fallback, exact frame lookup, retained/generator decorations, native update, and lazy factory. Manually wired to node. |
| `backend/test/test_opensim_adapter.py` | Pure, fake-binding, real-binding, and native smoke contracts | VERIFIED | Substantive tests; current environment passes always-run contracts and explicitly skips only absent native dependencies. |
| `backend/rehab_robotics_bridge/opensim_node.py` | Dual-Imu bridge, adapter wiring, state/status/staleness | VERIFIED | 301 lines; two subscriptions, one conversion boundary, independent role state, compact JSON, and transition logs. |
| `backend/test/test_opensim_node.py` | ROS-free bridge and lifecycle contracts | VERIFIED | Covers defaults/overrides, independent updates, invalid/out-of-order input, mapping failure, unavailable mode, and stale behavior. |
| `backend/rehab_robotics_bridge/opensim_test_publisher.py` | Deterministic native-Imu publisher | VERIFIED | 108 lines; pure fixtures plus configurable topics/rate and timestamped publication. Wired by setup and launch. |
| `backend/launch/rehab_robotics.launch.py` | Operator launch parameters and optional publisher | VERIFIED | All live-link values wired; test publisher default-off; unrelated pipeline nodes retained. |
| `backend/setup.py` | Console entry points | VERIFIED | Both `opensim_bridge` and `opensim_test_publisher` entries present; preservation test passes. |
| `backend/test/test_opensim_launch.py` | Publisher/launch and cross-component contracts | VERIFIED | Exact producer objects traverse configured callback paths; AST/source launch contracts pass. |
| `docs/opensim-quaternion-live-link.md` | Operator, convention, status, fallback, and scope guide | VERIFIED | Documents launch overrides, deterministic demo, status schema, dependency gate, non-visual fallback, and explicit non-IK meaning. |

`gsd-sdk query verify.artifacts` passed all 8 PLAN-declared artifacts. Its key-link scanner produced three false negatives from escaped regex/target-label handling; manual source inspection and passing behavioral tests verify those links below.

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `opensim_adapter.py` | OpenSim bindings | Lazy `import_module("opensim")` | WIRED | Import occurs only in construction/factory at lines 152 and 416; ordinary module import remains OpenSim-free. |
| `opensim_adapter.py` | Native visualizer | model/frame/decorations/show path | UNCERTAIN | Code and fake contracts verify `setUseVisualizer` before `initSystem`, exact frame lookup/ground position, retained or generator decoration paths, and `show`; actual window needs the missing native dependency. |
| `opensim_node.py` | Master/slave `Imu` topics | Two parameterized subscriptions | WIRED | Lines 121-131 route to separate callbacks; default and override tests pass. |
| `opensim_node.py` | `opensim_adapter.py` | Conversion plus injected/factory adapter | WIRED | Imports at lines 16-19, construction at 109-112, conversion at 155, update at 166. |
| `opensim_node.py` | `/opensim/status` | Compact `std_msgs/String` JSON | WIRED | Publisher at 116-119 and serialized snapshot at 251-289; schema/state tests pass. |
| Launch | Bridge and publisher | `LaunchConfiguration` + `IfCondition` | WIRED | Bridge defaults on; synthetic publisher defaults off and shares both topic values. |
| Publisher | Bridge | Exact known `Imu` objects | WIRED | Cross-component test feeds `known_orientations()` output directly into master/slave callbacks and asserts resulting adapter calls/state. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `opensim_test_publisher.py` | master/slave `Imu.orientation` | Deterministic identity and +90Z fixtures or live ESP publishers on the same configured topics | Yes for deterministic proof | FLOWING |
| `opensim_node.py` | per-role rotation/state/counters | `message.orientation` -> pure conversion -> `adapter.update_sensor` -> role state -> JSON status | Yes in focused cross-component tests | FLOWING |
| `opensim_adapter.py` | native sensor transform | Converted rotation plus exact mapped frame ground position | Contractually yes; native window not locally executable | UNCERTAIN |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Focused Phase 15 contracts | `PYTHONPATH=backend python -m unittest ...` focused adapter/node/launch classes | 43 tests passed in 0.075s | PASS |
| Full backend regression | `PYTHONPATH=backend python -m unittest discover -s backend/test -p test_*.py -v` | 73 passed, 3 native-dependency skips | PASS |
| Installed OpenSim binding contracts | `python -m unittest ...OpenSimInstalledBindingContractTests -v` | 2 skipped: `opensim module is not installed` | SKIP |
| Native visualizer smoke | `python -m unittest ...OpenSimNativeVisualizerSmokeTests -v` | 1 skipped: OpenSim module or `simbody-visualizer` absent | SKIP |
| Syntax and whitespace | `python -m py_compile ...` and `git diff --check -- <phase files>` | Exit 0 | PASS |

The obsolete planned class name `OpenSimInstalledRuntimeSmokeTests` no longer exists because review remediation split it into headless binding and native-window classes. Invoking the old name fails discovery; this is not an implementation failure, but the PLAN/SUMMARY command is stale.

### Probe Execution

No phase PLAN declares a `probe-*.sh`, and no conventional Phase 15 probe exists under `scripts/`; Step 7c is not applicable. The real-binding and native-window `unittest` classes are recorded separately above. The supplied official isolated `opensim==4.6` headless probe result is corroborating external evidence, not a substitute for this verifier's locally skipped native tests.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|---|---|---|---|---|
| LINK-01 | 15-02, 15-03 | Configurable dual native topics | SATISFIED | Node and launch contracts. |
| LINK-02 | 15-01 through 15-03 | Documented single conversion boundary | SATISFIED | Pure boundary, golden tests, docs. |
| LINK-03 | 15-01 through 15-03 | Configurable exact frame mapping | SATISFIED | Parameters, exact lookup, mismatch tests. |
| LINK-04 | 15-01 through 15-03 | Running OpenSim/native visualizer update | NEEDS HUMAN | Production API contract is strong; native runtime/window is dependency-gated locally. |
| LINK-05 | 15-01 through 15-03 | Visible failure and stale status | SATISFIED | Stable reasons, JSON, transition logs, focused tests. |
| LINK-06 | 15-01 through 15-03 | Hardware-free deterministic proof | SATISFIED | Exact publisher-to-callback-to-adapter integration test. |

All six Phase 15 requirements are claimed by plans; there are no orphaned Phase 15 requirements. `REQUIREMENTS.md` still labels them Pending, which is planning-state bookkeeping rather than contrary implementation evidence.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| Phase files | - | No `TBD`, `FIXME`, or `XXX` debt markers | None | No blocker markers. |
| `rehab_robotics.launch.py` | 24-100 | `udp_port`/`filtered_topic` still exist for the ESP acquisition/filter pipeline | INFO | They are unrelated retained nodes, not the removed legacy OpenSim UDP path; `opensim_node.py` contains no legacy forwarding. |
| `opensim_adapter.py` | 10-11 | Explicit non-calibration/non-IK statement | INFO | Search found no calibration, solver, joint-state, coordinate mutation, or IK implementation. Scope is preserved. |

Independent inspection, compilation, focused/full tests, and `git diff --check` found no critical/warning code-quality issue, consistent with the clean Phase 15 review.

### Disconfirmation Pass

- **Partial requirement:** LINK-04 is only contractually/headlessly proven in this environment; the actual native window is unobserved.
- **Potentially misleading test:** Launch tests parse source/AST and do not import or execute a real ROS 2 launch graph. They prove parameter wiring, not runtime ROS discovery.
- **Uncovered environment path:** No automated test here exercises physical ESP devices, DDS transport, a real `.osim` asset, and the native window together. These are the human items below.

### Human Verification Required

#### 1. Native OpenSim Window

**Test:** Install/locate a complete OpenSim/Simbody visualizer runtime, put `simbody-visualizer` on `PATH`, launch with a valid mapped `.osim` model and `enable_opensim_test_publisher:=true`.

**Expected:** A native window opens; both labeled triads appear at the mapped frame origins; master is identity, slave is positive 90 degrees about Z, and `/opensim/status` reports both live.

**Why human:** Visual appearance and the external native executable cannot be verified in the current dependency-limited environment.

#### 2. Live ESP-to-ROS Path

**Test:** Launch against connected master/slave ESP devices, inspect both configured `sensor_msgs/Imu` topics and `/opensim/status`, then pause or disconnect one stream.

**Expected:** Both roles update independently; the paused role alone becomes stale while the other continues live; malformed input is visible and does not terminate the bridge.

**Why human:** Physical devices and a live ROS 2 graph are unavailable.

### Gaps Summary

No code gap or blocker was found. Automated evidence verifies the complete deterministic publisher-to-bridge-to-adapter contract, launch wiring, conversion math, observability, fallback behavior, documentation, and non-IK scope. The escalation is limited to external/native behavior that cannot be reproduced in this verifier environment.

---

_Verified: 2026-07-27T20:32:21Z_
_Verifier: the agent (gsd-verifier)_
