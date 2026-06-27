# dashboard_keepalive.ps1
# Creates a Windows scheduled task that keeps the dashboard running 24/7
# Run once to install, run again to update

$TaskName = "TradingAgent-Dashboard"
$ScriptPath = "E:\Me\TradingAgent\dashboard\app.py"
$WorkingDir = "E:\Me\TradingAgent\dashboard"
$PyExe = (Get-Command py -ErrorAction SilentlyContinue).Source
if (-not $PyExe) {
    $PyExe = "python"
}

$Action = New-ScheduledTaskAction -Execute $PyExe -Argument "app.py" -WorkingDirectory $WorkingDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Restart on failure: retry every 1 minute, up to 3 times
$Settings.RestartInterval = "00:01:00"
$Settings.RestartCount = 3
$Settings.StopIfNotBumpedOn = $false

# Unregister existing task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Register new task
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Kay's Trading Agent Dashboard keepalive" | Out-Null

Write-Output "Dashboard keepalive installed. Task: $TaskName"
Write-Output "Dashboard will auto-start at login and restart if it crashes."
Write-Output "To remove: Unregister-ScheduledTask -TaskName '$TaskName'"
