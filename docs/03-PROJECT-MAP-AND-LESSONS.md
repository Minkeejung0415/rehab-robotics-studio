# Rehab Robotics - Project Map, File Ownership, and Lessons Learned

## Purpose and scope

This is the orientation document for a new maintainer. It explains the repository tree, where each responsibility lives, what to edit for a feature, and which failures have already been found. Physical setup is in `01-SETUP-WIRING-AND-JETSON.md`; daily operation is in `02-RUN-OPERATE-AND-CHANGE.md`.

## 1. System boundaries

The system is a rehabilitation-robotics prototype with ESP32 Master/Slave IMU nodes, a Windows relay and WSL ROS 2 path, a React Studio application, OpenSim IK, local SD recording, and an optional Jetson ROS 2 acquisition host. Each layer owns one job. Maintain those boundaries: components render; stores own UI/runtime state; data sources transport data; ROS nodes translate/validate; firmware acquires and records; OpenSim supplies calibrated IK.

## 2. Repository tree and what each folder means

```text
repo/
├── firmware/
│   ├── step_node/                 Master ESP32 sketch: IMU, DIO, ESP-NOW, TCP/UDP, SD
│   └── step_node_slave/           Slave sketch: same contracts, Slave role and pin map
├── backend/                       ROS bridge, fleet identity, mapping/OpenSim support, backend tests
├── rehab-robotics-studio/         React + TypeScript Studio UI
│   └── src/
│       ├── components/            visible panels, nodes, controls; no direct ROS construction
│       ├── data/                  mock/live data-source boundary and rosbridge transport
│       ├── graph/                 block types, defaults, graph serialization
│       └── state/                 runtime, mapping, and persistent UI ownership
├── scripts/                       Windows startup/stop, OpenSim link, acceptance helpers
├── opensim/                       OpenSim model/resources and IK support files
├── logs/                          local runtime diagnostics; do not treat as source of truth
├── output/pdf/                    distributable handoff PDFs
└── docs/                          human-facing handoff documents and the physical-hardware evidence gate
    └── hardware-acceptance-report.md  required evidence before fleet promotion
```

The documents in this folder have deliberate roles:

| Document | Use it for |
| --- | --- |
| `01-SETUP-WIRING-AND-JETSON.md` | first machine, wiring, network, Jetson and auxiliary-sensor setup |
| `02-RUN-OPERATE-AND-CHANGE.md` | startup, recording, troubleshooting, and safe configuration changes |
| `03-PROJECT-MAP-AND-LESSONS.md` | repository ownership, file map, historical failures, next work |
| `04-COMMISSIONING-RECORD.md` | controlled on-site BOM, wiring, versions, photos, test evidence, and sign-off |
| `TOTAL-HANDOFF-EN.md` | earlier combined reference; the four documents above are the preferred entry points |

## 3. File ownership and change impact

| If you change... | Start here | Required follow-through |
| --- | --- | --- |
| an ESP packet, command, SD record, or timing path | both `.ino` sketches | decoder/relay, ROS bridge, tests, operational docs |
| device identity or fleet assignment | `fleet_bridge_node.py` | registry aliases, Studio data source, reconnect tests |
| a Studio control | `RosbridgeDataSource.ts` and relevant component/store | ROS service acknowledgement, rollback UI, regression test |
| graph block semantics | `graph/blockDefinitions.ts` | node UI, properties editor, persisted graph compatibility |
| mapping/model semantics | `MappingWorkspace.tsx`, `mapping_node.py` | saved mapping, model catalog, OpenSim validation |
| calibration or IK output | `opensim_node.py`, `opensim/` | status reasons, fail-closed joint-state behavior, OpenSim tests |
| startup topology | `start_stepesp_wireless.ps1` | passed parameters, firewall/network record, runbook |

Always inspect `git status --short` before edits. Firmware communications/recording changes require Master and Slave review together. Never key persistent identity, mapping, or acceptance evidence on DHCP IP ordering.

## 4. Problems encountered and how they were corrected

### 4.1 GUI sample rate changed visually but hardware did not - resolved

The Properties panel originally updated only `graphStore.updateParam`, so Pair Rate could change in the browser while the hardware remained near 100 Hz. The fix routes rate commits through `setHardwareSampleRate` / `setHardwareImuControl`, which calls `/esp_bridge_master/set_parameters`. The UI updates requested/effective rate only after acknowledgement and rolls back on failure. The regression script `rehab-robotics-studio/scripts/frequency-panel-regression.mjs` covers success and rejection. Hardware observations after the fix were about 394-397 Hz Master and 393-399 Hz Slave at configured 400 Hz.

**Lesson:** every physical UI control needs an acknowledgement, failure state, and transport-boundary test.

### 4.2 Long 500 Hz tests had backwards Slave timestamps - source fix applied, revalidate on hardware

A 15-minute DIO test once showed no queue drops but 46.408 ms mean skew, 98.875 ms p95, 99.995 ms maximum skew, and a negative Slave inter-edge interval. ESP-NOW packet timing jitter was directly replacing a Slave clock offset, and the 64-bit offset could be read torn on a 32-bit MCU.

The firmware now collects startup samples, chooses a low-delay starting observation, rejects observations more than 2 ms from estimate, slews accepted corrections by at most 100 microseconds, and protects shared clock state. Source topology tests passed and both sketches compiled. Flash both nodes and repeat the long test before calling this resolved on hardware.

**Lesson:** rate averages and zero queue drops do not prove timestamp integrity; test monotonicity and edge skew over time.

### 4.3 DIO 2 ms polling issue was replaced with ISR capture - short pass, long acceptance open

Both sketches now attach `dioEdgeIsr` to D0/GPIO1 on `CHANGE`, timestamp with `esp_timer_get_time()` in the ISR, queue events, and publish safely in foreground code. The queue capacity is 16 and ISR/foreground access is synchronized.

The 60-second 500 Hz ISR capture passed the 2 ms maximum target: 1.680 ms mean absolute skew, 1.783 ms p95, 1.795 ms maximum. The 900-second capture matched edge counts with zero queue drops and good average/p95 (1.708/1.809 ms), but a 14.364 ms maximum outlier failed the strict 2 ms maximum condition. Preserve the ISR architecture and investigate rare outliers, debounce, queue/overrun telemetry, clock correction, and edge pairing before closing the requirement.

### 4.4 Network topology changed - operational caution

Older material uses the `STEP_ESP32` Soft AP and `192.168.4.1`. The current startup script defaults to an iPhone hotspot profile and Master host `172.20.10.3`, while firmware still supports Soft AP behavior. Read the current script and passed parameters; do not copy an old IP into a new deployment.

### 4.5 Mapping and OpenSim require fail-closed behavior

The project moved from role-based two-sensor assumptions to MAC-based identities, model-derived frames, persisted mapping, and calibration-gated IK. Product `/opensim/joint_states` must not publish when calibration is missing/capturing/failed/stale/invalid or when source timestamps are unusable. Never replace it with a raw relative quaternion calculation.

## 5. Recommended next-owner roadmap

1. Flash the current timing firmware and collect a new 900-second 500 Hz DIO data set with raw logs.
2. Close the rare long-run DIO outlier rather than removing the 2 ms criterion.
3. Perform all real-hardware rows in `hardware-acceptance-report.md` and attach actual measurements.
4. For any new firmware control, add backend validation, rosbridge handling, Studio acknowledgement/rollback, and an automated test.
5. Add sensors one by one with canonical identities and explicit model mapping; test reconnect under load at every size.
6. Document every measurement with date, firmware hash, board IDs, network topology, command line, method, and raw-log path.
