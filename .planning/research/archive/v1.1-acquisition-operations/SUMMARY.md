# Research Summary: ROS2 Backend Alignment

## Recommendation

Mirror the plugin repository's topic-first architecture, not its package name or every implementation detail. The stable compatibility boundary is the `oe_esp32.raw.v1` JSON schema and the dual-node launch topology.

## Key Decisions

- Live frames arrive on UDP after a TCP control handshake.
- `/esp/raw/{role}` and `/esp/filtered/{role}` carry JSON `std_msgs/String` payloads.
- The default workflow runs independent master/slave bridges and filters, one OpenSim forwarder, and an optional raw recorder.
- Rosbridge remains available for GUI consumers.
- Protocol validation and replayable offline tests are required before live-hardware acceptance.

## Watch Outs

- Do not preserve the broken local multi-node aggregator as the main orchestration path.
- Do not merge raw and scaled/unit-converted data into one ambiguous contract.
- Treat recorder writes and reconnect handling as first-class reliability work.
