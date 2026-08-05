---
phase: 22-model-catalog-mapping-store-and-transactional-contracts
plan: "06"
subsystem: backend/launch
tags: [launch, entry-points, ros2, model-catalog, mapping]
dependency_graph:
  requires: ["22-04", "22-05"]
  provides: ["model_catalog_node launch registration", "mapping_node launch registration"]
  affects: ["backend/setup.py", "backend/launch/rehab_robotics.launch.py"]
tech_stack:
  added: []
  patterns: ["ROS2 Node with IfCondition guard", "DeclareLaunchArgument with default"]
key_files:
  modified:
    - backend/setup.py
    - backend/launch/rehab_robotics.launch.py
decisions:
  - "Reused existing model_path launch argument for opensim_model_path rather than adding a redundant new arg"
  - "Both nodes guarded with IfCondition (default true) matching the existing enable_* pattern"
  - "mapping_store_path new arg defaults to empty string, MappingNode resolves empty to ~/.ros/rehab_robotics/mapping_store.json internally"
metrics:
  duration: "5 minutes"
  completed: "2026-08-05"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 22 Plan 06: Wire model_catalog_node and mapping_node into launch — Summary

**One-liner:** Registered model_catalog_node and mapping_node as ROS console_scripts entry points and added both to rehab_robotics.launch.py with IfCondition guards and parameterised launch arguments.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Register new entry points in setup.py | dcce32c | backend/setup.py |
| 2 | Add model_catalog_node and mapping_node to rehab_robotics.launch.py | dcce32c | backend/launch/rehab_robotics.launch.py |

## What Was Built

### backend/setup.py
Two new `console_scripts` entries appended after the existing eight:

```python
'model_catalog_node = rehab_robotics_bridge.model_catalog_node:main',
'mapping_node = rehab_robotics_bridge.mapping_node:main',
```

All existing eight entries are unchanged.

### backend/launch/rehab_robotics.launch.py
Three new `DeclareLaunchArgument` entries added to the args list:

- `enable_model_catalog` (default `'true'`) — IfCondition guard for model_catalog_node
- `enable_mapping_node` (default `'true'`) — IfCondition guard for mapping_node
- `mapping_store_path` (default `''`) — forwarded as `store_path` to MappingNode

Two new Node objects defined and added to the `LaunchDescription` return list:

```python
model_catalog = Node(
    package='rehab_robotics_bridge',
    executable='model_catalog_node',
    name='model_catalog_node',
    output='screen',
    parameters=[{'opensim_model_path': LaunchConfiguration('model_path')}],
    condition=IfCondition(LaunchConfiguration('enable_model_catalog')),
)
mapping = Node(
    package='rehab_robotics_bridge',
    executable='mapping_node',
    name='mapping_node',
    output='screen',
    parameters=[{'store_path': LaunchConfiguration('mapping_store_path')}],
    condition=IfCondition(LaunchConfiguration('enable_mapping_node')),
)
```

The `model_catalog_node` receives its `opensim_model_path` parameter from the pre-existing `model_path` launch argument (avoiding a redundant arg). All existing nodes (fleet_bridge_node, esp32_bridge_node, filter_node, opensim_bridge, opensim_test_publisher, esp_record, esp_status, processing_block_observer, rosbridge_websocket) are unchanged.

## Verification Results

| Check | Result |
|-------|--------|
| setup.py contains model_catalog_node entry | PASSED |
| setup.py contains mapping_node entry | PASSED |
| setup.py all 8 original entries intact | PASSED |
| rehab_robotics.launch.py AST parse | PASSED |
| rehab_robotics.launch.py contains model_catalog_node | PASSED |
| rehab_robotics.launch.py contains mapping_node | PASSED |
| rehab_robotics.launch.py enable_model_catalog arg present | PASSED |
| rehab_robotics.launch.py enable_mapping_node arg present | PASSED |
| fleet_bridge_node not regressed | PASSED |
| opensim_bridge not regressed | PASSED |
| test_model_catalog_node (53 tests) | PASSED |
| test_mapping_node (included in 53) | PASSED |
| test_fleet_bridge (35 tests) | PASSED |

## Deviations from Plan

None — plan executed exactly as written.

**Note on pre-existing test failure:** `test_identify_completes_while_unrelated_fleet_session_is_reconnecting` in `test_esp32_controls.py` fails with `ImportError: cannot import name 'Float32MultiArray' from 'std_msgs.msg'` — this is a pre-existing ROS stub environment limitation that predates these changes. `test_esp32_controls.py` is not in the git diff and was not touched by this plan.

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-22-06-01 (Tampering: mapping_store_path) | Mitigated — MappingNode resolves empty string to hardcoded default path internally; arbitrary paths are operator-controlled by design |
| T-22-06-02 (Info Disclosure: model_path exposure) | Accepted — model_path was already visible in existing launch configuration |
| T-22-06-SC (No package installs) | Confirmed — launch file is plain Python, no new dependencies |

## Self-Check: PASSED

- `backend/setup.py` exists and contains both new entry points: confirmed
- `backend/launch/rehab_robotics.launch.py` exists and passes AST parse: confirmed
- Commit `dcce32c` exists: confirmed (git rev-parse --short HEAD)
