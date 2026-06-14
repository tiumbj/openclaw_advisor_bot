param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Import-CanonicalEnv {
    param([string]$EnvPath)

    if (-not (Test-Path -LiteralPath $EnvPath)) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $EnvPath) {
        $trim = $line.Trim()
        if (-not $trim -or $trim.StartsWith('#')) {
            continue
        }
        if ($trim -notmatch '^(?<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?<value>.*)$') {
            continue
        }
        $key = $Matches.key.Trim()
        $value = $Matches.value.Trim()
        if ($value.StartsWith('"') -and $value.EndsWith('"') -and $value.Length -ge 2) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        Set-Item -Path "Env:$key" -Value $value
    }

    Remove-Item -Path 'Env:GROQ_API_KEY' -ErrorAction SilentlyContinue
}

Import-CanonicalEnv -EnvPath (Join-Path $ProjectRoot 'state\.env')

$baseUri = 'http://127.0.0.1:18789'
$results = [ordered]@{
    root_status = 0
    root_has_html = $false
    root_has_thai = $false
}

try {
    $rootResponse = Invoke-WebRequest -Uri "$baseUri/" -UseBasicParsing -TimeoutSec 10
    $results.root_status = [int]$rootResponse.StatusCode
    $results.root_has_html = $rootResponse.Content -match '<html'
    $results.root_has_thai = $rootResponse.Content -match 'ไทย'
} catch {
    $results.root_error = $_.Exception.Message
}

try {
    $configResponse = Invoke-WebRequest -Uri "$baseUri/control-ui-config.json" -UseBasicParsing -TimeoutSec 10 -MaximumRedirection 0
    $results.config_status = [int]$configResponse.StatusCode
} catch {
    $results.config_error = $_.Exception.Message
}

try {
    $status = & openclaw gateway status
    $results.gateway_status = ($status -join "`n")
} catch {
    $results.gateway_error = $_.Exception.Message
}

$results | ConvertTo-Json -Depth 6
if ($results.root_status -ne 200) {
    exit 1
}
exit 0
