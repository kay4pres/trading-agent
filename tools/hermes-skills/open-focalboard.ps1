# Focalboard Verify Helper
# Decrypts the password from DPAPI vault and opens the DevOps Sprint board URL in your default browser.
# Run this on Kay's Windows machine to verify the board state quickly.

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security
$vault = "$PSScriptRoot\..\..\vault\focalboard_password.enc"
$vault = (Resolve-Path $vault).Path

$encBytes = [IO.File]::ReadAllBytes($vault)
$decrypted = [System.Security.Cryptography.ProtectedData]::Unprotect(
    $encBytes, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
$password = [System.Text.Encoding]::UTF8.GetString($decrypted)

Write-Host "=== Focalboard Verify Helper ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Username: Ai_agent_01"
Write-Host "Password: $password"
Write-Host ""
Write-Host "Board URL: http://10.8.0.10:9087/bzzy9qg1dabfutdsyb8us5r1x8r"
Write-Host ""
Write-Host "Opening board in default browser..." -ForegroundColor Green

# Open the board URL — the user just needs to log in
Start-Process "http://10.8.0.10:9087/bzzy9qg1dabfutdsyb8us5r1x8r"

Write-Host ""
Write-Host "If 'Create a board' appears, the board is missing — log in then create it." -ForegroundColor Yellow
Write-Host "If board loads with cards, board is fine — check 'Group by:' filter if cards hidden." -ForegroundColor Yellow
Write-Host ""
Write-Host "Login tip: use Enter key on password field, NOT button click. Wait 4-5 sec." -ForegroundColor Cyan

# Clean up
Remove-Variable decrypted, password
