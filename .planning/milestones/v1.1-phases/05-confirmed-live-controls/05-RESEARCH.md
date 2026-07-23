# Phase 5 Research: Confirmed Live Controls

## Existing Capability

- `step_node.ino` accepts `FILTER ON|OFF`, `FREQ:<hz>`, `CFG 0 ACC <0-3>`, `CFG 0 GYR <0-3>`, and `CFG 0 SRATE <hz>`; the master relays paired configuration to the slave over ESP-NOW.
- The plugin bridge already forwards these command families while streaming. USB binary transport does not reliably preserve every text acknowledgement, so the bridge must provide a deterministic command-result contract to the ROS layer.
- The GUI has a real sample-rate field with acknowledgement-only commits. It does not yet offer filter, range, or effective-rate controls.

## Decisions

- Retain `RosbridgeDataSource` as the sole browser-to-ROS transport boundary.
- Add a typed, shared control request path rather than duplicating recording-specific command handling.
- Use optimistic drafts only; commit displayed values to graph/runtime state after a confirmed command result.
- Keep all physical changes master-originated so existing ESP-NOW propagation remains authoritative.

## Risks

- The USB serial bridge can interleave binary frames and control text. Tests must validate the bridge preserves streaming after a control command.
- Rate values above the available serial bandwidth may be accepted by firmware but not sustain lossless USB delivery. Phase 5 should report acceptance; Phase 6 will expose observed stream rate and loss diagnostics.
- Filter and range state needs a queryable source of truth after reconnect, not only UI-local state.

## Verification Strategy

1. Unit-test command construction and result parsing for success, rejection, timeout, and disconnect paths.
2. Run a two-ESP USB test with a non-default rate, filter toggle, accel range, gyro range, and effective sensor rate.
3. Confirm both master and slave resume real frame publication after each command.
