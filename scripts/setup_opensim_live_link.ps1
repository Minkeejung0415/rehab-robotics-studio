[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$distribution = 'Ubuntu-22.04'
$shellScript = Join-Path $PSScriptRoot 'setup_opensim_live_link_wsl.sh'
$shellScriptWsl = (
    & wsl.exe -d $distribution -- wslpath -a -- $shellScript
).Trim()

if ($LASTEXITCODE -ne 0 -or -not $shellScriptWsl) {
    throw 'Could not translate the setup script path into WSL.'
}

& wsl.exe -d $distribution -- bash $shellScriptWsl
if ($LASTEXITCODE -ne 0) {
    throw "OpenSim live-link setup failed with exit code $LASTEXITCODE."
}
