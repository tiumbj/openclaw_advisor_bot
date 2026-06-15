param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptVersion = '1.2.12'
$warnings = [System.Collections.Generic.List[string]]::new()
$failures = [System.Collections.Generic.List[string]]::new()

function Get-TokenFingerprint {
    param([string]$Value)

    if ($null -eq $Value) {
        return [pscustomobject]@{
            status      = 'MISSING'
            length      = 0
            fingerprint = $null
        }
    }

    $trimmed = $Value.Trim().Trim('"').Trim("'")
    if ([string]::IsNullOrWhiteSpace($trimmed)) {
        return [pscustomobject]@{
            status      = 'MISSING'
            length      = 0
            fingerprint = $null
        }
    }

    $status = if ($trimmed.Length -lt 32 -or $trimmed -match '^(?i:(changeme|replace.*|your.*|example.*|token.*here|<.*>|none|null|blank))$') {
        'INVALID'
    }
    else {
        'SET'
    }

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($trimmed)
        $hash = $sha.ComputeHash($bytes)
    }
    finally {
        $sha.Dispose()
    }

    [pscustomobject]@{
        status      = $status
        length      = $trimmed.Length
        fingerprint = (([BitConverter]::ToString($hash) -replace '-', '').ToLowerInvariant()).Substring(0, 12)
    }
}

function Read-EnvFile {
    param([string]$EnvPath)

    $values = [ordered]@{}
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
        $values[$key] = $value
    }

    return $values
}

function Set-EnvironmentValue {
    param(
        [string]$Name,
        [string]$Value
    )

    if ([string]::IsNullOrEmpty($Value)) {
        Remove-Item -Path "Env:$Name" -ErrorAction SilentlyContinue
        return
    }

    Set-Item -Path "Env:$Name" -Value $Value
}

function Invoke-OpenClawText {
    param([string[]]$Arguments)

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & openclaw @Arguments 2>&1
        return [pscustomobject]@{
            exit_code = $LASTEXITCODE
            text      = ($output -join "`n")
        }
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}

$envFile = Join-Path $ProjectRoot 'state\.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Missing canonical env file: $envFile"
}

$envValues = Read-EnvFile -EnvPath $envFile
foreach ($name in $envValues.Keys) {
    Set-EnvironmentValue -Name $name -Value $envValues[$name]
}
Set-EnvironmentValue -Name 'GROQ_API_KEY' -Value ''
Set-EnvironmentValue -Name 'QROQ_API_KEY' -Value ''

$canonicalToken = $envValues['OPENCLAW_GATEWAY_TOKEN']
$canonicalFingerprint = Get-TokenFingerprint $canonicalToken
$processFingerprint = Get-TokenFingerprint $env:OPENCLAW_GATEWAY_TOKEN

$renderedConfig = $null
$serviceTokenFingerprint = $null
$runtimeTokenSource = 'unknown'
$runtimeTokenVariable = $null
try {
    $renderedConfig = Get-Content -LiteralPath (Join-Path $ProjectRoot 'state\openclaw.json') -Raw | ConvertFrom-Json
    $tokenRef = $renderedConfig.gateway.auth.token
    if ($tokenRef -is [string]) {
        $runtimeTokenSource = 'literal'
        $serviceTokenFingerprint = (Get-TokenFingerprint $tokenRef).fingerprint
    }
    elseif ($tokenRef.source -eq 'env' -and -not [string]::IsNullOrWhiteSpace([string]$tokenRef.id)) {
        $runtimeTokenSource = 'env'
        $runtimeTokenVariable = [string]$tokenRef.id
        $serviceTokenFingerprint = (Get-TokenFingerprint ([string]$envValues[$runtimeTokenVariable])).fingerprint
    }
    else {
        $warnings.Add('rendered config token SecretRef is unsupported or missing an env id')
    }
}
catch {
    $warnings.Add("rendered config token could not be read: $($_.Exception.Message)")
}

$statusResult = Invoke-OpenClawText -Arguments @('status', '--json')
$statusJson = $null
try {
    $statusJson = $statusResult.text | ConvertFrom-Json
}
catch {
    $warnings.Add("openclaw status --json could not be parsed: $($_.Exception.Message)")
}

