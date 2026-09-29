[CmdletBinding()]
param(
    [string]$RunnerRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$Save,
    [string]$DataDir = (Join-Path $env:LOCALAPPDATA 'FE7-Link-Arena'),
    [string]$CurrentDataDir = (Join-Path $env:LOCALAPPDATA 'FE7-Link-Arena'),
    [string]$CredentialPath = (Join-Path $env:LOCALAPPDATA 'FE7-Link-Arena\secrets\provider-credentials.dpapi.json'),
    [string]$ObsPath = 'C:\Program Files\obs-studio\bin\64bit\obs64.exe',
    [ValidatePattern('^[A-Za-z0-9_]{1,25}$')]
    [string]$TwitchChannel = 'llmletsplay',
    [ValidateSet('minimax', 'chutes', 'minimax-api')]
    [string]$AgentA = 'minimax',
    [string]$ModelA,
    [ValidateSet('adaptive', 'disabled')]
    [string]$MinimaxThinkingA,
    [ValidateSet('low', 'medium', 'high', 'xhigh', 'max')]
    [string]$MinimaxReasoningEffortA,
    [ValidateRange(1, 204800)]
    [int]$MaxCompletionTokensA = 2048,
    [ValidateSet('minimax', 'chutes', 'minimax-api')]
    [string]$AgentB = 'minimax',
    [string]$ModelB,
    [ValidateSet('adaptive', 'disabled')]
    [string]$MinimaxThinkingB,
    [ValidateSet('low', 'medium', 'high', 'xhigh', 'max')]
    [string]$MinimaxReasoningEffortB,
    [ValidateRange(1, 204800)]
    [int]$MaxCompletionTokensB = 2048,
    [ValidateRange(1, 600)]
    [double]$AgentTimeout = 120,
    [ValidateRange(0, 100000)]
    [int]$MaxMatches = 0,
    [switch]$AlternateAgentSeats,
    [int]$SeatOrderSeed = 0,
    [ValidateRange(30, 86400)]
    [int]$HandoffTimeoutSeconds = 21600,
    [switch]$HandoffAtMatchBoundary,
    [switch]$RestartNow
)

$ErrorActionPreference = 'Stop'
$RunnerRoot = (Resolve-Path $RunnerRoot).Path
. (Join-Path $PSScriptRoot 'Get-Link-Arena-DotEnvValue.ps1')
$DotEnvPath = Join-Path $RunnerRoot '.env'
if (-not $ModelA -and $AgentA -eq 'minimax-api') {
    $ModelA = Get-LinkArenaDotEnvValue -Path $DotEnvPath -Name 'MINIMAX_MODEL'
}
elseif (-not $ModelA -and $AgentA -eq 'chutes') {
    $ModelA = Get-LinkArenaDotEnvValue -Path $DotEnvPath -Name 'CHUTES_MODEL'
}
if (-not $ModelB -and $AgentB -eq 'minimax-api') {
    $ModelB = Get-LinkArenaDotEnvValue -Path $DotEnvPath -Name 'MINIMAX_MODEL'
}
elseif (-not $ModelB -and $AgentB -eq 'chutes') {
    $ModelB = Get-LinkArenaDotEnvValue -Path $DotEnvPath -Name 'CHUTES_MODEL'
}
if (-not $Save) { $Save = Join-Path $RunnerRoot 'roms\fe7.sav' }
$Save = (Resolve-Path $Save).Path
$DataDir = [System.IO.Path]::GetFullPath($DataDir)
$CurrentDataDir = [System.IO.Path]::GetFullPath($CurrentDataDir)
$ObsPath = (Resolve-Path $ObsPath).Path
$runnerScript = Join-Path $RunnerRoot 'scripts\windows\Start-Link-Arena.ps1'
$obsSupervisor = Join-Path $PSScriptRoot 'Start-OBS-Link-Arena.ps1'
$credentialImporter = Join-Path $PSScriptRoot 'Import-Link-Arena-Credentials.ps1'
$sceneCollection = Join-Path $env:APPDATA 'obs-studio\basic\scenes\FE7 Link Arena.json'
foreach ($path in @($runnerScript, $obsSupervisor, $Save, $sceneCollection)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required Link Arena stream file not found: $path"
    }
}

