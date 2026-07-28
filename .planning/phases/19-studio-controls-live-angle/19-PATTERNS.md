# Phase 19: Studio Controls + Live Angle Display - Pattern Map

**Mapped:** 2026-07-28  
**Files analyzed:** 24 anticipated new/modified files  
**Analogs found:** 23 / 24

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `backend/rehab_robotics_bridge/opensim/ik_contracts.py` | config | request-response | same file, calibration constants at lines 20-29 | exact |
| `backend/rehab_robotics_bridge/opensim_adapter.py` | service | request-response + native I/O | same file, `update_sensor()`/`status()` at lines 106-148, 374-416 | exact |
| `backend/rehab_robotics_bridge/opensim_node.py` | controller | event-driven + request-response | same file, calibration Trigger services at lines 265-274, 353-385 | exact |
| `backend/test/test_opensim_adapter.py` | test | native-I/O simulation | same file, failure/recovery tests at lines 572-650 | exact |
| `backend/test/test_opensim_node.py` | test | event-driven + request-response | same file, fake-rclpy/service harness at lines 17-90, 135-192 | exact |
| `rehab-robotics-studio/src/types/health.ts` | model | transform | same file, typed optional snapshots at lines 33-67 | exact |
| `rehab-robotics-studio/src/types/signals.ts` | model | streaming | same file, `Frame` boundary at lines 70-86 | role-match |
| `rehab-robotics-studio/src/data/DataSource.ts` | provider | streaming + event-driven | same file, subscription contract at lines 10-26 | exact |
| `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` | provider | streaming + request-response | same file, topic/service routing at lines 173-278, 389-495 | exact |
| `rehab-robotics-studio/src/data/appDataSource.ts` | provider | request-response | same file, narrow calibration actions at lines 57-79 | exact |
| `rehab-robotics-studio/src/data/liveKneeAngle.ts` (new) | utility | transform + event-driven | `components/dashboard/calibrationStatus.ts` plus backend `opensim_node.py` state-signature pattern | role-match |
| `rehab-robotics-studio/src/data/liveKneeAngle.test.ts` (new) | test | transform + timer | `graph/productKneeReadout.test.ts`; clock seam from `backend/test/test_opensim_node.py` | composite |
| `rehab-robotics-studio/src/data/RosbridgeDataSource.test.ts` | test | streaming + request-response | same file, fake WebSocket at lines 402-485 | exact |
| `rehab-robotics-studio/src/state/systemStore.ts` | store | event-driven | same file, typed snapshots/setters at lines 22-55, 94-95 | exact |
| `rehab-robotics-studio/src/components/chrome/Toolbar.tsx` | component | request-response | same file, calibration busy/toast/log flow at lines 36-45, 81-104 | exact |
| `rehab-robotics-studio/src/components/dashboard/HealthPanel.tsx` | component | event-driven | same file, persistent OpenSim key/value rows at lines 46-107 | exact |
| `rehab-robotics-studio/src/components/dashboard/HealthPanel.test.ts` | test | transform | same file, pure formatter assertions | exact |
| `rehab-robotics-studio/src/data/signalBus.ts` | provider | streaming + transform | same file, throttled snapshot/ring buffers at lines 6-21, 63-139 | exact |
| `rehab-robotics-studio/src/components/dashboard/MotorPanel.tsx` | component | streaming | same file, knee readout/chart at lines 5-24 | exact |
| `rehab-robotics-studio/src/components/canvas/BlockNode.tsx` | component | streaming | same file, angle body at lines 27-47 | exact |
| `rehab-robotics-studio/src/components/common/MiniChart.tsx` | component | transform | same file, clear-then-empty return at lines 19-28 | exact |
| `rehab-robotics-studio/src/styles/app.css` | config | presentation | same file, toolbar/readout/kv/toast styles at lines 33-110, 565-631, 920-937 | exact |
| `rehab-robotics-studio/src/graph/productKneeReadout.test.ts` | test | transform | same file, fail-closed product assertions at lines 51-106 | exact |
| `rehab-robotics-studio/scripts/phase19-qa.mjs` (new) | test | request-response + streaming | `scripts/phase8-qa.mjs` and `scripts/frequency-panel-regression.mjs` | role-match |
| `docs/stepesp-wireless-setup.md` | runbook | operator procedure | same file, numbered start/verify/stop flow at lines 13-73 | exact |

## Pattern Assignments

### Backend visualizer Trigger

**Apply to:** `ik_contracts.py`, `opensim_adapter.py`, `opensim_node.py`, and their tests.

Use the existing contract-constant location:

