# Phase 19 Research: Studio Controls + Live Angle Display

## Scope

Phase 19 closes the operator-facing loop without changing the ESP transport or sample
frequency. Studio must ask the existing ROS/OpenSim process to open its native
visualizer, and it must display only a calibrated, valid, fresh OpenSim IK knee angle.

The approved contracts in `19-CONTEXT.md` and `19-UI-SPEC.md` are binding:

- toolbar action: `Open visualizer`, positioned after `Clear cal`
- source of truth: `/opensim/joint_states`, coordinate `knee_angle_r`
- convert radians to degrees at the GUI boundary
- show a numeric angle only while calibration is `CALIBRATED`, IK is valid, and the
  selected JointState sample is no more than 2 seconds old
- missing, invalid, or stale data displays `Waiting for calibrated IK` and `—`
- visualizer failures remain visible in HealthPanel and may be retried
- log only state transitions, not every sample

## Current Architecture and Gaps

### Backend visualizer ownership

`opensim_bridge/opensim_node.py` already owns the OpenSim model and an
`OpenSimVisualizerAdapter`. This is the correct process boundary for native Simbody
visualization, especially under WSLg. The browser must not launch WSL commands or own
the visualizer lifecycle.

The adapter is currently created eagerly and reports availability/reason through the
existing OpenSim status path. There is no ROS Trigger service dedicated to opening or
showing the visualizer. Add an idempotent service at the OpenSim node boundary. Its
response must carry `success` and a human-readable `message`; repeated calls must
either bring the existing window forward/show it again or return a stable, actionable
failure without taking down IK.

Keep visualization optional. Missing Simbody visualizer support must not stop the
node, calibration, IK publication, or recording.

### Rosbridge data model

`RosbridgeDataSource.ts` already contains subscription and service-call plumbing and
subscribes to `/opensim/status`. Its current status parser assumes a `msg.data`
payload, so it cannot be reused blindly for `sensor_msgs/JointState`.

Add explicit, independently tracked contracts for:

- `/opensim/status`: node/calibration/visualization state
- `/opensim/ik_status`: whether the latest IK solution is valid and its reason
- `/opensim/joint_states`: coordinate names, positions, and source timestamp

The JointState parser must:

1. require `name` and `position` arrays,
2. find `knee_angle_r` by name rather than by a fixed index,
3. require a finite matching position,
4. convert radians to degrees exactly once at the data-source boundary,
5. record local receipt time for deterministic stale evaluation, while retaining the
   ROS header stamp only as diagnostic metadata.

Subscriptions and service calls should use the existing reconnect/session generation
guards so messages or replies from a superseded WebSocket cannot mutate current UI
state.

### GUI angle path

The existing product graph deliberately does not consume `frame.jointAngleDeg`, and
`signalBus.ts` currently converts a missing knee output to `0` and can feed a
zero-filled chart. `MotorPanel.tsx` and `BlockNode.tsx` then assume a number and call
`toFixed(1)`.

That behavior is unsafe for Phase 19 because “no trustworthy angle” is not a zero
degree measurement. The runtime/UI contract needs an explicit unavailable state
(`number | null`, or a discriminated snapshot) that carries availability and reason.
The UI components must render `—` and `Waiting for calibrated IK` without retaining
the last valid value.

Do not reintroduce the Phase 16 placeholder `frame.jointAngleDeg` as the production
source. The only live source is the parsed OpenSim JointState snapshot.

### Freshness and transitions

Freshness must be recomputed as wall-clock time advances, not only when a ROS message
arrives. A one-shot timeout keyed to the latest accepted sample or a low-frequency
health tick is sufficient. At 2 seconds, clear the display and transition to stale.

State transition logging should deduplicate:

- waiting -> valid
- valid -> invalid
- valid -> stale
- unavailable -> valid
- visualizer opening -> opened
- visualizer opening -> failed

High-rate JointState samples must never produce per-sample log entries or React
notifications.

## Recommended Implementation Shape

1. Extend the backend adapter/node with a small idempotent visualizer-open operation
   and expose it as a `std_srvs/Trigger` service.
