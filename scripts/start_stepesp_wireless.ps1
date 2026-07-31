param(
  [string]$Distro = 'Ubuntu-22.04',
  [string]$MasterHost = '192.168.4.1',
  [int]$MasterPort = 5000,
  [string]$ExpectedMasterDeviceId = '',
  [string]$SlaveHost = 'auto',
  [int]$SlavePort = 5000,
  [string]$ExpectedSlaveDeviceId = '',
  [string[]]$ExpectedSlaveDeviceIds = @(),
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
  [string]$InternetProfile = 'ubcvisitor',
  [string]$WifiInterface = 'Wi-Fi',
  [switch]$SkipGui,
  [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
# Firmware peer inventory capacity; relay CLI enforces the same cap.
$MAX_SLAVE_ROUTES = 6

function ConvertTo-StepEspCanonicalId {
  param(
    [Parameter(Mandatory = $true)]
    [string]$DeviceId,
    [string]$Label = 'device identity'
  )

  if ($DeviceId -notmatch '^esp32:[0-9a-fA-F]{12}$') {
    throw "$Label must use the exact canonical form esp32:aabbccddeeff."
  }
  return $DeviceId.ToLowerInvariant()
}

function ConvertTo-StepEspMacId {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Mac,
    [string]$Label
  )

  if ($Mac -notmatch '^(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$') {
    throw "$Label is not a complete six-byte MAC."
  }
  return "esp32:$($Mac.Replace(':', '').ToLowerInvariant())"
}

function ConvertFrom-StepEspControlFields {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Line
  )

  if ($Line.Length -gt 768) {
    throw 'Identity response line exceeds the 768-byte bound.'
  }
  $parts = @($Line.Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries))
  if ($parts.Count -eq 0) {
    throw 'Identity response contained an empty line.'
  }
  $fields = @{}
  for ($index = 1; $index -lt $parts.Count; $index++) {
    if ($parts[$index] -notmatch '^([A-Za-z_][A-Za-z0-9_]*)=([A-Za-z0-9_.:,/@+\-]+)$') {
      throw "Malformed identity field: $($parts[$index])"
    }
    if ($fields.ContainsKey($Matches[1])) {
      throw "Duplicate identity field: $($Matches[1])"
    }
    $fields[$Matches[1]] = $Matches[2]
  }
  return [pscustomobject]@{
    Prefix = $parts[0]
    Fields = $fields
  }
}

