# Roadmap: Rehab Robotics Studio

## Overview

Milestone v1.3 restores trust in live paired-ESP32 acquisition by correcting measurement interpretation and sample identity first, then making control/recovery and health state reliable, and finally locking the corrected contracts down with focused regression coverage. The parked Block Deployment scope and audit findings 1 and 8-10 remain outside this milestone.

## Milestones

- **v1.1 Acquisition Operations** - Phases 5-8 completed; archived in `.planning/milestones/v1.1-ROADMAP.md`
- **v1.2 Block Deployment** - Parked without phases
- **v1.3 Acquisition Integrity** - Phases 9-13 planned

## Phases

- [ ] **Phase 9: Range-Correct Measurement Contract** - Operators and consumers receive IMU values interpreted with confirmed device ranges and explicit metadata.
- [ ] **Phase 10: Timing, Sequence, and Orientation Integrity** - Samples retain device identity through transport and filtering produces valid orientations.
- [ ] **Phase 11: Pause-Safe Control and ROS Recovery** - Control replies and live ROS reconnection remain reliable across pause, fallback, close, and restart events.
- [ ] **Phase 12: Fresh Acquisition Health** - Pair and stream state expires when hardware or valid frames stop reporting.
- [ ] **Phase 13: Acquisition Integrity Verification** - Automated regressions prove the corrected contracts for audit findings 2-7.

## Phase Details

### Phase 9: Range-Correct Measurement Contract
**Goal**: Operators and downstream consumers can trust that raw and live IMU values use each device's confirmed active ranges and carry enough context to be interpreted consistently.
**Depends on**: Phase 8
**Requirements**: DATA-01, DATA-02
**Success Criteria** (what must be TRUE):
  1. An operator who selects a supported non-default accelerometer or gyroscope range receives acceleration and angular velocity scaled according to the range confirmed by that device.
  2. Raw ROS and rosbridge acquisition data exposes the active range or equivalent unit/scale metadata needed to interpret every sample.
  3. Backend and GUI consumers report mutually consistent physical values for the same raw IMU sample and confirmed range.
**Plans**: TBD
**UI hint**: yes

### Phase 10: Timing, Sequence, and Orientation Integrity
**Goal**: Consumers can trace when and in what order a device acquired each sample while receiving only finite, normalized filtered orientations.
**Depends on**: Phase 9
**Requirements**: TIME-01, TIME-02, ORIENT-01
**Success Criteria** (what must be TRUE):
  1. A sample's synchronized device acquisition time remains identifiable through firmware transport, backend parsing, ROS publication, and rosbridge delivery rather than being replaced by host receipt time.
  2. TCP and UDP samples expose meaningful monotonic device sequence values, allowing a consumer to detect a gap or reordered frame.
  3. Filtering equivalent quaternion inputs `q` and `-q` yields the same physical orientation without cancellation.
  4. Every emitted filtered quaternion is finite, normalized, and usable as an orientation; zero or otherwise invalid orientations are not emitted as valid samples.
**Plans**: TBD

### Phase 11: Pause-Safe Control and ROS Recovery
**Goal**: Operators can issue commands and regain live ROS acquisition without reloads or stale sockets corrupting the active connection.
**Depends on**: Phase 10
**Requirements**: CTRL-04, RECOV-01, RECOV-02
**Success Criteria** (what must be TRUE):
  1. An operator receives the actual ROS service result while live sample rendering is paused, without a false command timeout.
  2. After the application falls back to mock data, an operator can reconnect to live ROS acquisition without reloading the page.
  3. A delayed callback from an obsolete WebSocket cannot mark a newer live connection disconnected or replace its state.
  4. Loss of an established rosbridge connection enters a controlled recovery state from which live acquisition can resume.
**Plans**: TBD
**UI hint**: yes

### Phase 12: Fresh Acquisition Health
**Goal**: Operators see pair and stream availability as time-bounded live state rather than indefinitely cached history.
**Depends on**: Phase 11
**Requirements**: HEALTH-04, HEALTH-05
**Success Criteria** (what must be TRUE):
  1. Pair availability changes offline after slave-health updates exceed the defined freshness threshold.
  2. Socket loss or an acquisition stop/restart clears prior stream and pair indicators instead of preserving an online state from the previous connection.
  3. A sustained absence of valid frames ages the stream offline, and a subsequent valid live update can establish fresh status again.
**Plans**: TBD
**UI hint**: yes

### Phase 13: Acquisition Integrity Verification
**Goal**: Maintainers can repeatedly verify every acquisition-integrity correction from audit findings 2-7 through automated tests.
**Depends on**: Phases 9-12
**Requirements**: VERIFY-05
**Success Criteria** (what must be TRUE):
  1. A maintainer can run automated regressions that exercise non-default range conversion, timestamp and sequence preservation, and quaternion antipodal/normalization cases.
  2. A maintainer can run automated regressions that exercise paused service replies, socket-generation ownership, mock-to-live fallback recovery, and established-connection loss.
  3. A maintainer can run automated regressions that prove pair and stream state expire after their freshness bounds and recover only from fresh valid updates.
  4. The focused acquisition-integrity suite passes locally without requiring the disconnected Jetson target.
**Plans**: TBD

## Progress

**Execution Order:** Phase 9 -> Phase 10 -> Phase 11 -> Phase 12 -> Phase 13

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 9. Range-Correct Measurement Contract | 0/TBD | Not started | - |
| 10. Timing, Sequence, and Orientation Integrity | 0/TBD | Not started | - |
| 11. Pause-Safe Control and ROS Recovery | 0/TBD | Not started | - |
| 12. Fresh Acquisition Health | 0/TBD | Not started | - |
| 13. Acquisition Integrity Verification | 0/TBD | Not started | - |

---
*Roadmap created: 2026-07-23 for milestone v1.3 Acquisition Integrity*
