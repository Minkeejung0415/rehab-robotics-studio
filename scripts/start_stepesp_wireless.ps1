param(
  [string]$Distro = 'Ubuntu-22.04',
  [string]$MasterHost = '192.168.4.1',
  [int]$MasterPort = 5000,
  [string]$SlaveHost = 'auto',
  [int]$SlavePort = 5000,
  [int]$UdpPort = 55001,
  [int]$RelayPort = 5002,
  [int]$SlaveRelayPort = 5003,
  [string]$RosInstall = '/home/justi/.rehab-install-v12',
  [string]$OpenSimInstall = '/home/justi/rehab_robotics_ws/install',
  [string]$OpenSimEnvironment = '/home/justi/.micromamba/envs/rehab-opensim',
  [string]$OpenSimModel = '/home/justi/rehab_robotics_ws/opensim_quaternion_demo.osim',
  [int]$RosDomainId = 0,
  [string]$DiagnosticPort = 'COM3',
  [string]$WifiProfile = 'STEP_ESP32',
  [string]$InternetProfile = 'ubcsecure',
  [string]$WifiInterface = 'Wi-Fi',
  [switch]$SkipGui,
  [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$relayScript = Join-Path $workspace 'scripts\stepesp_tcp_udp_relay.py'
$serialDrainScript = Join-Path $workspace 'scripts\stepesp_serial_drain.py'
$bridgeLog = '/home/justi/stepesp_master_bridge.log'
$slaveBridgeLog = '/home/justi/stepesp_slave_bridge.log'
$rosbridgeLog = '/home/justi/stepesp_rosbridge.log'
$observerLog = '/home/justi/stepesp_processing_observer.log'
$openSimLog = '/home/justi/stepesp_opensim_bridge.log'
$relayLog = Join-Path $workspace 'logs\stepesp_windows_relay.log'
$relayErrorLog = Join-Path $workspace 'logs\stepesp_windows_relay.err.log'
$serialLog = Join-Path $workspace 'logs\stepesp_master_serial.log'
$serialErrorLog = Join-Path $workspace 'logs\stepesp_master_serial.err.log'
$guiRoot = Join-Path $workspace 'rehab-robotics-studio'
$guiLog = Join-Path $workspace 'logs\stepesp_gui.log'
$guiErrorLog = Join-Path $workspace 'logs\stepesp_gui.err.log'
$openSimSetupScript = Join-Path $workspace 'scripts\setup_opensim_live_link.ps1'
$openSimRunner = '/home/justi/rehab_robotics_ws/run_opensim_live_link_wsl.sh'

if ((wsl -d $Distro -- bash -lc "test -f '$RosInstall/setup.bash'; echo `$?").Trim() -ne '0') {
  throw "ROS install not found at $RosInstall inside $Distro. Build the backend before starting wireless mode."
}

$rosReadiness = (wsl -d $Distro -- bash -lc "source /opt/ros/humble/setup.bash; source '$RosInstall/setup.bash'; ros2 pkg prefix rehab_robotics_interfaces >/dev/null 2>&1 && ros2 pkg executables rehab_robotics_bridge | grep -q processing_block_observer && ros2 pkg executables rosbridge_server | grep -q rosbridge_websocket; echo `$?").Trim()
if ($rosReadiness -ne '0') {
  throw "The ROS install is missing rehab_robotics_interfaces, processing_block_observer, or rosbridge_websocket. Rebuild the v12 workspace before starting wireless mode."
}

# Install/build the OpenSim overlay before switching to the offline ESP access
# point. Subsequent starts only perform the fast readiness check.
$openSimReadinessCommand = "test -f '$OpenSimInstall/setup.bash' && test -x '$OpenSimEnvironment/bin/python' && test -f '$OpenSimModel' && test -f '$openSimRunner'; echo `$?"
$openSimReady = (wsl -d $Distro -- bash -lc $openSimReadinessCommand).Trim()
if ($openSimReady -ne '0') {
  if (-not (Test-Path -LiteralPath $openSimSetupScript)) {
    throw "OpenSim setup script is missing: $openSimSetupScript"
  }
  Write-Host 'OpenSim live link is not ready. Running its one-time setup before connecting to STEP_ESP32...'
  & $openSimSetupScript
  if ($LASTEXITCODE -ne 0) {
    throw "OpenSim live-link setup failed with exit code $LASTEXITCODE."
  }
}

$openSimReadiness = (wsl -d $Distro -- bash -lc "source /opt/ros/humble/setup.bash; source '$RosInstall/setup.bash'; source '$OpenSimInstall/setup.bash'; test -f '$OpenSimModel' && ros2 pkg executables rehab_robotics_bridge | grep -q opensim_bridge; echo `$?").Trim()
if ($openSimReadiness -ne '0') {
  throw "OpenSim overlay, demo model, or opensim_bridge executable is unavailable after setup."
}

if (-not $SkipGui) {
  if (-not (Test-Path -LiteralPath (Join-Path $guiRoot 'node_modules'))) {
    throw "GUI dependencies are missing at $guiRoot\node_modules. Connect to the internet and run npm install once before STEP_ESP32 mode."
  }
  if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'npm.cmd is not available. Install Node.js before starting the GUI.'
  }
}

# The ESP access point intentionally has no internet. Prevent Windows from
# preferring the campus profile during an acquisition session, connect to the
# ESP profile, and wait until the association is actually complete.
netsh wlan set profileparameter name="$InternetProfile" connectionmode=manual | Out-Null
netsh wlan set profileparameter name="$WifiProfile" connectionmode=auto autoswitch=no | Out-Null
netsh wlan set profileorder name="$WifiProfile" interface="$WifiInterface" priority=1 | Out-Null
netsh wlan connect name="$WifiProfile" interface="$WifiInterface" | Out-Null

$wifiConnected = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
  Start-Sleep -Seconds 1
  $interfaceState = netsh wlan show interfaces
  if ($interfaceState -match "SSID\s+:\s+$([regex]::Escape($WifiProfile))\s*") {
    $wifiConnected = $true
    break
  }
}

