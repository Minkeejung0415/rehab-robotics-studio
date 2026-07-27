---
status: resolved
trigger: "with the current version although it says both esp are connected, there isn't a change in angle displayed on teh gui"
created: "2026-07-27"
updated: "2026-07-27T11:30:00-07:00"
---

# Angle Display Not Updating

## Symptoms

- expected: Moving either ESP should cause the angle displayed in the GUI to change.
- actual: Both ESP devices report connected, but the displayed angle does not change.
- errors: No visible browser, backend, or ROS errors have been observed.
- timeline: This worked previously with the same two-ESP setup and is now a regression in the current version.
- reproduction: Connect both ESP devices until the GUI reports both connected, then move either ESP and observe that the displayed angle remains unchanged.

## Current Focus

- hypothesis: Resolved — the launcher executed a stale WSL bridge that published `oe_esp32.raw.v1` without required `sensor_config`; rebuilding the deployed package restored valid telemetry and angle updates.
- test: Completed automated contract/regression checks and human end-to-end verification with the physical master/slave ESP pair.
- expecting: Both devices connect, valid `/esp/raw/master` and `/esp/raw/slave` frames flow, and moving either device changes the GUI knee angle.
- next_action: Archive the resolved debug session and commit the two regression tests plus debug record.
- reasoning_checkpoint:
    hypothesis: "The angle is frozen because the deployed WSL backend emits raw ESP JSON without sensor_config, and RosbridgeDataSource rejects such frames before updating masterFrame/slaveFrame."
    confirming_evidence:
      - "The launcher sources /home/justi/.rehab-install-v12, and module introspection resolves to /home/justi/.rehab-build-v12 rather than this workspace."
      - "The deployed _publish_frame raw_json has no sensor_config, while RosbridgeDataSource returns before caching/emitting when validateSensorConfig fails."
      - "Live relay/bridge logs show both devices reach STARTED/SENSORS, matching green connection health while the frontend receives no valid frame."
    falsification_test: "If rebuilding the deployed package still leaves its _publish_frame without sensor_config, or if a valid master/slave frame pair is rejected after deployment, this diagnosis is wrong or incomplete."
    fix_rationale: "Deploying the current bridge establishes confirmed ranges in text mode before START and includes the resulting canonical sensor_config in every raw message, satisfying the frontend contract at its rejection boundary."
    blind_spots: "The physical two-ESP workflow cannot be end-to-end verified until the stack is restarted on STEP_ESP32 Wi-Fi; old firmware without CFG relies on the current default-range fallback."
- tdd_checkpoint:

## Evidence

- timestamp: "2026-07-27T10:31:00-07:00"
  checked: Debug knowledge base and project-defined skill directories.
  found: No knowledge-base.md exists, and neither .codex/skills nor .agents/skills contains a project skill.
  implication: There is no known-pattern candidate or project-specific rule set; investigation must trace the live code path directly.

- timestamp: "2026-07-27T10:34:00-07:00"
  checked: Repository inventory, git status, and broad angle/ESP/telemetry search.
  found: The relevant implementation spans rehab-robotics-studio/src and backend/rehab_robotics_bridge. The worktree already contains extensive user changes, including esp32_bridge_node.py and several frontend state/UI files. Large historical JSONL result files made the broad search noisy.
  implication: Preserve all existing edits and narrow investigation to source/config/tests; do not infer the fault from historical data or overwrite dirty files.

- timestamp: "2026-07-27T10:37:00-07:00"
  checked: Source-only symbol search across frontend, backend, launch/config, and tests.
  found: RosbridgeDataSource subscribes to /esp/raw/master and /esp/raw/slave, computes a stabilized paired relative angle, and emits a Frame. SignalBus derives the displayed `kneeAngle` specifically as `out.knee ?? 0`.
  implication: Connection health and angle display have separate data paths. A missing graph output named `knee` can leave both ESPs connected while pinning the display to zero, so the graph execution contract is a high-priority state-management/data-shape hypothesis.