2. Add typed OpenSim IK and JointState snapshots to the frontend health/data-source
   contract. Keep the three ROS topics independent.
3. Add a rosbridge Trigger method for the visualizer action, with a busy lock and
   stale-session reply protection.
4. Derive one fail-closed `liveKneeAngle` view model from calibration, IK validity,
   coordinate presence, finiteness, and 2-second freshness.
5. Feed that view model to both numeric readout locations and prevent missing values
   from entering history as zero.
6. Add the toolbar action, persistent HealthPanel reason/retry surface, toast, and
   transition-only log messages specified by the UI contract.
7. Document the wireless operator flow and the boundary between automated tests and
   the native WSLg window smoke test.

## Testing Strategy

### Frontend deterministic tests

Reuse the existing node:test/fake-WebSocket patterns.

- verify the three subscriptions are issued after connect and reissued once after
  reconnect
- parse `knee_angle_r` by name when coordinate order varies
- verify radians-to-degrees conversion
- reject missing coordinate, mismatched arrays, non-finite positions, invalid IK, and
  uncalibrated state
- use a fake clock to verify a valid value becomes `—` after 2 seconds without a new
  sample
- ensure a stale/invalid sample clears the displayed value rather than retaining the
  previous one or producing zero
- exercise visualizer Trigger success, explicit failure, timeout/disconnect, retry,
  and late reply from an old session
- verify transition deduplication and absence of per-sample log spam
- render/assert Toolbar, HealthPanel, MotorPanel, and block-node unavailable copy

### Backend tests

Reuse the fake-rclpy/fake-OpenSim seams.

- service exists and delegates to the node-owned adapter
- success and failure map to Trigger response fields
- repeated calls are safe
- visualization failure does not stop calibration/IK publishers
- adapter exceptions are converted to a stable failure reason

### Production-preview flow

In the production build/preview with fake rosbridge:

1. connect,
2. click `Open visualizer`,
3. calibrate,
4. publish invalid/waiting state and confirm `—`,
5. publish calibrated valid JointState and confirm the degree value,
6. stop samples and confirm the value clears after 2 seconds,
7. confirm visualizer failure remains actionable in HealthPanel.

## Validation Architecture

### Fast feedback commands

- frontend targeted unit/integration tests for the rosbridge source, signal/view
  model, toolbar, health panel, and angle readouts
- backend targeted Python tests for the OpenSim node and visualizer adapter
- TypeScript typecheck and production build

### Plan-level verification

Each implementation plan should end with its own narrow tests. The final plan should
run the full frontend suite, backend suite, typecheck/build, and a production-preview
fake-rosbridge scenario.

### Human-needed boundary

The current WSL environment has ROS Humble, OpenSim 4.5.2, and WSLg, but the
`simbody-visualizer` executable/runtime component is not presently available.
Automated tests can prove the Trigger and failure path; they cannot prove that a real
native window appears. Record the real WSL/native visualizer smoke as
`human_needed` unless the runtime dependency becomes available:

1. start the OpenSim node inside WSL,
2. connect Studio wirelessly,
3. click `Open visualizer`,
4. confirm the Simbody window appears and continues updating during calibrated IK,
5. close/reopen or retry and confirm IK/recording remain alive.

## Planning Risks

- Treating a ROS header clock from another machine as the freshness clock can produce
  false stale/fresh decisions; use local receipt monotonic time for the UI deadline.
- A generic `msg.data` parser will silently discard JointState fields.
- Keeping the previous numeric value violates the fail-closed requirement.
- Eager visualizer construction can make optional visualization affect core IK; keep
  failures isolated and report them.
- React updates at JointState frequency can create the appearance of a transport cap;
  parse every required message but publish a compact snapshot and avoid per-sample
  logs/toasts.

## Conclusion

Phase 19 is primarily a contract-and-state-boundary change, not a wireless frequency
change. The backend owns the native visualizer; rosbridge exposes typed independent
status and JointState channels; the GUI shows a number only when all validity gates
are true. This shape directly satisfies VIS-01/VIS-02 while preserving the calibrated
IK path established by IK-06.
