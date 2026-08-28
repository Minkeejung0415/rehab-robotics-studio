---
status: resolved
trigger: "frequency changes in the block diagram are shown in the GUI but do not apply to the ESP32"
created: "2026-08-25"
updated: "2026-08-25"
---

# ESP32 Frequency Application

## Symptoms

- expected: Changing the acquisition frequency in the block diagram applies that frequency to the ESP32 devices.
- actual: The GUI reports the new value, but the front panel continues to show a frequency near 100 Hz after changing 100 to 400.
- errors: No error messages are shown.
- timeline: This previously worked, but the user does not know when it regressed.
- reproduction: In the block diagram, change the frequency from 100 Hz to 400 Hz; then inspect the front panel, which remains near 100 Hz.

## Current Focus

- hypothesis: The Properties panel changes the graph-level sample-rate state without a successful hardware control request.
- test: Trace both ESP32 editing surfaces and compare their rate-change behavior.
- expecting: The Properties panel bypasses the ROS parameter request while the inline ESP32 control sends it.
- next_action: resolved
- reasoning_checkpoint:
- tdd_checkpoint:

## Evidence

- timestamp: 2026-08-25; The ESP32 inline block control calls `setHardwareImuControl('sample_rate_hz', value)`, which requests `/esp_bridge_master/set_parameters` and maps to the firmware `FREQ:<hz>` command.
- timestamp: 2026-08-25; The Properties panel's generic `ParamField` callback called only `graphStore.updateParam`, so editing ESP32 `sampleRate` there never reached rosbridge or either ESP32.
- timestamp: 2026-08-25; Firmware and bridge already acknowledge and apply `FREQ:400`, including master-to-slave ESP-NOW relay; the loss was before the bridge.
- timestamp: 2026-08-25; Fixed the Properties panel to send an acknowledged hardware rate request on commit, and update requested/effective graph state plus runtime state only after success.
- timestamp: 2026-08-25; Verification passed: frontend typecheck, 163 frontend tests, production build, and backend ESP32-control tests (33 tests, 52 subtests).
- timestamp: 2026-08-25; Live hardware verification called `/esp_bridge_master/set_parameters` with `sample_rate_hz=400`. The service acknowledged it; both devices reported configured/effective 400 Hz, and five later observations measured master 394.3–397.3 Hz and slave 393.3–399.1 Hz.
- timestamp: 2026-08-25; The inline block control previously updated the Pair Rate and runtime before the service response. It now changes both requested/effective display values only after acknowledgement and restores the draft value after rejection. The new `test:frequency-panel` browser regression asserts the exact ROS request and failure rollback.

## Eliminated

## Resolution

- root_cause: Editing the ESP32 Pair Rate in the block Properties panel only updated the UI graph model; it did not issue the existing ROS-to-firmware sample-rate command.
- fix: Commit Pair Rate edits through `setHardwareSampleRate`; retain the previous graph value on failure and synchronize requested/effective/runtime rates only after the ESP32 acknowledges the command.
- cycles: investigation=1; fix=1
- tdd: no
- specialist_review: none (no mapped specialist skill available)
