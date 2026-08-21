param(
  [string]$Distro = 'Ubuntu-22.04',
  [string]$MasterHost = '172.20.10.3',
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
  [string]$WifiProfile = 'iPhone (111)',
  [string]$InternetProfile = 'ubcsecure',
  [string]$WifiInterface = 'Wi-Fi',
  [switch]$SkipGui,
  [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$launcherLock = $null
$launcherLockPath = Join-Path ([System.IO.Path]::GetTempPath()) 'rehab-stepesp-wireless-start.lock'
try {
  $launcherLock = [System.IO.File]::Open(
    $launcherLockPath,
    [System.IO.FileMode]::OpenOrCreate,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::None
  )
} catch [System.IO.IOException] {
  throw 'Another iPhone hotspot STEP ESP startup is already running.'
}

try {
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
    if (-not $connect.Wait($TimeoutMs)) {
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

function Get-StepEspCurrentSsid {
  $iface = netsh wlan show interfaces
  foreach ($line in $iface -split "`r?`n") {
    if ($line -match '^\s*SSID\s+:\s+(.+?)\s*$' -and $line -notmatch 'BSSID') {
      $value = $Matches[1].Trim()
      if ($value) { return $value }
    }
  }
  return ''
}

function Get-StepEspIpv4Like {
  param([Parameter(Mandatory = $true)][string]$Pattern)
  Get-NetIPAddress -InterfaceAlias $WifiInterface -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -like $Pattern } |
    Select-Object -First 1 -ExpandProperty IPAddress
}

function Disable-CampusWifiAutoconnect {
  foreach ($name in @($InternetProfile, 'ubcsecure', 'ubcvisitor')) {
    if (-not [string]::IsNullOrWhiteSpace($name)) {
      netsh wlan set profileparameter name="$name" connectionmode=manual 2>$null | Out-Null
    }
  }
}

function Lock-StepEspWifi {
  param([switch]$Quiet)
  Disable-CampusWifiAutoconnect
  netsh wlan set profileparameter name="$WifiProfile" connectionmode=auto autoswitch=no 2>$null | Out-Null
  netsh wlan set profileorder name="$WifiProfile" interface="$WifiInterface" priority=1 2>$null | Out-Null
  $ssid = Get-StepEspCurrentSsid
  $hotspot = Get-StepEspIpv4Like -Pattern '172.20.10.*'
  $ap = Get-StepEspIpv4Like -Pattern '192.168.4.*'
  if ($ssid -eq $WifiProfile -and ($hotspot -or $ap)) {
    if ($hotspot) { return $hotspot }
    return $ap
  }
  if (-not $Quiet) {
    Write-Host "Holding $WifiProfile (current SSID='$ssid'). Campus auto-connect is off."
  }
  netsh wlan connect name="$WifiProfile" interface="$WifiInterface" | Out-Null
  Start-Sleep -Seconds 2
  $hotspot = Get-StepEspIpv4Like -Pattern '172.20.10.*'
  if ($hotspot) { return $hotspot }
  return (Get-StepEspIpv4Like -Pattern '192.168.4.*')
}

function Repair-StepEspGuiDist {
  $htmlPath = Join-Path $guiRoot 'dist\index.html'
  $assets = Join-Path $guiRoot 'dist\assets'
  if (-not (Test-Path -LiteralPath $htmlPath) -or -not (Test-Path -LiteralPath $assets)) {
    return
  }
  $css = Get-ChildItem -LiteralPath $assets -Filter 'index-*.css' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if (-not $css) { return }
  $html = [IO.File]::ReadAllText($htmlPath)
  $wanted = '/assets/' + $css.Name
  if ($html -notlike "*$wanted*") {
    $html = [regex]::Replace($html, '/assets/index-[A-Za-z0-9_-]+\.css', $wanted)
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [IO.File]::WriteAllText($htmlPath, $html, $utf8)
    Write-Host "Repaired GUI stylesheet to $($css.Name)"
  }
}

function Test-StepEspCssReady {
  try {
    $html = (Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 2).Content
    if ($html -notmatch 'href="(/assets/index-[^"]+\.css)"') {
      return $false
    }
    $cssPath = $Matches[1]
    $css = Invoke-WebRequest -Uri "http://127.0.0.1:5173$cssPath" -UseBasicParsing -TimeoutSec 2
    $type = [string]$css.Headers['Content-Type']
    return ($type -like 'text/css*') -or ($css.Content.StartsWith('*{') -or $css.Content.Contains('.app-shell'))
  } catch {
    return $false
  }
}

function Stop-ArduinoSerialHolders {
  Get-Process -Name 'serial-monitor' -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
}

function Reset-StepEspOverUsb {
  param([string]$PortName)
  if ([string]::IsNullOrWhiteSpace($PortName)) {
    return
  }
  Stop-ArduinoSerialHolders
  Start-Sleep -Milliseconds 400
  $ports = [System.IO.Ports.SerialPort]::GetPortNames()
  if ($ports -notcontains $PortName) {
    Write-Warning "USB reset skipped: $PortName is not present."
    return
  }
  $port = $null
  try {
    $port = New-Object System.IO.Ports.SerialPort $PortName, 115200
    $port.DtrEnable = $true
    $port.RtsEnable = $false
    $port.Open()
    Start-Sleep -Milliseconds 600
    Write-Host "USB-reset $PortName (DTR) to recover IDENTITY."
  } catch {
    Write-Warning "USB reset of $PortName failed: $($_.Exception.Message)"
  } finally {
    if ($port) {
      try { if ($port.IsOpen) { $port.Close() } } catch { }
      $port.Dispose()
    }
  }
}

function Test-StepEspHttpReady {
  param([string]$Uri = 'http://127.0.0.1:5173')
  try {
    $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 2
    return ($response.StatusCode -eq 200)
  } catch {
    return $false
  }
}

function Test-StepEspTcpOpen {
  param(
    [string]$TargetHost = '127.0.0.1',
    [int]$Port,
    [int]$TimeoutMs = 400
  )
  $client = $null
  try {
    $client = [System.Net.Sockets.TcpClient]::new()
    $connect = $client.ConnectAsync($TargetHost, $Port)
    if (-not $connect.Wait($TimeoutMs)) {
      return $false
    }
    if ($connect.IsFaulted) {
      return $false
    }
    return $client.Connected
  } catch {
    return $false
  } finally {
    if ($client) { $client.Dispose() }
  }
}

function Wait-StepEspTcpState {
  param(
    [int[]]$Ports,
    [bool]$ShouldBeOpen,
    [int]$TimeoutSeconds = 20,
    [string]$TargetHost = '127.0.0.1'
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    $allMatch = $true
    foreach ($port in $Ports) {
      $open = Test-StepEspTcpOpen -TargetHost $TargetHost -Port $port
      if ($open -ne $ShouldBeOpen) {
        $allMatch = $false
        break
      }
    }
    if ($allMatch) {
      return $true
    }
    Start-Sleep -Milliseconds 250
  }
  return $false
}

function Test-StepEspIcmp {
  param([string]$HostAddress)
  # iPhone hotspot clients can answer ARP/ICMP more slowly immediately after
  # association; 400 ms incorrectly rejected a healthy slave at .2.
  & ping.exe -n 1 -w 1000 $HostAddress | Out-Null
  return ($LASTEXITCODE -eq 0)
}

function Invoke-StepEspIdentityUntilReady {
  param(
    [Parameter(Mandatory = $true)][string]$HostAddress,
    [Parameter(Mandatory = $true)][int]$Port,
    [string]$ExpectedRole = '',
    [int]$MaxAttempts = 80
  )

  $lastError = $null
  for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    try {
      Write-Host "Identity probe $attempt/$MaxAttempts -> ${HostAddress}:${Port}"
      $identity = Get-StepEspIdentity -HostAddress $HostAddress -Port $Port -TimeoutMs 8000
      if ($ExpectedRole -and $identity.Role -ne $ExpectedRole) {
        throw "role=$($identity.Role), expected $ExpectedRole"
      }
      return $identity
    } catch {
      $lastError = $_
      Write-Warning $_.Exception.Message
      [void](Lock-StepEspWifi -Quiet)
      if ($DiagnosticPort -and (($attempt % 5) -eq 0)) {
        Reset-StepEspOverUsb -PortName $DiagnosticPort
        Start-Sleep -Seconds 8
      } else {
        Start-Sleep -Seconds 10
      }
    }
  }
  $detail = if ($lastError) { $lastError.Exception.Message } else { 'no response' }
  throw "Identity never succeeded for ${HostAddress}:${Port} after $MaxAttempts attempts. Last error: $detail"
}

$workspace = Split-Path -Parent $PSScriptRoot
$backendRootWin = Join-Path $workspace 'backend'
$backendRootWsl = (wsl -d $Distro -- wslpath -a $backendRootWin).Trim()
if (-not $backendRootWsl) {
  throw 'Could not resolve the backend source path inside WSL.'
}
$relayScript = Join-Path $workspace 'scripts\stepesp_tcp_udp_relay.py'
$serialDrainScript = Join-Path $workspace 'scripts\stepesp_serial_drain.py'
$bridgeLog = '/home/justi/stepesp_fleet_bridge.log'
$rosbridgeLog = '/home/justi/stepesp_rosbridge.log'
$observerLog = '/home/justi/stepesp_processing_observer.log'
$openSimLog = '/home/justi/stepesp_opensim_bridge.log'
$modelCatalogLog = '/home/justi/stepesp_model_catalog.log'
$mappingLog = '/home/justi/stepesp_mapping.log'
$relayLog = Join-Path $workspace 'logs\stepesp_windows_relay.log'
$relayErrorLog = Join-Path $workspace 'logs\stepesp_windows_relay.err.log'
$serialLog = Join-Path $workspace 'logs\stepesp_master_serial.log'
$serialErrorLog = Join-Path $workspace 'logs\stepesp_master_serial.err.log'
$slaveSerialLog = Join-Path $workspace 'logs\stepesp_slave_serial.log'
$slaveSerialErrorLog = Join-Path $workspace 'logs\stepesp_slave_serial.err.log'
$guiRoot = Join-Path $workspace 'rehab-robotics-studio'
$guiLog = Join-Path $workspace 'logs\stepesp_gui.log'
$guiErrorLog = Join-Path $workspace 'logs\stepesp_gui.err.log'
$openSimSetupScript = Join-Path $workspace 'scripts\setup_opensim_live_link.ps1'
$openSimRunner = '/home/justi/rehab_robotics_ws/run_opensim_live_link_wsl.sh'

if ((wsl -d $Distro -- bash -lc "test -f '$RosInstall/setup.bash'; echo `$?").Trim() -ne '0') {
  throw "ROS install not found at $RosInstall inside $Distro. Build the backend before starting wireless mode."
}

$rosReadiness = (wsl -d $Distro -- bash -lc "source /opt/ros/humble/setup.bash; source '$RosInstall/setup.bash'; ros2 pkg prefix rehab_robotics_interfaces >/dev/null 2>&1 && ros2 pkg executables rosbridge_server | grep -q rosbridge_websocket; echo `$?").Trim()
if ($rosReadiness -ne '0') {
  throw "The ROS install is missing rehab_robotics_interfaces or rosbridge_websocket. Rebuild the v12 workspace before starting wireless mode."
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

# Pin iPhone (or STEP_ESP32) and prevent campus profiles from stealing the NIC.
$masterHostWasExplicit = $PSBoundParameters.ContainsKey('MasterHost')
Disable-CampusWifiAutoconnect
$wifiDeadline = (Get-Date).AddMinutes(8)
$wifiAttempt = 0
$wifiAddress = $null
$activeWifiProfile = $WifiProfile
while ((Get-Date) -lt $wifiDeadline) {
  $wifiAttempt++
  $wifiAddress = Lock-StepEspWifi
  $currentSsid = Get-StepEspCurrentSsid
  if ($wifiAddress) {
    $activeWifiProfile = if ($currentSsid) { $currentSsid } else { $WifiProfile }
    if (-not $masterHostWasExplicit) {
      if ($wifiAddress -like '192.168.4.*') { $MasterHost = '192.168.4.1' }
      elseif ($wifiAddress -like '172.20.10.*') { $MasterHost = '172.20.10.3' }
    }
    Write-Host "Using $activeWifiProfile at $wifiAddress, master=$MasterHost (campus Wi-Fi auto-connect disabled)"
    break
  }
  Write-Host "Wi-Fi attempt ${wifiAttempt}: waiting for $WifiProfile address..."
  Start-Sleep -Seconds 3
}
if (-not $wifiAddress) {
  throw "Could not obtain a $WifiProfile address on $WifiInterface. Stay on that SSID and retry."
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
$scanPrefix = ($wifiAddress -replace '\.\d+$', '.')
if ($SlaveHost -eq 'auto') {
  # ICMP alone is not device identity. Probe the expected hotspot pool in a
  # stable order and let the later IDENTITY exchange select the actual slave.
  # This keeps the known .2 slave ahead of unrelated hotspot clients.
  $candidateSlaveHosts = @(
    2..20 |
      ForEach-Object { "$scanPrefix$_" } |
      Where-Object { $_ -ne $wifiAddress -and $_ -ne $MasterHost }
  )
} else {
  $candidateSlaveHosts = @($SlaveHost)
}
if ($candidateSlaveHosts -contains $wifiAddress) {
  throw "SlaveHost includes this Windows laptop ($wifiAddress), not a slave endpoint."
}

New-Item -ItemType Directory -Path (Split-Path -Parent $relayLog) -Force | Out-Null

# Stop prior USB-backed or Wi-Fi ROS processes before launching this complete stack.
wsl -d $Distro -- bash -lc "pkill -f '[f]leet_bridge_node' || true; pkill -f '[e]sp32_bridge_node' || true; pkill -f '[m]apping_node' || true; pkill -f '[m]odel_catalog_node' || true; pkill -f '[r]osbridge_websocket' || true; pkill -f '[p]rocessing_block_observer' || true; pkill -f '[o]pensim_live_link.launch.py' || true; pkill -f '[o]pensim_bridge' || true"
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

# Old WSL clients and the Windows relay both occupy the ESP's single TCP
# session. Wait until the listen ports drop, then give the boards time to FIN.
if (-not (Wait-StepEspTcpState -Ports @($RelayPort, $SlaveRelayPort, 9090) -ShouldBeOpen $false -TimeoutSeconds 15)) {
  Write-Warning "Prior relay/rosbridge ports are still open; continuing anyway."
}
Start-Sleep -Seconds 10
Stop-ArduinoSerialHolders

# Clear any single-client TCP slot left behind by an interrupted prior run.
# Native USB DTR resets are optional: Wi-Fi-only deployments continue when the
# ports are absent, while the standard COM3/COM4 bench starts from clean queues.
$preflightResetPorts = @($DiagnosticPort, 'COM4') |
  Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
  Select-Object -Unique
$availablePreflightPorts = [System.IO.Ports.SerialPort]::GetPortNames()
$didPreflightReset = $false
foreach ($portName in $preflightResetPorts) {
  if ($availablePreflightPorts -contains $portName) {
    Reset-StepEspOverUsb -PortName $portName
    $didPreflightReset = $true
  }
}

function Test-StepEspTcpListening {
  param([int]$Port)
  return $null -ne (
    Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
      Select-Object -First 1
  )
}

function Wait-StepEspListenState {
  param(
    [int[]]$Ports,
    [int]$TimeoutSeconds = 20
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    $allListening = $true
    foreach ($port in $Ports) {
      if (-not (Test-StepEspTcpListening -Port $port)) {
        $allListening = $false
        break
      }
    }
    if ($allListening) { return $true }
    Start-Sleep -Milliseconds 250
  }
  return $false
}
if ($didPreflightReset) {
  Write-Host 'Waiting for reset ESP nodes to rejoin the hotspot.'
  Start-Sleep -Seconds 10
}

# Firmware status output uses USB CDC. Keep both ports drained before the first
# TCP command so a full CDC buffer cannot stall IDENTITY handling.
if (Test-Path -LiteralPath $serialDrainScript) {
  $availableDrainPorts = [System.IO.Ports.SerialPort]::GetPortNames()
  $drainRoutes = @(
    [pscustomobject]@{ Port = $DiagnosticPort; Log = $serialLog; ErrorLog = $serialErrorLog }
    [pscustomobject]@{ Port = 'COM4'; Log = $slaveSerialLog; ErrorLog = $slaveSerialErrorLog }
  )
  foreach ($drainRoute in $drainRoutes) {
    if ($drainRoute.Port -and $availableDrainPorts -contains $drainRoute.Port) {
      $serialArgs = "`"$serialDrainScript`" $($drainRoute.Port)"
      Start-Process -FilePath python.exe -ArgumentList $serialArgs -RedirectStandardOutput $drainRoute.Log -RedirectStandardError $drainRoute.ErrorLog -WindowStyle Hidden
    }
  }
  if ($drainRoutes | Where-Object { $_.Port -and $availableDrainPorts -contains $_.Port }) {
    Write-Host 'USB serial drains active for ESP command responsiveness.'
    Start-Sleep -Seconds 8
  }
} else {
  Write-Warning "USB serial drain is missing at $serialDrainScript; continuing in Wi-Fi-only mode."
}

$pingDeadline = (Get-Date).AddMinutes(2)
while ((Get-Date) -lt $pingDeadline) {
  [void](Lock-StepEspWifi -Quiet)
  $masterUp = Test-StepEspIcmp -HostAddress $MasterHost
  $slaveUp = $false
  foreach ($candidateHost in $candidateSlaveHosts) {
    if (Test-StepEspIcmp -HostAddress $candidateHost) {
      $slaveUp = $true
      break
    }
  }
  if ($masterUp -and $slaveUp) {
    Write-Host "ICMP reachable: master=$MasterHost slave=$($candidateSlaveHosts -join ', ')"
    break
  }
  Write-Host "Waiting for ESP ICMP (master=$masterUp slave=$slaveUp) on $WifiProfile..."
  $availableNow = [System.IO.Ports.SerialPort]::GetPortNames()
  # COM4 may already be deliberately owned by the serial-drain helper. Do not
  # fight that process with repeated DTR resets during network association.
  Start-Sleep -Seconds 2
}

if (-not $SkipGui) {
  Repair-StepEspGuiDist
  $guiEnv = 'set VITE_DATA_SOURCE=rosbridge&& set VITE_ROSBRIDGE_URL=ws://127.0.0.1:9090&& set VITE_ESP_RAW_TOPIC=/esp/raw/master&& set VITE_ESP_SLAVE_TOPIC=/esp/raw/slave&& '
  $guiDist = Join-Path $guiRoot 'dist\index.html'
  $earlyGuiCommand = if (Test-Path -LiteralPath $guiDist) {
    $guiEnv + 'npm.cmd run preview -- --host 127.0.0.1 --port 5173 --strictPort'
  } else {
    $guiEnv + 'npm.cmd run build&& npm.cmd run preview -- --host 127.0.0.1 --port 5173 --strictPort'
  }
  Write-Host 'Starting GUI before IDENTITY so the browser can open on iPhone (111) without COM3.'
  Start-Process -FilePath cmd.exe -ArgumentList '/c', $earlyGuiCommand -WorkingDirectory $guiRoot -RedirectStandardOutput $guiLog -RedirectStandardError $guiErrorLog -WindowStyle Hidden
}

$masterIdentity = $null
$identityDeadline = (Get-Date).AddMinutes(12)
$identityAttempt = 0
while ((Get-Date) -lt $identityDeadline -and -not $masterIdentity) {
  $identityAttempt++
  try {
    $masterIdentity = Invoke-StepEspIdentityUntilReady -HostAddress $MasterHost -Port $MasterPort -ExpectedRole 'master' -MaxAttempts 8
  } catch {
    Write-Warning "Master identity batch $identityAttempt failed: $($_.Exception.Message)"
    if (-not $masterHostWasExplicit) {
      $scanHosts = @(
        1..20 | ForEach-Object { "$scanPrefix$_" } |
          Where-Object { $_ -ne $wifiAddress }
      )
      foreach ($candidate in $scanHosts) {
        try {
          $probe = Get-StepEspIdentity -HostAddress $candidate -Port $MasterPort -TimeoutMs 2500
          if ($probe.Role -eq 'master') {
            $MasterHost = $candidate
            $masterIdentity = $probe
            Write-Host "Discovered master identity at $MasterHost ($($probe.DeviceId))"
            break
          }
        } catch { }
      }
    }
    if (-not $masterIdentity) {
      [void](Lock-StepEspWifi -Quiet)
      if ($DiagnosticPort) {
        Reset-StepEspOverUsb -PortName $DiagnosticPort
      } else {
        Write-Warning "COM diagnostic port is not connected; retrying identity over Wi-Fi only."
      }
      Start-Sleep -Seconds 4
    }
  }
}
if (-not $masterIdentity) {
  throw "Master identity at $MasterHost never returned IDENTITY_OK. Reflash firmware/step_node/step_node.ino, close Arduino Serial Monitor, then retry."
}
if ($expectedMasterCanonical -and $masterIdentity.DeviceId -ne $expectedMasterCanonical) {
  throw "Master route $MasterHost reported $($masterIdentity.DeviceId), expected $expectedMasterCanonical."
}
$verifiedMasterDeviceId = $masterIdentity.DeviceId

$slaveIdentityProbes = @()
$slaveDeadline = (Get-Date).AddMinutes(8)
$slaveAttempt = 0
while ((Get-Date) -lt $slaveDeadline -and $slaveIdentityProbes.Count -eq 0) {
  $slaveAttempt++
  Write-Host "Slave identity attempt $slaveAttempt on $($candidateSlaveHosts -join ', ')"
  foreach ($candidateHost in $candidateSlaveHosts) {
    try {
      $probe = Get-StepEspIdentity -HostAddress $candidateHost -Port $SlavePort -TimeoutMs 8000
      if ($probe.Role -ne 'slave') {
        Write-Warning "Ignoring candidate $candidateHost because its verified self role is $($probe.Role), not slave."
        continue
      }
      $slaveIdentityProbes += $probe
      # One physical slave route is supported by this bench profile. Once a
      # protocol-verified slave responds, do not spend 8 s on each unrelated
      # iPhone hotspot address that merely answers ICMP.
      break
    } catch {
      Write-Warning "Identity probe rejected candidate $candidateHost`: $($_.Exception.Message)"
    }
  }
  if ($slaveIdentityProbes.Count -eq 0) {
    [void](Lock-StepEspWifi -Quiet)
    $availableNow = [System.IO.Ports.SerialPort]::GetPortNames()
    if (($slaveAttempt % 6) -eq 0 -and $availableNow -contains 'COM4') {
      Write-Host 'Slave IDENTITY stalled; USB-resetting COM4.'
      Reset-StepEspOverUsb -PortName 'COM4'
      Start-Sleep -Seconds 8
    } else {
      Start-Sleep -Seconds 10
    }
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
Write-Host "STEP ESP routes: master=$MasterHost ($verifiedMasterDeviceId), slaves=$($slaveRouteSummaries -join ', '), Windows=$wifiAddress"

# The ESP TCP server is single-client. The identity probe must fully close
# before the relay connects, or fleet_bridge sees "stream closed during identity".
Start-Sleep -Seconds 4

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
if ($DiagnosticPort -and $availableSerialPorts -notcontains $DiagnosticPort) {
  Write-Warning "Diagnostic port $DiagnosticPort is not present; continuing in Wi-Fi-only mode."
}
if (Test-Path -LiteralPath $relayLog) {
  Clear-Content -LiteralPath $relayLog -ErrorAction SilentlyContinue
}
Start-Process -FilePath python.exe -ArgumentList $relayArgs -RedirectStandardOutput $relayLog -RedirectStandardError $relayErrorLog -WindowStyle Hidden
$relayReady = Wait-StepEspListenState -Ports @($RelayPort, $SlaveRelayPort) -TimeoutSeconds 20
if (-not $relayReady) {
  throw "Relay ports $RelayPort/$SlaveRelayPort did not open. Check $relayLog and $relayErrorLog"
}
Write-Host "Relay listening on $RelayPort (master) and $SlaveRelayPort (slave)."

$openSimPythonPath = "$OpenSimEnvironment/lib/python3.10/site-packages"
$openSimLibraryPath = "$OpenSimEnvironment/lib"
$rosEnvironment = "export ROS_DOMAIN_ID=$RosDomainId; export PYTHONPATH=`"${backendRootWsl}:${openSimPythonPath}:`${PYTHONPATH:-}`"; export LD_LIBRARY_PATH=`"${openSimLibraryPath}:`${LD_LIBRARY_PATH:-}`"; source /opt/ros/humble/setup.bash; source $RosInstall/setup.bash; source $OpenSimInstall/setup.bash"
$fleetRouteObjects = [System.Collections.Generic.List[object]]::new()
[void]$fleetRouteObjects.Add([ordered]@{
  host = $wslGateway
  port = $RelayPort
  expected_device_id = $verifiedMasterDeviceId
  role = 'master'
  body_segment = 'femur_r_imu'
})
for ($index = 0; $index -lt $selectedSlaves.Count; $index++) {
  $route = $selectedSlaves[$index]
  $listenPort = $SlaveRelayPort + $index
  $bodySegment = if ($index -eq 0) { 'tibia_r_imu' } else { '' }
  [void]$fleetRouteObjects.Add([ordered]@{
    host = $wslGateway
    port = $listenPort
    expected_device_id = $route.DeviceId
    role = 'slave'
    body_segment = $bodySegment
  })
}
$routesJson = ConvertTo-Json -InputObject @($fleetRouteObjects.ToArray()) -Compress -Depth 6
# rcl parses -p values as YAML. A JSON array is not a string, so write a params
# file with routes_json quoted. Keep it off the workspace path (which contains '#').
$fleetParamsWin = Join-Path $env:USERPROFILE 'stepesp_fleet_params.yaml'
$fleetParamsWsl = '/mnt/c/Users/justi/stepesp_fleet_params.yaml'
@(
  'esp_fleet_bridge:'
  '  ros__parameters:'
  ("    routes_json: '{0}'" -f $routesJson.Replace("'", "''"))
  "    alias_master_device_id: `"$verifiedMasterDeviceId`""
  "    alias_slave_device_id: `"$verifiedSlaveDeviceId`""
) | Set-Content -LiteralPath $fleetParamsWin -Encoding ascii
$fleet = "$rosEnvironment; exec ros2 run rehab_robotics_bridge fleet_bridge_node --ros-args -r __node:=esp_fleet_bridge --params-file $fleetParamsWsl > $bridgeLog 2>&1"
$rosbridge = "$rosEnvironment; exec ros2 run rosbridge_server rosbridge_websocket --ros-args -p port:=9090 -p address:=0.0.0.0 > $rosbridgeLog 2>&1"
$observer = "$rosEnvironment; exec ros2 run rehab_robotics_bridge processing_block_observer > $observerLog 2>&1"
$modelCatalog = "$rosEnvironment; exec ros2 run rehab_robotics_bridge model_catalog_node --ros-args -p opensim_model_path:=$OpenSimModel > $modelCatalogLog 2>&1"
$mapping = "$rosEnvironment; exec ros2 run rehab_robotics_bridge mapping_node > $mappingLog 2>&1"
$openSim = "export ROS_DOMAIN_ID=$RosDomainId; exec bash $openSimRunner $OpenSimModel false master_imu_topic:=/esp32/master/imu slave_imu_topic:=/esp32/slave/imu > $openSimLog 2>&1"

# The readiness test below must examine this launch only.  A prior OpenSim import
# failure in an appended log must not turn a subsequently healthy catalog into a
# false startup failure.
wsl -d $Distro -- bash -lc ": > '$modelCatalogLog'"

Start-Process -FilePath wsl.exe -ArgumentList '-d', $Distro, '--', 'bash', '-lc', $fleet -WindowStyle Hidden
Start-Process -FilePath wsl.exe -ArgumentList '-d', $Distro, '--', 'bash', '-lc', $rosbridge -WindowStyle Hidden
try {
  Start-Process -FilePath wsl.exe -ArgumentList '-d', $Distro, '--', 'bash', '-lc', $observer -WindowStyle Hidden
} catch {
  Write-Warning "processing_block_observer did not start: $($_.Exception.Message)"
}
Start-Process -FilePath wsl.exe -ArgumentList '-d', $Distro, '--', 'bash', '-lc', $modelCatalog -WindowStyle Hidden
Start-Process -FilePath wsl.exe -ArgumentList '-d', $Distro, '--', 'bash', '-lc', $mapping -WindowStyle Hidden
Start-Process -FilePath wsl.exe -ArgumentList '-d', $Distro, '--', 'bash', '-lc', $openSim -WindowStyle Hidden

$catalogReady = $false
$catalogDeadline = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $catalogDeadline) {
  $catalogTail = ((wsl -d $Distro -- bash -lc "tail -n 40 '$modelCatalogLog' 2>/dev/null") -join "`n")
  if ($catalogTail -match 'catalog ready.+[1-9][0-9]* frames') {
    $catalogReady = $true
    break
  }
  if ($catalogTail -match 'opensim bindings unavailable|frame enumeration failed|model file not found') {
    throw "Model catalog failed and the GUI cannot map sensors. Check $modelCatalogLog."
  }
  Start-Sleep -Milliseconds 500
}
if (-not $catalogReady) {
  throw "Model catalog did not publish a non-empty frame list. Check $modelCatalogLog."
}
Write-Host 'Model catalog published a non-empty model-derived frame list.'

$rosbridgeReady = Wait-StepEspListenState -Ports @(9090) -TimeoutSeconds 60
if (-not $rosbridgeReady) {
  throw "rosbridge did not open port 9090. Check $rosbridgeLog inside WSL."
}
Write-Host 'rosbridge listening on 9090.'

$fleetBound = $false
$fleetRecoveryDone = $false
$fleetDeadline = (Get-Date).AddMinutes(3)
$fleetAttempt = 0
while ((Get-Date) -lt $fleetDeadline -and -not $fleetBound) {
  $fleetAttempt++
  [void](Lock-StepEspWifi -Quiet)
  $tailLines = @(wsl -d $Distro -- bash -lc "tail -n 80 '$bridgeLog' 2>/dev/null")
  $tail = ($tailLines -join "`n").Trim()
  if ($tail -match 'identity bound:.*role=master' -and $tail -match 'identity bound:.*role=slave') {
    $fleetBound = $true
    Write-Host 'Fleet bridge bound master and slave identities.'
    break
  }
  if (($fleetAttempt % 8) -eq 0) {
    Write-Host "Waiting for fleet identity bind (attempt $fleetAttempt)..."
  }
  if (-not $fleetRecoveryDone -and $fleetAttempt -ge 24) {
    $fleetRecoveryDone = $true
    $fleetRecoveryPorts = @($DiagnosticPort, 'COM4') |
      Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
      Select-Object -Unique
    $availableRecoveryPorts = [System.IO.Ports.SerialPort]::GetPortNames()
    foreach ($portName in $fleetRecoveryPorts) {
      if ($availableRecoveryPorts -contains $portName) {
        Write-Host "Fleet bind recovery: USB-resetting $portName once."
        Reset-StepEspOverUsb -PortName $portName
      }
    }
    Start-Sleep -Seconds 10
  }
  Start-Sleep -Seconds 2
}
if (-not $fleetBound) {
  Write-Warning "Fleet bridge has not bound both identities yet. GUI/rosbridge are up; check $bridgeLog and $relayLog."
}

if (-not $SkipGui) {
  # Vite dev mode cannot reliably resolve source URLs when this workspace path
  # contains '#'. Build first and serve dist so the existing folder name works.
  $guiEnv = 'set VITE_DATA_SOURCE=rosbridge&& set VITE_ROSBRIDGE_URL=ws://127.0.0.1:9090&& set VITE_ESP_RAW_TOPIC=/esp/raw/master&& set VITE_ESP_SLAVE_TOPIC=/esp/raw/slave&& '
  $guiPreviewOnly = $guiEnv + 'npm.cmd run preview -- --host 127.0.0.1 --port 5173 --strictPort'
  $guiDist = Join-Path $guiRoot 'dist\index.html'
  $guiStartedAt = Get-Date
  $guiRestartEvery = New-TimeSpan -Minutes 4
  $guiDeadline = (Get-Date).AddMinutes(8)
  $guiReady = $false
  $guiLaunchCount = 0

  function Start-StepEspGuiProcess {
    param([string]$Command)
    $script:guiLaunchCount++
    Write-Host "Starting GUI process #$guiLaunchCount"
    Start-Process -FilePath cmd.exe -ArgumentList '/c', $Command -WorkingDirectory $guiRoot -RedirectStandardOutput $guiLog -RedirectStandardError $guiErrorLog -WindowStyle Hidden
  }

  Write-Host 'Building the current GUI source before serving it.'
  $guiBuild = Start-Process -FilePath cmd.exe -ArgumentList '/c', ($guiEnv + 'npm.cmd run build') -WorkingDirectory $guiRoot -RedirectStandardOutput $guiLog -RedirectStandardError $guiErrorLog -WindowStyle Hidden -Wait -PassThru
  if ($guiBuild.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $guiDist)) {
    throw "GUI build failed. Check $guiLog and $guiErrorLog; stale dist assets will not be served."
  }
  Repair-StepEspGuiDist

  if (-not (Test-StepEspHttpReady -Uri 'http://127.0.0.1:5173') -or -not (Test-StepEspCssReady)) {
    Start-StepEspGuiProcess -Command $guiPreviewOnly
  }
  while (-not $guiReady) {
    if ((Get-Date) -ge $guiDeadline) {
      throw "GUI did not become ready at http://127.0.0.1:5173 with a real stylesheet. Check $guiLog and $guiErrorLog"
    }
    if ((Test-StepEspHttpReady -Uri 'http://127.0.0.1:5173') -and (Test-StepEspCssReady)) {
      $guiReady = $true
      break
    }
    $elapsed = (Get-Date) - $guiStartedAt
    Write-Host ("Waiting for GUI at http://127.0.0.1:5173 ({0:n0}s elapsed)" -f $elapsed.TotalSeconds)
    if ($elapsed -ge $guiRestartEvery) {
      $escapedGuiRoot = [regex]::Escape($guiRoot)
      Get-CimInstance Win32_Process |
        Where-Object {
          $_.ProcessId -ne $PID -and $_.CommandLine -match $escapedGuiRoot -and
          $_.CommandLine -match 'vite|npm(.cmd)?\s+run\s+(build|dev|preview)'
        } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
      Repair-StepEspGuiDist
      $guiStartedAt = Get-Date
      Start-StepEspGuiProcess -Command $guiPreviewOnly
    }
    Start-Sleep -Seconds 3
  }
  if (-not $NoBrowser) {
    Start-Process 'http://127.0.0.1:5173'
  }
}

Write-Host "Started the complete STEP ESP stack on $activeWifiProfile`: N-route Windows relay, one fleet_bridge_node (aliases + registry), OpenSim live link, rosbridge, processing observer$(if (-not $SkipGui) { ', and GUI' })."
Write-Host "ROS domain: $RosDomainId"
Write-Host "GUI: http://127.0.0.1:5173"
Write-Host "rosbridge: ws://127.0.0.1:9090"
Write-Host "Verify pair: source $RosInstall/setup.bash; ROS_DOMAIN_ID=$RosDomainId ros2 topic echo /esp/status/pair --once --field data"
Write-Host "Verify registry: source $RosInstall/setup.bash; ROS_DOMAIN_ID=$RosDomainId ros2 topic echo /esp/fleet/registry --once --field data"
Write-Host "Verify deployment topics: source $RosInstall/setup.bash; ROS_DOMAIN_ID=$RosDomainId ros2 topic list | grep processing_blocks"
Write-Host "Fleet bridge log: $bridgeLog (kept after you return to $InternetProfile)"
Write-Host "rosbridge log: $rosbridgeLog"
Write-Host "observer log: $observerLog"
Write-Host "model catalog log: $modelCatalogLog"
Write-Host "mapping log: $mappingLog"
Write-Host "OpenSim status: source $OpenSimInstall/setup.bash; ROS_DOMAIN_ID=$RosDomainId ros2 topic echo /opensim/status --once --full-length"
Write-Host "OpenSim log: $openSimLog"
Write-Host "Relay log: $relayLog"
if ($DiagnosticPort -and $availableSerialPorts -contains $DiagnosticPort) { Write-Host "USB diagnostic logs: $serialLog and $slaveSerialLog" }
if (-not $SkipGui) { Write-Host "GUI logs: $guiLog and $guiErrorLog" }
Write-Host "Stay on $activeWifiProfile while acquiring. Restore normal Wi-Fi with: .\scripts\stop_stepesp_wireless.ps1"
} finally {
  if ($null -ne $launcherLock) {
    $launcherLock.Dispose()
  }
}
