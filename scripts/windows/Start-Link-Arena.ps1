[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$Rom,
    [string]$Save,
    [string]$DataDir,
    [string]$Mgba,
    [string]$MgbaLogLevel,
    [ValidateRange(1, 120)]
    [int]$StartupTimeout = 20
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path $RepoRoot).Path
$Runner = Join-Path $RepoRoot 'tools\link_arena.py'
if (-not (Test-Path $Runner)) {
    throw "Link Arena runner not found: $Runner"
}

$Python = Get-Command python -ErrorAction SilentlyContinue
$PythonArgs = @('-u')
if (-not $Python) {
    $Python = Get-Command py -ErrorAction SilentlyContinue
    if (-not $Python) {
        throw 'Python was not found. Install Python 3 or add python/py to PATH.'
    }
    $PythonArgs = @('-3', '-u')
}

$Arguments = @($Runner)
if ($Rom) { $Arguments += @('--rom', (Resolve-Path $Rom).Path) }
if ($Save) { $Arguments += @('--save', (Resolve-Path $Save).Path) }
if ($DataDir) { $Arguments += @('--data-dir', $DataDir) }
if ($Mgba) { $Arguments += @('--mgba', (Resolve-Path $Mgba).Path) }
if ($MgbaLogLevel) { $Arguments += @('--mgba-log-level', $MgbaLogLevel) }
$Arguments += @('--startup-timeout', $StartupTimeout)

Push-Location $RepoRoot
try {
    & $Python.Source @PythonArgs @Arguments
    $ExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}
exit $ExitCode