- timestamp: "2026-07-27T10:40:00-07:00"
  checked: Full RosbridgeDataSource, SignalBus, app data-source selection, dashboard consumer, signal types, and exact knee references.
  found: RosbridgeDataSource encodes paired relative angle back into `frame.imu.accel` as gravity components. SignalBus passes that frame through runMockExecutor, whose `esp32_imu` and `opensim_ik_mock` blocks produce the value consumed by `joint_angle_display`. React renders `kneeAngle.toFixed(1)` directly as degrees.
  implication: React subscription/render is straightforward. The next differentiating test is the executor's IMU-to-angle math and units; it is the single transformation between the paired angle and the displayed number.

- timestamp: "2026-07-27T10:44:00-07:00"
  checked: Complete runMockExecutor and relevant working-tree diffs.
  found: The executor maps inclination monotonically into the displayed value, so hardware motion would still change the display despite its mock scaling. In contrast, the backend diff shows CFG range confirmation was moved from after START to before START, with a fallback that prevents publication suppression when old firmware lacks CFG support.
  implication: The executor unit issue does not explain a fully static display and is deprioritized. The backend handshake/publication gate is a specific, falsifiable regression candidate matching connected-without-telemetry.

- timestamp: "2026-07-27T10:48:00-07:00"
  checked: Bridge connection, health, handshake, and publication code plus log inventory.
  found: `_connection_state` becomes `connected` immediately after handshake, while pair health marks the pair available solely from the slave's connection state. Frame counters/rate are separate. Confirmed sensor ranges initialize as null and are required to attach valid `sensor_config`; the current diff explicitly prevents the former post-START CFG failure from leaving publication suppressed. The latest GUI/relay logs are from the user's reproduction time.
  implication: The GUI can truthfully show both ESPs connected even when no usable raw frames reach RosbridgeDataSource. This directly supports the handshake/range-gate hypothesis; current logs and tests can provide the remaining causal confirmation.

- timestamp: "2026-07-27T10:52:00-07:00"
  checked: Reproduction-time GUI, relay, and serial logs plus backend control/topology tests.
  found: The relay log records the exact old sequence for both devices: REDPITAYA, then START, then STARTED/SENSORS, with no CFG range commands. The connections are then forcibly closed and subsequent attempts time out. `_publish_frame` counts received frames but returns without publishing whenever either confirmed range is null. All 19 existing backend control/topology tests pass, but none asserts handshake CFG ordering.
  implication: Direct runtime evidence matches the hypothesized mechanism. Existing tests missed the regression, so deployment path and a focused handshake-order regression test are needed before declaring the fix verified.

- timestamp: "2026-07-27T10:56:00-07:00"
  checked: Launcher deployment path, installed WSL module introspection, and live master/slave bridge logs.
  found: The launcher sources `/home/justi/.rehab-install-v12`; Python resolves the bridge to `/home/justi/.rehab-build-v12/.../esp32_bridge_node.py`. That deployed `_handshake` sends REDPITAYA then START and contains no range confirmation at all. Live logs match it exactly: both nodes reach STARTED/SENSORS, stay connected for about 38 seconds, then close and repeatedly fail handshakes. Current workspace source has the corrected CFG-before-START sequence.
  implication: The reproduction ran stale deployed backend code, not current source. This explains why a source-level fix had no effect and confirms deployment staleness as part of the root cause.

- timestamp: "2026-07-27T11:00:00-07:00"
  checked: Deployed WSL `_publish_frame` implementation against the current frontend validation boundary.
  found: The deployed bridge does publish `/esp/raw/*`, but its `raw_json` omits `sensor_config`. RosbridgeDataSource calls `validateSensorConfig(raw.sensor_config)` and immediately returns on failure without updating either cached device frame or notifying signal listeners. Connection/pair health is published separately.
  implication: This is the exact first divergence: transport health is green, but every telemetry frame is discarded as an old-schema message. Root cause is confirmed and the current source contract plus deployment must be fixed/verified.

