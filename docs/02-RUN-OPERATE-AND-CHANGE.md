# Rehab Robotics - Run, Operate, and Change Guide

## Purpose and scope

Use this guide for normal startup, shutdown, recording, safe configuration changes, and first-line troubleshooting. Setup and wiring are in `01-SETUP-WIRING-AND-JETSON.md`. Repository ownership and historical problems are in `03-PROJECT-MAP-AND-LESSONS.md`.

## 1. Normal startup

1. Power Master, then Slave(s). Close any application holding the serial/control port.
2. Start the wireless stack from the repository root:

   ```powershell
   .\scripts\start_stepesp_wireless.ps1
   ```

3. Where known, pass `-ExpectedMasterDeviceId` and `-ExpectedSlaveDeviceId` using full canonical MAC identities.
4. Open Studio and select `Run`.

Verify `/esp/status/pair` and `/esp/fleet/registry` before treating a session as ready. Alias devices must be `connected`, `pair_available` must be true, and the expected full MAC IDs must be present. Current start-script defaults include Wi-Fi profile `iPhone (111)`, Master host `172.20.10.3`, control port `5000`, Studio port `5173`, and rosbridge port `9090`; treat script parameters, not old screenshots, as the live operational authority.

For GUI-only work, use `VITE_DATA_SOURCE=mock` rather than issuing hardware commands.

## 2. Normal shutdown

End recording first, select `Stop` in Studio, then run:

```powershell
.\scripts\stop_stepesp_wireless.ps1
```

Avoid starting a second stack before the first one is stopped. Confused restarts frequently leave a stale port owner or an old relay process running.

## 3. Recording and host-disconnect behavior

During recording, a lost host control connection puts an ESP32 into `host-disconnected-grace`: local SD recording continues. Reconnection before expiry returns it to normal recording. Expiry finalizes with `disconnect_timeout`; the Master relays `REC_STOP` to Slaves.

| Setting | Location | Current value |
| --- | --- | --- |
| Disconnect grace | `REC_RECONNECT_GRACE_MS` in both Master and Slave sketches | `90000UL` = 90 seconds |
| SD periodic flush | `SD_PERIODIC_FLUSH_MS` in both sketches | `1000` ms |

Change Master and Slave together. Test normal record/stop, reconnect inside the grace period, and expiry outside it. A GUI status is not enough: inspect the resulting SD file and confirm it is finalized/readable.

## 4. Where to make a change

| Desired change | Primary location | Also review |
| --- | --- | --- |
| Studio ROS URL/topics/services | `rehab-robotics-studio/src/data/RosbridgeDataSource.ts` | backend publisher/service and tests |
| ROS service timeout | `SERVICE_TIMEOUT_MS` | current value: `10_000` ms |
| Toast visibility | `components/common/Toast.tsx` | current value: `2500` ms |
| Block defaults, rate/range UI | `graph/blockDefinitions.ts` | `BlockNode.tsx`, `PropertiesPanel.tsx`, backend/firmware |
| Runtime/E-stop rules | `state/runtimeStore.ts` | Toolbar and `systemStore` |
| Sensor mapping | `MappingWorkspace.tsx` | `mappingStore`, `mapping_node.py` |
| OpenSim calibration/IK | `opensim_node.py`, `opensim/` | live angle and Health Panel |
| Fleet identity/control | `fleet_bridge_node.py`, `esp32_bridge_node.py` | relay, firmware, tests |
| Wi-Fi/host/ports | `scripts/start_stepesp_wireless.ps1` | pass parameters before changing defaults |
| ESP network/SD/packet behavior | Master/Slave `.ino` files | bridge, relay, firmware tests |

The product knee-angle output is `/opensim/joint_states`; `/opensim/joint_angle` is debug-only. Do not publish or consume a product angle unless calibration is `CALIBRATED` and IK is valid.

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

## 6. Troubleshooting order

| Symptom | First check |
| --- | --- |
| Studio does not open | `logs/stepesp_gui.err.log`, port `5173` |
| Studio has no data | pair/registry topics, relay/fleet log |
| One Slave is missing | canonical identity inventory, not DHCP ordering |
| OpenSim or angle fails | `/opensim/status`, `/opensim/ik_status`, calibration/freshness |
| Restart is confused | stop script, then one clean start |

| Log | Location |
| --- | --- |
| Windows relay | `logs/stepesp_windows_relay.log` |
| Studio | `logs/stepesp_gui.log`, `logs/stepesp_gui.err.log` |
| Fleet bridge | `/home/justi/stepesp_fleet_bridge.log` |
| rosbridge | `/home/justi/stepesp_rosbridge.log` |
| OpenSim | `/home/justi/stepesp_opensim_bridge.log` |

When a path fails, inspect one boundary at a time: firmware, network/relay, ROS publisher, rosbridge, then Studio store. A ping only proves routing; it does not prove the expected board identity or valid sensor payload.

## 7. Verification and handoff record

```powershell
cd rehab-robotics-studio
npm run typecheck
npm test
npm run build
.\scripts\run_opensim_live_link.ps1 -Test
python scripts\acceptance_gate.py
```

At every handoff record: date/owner; scope; baseline commit and `git status`; network and canonical board IDs; board/firmware revision; exact startup command; ROS/WSL/OpenSim configuration; pair/registry/Studio/IK/recording results; log paths and timestamps; open work and reproduction steps.
