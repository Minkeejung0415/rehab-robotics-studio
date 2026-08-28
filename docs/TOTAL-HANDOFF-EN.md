# Rehab Robotics - Total Handoff Document

## 1. Non-negotiable rules

1. Use `esp32:aabbccddeeff` canonical full-MAC identities, never DHCP IP addresses or roles, to identify devices.
2. `/opensim/joint_states` is the product knee-angle output. `/opensim/joint_angle` is debug-only.
3. Use knee angles only when calibration is `CALIBRATED` and IK is valid.
4. Review Master and Slave firmware together when changing communications or recording.
5. Check `git status --short` before editing shared work.

## 2. Setup and startup

Requirements: Windows PowerShell, Python, Node.js/npm, WSL `Ubuntu-22.04`, ROS 2 Humble, and OpenSim for IK work.

```powershell
.\scripts\setup_opensim_live_link.ps1
.\scripts\run_opensim_live_link.ps1 -Test
cd rehab-robotics-studio
npm install
```

For GUI-only work, set `VITE_DATA_SOURCE=mock`.

1. Power Master first, then Slave(s); close tools that occupy a serial/control port.
2. From the repository root, run:

   ```powershell
   .\scripts\start_stepesp_wireless.ps1
   ```

3. If known, bind stable device identities with `-ExpectedMasterDeviceId` and `-ExpectedSlaveDeviceId`.
4. In Studio, select `Run`.

Verify `/esp/status/pair` and `/esp/fleet/registry`. Both alias devices must be `connected`, `pair_available` must be true, and expected full-MAC IDs must be present.

To stop, end recording, select `Stop` in Studio, then run:

```powershell
.\scripts\stop_stepesp_wireless.ps1
```

## 3. Recording and connection loss

If host control disconnects during recording, ESP32 enters `host-disconnected-grace` and continues local SD recording. If control returns before expiry, it resumes normal recording. Expiry finalizes with `disconnect_timeout`; the Master relays `REC_STOP` to Slaves.

The current grace period is **90 seconds**, not three minutes:

| Setting | Location | Value |
| --- | --- | --- |
| Disconnect grace | `REC_RECONNECT_GRACE_MS` in both Master and Slave firmware | `90000UL` |
| SD flush interval | `SD_PERIODIC_FLUSH_MS` in both firmware files | `1000` ms |

Change both Master and Slave copies together.

## 4. Configuration and code map

| Change | Primary location | Also review |
| --- | --- | --- |
| Studio ROS URL/topics/services | `src/data/RosbridgeDataSource.ts` | backend publisher/service and tests |
| ROS service timeout | `SERVICE_TIMEOUT_MS` | current value: `10_000` ms |
| UI toast timeout | `components/common/Toast.tsx` | current value: `2500` ms |
| Block defaults and rate/range UI | `graph/blockDefinitions.ts` | `BlockNode.tsx`, `PropertiesPanel.tsx`, backend/firmware |
| Runtime/E-stop rules | `state/runtimeStore.ts` | Toolbar and systemStore |
| Sensor mapping | `MappingWorkspace.tsx` | mappingStore and `mapping_node.py` |
| OpenSim calibration/IK | `opensim_node.py`, `opensim/` | liveKneeAngle and HealthPanel |
| Fleet and identity | `fleet_bridge_node.py`, `esp32_bridge_node.py` | relay and firmware |
| Wi-Fi, host, relay ports | `start_stepesp_wireless.ps1` parameters | pass parameters before changing defaults |
| ESP network/SD/packets | Master/Slave `.ino` files | bridge, relay, firmware tests |

Current start-script defaults include Wi-Fi profile `iPhone (111)`, Master host `172.20.10.3`, control port `5000`, Studio port `5173`, and rosbridge port `9090`.

## 5. Essential ROS interfaces

