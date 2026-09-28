[CmdletBinding()]
param(
    [string]$RunnerRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$Save,
    [string]$DataDir = (Join-Path $env:LOCALAPPDATA 'FE7-Link-Arena'),
    [string]$ObsPath = 'C:\Program Files\obs-studio\bin\64bit\obs64.exe',
    [ValidatePattern('^[A-Za-z0-9_]{1,25}$')]
    [string]$TwitchChannel = 'llmletsplay',
    [switch]$RestartNow
)

$ErrorActionPreference = 'Stop'
$RunnerRoot = (Resolve-Path $RunnerRoot).Path
if (-not $Save) { $Save = Join-Path $RunnerRoot 'roms\fe7.sav' }
$Save = (Resolve-Path $Save).Path
$ObsPath = (Resolve-Path $ObsPath).Path
$runnerScript = Join-Path $RunnerRoot 'scripts\windows\Start-Link-Arena.ps1'
$obsSupervisor = Join-Path $PSScriptRoot 'Start-OBS-Link-Arena.ps1'
$sceneCollection = Join-Path $env:APPDATA 'obs-studio\basic\scenes\FE7 Link Arena.json'
foreach ($path in @($runnerScript, $obsSupervisor, $Save, $sceneCollection)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required Link Arena stream file not found: $path"
    }
}

$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$legacyTaskNames = @('FE7-Link-Arena-Stream-Runner', 'Codex-FE7-Link-Arena-OBS-Setup')
if (-not $RestartNow) {
    $runningLegacy = @($legacyTaskNames | ForEach-Object {
        Get-ScheduledTask -TaskName $_ -ErrorAction SilentlyContinue
    } | Where-Object State -eq 'Running')
    if ($runningLegacy.Count -gt 0) {
        throw 'Legacy Link Arena tasks are still running. Rerun with -RestartNow to replace them safely.'
    }
    foreach ($taskName in $legacyTaskNames) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    }
}
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentIdentity
$principal = New-ScheduledTaskPrincipal -UserId $currentIdentity `
    -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
$powerShellPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

$obsArguments = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $obsSupervisor),
    '-ObsPath', ('"{0}"' -f $ObsPath), '-Collection', '"FE7 Link Arena"',
    '-Scene', '"FE7 Link Arena"', '-DataDir', ('"{0}"' -f $DataDir),
    '-StartStreaming', '-MinimizeToTray'
) -join ' '
$obsAction = New-ScheduledTaskAction -Execute $powerShellPath `
    -Argument $obsArguments -WorkingDirectory (Split-Path -Parent $ObsPath)

$runnerArguments = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $runnerScript),
    '-RepoRoot', ('"{0}"' -f $RunnerRoot), '-Save', ('"{0}"' -f $Save),
    '-DataDir', ('"{0}"' -f $DataDir), '-TwitchChannel', $TwitchChannel,
    '-AutoMinimax', '-Continuous'
) -join ' '
$runnerAction = New-ScheduledTaskAction -Execute $powerShellPath `
    -Argument $runnerArguments -WorkingDirectory $RunnerRoot

if ($RestartNow) {
    foreach ($taskName in @(
        'FE7-Link-Arena-Continuous-Runner', 'FE7-Link-Arena-Stream-Runner',
        'FE7-Link-Arena-OBS-Watchdog', 'Codex-FE7-Link-Arena-OBS-Setup'
    )) {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($task -and $task.State -eq 'Running') {
            Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        }
    }

    $runnerPathToken = $RunnerRoot.TrimEnd('\').ToLowerInvariant()
    $managedProcesses = Get-CimInstance Win32_Process | Where-Object {
        $commandLine = ([string]$_.CommandLine).ToLowerInvariant()
        $name = [string]$_.Name
        ($name -in @('python.exe', 'pythonw.exe') -and $commandLine.Contains('tools\link_arena.py') -and $commandLine.Contains($runnerPathToken)) -or
        ($name -eq 'mGBA.exe' -and $commandLine.Contains($runnerPathToken)) -or
        ($name -eq 'obs64.exe' -and ([string]$_.ExecutablePath).Equals($ObsPath, [StringComparison]::OrdinalIgnoreCase))
    }
    foreach ($process in $managedProcesses) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    foreach ($taskName in @(
        'FE7-Link-Arena-Continuous-Runner', 'FE7-Link-Arena-Stream-Runner',
        'FE7-Link-Arena-OBS-Watchdog', 'Codex-FE7-Link-Arena-OBS-Setup'
    )) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    }
}

Register-ScheduledTask -TaskName 'FE7-Link-Arena-OBS-Watchdog' `
    -Action $obsAction -Trigger $trigger -Settings $settings -Principal $principal `
    -Description 'Keeps the FE7 Link Arena OBS collection running in normal mode for the 24/7 Twitch stream.' `
    -Force | Out-Null
Register-ScheduledTask -TaskName 'FE7-Link-Arena-Continuous-Runner' `
    -Action $runnerAction -Trigger $trigger -Settings $settings -Principal $principal `
    -Description 'Runs verified minimax FE7 Link Arena matches continuously and keeps the series score.' `
    -Force | Out-Null

if ($RestartNow) {
    Start-ScheduledTask -TaskName 'FE7-Link-Arena-OBS-Watchdog'
    Start-ScheduledTask -TaskName 'FE7-Link-Arena-Continuous-Runner'
}

Write-Output "Installed logon tasks for $currentIdentity."
Write-Output 'OBS scene: FE7 Link Arena; OBS watchdog archives stale recovery markers and starts normal mode.'
Write-Output "Twitch channel: $TwitchChannel; continuous Link Arena score data: $DataDir\series\results.jsonl"
if ($RestartNow) {
    Write-Output 'The current isolated match and OBS process were restarted; both new tasks are running.'
} else {
    Write-Output 'Run again with -RestartNow to replace current processes and start both tasks immediately.'
}
