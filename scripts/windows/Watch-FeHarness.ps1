<#
.SYNOPSIS
  Restart loop + Discord alerts for unattended FE harness babysitting on Windows.

.DESCRIPTION
  Starts the harness via Start-FeHarness.ps1, waits for exit, then restarts with
  exponential backoff (5s, 15s, 30s, ... capped at 5 minutes). Posts Discord
  webhook alerts on crash/nonzero exit (and optionally on consecutive empty/failed
  LLM actions when detectable from recent logs).

  Reuses the healthcheck Discord shape: JSON POST {"content": "..."} to
  DISCORD_WEBHOOK_URL. No systemctl.

.PARAMETER RepoRoot
  Path to the fe-gba repo root.

.PARAMETER NoFrontend
  Passed through to Start-FeHarness (default $true).

.PARAMETER MaxRestarts
  Stop after this many restarts (0 = unlimited). Default 0.

.PARAMETER AlertCooldownSeconds
  Minimum seconds between Discord alerts (state file under logs/). Default 300.

.PARAMETER EmptyActionThreshold
  Alert if this many consecutive empty/failed LLM action lines appear in recent
  logs. Default 8. Set 0 to disable log-based LLM failure alerts.

.EXAMPLE
  .\scripts\windows\Watch-FeHarness.ps1 -RepoRoot C:\fe-gba
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [bool]$NoFrontend = $true,
    [int]$MaxRestarts = 0,
    [int]$AlertCooldownSeconds = 300,
    [int]$EmptyActionThreshold = 8
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Only one Watch-FeHarness should run. Older babysitters left in backoff will
# otherwise fight over mGBA and cause WinError 10053 / exit-code-1 flaps.
try {
    $myPid = $PID
    Get-CimInstance Win32_Process -Filter "name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessId -ne $myPid -and
            $_.CommandLine -and
            ($_.CommandLine -like '*Watch-FeHarness*')
        } |
        ForEach-Object {
            Write-Host "[watch] Stopping sibling Watch-FeHarness PID $($_.ProcessId)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
} catch {
    Write-Host "[watch] Sibling cleanup skipped: $_"
}

function Write-Log([string]$Message) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $Message"
    Write-Host $line
    if ($script:WatchLogPath) {
        Add-Content -LiteralPath $script:WatchLogPath -Value $line -Encoding UTF8
    }
}

function Resolve-RepoRoot([string]$Hint) {
    if ($Hint) {
        $resolved = (Resolve-Path -LiteralPath $Hint).Path
        if (-not (Test-Path -LiteralPath (Join-Path $resolved "src\core\run.py"))) {
            throw "RepoRoot does not look like fe-gba (missing src\core\run.py): $resolved"
        }
        return $resolved
    }
    $cwd = (Get-Location).Path
    if (Test-Path -LiteralPath (Join-Path $cwd "src\core\run.py")) {
        return $cwd
    }
    $fromScript = Resolve-Path (Join-Path $PSScriptRoot "..\..")
    if (Test-Path -LiteralPath (Join-Path $fromScript "src\core\run.py")) {
        return $fromScript.Path
    }
    throw "Run from the fe-gba repo root, or pass -RepoRoot. Current directory: $cwd"
}