| Interface | Purpose |
| --- | --- |
| `/esp/fleet/registry` | authoritative device inventory/readiness |
| `/esp/status/pair` | Master/Slave pair health |
| `/esp/raw/master`, `/esp/raw/slave` | Studio live inputs |
| `/esp32/master/imu`, `/esp32/slave/imu` | default OpenSim IMU input |
| `/opensim/status`, `/opensim/ik_status` | OpenSim status and reason |
| `/opensim/joint_states` | calibrated product joint output |
| `/rehab/model/catalog`, `/rehab/mapping/current` | model and mapping state |

## 6. Troubleshooting and logs

| Symptom | First check |
| --- | --- |
| Studio does not open | `logs/stepesp_gui.err.log`, port 5173 |
| Studio has no data | pair/registry topics, relay/fleet log |
| One Slave is missing | canonical identity inventory, not DHCP order |
| OpenSim or angle fails | `/opensim/status`, `/opensim/ik_status`, calibration/freshness |
| Restart is confused | run the stop script, then start once |

| Log | Location |
| --- | --- |
| Windows relay | `logs/stepesp_windows_relay.log` |
| Studio | `logs/stepesp_gui.log`, `logs/stepesp_gui.err.log` |
| Fleet bridge | `/home/justi/stepesp_fleet_bridge.log` |
| rosbridge | `/home/justi/stepesp_rosbridge.log` |
| OpenSim | `/home/justi/stepesp_opensim_bridge.log` |

## 7. Verification and handoff

```powershell
cd rehab-robotics-studio
npm run typecheck
npm test
npm run build
.\scripts\run_opensim_live_link.ps1 -Test
python scripts\acceptance_gate.py
```

Record the following at every handoff:

```text
Date / owner:
Purpose and scope:
Baseline commit / git status:
Network, Master IP, canonical Master/Slave IDs:
Firmware version and board revision:
Start command and parameters:
ROS domain, WSL distribution, OpenSim model/frames:
Pair, registry, Studio, IK, recording, and disconnect-grace results:
Errors, timestamps, relevant log paths, open work, and reproduction steps:
```

## 8. How to continue this project from scratch

Treat the system as five progressively harder layers. Do not begin with OpenSim or a full multi-device recording session.

### Stage 1 - Make the Studio predictable

Start the React application with mock data. Confirm that the Block Diagram, Front Panel, graph save/load behavior, runtime state transitions, and dashboard panels work without hardware. The useful boundaries are:

- `src/components/`: visual behavior only.
- `src/state/`: persistent UI/runtime ownership.
- `src/data/MockDataSource.ts`: safe simulated frames.
- `src/data/appDataSource.ts`: the deliberate switch between mock and live ROS data.

At this stage, add UI features and tests without needing an ESP32. Keep all physical-control commands behind `appDataSource`; do not let a component construct ROS messages itself.

### Stage 2 - Bring up one device safely

Use one Master and verify the TCP/UDP path, identity response, ROS bridge topics, and Studio rosbridge connection. Record the full MAC and never turn an IP address into the identity key. A successful ping is only evidence that a route exists; it is not proof that the expected physical board is connected.

Verify raw input first, then the typed IMU topic, then Studio. When this fails, inspect one boundary at a time: firmware, Windows relay, ROS publisher, rosbridge parser, and UI store.

### Stage 3 - Add the Slave and fleet behavior

Add one Slave only after the Master path is stable. Verify `/esp/fleet/registry`, compatibility aliases, pair health, and separate canonical MAC identities. Then test reconnect behavior: power-cycle only the Slave while the Master remains streaming and confirm that the canonical stream and assignment reappear.

Do not promote dynamic fleet mode to the default until every section in `hardware-acceptance-report.md` has real hardware evidence. That gate is currently open; its rows are not a completed validation record.

### Stage 4 - Add recording resilience

Run a normal record/stop cycle before intentionally disconnecting the host. Then test a controlled host-control loss during recording. Confirm that the device reports the grace state, local SD counts continue, reconnection returns to recording, and a missed deadline finalizes cleanly. Inspect both Master and Slave SD output.

