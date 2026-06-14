param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptVersion = '1.2.7'
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

    if ($trimmed.Length -lt 32 -or $trimmed -match '^(?i:(changeme|replace.*|your.*|example.*|token.*here|<.*>|none|null|blank))$') {
        $status = 'INVALID'
    }
    else {
        $status = 'SET'
    }

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($trimmed)
        $hash = $sha.ComputeHash($bytes)
    }
    finally {
        $sha.Dispose()
    }

    $fingerprint = ([BitConverter]::ToString($hash) -replace '-', '').ToLowerInvariant().Substring(0, 12)
    return [pscustomobject]@{
        status      = $status
        length      = $trimmed.Length
        fingerprint = $fingerprint
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

function Try-SetPersistentEnv {
    param(
        [string]$Name,
        [string]$Value,
        [ValidateSet('User', 'Machine')] [string]$Target
    )

    try {
        [Environment]::SetEnvironmentVariable($Name, $Value, $Target)
        return $true
    }
    catch {
        $warnings.Add("$Target scope update failed for ${Name}: $($_.Exception.Message)")
        return $false
    }
}

$envFile = Join-Path $ProjectRoot 'state\.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Missing canonical env file: $envFile"
}

$envValues = Read-EnvFile -EnvPath $envFile
$canonicalToken = $envValues['OPENCLAW_GATEWAY_TOKEN']
$canonicalFingerprint = Get-TokenFingerprint $canonicalToken
if ($canonicalFingerprint.status -ne 'SET') {
    $failures.Add('canonical gateway token is missing or invalid in state\.env')
}

foreach ($name in $envValues.Keys) {
    Set-EnvironmentValue -Name $name -Value $envValues[$name]
}

Set-EnvironmentValue -Name 'GROQ_API_KEY' -Value ''
Set-EnvironmentValue -Name 'QROQ_API_KEY' -Value ''

Try-SetPersistentEnv -Name 'OPENCLAW_GATEWAY_TOKEN' -Value $canonicalToken -Target 'User' | Out-Null
Try-SetPersistentEnv -Name 'OPENCLAW_GATEWAY_TOKEN' -Value $canonicalToken -Target 'Machine' | Out-Null
Try-SetPersistentEnv -Name 'GROQ_API_KEY' -Value '' -Target 'User' | Out-Null
Try-SetPersistentEnv -Name 'GROQ_API_KEY' -Value '' -Target 'Machine' | Out-Null
Try-SetPersistentEnv -Name 'QROQ_API_KEY' -Value '' -Target 'User' | Out-Null
Try-SetPersistentEnv -Name 'QROQ_API_KEY' -Value '' -Target 'Machine' | Out-Null

$statusBefore = Invoke-OpenClawText -Arguments @('status', '--json')
$statusJson = $null
try {
    $statusJson = $statusBefore.text | ConvertFrom-Json
}
catch {
    $warnings.Add("openclaw status --json could not be parsed: $($_.Exception.Message)")
}

$gatewayError = if ($statusJson) { [string]$statusJson.gateway.error } else { '' }
$secretDiagnostics = @()
if ($statusJson -and $null -ne $statusJson.secretDiagnostics) {
    $secretDiagnostics = @($statusJson.secretDiagnostics)
}
$driftDetected = $gatewayError -match 'gateway token mismatch|unauthorized' -or $secretDiagnostics.Count -gt 0

