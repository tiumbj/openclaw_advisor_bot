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

$envFile = Join-Path $ProjectRoot 'state\.env'
Import-CanonicalEnv -EnvPath $envFile

$status = & openclaw gateway status
$status_text = $status -join "`n"
if ($LASTEXITCODE -ne 0 -or $status_text -match 'Service not installed|Service unit not found|Scheduled Task \(missing\)') {
    & openclaw gateway install | Out-Null
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

if ($status_text -match 'Runtime:\s+stopped' -or $status_text -match 'Service not installed|Service unit not found|Scheduled Task \(missing\)') {
    & openclaw gateway start | Out-Null
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $deadline = (Get-Date).AddSeconds(20)
    do {
        Start-Sleep -Seconds 2
        $status = & openclaw gateway status
        $status_text = $status -join "`n"
    } while ((($status_text -match 'Runtime:\s+stopped') -or ($status_text -match 'Service not installed|Service unit not found|Scheduled Task \(missing\)')) -and ((Get-Date) -lt $deadline))
}

& openclaw dashboard --no-open
exit $LASTEXITCODE