### Stage 5 - Add OpenSim and calibration

First run `run_opensim_live_link.ps1 -Test` without hardware. Then connect real IMUs, verify status topics, open the native visualizer, calibrate the standing reference pose, and finally check the official joint-state output. Do not substitute a raw relative quaternion angle for the calibrated IK value.

## 9. Development history: problems encountered and lessons learned

This section records evidence available in the repository. It distinguishes resolved software defects from validation that still requires physical hardware.

### 9.1 GUI rate looked changed but the ESP32 stayed near 100 Hz - resolved

**Observed behavior:** changing Pair Rate in the Block Diagram could display a new number while the Front Panel continued to observe about 100 Hz. No visible error was produced.

**Root cause:** the generic Properties panel called only `graphStore.updateParam`. It changed the browser graph document but did not call the existing ROS parameter service, so no `FREQ:<hz>` command reached either ESP32.

**Fix:** rate commits now use `setHardwareSampleRate` / `setHardwareImuControl`, which requests `/esp_bridge_master/set_parameters`. Requested and effective rate values update only after acknowledgement; a rejected request restores the prior displayed value.

**Evidence:** the browser regression `rehab-robotics-studio/scripts/frequency-panel-regression.mjs` asserts the exact service request for 400 Hz, verifies acknowledgement, then verifies rollback after a rejected 500 Hz request. Recorded hardware observations after the fix were approximately 394-397 Hz on Master and 393-399 Hz on Slave for a configured 400 Hz rate.

**Lesson:** a UI value is not an applied hardware value. Every physical control needs an acknowledgement path, failure UI, and a regression test at the UI-to-transport boundary.

### 9.2 Long 500 Hz runs produced backwards Slave timestamps - fixed in source, hardware revalidation pending

**Observed behavior:** a 15-minute 500 Hz DIO test had zero queue drops but very poor synchronization: 46.408 ms mean absolute skew, 98.875 ms p95, 99.995 ms maximum skew, and a negative Slave inter-edge interval.

**Root cause:** every received ESP-NOW clock packet directly replaced the Slave offset. One-way packet delay jitter therefore became a timestamp jump. The 64-bit offset was also written in an ESP-NOW callback and read by the acquisition loop without synchronization on a 32-bit MCU, allowing a torn read.

**Fix:** firmware now requires five startup samples, selects the least-delayed starting observation, rejects offset observations more than 2 ms from the estimate, slews accepted corrections by at most 100 microseconds, and snapshots the shared clock state in a critical section.

**Current status:** topology tests passed and both XIAO ESP32-S3 sketches compiled. Flash both boards and repeat the 15-minute capture before declaring the timing requirement closed.

**Lesson:** average sampling rate and queue-drop counts can look healthy while timestamp integrity is broken. Test monotonicity and long-run edge skew directly.

### 9.3 DIO interrupt timestamping is implemented; long-run 2 ms acceptance is still open

The polling diagnosis was acted on. Both Master and Slave now attach `dioEdgeIsr` to D0/GPIO1 with `CHANGE`, capture `esp_timer_get_time()` and level inside an ISR, queue the event, and publish it from foreground code after safe synchronization. The queue capacity is 16, ISR/foreground access is protected, and the topology tests assert this design.

The implementation improved short-run behavior: the 60-second 500 Hz ISR smoke capture measured 1.680 ms mean absolute skew, 1.783 ms p95, and 1.795 ms maximum skew - within the 2 ms maximum criterion.

However, do not call the **15-minute acceptance requirement** closed yet. The latest 900-second ISR capture measured 1.708 ms mean absolute skew and 1.809 ms p95, but a 14.364 ms maximum outlier. It therefore failed the strict 2 ms maximum rule despite matching edge counts and zero queue drops. The next owner should preserve the ISR design, investigate the long-run outlier (including debounce, interrupt queue/overrun telemetry, clock correction, and pairing logic), and rerun the 900-second test.

