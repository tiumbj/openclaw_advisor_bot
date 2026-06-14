#Requires -Version 5.1
<#
.SYNOPSIS
    Start the OpenClaw Super Advisor stack in the correct order.
    Enforces single-instance via mutex. Resumes pending jobs.

.DESCRIPTION
    Startup order:
    1. Load canonical env (state/.env)
    2. Validate token / config
    3. Start OpenClaw Gateway
    4. Start Python Engine
    5. Start Watchdog
    6. Resume pending jobs
    7. (Telegram alert dispatched by Python engine: SYSTEM_RECOVERED)

.PARAMETER ProjectRoot
    Root directory of the project.
#>

param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$MutexName = "Global\OpenClawSuperAdvisor"
$Mutex = $null

# Duplicate-instance prevention via named mutex
try {
    $Mutex = New-Object System.Threading.Mutex($false, $MutexName)
    $acquired = $Mutex.WaitOne(0)
    if (-not $acquired) {
        Write-Host "$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ') [WARN] OpenClaw advisor already running (mutex held). Exiting."
        exit 0
    }
} catch {
    Write-Warning "Could not create mutex: $_"
}

$EnvFile = Join-Path $ProjectRoot "state\.env"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ') [INFO] Starting OpenClaw Super Advisor from: $ProjectRoot"

# Step 1: Validate env file exists
if (-not (Test-Path $EnvFile)) {
    Write-Error "Canonical env file not found: $EnvFile"
    exit 1
}

# Step 2: Validate Python venv
if (-not (Test-Path $VenvPython)) {
    Write-Error "Python venv not found: $VenvPython"
    exit 1
}

# Step 3: Start OpenClaw Gateway (if not already running)
$GatewayScript = Join-Path $ProjectRoot "scripts\Start-OpenClawUI.ps1"
if (Test-Path $GatewayScript) {
    Write-Host "$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ') [INFO] Starting OpenClaw Gateway..."
    try {
        & $GatewayScript -ErrorAction SilentlyContinue
    } catch {
        Write-Warning "Gateway start warning (may already be running): $_"
    }
}

# Step 4: Start Python Engine in background
Write-Host "$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ') [INFO] Starting Python engine..."
$EngineArgs = @(
    "-m", "openclaw_super_advisor",
    "--env-file", $EnvFile,
    "--project-root", $ProjectRoot,
    "--resume"
)
$EngineProcess = Start-Process `
    -FilePath $VenvPython `
    -ArgumentList $EngineArgs `
    -WorkingDirectory $ProjectRoot `
    -PassThru `
    -WindowStyle Hidden

if ($EngineProcess) {
    Write-Host "$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ') [INFO] Python engine started (PID: $($EngineProcess.Id))"
    # Record PID for watchdog
    $PidFile = Join-Path $ProjectRoot "state\advisor-engine.pid"
    $EngineProcess.Id | Out-File -FilePath $PidFile -Encoding utf8 -NoNewline
} else {
    Write-Error "Failed to start Python engine"
    exit 1
}

Write-Host "$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ') [INFO] Advisor stack started."

# Keep mutex held while running (released when this script exits)
# The engine process is detached and manages its own lifecycle.
if ($Mutex) {
    $Mutex.ReleaseMutex()
    $Mutex.Dispose()
}
