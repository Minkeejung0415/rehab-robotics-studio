# GUI End-to-End Acceptance Checklist

**Primary entry point:** `./scripts/start_stepesp_wireless.ps1`

An item is complete only when its automated contract passes and, where hardware is involved, it is exercised through the running GUI with retained evidence.

## 1. One-command startup and recovery

- [x] GUI source tree type-checks and produces a fresh production build.
- [ ] Launcher selects and holds `iPhone (111)` without falling back to STEP_ESP32 or campus Wi-Fi.
- [ ] COM3 master and COM4 slave are responsive and both rejoin the hotspot.
- [ ] Full-MAC identity inventory completes without replacing the firmware's active control client.
- [ ] Relay, ROS fleet bridge, rosbridge, model catalog, mapping node, OpenSim node, and GUI each start once.
- [ ] Launcher fails with a precise stage/error instead of serving stale GUI assets.
- [ ] Stop/restart leaves no duplicate owners, stale locks, or orphaned control clients.

## 2. Application shell and runtime safety

- [ ] Block Diagram, Front Panel, and Sensor Mapping tabs render and remain navigable.
- [ ] Run, Pause, Resume, and Stop follow the allowed runtime state transitions.
- [ ] E-STOP stops runtime activity, latches visibly, and requires Reset before Run.
- [ ] Runtime/status strip truthfully reports ROS, hardware, recording, and fault state.
- [ ] Errors remain visible in the system log and controls recover for retry.

## 3. Graph editor and project workflow

- [ ] Palette search, add, drag/drop, select, multi-select, move, wire, delete, context menu, and zoom work.
- [ ] Properties edit the selected block and live-safe controls receive confirmed hardware acknowledgements.
- [ ] Validate Graph reports missing inputs, type mismatches, and unsafe paths.
- [ ] Save downloads a complete graph document; Load restores graph identity, nodes, edges, positions, and parameters.
- [ ] Deploy never falsely reports success; parked deployment scope is labelled explicitly.

## 4. Acquisition and health

- [ ] Both ESPs appear automatically with canonical full MAC, role, connection, rate, drops, and reconnect epoch.
- [ ] Master and slave sustain fresh data near the requested rate without silent substitution or stale cached pairing.
- [ ] Requested frequency and effective measured rate remain distinct and accurate.
- [ ] Reconnect produces a new epoch and visible gap without joining unrelated samples.
- [ ] Malformed/stale/missing inputs are rejected or marked unavailable; zeros are never fabricated.

## 5. Individual signal values and graphs

- [ ] Each ESP shows live values for ax, ay, az, gx, gy, gz, mx, my, and mz.
- [ ] Each available component has its own live scrolling graph; qw, qx, qy, qz appear only when declared valid.
- [ ] Source selector uses full MAC plus authoritative applied body part.
- [ ] One-ESP stacked view, multi-ESP selection, and same-channel comparison share a synchronized time axis.
- [ ] Group/channel visibility, raw/SI units, time window, local pause, vertical scale/zoom, and autoscale work.
- [ ] Display pause/settings never alter acquisition, health, recording, mapping, or OpenSim input.
- [ ] Browser buffers stay bounded and display projection preserves extrema at responsive frame rate.

## 6. Recording, export, and persistence

- [ ] Rec starts/stops hardware SD recording independently of Run/Stop and reflects an already-active session.
- [ ] Recording errors and session metadata are visible and retryable.
- [ ] Export retains full-rate samples independently of viewer pause, visibility, and downsampling.
- [ ] Export columns retain time/sequence, full MAC, role, channel, raw/SI value and unit, mapping revision, segment/frame, reconnect and mapping epochs.
- [ ] Automated reconciliation matches displayed identity/value/time to the corresponding export.

## 7. Model catalog and full-body sensor mapping

- [ ] Bundled compatible `.osim` loads automatically and removes the `NO MODEL` state.
- [ ] Catalog exposes model-derived frames for head, torso, pelvis, bilateral arms/hands, thighs/shanks, and feet.
- [ ] Every known ESP row supports Identify, segment/frame selection, Not Used, per-row Save, and global Apply Mapping.
- [ ] Draft and Saved assignments never relabel live data; only Applied revision changes authoritative labels.
- [ ] Duplicate segment assignment, stale revision, recording/calibration interlocks, Reset confirmation, and reconnect restoration behave correctly.
- [ ] Applying a swap updates viewer identity, backend routing, and subsequent export provenance by full MAC.

## 8. Calibration, IK, and 3D visualization

- [ ] Calibrate captures a provenance-bound artifact for the exact model hash, applied revision, full-MAC/frame order, and offsets.
- [ ] Clear cal invalidates the artifact and suppresses solved output until recalibration.
- [ ] Official OpenSim IK publishes only when the required synchronized inputs are complete, fresh, and within skew limits.
- [ ] Angle values and graphs change with physical motion and fail closed when calibration/IK/identity gates close.
- [ ] Open visualizer launches once, reports Opening/Open/failure truthfully, and remains retryable.
- [ ] Moving one ESP changes the mapped native OpenSim segment rather than producing constant or unrelated motion.
- [ ] Swap two mappings, Apply, recalibrate, and verify the responding 3D segments swap with the full-MAC devices.
- [ ] Full supported body configuration drives head, trunk, bilateral arms, and bilateral legs simultaneously.

## 9. Quality gates and retained evidence

- [ ] All frontend unit/component tests pass through one documented command.
- [ ] All backend and launcher/relay tests pass.
- [ ] Production build, PowerShell parser, Python compile, and firmware compile/flash checks pass.
- [ ] Browser console has no uncaught errors; all controls are keyboard reachable and critical states have accessible text.
- [ ] Long-run memory, display FPS, backlog, freshness, rate, drops, reconnect, and synchronization diagnostics stay within measured limits.
- [ ] Final physical run retains logs, mapping/calibration snapshots, recording/export files, and 3D remap evidence.