if (-not $wifiConnected) {
  netsh wlan set profileparameter name="$WifiProfile" connectionmode=manual | Out-Null
  netsh wlan set profileparameter name="$InternetProfile" connectionmode=auto | Out-Null
  netsh wlan connect name="$InternetProfile" interface="$WifiInterface" | Out-Null
  throw "Could not connect to STEP_ESP32. Check that the master is powered and its access point is visible."
}

$wifiAddress = Get-NetIPAddress -InterfaceAlias $WifiInterface -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { $_.IPAddress -like '192.168.4.*' } |
  Select-Object -First 1 -ExpandProperty IPAddress
if (-not $wifiAddress) {
  throw "STEP_ESP32 is associated, but $WifiInterface has no 192.168.4.x address."
}

$resolvedSlaveHost = $SlaveHost
if ($SlaveHost -eq 'auto') {
  # DHCP assignment order is not stable: the laptop may receive .2 before the
  # slave joins. Find the other responding station instead of assuming .2.
  $responsiveStations = @()
  for ($attempt = 0; $attempt -lt 15 -and $responsiveStations.Count -eq 0; $attempt++) {
    $responsiveStations = @(
      2..10 |
        ForEach-Object { "192.168.4.$_" } |
        Where-Object { $_ -ne $wifiAddress -and $_ -ne $MasterHost } |
        Where-Object {
          & ping.exe -n 1 -w 150 $_ | Out-Null
          $LASTEXITCODE -eq 0
        }
    )
    if ($responsiveStations.Count -eq 0) { Start-Sleep -Seconds 1 }
  }
  if ($responsiveStations.Count -eq 0) {
    throw "Could not discover the slave on STEP_ESP32. Power the slave, wait for it to join, then retry or pass -SlaveHost 192.168.4.x."
  }
  if ($responsiveStations.Count -gt 1) {
    throw "Multiple STEP_ESP32 stations responded ($($responsiveStations -join ', ')). Retry with the slave address explicitly: -SlaveHost 192.168.4.x."
  }
  $resolvedSlaveHost = $responsiveStations[0]
}
if ($resolvedSlaveHost -eq $wifiAddress) {
  throw "SlaveHost $resolvedSlaveHost is this Windows laptop, not the slave. Use -SlaveHost with the slave's actual STEP_ESP32 address."
}

