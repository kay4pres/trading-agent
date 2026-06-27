# alpaca_secret.ps1
# Double-click this file to enter your Alpaca secret key.
# A popup box will appear. Type your secret and click OK.
# The secret is written to a temp file and displayed briefly for confirmation.
# Nothing is saved to disk.

Add-Type -AssemblyName Microsoft.VisualBasic

$secret = [Microsoft.VisualBasic.Interaction]::InputBox(
    "Enter your Alpaca Secret Key.`n`nIt will NOT be saved — just copy it to use in the connector.",
    "Alpaca Secret Key",
    ""
)

if ([string]::IsNullOrWhiteSpace($secret)) {
    Write-Host "No secret entered. Closing." -ForegroundColor Yellow
    Start-Sleep 2
    exit
}

# Show first 4 and last 4 chars as confirmation
$shown = $secret.Substring(0, [Math]::Min(4, $secret.Length)) + "..." + $secret.Substring([Math]::Max(0, $secret.Length - 4))
Write-Host ""
Write-Host "Secret received: $shown" -ForegroundColor Green
Write-Host "Now run: py -3 trading_agent\alpaca_connector.py --test" -ForegroundColor Cyan
Write-Host "The connector will ask again next time."
Start-Sleep 4
