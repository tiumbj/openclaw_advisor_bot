param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptVersion = '1.2.7'
$warnings = [System.Collections.Generic.List[string]]::new()
$stopped = [System.Collections.Generic.List[int]]::new()
$forceStopped = [System.Collections.Generic.List[object]]::new()

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

function Get-GatewayProcesses {
    param([string]$Root)

    $escapedRoot = [regex]::Escape($Root)
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and
        $_.CommandLine -match 'openclaw' -and
        $_.CommandLine -match 'gateway' -and
        $_.CommandLine -match $escapedRoot -and
        $_.CommandLine -match 'dist\\index\.js'
    }
}

$officialStop = Invoke-OpenClawText -Arguments @('gateway', 'stop')
if ($officialStop.exit_code -ne 0) {
    $warnings.Add("openclaw gateway stop exited with $($officialStop.exit_code)")
}

$leftovers = @(Get-GatewayProcesses -Root $ProjectRoot)
foreach ($proc in $leftovers) {
    $reason = 'OpenClaw gateway process remained after official stop'
    $forceStopped.Add([pscustomobject]@{
        pid         = [int]$proc.ProcessId
        executable  = $proc.ExecutablePath
        commandline = $proc.CommandLine
        reason      = $reason
    })
    Stop-Process -Id $proc.ProcessId -Force
    $stopped.Add([int]$proc.ProcessId)
}

$summary = [ordered]@{
    script_version          = $scriptVersion
    timestamp_utc           = (Get-Date).ToUniversalTime().ToString('o')
    official_stop_exit_code  = $officialStop.exit_code
    official_stop_output     = $officialStop.text
    gateway_processes_stopped = @($stopped)
    force_stop_details       = @($forceStopped)
    warnings                = $warnings
    overall_pass             = ($officialStop.exit_code -eq 0 -and $stopped.Count -eq 0 -and $forceStopped.Count -eq 0)
}

$summary | ConvertTo-Json -Depth 6
if (-not $summary.overall_pass) {
    exit 1
}
exit 0
