<#
.SYNOPSIS
  Non-interactive unattended start of the FE GBA harness (Windows babysitting).

.DESCRIPTION
  Ensures a Python venv, installs requirements, loads .env keys (without printing
  secrets), and starts `python src\core\run.py --auto`.

  Designed for production MiniMax babysitting on Windows (e.g. zephyrus). Does
  not require systemd, FIFOs, Node, or interactive LLM setup when LLM_PROVIDER
  is already set in the environment / .env.

  Frontend is skipped by default (headless). Pass -WithFrontend to start npm.

.PARAMETER RepoRoot
  Path to the fe-gba repo root. Defaults to the current working directory, or
  the directory two levels above this script when cwd is wrong.

.PARAMETER NoFrontend
  Skip React frontend. Default: $true. Pass -NoFrontend:$false or -WithFrontend
  to enable the frontend.

.PARAMETER WithFrontend
  Start the React frontend (overrides default headless behavior).

.PARAMETER Foreground
  Run the harness in the foreground (blocks). When omitted, starts a background
  process and returns process info.

.PARAMETER SkipPip
  Skip pip install (use existing venv packages).

.EXAMPLE
  cd C:\path\to\fe-gba
  .\scripts\windows\Start-FeHarness.ps1 -Foreground

.EXAMPLE
  .\scripts\windows\Start-FeHarness.ps1 -RepoRoot C:\fe-gba -NoFrontend
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [bool]$NoFrontend = $true,
    [switch]$WithFrontend,
    [switch]$Foreground,
    [switch]$SkipPip
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host "[fe-harness] $Message"
}

function Write-Err([string]$Message) {
    Write-Host "[fe-harness] ERROR: $Message" -ForegroundColor Red
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
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    Write-Info "Loading .env (values not printed)"
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
        # Do not override variables already set in the process environment.
        $existing = [Environment]::GetEnvironmentVariable($key, "Process")
        if ([string]::IsNullOrEmpty($existing)) {
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}

$root = Resolve-RepoRoot $RepoRoot
Set-Location -LiteralPath $root
Write-Info "Repo root: $root"

Import-DotEnv (Join-Path $root ".env")

$romFile = $env:ROM_FILE
$feGame = $env:FE_GAME
$provider = $env:LLM_PROVIDER
if ($provider) { $provider = $provider.Trim().ToUpperInvariant() }

$validProviders = @(
    "OPENAI", "ANTHROPIC", "GEMINI", "GROQ", "TOGETHER", "GROK",
    "OLLAMA", "LMSTUDIO", "CUSTOM", "ZAI", "MINIMAX"
)
if (-not $provider) {
    Write-Err "LLM_PROVIDER is not set. Set LLM_PROVIDER=MINIMAX (or another provider) in .env."
    exit 1
}
if ($validProviders -notcontains $provider) {
    Write-Err "Unsupported LLM_PROVIDER='$provider'. Expected one of: $($validProviders -join ', ')"
    exit 1
}

if (-not $romFile) {
    $candidates = @("FE7.gba", "fe7.gba", "FE8.gba", "fe8.gba")
    $found = @()
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath (Join-Path $root "roms\$c")) { $found += $c }
    }
    if ($found.Count -eq 1) {
        $romFile = $found[0]
        $env:ROM_FILE = $romFile
    } else {
        Write-Err "ROM_FILE is not set and could not auto-detect a single ROM under roms\."
        Write-Err "Set ROM_FILE=FE7.gba or ROM_FILE=FE8.gba in .env."
        exit 1
    }
}

$romPath = Join-Path $root "roms\$romFile"
if (-not (Test-Path -LiteralPath $romPath)) {
    Write-Err "ROM file not found: $romPath"
    Write-Err "Place a legally obtained ROM in roms\ and set ROM_FILE in .env."
    exit 1
}

# Provider-specific key check (do not print values)
if ($provider -eq "MINIMAX") {
    if (-not $env:MINIMAX_API_KEY -and -not $env:MINIMAX_TOKEN_PLAN_KEY) {
        Write-Err "LLM_PROVIDER=MINIMAX but MINIMAX_API_KEY is missing from the environment / .env."
        exit 1
    }
}