### 9.4 Network topology changed during development - operational caution

Older material describes a `STEP_ESP32` Soft AP at `192.168.4.1`. The current start script defaults to an iPhone hotspot profile and Master host `172.20.10.3`, while firmware still supports its Soft-AP configuration. This is why the start script and its passed parameters are the operational source of truth. Do not copy an old IP example into a deployment without checking the active hardware topology.

### 9.5 Mapping and OpenSim needed explicit safety contracts

The project evolved from role-based two-sensor assumptions toward stable MAC-based fleet identities, model-derived frame catalogs, persisted mappings, and a calibration-gated IK output. This prevents a changing DHCP route or role alias from silently becoming a different physical sensor assignment.

The critical contract is: no product `JointState` publication when calibration is missing, capturing, failed, stale, invalid, or missing a usable source timestamp. Preserve this fail-closed behavior when extending IK or adding sensor counts.

## 10. Practical roadmap for the next owner

1. **Stabilize evidence first.** Flash the latest clock-correction firmware and rerun the 15-minute 500 Hz DIO test. Record raw logs, rates, skew, drops, and final status in the handoff.
2. **Close the DIO timing acceptance gap.** The interrupt capture is already implemented; diagnose the rare long-run outlier and rerun the 900-second test until the strict 2 ms maximum passes.
3. **Complete the acceptance gate.** Perform each real-hardware section of `hardware-acceptance-report.md`: identify safety, continuity, recording reconnect, radio load, OpenSim latency, and legacy/fleet aliases.
4. **Keep API boundaries aligned.** For every new firmware control, add backend validation, rosbridge handling, Studio acknowledgement/rollback behavior, and an automated test.
5. **Only then expand the fleet.** Add sensors one by one, keep canonical identities and model mapping explicit, and test reconnect under load at each fleet size.
6. **Document every measured change.** Put test date, firmware hash/version, board IDs, network topology, command line, measurement method, and raw log path beside every claimed result.

## 11. Hardware wiring and electrical bring-up

This section is intentionally conservative. It records the pin definitions that the current firmware compiles with; it is not permission to connect an unknown breakout board to power. Before applying power, confirm the exact sensor and SD breakout pin labels in their vendor documentation, use a shared ground, and keep all ESP32 signal levels at 3.3 V. Do not assume a module is 5 V-tolerant.

### 11.1 Minimum system topology

```text
          3.3 V / GND                 Wi-Fi / ESP-NOW
  ICM IMU -------- XIAO Master <--------------------> XIAO Slave -------- ICM IMU
                 |       ^                  DIO shared trigger          |       ^
                 |       |                                                |       |
              microSD    +---------------- trigger source ----------------+    microSD
                 |
     TCP control :5000 / UDP frames :55001
                 |
     Windows relay + WSL ROS 2, or a Jetson ROS 2 host (Section 12)
```

The Master and Slave are separate physical nodes. Do not swap their firmware or copy their IMU pin maps blindly: their compiled pin assignments differ.

### 11.2 IMU SPI wiring - current firmware definitions

Connect the sensor's SPI labels to the matching firmware signal name, not to a guessed XIAO pin name. `SDO` is normally the sensor's MISO output; `SDI` is normally the sensor's MOSI input. The final column is the value currently compiled into the stated sketch.

| Sensor signal | Master: `firmware/step_node/step_node.ino` | Slave: `firmware/step_node_slave/step_node_slave.ino` |
| --- | --- | --- |
| SCK / SCL | `PIN_SPI_SCK = D6` (GPIO4) | `PIN_SPI_SCK = D3` (GPIO4) |
| SDO / MISO | `PIN_SPI_MISO = D4` (GPIO6) | `PIN_SPI_MISO = D5` (GPIO6) |
| SDI / MOSI | `PIN_SPI_MOSI = D5` (GPIO2) | `PIN_SPI_MOSI = D1` (GPIO2) |
| CS / NCS | `PIN_ICM_CS = D3` (GPIO5) | `PIN_ICM_CS = D4` (GPIO5) |
| INT / DIO | `PIN_DIO = D0` (GPIO1) | `PIN_DIO = D0` (GPIO1) |
| Power | board-specific 3.3 V supply and GND | board-specific 3.3 V supply and GND |

