# Roadmap: Rehab Robotics Studio

## Overview

Milestone v1.4 is a single-phase proof of connection between the paired ESP quaternion topics and OpenSim. It replaces the placeholder one-topic UDP forwarder with a directly testable ROS subscription and OpenSim live-orientation update path. IK, calibration, production packaging, and embedded visualization remain deferred.

## Milestones

- **v1.1 Acquisition Operations** - Phases 5-8 completed and archived.
- **v1.2 Block Deployment** - Parked without phases.
- **v1.3 Acquisition Integrity** - Unfinished prior scope preserved in repository history and existing Phase 9 artifacts.
- **v1.4 OpenSim Quaternion Live Link** - Phase 15 planned.

## Phases

- [ ] **Phase 15: OpenSim Quaternion Live Link** - An operator can launch OpenSim integration and see the model receive the quaternion orientations already published by the master and slave ESP devices.

## Phase Details

### Phase 15: OpenSim Quaternion Live Link

**Goal**: Prove the complete live path from the existing ESP `sensor_msgs/Imu` quaternion topics through `opensim_bridge` into mapped OpenSim model-frame orientation updates.
**Depends on**: Existing ESP native IMU publishers
**Requirements**: LINK-01, LINK-02, LINK-03, LINK-04, LINK-05, LINK-06
**Success Criteria**:
1. Launching the stack starts `opensim_bridge` with configurable master/slave IMU topics, model path, and frame mappings.
2. Publishing known valid quaternions on both configured topics produces corresponding orientation updates in the OpenSim adapter or native visualizer demonstration.
3. ROS `(x, y, z, w)` ordering and the OpenSim rotation convention are documented and covered by deterministic identity and known-axis tests.
4. Missing runtime/model assets, invalid inputs, unknown mappings, and stale streams are visible through logs or a status topic.
5. The local verification path passes without connected ESP hardware.
**Plans**: TBD

## Progress

**Execution Order:** Phase 15

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 15. OpenSim Quaternion Live Link | 0/TBD | Not started | - |

---
*Roadmap created: 2026-07-27 for milestone v1.4 OpenSim Quaternion Live Link*
