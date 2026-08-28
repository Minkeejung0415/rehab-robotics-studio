---
status: resolved
trigger: "15-minute 500 Hz DIO synchronization test reports slave timestamp jumps, up to 99.995 ms skew, and negative slave inter-edge intervals."
created: "2026-08-26"
updated: "2026-08-26"
---

# ESP-NOW Clock Jumps

## Symptoms

- expected: At 500 Hz, master and slave DIO timestamps remain monotonic and within the 2 ms one-sample synchronization requirement over 15 minutes.
- actual: Both nodes acquire near 500 Hz with no queue drops, but slave corrected timestamps jump backward and the DIO comparison reports 46.408 ms mean absolute skew, 98.875 ms p95 skew, and 99.995 ms maximum skew.
- errors: The test fails its 2 ms maximum-skew requirement. The slave reports a negative inter-edge interval.
- timeline: Short tests showed millisecond-scale skew; the failure is clear in a 15-minute capture.
- reproduction: Drive GPIO D0 on both ESPs from the same 10 Hz square-wave source, run `test_dio_sync_serial.py` for 900 seconds at `--sample-rate 500 --threshold-ms 2`, then inspect the DIO timestamp statistics.

## Current Focus

- hypothesis: confirmed. The slave immediately replaces its ESP-NOW clock offset on every received sync packet, so packet-arrival jitter causes `recNowUs()` to jump backward or forward.
- test: completed. Added startup qualification, outlier rejection, bounded filtered corrections, and locked 64-bit clock snapshots.
- expecting: Corrected slave time remains monotonic and insensitive to delayed ESP-NOW packets; hardware validation remains required.
- next_action: flash both compiled sketches and rerun the 15-minute 500 Hz DIO capture.
- reasoning_checkpoint:
- tdd_checkpoint:

## Evidence

- timestamp: 2026-08-26; 15-minute 500 Hz test: master 496.14 samples/s, slave 495.12 samples/s, zero queue drops, master loop overruns 7, slave loop overruns 24, 18,002 DIO edges each, 17,994 paired; mean absolute skew 46.408 ms, p95 98.875 ms, maximum 99.995 ms.
- timestamp: 2026-08-26; Slave DIO inter-edge interval minimum was -36.164 ms, proving the reported corrected timestamp was non-monotonic.
- timestamp: 2026-08-26; Firmware inspection found both receive paths directly assign `g_clock_offset_us = pkt->time_us - recv_us`, importing one-way ESP-NOW delivery jitter into recorded timestamps.
- timestamp: 2026-08-26; `g_clock_offset_us` is a 64-bit value written in the ESP-NOW callback and read by the acquisition loop with no synchronization, allowing a torn read on the 32-bit ESP32-S3.
- timestamp: 2026-08-26; `python -m unittest backend.test.test_stepesp_firmware_topology` passed (28 tests); both XIAO ESP32-S3 sketches compiled successfully.

## Eliminated


## Resolution

- root_cause: One-way ESP-NOW packet delay and an unsynchronized 64-bit shared offset were directly exposed as timestamp corrections, causing time discontinuities.
- fix: Require five startup samples and use the least-delayed sample, reject offset observations more than 2 ms from the estimate, slew accepted corrections by at most 100 us, and snapshot shared clock state in a critical section.
- verification: 28 firmware topology tests pass; master and slave Arduino sketches compile. Physical 15-minute validation has not run because no boards were flashed.
- files_changed: firmware/step_node/step_node.ino; firmware/step_node_slave/step_node_slave.ino; backend/test/test_stepesp_firmware_topology.py
