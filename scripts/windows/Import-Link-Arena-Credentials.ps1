[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CredentialPath
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $CredentialPath -PathType Leaf)) { return }
$payload = Get-Content -LiteralPath $CredentialPath -Raw | ConvertFrom-Json -ErrorAction Stop
if ($payload.schema_version -ne 1) {
    throw 'Unsupported Link Arena credential file schema.'
}

foreach ($name in @('CHUTES_API_KEY', 'MINIMAX_API_KEY')) {
    $encrypted = $payload.$name
    if (-not ($encrypted -is [string]) -or $encrypted.Length -eq 0) { continue }
    $secure = ConvertTo-SecureString -String $encrypted -ErrorAction Stop
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        $secure.Dispose()
        $value = $null
    }
}
