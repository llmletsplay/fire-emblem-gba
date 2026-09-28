[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$Rom,
    [string]$Save,
    [string]$DataDir,
    [string]$CredentialPath,
    [string]$Mgba,
    [string]$MgbaLogLevel,
    [string]$TwitchChannel = 'llmletsplay',
    [switch]$AutoMinimax,
    [ValidateSet('minimax', 'chutes', 'minimax-api')]
    [string]$AgentA = 'minimax',
    [string]$ModelA,
    [string]$BaseUrlA,
    [string]$ApiKeyEnvA,
    [ValidateSet('adaptive', 'disabled')]
    [string]$MinimaxThinkingA,
    [ValidateSet('low', 'medium', 'high', 'xhigh', 'max')]
    [string]$MinimaxReasoningEffortA,
    [ValidateRange(1, 204800)]
    [int]$MaxCompletionTokensA = 2048,
    [ValidateSet('minimax', 'chutes', 'minimax-api')]
    [string]$AgentB = 'minimax',
    [string]$ModelB,
    [string]$BaseUrlB,
    [string]$ApiKeyEnvB,
    [ValidateSet('adaptive', 'disabled')]
    [string]$MinimaxThinkingB,
    [ValidateSet('low', 'medium', 'high', 'xhigh', 'max')]
    [string]$MinimaxReasoningEffortB,
    [ValidateRange(1, 204800)]
    [int]$MaxCompletionTokensB = 2048,
    [ValidateRange(1, 600)]
    [double]$AgentTimeout = 120,
    [switch]$Continuous,
    [switch]$ManualSetup,
    [ValidateRange(0.05, 30)]
    [double]$AutoPollInterval = 0.5,
    [ValidateRange(0.5, 120)]
    [double]$AutoSettleTimeout = 60,
    [ValidateRange(0, 600)]
    [double]$BetweenMatchesSeconds = 8,
    [ValidateRange(1024, 65532)]
    [int]$BasePort = 18888,
    [ValidateRange(1, 65535)]
    [int]$ApiPort = 18700,
    [ValidateRange(1, 120)]
    [int]$StartupTimeout = 20
)

$ErrorActionPreference = 'Stop'
if ($Continuous -and -not ($AutoMinimax -or $AgentA -ne 'minimax' -or $AgentB -ne 'minimax')) {
    throw 'Continuous mode requires -AutoMinimax or at least one hosted model policy.'
}
if (($AutoMinimax -or $AgentA -ne 'minimax' -or $AgentB -ne 'minimax') -and $ManualSetup) {
    throw 'Autonomous policies cannot be combined with -ManualSetup.'
}
if ($AgentA -ne 'minimax' -and -not $ModelA) { throw '-ModelA is required for a hosted seat A policy.' }
if ($AgentB -ne 'minimax' -and -not $ModelB) { throw '-ModelB is required for a hosted seat B policy.' }
$RepoRoot = (Resolve-Path $RepoRoot).Path
$Runner = Join-Path $RepoRoot 'tools\link_arena.py'
if (-not (Test-Path $Runner)) {
    throw "Link Arena runner not found: $Runner"
}
$RunnerDataDir = $DataDir
if (-not $RunnerDataDir) {
    $RunnerDataDir = Join-Path $env:LOCALAPPDATA 'FE7-Link-Arena'
}
New-Item -ItemType Directory -Force -Path $RunnerDataDir | Out-Null
$RunnerLog = Join-Path $RunnerDataDir 'stream-runner.log'
$RunnerErrorLog = Join-Path $RunnerDataDir 'stream-runner-errors.log'

$HasHostedAgent = ($AgentA -ne 'minimax' -or $AgentB -ne 'minimax')
if ($HasHostedAgent) {
    if (-not $CredentialPath) {
        $CredentialPath = Join-Path $env:LOCALAPPDATA 'FE7-Link-Arena\secrets\provider-credentials.dpapi.json'
    }
    $CredentialImporter = Join-Path $PSScriptRoot 'Import-Link-Arena-Credentials.ps1'
    if (-not (Test-Path -LiteralPath $CredentialImporter -PathType Leaf)) {
        throw "Hosted policies require the credential importer: $CredentialImporter"
    }
    & $CredentialImporter -CredentialPath $CredentialPath
    $selectedProviders = @()
    foreach ($provider in @($AgentA, $AgentB)) {
        if ($provider -ne 'minimax') { $selectedProviders += $provider }
    }
    foreach ($provider in @($selectedProviders | Select-Object -Unique)) {
        $credentialName = if ($provider -eq 'chutes') { 'CHUTES_API_KEY' } else { 'MINIMAX_API_KEY' }
        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($credentialName, 'Process'))) {
            throw "Hosted policy '$provider' requires a locally saved $credentialName. Run Set-Link-Arena-ProviderCredentials.ps1 as this Windows user."
        }
    }
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
if ($TwitchChannel) { $Arguments += @('--twitch-channel', $TwitchChannel) }
if ($AutoMinimax) { $Arguments += '--auto-minimax' }
if ($AgentA -ne 'minimax') { $Arguments += @('--agent-a', $AgentA, '--model-a', $ModelA) }
if ($BaseUrlA) { $Arguments += @('--base-url-a', $BaseUrlA) }
if ($ApiKeyEnvA) { $Arguments += @('--api-key-env-a', $ApiKeyEnvA) }
if ($MinimaxThinkingA) { $Arguments += @('--minimax-thinking-a', $MinimaxThinkingA) }
if ($MinimaxReasoningEffortA) { $Arguments += @('--minimax-reasoning-effort-a', $MinimaxReasoningEffortA) }
$Arguments += @('--max-completion-tokens-a', $MaxCompletionTokensA)
if ($AgentB -ne 'minimax') { $Arguments += @('--agent-b', $AgentB, '--model-b', $ModelB) }
if ($BaseUrlB) { $Arguments += @('--base-url-b', $BaseUrlB) }
if ($ApiKeyEnvB) { $Arguments += @('--api-key-env-b', $ApiKeyEnvB) }
if ($MinimaxThinkingB) { $Arguments += @('--minimax-thinking-b', $MinimaxThinkingB) }
if ($MinimaxReasoningEffortB) { $Arguments += @('--minimax-reasoning-effort-b', $MinimaxReasoningEffortB) }
$Arguments += @('--max-completion-tokens-b', $MaxCompletionTokensB)
if ($AgentA -ne 'minimax' -or $AgentB -ne 'minimax') { $Arguments += @('--agent-timeout', $AgentTimeout) }
if ($Continuous) {
    $Arguments += '--continuous'
    $Arguments += @('--between-matches-seconds', $BetweenMatchesSeconds)
}
if ($ManualSetup) { $Arguments += '--manual-setup' }
$Arguments += @('--auto-poll-interval', $AutoPollInterval, '--auto-settle-timeout', $AutoSettleTimeout)
$Arguments += @('--base-port', $BasePort, '--api-port', $ApiPort)
$Arguments += @('--startup-timeout', $StartupTimeout)

Push-Location $RepoRoot
try {
    $ProcessArguments = @($PythonArgs + $Arguments) | ForEach-Object {
        $argument = [string]$_
        if ($argument -match '\s') {
            '"' + $argument.Replace('"', '\"') + '"'
        } else {
            $argument
        }
    }
    $Process = Start-Process -FilePath $Python.Source `
        -ArgumentList ($ProcessArguments -join ' ') `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $RunnerLog `
        -RedirectStandardError $RunnerErrorLog `
        -Wait -PassThru
    $ExitCode = $Process.ExitCode
}
finally {
    Pop-Location
}
exit $ExitCode
