# STEP_ESP32 Wireless Setup

This mode replaces the USB serial bridge with a direct connection to the
ESP32 master. One PowerShell command starts the complete local application:
the Windows relay, WSL master and slave ROS bridges, rosbridge on port `9090`,
processing block observer, OpenSim quaternion subscriber, and Vite GUI on port
`5173`. The Windows relay owns the master ESP TCP control connection plus every
verified slave route (up to the firmware peer slot limit of 6) and shared UDP
port `55001`. It separates master (`192.168.4.1`) and slave datagrams by source
IP and forwards them to WSL listen ports `5002`, `5003`, `5004`, … Contiguous
slave listen ports start at `SlaveRelayPort` (default `5003`). This is required
because the ESP Soft AP cannot route UDP packets to WSL's private NAT address.

1. Power the master first, then the slave(s). Confirm the master has created the
   `STEP_ESP32` access point.
2. From the repository root in PowerShell, run:

   ```powershell
   .\scripts\start_stepesp_wireless.ps1
   ```

   The script temporarily disables automatic connection to `ubcsecure`, joins
   `STEP_ESP32`, and starts the complete stack against the master at
   `192.168.4.1:5000`. It opens `http://127.0.0.1:5173` after rosbridge and the
   GUI are ready. Windows showing **No internet** is expected. Do not manually
   return to `ubcsecure` while acquiring.

   This is also the only command required for the OpenSim live link. On its
   first run, the script installs/builds missing OpenSim components before
   leaving the internet-connected network. It then subscribes to
   `/esp32/master/imu` and `/esp32/slave/imu` automatically.

   A USB connection is optional in this mode. If the configured diagnostic
   port (default `COM3`) is absent, the script skips serial diagnostics and
   continues with the Wi-Fi data/control path.

   Every verified slave self-identity on the Soft AP is routed automatically
   (capped at 6). STEP_ESP32 DHCP assignment order is not fixed, so the laptop
   may receive `192.168.4.2` while slaves receive later addresses. Discovery
   never selects by ping order — only verified `record=self` identities bind
   routes. To filter the set, pass one or more canonical IDs:

   ```powershell
   .\scripts\start_stepesp_wireless.ps1 -ExpectedSlaveDeviceIds esp32:112233445566,esp32:77bbccddeeff
   .\scripts\start_stepesp_wireless.ps1 -ExpectedSlaveDeviceId esp32:112233445566
   .\scripts\start_stepesp_wireless.ps1 -SlaveHost 192.168.4.3
   ```

   Duplicate MAC discovery or more than six verified slaves fails closed.
   Transitional ROS still launches one master bridge and one slave bridge for
   the first selected identity; the relay itself receives every selected slave
   via repeatable `--slave-route HOST:LISTEN_PORT:EXPECTED_DEVICE_ID` args.
3. Verify the master/slave pair connection:

   ```powershell
   wsl -d Ubuntu-22.04 -- bash -lc "source /opt/ros/humble/setup.bash; source /home/justi/.rehab-install-v12/setup.bash; ros2 topic echo /esp/status/pair --once --field data"
   ```

   Confirm that `master.connection_state` and `slave.connection_state` are
   `connected` and `pair_available` is `true`. The two live GUI inputs are
   `/esp/raw/master` and `/esp/raw/slave`.

4. In the browser opened by the script, press `Run` and confirm that the master
   IMU values and graph move. Draft and final processing messages use the same
   local rosbridge and are visible on `/processing_blocks/draft` and
   `/processing_blocks/update`.

5. When acquisition is finished, stop the wireless processes and restore
   normal automatic Wi-Fi with:

   ```powershell
   .\scripts\stop_stepesp_wireless.ps1
   ```

The logs remain available after returning:

```powershell
wsl -d Ubuntu-22.04 -- bash -lc "tail -80 /home/justi/stepesp_master_bridge.log"
wsl -d Ubuntu-22.04 -- bash -lc "tail -80 /home/justi/stepesp_slave_bridge.log"
wsl -d Ubuntu-22.04 -- bash -lc "tail -80 /home/justi/stepesp_rosbridge.log"
wsl -d Ubuntu-22.04 -- bash -lc "tail -80 /home/justi/stepesp_processing_observer.log"
wsl -d Ubuntu-22.04 -- bash -lc "tail -80 /home/justi/stepesp_opensim_bridge.log"
```

## One-page OpenSim IK operator checklist

Use this fixed sequence for a wireless standing-calibration and live-angle run.
The Studio browser only calls the bounded ROS service
`/opensim/visualizer/open` (`std_srvs/Trigger`); it never runs a shell command
or launches WSL/OpenSim itself.

1. **Start the complete stack.** Power the master, then the slave, and run this
   from the repository root in PowerShell:

   ```powershell
   .\scripts\start_stepesp_wireless.ps1
   ```

   Wait for Studio to open at `http://127.0.0.1:5173`. Remaining on the
   `STEP_ESP32` network with **No internet** is expected.

