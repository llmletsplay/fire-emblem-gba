[CmdletBinding()]
param(
    [string]$CredentialPath = (Join-Path $env:LOCALAPPDATA 'FE7-Link-Arena\secrets\provider-credentials.dpapi.json'),
    [string]$EnvFile,
    [switch]$ClearChutes,
    [switch]$ClearMiniMax
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Get-Link-Arena-DotEnvValue.ps1')
if ($EnvFile -and -not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Provider environment file not found: $EnvFile"
}
$CredentialPath = [System.IO.Path]::GetFullPath($CredentialPath)
$SecretDir = Split-Path -Parent $CredentialPath
New-Item -ItemType Directory -Force -Path $SecretDir | Out-Null

$values = [ordered]@{
    schema_version = 1
    CHUTES_API_KEY = $null
    MINIMAX_API_KEY = $null
}
if (Test-Path -LiteralPath $CredentialPath -PathType Leaf) {
    $current = Get-Content -LiteralPath $CredentialPath -Raw | ConvertFrom-Json -ErrorAction Stop
    if ($current.schema_version -ne 1) {
        throw 'Unsupported Link Arena credential file schema.'
    }
    foreach ($name in @('CHUTES_API_KEY', 'MINIMAX_API_KEY')) {
        $encrypted = $current.$name
        if ($encrypted -is [string] -and $encrypted.Length -gt 0) {
            $values[$name] = $encrypted
        }
    }
}

if ($ClearChutes) { $values.CHUTES_API_KEY = $null }
if ($ClearMiniMax) { $values.MINIMAX_API_KEY = $null }

function Protect-LinkArenaCredential {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PlainText
    )
    if ([string]::IsNullOrEmpty($PlainText)) { return $null }
    $secureValue = ConvertTo-SecureString -String $PlainText -AsPlainText -Force
    try {
        return ConvertFrom-SecureString -SecureString $secureValue
    }
    finally {
        $secureValue.Dispose()
    }
}

if ($EnvFile) {
    if (-not $ClearChutes) {
        $plain = Get-LinkArenaDotEnvValue -Path $EnvFile -Name 'CHUTES_API_KEY'
        if ($plain) { $values.CHUTES_API_KEY = Protect-LinkArenaCredential $plain }
        $plain = $null
    }
    if (-not $ClearMiniMax) {
        $plain = Get-LinkArenaDotEnvValue -Path $EnvFile -Name 'MINIMAX_API_KEY'
        if (-not $plain) {
            $plain = Get-LinkArenaDotEnvValue -Path $EnvFile -Name 'MINIMAX_TOKEN_PLAN_KEY'
        }
        if ($plain) { $values.MINIMAX_API_KEY = Protect-LinkArenaCredential $plain }
        $plain = $null
    }
}
elseif (-not $ClearChutes) {
    $secret = Read-Host 'Chutes API key (press Enter to keep the saved key)' -AsSecureString
    if ($secret.Length -gt 0) {
        $values.CHUTES_API_KEY = ConvertFrom-SecureString -SecureString $secret
    }
    $secret.Dispose()
}
if (-not $EnvFile -and -not $ClearMiniMax) {
    $secret = Read-Host 'MiniMax API / Token Plan key (not Code login; Enter keeps saved key)' -AsSecureString
    if ($secret.Length -gt 0) {
        $values.MINIMAX_API_KEY = ConvertFrom-SecureString -SecureString $secret
    }
    $secret.Dispose()
}

if (-not $values.CHUTES_API_KEY -and -not $values.MINIMAX_API_KEY) {
    Remove-Item -LiteralPath $CredentialPath -Force -ErrorAction SilentlyContinue
    Write-Output 'No provider credentials are saved.'
    exit 0
}

$json = $values | ConvertTo-Json -Depth 3
$temporaryPath = "$CredentialPath.$([Guid]::NewGuid().ToString('N')).tmp"
Set-Content -LiteralPath $temporaryPath -Value $json -Encoding UTF8
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $temporaryPath /inheritance:r /grant:r "${identity}:(F)" 'SYSTEM:(F)' | Out-Null
if ($LASTEXITCODE -ne 0) {
    Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
    throw 'Could not restrict access to the encrypted provider credential file.'
}
Move-Item -LiteralPath $temporaryPath -Destination $CredentialPath -Force
Write-Output 'Provider credentials saved using current-user Windows DPAPI. Secret values were not printed.'