if ($driftDetected) {
    $stopResult = Invoke-OpenClawText -Arguments @('gateway', 'stop')
    if ($stopResult.exit_code -ne 0) {
        $warnings.Add("openclaw gateway stop exited with $($stopResult.exit_code)")
    }

    $postStop = Invoke-OpenClawText -Arguments @('gateway', 'status')
    if ($postStop.text -match 'Runtime:\s+running') {
        $warnings.Add('gateway still reported running after official stop; proceeding with reinstall flow')
    }

    $uninstallResult = Invoke-OpenClawText -Arguments @('gateway', 'uninstall')
    if ($uninstallResult.exit_code -ne 0) {
        $warnings.Add("openclaw gateway uninstall exited with $($uninstallResult.exit_code)")
    }

    $installResult = Invoke-OpenClawText -Arguments @('gateway', 'install')
    if ($installResult.exit_code -ne 0) {
        throw "Gateway reinstall failed: $($installResult.text)"
    }

    $startResult = Invoke-OpenClawText -Arguments @('gateway', 'start')
    if ($startResult.exit_code -ne 0) {
        throw "Gateway start failed: $($startResult.text)"
    }
}
elseif ($statusBefore.text -notmatch 'Runtime:\s+running') {
    $startResult = Invoke-OpenClawText -Arguments @('gateway', 'start')
    if ($startResult.exit_code -ne 0) {
        throw "Gateway start failed: $($startResult.text)"
    }
}

$deadline = (Get-Date).AddSeconds(45)
$gatewayReady = $false
$gatewayStatusText = ''
$gatewayProbeText = ''
do {
    Start-Sleep -Seconds 2
    $gatewayStatus = Invoke-OpenClawText -Arguments @('gateway', 'status')
    $gatewayStatusText = $gatewayStatus.text
    $gatewayProbe = Invoke-OpenClawText -Arguments @('gateway', 'probe')
    $gatewayProbeText = $gatewayProbe.text
    $gatewayReady = $gatewayStatusText -match 'Runtime:\s+running' -and $gatewayProbeText -match 'Connect:\s+ok' -and $gatewayProbeText -match 'Read probe:\s+ok'
} while (-not $gatewayReady -and (Get-Date) -lt $deadline)

if (-not $gatewayReady) {
    $failures.Add('gateway did not reach ready state')
}

$configResult = Invoke-OpenClawText -Arguments @('config', 'get', 'gateway')
$configJson = $null
try {
    $configJson = $configResult.text | ConvertFrom-Json
}
catch {
    $warnings.Add("openclaw config get gateway could not be parsed: $($_.Exception.Message)")
}

$gatewayAuthMode = if ($configJson) { [string]$configJson.auth.mode } else { 'unknown' }
$controlUiEnabled = if ($configJson) { [bool]$configJson.controlUi.enabled } else { $false }

$dashboardResult = Invoke-OpenClawText -Arguments @('dashboard', '--no-open', '--yes')
$dashboardUrl = if ($dashboardResult.text -match '(https?://\S+)') { $Matches[1] } else { 'http://127.0.0.1:18789/' }

if ($dashboardResult.exit_code -ne 0) {
    $warnings.Add("openclaw dashboard --no-open --yes exited with $($dashboardResult.exit_code)")
}

$summary = [ordered]@{
    script_version                 = $scriptVersion
    timestamp_utc                  = (Get-Date).ToUniversalTime().ToString('o')
    openclaw_version               = (Invoke-OpenClawText -Arguments @('--version')).text.Trim()
    config_path                    = $envValues['OPENCLAW_CONFIG_PATH']
    gateway_port                   = [int]$envValues['OPENCLAW_GATEWAY_PORT']
    gateway_process_running        = $gatewayReady
    gateway_rpc_ready              = $gatewayReady
    gateway_auth_mode              = $gatewayAuthMode
    canonical_token_status         = $canonicalFingerprint.status
    canonical_token_fingerprint    = $canonicalFingerprint.fingerprint
    process_token_fingerprint      = (Get-TokenFingerprint $env:OPENCLAW_GATEWAY_TOKEN).fingerprint
    service_token_fingerprint      = $null
    token_consistent               = $false
    control_ui_enabled             = $controlUiEnabled
    root_status                    = 0
    root_has_html                  = $false
    websocket_authenticated        = $gatewayReady
    session_read_pass              = $false
    agent_turn_pass                = $false
    agent_turn_marker_found        = $false
    config_unauthenticated_status  = 0
    config_authenticated_status    = 0
    dashboard_url                  = $dashboardUrl
    overall_pass                   = $false
    failures                       = $failures
    warnings                       = $warnings
}

