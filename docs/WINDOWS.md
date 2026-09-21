# Windows runbook (MiniMax unattended babysitting)

Short guide for running the FE GBA harness on Windows (e.g. zephyrus) with
`LLM_PROVIDER=MINIMAX`, without Linux streaming (RTMP / FIFOs / systemd).

## 1. Checkout

```powershell
git clone https://github.com/llmletsplay/fire-emblem-gba.git
cd fire-emblem-gba
git checkout feat/minimax-harness-refresh
git pull
```

Or use your existing local checkout (e.g. under `repos\llmletsplay-fire-emblem\fe-gba`).

## 2. Python venv + deps

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements_windows.txt
```

`Start-FeHarness.ps1` will create the venv and install both requirements files
automatically if you skip this step.

## 3. `.env` keys

Copy `.env.example` → `.env` and set at least:

| Key | Example / notes |
|-----|-----------------|
| `LLM_PROVIDER` | `MINIMAX` |
| `MINIMAX_API_KEY` | Token Plan / API key (never commit) |
| `MINIMAX_MODEL` | `MiniMax-M2.5` |
| `MINIMAX_BASE_URL` | `https://api.minimax.io/v1` |
| `ROM_FILE` | `FE7.gba` or `FE8.gba` (place ROM under `roms\`) |
| `FE_GAME` | `fe7` or `fe8` (optional; inferred from ROM) |
| `DISCORD_WEBHOOK_URL` | Channel webhook for crash/restart alerts |

Do **not** commit `.env`, `roms\*`, or API keys.

Interactive LLM setup is skipped when `LLM_PROVIDER` is already set.
`scripts\windows\start.bat` accepts `MINIMAX` in its provider allow-list.

## 4. One-shot start (foreground)

From the repo root:

```powershell
.\scripts\windows\Start-FeHarness.ps1 -Foreground
```

Useful flags:

- `-RepoRoot C:\path\to\fe-gba` — if not already in the repo root
- `-NoFrontend` / default headless — skips React/npm (recommended for babysitting)
- `-WithFrontend` — also start `fe-client` (`npm run dev`)
- `-SkipPip` — reuse an existing venv without reinstalling

This runs `python src\core\run.py --auto`. Requires Python on PATH, a valid
ROM path, and provider credentials. No systemd, FIFOs, or Node when headless.

## 5. Watch / restart babysitting

```powershell
.\scripts\windows\Watch-FeHarness.ps1 -RepoRoot (Get-Location)
```

Behavior:

- Starts the harness, waits for exit, then restarts with backoff: 5s → 15s → 30s → … capped at 5 minutes
- Logs to `logs\watch-fe-harness.log`
- Discord alerts (`{"content": "..."}` POST) on crash / nonzero exit; optional
  signal when recent logs show many empty/failed LLM actions
- Alert cooldown state: `logs\watch-fe-harness-alert-state.json`
- Params: `-MaxRestarts`, `-RepoRoot`, `-NoFrontend`, `-AlertCooldownSeconds`,
  `-EmptyActionThreshold`

Leave this PowerShell window running (or register a Scheduled Task that runs
`Watch-FeHarness.ps1` at logon).

## 6. Linux / WSL streaming follow-up

RTMP ingest, named FIFOs, and systemd units under `scripts/stream` and
`scripts/healthcheck` are **Linux/WSL** concerns. They are not started by the
Windows babysitting scripts. See `docs/STREAMING.md` when you wire Twitch/RTMP
from WSL or a Linux host.

## Quick smoke checklist

1. `.env` has `LLM_PROVIDER=MINIMAX` + `MINIMAX_API_KEY` + `ROM_FILE`
2. `roms\%ROM_FILE%` exists
3. `.\scripts\windows\Start-FeHarness.ps1 -Foreground` connects to mGBA and requests MiniMax
4. `Watch-FeHarness.ps1` restarts after a forced kill and (if configured) posts to Discord