- timestamp: "2026-07-27T11:07:00-07:00"
  checked: New handshake-order regression plus existing backend control/topology tests.
  found: All 20 tests pass. The new test proves the current bridge writes REDPITAYA, CFG ACC, CFG GYR, then START and retains confirmed ranges.
  implication: Source behavior is protected against the exact handshake-order regression; the remaining fix step is deploying that source into the WSL install actually used by the launcher.

- timestamp: "2026-07-27T11:14:00-07:00"
  checked: Targeted WSL colcon rebuild using the current backend source and the launcher's existing build/install bases.
  found: `rehab_robotics_bridge` rebuilt successfully into `/home/justi/.rehab-install-v12` with symlink install.
  implication: New bridge processes launched from the normal script will load the corrected source; verification must now confirm the installed module contents and cross-layer tests.

- timestamp: "2026-07-27T11:18:00-07:00"
  checked: Rebuilt WSL module introspection, full backend unit suite, frontend data/deployment suite, and production build.
  found: Deployed module reports CFG-before-START=true, sensor_config emission=true, and the confirmed-range guard=true. All 27 backend tests and all 17 frontend tests pass. TypeScript/Vite production build passes; only the known `#`-in-path warning remains.
  implication: Deployment and contract-level verification pass. One changing-angle injection test remains to verify the original symptom through the paired-frame math rather than only frame acceptance.

- timestamp: "2026-07-27T11:25:00-07:00"
  checked: New paired-angle regression, backend suite, and production build.
  found: The paired-angle regression passes and proves moving the slave changes the emitted pair-frame inclination proxy; all backend tests pass. Production typecheck rejected two test-only uses of `Array.at` because the project targets an older JavaScript library.
  implication: Runtime behavior is correct; verification is not complete until the test uses target-compatible indexing and the production build passes again.

- timestamp: "2026-07-27T11:29:00-07:00"
  checked: Final automated verification after target-compatible test adjustment.
  found: All 27 backend tests pass, all 18 frontend data/deployment tests pass (including moving-slave angle change), and the TypeScript/Vite production build passes. The rebuilt deployed module was separately introspected with CFG-before-START, sensor_config emission, and range guard all present.
  implication: The fix is self-verified across deployment, backend contract, frontend acceptance, paired-angle math, and production build. Only the physical two-ESP workflow remains for human confirmation.

- timestamp: "2026-07-27T11:30:00-07:00"
  checked: Human end-to-end verification with the physical two-ESP workflow.
  found: User confirmed the original frozen-angle issue is fixed.
  implication: Automated and real-hardware verification are complete; the debug session can be resolved and archived.

## Eliminated

- hypothesis: The React graph executor or dashboard render pins the knee angle to zero despite valid paired frames.
  evidence: runMockExecutor maps inclination monotonically into the joint display, React renders `kneeAngle` directly, and the new paired-frame regression shows moving the slave changes the emitted angle proxy. The first actual divergence was upstream frame rejection for missing sensor_config.
  timestamp: "2026-07-27T11:29:00-07:00"

## Resolution

- root_cause: The wireless launcher used a stale WSL ROS bridge build that emitted `oe_esp32.raw.v1` messages without the required `sensor_config`. The current GUI rejects those messages before caching/emitting frames, while independent pair-health messages still report both ESPs connected.
- fix: Added handshake-order regression coverage and rebuilt the launcher’s `/home/justi/.rehab-install-v12` package from the current bridge implementation, which confirms/falls back sensor ranges before START and includes canonical `sensor_config` in every raw message.
- verification: Deployed-module introspection confirms CFG-before-START and sensor_config emission. All 27 backend tests, all 18 frontend tests, and the production build pass. A new paired-frame test confirms moving the slave changes the emitted relative-angle proxy. The user confirmed the original issue is fixed in the physical two-ESP workflow after restart.
- files_changed:
    - backend/test/test_esp32_controls.py
    - rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts
