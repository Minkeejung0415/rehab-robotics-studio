# STEP_ESP32 Wireless Setup

This mode replaces the USB serial bridge with a direct connection to the
ESP32 master. One PowerShell command starts the complete local application:
the Windows relay, WSL master and slave ROS bridges, rosbridge on port `9090`,
processing block observer, OpenSim quaternion subscriber, and Vite GUI on port
`5173`. The Windows relay owns both ESP TCP control connections and shared UDP
port `55001`. It separates master (`192.168.4.1`) and slave
(`192.168.4.2`) datagrams by source IP and forwards them to WSL ports `5002`
and `5003`. This is required because the ESP Soft AP cannot route UDP packets
to WSL's private NAT address.

1. Power the master first, then the slave. Confirm the master has created the
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

   The slave address is discovered automatically. STEP_ESP32 DHCP assignment
   order is not fixed, so the laptop may receive `192.168.4.2` and the slave
   may receive `192.168.4.3`. To override discovery, pass the actual address:

   ```powershell
   .\scripts\start_stepesp_wireless.ps1 -SlaveHost 192.168.4.3
   ```
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
