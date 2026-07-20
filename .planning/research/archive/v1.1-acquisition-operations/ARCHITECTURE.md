# Architecture Research: ROS2 Backend Alignment

## Target Data Flow

```text
ESP32 TCP control  ->  UDP frame stream
                         |
                         v
                  esp_bridge (per node)
                         |
              /esp/raw/master, /esp/raw/slave
                         |
              esp_filter (per node)
                         |
       /esp/filtered/master, /esp/filtered/slave
                         |
               opensim_bridge (selected source) -> OpenSim UDP
                         |
            esp_record (raw topics) -> JSONL sessions

rosbridge_server exposes ROS topics to the GUI.
```

## Integration Rules

1. The bridge owns network protocol parsing and emits only valid canonical samples.
2. Filters consume and produce JSON strings so they are replayable and independently testable.
3. The OpenSim adapter forwards filtered payloads, not raw bytes.
4. The recorder subscribes without blocking publishers and owns file lifecycle.
5. The launch file owns master/slave topology and all deployment-time configuration.

## Build Order

1. Shared schema and UDP bridge.
2. Filter, OpenSim adapter, recorder, and status behavior.
3. Full launch configuration plus rosbridge compatibility.
4. Protocol and offline-pipeline verification.

## Sources

- Plugin repository `live_workflow.launch.py` and node implementations.
- [ROS 2 launch guide](https://docs.ros.org/en/ros2_documentation/lyrical/How-To-Guides/Launching-composable-nodes.html): launch-time node configuration and remapping patterns.
