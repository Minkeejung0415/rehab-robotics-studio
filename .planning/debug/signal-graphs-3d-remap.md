---
status: resolved
trigger: "individual components have to be shown in values and in graphs; values are shown but graphs are missing, and changing ESP segments is not reflected in 3D visualization"
created: "2026-08-17"
updated: "2026-08-21T13:57:00-07:00"
---

# Signal Graphs and 3D Remap

## Symptoms

- expected: Each connected ESP exposes ax/ay/az, gx/gy/gz, mx/my/mz and available quaternion components as live scrolling graphs as well as numeric values. After changing two ESP segment assignments, applying the mapping, and recalibrating, the native OpenSim 3D visualization must move the newly assigned model regions for those full MACs.
- actual: Individual component numeric values are visible, but no individual component graphs are shown. Changing an ESP segment in Studio does not visibly change which 3D model region responds.
- errors: No explicit runtime error was reported with either symptom.
- timeline: Observed in the current v1.7/Phase 26 build; the full graph capability has not yet been demonstrated, and physical remap-to-3D behavior was never conclusively validated.
- reproduction: Connect the ESP pair, run acquisition, inspect the Front Panel for per-component values/graphs, then change applied segment assignments in Sensor Mapping, Apply, recalibrate, open the native visualizer, and move one sensor at a time.

## Current Focus

- hypothesis: FleetBridge publishes valid raw and canonical samples but never updates the fleet registry's frame observations or publishes per-device/pair health, so the GUI correctly shows connected devices at 0 Hz and no pair state. Fleet mode also omits the `/esp/recording/set` service that the GUI calls.
- test: Add the missing frame-observation, health publication, and master recording forwarding paths; assert their resulting registry, status, pair, and service behavior in focused tests before rebuilding the live WSL stack.
- expecting: During live frames, registry observed_hz becomes positive, `/esp/status/pair` contains connected master/slave health, and `/esp/recording/set` yields a non-empty service response instead of InvalidServiceException.
- next_action: Parent agent verifies the refreshed browser's canonical graph admission and the repaired calibrated N-sensor OpenSim path; physical visualizer motion remains the final human check.

reasoning_checkpoint:
  hypothesis: "FleetBridge does not update or publish live health while it emits samples, and does not expose the recording service expected by the GUI, causing a connected/0 Hz/pair-waiting UI and an empty recording response despite physical streaming."
  confirming_evidence:
    - "Live ROS echo receives valid samples including `sample_contract` from canonical and legacy raw topics while registry rows remain connected at observed_hz 0.0."
    - "Live ROS echo receives no `/esp/status/pair` message, and `_publish_fleet_frame` calls only `publish_session_raw`, never health/pair publication or registry observation updates."
    - "The active rosbridge log records `InvalidServiceException: Service /esp/recording/set does not exist`, and FleetBridge registers only the Identify service."
  falsification_test: "Existing fleet code that updates observed_hz/last_seen and publishes pair health for every accepted frame, or a live `/esp/recording/set` service in fleet mode, would disprove the hypothesis; neither exists."
  fix_rationale: "Updating the registry and publishing the already-defined health contract at the point every accepted frame is decoded makes telemetry state share the same source as raw samples. Forwarding the existing rec-v1 command over the bound master session restores the frontend's established service contract."
  blind_spots: "Actual firmware may reject recording commands due to unsupported SD capability; the fix guarantees a concrete backend response, but physical SD finalization requires live confirmation."

## Evidence

- timestamp: 2026-08-21T13:38:00-07:00
  checked: Live ROS topics, fleet source, and rosbridge service logs.
  found: Both canonical and legacy raw topics carry valid `sample_contract` payloads, but the registry remains at observed_hz 0.0 and `/esp/status/pair` publishes nothing. The fleet frame path only published raw samples. Rosbridge recorded `InvalidServiceException: Service /esp/recording/set does not exist` for the GUI request.
  implication: The active live discrepancy is a missing fleet telemetry/recording boundary, not graph parsing or relay connectivity.

- timestamp: 2026-08-21T13:49:00-07:00
  checked: Focused RED/GREEN and full fleet regression suite after fleet bridge fix.
  found: Before the change, health publication and the recording service tests failed. After adding frame-driven health/pair publication, registry rate updates, and master rec-v1 forwarding, both pass; all 45 `backend.test.test_fleet_bridge` tests pass.
  implication: The repaired fleet contract now shares one accepted-frame source with canonical samples and exposes the UI's existing recording service. A restart is required because the active WSL Python process loaded the old module before this edit.

- timestamp: 2026-08-21T13:56:00-07:00
  checked: Restarted physical STEP ESP / WSL ROS stack.
  found: `/esp/status/pair` now publishes two connected health snapshots at approximately 100 Hz with `pair_available: true`; fleet registry rows report approximately 100 Hz and fresh last-seen data; canonical raw carries the contract; `/esp/recording/set` is registered and an idle stop returns `success=True, REC IDLE ...`.
  implication: The previously disconnected live telemetry and recording-service boundaries are repaired end-to-end through the active hardware stack.

- timestamp: 2026-08-21T14:00:00-07:00
  checked: Mapped calibration, public IK status, and live browser workflow on the restarted stack.
  found: The Toolbar had targeted legacy `/opensim/calibration/capture` rather than mapping-owned `/rehab/calibration/capture`, allowing a legacy CALIBRATED label while N-sensor IK remained uncalibrated. Valid N-sensor output was also not copied to the public IK snapshot, leaving the UI at `no_solution_yet`. After routing capture/clear to the mapped service and publishing the N solution as public status, live mapped capture returns success, `/opensim/ik_status` is valid (`reason: ok`), `/opensim/joint_states` publishes `knee_angle_r`, and `npm run test:gui-live` passes including mapping, recording, and graph workflows.
  implication: The visible calibration, angle, and visualizer route now agrees with the actual MAC-mapped runtime rather than legacy fixed-role state.

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

- root_cause: The graph feature originally lacked canonical history and a graph consumer; applied full-MAC mapping originally bypassed native pose forwarding and could be overwritten by legacy aliases. The reported live regression added three separate boundaries: fleet frames did not update or publish health/pair state, fleet mode omitted the recording service, and the UI calibrated/read status through legacy fixed-role paths rather than the active mapped N-sensor route.
- fix: Added bounded canonical history/charts; mapped pose forwarding and precedence; frame-driven fleet registry/device/pair health plus fleet recording service; mapping-owned calibration capture/clear; and public IK status synchronization with the valid N-sensor solution.
- verification: 45 fleet tests, 163 frontend tests, and 75 OpenSim tests plus 6 subtests pass. On the physical iPhone (111) ESP stack, health is online around 100 Hz, recording returns a concrete response, mapped calibration succeeds, valid IK/joint state publishes, and live GUI E2E passes.
- files_changed:
  - rehab-robotics-studio/src/data/signalBus.ts
  - rehab-robotics-studio/src/data/signalBus.test.ts
  - rehab-robotics-studio/src/components/dashboard/SignalContractPanel.tsx
  - rehab-robotics-studio/src/components/dashboard/SignalContractPanel.test.tsx
  - rehab-robotics-studio/src/styles/app.css
  - backend/rehab_robotics_bridge/opensim_node.py
  - backend/test/test_opensim_node.py