function Import-DotEnv([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { return }
        $key = $line.Substring(0, $eq).Trim()
        $val = $line.Substring($eq + 1).Trim()
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        if (-not $key) { return }
        $existing = [Environment]::GetEnvironmentVariable($key, "Process")
        if ([string]::IsNullOrEmpty($existing)) {
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}

function Send-DiscordAlert([string]$Content) {
    $url = $env:DISCORD_WEBHOOK_URL
    if ([string]::IsNullOrWhiteSpace($url)) {
        Write-Log "Discord alert skipped (DISCORD_WEBHOOK_URL not set): $Content"
        return
    }
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $last = 0
    if (Test-Path -LiteralPath $script:AlertStatePath) {
        try {
            $raw = Get-Content -LiteralPath $script:AlertStatePath -Raw | ConvertFrom-Json
            if ($raw.last_alert_unix) { $last = [int64]$raw.last_alert_unix }
        } catch {
            $last = 0
        }
    }
    if (($now - $last) -lt $AlertCooldownSeconds) {
        Write-Log "Discord alert suppressed (cooldown): $Content"
        return
    }
    $body = @{ content = $Content } | ConvertTo-Json -Compress
    try {
        Invoke-RestMethod -Method Post -Uri $url -ContentType "application/json" -Body $body | Out-Null
        @{ last_alert_unix = $now; last_content = $Content } | ConvertTo-Json |
            Set-Content -LiteralPath $script:AlertStatePath -Encoding UTF8
        Write-Log "Discord alert sent."
    } catch {
        Write-Log "Discord alert failed: $($_.Exception.Message)"
    }
}

function Get-BackoffSeconds([int]$RestartIndex) {
    # 5s, 15s, 30s, then double, cap 5m
    $sequence = @(5, 15, 30)
    if ($RestartIndex -lt $sequence.Count) {
        return $sequence[$RestartIndex]
    }
    $secs = 30 * [math]::Pow(2, ($RestartIndex - 2))
    if ($secs -gt 300) { return 300 }
    return [int]$secs
}

function Test-RecentEmptyLlmActions([string]$LogsDir, [int]$Threshold) {
    if ($Threshold -le 0) { return $false }
    if (-not (Test-Path -LiteralPath $LogsDir)) { return $false }
    $candidates = Get-ChildItem -LiteralPath $LogsDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '\.log$' -and $_.Name -ne 'watch-fe-harness.log' } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 3
    if (-not $candidates) { return $false }

    $patterns = @(
        'No valid action extracted',
        'No valid COMMAND: or ACTION:',
        'Emergency retry returned empty',
        'Rejecting free-form ACTION while legal_moves',
        'MOVE:.*is not in legal_moves',
        'legal_moves build failed',
        'Error during LLM interaction'
    )
    $combined = ($patterns | ForEach-Object { "($_)" }) -join '|'
    $hits = 0
    foreach ($f in $candidates) {
        try {
            $tail = Get-Content -LiteralPath $f.FullName -Tail 200 -ErrorAction SilentlyContinue
            foreach ($line in $tail) {
                if ($line -match $combined) { $hits++ }
            }
        } catch { }
    }
    return ($hits -ge $Threshold)
}

$root = Resolve-RepoRoot $RepoRoot
Set-Location -LiteralPath $root
Import-DotEnv (Join-Path $root ".env")

$logsDir = Join-Path $root "logs"
if (-not (Test-Path -LiteralPath $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}
$script:WatchLogPath = Join-Path $logsDir "watch-fe-harness.log"
$script:AlertStatePath = Join-Path $logsDir "watch-fe-harness-alert-state.json"
$starter = Join-Path $PSScriptRoot "Start-FeHarness.ps1"
if (-not (Test-Path -LiteralPath $starter)) {
    throw "Missing Start-FeHarness.ps1 next to this script: $starter"
}

Write-Log "Watch-FeHarness starting. RepoRoot=$root MaxRestarts=$MaxRestarts NoFrontend=$NoFrontend"
Write-Log "Logging to $script:WatchLogPath"

$restartCount = 0
$skipPipAfterFirst = $false

while ($true) {
    if (($MaxRestarts -gt 0) -and ($restartCount -gt $MaxRestarts)) {
        Write-Log "Reached MaxRestarts=$MaxRestarts; exiting watch loop."
        Send-DiscordAlert "FE harness watch stopped after $MaxRestarts restarts on $env:COMPUTERNAME"
        exit 1
    }

    $args = @{
        RepoRoot   = $root
        NoFrontend = $NoFrontend
        Foreground = $true
    }
    if ($skipPipAfterFirst) {
        $args["SkipPip"] = $true
    }

    Write-Log "Starting harness (restart #$restartCount)..."
    $exitCode = 0
    try {
        & $starter @args
        $exitCode = $LASTEXITCODE
        if ($null -eq $exitCode) { $exitCode = 0 }
    } catch {
        $exitCode = 1
        Write-Log "Start-FeHarness threw: $($_.Exception.Message)"
    }

    $skipPipAfterFirst = $true
    Write-Log "Harness exited with code $exitCode"

    $emptyLlm = Test-RecentEmptyLlmActions -LogsDir $logsDir -Threshold $EmptyActionThreshold
    if ($exitCode -ne 0) {
        Send-DiscordAlert ("FE harness CRASH/exit=$exitCode on {0} (restart #{1}). Check logs/watch-fe-harness.log" -f $env:COMPUTERNAME, $restartCount)
    } elseif ($emptyLlm) {
        Send-DiscordAlert ("FE harness: {0}+ empty/failed LLM action signals in recent logs on {1} (restart #{2})" -f $EmptyActionThreshold, $env:COMPUTERNAME, $restartCount)
    } else {
        Write-Log "Clean exit (code 0); restarting without Discord alert."
    }

    $backoff = Get-BackoffSeconds -RestartIndex $restartCount
    Write-Log "Backing off ${backoff}s before restart..."
    Start-Sleep -Seconds $backoff
    $restartCount++
}
