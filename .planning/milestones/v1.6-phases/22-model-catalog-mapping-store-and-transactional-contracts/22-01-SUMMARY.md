---
phase: 22-model-catalog-mapping-store-and-transactional-contracts
plan: "01"
subsystem: rehab_robotics_interfaces
tags: [ros2, srv, interfaces, mapping, contracts]

dependency_graph:
  requires: []
  provides:
    - rehab_robotics_interfaces/srv/SetAssignment.srv
    - rehab_robotics_interfaces/srv/ApplyMapping.srv
    - rehab_robotics_interfaces/srv/GetMappingState.srv
    - rehab_robotics_interfaces/srv/ResetMapping.srv
  affects:
    - backend/rehab_robotics_bridge/mapping_node.py (future plan 22-03+)

tech_stack:
  added: []
  patterns:
    - ROS 2 .srv interface definition (request/response separated by ---)
    - rosidl_generate_interfaces CMake registration pattern

key_files:
  created:
    - rehab_robotics_interfaces/srv/SetAssignment.srv
    - rehab_robotics_interfaces/srv/ApplyMapping.srv
    - rehab_robotics_interfaces/srv/GetMappingState.srv
    - rehab_robotics_interfaces/srv/ResetMapping.srv
  modified:
    - rehab_robotics_interfaces/CMakeLists.txt

decisions:
  - "Used plain string fields for outcome and state — no ROS2 enum type; mapping_node validates values at runtime per D-09/D-10/D-13"
  - "GetMappingState uses single state_json string response to avoid defining a custom message type for Phase 22"
  - "ResetMapping uses 'ok'/'unknown_model' outcomes per plan action block (authoritative), not 'reset'/'invalid_hash' from plan_summary"

metrics:
  duration: "< 5 minutes"
  completed: "2026-08-05"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 22 Plan 01: ROS Service Interfaces for mapping_node Summary

Four ROS 2 .srv interface contracts for the mapping_node, covering assignment, apply, state query, and reset operations, registered in CMakeLists.txt so colcon generates Python stubs.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create four mapping service .srv files | 5a7babe | SetAssignment.srv, ApplyMapping.srv, GetMappingState.srv, ResetMapping.srv |
| 2 | Register all four services in CMakeLists.txt | 5a7babe | CMakeLists.txt |

## Interface Contracts Defined

### SetAssignment.srv
Request: `string device_id`, `string segment`, `string frame`, `string state`
Response: `string outcome`, `string detail`
Valid state values: `assigned`, `not_used`, `unassigned`
Valid outcomes: `ok`, `duplicate_frame`, `invalid_frame`, `invalid_state`, `unknown_device`

### ApplyMapping.srv
Request: `int32 expected_revision`
Response: `string outcome`, `int32 applied_revision`, `string detail`
Valid outcomes: `applied`, `model_changed`, `revision_mismatch`, `incomplete`, `duplicate_frame`, `invalid_frame`, `blocked`, `solver_insufficient_warning`

### GetMappingState.srv
Request: (empty)
Response: `string state_json`
Purpose: returns full mapping state serialized as JSON; single-string approach avoids a custom message type in Phase 22.

### ResetMapping.srv
Request: `string model_hash`
Response: `string outcome`
Valid outcomes: `ok`, `unknown_model`
Note: model_hash accepts SHA-256 hex string or empty string to reset current model's draft.

## Deviations from Plan

### Minor Outcome String Discrepancy (plan_summary vs plan body)

The `<plan_summary>` in the orchestrator prompt listed ResetMapping outcomes as "reset"/"invalid_hash", but the plan's authoritative `<action>` block specifies "ok"/"unknown_model". The plan body was treated as authoritative. The outcome strings used are "ok"/"unknown_model" per the action block and CONTEXT D-13 spirit.

### Missing invalid_state outcome added (Rule 2)

The threat model (T-22-01-01) requires `invalid_state` be a valid outcome for SetAssignment when the state field carries an unsupported value. The plan's action block did not list `invalid_state` explicitly in the outcome enumeration, but it is required for the mitigation to be implementable. The outcome is documented in the SUMMARY (the .srv file itself only defines field names, not value constraints — constraints are enforced by mapping_node at runtime). No file change was required; this is a documentation clarification only.

## Known Stubs

None — .srv interface files are contracts only; no runtime logic is present in this plan.

## Threat Flags

None — no new network endpoints or auth paths introduced. The .srv files define wire contracts only; mapping_node (future plan) enforces validation per T-22-01-01 and T-22-01-02.

## Self-Check: PASSED

- rehab_robotics_interfaces/srv/SetAssignment.srv: EXISTS, contains "---"
- rehab_robotics_interfaces/srv/ApplyMapping.srv: EXISTS, contains "---"
- rehab_robotics_interfaces/srv/GetMappingState.srv: EXISTS, contains "---"
- rehab_robotics_interfaces/srv/ResetMapping.srv: EXISTS, contains "---"
- rehab_robotics_interfaces/CMakeLists.txt: contains SetAssignment.srv, ApplyMapping.srv, GetMappingState.srv, ResetMapping.srv
- Commit 5a7babe: verified present in git log
- Existing entries (IdentifyDevice.srv, ProcessingBlockUpdate.msg, DEPENDENCIES std_msgs): untouched
