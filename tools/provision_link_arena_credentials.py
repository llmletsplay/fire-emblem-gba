#!/usr/bin/env python3
"""Provision local .env provider keys into Zephyrus' user-bound DPAPI store.

Only the selected provider values travel over the configured SSH connection,
on stdin. They are never placed in a process argument or printed. PowerShell
encrypts them with current-user DPAPI before replacing the protected file.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
REMOTE_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$inputText = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($inputText)) { throw 'No provider values arrived on stdin.' }
$payload = $inputText | ConvertFrom-Json -ErrorAction Stop
if ($payload.schema_version -ne 1) { throw 'Unsupported provider payload schema.' }

$credentialPath = Join-Path $env:LOCALAPPDATA 'FE7-Link-Arena\secrets\provider-credentials.dpapi.json'
$secretDir = Split-Path -Parent $credentialPath
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null
$values = [ordered]@{ schema_version = 1; CHUTES_API_KEY = $null; MINIMAX_API_KEY = $null }
if (Test-Path -LiteralPath $credentialPath -PathType Leaf) {
    $current = Get-Content -LiteralPath $credentialPath -Raw | ConvertFrom-Json -ErrorAction Stop
    if ($current.schema_version -ne 1) { throw 'Unsupported credential-file schema.' }
    foreach ($name in @('CHUTES_API_KEY', 'MINIMAX_API_KEY')) {
        $saved = $current.$name
        if ($saved -is [string] -and $saved.Length -gt 0) { $values[$name] = $saved }
    }
}

$updated = @()
foreach ($name in @('CHUTES_API_KEY', 'MINIMAX_API_KEY')) {
    $plain = $payload.$name
    if ($plain -isnot [string] -or [string]::IsNullOrEmpty($plain)) { continue }
    $secure = ConvertTo-SecureString -String $plain -AsPlainText -Force
    try { $values[$name] = ConvertFrom-SecureString -SecureString $secure }
    finally { $secure.Dispose(); $plain = $null }
    $updated += $name
}
if ($updated.Count -eq 0) { throw 'No provider credentials were supplied.' }

$temporaryPath = "$credentialPath.$([Guid]::NewGuid().ToString('N')).tmp"
try {
    $json = $values | ConvertTo-Json -Depth 3
    Set-Content -LiteralPath $temporaryPath -Value $json -Encoding UTF8
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    & icacls.exe $temporaryPath /inheritance:r /grant:r "${identity}:(F)" 'SYSTEM:(F)' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not restrict credential-file access.' }
    Move-Item -LiteralPath $temporaryPath -Destination $credentialPath -Force
}
finally {
    Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
}
Write-Output ('LINKARENA_CREDENTIALS_OK ' + ($updated -join ','))
"""


def _local_provider_values(env_file: Path) -> dict[str, str]:
    parsed = dotenv_values(env_file)
    values: dict[str, str] = {}
    chutes = parsed.get("CHUTES_API_KEY")
    minimax = parsed.get("MINIMAX_API_KEY") or parsed.get("MINIMAX_TOKEN_PLAN_KEY")
    if isinstance(chutes, str) and chutes.strip():
        values["CHUTES_API_KEY"] = chutes
    if isinstance(minimax, str) and minimax.strip():
        values["MINIMAX_API_KEY"] = minimax
    if not values:
        raise ValueError("No CHUTES_API_KEY, MINIMAX_API_KEY, or MINIMAX_TOKEN_PLAN_KEY is set in the selected .env.")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="SSH host alias or hostname for the Windows runner")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env", help="local dotenv file; values are never printed")
    parser.add_argument("--timeout", type=float, default=45.0, help="SSH provisioning timeout in seconds")
    args = parser.parse_args()
    try:
        values = _local_provider_values(args.env_file.expanduser().resolve())
    except (OSError, ValueError) as exc:
        print(f"Credential provisioning stopped: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps({"schema_version": 1, **values}, separators=(",", ":")).encode("utf-8")
    encoded_script = base64.b64encode(REMOTE_SCRIPT.encode("utf-16le")).decode("ascii")
    command = [
        "ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
        args.host, "powershell.exe", "-NoProfile", "-NonInteractive",
        "-EncodedCommand", encoded_script,
    ]
    try:
        result = subprocess.run(
            command, input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=args.timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        print("Credential provisioning timed out; no secret values were printed.", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"Credential provisioning could not start SSH ({type(exc).__name__}).", file=sys.stderr)
        return 4

    output = result.stdout.decode("utf-8", errors="replace")
    if result.returncode != 0 or "LINKARENA_CREDENTIALS_OK" not in output:
        print(f"Credential provisioning failed (SSH exit code {result.returncode}); remote details suppressed.", file=sys.stderr)
        return 5
    updated_names = output.split("LINKARENA_CREDENTIALS_OK", 1)[1].strip().splitlines()[0].strip()
    print(f"DPAPI credentials updated on {args.host}: {updated_names}. Secret values were not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