if (Test-Path -LiteralPath (Join-Path $ProjectRoot 'state\openclaw.json')) {
    try {
        $renderedConfig = Get-Content -LiteralPath (Join-Path $ProjectRoot 'state\openclaw.json') -Raw | ConvertFrom-Json
        $serviceToken = [string]$renderedConfig.gateway.auth.token
        $summary.service_token_fingerprint = (Get-TokenFingerprint $serviceToken).fingerprint
    }
    catch {
        $warnings.Add("rendered config token could not be parsed: $($_.Exception.Message)")
    }
}

$summary.token_consistent = @(
    $summary.canonical_token_status -eq 'SET'
    $summary.canonical_token_fingerprint
    $summary.process_token_fingerprint
    $summary.service_token_fingerprint
) -notcontains $null -and $summary.canonical_token_fingerprint -eq $summary.process_token_fingerprint -and $summary.canonical_token_fingerprint -eq $summary.service_token_fingerprint

$rootResponse = $null
try {
    $rootResponse = Invoke-WebRequest -Uri 'http://127.0.0.1:18789/' -UseBasicParsing -TimeoutSec 10
    $summary.root_status = [int]$rootResponse.StatusCode
    $summary.root_has_html = $rootResponse.Content -match '<html'
}
catch {
    $failures.Add("unauthenticated root request failed: $($_.Exception.Message)")
}

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
try {
    $authResponse = Invoke-WebRequest -Uri $dashboardUrl -UseBasicParsing -TimeoutSec 10 -WebSession $session
    $summary.config_authenticated_status = [int]$authResponse.StatusCode
}
catch {
    $warnings.Add("authenticated dashboard bootstrap request failed: $($_.Exception.Message)")
}

try {
    $configUnauth = Invoke-WebRequest -Uri 'http://127.0.0.1:18789/control-ui-config.json' -UseBasicParsing -TimeoutSec 10
    $summary.config_unauthenticated_status = [int]$configUnauth.StatusCode
}
catch {
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
        $summary.config_unauthenticated_status = [int]$_.Exception.Response.StatusCode
    }
    else {
        $failures.Add("unauthenticated config request failed: $($_.Exception.Message)")
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

if ($agentResult.exit_code -eq 0) {
    $summary.session_read_pass = $agentResult.text -match 'session' -or $agentResult.text -match 'sessionId'
    $summary.agent_turn_marker_found = $agentResult.text -match 'P2_4_OPENCLAW_UI_E2E_OK'
    $summary.agent_turn_pass = $summary.session_read_pass -and $summary.agent_turn_marker_found
}
else {
    $failures.Add("agent turn failed with exit code $($agentResult.exit_code)")
    if ($agentResult.text) {
        $warnings.Add($agentResult.text.Trim())
    }
}

$summary.gateway_process_running = $gatewayReady
$summary.gateway_rpc_ready = $gatewayReady
$summary.websocket_authenticated = $gatewayReady -and $summary.session_read_pass
$summary.overall_pass = $summary.gateway_process_running -and
    $summary.gateway_rpc_ready -and
    $summary.token_consistent -and
    $summary.control_ui_enabled -and
    ($summary.root_status -eq 200) -and
    $summary.websocket_authenticated -and
    $summary.session_read_pass -and
    $summary.agent_turn_pass -and
    $summary.agent_turn_marker_found -and
    ($summary.config_unauthenticated_status -in 401, 403) -and
    ($summary.config_authenticated_status -eq 200)

$summary | ConvertTo-Json -Depth 6
if (-not $summary.overall_pass) {
    exit 1
}
exit 0
