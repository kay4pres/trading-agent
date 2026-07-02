# alpaca_secret.ps1
# One-time setup: store Alpaca secret key to DPAPI vault.
# Double-click this file, enter your secret, done forever.

Add-Type -AssemblyName Microsoft.VisualBasic

$secret = [Microsoft.VisualBasic.Interaction]::InputBox(
    "Enter your Alpaca Secret Key." + [char]10 + [char]10 +
    "Encrypted with Windows DPAPI -- only your account can decrypt." + [char]10 +
    "Saved to: E:\Me\TradingAgent\vault\alpaca_secret.enc",
    "Alpaca Secret -- One-Time Setup",
    ""
)

if ([string]::IsNullOrWhiteSpace($secret)) {
    Write-Host "No secret entered. Closing." -ForegroundColor Yellow
    Start-Sleep 2
    exit
}

# Write secret to a temp file (no trailing newline)
$tmp = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tmp, $secret, [System.Text.Encoding]::UTF8)

# Write Python runner to a temp .py file
$pyFile = [System.IO.Path]::GetTempFileName() + ".py"
$pyCode = @"
import sys
sys.path.insert(0, r'E:\Me\TradingAgent')
from trading_agent.alpaca_connector import _store_secret_to_vault
secret = open(r'$tmp', encoding='utf-8').read()
ok = _store_secret_to_vault(secret)
print('OK' if ok else 'FAILED')
"@
[System.IO.File]::WriteAllText($pyFile, $pyCode, [System.Text.Encoding]::UTF8)

# Run it
$output = python $pyFile 2>&1

# Clean up
Remove-Item $tmp -ErrorAction SilentlyContinue
Remove-Item $pyFile -ErrorAction SilentlyContinue

if ($output -match 'OK') {
    Write-Host ""
    Write-Host "Secret stored securely." -ForegroundColor Green
    Write-Host "E:\Me\TradingAgent\vault\alpaca_secret.enc" -ForegroundColor Gray
    Write-Host ""
    Write-Host "The live_event_loop auto-reads it -- no more prompts." -ForegroundColor Cyan
    Start-Sleep 3
} else {
    Write-Host ""
    Write-Host "Storage failed: $output" -ForegroundColor Red
    Start-Sleep 4
}