```python
# backend/rehab_robotics_bridge/opensim/ik_contracts.py:20-28
CALIBRATION_CAPTURE_SERVICE = "/opensim/calibration/capture"
CALIBRATION_CLEAR_SERVICE = "/opensim/calibration/clear"

IK_STATUS_TOPIC = "/opensim/ik_status"
```

Add `VISUALIZER_OPEN_SERVICE = "/opensim/visualizer/open"` beside these constants. Copy the node-owned Trigger construction and response mapping:

```python
# backend/rehab_robotics_bridge/opensim_node.py:265-274, 353-367
self._capture_service = self.create_service(
    Trigger,
    CALIBRATION_CAPTURE_SERVICE,
    self._on_calibration_capture,
)

def _on_calibration_capture(self, _request, response):
    ready, reason = self._sensors_ready_for_capture()
    if not ready:
        response.success = False
        response.message = reason
        return response
    ok, message = self._calibration.begin_capture()
    response.success = ok
    response.message = message
    return response
```

The adapter remains the native-window owner. Extend `VisualizerAdapter` and both implementations with an idempotent `open_visualizer() -> tuple[bool, str]`; do not put OpenSim/process code in the ROS callback. Preserve stable, JSON-safe status:

```python
# backend/rehab_robotics_bridge/opensim_adapter.py:121-148
class UnavailableVisualizerAdapter:
    def status(self) -> dict[str, object]:
        return {
            "available": False,
            "state": "unavailable",
            "reason": self._reason,
        }
```

Isolate native exceptions exactly as `update_sensor()` does; convert them to a failure result/status instead of letting visualization stop IK:

```python
# backend/rehab_robotics_bridge/opensim_adapter.py:388-408
try:
    ...
    self._model.updVisualizer().show(self._state)
except Exception:
    self._available = False
    self._state_name = "unavailable"
    self._reason = "visualizer_update_failed"
    return False
self._available = True
self._state_name = "ready"
self._reason = ""
return True
```

### Fake-rclpy and adapter tests

Copy the in-process ROS seam, not a live ROS/OpenSim dependency:

```python
# backend/test/test_opensim_node.py:75-87, 135-147
def create_service(self, srv_type, name, callback):
    service = types.SimpleNamespace(
        srv_type=srv_type, name=name, callback=callback,
    )
    self.services.append(service)
    return service

class _TriggerResponse:
    def __init__(self):
        self.success = False
        self.message = ""
```

Test service existence/type, callback response fields, repeat calls, thrown adapter exceptions, and that IK publishers remain operational. For adapter state persistence/recovery, copy:

```python
# backend/test/test_opensim_adapter.py:618-648
self.assertFalse(adapter.update_sensor(...))
self.assertEqual(adapter.status()["reason"], "visualizer_update_failed")
self.assertTrue(adapter.update_sensor(...))
self.assertEqual(adapter.status(), {
    "available": True,
    "state": "ready",
    "reason": "",
    "mode": "retained_decorations",
})
```

### Rosbridge typed topics, Trigger calls, and session guards

**Apply to:** `DataSource.ts`, `RosbridgeDataSource.ts`, `appDataSource.ts`, `types/health.ts`, `systemStore.ts`.

Keep `/opensim/status`, `/opensim/ik_status`, and `/opensim/joint_states` as separate callbacks/snapshots. Follow the optional-field wire model in `types/health.ts:33-67`, but introduce explicit `OpenSimIkStatusSnapshot`, `OpenSimJointStateSnapshot`, and a discriminated/nullable `LiveKneeAngleSnapshot`. Do not parse JointState through `msg.data`; widen the envelope by message type:

```typescript
// rehab-robotics-studio/src/data/RosbridgeDataSource.ts:19-29
type RosbridgeEnvelope = {
  op?: string;
  topic?: string;
  msg?: { data?: string };
  id?: string;
  values?: {
    success?: boolean;
    message?: string;
  };
};
```

Use topic-specific subscriptions and parsers. The current shared String subscription loop is the structural analog, but JointState must use `sensor_msgs/msg/JointState`:

```typescript
// RosbridgeDataSource.ts:215-225
this.socket.onopen = () => {
  this.connected = true;
  ...
  this.socket?.send(JSON.stringify({
    op: 'subscribe', topic, type: 'std_msgs/msg/String',
  }));
};
```

Copy the Trigger method shape from calibration:

```typescript
// RosbridgeDataSource.ts:262-278
captureCalibration(): Promise<RecordingCommandResult> {
  return this.callService(
    '/opensim/calibration/capture',
    {},
    'std_srvs/srv/Trigger',
  );
}
```

