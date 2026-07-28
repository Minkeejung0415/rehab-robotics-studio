---
phase: 19-studio-controls-live-angle
reviewed: 2026-07-28T21:34:25Z
depth: standard
files_reviewed: 30
files_reviewed_list:
  - backend/rehab_robotics_bridge/opensim/ik_contracts.py
  - backend/rehab_robotics_bridge/opensim_adapter.py
  - backend/rehab_robotics_bridge/opensim_node.py
  - backend/test/test_opensim_adapter.py
  - backend/test/test_opensim_node.py
  - rehab-robotics-studio/src/types/health.ts
  - rehab-robotics-studio/src/types/signals.ts
  - rehab-robotics-studio/src/data/liveKneeAngle.ts
  - rehab-robotics-studio/src/data/liveKneeAngle.test.ts
  - rehab-robotics-studio/src/data/DataSource.ts
  - rehab-robotics-studio/src/data/RosbridgeDataSource.ts
  - rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts
  - rehab-robotics-studio/src/data/appDataSource.ts
  - rehab-robotics-studio/src/data/signalBus.ts
  - rehab-robotics-studio/src/state/systemStore.ts
  - rehab-robotics-studio/src/state/graphStore.ts
  - rehab-robotics-studio/src/graph/blockDefinitions.ts
  - rehab-robotics-studio/src/graph/mockExecutor.ts
  - rehab-robotics-studio/src/graph/productKneeReadout.test.ts
  - rehab-robotics-studio/src/components/chrome/Toolbar.tsx
  - rehab-robotics-studio/src/components/chrome/Toolbar.test.ts
  - rehab-robotics-studio/src/components/common/Toast.tsx
  - rehab-robotics-studio/src/components/dashboard/HealthPanel.tsx
  - rehab-robotics-studio/src/components/dashboard/HealthPanel.test.ts
  - rehab-robotics-studio/src/components/dashboard/calibrationStatus.ts
  - rehab-robotics-studio/src/components/dashboard/MotorPanel.tsx
  - rehab-robotics-studio/src/components/canvas/BlockNode.tsx
  - rehab-robotics-studio/src/styles/app.css
  - rehab-robotics-studio/scripts/phase19-qa.mjs
  - rehab-robotics-studio/package.json
findings:
  critical: 4
  warning: 1
  info: 0
  total: 5
status: issues_found
---

# Phase 19: Code Review Report

**Reviewed:** 2026-07-28T21:34:25Z
**Depth:** standard
**Files Reviewed:** 30
**Status:** issues_found

## Summary

The fail-closed angle derivation, stamp ordering, radian conversion, malformed OpenSim payload rejection, and obsolete-socket guards are generally coherent. However, four lifecycle defects break the promised bounded/recoverable operator workflow: a native visualizer call can block the ROS executor indefinitely, pausing acquisition discards service replies, explicit stop suppresses the disconnect transition, and the mock fallback permanently disables reconnect. The current targeted suites all pass because none exercises those paths. One additional cleanup defect leaves disposed SignalBus animation loops alive.

Verification performed:

- Frontend targeted tests: 57 passed, 0 failed.
- Frontend TypeScript typecheck: passed.
- Backend targeted tests: 62 run, 59 passed, 3 expected native-runtime skips.
- Dirty-worktree preservation evidence was inspected; no source file was modified during review.

## Critical Issues

### CR-01: Visualizer Trigger is not bounded and can freeze all OpenSim callbacks

**Classification:** BLOCKER
**File:** `backend/rehab_robotics_bridge/opensim_node.py:394-433`
**Related:** `backend/rehab_robotics_bridge/opensim_adapter.py:382-396`
**Issue:** `_on_visualizer_open` calls `adapter.open_visualizer()` synchronously inside the ROS service callback, and the adapter immediately calls the optional native `show()` API. Exception handling only covers calls that return by throwing; there is no deadline, worker isolation, or cancellation path. If Simbody/OpenSim hangs while opening a window, the ROS executor remains inside the Trigger callback, so calibration services, IK publication, diagnostics, and status timers can all stop. The browser's 10-second timeout does not release the blocked backend callback. This contradicts the phase's bounded-operation and native-failure-isolation contracts.
**Fix:** Execute the native show/raise operation outside the ROS executor callback and impose a backend deadline. The Trigger callback should return a stable failure when the deadline elapses while a worker-owned state machine reports `opening`/`failed`; it must also reject or coalesce another request while the same native operation is pending. Add a fake adapter whose `open_visualizer()` never returns and assert that the callback/timers remain responsive.

### CR-02: Explicit stop suppresses the disconnect callback and leaves stale connected/live UI state