**Required verification before a test:** the Master sketch contains nearby diagnostic/comment text that does not consistently match these compiled `#define` lines. Treat the `#define PIN_*` values as the source code authority, then boot each board and confirm the IMU `WHO_AM_I` check succeeds before relying on streaming data. If the physical harness was assembled to a different map, update the relevant `PIN_*` definitions and recompile - do not change only a comment or diagnostic message.

### 11.3 DIO trigger wiring

Each board configures D0/GPIO1 as `INPUT_PULLUP` and captures both edges through `attachInterrupt(..., CHANGE)`. Wire the external trigger output to **both** boards' DIO input, and connect the trigger source ground to both ESP32 grounds. Use a 3.3 V-compatible, clean digital signal. Do not connect a 5 V trigger directly to GPIO1.

Bring-up sequence:

1. With the IMUs disconnected from the trigger, boot both nodes and confirm the initial DIO level in serial output.
2. Connect the shared trigger and observe one rising/falling pair at a low rate.
3. Confirm both streams report matching DIO transitions before running at 500 Hz.
4. Run the 60-second ISR smoke test, then the 900-second test. The short test has met the 2 ms maximum criterion; the long test still has a 14.364 ms maximum outlier (Section 9.3).

### 11.4 microSD wiring and recording constraints

The firmware enables SD support and calls `SD.begin(PIN_SD_CS, SPI, 25000000)` with `PIN_SD_CS = 21` in both sketches. Thus only the chip-select pin is unambiguously defined by this project. The remaining SD SPI pin routing depends on the XIAO board/core SPI mapping and the physical SD breakout. Verify that routing against the exact board revision and breakout documentation before making a wiring diagram or changing hardware.

After wiring, perform a short recording, stop it normally, and inspect the card. Then repeat using the 90-second host-disconnected grace behavior described in Section 3. Never diagnose recording resilience from a GUI status alone; confirm that the SD file is finalized and readable.

### 11.5 Radio and network prerequisites

Master/Slave synchronization uses ESP-NOW. Both sketches currently compile `ESPNOW_WIFI_CHANNEL` as `6`; the active Wi-Fi/channel arrangement must be compatible with that setting. The host connection is a different link: TCP control uses port `5000` and live UDP frames use port `55001`. Do not expose those services to an untrusted public network, and do not store Wi-Fi credentials in documentation or commits.

## 12. Jetson integration: merged deployment guidance

Jetson can replace the Windows relay/WSL ROS host for direct device acquisition, or it can act as an additional ROS 2 sensor computer for EMG and load-cell hardware. It should not be treated as an ESP32 peripheral: its primary connection to the ESP fleet is network-based.

### 12.1 Choose one topology deliberately

| Topology | Use it when | Data path |
| --- | --- | --- |
| Existing Windows + WSL path | preserving the current tested desktop workflow | ESP32 -> UDP `55001` -> Windows relay -> WSL ROS 2 -> rosbridge `9090` -> Studio |
| Direct Jetson ESP path | deploying a standalone Linux acquisition host | ESP32 -> UDP `55001` -> Jetson ROS 2 bridge -> rosbridge `9090` -> Studio |
| Jetson auxiliary sensors | adding EMG or load cells while keeping the existing ESP path | ESP IMU path plus Jetson acquisition nodes -> common ROS graph -> Studio |