foreach ($side in @('A', 'B')) {
    $agent = if ($side -eq 'A') { $AgentA } else { $AgentB }
    $model = if ($side -eq 'A') { $ModelA } else { $ModelB }
    $thinking = if ($side -eq 'A') { $MinimaxThinkingA } else { $MinimaxThinkingB }
    $effort = if ($side -eq 'A') { $MinimaxReasoningEffortA } else { $MinimaxReasoningEffortB }
    if ($agent -ne 'minimax' -and [string]::IsNullOrWhiteSpace($model)) {
        throw "-Model$side is required when -Agent$side is '$agent'."
    }
    if ($agent -ne 'minimax-api' -and ($thinking -or $effort)) {
        throw "MiniMax thinking options for seat $side require -Agent$side minimax-api."
    }
    if ($agent -eq 'minimax-api' -and $model -match '(?i)m3\.1' -and -not $effort) {
        throw "MiniMax M3.1 requires -MinimaxReasoningEffort$side with an explicit effort."
    }
}

if ($HandoffAtMatchBoundary) {
    if ($RestartNow) {
        throw 'Use either -HandoffAtMatchBoundary or -RestartNow, not both.'
    }
    if ([string]::Equals($DataDir.TrimEnd('\'), $CurrentDataDir.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
        throw '-HandoffAtMatchBoundary requires a new DataDir separate from the live series.'
    }
    if (-not $AlternateAgentSeats -or $MaxMatches -lt 2 -or ($MaxMatches % 2) -ne 0) {
        throw 'A safe hosted handoff requires -AlternateAgentSeats and an even -MaxMatches of at least 2.'
    }
    if ($AgentA -eq 'minimax' -and $AgentB -eq 'minimax') {
        throw 'A safe hosted handoff requires at least one hosted agent.'
    }
    if (Test-Path -LiteralPath $DataDir -PathType Leaf) {
        throw '-HandoffAtMatchBoundary requires a directory path for DataDir.'
    }
    $existingData = @()
    if (Test-Path -LiteralPath $DataDir -PathType Container) {
        $existingData = @(Get-ChildItem -LiteralPath $DataDir -Force -ErrorAction SilentlyContinue)
    }
    if ($existingData.Count -gt 0) {
        throw '-HandoffAtMatchBoundary requires an empty experimental DataDir.'
    }
}

$hostedProviders = @()
foreach ($provider in @($AgentA, $AgentB)) {
    if ($provider -ne 'minimax') { $hostedProviders += $provider }
}
$hostedProviders = @($hostedProviders | Select-Object -Unique)
if ($hostedProviders.Count -gt 0) {
    if (-not (Test-Path -LiteralPath $credentialImporter -PathType Leaf)) {
        throw "Hosted policies require the credential importer: $credentialImporter"
    }
    $credentialSetter = Join-Path $PSScriptRoot 'Set-Link-Arena-ProviderCredentials.ps1'
    if ($DotEnvPath -and (Test-Path -LiteralPath $DotEnvPath -PathType Leaf)) {
        if (-not (Test-Path -LiteralPath $credentialSetter -PathType Leaf)) {
            throw "Hosted policies require the credential setter: $credentialSetter"
        }
        & $credentialSetter -CredentialPath $CredentialPath -EnvFile $DotEnvPath
    }
    & $credentialImporter -CredentialPath $CredentialPath
    foreach ($provider in $hostedProviders) {
        $credentialName = if ($provider -eq 'chutes') { 'CHUTES_API_KEY' } else { 'MINIMAX_API_KEY' }
        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($credentialName, 'Process'))) {
            throw "Hosted policy '$provider' requires a locally saved $credentialName. Run Set-Link-Arena-ProviderCredentials.ps1 as this Windows user."
        }
    }
}

