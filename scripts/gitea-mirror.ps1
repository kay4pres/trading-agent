# Mirror Gitea main to GitHub
# Run after merging dev -> main on Gitea

# Get GitHub PAT from environment
$Pat = $env:GITHUB_PAT
if (-not $Pat) {
    Write-Host "Set GitHub PAT first:" -ForegroundColor Yellow
    Write-Host '  $env:GITHUB_PAT = "ghp_your_token"; E:\Me\TradingAgent\scripts\gitea-mirror.ps1' -ForegroundColor Gray
    exit 1
}

Push-Location E:\Me\TradingAgent

# Ensure main is up to date
git fetch gitea main

# Merge dev into main locally
git checkout main
git merge gitea/dev --no-edit

# Push to Gitea main
git push gitea main

# Push to GitHub
git push "https://$Pat@github.com/kay4pres/trading-agent.git" main

Pop-Location

Write-Host ""
Write-Host "mirrored: Gitea main -> GitHub main" -ForegroundColor Green