$gatewayStatus = Invoke-OpenClawText -Arguments @('gateway', 'status')
$gatewayProbe = Invoke-OpenClawText -Arguments @('gateway', 'probe')
$configResult = Invoke-OpenClawText -Arguments @('config', 'get', 'gateway')
$configJson = $null
try {
    $configJson = $configResult.text | ConvertFrom-Json
}
catch {
    $warnings.Add("openclaw config get gateway could not be parsed: $($_.Exception.Message)")
}
$configUnauthenticatedStatus = 0
$configAuthenticatedStatus = 0
$rootStatus = 0
$rootHasHtml = $false
$dashboardUrl = 'http://127.0.0.1:18789/'
$dashboardUrlDisplay = $dashboardUrl
$dashboardAuthToken = $null

try {
    $dashboardBootstrap = Invoke-OpenClawText -Arguments @('dashboard', '--no-open', '--yes')
    if ($dashboardBootstrap.text -match '(https?://\S+)') {
        $dashboardUrl = $Matches[1]
    }
    try {
        $clipboardUrl = Get-Clipboard
        if ($clipboardUrl -match '^https?://') {
            $dashboardUrl = $clipboardUrl
        }
    }
    catch {
        $warnings.Add("dashboard clipboard token could not be read: $($_.Exception.Message)")
    }
    try {
        $parsedUrl = [uri]$dashboardUrl
        if ($parsedUrl.Fragment) {
            $fragment = $parsedUrl.Fragment.TrimStart('#')
            if ($fragment -match '^token=(?<token>.+)$') {
                $dashboardAuthToken = [uri]::UnescapeDataString($Matches.token)
            }
            elseif ($fragment) {
                $dashboardAuthToken = [uri]::UnescapeDataString($fragment)
            }
        }
    }
    catch {
        $warnings.Add("dashboard token fragment could not be parsed: $($_.Exception.Message)")
    }
    $dashboardUrlDisplay = $dashboardUrl -replace '#.*$', '#<redacted>'
}
catch {
    $warnings.Add("dashboard bootstrap failed: $($_.Exception.Message)")
}

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
try {
    $rootResponse = Invoke-WebRequest -Uri 'http://127.0.0.1:18789/' -UseBasicParsing -TimeoutSec 10
    $rootStatus = [int]$rootResponse.StatusCode
    $rootHasHtml = $rootResponse.Content -match '<html'
}
catch {
    $failures.Add("unauthenticated root request failed: $($_.Exception.Message)")
}

try {
    Invoke-WebRequest -Uri $dashboardUrl -UseBasicParsing -TimeoutSec 10 -WebSession $session | Out-Null
    $configUnauthenticated = Invoke-WebRequest -Uri 'http://127.0.0.1:18789/control-ui-config.json' -UseBasicParsing -TimeoutSec 10
    $configUnauthenticatedStatus = [int]$configUnauthenticated.StatusCode
}
catch {
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
        $configUnauthenticatedStatus = [int]$_.Exception.Response.StatusCode
    }
    else {
        $warnings.Add("config bootstrap failed: $($_.Exception.Message)")
    }
}

try {
    $headers = @{}
    if ($dashboardAuthToken) {
        $headers['Authorization'] = "Bearer $dashboardAuthToken"
    }
    elseif ($canonicalToken) {
        $headers['Authorization'] = "Bearer $canonicalToken"
    }
    $configAuthenticated = Invoke-WebRequest -Uri 'http://127.0.0.1:18789/control-ui-config.json' -UseBasicParsing -TimeoutSec 10 -WebSession $session -Headers $headers
    $configAuthenticatedStatus = [int]$configAuthenticated.StatusCode
}
catch {
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
        $configAuthenticatedStatus = [int]$_.Exception.Response.StatusCode
        if ($configAuthenticatedStatus -ne 200 -and $canonicalToken) {
            try {
                $configAuthenticated = Invoke-WebRequest -Uri 'http://127.0.0.1:18789/control-ui-config.json' -UseBasicParsing -TimeoutSec 10 -WebSession $session -Headers @{ Authorization = "Bearer $canonicalToken" }
                $configAuthenticatedStatus = [int]$configAuthenticated.StatusCode
            }
            catch {
                if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
                    $configAuthenticatedStatus = [int]$_.Exception.Response.StatusCode
                }
                else {
                    $warnings.Add("canonical authenticated config request failed: $($_.Exception.Message)")
                }
            }
        }
    }
    else {
        $warnings.Add("authenticated config request failed: $($_.Exception.Message)")
    }
}

$agentResult = Invoke-OpenClawText -Arguments @(
    'agent',
    '--agent', 'super-advisor',
    '--message', 'Return exactly: P2_4_OPENCLAW_UI_E2E_OK. Do not call tools or modify the system.',
    '--thinking', 'off',
    '--timeout', '120',
    '--json'
)

