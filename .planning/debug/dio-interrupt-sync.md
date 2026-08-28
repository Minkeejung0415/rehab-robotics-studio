---
status: investigating
trigger: "500 Hz paired acquisition requires sub-sample synchronization; current D0 polling leaves 1.599 ms mean and up to 3.309 ms skew after clock-jump repair."
created: "2026-08-26"
updated: "2026-08-26"
---

# DIO Interrupt Synchronization

## Symptoms

- expected: Shared D0 edges produce monotonic, hardware-timestamped references that keep two 500 Hz acquisitions aligned within 2 ms over 15 minutes.
- actual: D0 is polled from the main loop. Long-run clock jumps are repaired, but residual edge skew is 1.599 ms mean, 2.454 ms p95, and 3.309 ms maximum.
- errors: Strict 2 ms maximum-skew test fails despite zero queue drops and equal edge counts.
- timeline: Persistent after filtered ESP-NOW correction fix.
- reproduction: Feed a shared 10 Hz square wave to D0/GPIO1 on both boards and run the 900-second 500 Hz serial DIO test.

## Current Focus

- hypothesis: Main-loop polling, not clock discontinuity, dominates residual DIO timing error. GPIO edge interrupts can timestamp the common physical edge independently of acquisition-loop scheduling.
- test: Trace DIO setup and access paths, then add safe ISR capture plus atomic foreground publication and test coverage.
- expecting: DIO timestamp captures are edge-driven, monotonic, and no longer depend on loop polling latency.
- next_action: implement ISR capture for both roles
- reasoning_checkpoint:
- tdd_checkpoint:

## Evidence

- timestamp: 2026-08-26; After ESP-NOW correction fix, 15-minute test has 18,002/18,002 paired transitions, monotonic slave intervals, but 3.309 ms maximum skew.
- timestamp: 2026-08-26; Both firmware loops call updateDio() before the sampling gate, and no DIO GPIO interrupt is attached.

## Eliminated


## Resolution

- root_cause:
- fix:
- verification:
- files_changed:
