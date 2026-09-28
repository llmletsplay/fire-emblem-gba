[CmdletBinding()]
param(
    [string]$ObsPath = 'C:\Program Files\obs-studio\bin\64bit\obs64.exe',
    [string]$Collection = 'FE7 Link Arena',
    [string]$Scene = 'FE7 Link Arena',
    [string]$DataDir = (Join-Path $env:LOCALAPPDATA 'FE7-Link-Arena'),
    [switch]$StartStreaming,
    [switch]$MinimizeToTray
)

$ErrorActionPreference = 'Stop'
$ObsPath = (Resolve-Path $ObsPath).Path
$LogPath = Join-Path $DataDir 'obs-startup.log'
$RecoveryDir = Join-Path $DataDir 'obs-recovery'
$SentinelPath = Join-Path $env:APPDATA 'obs-studio\.sentinel'
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

function Write-ObsSupervisorLog([string]$Message) {
    Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value "$(Get-Date -Format o) $Message"
}

function Archive-ObsRecoveryMarker {
    if (-not (Test-Path -LiteralPath $SentinelPath)) { return }
    New-Item -ItemType Directory -Force -Path $RecoveryDir | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $destination = Join-Path $RecoveryDir "sentinel-$stamp"
    Move-Item -LiteralPath $SentinelPath -Destination $destination
    Write-ObsSupervisorLog "Archived OBS unclean-shutdown marker to $destination; starting the configured scene in normal mode for unattended streaming."
}

if (-not (Test-Path -LiteralPath $ObsPath -PathType Leaf)) {
    throw "OBS executable not found: $ObsPath"
}

$arguments = @('--collection', "`"$Collection`"", '--scene', "`"$Scene`"")
if ($MinimizeToTray) { $arguments += '--minimize-to-tray' }
if ($StartStreaming) { $arguments += '--startstreaming' }
$argumentLine = $arguments -join ' '
$retrySeconds = 5

Write-ObsSupervisorLog "OBS supervisor started for collection '$Collection', scene '$Scene'."
while ($true) {
    $existing = Get-Process -Name obs64 -ErrorAction SilentlyContinue
    if ($existing) {
        Write-ObsSupervisorLog 'OBS is already running; waiting for it to exit before relaunch.'
        while (Get-Process -Name obs64 -ErrorAction SilentlyContinue) {
            Start-Sleep -Seconds 5
        }
    }

    try {
        Archive-ObsRecoveryMarker
        Write-ObsSupervisorLog "Launching OBS normally with arguments: $argumentLine"
        $process = Start-Process -FilePath $ObsPath -ArgumentList $argumentLine `
            -WorkingDirectory (Split-Path -Parent $ObsPath) -PassThru
        $process.WaitForExit()
        $exitCode = $process.ExitCode
        Write-ObsSupervisorLog "OBS exited with code $exitCode; restarting in $retrySeconds seconds."
    }
    catch {
        Write-ObsSupervisorLog "OBS launch/recovery failed: $($_.Exception.Message). Retrying in $retrySeconds seconds."
    }

    Start-Sleep -Seconds $retrySeconds
    $retrySeconds = [Math]::Min(300, $retrySeconds * 2)
}