function Get-StepEspIdentity {
  param(
    [Parameter(Mandatory = $true)]
    [string]$HostAddress,
    [Parameter(Mandatory = $true)]
    [int]$Port,
    [int]$TimeoutMs = 5000
  )

  $client = [System.Net.Sockets.TcpClient]::new()
  try {
    $connect = $client.ConnectAsync($HostAddress, $Port)
    if (-not $connect.Wait([Math]::Min($TimeoutMs, 2000))) {
      throw "Timed out connecting to identity endpoint $HostAddress`:$Port."
    }
    if ($connect.IsFaulted) {
      throw $connect.Exception.GetBaseException()
    }

    $stream = $client.GetStream()
    $stream.ReadTimeout = 250
    $stream.WriteTimeout = 1000
    $request = [System.Text.Encoding]::ASCII.GetBytes("IDENTITY?`n")
    $stream.Write($request, 0, $request.Length)
    $stream.Flush()

    $buffer = [byte[]]::new(4096)
    $text = [System.Text.StringBuilder]::new()
    $rawResponse = [System.Text.StringBuilder]::new()
    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMs)
    $receivedBytes = 0
    $selfFields = $null
    $advertisedPeerCount = -1
    $peers = [System.Collections.Generic.List[string]]::new()

    while ([DateTime]::UtcNow -lt $deadline) {
      try {
        $count = $stream.Read($buffer, 0, $buffer.Length)
      } catch [System.IO.IOException] {
        continue
      }
      if ($count -eq 0) {
        break
      }
      $receivedBytes += $count
      if ($receivedBytes -gt 16384) {
        throw "Identity response from $HostAddress exceeds the 16384-byte bound."
      }
      $chunk = [System.Text.Encoding]::ASCII.GetString($buffer, 0, $count)
      [void]$rawResponse.Append($chunk)
      [void]$text.Append($chunk)

      while (($newline = $text.ToString().IndexOf("`n", [StringComparison]::Ordinal)) -ge 0) {
        $line = $text.ToString(0, $newline).TrimEnd("`r")
        [void]$text.Remove(0, $newline + 1)

        if (($line.StartsWith('IDENTITY_PEER ') -or $line.StartsWith('IDENTITY_END ')) -and -not $selfFields) {
          throw "Identity inventory from $HostAddress placed peer/end before record=self."
        }

        if ($line.StartsWith('IDENTITY_OK ')) {
          if ($selfFields) {
            throw "Identity inventory from $HostAddress contains duplicate record=self."
          }
          $parsed = ConvertFrom-StepEspControlFields -Line $line
          $selfFields = $parsed.Fields
          if (
            $parsed.Prefix -ne 'IDENTITY_OK' -or
            $selfFields.protocol -ne 'id-v1' -or
            $selfFields.record -ne 'self' -or
            $selfFields.verified -ne '1'
          ) {
            throw "Identity self row must be IDENTITY_OK protocol=id-v1 record=self verified=1."
          }
          $canonicalSelf = ConvertTo-StepEspCanonicalId -DeviceId $selfFields.device_id -Label "Identity from $HostAddress"
          if (
            (ConvertTo-StepEspMacId -Mac $selfFields.display_mac -Label 'display_mac') -ne $canonicalSelf -or
            (ConvertTo-StepEspMacId -Mac $selfFields.base_mac -Label 'base_mac') -ne $canonicalSelf
          ) {
            throw "Identity MAC metadata from $HostAddress does not match its device_id."
          }
          $parsedCount = 0
          if (
            -not [int]::TryParse($selfFields.peer_count, [ref]$parsedCount) -or
            $parsedCount -lt 0 -or
            $parsedCount -gt 64
          ) {
            throw "Identity peer_count from $HostAddress is invalid."
          }
          $advertisedPeerCount = $parsedCount
          continue
        }

        if ($selfFields -and $line.StartsWith('IDENTITY_PEER ')) {
          if ($peers.Count -ge $advertisedPeerCount) {
            throw "Identity inventory from $HostAddress exceeds its advertised peer_count."
          }
          $parsed = ConvertFrom-StepEspControlFields -Line $line
          $peerFields = $parsed.Fields
          if (
            $parsed.Prefix -ne 'IDENTITY_PEER' -or
            $peerFields.protocol -ne 'id-v1' -or
            $peerFields.record -ne 'peer' -or
            $peerFields.verified -notin @('0', '1')
          ) {
            throw "Identity peer row must be IDENTITY_PEER protocol=id-v1 record=peer."
          }
          if ($peerFields.verified -eq '1') {
            $peerId = ConvertTo-StepEspCanonicalId -DeviceId $peerFields.device_id -Label 'Peer identity'
          } elseif ($peerFields.device_id -eq 'unknown') {
            $peerId = "unverified:$($peerFields.transport_mac)"
          } else {
            throw 'Unverified peer must report device_id=unknown.'
          }
          if ($peers.Contains($peerId)) {
            throw "Identity inventory from $HostAddress contains a duplicate peer."
          }
          [void]$peers.Add($peerId)
          continue
        }

        if ($selfFields -and $line.StartsWith('IDENTITY_END ')) {
          $parsed = ConvertFrom-StepEspControlFields -Line $line
          $endFields = $parsed.Fields
          $endCount = -1
          if (
            $parsed.Prefix -ne 'IDENTITY_END' -or
            $endFields.protocol -ne 'id-v1' -or
            -not [int]::TryParse($endFields.peer_count, [ref]$endCount) -or
            $endCount -ne $advertisedPeerCount -or
            $peers.Count -ne $advertisedPeerCount
          ) {
            throw "Identity terminator from $HostAddress does not match peer_count."
          }
          return [pscustomobject]@{
            Host = $HostAddress
            DeviceId = $canonicalSelf
            Role = $selfFields.role
            PeerIds = @($peers)
          }
        }

        if ($selfFields) {
          throw "Identity inventory from $HostAddress was interrupted before IDENTITY_END."
        }
      }
    }
    $receivedPreview = $rawResponse.ToString()
    if ($receivedPreview.Length -gt 500) {
      $receivedPreview = $receivedPreview.Substring(0, 500)
    }
    $receivedPreview = $receivedPreview.Replace("`r`n", "\n").Replace("`n", "\n").Replace("`r", "\n")
    throw "Endpoint $HostAddress did not return a complete IDENTITY_OK/IDENTITY_PEER/IDENTITY_END inventory. Received: $receivedPreview"
  } finally {
    $client.Dispose()
  }
}

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

