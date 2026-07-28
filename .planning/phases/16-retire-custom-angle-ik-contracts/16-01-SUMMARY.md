---
phase: 16-retire-custom-angle-ik-contracts
plan: "01"
subsystem: backend
tags: [opensim, ros2, joint-angle, fail-closed, unittest]

requires:
  - phase: 15-opensim-live-link
    provides: opensim_bridge dual-IMU live link and status schema
provides:
  - Default-OFF publish_joint_angle_enabled gate on opensim_bridge
  - Non-product status joint_angle_deg (null when debug off)
  - Quarantined relative_orientation_angle_deg debug utility
  - Live-link docs rejecting custom angle as OpenSim IK
affects:
  - 16-02 GUI retirement of custom angle as product IK
  - 16-03 IK contract lock for /opensim/joint_states

tech-stack:
  added: []
  patterns:
    - "Debug ROS publishers gated by launch/parameter flag default false"
    - "Product status fields null/omit when debug path disabled"

key-files:
  created: []
  modified:
    - backend/rehab_robotics_bridge/opensim_node.py
    - backend/rehab_robotics_bridge/opensim_adapter.py
    - backend/launch/rehab_robotics.launch.py
    - backend/launch/opensim_live_link.launch.py
    - backend/test/test_opensim_node.py
    - backend/test/test_opensim_launch.py
    - backend/test/test_opensim_adapter.py
    - docs/opensim-quaternion-live-link.md

key-decisions:
  - "Keep /opensim/joint_angle only behind publish_joint_angle_enabled default false"
  - "status_snapshot sets joint_angle_deg to null when debug publisher off"
  - "Retain relative_orientation_angle_deg as named non-product debug utility"

patterns-established:
  - "Fail-closed default: no Float64 joint_angle publisher unless flag enabled"
  - "Launch args mirror node parameter defaults for debug gates"

requirements-completed: [IK-00]

duration: 15min
completed: 2026-07-28
---

# Phase 16 Plan 01: Retire Backend Custom Joint Angle Summary

**Default-OFF `publish_joint_angle_enabled` gate stops opensim_bridge from advertising relative-quat Float64 as product OpenSim IK**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-28T17:25:09Z
- **Completed:** 2026-07-28T17:30:00Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Fail-closed unittest contract: default paired live IMUs never create/publish `/opensim/joint_angle`
- Node/launch wire `publish_joint_angle_enabled` default `false`; optional debug path retained
- Live-link doc states custom Float64 angle is not product IK

## Task Commits

1. **Task 1: Fail-closed backend tests** - `8b475c9` (test)
2. **Task 2: Demote custom joint_angle publisher and status field** - `cb363b0` (feat)

## Files Created/Modified
- `backend/rehab_robotics_bridge/opensim_node.py` - Gated debug publisher + null product status angle
- `backend/rehab_robotics_bridge/opensim_adapter.py` - Debug/utility docstring for relative angle helper
- `backend/launch/rehab_robotics.launch.py` / `opensim_live_link.launch.py` - Flag default false
- `backend/test/test_opensim_*.py` - Fail-closed + debug-flag coverage
- `docs/opensim-quaternion-live-link.md` - Explicit non-IK product semantics

## Decisions Made
- Discretion: keep deprecated debug publisher behind flag rather than delete outright
- Product `joint_angle_deg` is `null` when flag off (key retained for schema stability)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Working tree already contained an ungated product joint_angle path (uncommitted WIP); reshaped into gated default-OFF implementation rather than shipping product-on first.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Backend no longer defaults custom angle as product IK; ready for Studio GUI retirement (16-02) and contract lock (16-03).

---
*Phase: 16-retire-custom-angle-ik-contracts*
*Completed: 2026-07-28*
