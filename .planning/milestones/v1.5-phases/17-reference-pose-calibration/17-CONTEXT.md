# Phase 17: Reference-Pose Calibration - Context

**Gathered:** 2026-07-28
**Status:** Ready for planning
**Mode:** Discuss decisions locked by user (accepted all recommendations)

<domain>
## Phase Boundary

Make sensor-to-model mounting-offset calibration possible from the top-level Studio chrome. Capture a bounded stable window in a fixed known pose, compute mounting offsets, expose status, and hard-gate joint-angle publication until CALIBRATED. Do not ship the full persistent IK solver here (Phase 18) and do not add the visualizer button here (Phase 19) except as needed for calibration status display.

</domain>

<decisions>
## Implementation Decisions

### Top-level operator UX (LOCKED)
- **D-17-01 (Trigger):** Toolbar **Calibrate** button in Studio chrome (same top bar as Rec/Deploy), not buried only in the graph.
- **D-17-02 (Known pose):** Fixed lab pose — **standing, knees extended**. Show a short on-screen instruction when Calibrate is pressed.
- **D-17-03 (IK gate):** Hard gate — **no joint angles published** until calibration state is **CALIBRATED**.
- **D-17-04 (Clear):** Separate **Clear cal** control that returns to UNCALIBRATED and invalidates active offsets.

### Status surface (LOCKED)
- **D-17-05:** Front Panel OpenSim section shows UNCALIBRATED / CAPTURING / CALIBRATED / FAILED (+ reason).

### Capture behavior (LOCKED preferences)
- **D-17-06:** Multi-sample stable window (not first-frame auto-calibrate). Reject capture if motion exceeds a stability threshold during the window.
- **D-17-07:** ROS services per research intent: `/opensim/calibration/capture` and `/opensim/calibration/clear` (Trigger or equivalent), called from GUI via rosbridge.

### Claude's Discretion
- Exact window duration and residual thresholds (research/measure; start conservative).
- Whether Clear cal lives only on toolbar or also mirrored in HealthPanel (toolbar required; mirror optional).
- Artifact persistence format for the active session (in-memory first is acceptable if status + gate work; versioned save/load can follow).

</decisions>

<canonical_refs>
## Canonical References

- `.planning/REQUIREMENTS.md` (IK-01..IK-04)
- `.planning/ROADMAP.md` Phase 17
- `.planning/research/SUMMARY.md` — Phase 17 Reference-Pose Calibration
- `.planning/research/ARCHITECTURE.md` — `/opensim/calibration/capture|clear`
- `.planning/research/FEATURES.md` — anti first-sample calibration
- `rehab-robotics-studio/src/components/chrome/Toolbar.tsx` — top-level button plug-in
- `rehab-robotics-studio/src/components/dashboard/HealthPanel.tsx` — OpenSim status surface
- `rehab-robotics-studio/src/data/appDataSource.ts` — hardware command facade

</canonical_refs>

<code_context>
## Existing Code Insights

- No calibration services exist on `opensim_bridge` today.
- Browser `RelativeAngleStabilizer` is NOT mounting calibration — do not reuse it as OpenSense calibration.
- Toolbar already patterns busy/toast flows for Rec/Deploy.

</code_context>

<specifics>
## Specific Ideas

User accepted discuss recommendations 1A/2A/3A/4A verbatim for autonomous execution.

</specifics>

<deferred>
## Deferred Ideas

- Multi-pose calibration library
- Cross-session versioned calibration save/load bound to model hashes (future)
- Clinical validation

</deferred>
