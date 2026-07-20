# Feature Research: ROS2 Backend Alignment

## Table Stakes

- TCP `REDPITAYA` then `START` handshake, with explicit rejection of non-UDP live transport.
- UDP listener per ESP32 node; master and slave require distinct local ports.
- Header/source/element/size validation before interpreting payload bytes.
- Canonical raw JSON topic schema including sample index, role, ID, body segment, IMU, quaternion, DIO, and sync metadata.
- Independent filter nodes producing filtered JSON topics.
- OpenSim UDP adapter consuming a selected filtered topic.
- Non-blocking recorder with a separate file per raw topic.
- One launch file that starts the complete dual-node workflow.

## Safety and Observability

- Bounded queues and explicit drop warnings under backpressure.
- Exponential reconnect after handshake or transport loss.
- Startup and first-message logs per pipeline stage.
- Parameterized network endpoints, topics, body segments, filter window, output directory, and recording enablement.

## Explicitly Deferred

- Frontend replacement of its mock source.
- Firmware protocol redesign.
- Motor control, EtherCAT, and clinical workflow UI.
