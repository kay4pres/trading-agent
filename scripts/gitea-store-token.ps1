# Store Gitea Token
# Run this, paste your token at the prompt, press Enter. That's it.

$credTarget = "gitea:http://10.8.0.10:3000"

Write-Host "Paste your Gitea token and press Enter:" -ForegroundColor Yellow
$Token = Read-Host -AsSecureString
$Plain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Token))

cmdkey /generic:$credTarget /user:mavis-agent /pass:$Plain 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "Token stored in Windows Credential Manager." -ForegroundColor Green
} else {
    Write-Host "Failed." -ForegroundColor Red
}
