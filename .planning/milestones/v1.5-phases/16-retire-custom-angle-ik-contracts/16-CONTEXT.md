# Phase 16: Retire Custom Angle + IK Contracts - Context

**Gathered:** 2026-07-28
**Status:** Ready for planning
**Mode:** Autonomous (user accepted discuss recommendations; proceed)

<domain>
## Phase Boundary

Remove the product presentation of custom relative-quaternion angle as OpenSim IK. Define the ROS contracts for calibration-gated OpenSim IK inputs/outputs that Phases 17–19 will implement. Do not implement the solver or calibration capture in this phase.

</domain>

<decisions>
## Implementation Decisions

### Product semantics
- **D-16-01:** Custom `/opensim/joint_angle` (relative quat math) is NOT OpenSim IK and must not be the default GUI knee/angle source.
- **D-16-02:** Default graph must stop using `opensim_ik_live` fed by that custom topic as “OpenSim IK.” Prefer a placeholder/waiting state until Phase 18–19 wire real joint states.
- **D-16-03:** Agreed output contract for later phases: `sensor_msgs/JointState` on `/opensim/joint_states` (name locked unless research proves a required rename).
- **D-16-04:** Calibration gate is hard (from Phase 17 decisions): no joint-state publication until CALIBRATED.

### Claude's Discretion
- Exact deletion vs quarantine of helper `relative_orientation_angle_deg` (may remain as debug utility if clearly named/non-product).
- Whether to keep `/opensim/joint_angle` briefly as deprecated debug behind a launch flag — default OFF and not used by GUI.

</decisions>

<canonical_refs>
## Canonical References

- `.planning/REQUIREMENTS.md` (IK-00)
- `.planning/ROADMAP.md` Phase 16
- `.planning/research/SUMMARY.md` — output topics and calibration gate
- `.planning/research/ARCHITECTURE.md` — `/opensim/joint_states`, calibration services
- `backend/rehab_robotics_bridge/opensim_node.py` — current custom joint_angle publisher
- `rehab-robotics-studio/src/graph/mockExecutor.ts` — `opensim_ik_live`
- `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` — joint angle subscription

</canonical_refs>

<code_context>
## Existing Code Insights

- `opensim_bridge` currently publishes custom Float64 `/opensim/joint_angle` from `relative_orientation_angle_deg`.
- GUI `opensim_ik_live` reads `frame.jointAngleDeg` from that topic.
- Research already specifies `/opensim/joint_states` + calibration services for the real path.

</code_context>

<specifics>
## Specific Ideas

User directive: stop the wrong custom “IK”; use official OpenSim calculation for angles.

</specifics>

<deferred>
## Deferred Ideas

- Implementing OpenSim IK solver (Phase 18)
- Toolbar Calibrate / visualizer (Phases 17, 19)

</deferred>