Copy timeout cleanup and response routing from `callService()`/`handleMessage()` (`RosbridgeDataSource.ts:389-429`). Change visualizer timeout copy to the locked 10-second message.

The present socket callbacks are not protected against a superseded socket. Add a monotonically increasing connection generation, following:

```typescript
// rehab-robotics-studio/src/deployment/coordinator.ts:9-18
let generation = 0;
const run = ++generation;
...
if (run !== generation) return;
```

Capture the generation (or socket identity) in every `onopen`, `onmessage`, `onerror`, `onclose`, timeout, and pending service entry. Old callbacks/replies must neither resolve current calls nor set `this.socket = null`.

At the GUI boundary, accept only equal-length `name`/`position` arrays, locate `knee_angle_r` by name, require a finite value, preserve a usable nondecreasing ROS stamp, and convert once with `radians * 180 / Math.PI`. Store local monotonic receipt time separately.

`appDataSource.ts:65-79` is the narrow application-action analog. Add `openOpenSimVisualizer()` with the same live-source guard and `RecordingCommandResult`; keep components unaware of `RosbridgeDataSource`.

### Live-angle gate, staleness, and transition logging

**Apply to:** new `liveKneeAngle.ts`, its tests, `systemStore.ts`, and `signalBus.ts`.

Use a pure derivation helper like `calibrationStatus.ts:7-15`, but return a state such as:

```typescript
type LiveKneeAngleSnapshot =
  | { state: 'live'; valueDeg: number; reason: ''; sourceStampNs: number; receivedAtMs: number }
  | { state: 'waiting' | 'invalid' | 'stale'; valueDeg: null; reason: string };
```

Inject `nowMs`/a clock into freshness evaluation. The closest deterministic clock seam is:

```python
# backend/test/test_opensim_node.py:234-239
class _Clock:
    def __init__(self, now=10.0):
        self.now = now
    def __call__(self):
        return self.now
```

Frontend tests should mutate a numeric fake clock, evaluate at `receivedAt + 1_999`, then at `+2_001`, and invoke the scheduled callback directly. The existing browser timer polyfill is at `RosbridgeDataSource.test.ts:14-33`.

For transition-only logs, copy signature deduplication:

```python
# backend/rehab_robotics_bridge/opensim_node.py:499-518, 543-554
if (sensor.state, sensor.last_error) == (state, error):
    return
...
if visualization_signature != self._last_visualization_signature:
    ...
    self._last_visualization_signature = visualization_signature
```

Track the last `{state, reason}` signature and log only changes into/out of `LIVE`, `STALE`, and `INVALID`. Never call `addLog` from each JointState callback.

Do not copy the existing fake-zero behavior:

```typescript
// signalBus.ts:103-110 — replace these lines for the product knee path
const kneeAngle = out.knee ?? 0;
this.kneeBuf.push(kneeAngle);
```

Make `kneeAngle` nullable and clear the knee buffer when any gate closes. Valid recovery begins a new series. Preserve the throttled React publication pattern at `signalBus.ts:63-70, 126-139`.

### Toolbar and persistent HealthPanel state

**Apply to:** `Toolbar.tsx`, `HealthPanel.tsx`, `HealthPanel.test.ts`, `Toast.tsx`, `app.css`.

Copy the calibration busy lock and result handling:

```typescript
// Toolbar.tsx:81-93
if (calBusy) return;
setCalibrateBusy(true);
const result = await captureOpenSimCalibration();
setCalibrateBusy(false);
useSystemStore.getState().addLog(result.success ? 'INFO' : 'ERROR', result.message);
if (!result.success) {
  setToastMessage(result.message);
  setToastKey((key) => key + 1);
}
```

Use a separate `visualizerBusy`, render `Opening…`, set `disabled` and `aria-busy` only while pending, and place the button between `Clear cal` (`Toolbar.tsx:149-156`) and `Save` (`157-159`). No success toast.

Toast state is transient (`Toast.tsx:9-14`); therefore visualizer failure must also be written to the Zustand OpenSim/visualizer snapshot. A later backend `opening`/`open` status may replace it; toast dismissal must not.

Extend the existing compact OpenSim rows:

```tsx
// HealthPanel.tsx:88-107
<div className="kv-grid">
  <span>Calibration state</span>
  <strong>{calibration.state}</strong>
  <span>Calibration reason</span>
  <strong>{calibration.reason || '—'}</strong>
  <span>3D visualizer</span>
  <strong>{...}</strong>
</div>
```

Keep long reasons in the existing `overflow-wrap: anywhere` value column (`app.css:611-631`). Reuse `.btn`, `.node-readout`, `.kv-grid`, and `.toast`; add state classes without a component library.

