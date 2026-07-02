# dashboard_keepalive.ps1
# Creates a Windows scheduled task that keeps the dashboard running 24/7

$TaskName = "TradingAgent-Dashboard"
$WorkingDir = "E:\Me\TradingAgent\dashboard"

# Find python
$PyExe = (Get-Command py -ErrorAction SilentlyContinue).Source
if (-not $PyExe) { $PyExe = "python" }

# Remove existing
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Build task
$Action   = New-ScheduledTaskAction -Execute $PyExe -Argument "app.py" -WorkingDirectory $WorkingDir
$Trigger  = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register
$Task = Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Kay's Trading Agent Dashboard" -ErrorAction Stop

# Set restart: retry every 60s, max 3 attempts (via COM)
try {
    $sh = New-Object -ComObject Schedule.Service
    $sh.Connect()
    $rootFolder = $sh.GetFolder("\")
    $taskDef = $sh.GetTask("\$TaskName").Definition
    $taskDef.Settings.RestartCount = 3
    $taskDef.Settings.RestartInterval = "PT1M"
    $rootFolder.RegisterTaskDefinition($TaskName, $taskDef, 6, $null, $null, $null) | Out-Null
    Write-Output "Restart interval set via COM (PT1M, 3 retries)"
} catch {
    Write-Output "COM restart setup skipped (task still created)"
}

Write-Output ""
Write-Output "Task '$TaskName' installed successfully."
Write-Output "Start now:     Start-ScheduledTask -TaskName '$TaskName'"
Write-Output "Check status: Get-ScheduledTaskInfo -TaskName '$TaskName'"
Write-Output "Remove task:  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