$preserveObsProcess = [bool]$HandoffAtMatchBoundary
$replaceRunningProcesses = [bool]($RestartNow -or $HandoffAtMatchBoundary)
if ($HandoffAtMatchBoundary) {
    if (@(Get-Process -Name 'obs64' -ErrorAction SilentlyContinue).Count -lt 1) {
        throw 'Safe handoff requires the existing OBS stream process to be running.'
    }
    $runnerPathToken = $RunnerRoot.TrimEnd('\').ToLowerInvariant()
    $currentDataDirToken = $CurrentDataDir.TrimEnd('\').ToLowerInvariant()
    $currentRunnerProcesses = @(Get-CimInstance Win32_Process | Where-Object {
        $commandLine = ([string]$_.CommandLine).ToLowerInvariant()
        ([string]$_.Name) -in @('python.exe', 'pythonw.exe') -and
            $commandLine.Contains('tools\link_arena.py') -and
            $commandLine.Contains($runnerPathToken) -and
            $commandLine.Contains($currentDataDirToken)
    })
    if ($currentRunnerProcesses.Count -ne 1) {
        throw 'Safe handoff requires exactly one live runner matching -CurrentDataDir; no process was stopped.'
    }

    $requestDirectory = Join-Path $CurrentDataDir 'series'
    if (-not (Test-Path -LiteralPath $requestDirectory -PathType Container)) {
        throw '-CurrentDataDir does not contain the live series directory.'
    }
    $requestPath = Join-Path $requestDirectory '.stop-after-current-match.request'
    if (Test-Path -LiteralPath $requestPath) {
        throw 'A safe-handoff request is already pending for the live runner.'
    }
    $initialSnapshot = Invoke-RestMethod -Uri 'http://127.0.0.1:18700/v1/stream?frame=0' `
        -Method Get -TimeoutSec 2 -ErrorAction Stop
    if (-not $initialSnapshot.series -or $null -eq $initialSnapshot.series.games_played) {
        throw 'The live runner did not expose a verified series count; safe handoff was not requested.'
    }
    if ($initialSnapshot.match.runner_error -or
        [string]$initialSnapshot.match.runner_state -in @('stopped_for_supervision', 'stopped')) {
        throw 'The live runner needs supervision; safe handoff was not requested.'
    }
    $initialGamesPlayed = [int]$initialSnapshot.series.games_played
    $initialMatchIsRecorded = @($initialSnapshot.series.recent_games | Where-Object {
        $_.match_id -eq $initialSnapshot.match.id
    }).Count -gt 0

    $findRunnerProcesses = {
        @(Get-CimInstance Win32_Process | Where-Object {
            $commandLine = ([string]$_.CommandLine).ToLowerInvariant()
            $name = [string]$_.Name
            ($name -in @('python.exe', 'pythonw.exe') -and $commandLine.Contains('tools\link_arena.py') -and $commandLine.Contains($runnerPathToken) -and $commandLine.Contains($currentDataDirToken)) -or
            ($name -eq 'mGBA.exe' -and $commandLine.Contains($runnerPathToken) -and $commandLine.Contains($currentDataDirToken))
        })
    }
    $temporaryRequestPath = "$requestPath.$([Guid]::NewGuid().ToString('N')).tmp"
    $safeBoundaryObserved = [bool]($initialMatchIsRecorded -and
        [string]$initialSnapshot.match.runner_state -in @('complete', 'stopped_for_handoff'))
    try {
        if (-not $safeBoundaryObserved) {
            Set-Content -LiteralPath $temporaryRequestPath -Value 'stop after verified match result' `
                -NoNewline -Encoding Ascii
            Move-Item -LiteralPath $temporaryRequestPath -Destination $requestPath
            $deadline = [DateTime]::UtcNow.AddSeconds($HandoffTimeoutSeconds)
            Write-Output "Waiting for the runner to finish and record its current match (timeout: $HandoffTimeoutSeconds seconds); OBS will stay running."
            while ([DateTime]::UtcNow -lt $deadline) {
                $snapshot = $null
                try {
                    $snapshot = Invoke-RestMethod -Uri 'http://127.0.0.1:18700/v1/stream?frame=0' `
                        -Method Get -TimeoutSec 2 -ErrorAction Stop
                }
                catch {
                    # Poll through brief local API errors, but do not restart on them.
                }

                if ($snapshot -and $snapshot.match) {
                    $state = [string]$snapshot.match.runner_state
                    if ($snapshot.match.runner_error) {
                        throw 'Safe handoff stopped because the current runner reported an error.'
                    }
                    if ($state -eq 'stopped_for_supervision' -or $state -eq 'stopped') {
                        throw 'Safe handoff stopped because the current runner needs supervision.'
                    }
                    if ($state -eq 'stopped_for_handoff' -and
                        [int]$snapshot.series.games_played -gt $initialGamesPlayed) {
                        $safeBoundaryObserved = $true
                        break
                    }
                }
                Start-Sleep -Milliseconds 250
            }
            if (-not $safeBoundaryObserved) {
                throw 'Safe handoff timed out before a verified result was recorded; current tasks were left in place.'
            }
        }
    }
    finally {
        Remove-Item -LiteralPath $temporaryRequestPath -Force -ErrorAction SilentlyContinue
        if (-not $safeBoundaryObserved) {
            Remove-Item -LiteralPath $requestPath -Force -ErrorAction SilentlyContinue
        }
    }

    if ([string]$initialSnapshot.match.runner_state -eq 'complete') {
        Write-Output 'The old runner is already idle at a recorded match cap; stopping its task so the new runner can bind the API port.'
        foreach ($taskName in @('FE7-Link-Arena-Continuous-Runner', 'FE7-Link-Arena-Stream-Runner')) {
            $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
            if ($task -and $task.State -eq 'Running') {
                Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
            }
        }
    } else {
        Write-Output 'The old runner confirmed a recorded-result handoff; waiting for its graceful emulator shutdown.'
    }
    $shutdownWaitSeconds = if ([string]$initialSnapshot.match.runner_state -eq 'complete') { 10 } else { 90 }
    $shutdownDeadline = [DateTime]::UtcNow.AddSeconds($shutdownWaitSeconds)
    while (@(& $findRunnerProcesses).Count -gt 0 -and [DateTime]::UtcNow -lt $shutdownDeadline) {
        Start-Sleep -Milliseconds 250
    }
    if (@(& $findRunnerProcesses).Count -gt 0) {
        Write-Output "Runner shutdown exceeded $shutdownWaitSeconds seconds after the verified result; terminating only the old runner and mGBA."
        foreach ($taskName in @('FE7-Link-Arena-Continuous-Runner', 'FE7-Link-Arena-Stream-Runner')) {
            $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
            if ($task -and $task.State -eq 'Running') {
                Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
            }
        }
        foreach ($process in @(& $findRunnerProcesses)) {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 2
    }
    if (@(& $findRunnerProcesses).Count -gt 0) {
        throw 'The old Link Arena runner did not release its emulator processes after a verified result; OBS remains running.'
    }
}

$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$legacyTaskNames = @('FE7-Link-Arena-Stream-Runner', 'Codex-FE7-Link-Arena-OBS-Setup')
if (-not $replaceRunningProcesses) {
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

$runnerArgumentParts = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $runnerScript),
    '-RepoRoot', ('"{0}"' -f $RunnerRoot), '-Save', ('"{0}"' -f $Save),
    '-DataDir', ('"{0}"' -f $DataDir), '-CredentialPath', ('"{0}"' -f $CredentialPath), '-TwitchChannel', $TwitchChannel,
    '-AutoMinimax', '-Continuous', '-AgentA', $AgentA, '-MaxCompletionTokensA', "$MaxCompletionTokensA",
    '-AgentB', $AgentB, '-MaxCompletionTokensB', "$MaxCompletionTokensB",
    '-AgentTimeout', "$AgentTimeout"
)
if ($AlternateAgentSeats) {
    $runnerArgumentParts += @('-AlternateAgentSeats', '-SeatOrderSeed', "$SeatOrderSeed")
}
if ($MaxMatches -gt 0) { $runnerArgumentParts += @('-MaxMatches', "$MaxMatches") }
if ($ModelA) { $runnerArgumentParts += @('-ModelA', ('"{0}"' -f $ModelA)) }
if ($MinimaxThinkingA) { $runnerArgumentParts += @('-MinimaxThinkingA', $MinimaxThinkingA) }
if ($MinimaxReasoningEffortA) { $runnerArgumentParts += @('-MinimaxReasoningEffortA', $MinimaxReasoningEffortA) }
if ($ModelB) { $runnerArgumentParts += @('-ModelB', ('"{0}"' -f $ModelB)) }
if ($MinimaxThinkingB) { $runnerArgumentParts += @('-MinimaxThinkingB', $MinimaxThinkingB) }
if ($MinimaxReasoningEffortB) { $runnerArgumentParts += @('-MinimaxReasoningEffortB', $MinimaxReasoningEffortB) }
$runnerArguments = $runnerArgumentParts -join ' '
$runnerAction = New-ScheduledTaskAction -Execute $powerShellPath `
    -Argument $runnerArguments -WorkingDirectory $RunnerRoot

$runnerTaskNames = @('FE7-Link-Arena-Continuous-Runner', 'FE7-Link-Arena-Stream-Runner')
$obsTaskNames = @('FE7-Link-Arena-OBS-Watchdog', 'Codex-FE7-Link-Arena-OBS-Setup')
if ($replaceRunningProcesses) {
    $tasksToReplace = @($runnerTaskNames)
    if (-not $preserveObsProcess) { $tasksToReplace += $obsTaskNames }
    foreach ($taskName in $tasksToReplace) {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($task -and $task.State -eq 'Running') {
            Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        }
    }

    $runnerPathToken = $RunnerRoot.TrimEnd('\').ToLowerInvariant()
    $managedProcesses = Get-CimInstance Win32_Process | Where-Object {
        $commandLine = ([string]$_.CommandLine).ToLowerInvariant()
        $name = [string]$_.Name
        $isSelectedDataDir = -not $preserveObsProcess -or $commandLine.Contains($currentDataDirToken)
        ($name -in @('python.exe', 'pythonw.exe') -and $commandLine.Contains('tools\link_arena.py') -and $commandLine.Contains($runnerPathToken) -and $isSelectedDataDir) -or
        ($name -eq 'mGBA.exe' -and $commandLine.Contains($runnerPathToken) -and $isSelectedDataDir) -or
        (-not $preserveObsProcess -and $name -eq 'obs64.exe' -and ([string]$_.ExecutablePath).Equals($ObsPath, [StringComparison]::OrdinalIgnoreCase))
    }
    foreach ($process in $managedProcesses) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    foreach ($taskName in $tasksToReplace) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    }
}

if (-not $preserveObsProcess) {
    Register-ScheduledTask -TaskName 'FE7-Link-Arena-OBS-Watchdog' `
        -Action $obsAction -Trigger $trigger -Settings $settings -Principal $principal `
        -Description 'Keeps the FE7 Link Arena OBS collection running in normal mode for the 24/7 Twitch stream.' `
        -Force | Out-Null
}
Register-ScheduledTask -TaskName 'FE7-Link-Arena-Continuous-Runner' `
    -Action $runnerAction -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Runs verified FE7 Link Arena matches continuously (1P: $AgentA; 2P: $AgentB) and keeps the series score." `
    -Force | Out-Null

if ($replaceRunningProcesses) {
    if (-not $preserveObsProcess) { Start-ScheduledTask -TaskName 'FE7-Link-Arena-OBS-Watchdog' }
    Start-ScheduledTask -TaskName 'FE7-Link-Arena-Continuous-Runner'
    if ($HandoffAtMatchBoundary) {
        $newDataDirToken = $DataDir.TrimEnd('\').ToLowerInvariant()
        $startupDeadline = [DateTime]::UtcNow.AddSeconds(180)
        $newRunnerReady = $false
        Write-Output 'Waiting for the new isolated runner to expose its first match; OBS remains running.'
        while ([DateTime]::UtcNow -lt $startupDeadline) {
            $newRunnerProcesses = @(Get-CimInstance Win32_Process | Where-Object {
                $commandLine = ([string]$_.CommandLine).ToLowerInvariant()
                ([string]$_.Name) -in @('python.exe', 'pythonw.exe') -and
                    $commandLine.Contains('tools\link_arena.py') -and
                    $commandLine.Contains($runnerPathToken) -and
                    $commandLine.Contains($newDataDirToken)
            })
            if ($newRunnerProcesses.Count -eq 1) {
                try {
                    $newSnapshot = Invoke-RestMethod -Uri 'http://127.0.0.1:18700/v1/stream?frame=0' `
                        -Method Get -TimeoutSec 2 -ErrorAction Stop
                    if ($newSnapshot.match.id) {
                        $newSessionPath = Join-Path (Join-Path $DataDir ([string]$newSnapshot.match.id)) 'session.json'
                        if (Test-Path -LiteralPath $newSessionPath -PathType Leaf) {
                            $newRunnerReady = $true
                            break
                        }
                    }
                }
                catch {
                    # The new runner may still be booting mGBA or either link client.
                }
            }
            Start-Sleep -Seconds 1
        }
        if (-not $newRunnerReady) {
            throw 'The new runner did not expose a match within 180 seconds. OBS remains running; inspect the new DataDir runner logs.'
        }
        Write-Output "The new runner is serving match $($newSnapshot.match.id); the existing OBS broadcast was preserved."
    }
}

Write-Output "Installed logon tasks for $currentIdentity."
Write-Output 'OBS scene: FE7 Link Arena; OBS watchdog archives stale recovery markers and starts normal mode.'
Write-Output "Twitch channel: $TwitchChannel; continuous Link Arena score data: $DataDir\series\results.jsonl"
if ($HandoffAtMatchBoundary) {
    Write-Output 'The next experimental runner is running; the existing OBS process and stream were preserved.'
} elseif ($RestartNow) {
    Write-Output 'The current isolated match and OBS process were restarted; both new tasks are running.'
} else {
    Write-Output 'Run again with -RestartNow to replace current processes and start both tasks immediately.'
}
