param(
  [string]$Distro = 'Ubuntu-22.04',
  [string]$WifiProfile = 'iPhone (111)',
  [string]$InternetProfile = 'ubcsecure',
  [string]$WifiInterface = 'Wi-Fi'
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$guiRoot = Join-Path $workspace 'rehab-robotics-studio'

wsl -d $Distro -- bash -lc "pkill -f '[f]leet_bridge_node' || true; pkill -f '[e]sp32_bridge_node' || true; pkill -f '[m]apping_node' || true; pkill -f '[m]odel_catalog_node' || true; pkill -f '[r]osbridge_websocket' || true; pkill -f '[p]rocessing_block_observer' || true; pkill -f '[o]pensim_live_link.launch.py' || true; pkill -f '[o]pensim_bridge' || true"
Get-CimInstance Win32_Process |
  Where-Object {
    $_.ProcessId -ne $PID -and
    $_.CommandLine -match 'stepesp_tcp_udp_relay.py|stepesp_serial_drain.py'
  } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

$escapedGuiRoot = [regex]::Escape($guiRoot)
Get-CimInstance Win32_Process |
  Where-Object {
    $_.ProcessId -ne $PID -and $_.CommandLine -match $escapedGuiRoot -and
    $_.CommandLine -match 'vite|npm(.cmd)?\s+run\s+(dev|preview)'
  } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

netsh wlan set profileparameter name="$WifiProfile" connectionmode=manual | Out-Null
netsh wlan set profileparameter name="$InternetProfile" connectionmode=auto | Out-Null
netsh wlan connect name="$InternetProfile" interface="$WifiInterface" | Out-Null

Write-Host "Stopped the STEP_ESP32 relay, ROS nodes, OpenSim live link, rosbridge, observer, and GUI; restored $InternetProfile auto-connect."
