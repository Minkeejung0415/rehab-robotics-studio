# Roadmap: Rehab Robotics Studio

## Milestone v1.1: Acquisition Operations

**Goal:** Make the GUI a trustworthy operator surface for paired ESP32 acquisition, recording, and hardware health.

### Phase 5: Confirmed Live Controls

**Goal:** Expose the remaining plugin-compatible IMU controls with board acknowledgement and paired propagation.

**Requirements:** CTRL-01, CTRL-02, CTRL-03

**Success criteria:**
1. An operator can set a valid hardware rate and sees the field update only after master acknowledgement.
2. An operator can toggle the firmware filter and configure accelerometer and gyroscope ranges from the ESP32 IMU Pair block.
3. Controls distinguish rejected, timed-out, and disconnected commands without silently changing the displayed configuration.

### Phase 6: Health And Diagnostics Data

**Goal:** Make plugin-compatible recording, pair-health, and stream diagnostics available through stable ROS/rosbridge state.

**Requirements:** HEALTH-01, HEALTH-02, DIAG-01

**Success criteria:**
1. The backend publishes a structured master/slave status snapshot with recording, SD, sync, and error fields.
2. The snapshot includes configured rate, observed stream rate, last-frame age, and reconnect state.
3. Polling and status parsing do not interrupt live acquisition or recording.

### Phase 7: Operator Surfaces And Recovery

**Goal:** Add concise GUI surfaces for recording/pair health and actionable acquisition failures.

**Requirements:** HEALTH-03, DIAG-02

**Success criteria:**
1. The GUI shows current recording/session metadata and master/slave health without requiring a terminal.
2. A finalized recording shows retrieval/conversion progress and a usable result or a clear recovery instruction.
3. A failed control or transport action identifies what failed and offers the appropriate retry/reconnect action.

### Phase 8: Operations Verification

**Goal:** Prove the controls and operator workflow against testable contracts and the two-ESP USB setup.

**Requirements:** VERIFY-03, VERIFY-04

**Success criteria:**
1. Automated tests cover command-to-status mapping and acknowledgement-only UI updates.
2. A documented two-ESP USB procedure verifies settings, status, recording, finalization, and post-session export.
3. A Playwright check covers the GUI control and health states when the browser test surface is available.

## Progress

| Phase | Status |
|-------|--------|
| 5. Confirmed Live Controls | Not started |
| 6. Health And Diagnostics Data | Not started |
| 7. Operator Surfaces And Recovery | Not started |
| 8. Operations Verification | Not started |

---
*Roadmap created: 2026-07-16*
