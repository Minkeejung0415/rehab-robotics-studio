---
status: awaiting_human_verify
trigger: "individual components have to be shown in values and in graphs; values are shown but graphs are missing, and changing ESP segments is not reflected in 3D visualization"
created: "2026-08-17"
updated: "2026-08-17T13:25:00-07:00"
---

# Signal Graphs and 3D Remap

## Symptoms

- expected: Each connected ESP exposes ax/ay/az, gx/gy/gz, mx/my/mz and available quaternion components as live scrolling graphs as well as numeric values. After changing two ESP segment assignments, applying the mapping, and recalibrating, the native OpenSim 3D visualization must move the newly assigned model regions for those full MACs.
- actual: Individual component numeric values are visible, but no individual component graphs are shown. Changing an ESP segment in Studio does not visibly change which 3D model region responds.
- errors: No explicit runtime error was reported with either symptom.
- timeline: Observed in the current v1.7/Phase 26 build; the full graph capability has not yet been demonstrated, and physical remap-to-3D behavior was never conclusively validated.
- reproduction: Connect the ESP pair, run acquisition, inspect the Front Panel for per-component values/graphs, then change applied segment assignments in Sensor Mapping, Apply, recalibrate, open the native visualizer, and move one sensor at a time.

## Current Focus

- hypothesis: Confirmed and fixed: canonical signal history/graph consumers were absent, and the MAC-mapped N-sensor pose both failed to reach the native adapter and could be overwritten by the later fixed-role alias callbacks.
- test: User verifies live scrolling component graphs and physical swap-to-model correspondence after Apply and recalibration on the real ESP/OpenSim environment.
- expecting: Every available component has a live graph; swapping the two full-MAC assignments changes which anatomical region responds, with legacy aliases unable to overwrite the mapped pose.
- next_action: Await human verification in the real hardware/native visualizer workflow before resolving and archiving the debug session.

reasoning_checkpoint:
  hypothesis: "Signal graphs are missing because no canonical history or graph consumer exists; remapped 3D motion is missing because the valid N-sensor solve terminates at JointState publication and bypasses the native adapter."
  confirming_evidence:
    - "The frontend regression fails because canonicalHistoryByMac is undefined, and static markup contains values but no per-component graph accessibility labels."
    - "The backend regression reaches a valid solve_n result after applied full-MAC/frame mapping but node._adapter.pose_calls remains empty."
    - "The legacy pair solve calls update_pose, while the N-sensor method contains no update_pose call."
  falsification_test: "A pre-fix bounded history or N-sensor adapter pose call would disprove the corresponding hypothesis; neither exists under deterministic synthetic inputs."
  fix_rationale: "Adding bounded history and rendering consumes the already-validated canonical samples without altering ingress; forwarding the already-valid N-sensor solution to the adapter connects the missing final visualization edge without changing mapping or solver semantics."
  blind_spots: "Native OpenSim window behavior and physical sensor-to-body correspondence still require hardware/native visual verification after deterministic tests; high sensor-count render performance is not load-tested here."

## Evidence

- timestamp: 2026-08-17T12:00:00-07:00
  checked: Debug knowledge base and repository/worktree state.
  found: The only knowledge-base entry concerns rejected raw telemetry and frozen angles; it has fewer than two relevant symptom-keyword overlaps. The worktree is heavily dirty with Phase 26 and unrelated changes, on branch master.
  implication: There is no known-pattern shortcut for these symptoms, and all investigation/fixes must avoid checkout/reset/stash and preserve existing modifications.

- timestamp: 2026-08-17T12:00:00-07:00
  checked: Project skill discovery directories.
  found: Neither .codex/skills nor .agents/skills contains project-defined skills.
  implication: No additional project-local skill rules apply.

- timestamp: 2026-08-17T12:15:00-07:00
  checked: Front Panel canonical signal pipeline (Dashboard, useSignals, SignalBus, SignalContractPanel, MiniChart references).
  found: SignalBus canonical state is latest-sample-only; its only ring buffers are force, EMG, and knee. SignalContractPanel builds value rows and contains no chart consumer. MiniChart is used for other dashboard/block signals but not canonical IMU components.
  implication: Individual component graphs are a missing planned downstream capability, not a chart rendering regression.

- timestamp: 2026-08-17T12:15:00-07:00
  checked: MappingStore applied snapshot and OpenSimBridgeNode remap path.
  found: Apply atomically publishes applied_assignments as assigned full-MAC/frame tuples; _on_mapping_current updates MAC subscriptions and frame fields; _solve_and_publish_ik_n passes those remapped frames to solve_n and publishes JointState, but never calls adapter.update_pose. The only update_pose call is in the legacy fixed master/slave _solve_and_publish_ik path.
  implication: Remapping reaches the N-sensor solver, but its valid solution is not connected to the native visualizer, so visible 3D motion remains on the fixed legacy route regardless of remap.

