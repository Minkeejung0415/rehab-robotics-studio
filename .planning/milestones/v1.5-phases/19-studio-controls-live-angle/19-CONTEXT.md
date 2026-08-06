# Phase 19: Studio Controls + Live Angle Display - Context

**Gathered:** 2026-07-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Complete the top-level Studio operator workflow for the v1.5 OpenSim path: request the native OpenSim visualizer from the toolbar, display calibrated and valid OpenSim IK knee angles from `/opensim/joint_states`, keep unavailability and stale-data reasons visible, and document a runnable wireless end-to-end checklist. Do not add an embedded Studio 3D renderer, replace official OpenSim IK, or weaken the CALIBRATED publication gate.

</domain>

<decisions>
## Implementation Decisions

### Visualizer Control
- Place `Open visualizer` after `Clear cal` and before `Save` so OpenSim experiment controls remain grouped.
- Show `Opening…` while the request is in flight and prevent duplicate requests.
- Invoke a backend rosbridge `Trigger` service; the browser must not launch or manage a WSL/OpenSim process directly.
- Report failures through a toast and system log, and retain the failure reason in HealthPanel until a later successful state replaces it.

### Live Angle Display
- Consume only the `knee_angle_r` coordinate from `/opensim/joint_states` for the default product knee angle.
- Convert ROS radians to degrees at the GUI boundary.
- Update the displayed value only when calibration is `CALIBRATED` and the OpenSim IK solution is valid.
- When a valid fresh product angle is unavailable, show `Waiting for calibrated IK` and an em dash; never substitute a fake `0°` or retain a stale value.

### Status and Error Handling
- Track `/opensim/status`, `/opensim/ik_status`, and `/opensim/joint_states` as distinct observable contracts.
- Keep visualizer failure reasons visible in HealthPanel and allow the operator to retry.
- Mark the product angle stale and hide it when fresh JointState updates stop beyond a conservative timeout.
- Add INFO/ERROR logs on state transitions only, not per frame.

### Verification and Operations
- Add deterministic fake-rosbridge coverage for visualizer service success/failure, calibration and IK validity gates, JointState radian-to-degree mapping, and stale-angle behavior.
- Verify the Toolbar → Calibrate → live-angle UI flow against the production preview.
- Provide a one-page wireless operator checklist covering stack start, visualizer request, calibration, live angle confirmation, and clean shutdown.
- Keep automated verification independent of a local OpenSim installation; classify the real WSL native-window smoke as `human_needed` when the runtime is unavailable.

### the agent's Discretion
- Exact Trigger service name and status-schema field additions, provided they remain rosbridge-friendly and are covered by backend/frontend tests.
- Exact conservative stale timeout and visual styling, provided unavailable, invalid, and stale states are visibly distinct from a real zero-degree solution.
- Exact test and documentation file organization.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Toolbar.tsx` already implements busy state, toast, logging, and rosbridge service patterns for Calibrate and Clear cal.
- `HealthPanel.tsx`, `calibrationStatus.ts`, and `useSystemStore` already present persistent OpenSim status and failure reasons.
- `RosbridgeDataSource` already subscribes to `/opensim/status`, routes service responses, and owns the `Frame` boundary used by SignalBus.
- `OpenSimVisualizerAdapter` already owns the native model/Simbody visualizer and exposes availability, state, reason, and model path.
- Phase 18 publishes calibrated, valid `sensor_msgs/JointState` on `/opensim/joint_states` and rosbridge-friendly `/opensim/ik_status`.

### Established Patterns
- Top-level operator actions call narrow functions in `appDataSource.ts`, use `RecordingCommandResult`, and surface failures via toast plus system logs.
- Runtime status is stored in Zustand and rendered by compact dashboard key/value rows and status badges.
- The product path fails closed: custom relative-quaternion math and absent data must not appear as valid OpenSim IK.
- Frontend tests favor pure helpers and deterministic stub WebSocket envelopes; production preview scripts cover browser-level flows.

### Integration Points
- Add the visualizer Trigger service and persistent status transition to `opensim_node.py` and its adapter boundary.
- Extend `DataSource`, `RosbridgeDataSource`, and `appDataSource` with the visualizer action plus `/opensim/ik_status` and `/opensim/joint_states` subscriptions.
- Extend OpenSim health/types/store state to represent IK validity and fresh joint-coordinate data.
- Route valid `knee_angle_r` through `Frame.jointAngleDeg`, graph execution, SignalBus, MotorPanel, and the angle display block without a fake-zero fallback.
- Add Toolbar, HealthPanel, rosbridge contract, backend node/service, production-preview, and operator-checklist verification.

</code_context>

<specifics>
## Specific Ideas

Keep the operator workflow in the existing Studio chrome: Open visualizer, Calibrate in the fixed standing/knees-extended pose, then observe the live OpenSim knee angle. Unavailable runtime or invalid/stale IK must remain obvious rather than looking like a valid zero-degree result.

</specifics>

<deferred>
## Deferred Ideas

- Embedded Studio 3D rendering of the solved model.
- Cross-session calibration persistence and multi-pose calibration.
- Clinical/external-reference accuracy validation.
- Dedicated C++ OpenSense streaming package and typed IkStatus message.

</deferred>