**Classification:** BLOCKER
**File:** `rehab-robotics-studio/src/data/RosbridgeDataSource.ts:438-453`
**Related:** `rehab-robotics-studio/src/data/RosbridgeDataSource.ts:423-435`, `rehab-robotics-studio/src/data/appDataSource.ts:28-34`
**Issue:** `stop()` sets `this.socket = null` before calling `socket.close()`. The captured `onclose` handler then fails `isCurrentSession(generation, socket)` and returns before `onConnectionChange(false)`. Consequently, a normal Stop/E-STOP/fault teardown leaves Zustand reporting ROS as connected and bypasses the app callback that clears `/opensim/joint_states` and the displayable knee angle. The session-safety test only checks that the later reconnect ends in `true`; it never asserts the required intermediate `false`, so this regression passes.
**Fix:** Perform current-session teardown explicitly in `stop()` before invalidating the socket (set connected false, invoke `onConnectionChange(false)` once, reject pending calls, then detach/close), or introduce a single idempotent `closeSession()` helper used by both `stop()` and `onclose`. Add assertions that `stop()` emits exactly one `false` transition and immediately clears the stored JointState/live angle before a new generation starts.

### CR-03: Pausing acquisition discards visualizer/calibration service responses

**Classification:** BLOCKER
**File:** `rehab-robotics-studio/src/data/RosbridgeDataSource.ts:660-669`
**Related:** `rehab-robotics-studio/src/components/chrome/Toolbar.tsx:106-132`, `rehab-robotics-studio/src/components/chrome/Toolbar.tsx:185-194`
**Issue:** `handleMessage()` returns immediately whenever `this.paused` is true, before it routes `service_response` envelopes or OpenSim status topics. Toolbar calibration and visualizer actions remain enabled in the paused runtime state, so a legitimate backend reply received while paused is silently discarded. The UI waits the full 10 seconds, reports a false timeout/failure, and may invite a duplicate retry even though the backend already completed the action. This violates the DataSource contract that pause halts frame emission without tearing down control/observability.
**Fix:** Validate and route service responses plus health/OpenSim control-plane topics before applying the paused check. Restrict `paused` to raw acquisition frame caching/emission only. Add a test that pauses the source, sends a visualizer and calibration response, and proves both promises settle once while raw ESP frames remain suppressed.

### CR-04: Startup fallback permanently traps the application in mock mode

**Classification:** BLOCKER
**File:** `rehab-robotics-studio/src/data/appDataSource.ts:21-27`
**Related:** `rehab-robotics-studio/src/data/appDataSource.ts:164-171`, `rehab-robotics-studio/src/data/RosbridgeDataSource.ts:419-435`
**Issue:** On an initial WebSocket error/close, `onUnavailable` replaces `active` with `mockDataSource` and starts it, but no code ever assigns `active` back to `rosbridgeDataSource`. `reconnectHardware()` explicitly refuses to reconnect when `active !== rosbridgeDataSource`, so the HealthPanel's Reconnect ROS action cannot recover the live OpenSim workflow after the fallback. When `onerror` fires before `onclose`, the fallback also starts without stopping the still-owned RosbridgeDataSource, allowing its socket callbacks to continue mutating connection/OpenSim state behind the active mock source.
**Fix:** Model source mode and connection state separately. The reconnect action should stop any mock fallback, restore `active = rosbridgeDataSource`, and start a new guarded generation; the fallback transition should explicitly stop/close the failed ROS session first. Add an end-to-end unit test for error -> mock fallback -> Reconnect ROS -> current ROS subscriptions/live angle, including rejection of the old socket's late callbacks.

## Warnings

### WR-01: SignalBus.dispose() leaves its animation loop running forever

**Classification:** WARNING
**File:** `rehab-robotics-studio/src/data/signalBus.ts:97-99`
**Related:** `rehab-robotics-studio/src/data/signalBus.ts:132-144`, `rehab-robotics-studio/src/data/signalBus.ts:223-229`
**Issue:** The constructor starts a self-rescheduling `requestAnimationFrame` loop, but `dispose()` only unsubscribes from frames and Zustand. It neither stores/cancels the frame handle nor marks the bus disposed, so the callback retains the instance and continues scheduling forever after disposal. Tests and hot-module replacement can accumulate orphan loops; the public cleanup method does not fulfill its lifecycle contract.
**Fix:** Store the scheduled frame handle, inject/use `cancelAnimationFrame`, add a disposed flag checked before rescheduling, clear listeners on disposal, and test that invoking a captured callback after `dispose()` cannot schedule another frame or notify subscribers.

---

_Reviewed: 2026-07-28T21:34:25Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
