# Rehab Robotics - Commissioning Record and Build Evidence

## Purpose

This is the controlled, fill-in record that turns the three handoff guides into a reproducible physical build. Complete it on the actual bench. Do not enter Wi-Fi passwords, API keys, private IPs that identify a person, or patient/participant data. Store secrets in the approved secret manager and write only the reference name below.

**Build identifier:** `________________________`  
**Owner:** `________________________`  
**Date:** `________________________`  
**Repository commit:** `________________________`  
**Git status captured:** `Yes / No`  
**Reason for build / change scope:** `________________________________________________`

## 1. Bill of materials and provenance

| Item | Manufacturer / exact part number | Board revision | Quantity | Supplier/reference | Verified by |
| --- | --- | --- | --- | --- | --- |
| Master MCU | Seeed XIAO ESP32S3 or exact replacement | | 1 | | |
| Slave MCU | Seeed XIAO ESP32S3 or exact replacement | | 1+ | | |
| IMU module | ICM-20948-compatible module; exact breakout required | | 1 per node | | |
| microSD breakout/card | exact module/card, capacity, format | | 1 per node | | |
| DIO trigger source | exact make/model/output level | | 1 | | |
| USB-C data cable | exact cable/length | | 2+ | | |
| Power source | exact make/model/rating | | | | |
| Jetson (if used) | exact module/carrier/storage | | | | |
| EMG hardware (if used) | exact amplifier/ADC/electrodes | | | | |
| Load-cell hardware (if used) | exact cell/bridge/ADC/excitation | | | | |

Attach purchase references and photographs. If an entry is unknown, mark the system **not reproducible** rather than guessing.

## 2. Physical assembly evidence

| Assembly | Required attachment | File/link | Checked by / date |
| --- | --- | --- | --- |
| Master | top, bottom, connector-side photos with Master label visible | | |
| Slave | top, bottom, connector-side photos with Slave label visible | | |
| Trigger harness | source/output/ground and both DIO endpoints visible | | |
| SD harness | breakout/card and every routed pin visible | | |
| Jetson/network | Jetson, adapter/hotspot, and connection topology photo | | |

### Continuity-checked harness table

For every row, verify continuity power **off**. The expected MCU side comes from the current source; the sensor-side label must match its vendor manual.

| Role | Harness signal | MCU endpoint | Peripheral endpoint | Meter result | Checked by/date |
| --- | --- | --- | --- | --- | --- |
| Master | SCK | D6 / GPIO4 | | PASS / FAIL | |
| Master | MISO/SDO | D4 / GPIO6 | | PASS / FAIL | |
| Master | MOSI/SDI | D5 / GPIO2 | | PASS / FAIL | |
| Master | CS/NCS | D3 / GPIO5 | | PASS / FAIL | |
| Master | DIO/INT | D0 / GPIO1 | | PASS / FAIL | |
| Slave | SCK | D3 / GPIO4 | | PASS / FAIL | |
| Slave | MISO/SDO | D5 / GPIO6 | | PASS / FAIL | |
| Slave | MOSI/SDI | D1 / GPIO2 | | PASS / FAIL | |
| Slave | CS/NCS | D4 / GPIO5 | | PASS / FAIL | |
| Slave | DIO/INT | D0 / GPIO1 | | PASS / FAIL | |
| Both | trigger ground | common ground | trigger source ground | PASS / FAIL | |

## 3. Software, firmware, and network baseline

| Component | Exact version/value | Evidence file/link |
| --- | --- | --- |
| Windows version | | |
| WSL distro/version | | |
| Python and Node.js/npm | | |
| Arduino IDE | | |
| ESP32 board package and XIAO target name | | |
| USB serial driver | | |
| ROS 2 / OpenSim | | |
| Jetson image / Ubuntu / ROS / drivers (if used) | | |
| Master sketch commit and firmware version | | |
| Slave sketch commit and firmware version | | |
| Master canonical device ID | | |
| Slave canonical device ID(s) | | |
| Wi-Fi SSID/channel/addressing policy | no secret; link secret-manager item | |
| Firewall ports/rules | TCP 5000, UDP 55001, rosbridge 9090 as applicable | |

## 4. Commissioning sequence and evidence

| Step | Pass criterion | Result / evidence | Owner/date |
| --- | --- | --- | --- |
| Master firmware flash | uploads to labelled Master; serial role is Master | | |
| Slave firmware flash | uploads to labelled Slave; serial role is Slave | | |
| IMU identification | both boot logs show `WHO_AM_I=0xEA` / ICM OK | | |
| SD ready | each node reports ready; card visible/readable after test | | |
| DIO low-rate test | both nodes see matching edge sequence | | |
| DIO 60 s / 500 Hz | command output saved; maximum skew <= 2 ms | | |
| Network identity | `IDENTITY?` responses saved; full MACs recorded | | |
| ROS registry/pair | both connected; pair available | | |
| Studio live view | expected streams/graphs visible | | |
| Record/stop | SD data is finalized/readable | | |
| Disconnect grace | reconnect and expiry behavior recorded | | |
| OpenSim calibration | `CALIBRATED` and valid joint state demonstrated | | |
| Jetson parity (if used) | decoder/topics match baseline values | | |

## 5. Long-run acceptance and deviations

| Test | Command/method | Target | Measured result | Raw log / owner/date |
| --- | --- | --- | --- | --- |
| DIO 900 s / 500 Hz | `test_dio_sync_serial.py` | max skew <= 2 ms | | |
| Fleet continuity | 60 s at target rate per device | measured rate/drop count | | |
| Reconnect under load | power-cycle one Slave | canonical stream returns | | |
| SD recording reconnect | record through disconnect/reconnect | valid final files | | |
| OpenSim latency | 1000 frames | mean/p99 recorded | | |

**Open deviations / risk accepted by:** `_______________________________________________`

**Reproduction result:** `REPRODUCIBLE / NOT REPRODUCIBLE`  
**Commissioning sign-off (owner/date):** `_____________________________________`