$expectedMasterCanonical = if ($ExpectedMasterDeviceId) {
  ConvertTo-StepEspCanonicalId -DeviceId $ExpectedMasterDeviceId -Label 'Expected Master identity'
} else {
  $null
}
$expectedSlaveFilterIds = [System.Collections.Generic.List[string]]::new()
if ($ExpectedSlaveDeviceIds -and $ExpectedSlaveDeviceIds.Count -gt 0) {
  foreach ($rawId in $ExpectedSlaveDeviceIds) {
    if (-not [string]::IsNullOrWhiteSpace($rawId)) {
      $expectedSlaveFilterIds.Add(
        (ConvertTo-StepEspCanonicalId -DeviceId $rawId -Label 'Expected Slave identity')
      )
    }
  }
}
if ($ExpectedSlaveDeviceId) {
  $singular = ConvertTo-StepEspCanonicalId -DeviceId $ExpectedSlaveDeviceId -Label 'Expected Slave identity'
  if (-not $expectedSlaveFilterIds.Contains($singular)) {
    $expectedSlaveFilterIds.Add($singular)
  }
}
$expectedSlaveCanonical = if ($expectedSlaveFilterIds.Count -eq 1) {
  $expectedSlaveFilterIds[0]
} else {
  $null
}

$candidateSlaveHosts = @()
if ($SlaveHost -eq 'auto') {
  # Ping only discovers candidate routes. It never selects device identity.
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
  $candidateSlaveHosts = @($responsiveStations | Sort-Object -Unique)
} else {
  $candidateSlaveHosts = @($SlaveHost)
}
if ($candidateSlaveHosts -contains $wifiAddress) {
  throw "SlaveHost includes this Windows laptop ($wifiAddress), not a slave endpoint."
}

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

# Give each ESP TCP server time to observe the old relay's FIN and release its
# single active client before the bounded identity probes connect.
Start-Sleep -Seconds 6

$masterIdentity = Get-StepEspIdentity -HostAddress $MasterHost -Port $MasterPort
if ($masterIdentity.Role -ne 'master') {
  throw "Master route $MasterHost reported role=$($masterIdentity.Role), not master."
}
if ($expectedMasterCanonical -and $masterIdentity.DeviceId -ne $expectedMasterCanonical) {
  throw "Master route $MasterHost reported $($masterIdentity.DeviceId), expected $expectedMasterCanonical."
}
$verifiedMasterDeviceId = $masterIdentity.DeviceId

$slaveIdentityProbes = @()
foreach ($candidateHost in $candidateSlaveHosts) {
  try {
    $probe = Get-StepEspIdentity -HostAddress $candidateHost -Port $SlavePort
    if ($probe.Role -ne 'slave') {
      Write-Warning "Ignoring candidate $candidateHost because its verified self role is $($probe.Role), not slave."
      continue
    }
    $slaveIdentityProbes += $probe
  } catch {
    Write-Warning "Identity probe rejected candidate $candidateHost`: $($_.Exception.Message)"
  }
}

$verifiedSlaveCandidates = @($slaveIdentityProbes)
if ($expectedSlaveFilterIds.Count -gt 0) {
  $verifiedSlaveCandidates = @($slaveIdentityProbes | Where-Object {
    $expectedSlaveFilterIds.Contains($_.DeviceId)
  })
}
$discoveredSelfIds = @(
  $slaveIdentityProbes |
    Sort-Object -Property DeviceId, Host |
    ForEach-Object { "$($_.DeviceId)@$($_.Host)" }
)
if ($verifiedSlaveCandidates.Count -eq 0) {
  $discovered = if ($discoveredSelfIds.Count) {
    $discoveredSelfIds -join ', '
  } else {
    'none'
  }
  throw "No verified Slave self identity matched. Discovered verified self identities: $discovered"
}
if ($verifiedSlaveCandidates.Count -gt $MAX_SLAVE_ROUTES) {
  throw "Discovered $($verifiedSlaveCandidates.Count) verified slaves; exceeds the firmware peer slot limit ($MAX_SLAVE_ROUTES). Discovered verified self identities: $($discoveredSelfIds -join ', ')."
}