2. **Confirm both devices and the three OpenSim contracts.**

   ```powershell
   wsl -d Ubuntu-22.04 -- bash -lc "source /opt/ros/humble/setup.bash; source /home/justi/.rehab-install-v12/setup.bash; ros2 topic echo /esp/status/pair --once --field data"
   wsl -d Ubuntu-22.04 -- bash -lc "source /opt/ros/humble/setup.bash; source /home/justi/.rehab-install-v12/setup.bash; ros2 topic list | grep -E '^/opensim/(status|ik_status|joint_states)$'"
   ```

   Continue only when both connection states are `connected`,
   `pair_available` is `true`, and all three OpenSim topics are listed.

3. **Connect Studio and request the visualizer.** Select `Run`, then select
   `Open visualizer`. HealthPanel must advance from `Opening…` to `Open`.
   `Unavailable` or `Failed` is not a reason to stop IK: read the persistent
   reason, correct the runtime problem, and select `Open visualizer` again.

4. **Capture the standing reference.** Stand still with knees extended, select
   `Calibrate`, and hold the pose until HealthPanel reports
   `Calibration state: CALIBRATED`. Do not use an angle while calibration is
   `UNCALIBRATED`, `CAPTURING`, or `FAILED`.

5. **Verify the official live angle.** Confirm `IK solution: Valid`, then move
   the knee gently. The `Knee` value in **Front Panel**, the
   **Joint Angle Display** in **Block Diagram**, and `OpenSim knee angle` in
   HealthPanel must agree in degrees. A valid straight-knee result is
   `180.0 deg` and decreases with flexion; missing, invalid, or data older than
   2 seconds must show `—` and
   `Waiting for calibrated IK`, never a fabricated or retained zero.

6. **Recover without bypassing the safety gates.**

   - `JointState stale`: restore the ESP/rosbridge connection and wait for a
     fresh `/opensim/joint_states`; do not clear the warning or reuse the old
     number.
   - `IK invalid`: return to the standing pose and inspect the IK/calibration
     reason. Recalibrate only when the sensors are stable.
   - `3D visualizer Failed/Unavailable`: inspect the bridge log, restore the
     Simbody runtime, and retry the same toolbar button. IK and recording may
     continue while the optional native window is unavailable.

   ```powershell
   wsl -d Ubuntu-22.04 -- bash -lc "tail -80 /home/justi/stepesp_opensim_bridge.log"
   wsl -d Ubuntu-22.04 -- bash -lc "source /opt/ros/humble/setup.bash; source /home/justi/.rehab-install-v12/setup.bash; ros2 topic echo /opensim/status --once --field data"
   wsl -d Ubuntu-22.04 -- bash -lc "source /opt/ros/humble/setup.bash; source /home/justi/.rehab-install-v12/setup.bash; ros2 topic echo /opensim/ik_status --once --field data"
   ```

7. **Stop cleanly.** Stop any active recording in Studio, select `Stop`, then
   restore normal Wi-Fi and terminate the managed processes:

   ```powershell
   .\scripts\stop_stepesp_wireless.ps1
   ```

**`human_needed` native-window boundary:** setup installs a matching Simbody 3.8
visualizer under `~/.local/libexec/simbody`, and automated QA verifies the open
service plus its `available=true`, `state=open` status. A human must still
confirm that the native window is visibly rendered, updates during calibrated
IK, and reopens on retry without stopping IK or recording.

## One-shot 250 Hz hardware verification

The bounded verifier captures only the active Wi-Fi profile name (never a
profile key), starts the existing wireless stack, applies and acknowledges
both GUI rate fields, stress-remounts the diagram, records the master
configured/effective/observed rates, stops the stack, and attempts to restore
the captured profile in a `finally` block.

Run its local safety checks and non-mutating preflight first:

```powershell
.\scripts\verify_stepesp_frequency.ps1 -SelfTest
.\scripts\verify_stepesp_frequency.ps1 -DryRun
```

With the master and slave powered, run the one-shot verification:

```powershell
.\scripts\verify_stepesp_frequency.ps1
```

It is bounded to four minutes by default. The machine-readable result always
uses this deterministic path:

```text
logs\stepesp_frequency_verification.json
```

An exit code of zero and top-level `"ok": true` mean the GUI retained 250 Hz,
both hardware controls acknowledged it, the configured/effective values were
250 Hz, the observed master stream was within the documented tolerance, the
pair was connected, and normal Wi-Fi was restored. A failed or timed-out stage
is recorded with its local stdout/stderr log paths.

## Why ubcsecure cannot be used for acquisition

The ESP master creates its own isolated Wi-Fi access point. Its fixed address
`192.168.4.1` exists only on the `STEP_ESP32` network; the master is not a
station on `ubcsecure` and campus routing does not provide a path to that
private subnet. A laptop with one Wi-Fi adapter can be associated with
`STEP_ESP32` or `ubcsecure`, but not both at the same time. Automatic
reconnection to `ubcsecure` therefore breaks the ESP TCP/UDP session, which is
why the start script temporarily changes the campus profile to manual mode.

The GUI still works without internet because it, rosbridge, and ROS all run on
the same computer. Internet access is only needed beforehand to install npm or
system packages.

The master continues to relay acquisition controls and recording commands to
the slave over ESP-NOW, so both SD cards can record as a synchronized pair.
ESP-NOW is a board-to-board control/synchronization link; the laptop does not
receive it as a normal IP stream. Live IMU samples therefore still travel over
each board's Wi-Fi TCP/UDP endpoint. The Windows relay now demultiplexes those
two live streams before exposing both IMUs to the GUI.