For the direct Jetson path, put the Jetson and both ESP32s on the same trusted 2.4 GHz Wi-Fi/hotspot. The Jetson opens TCP control connections to each device on port `5000` and binds one UDP receiver on `55001`; distinguish incoming sensors by source identity, then translate them into the canonical full-MAC device IDs. ESP-NOW remains an on-device Master-to-Slave synchronization/control mechanism, not a Jetson control bus.

### 12.2 Jetson software checklist

1. Install a supported ROS 2 distribution (the current project uses Humble) and the vendor driver/SDK for each added acquisition device.
2. Run `rosbridge_websocket` on port `9090` if Studio runs on another computer; set compatible `ROS_DOMAIN_ID`, Jetson IP, and firewall rules.
3. Port or run the ESP fleet bridge only after validating the exact 50-byte UDP protocol against the current firmware. Do not silently change field order or byte order.
4. Start the Jetson bridge, verify the fleet registry and pair health, then connect Studio using the Jetson rosbridge URL.
5. Preserve the existing safety contract: `/opensim/joint_states` remains calibration-gated; a new host must not bypass it.

### 12.3 ESP UDP protocol contract for a Jetson bridge

The network frame is fixed at 50 bytes and little-endian. It contains a 22-byte header (`<iiHiii`) followed by fourteen signed 16-bit values (`<14h`). The header holds the boot-time microsecond low 32 bits, payload length, bit-depth enum, element size, channel count, and samples-per-channel. It contains **no network sequence number**; use device identity, source metadata, timestamp checks, and any recording sequence separately.

The fourteen payload channels are accelerometer XYZ, gyroscope XYZ, magnetometer XYZ, quaternion WXYZ, and DIO state/edge. Preserve units and scaling in one explicit decoder; do not make the GUI infer raw units. Before declaring a Jetson decoder complete, compare its values with the current Windows/ROS stream from the same physical device.

### 12.4 EMG and load-cell integration pattern

Do not pack EMG or load-cell samples into the ESP's fixed 50-byte IMU packet. Give each acquisition device a Jetson ROS 2 node and a common message contract including `device_id`, monotonic `timestamp_ns` captured at acquisition, `sequence`, configured and observed sample rate, channel names, values, and health/drop state.

Suggested topic family:

```text
/sensors/emg/<device-id>/raw
/sensors/emg/<device-id>/envelope
/sensors/load_cell/<device-id>/raw
/sensors/load_cell/<device-id>/calibrated
/sensors/<device-id>/status
```

For EMG, retain raw microvolt-scale data, then publish filtered/rectified/envelope views separately. For a load cell, retain ADC counts as well as tare- and calibration-transformed force/torque values so calibration can be repeated without losing raw evidence. Record full-rate data on Jetson or in a ROS bag; publish decimated data to Studio so the browser stays responsive.

Exact EMG electrode, amplifier, ADC, load-cell bridge, and excitation wiring cannot be safely derived from this repository because the hardware models and vendor pinouts are not recorded here. Add those model-specific diagrams only after identifying the exact acquisition board. At minimum, use the vendor-required supply/reference wiring, a common ground where required by that interface, strain relief, and the vendor's isolation/safety requirements for any human-connected EMG equipment.

### 12.5 Time alignment, acceptance, and operational handoff

Timestamp at the source: ESP firmware timestamps its DIO/IMU path, while each Jetson acquisition node must timestamp at sampling rather than browser arrival. For coarse alignment, preserve sequence numbers and record clock-offset metadata. For precision multi-modal studies, use a shared trigger, hardware synchronization, or a documented clock-offset method; software arrival time is not adequate proof of synchronization.

Before deployment, demonstrate all of the following together: Master and Slave identities remain stable after reconnect; pair and registry status recover; Jetson and Studio show the same expected streams; recording survives the documented disconnect window; EMG/load-cell calibration metadata is saved; Studio does not lock up at full acquisition rate; and the long 500 Hz DIO acceptance criterion is rerun. Record the Jetson image/ROS version, device driver version, network topology, topic names, calibration files, and measured results in the Section 7 handoff template.