$seenSlaveIds = @{}
foreach ($candidate in $verifiedSlaveCandidates) {
  if ($candidate.DeviceId -eq $verifiedMasterDeviceId) {
    throw "Master and Slave routes reported the same self identity $verifiedMasterDeviceId."
  }
  if ($seenSlaveIds.ContainsKey($candidate.DeviceId)) {
    throw "duplicate slave identity $($candidate.DeviceId) discovered on $($seenSlaveIds[$candidate.DeviceId]) and $($candidate.Host)."
  }
  $seenSlaveIds[$candidate.DeviceId] = $candidate.Host
}

$selectedSlaves = @(
  $verifiedSlaveCandidates |
    Sort-Object -Property DeviceId, Host
)
$selectedSlave = $selectedSlaves[0]
$resolvedSlaveHost = $selectedSlave.Host
$verifiedSlaveDeviceId = $selectedSlave.DeviceId

$slaveRouteSummaries = @(
  for ($index = 0; $index -lt $selectedSlaves.Count; $index++) {
    $route = $selectedSlaves[$index]
    $listenPort = $SlaveRelayPort + $index
    "$($route.DeviceId)@$($route.Host):$listenPort"
  }
)
Write-Host "STEP_ESP32 routes: master=$MasterHost ($verifiedMasterDeviceId), slaves=$($slaveRouteSummaries -join ', '), Windows=$wifiAddress"

# The short-lived identity probe closes before the relay takes ownership.
Start-Sleep -Seconds 2

$wslGateway = (wsl -d $Distro -- bash -lc "ip route show default | cut -d' ' -f3").Trim()
if (-not $wslGateway) {
  throw 'Could not determine the Windows gateway address visible from WSL.'
}

$relayArgList = [System.Collections.Generic.List[string]]::new()
$relayArgList.AddRange([string[]]@(
  $relayScript,
  '--esp-host', $MasterHost,
  '--esp-port', "$MasterPort",
  '--expected-device-id', $verifiedMasterDeviceId,
  '--udp-port', "$UdpPort",
  '--listen-port', "$RelayPort",
  '--slave-esp-port', "$SlavePort"
))
for ($index = 0; $index -lt $selectedSlaves.Count; $index++) {
  $route = $selectedSlaves[$index]
  $listenPort = $SlaveRelayPort + $index
  $relayArgList.Add('--slave-route')
  $relayArgList.Add("$($route.Host):${listenPort}:$($route.DeviceId)")
}
$relayArgs = ($relayArgList | ForEach-Object {
  if ($_ -match '\s') { '"{0}"' -f $_ } else { $_ }
}) -join ' '
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

$rosEnvironment = "export ROS_DOMAIN_ID=$RosDomainId; source /opt/ros/humble/setup.bash; source $RosInstall/setup.bash; source $OpenSimInstall/setup.bash"
$master = "$rosEnvironment; exec ros2 run rehab_robotics_bridge esp32_bridge_node --ros-args -r __node:=esp_bridge_master -p node_id:=master -p expected_device_id:=$verifiedMasterDeviceId -p host:=$wslGateway -p port:=$RelayPort -p transport:=tcp -p body_segment:=femur_r_imu -p recording_control_mode:=active > $bridgeLog 2>&1"
$slave = "$rosEnvironment; exec ros2 run rehab_robotics_bridge esp32_bridge_node --ros-args -r __node:=esp_bridge_slave -p node_id:=slave -p expected_device_id:=$verifiedSlaveDeviceId -p host:=$wslGateway -p port:=$SlaveRelayPort -p transport:=tcp -p body_segment:=tibia_r_imu -p recording_control_mode:=active > $slaveBridgeLog 2>&1"
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
Write-Host "Bridge log: $bridgeLog (kept after you return to ubcvisitor)"
Write-Host "Slave bridge log: $slaveBridgeLog"
Write-Host "rosbridge log: $rosbridgeLog"
Write-Host "observer log: $observerLog"
Write-Host "OpenSim status: source $OpenSimInstall/setup.bash; ROS_DOMAIN_ID=$RosDomainId ros2 topic echo /opensim/status --once --full-length"
Write-Host "OpenSim log: $openSimLog"
Write-Host "Relay log: $relayLog"
if ($DiagnosticPort -and $availableSerialPorts -contains $DiagnosticPort) { Write-Host "USB diagnostic log: $serialLog" }
if (-not $SkipGui) { Write-Host "GUI logs: $guiLog and $guiErrorLog" }
Write-Host "Stay on $WifiProfile while acquiring. Restore normal Wi-Fi with: .\scripts\stop_stepesp_wireless.ps1"
