# Read-only local task status; shared Python engine.
param([string]$Feature, [switch]$Json, [switch]$Help)
$ErrorActionPreference = 'Stop'
$pythonCommand = $env:PYTHON
if (-not $pythonCommand) {
    if (Get-Command python3 -ErrorAction SilentlyContinue) { $pythonCommand = 'python3' }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $pythonCommand = 'python' }
    else { Write-Error 'Project Status requires Python 3; set PYTHON to its executable.'; exit 2 }
}
$engine = Join-Path $PSScriptRoot '../status.py'
$engineArguments = @('-B', $engine)
if ($Feature) { $engineArguments += @('--feature', $Feature) }
if ($Json) { $engineArguments += '--json' }
if ($Help) { $engineArguments += '--help' }
& $pythonCommand @engineArguments
exit $LASTEXITCODE