$pythonBootstrap = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonBootstrap) {
    $pythonBootstrap = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $pythonBootstrap) {
    Write-Err "Python is not installed or not in PATH."
    exit 1
}

$venvDir = Join-Path $root "venv"
$venvPy = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPy)) {
    Write-Info "Creating Python virtual environment..."
    & $pythonBootstrap.Source -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to create venv."
        exit 1
    }
}

$python = $venvPy
Write-Info "Using Python: $python"

if (-not $SkipPip) {
    Write-Info "Installing Python dependencies..."
    & $python -m pip install --upgrade pip | Out-Null
    $req = Join-Path $root "requirements.txt"
    if (-not (Test-Path -LiteralPath $req)) {
        Write-Err "requirements.txt not found at $req"
        exit 1
    }
    & $python -m pip install -r $req
    if ($LASTEXITCODE -ne 0) {
        Write-Err "pip install -r requirements.txt failed."
        exit 1
    }
    $reqWin = Join-Path $root "requirements_windows.txt"
    if (Test-Path -LiteralPath $reqWin) {
        Write-Info "Installing Windows requirements..."
        & $python -m pip install -r $reqWin
        if ($LASTEXITCODE -ne 0) {
            Write-Err "pip install -r requirements_windows.txt failed."
            exit 1
        }
    }
}

# Directories the harness expects
@(
    "fe-client\public\chronicle\screenshots",
    "assets\maps",
    "assets\sprites",
    "screenshots",
    "logs"
) | ForEach-Object {
    $d = Join-Path $root $_
    if (-not (Test-Path -LiteralPath $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
    }
}

$env:LLM_PROVIDER = $provider
Write-Info "LLM_PROVIDER=$provider"
if ($feGame) {
    Write-Info "FE_GAME=$feGame ROM_FILE=$romFile"
} else {
    Write-Info "ROM_FILE=$romFile (FE_GAME will be inferred)"
}

$skipFrontend = $NoFrontend
if ($WithFrontend) { $skipFrontend = $false }

if (-not $skipFrontend) {
    $node = Get-Command node -ErrorAction SilentlyContinue
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $node -or -not $npm) {
        Write-Err "Frontend requested but Node.js/npm not found. Pass -NoFrontend or install Node."
        exit 1
    }
    $feClient = Join-Path $root "fe-client"
    Push-Location $feClient
    try {
        if (-not (Test-Path -LiteralPath "node_modules")) {
            Write-Info "Installing frontend dependencies..."
            npm install --quiet
            if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
        }
        Write-Info "Starting React frontend (background)..."
        Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WorkingDirectory $feClient -WindowStyle Hidden
        Start-Sleep -Seconds 3
    } finally {
        Pop-Location
    }
} else {
    Write-Info "Skipping frontend (headless babysitting)"
}

$runPy = Join-Path $root "src\core\run.py"
$argList = @($runPy, "--auto")
$harnessLog = Join-Path $root "logs\harness.log"
Write-Info "Harness log (append): $harnessLog"

Write-Info "Starting harness: python src\core\run.py --auto"
if ($Foreground) {
    # Append both stdout and stderr so babysitting can tail LLM cycles.
    & $python @argList *>> $harnessLog
    exit $LASTEXITCODE
}

# Background: wrap so both streams append to the same harness.log
$pyEsc = $python.Replace("'", "''")
$logEsc = $harnessLog.Replace("'", "''")
$rootEsc = $root.Replace("'", "''")
$argsEsc = ($argList | ForEach-Object { "'" + ($_ -replace "'", "''") + "'" }) -join ", "
$psCommand = @"
Set-Location -LiteralPath '$rootEsc'
& '$pyEsc' @($argsEsc) *>> '$logEsc'
"@
$proc = Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command", $psCommand
) -WorkingDirectory $root -PassThru -WindowStyle Hidden
Write-Info "Harness PID=$($proc.Id) (logging to logs\harness.log)"
[pscustomobject]@{
    Id           = $proc.Id
    ProcessName  = $proc.ProcessName
    StartTime    = $proc.StartTime
    LLM_PROVIDER = $provider
    ROM_FILE     = $romFile
    RepoRoot     = $root
    LogFile      = $harnessLog
}