$agentTurnPass = $false
$agentMarkerFound = $false
$sessionReadPass = $false
$websocketAuthenticated = $false
if ($agentResult.exit_code -eq 0) {
    $agentMarkerFound = $agentResult.text -match 'P2_4_OPENCLAW_UI_E2E_OK'
    $sessionReadPass = $agentResult.text -match 'sessionId' -or $agentResult.text -match 'session'
    $websocketAuthenticated = $gatewayProbe.text -match 'Connect:\s+ok' -and $gatewayProbe.text -match 'Read probe:\s+ok'
    $agentTurnPass = $agentMarkerFound -and $sessionReadPass -and $websocketAuthenticated
}
else {
    $failures.Add("agent turn failed with exit code $($agentResult.exit_code)")
    if ($agentResult.text) {
        $warnings.Add($agentResult.text.Trim())
    }
}

$tokenConsistent = $canonicalFingerprint.status -eq 'SET' -and
    $canonicalFingerprint.fingerprint -eq $processFingerprint.fingerprint -and
    ($null -ne $serviceTokenFingerprint) -and
    $canonicalFingerprint.fingerprint -eq $serviceTokenFingerprint

$controlUiEnabled = $false
$gatewayAuthMode = 'unknown'
if ($configJson) {
    $controlUiEnabled = [bool]$configJson.controlUi.enabled
    $gatewayAuthMode = [string]$configJson.auth.mode
}
if ($statusJson) {
    if ($statusJson.gateway.error -match 'gateway token mismatch|unauthorized') {
        $failures.Add([string]$statusJson.gateway.error)
    }
}

$probeConnectOk   = $gatewayProbe.text -match 'Connect:\s+ok'
$probeReadOk      = $gatewayProbe.text -match 'Read probe:\s+ok'
$noTokenMismatch  = $failures.Count -eq 0 -or -not ($failures -match 'token mismatch|unauthorized')

$gatewayAuthPass  = $probeConnectOk -and $tokenConsistent -and ($configAuthenticatedStatus -eq 200)
$statusProbePass  = $probeConnectOk -and $probeReadOk -and $noTokenMismatch
$uiBootstrapPass  = ($rootStatus -eq 200) -and $rootHasHtml -and $agentTurnPass -and $agentMarkerFound

$overallPass = $statusProbePass -and
    $gatewayAuthPass -and
    $uiBootstrapPass -and
    $tokenConsistent -and
    $controlUiEnabled -and
    $websocketAuthenticated -and
    $sessionReadPass -and
    ($configUnauthenticatedStatus -in 401, 403) -and
    ($configAuthenticatedStatus -eq 200)

$summary = [ordered]@{
    script_version                = $scriptVersion
    timestamp_utc                 = (Get-Date).ToUniversalTime().ToString('o')
    openclaw_version              = (Invoke-OpenClawText -Arguments @('--version')).text.Trim()
    config_path                   = $envValues['OPENCLAW_CONFIG_PATH']
    gateway_port                  = [int]$envValues['OPENCLAW_GATEWAY_PORT']
    gateway_process_running       = $probeConnectOk
    gateway_rpc_ready             = $probeReadOk
    gateway_auth_mode             = $gatewayAuthMode
    runtime_token_source          = $runtimeTokenSource
    runtime_token_variable        = $runtimeTokenVariable
    canonical_token_status        = $canonicalFingerprint.status
    canonical_token_fingerprint   = $canonicalFingerprint.fingerprint
    process_token_fingerprint     = $processFingerprint.fingerprint
    service_token_fingerprint     = $serviceTokenFingerprint
    token_consistent              = $tokenConsistent
    gateway_auth_pass             = $gatewayAuthPass
    status_probe_pass             = $statusProbePass
    ui_bootstrap_pass             = $uiBootstrapPass
    control_ui_enabled            = $controlUiEnabled
    root_status                   = $rootStatus
    root_has_html                 = $rootHasHtml
    websocket_authenticated       = $websocketAuthenticated
    session_read_pass             = $sessionReadPass
    agent_turn_pass               = $agentTurnPass
    agent_turn_marker_found       = $agentMarkerFound
    config_unauthenticated_status = $configUnauthenticatedStatus
    config_authenticated_status   = $configAuthenticatedStatus
    dashboard_url                 = $dashboardUrlDisplay
    overall_pass                  = $overallPass
    failures                      = $failures
    warnings                      = $warnings
}

$summary | ConvertTo-Json -Depth 6
if (-not $overallPass) {
    exit 1
}
exit 0