Write-Host "STEP_ESP32 addresses: master=$MasterHost, slave=$resolvedSlaveHost, Windows=$wifiAddress"

New-Item -ItemType Directory -Path (Split-Path -Parent $relayLog) -Force | Out-Null

# Stop prior USB-backed or Wi-Fi ROS processes before launching this complete stack.
wsl -d $Distro -- bash -lc "pkill -f '[e]sp32_bridge_node' || true; pkill -f '[r]osbridge_websocket' || true; pkill -f '[p]rocessing_block_observer' || true; pkill -f '[o]pensim_live_link.launch.py' || true; pkill -f '[o]pensim_bridge' || true"
Get-CimInstance Win32_Process |
  Where-Object {
    $_.ProcessId -ne $PID -and $_.CommandLine -match 'serial_tcp_bridge.py|stepesp_tcp_udp_relay.py|stepesp_serial_drain.py'
  } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

if (-not $SkipGui) {
  $escapedGuiRoot = [regex]::Escape($guiRoot)
  Get-CimInstance Win32_Process |
    Where-Object {
      $_.ProcessId -ne $PID -and $_.CommandLine -match $escapedGuiRoot -and
      $_.CommandLine -match 'vite|npm(.cmd)?\s+run\s+(dev|preview)'
    } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
}

# Give the ESP TCP server time to observe the old relay's FIN and release its
# single active client before the replacement relay connects. Do not probe its
# TCP port here: even a reachability probe consumes that single-client slot.
Start-Sleep -Seconds 6

$wslGateway = (wsl -d $Distro -- bash -lc "ip route show default | cut -d' ' -f3").Trim()
if (-not $wslGateway) {
  throw 'Could not determine the Windows gateway address visible from WSL.'
}

$relayArgs = "`"$relayScript`" --esp-host $MasterHost --esp-port $MasterPort --udp-port $UdpPort --listen-port $RelayPort --slave-host $resolvedSlaveHost --slave-esp-port $SlavePort --slave-listen-port $SlaveRelayPort"
$availableSerialPorts = [System.IO.Ports.SerialPort]::GetPortNames()
if ($DiagnosticPort -and $availableSerialPorts -contains $DiagnosticPort) {
  $serialArgs = "`"$serialDrainScript`" $DiagnosticPort"
  Start-Process -FilePath python.exe -ArgumentList $serialArgs -RedirectStandardOutput $serialLog -RedirectStandardError $serialErrorLog -WindowStyle Hidden
  Start-Sleep -Milliseconds 750
} else {
  Write-Warning "Diagnostic port $DiagnosticPort is not present; continuing in Wi-Fi-only mode."
}
Start-Process -FilePath python.exe -ArgumentList $relayArgs -RedirectStandardOutput $relayLog -RedirectStandardError $relayErrorLog -WindowStyle Hidden
Start-Sleep -Milliseconds 750

$rosEnvironment = "export ROS_DOMAIN_ID=$RosDomainId; source /opt/ros/humble/setup.bash; source $RosInstall/setup.bash"
$master = "$rosEnvironment; exec ros2 run rehab_robotics_bridge esp32_bridge_node --ros-args -r __node:=esp_master -p node_id:=master -p host:=$wslGateway -p port:=$RelayPort -p transport:=tcp -p body_segment:=femur_r_imu -p recording_control_mode:=active > $bridgeLog 2>&1"
$slave = "$rosEnvironment; exec ros2 run rehab_robotics_bridge esp32_bridge_node --ros-args -r __node:=esp_slave -p node_id:=slave -p host:=$wslGateway -p port:=$SlaveRelayPort -p transport:=tcp -p body_segment:=tibia_r_imu -p recording_control_mode:=active > $slaveBridgeLog 2>&1"
$rosbridge = "$rosEnvironment; exec ros2 run rosbridge_server rosbridge_websocket --ros-args -p port:=9090 -p address:=0.0.0.0 > $rosbridgeLog 2>&1"
$observer = "$rosEnvironment; exec ros2 run rehab_robotics_bridge processing_block_observer > $observerLog 2>&1"
$openSim = "export ROS_DOMAIN_ID=$RosDomainId; exec bash $openSimRunner $OpenSimModel false master_imu_topic:=/esp32/master/imu slave_imu_topic:=/esp32/slave/imu > $openSimLog 2>&1"