### Nullable readouts and chart

**Apply to:** `MotorPanel.tsx`, `BlockNode.tsx`, `MiniChart.tsx`, `signalBus.ts`, `productKneeReadout.test.ts`.

Replace unconditional `toFixed()` calls at `MotorPanel.tsx:16-24` and `BlockNode.tsx:35-37` with a shared nullable formatter: live finite values render one decimal plus `deg`; every unavailable state renders `—` and `Waiting for calibrated IK`.

`MiniChart` already clears before checking for insufficient data:

```typescript
// MiniChart.tsx:19-28
const ctx = cv.getContext('2d');
...
ctx.clearRect(0, 0, W, H);
if (data.length < 2) return;
```

Pass `[]` when gated unavailable/stale so the old trace disappears. Never pass placeholder zeros. Extend the existing fail-closed assertions:

```typescript
// graph/productKneeReadout.test.ts:100-105
assert.ok(
  kneeResult.knee === undefined
    || kneeResult.knee === null
    || !Number.isFinite(kneeResult.knee),
  `opensim_ik_live must fail closed without sample`,
);
```

Add cases for true zero through all gates, calibration-id mismatch, non-finite/missing/out-of-order JointState, stale clearing, and recovery with an empty/new trace.

### Production preview and operator runbook

Create `scripts/phase19-qa.mjs` beside existing phase scripts. Copy Playwright role-based actions and `try/finally` cleanup from `scripts/phase8-qa.mjs:1-25`; copy bounded preview startup/polling and machine-readable result handling from `scripts/frequency-panel-regression.mjs:39-67, 83-163`. The Phase 19 script additionally needs a fake rosbridge WebSocket server; no existing preview script supplies that exact analog.

Update `docs/stepesp-wireless-setup.md` rather than creating a disconnected runbook. Its numbered operator sequence already covers stack start (`13-30`), status verification (`43-56`), shutdown (`58-73`), and preserves copy-paste commands. Add a one-page OpenSim subsection: start stack, request visualizer, calibrate, confirm valid live angle, inspect persistent failure/stale state, and clean shutdown. Link detailed runtime limitations from `docs/opensim-quaternion-live-link.md:52-57, 127-158`. Mark real native-window verification `human_needed` when `simbody-visualizer` is unavailable.

## Shared Patterns

### Fail Closed

- Backend publishes JointState only under calibration + validity + source-stamp gates (`opensim_node.py:452-473`).
- Frontend must independently gate calibration state, IK validity, matching non-empty calibration IDs, finite named coordinate, ordered source stamp, and receipt age.
- Missing data is `null`/discriminated unavailable state, never `0`.

### Persistent vs Ephemeral Failure

- Toast: temporary feedback only.
- Zustand health snapshot: authoritative persistent reason.
- Backend status `opening`/`open`: the only normal replacement for a retained visualizer failure.

### Reconnect Safety

- One generation per WebSocket session.
- Topic messages, service responses, close/error handlers, and timeouts validate that generation.
- Disconnect settles all calls from that generation; a late prior reply is ignored.

### Error Handling

- Backend adapter catches optional native visualization failures and returns stable reason codes.
- ROS Trigger always returns `success` plus human-readable `message`.
- Rosbridge malformed/unrelated envelopes remain isolated (`RosbridgeDataSource.ts:419-485`).
- UI emits one ERROR log and one failure toast per request settlement, while HealthPanel keeps the reason.

## No Exact Analog Found

| File/Concern | Reason | Planner Guidance |
|---|---|---|
| `src/data/liveKneeAngle.ts` frontend monotonic stale timer | No existing frontend helper combines a nullable product snapshot, injected monotonic clock, scheduled expiry, and transition signatures. | Compose `calibrationStatus.ts` pure-helper style, backend `_Clock` tests, and backend signature deduplication; do not hide timer logic in React components. |
| `scripts/phase19-qa.mjs` fake rosbridge preview | Existing preview scripts drive Playwright but do not host a fake rosbridge server. | Reuse preview lifecycle/Playwright conventions and the unit-test rosbridge envelope shapes. |

## Metadata

**Analog search scope:** `backend/rehab_robotics_bridge`, `backend/test`, `rehab-robotics-studio/src`, `rehab-robotics-studio/scripts`, `docs`  
**Primary analogs read:** OpenSim node/adapter and tests; rosbridge source/test; Toolbar; HealthPanel/store/types; signal bus/readouts/chart; preview scripts; wireless/OpenSim docs  
**Pattern extraction date:** 2026-07-28
