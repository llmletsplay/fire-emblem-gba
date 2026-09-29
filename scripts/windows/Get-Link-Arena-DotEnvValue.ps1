function Get-LinkArenaDotEnvValue {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $namePattern = [regex]::Escape($Name)
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ($line -match "^\s*(?:export\s+)?$namePattern\s*=\s*(?<value>.*)$") {
            $value = $Matches.value.Trim()
            if ($value.Length -ge 2) {
                $first = $value[0]
                $last = $value[$value.Length - 1]
                if (($first -eq '"' -and $last -eq '"') -or
                    ($first -eq "'" -and $last -eq "'")) {
                    $value = $value.Substring(1, $value.Length - 2)
                }
            }
            return $value
        }
    }
    return $null
}