- timestamp: 2026-08-17T12:40:00-07:00
  checked: New frontend regression tests on the unmodified implementation.
  found: The bounded-history assertion raises because canonicalHistoryByMac is undefined; the component graph assertion sees all numeric channel values but no graph markup.
  implication: The graph hypothesis is directly reproduced and confirmed as missing state plus missing consumer, not CSS or canvas failure.

- timestamp: 2026-08-17T12:40:00-07:00
  checked: New synthetic N-sensor OpenSim regression on the unmodified implementation.
  found: A calibrated, synchronized, valid solve_n execution produces zero adapter.pose_calls.
  implication: The 3D remap symptom is reproduced at the exact solver-to-native-visualizer boundary.

- timestamp: 2026-08-17T13:00:00-07:00
  checked: FleetBridge publication order and native adapter semantics.
  found: FleetBridge publishes the MAC-addressed Imu and then the legacy master/slave alias for the same sample. OpenSimBridgeNode subscribes to both; both solve paths share one adapter, and the legacy path remains calibrated and calls update_pose using fixed frames.
  implication: Merely adding N-sensor update_pose is insufficient under live fleet traffic because the subsequent alias callback can overwrite it. Applied MAC mapping must own native visualization until removed.

- timestamp: 2026-08-17T13:00:00-07:00
  checked: Focused post-fix frontend/backend tests and TypeScript typecheck.
  found: 15 frontend tests pass, the new N-sensor adapter-forwarding test passes, and tsc --noEmit passes.
  implication: The two primary missing boundaries are fixed; mixed-route precedence remains to verify before broader regression testing.

- timestamp: 2026-08-17T13:10:00-07:00
  checked: Mixed-route synthetic regression with both legacy calibration and applied MAC mapping active.
  found: After one mapped adapter pose call, one master and one slave alias callback increase adapter.pose_calls from 1 to 3.
  implication: The live publication order deterministically overwrites remapped visualization with the fixed legacy route; mapped inputs must have adapter ownership precedence.

- timestamp: 2026-08-17T13:25:00-07:00
  checked: Mixed-route regression after mapped visualization precedence fix.
  found: The mapped pose remains the final adapter pose after subsequent master/slave alias callbacks; legacy-only visualization and mapped-only visualization tests remain green within the full OpenSim suite.
  implication: The deterministic dual-source overwrite is removed without retiring backward-compatible legacy subscriptions.

- timestamp: 2026-08-17T13:25:00-07:00
  checked: Full adjacent automated verification.
  found: Backend OpenSim/mapping/adapter suites pass 142 tests with 3 optional skips and 9 subtests; frontend data/deployment/graph suites pass 118 tests; SignalContractPanel passes 13 tests; TypeScript typecheck and Vite production build pass.
  implication: Original synthetic reproductions and adjacent regression coverage are green; only physical sensor/native-window correspondence remains unobservable in this environment.

- timestamp: 2026-08-17T14:05:00-07:00
  checked: Headless browser render of the live localhost Front Panel after the fix.
  found: The Signal Contract panel renders without console/page errors, but the running session reports `0 accepted` and `No canonical samples`; therefore no source cards or graph elements can exist in that session.
  implication: Browser structure and empty-state integration are healthy, but live graph motion cannot be visually confirmed until the ESP canonical stream is connected and accepted.

## Eliminated

## Resolution

- root_cause: The graph feature stopped at latest numeric canonical samples: SignalBus had no per-MAC history and SignalContractPanel had no chart consumer, so this was missing planned capability rather than a rendering regression. The applied full-MAC mapping did reach solve_n, but valid N-sensor solutions were not forwarded to VisualizerAdapter.update_pose. Additionally, FleetBridge publishes each MAC Imu before its legacy role alias, and the calibrated fixed master/slave path subsequently overwrote the same adapter with the pre-remap pose.
- fix: Added immutable bounded 240-sample canonical histories keyed by full MAC; rendered a live MiniChart for every currently available accel, gyro, magnetometer, and quaternion component in the selected raw/SI mode; forwarded valid N-sensor visualization coordinates to the native adapter; and gave applied MAC mapping exclusive adapter-pose ownership while retaining legacy-only compatibility.
- verification: RED tests reproduced missing history/chart markup, zero N-sensor adapter calls, and a deterministic mapped-pose overwrite from 1 to 3 adapter calls. After fixes, 142 backend tests passed (3 optional skips, 9 subtests), 118 frontend suites passed, 13 Signal Contract component tests passed, typecheck passed, and production build passed. Hardware/native visualizer confirmation is pending.
- files_changed:
  - rehab-robotics-studio/src/data/signalBus.ts
  - rehab-robotics-studio/src/data/signalBus.test.ts
  - rehab-robotics-studio/src/components/dashboard/SignalContractPanel.tsx
  - rehab-robotics-studio/src/components/dashboard/SignalContractPanel.test.tsx
  - rehab-robotics-studio/src/styles/app.css
  - backend/rehab_robotics_bridge/opensim_node.py
  - backend/test/test_opensim_node.py
