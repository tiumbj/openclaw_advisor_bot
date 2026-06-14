param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$target = 'openclaw'
$matches = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^pwsh(\.exe)?$|^powershell(\.exe)?$' -and
    $_.CommandLine -match 'openclaw' -and
    $_.CommandLine -match 'gateway' -and
    $_.CommandLine -match [regex]::Escape($ProjectRoot)
}

foreach ($proc in $matches) {
    Stop-Process -Id $proc.ProcessId -Force
}

[pscustomobject]@{
    stopped = @($matches | Select-Object -ExpandProperty ProcessId)
} | ConvertTo-Json -Depth 4
