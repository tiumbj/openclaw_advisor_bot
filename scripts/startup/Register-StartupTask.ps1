#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Register OpenClaw Super Advisor as a Windows Task Scheduler task.
    Safe to run multiple times (idempotent).

.DESCRIPTION
    Creates a scheduled task that starts the advisor stack on Windows logon.
    Checks for existing task before creating to prevent duplicates.
    Requires administrator privileges.

.PARAMETER ProjectRoot
    Root directory of the project. Defaults to the parent of this script's directory.

.PARAMETER TaskName
    Name for the scheduled task. Defaults to "OpenClawSuperAdvisor".

.PARAMETER Unregister
    If specified, removes the scheduled task instead of creating it.
#>

param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$TaskName = "OpenClawSuperAdvisor",
    [switch]$Unregister
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($Unregister) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Unregistered task: $TaskName"
    } else {
        Write-Host "Task not found: $TaskName"
    }
    exit 0
}

# Prevent duplicate registration
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Task already registered: $TaskName (skipping)"
    exit 0
}

$startScript = Join-Path $PSScriptRoot "Start-AdvisorStack.ps1"
if (-not (Test-Path $startScript)) {
    Write-Error "Startup script not found: $startScript"
    exit 1
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -WindowStyle Hidden -File `"$startScript`" -ProjectRoot `"$ProjectRoot`"" `
    -WorkingDirectory $ProjectRoot

$trigger = New-ScheduledTaskTrigger -AtLogon

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "OpenClaw Super Advisor 24/7 research platform auto-start" `
    -Force | Out-Null

Write-Host "Registered task: $TaskName"
Write-Host "It will run at next logon from: $startScript"
