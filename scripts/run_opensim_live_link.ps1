[CmdletBinding()]
param(
    [string]$ModelPath = '',
    [switch]$Test,
    [string]$MasterTopic = '/esp32/master/imu',
    [string]$SlaveTopic = '/esp32/slave/imu'
)

$ErrorActionPreference = 'Stop'
$distribution = 'Ubuntu-22.04'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if (-not $ModelPath) {
    $ModelPath = Join-Path $projectRoot 'examples\opensim_quaternion_demo.osim'
}
$resolvedModel = (Resolve-Path $ModelPath).Path
$modelWsl = (
    & wsl.exe -d $distribution -- wslpath -a -- $resolvedModel
).Trim()
$runner = Join-Path $PSScriptRoot 'run_opensim_live_link_wsl.sh'
$runnerWsl = (
    & wsl.exe -d $distribution -- wslpath -a -- $runner
).Trim()

if ($LASTEXITCODE -ne 0 -or -not $modelWsl -or -not $runnerWsl) {
    throw 'Could not translate the launch paths into WSL.'
}

$testPublisher = if ($Test) { 'true' } else { 'false' }
& wsl.exe -d $distribution -- bash $runnerWsl `
    $modelWsl `
    $testPublisher `
    "master_imu_topic:=$MasterTopic" `
    "slave_imu_topic:=$SlaveTopic"

if ($LASTEXITCODE -ne 0) {
    throw "OpenSim live link exited with code $LASTEXITCODE."
}