Start-Process -FilePath wsl.exe -ArgumentList '-d', $Distro, '--', 'bash', '-lc', $master -WindowStyle Hidden
Start-Process -FilePath wsl.exe -ArgumentList '-d', $Distro, '--', 'bash', '-lc', $slave -WindowStyle Hidden
Start-Process -FilePath wsl.exe -ArgumentList '-d', $Distro, '--', 'bash', '-lc', $rosbridge -WindowStyle Hidden
Start-Process -FilePath wsl.exe -ArgumentList '-d', $Distro, '--', 'bash', '-lc', $observer -WindowStyle Hidden
Start-Process -FilePath wsl.exe -ArgumentList '-d', $Distro, '--', 'bash', '-lc', $openSim -WindowStyle Hidden

$rosbridgeReady = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
  Start-Sleep -Milliseconds 500
  if (Test-NetConnection -ComputerName 127.0.0.1 -Port 9090 -InformationLevel Quiet -WarningAction SilentlyContinue) {
    $rosbridgeReady = $true
    break
  }
}
if (-not $rosbridgeReady) {
  throw "rosbridge did not open port 9090. Check $rosbridgeLog inside WSL."
}

if (-not $SkipGui) {
  # Vite dev mode cannot reliably resolve source URLs when this workspace path
  # contains '#'. Build first and serve dist so the existing folder name works.
  $guiCommand = 'set VITE_DATA_SOURCE=rosbridge&& set VITE_ROSBRIDGE_URL=ws://127.0.0.1:9090&& set VITE_ESP_RAW_TOPIC=/esp/raw/master&& set VITE_ESP_SLAVE_TOPIC=/esp/raw/slave&& npm.cmd run build&& npm.cmd run preview -- --host 127.0.0.1 --port 5173 --strictPort'
  Start-Process -FilePath cmd.exe -ArgumentList '/c', $guiCommand -WorkingDirectory $guiRoot -RedirectStandardOutput $guiLog -RedirectStandardError $guiErrorLog -WindowStyle Hidden

  $guiReady = $false
  for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 500
    try {
      $response = Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 1
      if ($response.StatusCode -eq 200) {
        $guiReady = $true
        break
      }
    } catch { }
  }
  if (-not $guiReady) {
    throw "GUI did not open port 5173. Check $guiErrorLog."
  }
  if (-not $NoBrowser) {
    Start-Process 'http://127.0.0.1:5173'
  }
}

Write-Host "Started the complete STEP_ESP32 stack: dual-device Windows relay, master/slave ROS bridges, OpenSim live link, rosbridge, processing observer$(if (-not $SkipGui) { ', and GUI' })."
Write-Host "ROS domain: $RosDomainId"
Write-Host "GUI: http://127.0.0.1:5173"
Write-Host "rosbridge: ws://127.0.0.1:9090"
Write-Host "Verify pair: source $RosInstall/setup.bash; ROS_DOMAIN_ID=$RosDomainId ros2 topic echo /esp/status/pair --once --field data"
Write-Host "Verify deployment topics: source $RosInstall/setup.bash; ROS_DOMAIN_ID=$RosDomainId ros2 topic list | grep processing_blocks"
Write-Host "Bridge log: $bridgeLog (kept after you return to ubcsecure)"
Write-Host "Slave bridge log: $slaveBridgeLog"
Write-Host "rosbridge log: $rosbridgeLog"
Write-Host "observer log: $observerLog"
Write-Host "OpenSim status: source $OpenSimInstall/setup.bash; ROS_DOMAIN_ID=$RosDomainId ros2 topic echo /opensim/status --once --full-length"
Write-Host "OpenSim log: $openSimLog"
Write-Host "Relay log: $relayLog"
if ($DiagnosticPort -and $availableSerialPorts -contains $DiagnosticPort) { Write-Host "USB diagnostic log: $serialLog" }
if (-not $SkipGui) { Write-Host "GUI logs: $guiLog and $guiErrorLog" }
Write-Host "Stay on $WifiProfile while acquiring. Restore normal Wi-Fi with: .\scripts\stop_stepesp_wireless.ps1"
