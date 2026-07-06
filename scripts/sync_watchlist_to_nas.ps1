# sync_watchlist_to_nas.ps1
# Copies Richard's premarket watchlist to the NAS Z: share
# so the Docker container can access it at /app/data/watchlists/

$SourceDir = "E:\Me\TradingAgent\data\watchlists"
$ZShareDir = "Z:\trading-agent-source\data\watchlists"
$TodayFile = "watchlist_$(Get-Date -Format 'yyyyMMdd').csv"
$LatestFile = "watchlist_latest.csv"

# Create Z: destination dir if missing
if (-not (Test-Path $ZShareDir)) {
    New-Item -Path $ZShareDir -ItemType Directory -Confirm:$false | Out-Null
    Write-Host "[sync] Created $ZShareDir"
}

# Sync today's watchlist
$SourceToday = Join-Path $SourceDir $TodayFile
$DestToday   = Join-Path $ZShareDir $TodayFile
if (Test-Path $SourceToday) {
    Copy-Item -Path $SourceToday -Destination $DestToday -Confirm:$false -Force
    Write-Host "[sync] Copied $TodayFile -> Z: share"
} else {
    Write-Host "[sync] WARNING: $SourceToday not found"
}

# Sync latest alias
$SourceLatest = Join-Path $SourceDir $LatestFile
$DestLatest   = Join-Path $ZShareDir $LatestFile
if (Test-Path $SourceLatest) {
    Copy-Item -Path $SourceLatest -Destination $DestLatest -Confirm:$false -Force
    Write-Host "[sync] Copied $LatestFile -> Z: share"
}

Write-Host "[sync] Done. Files in Z: share:"
Get-ChildItem $ZShareDir | Select-Object Name,Length | Format-Table
