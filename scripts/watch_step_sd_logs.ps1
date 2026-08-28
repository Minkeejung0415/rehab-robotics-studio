param(
  [Parameter(Mandatory = $true)]
  [ValidateScript({ Test-Path -LiteralPath $_ -PathType Container })]
  [string]$Folder,
  [double]$IntervalSeconds = 2
)

$scriptPath = Join-Path $PSScriptRoot 'convert_step_sd_bin.py'
python $scriptPath --watch $Folder --interval $IntervalSeconds
