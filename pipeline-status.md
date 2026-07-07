# Pipeline Status — 2026-07-07 13:00 (Berlin, UTC+2)

## Dashboard State
| Field | Value | Notes |
|---|---|---|
| `last_scan` | 20:59 | ✅ Scanner ran yesterday evening (normal — runs 15:30–21:00) |
| `market_open` | true | ✅ |
| `watchlist` | `[]` | ❌ Empty — container can't see today's watchlist |
| `signals` | `[]` | No signals yet today |
| `positions` | `[]` | No open positions |
| `bull_bear` | `[]` | No debates yet |
| `mount_status` | `missing_today_watchlist` | ❌ **Docker can't read today's watchlist CSV** |

## Watchlist File Status
Richard's `premarket-scan` cron (6 AM Berlin) generated today's watchlist:
- `E:\Me\TradingAgent\data\watchlists\watchlist_20260707.csv` ✅ exists (11 stocks)
- `Z:\trading-agent-source\data\watchlists\watchlist_20260707.csv` ✅ synced
- Docker container sees: **nothing** ❌

## fincept_connector.py — No Fix Needed ✅
- Code review: no literal "quote error" string anywhere in the file
- **yfinance fallback is correctly implemented** — runs transparently inside the Linux Docker container (sys.platform != "win32" → skips Fincept Windows path → calls yfinance directly)
- Both `get_quote()` and `get_batch_quotes()` fall back on failure
- **No push needed** for fincept_connector.py

## Root Cause — Docker Volume Mount Points to Wrong Path

**docker-compose.yml (Portainer):**
```yaml
volumes:
  - /volume1/Docker/data:/app/data    # ← WRONG PATH
```

**Richard's premarket cron syncs to:**
```
Z:\trading-agent-source\data\watchlists\watchlist_20260707.csv
```
→ Maps to `\\10.8.0.10\Home\backups\trading-agent-source\data\watchlists\` on the NAS

**Docker container looks for data at:**
```
/volume1/Docker/data/watchlists/
```
→ Completely different filesystem path on the Synology — **container never sees the Z: share**

## Evidence
- `watchlist_20260707.csv` exists on Z: ✅ (written 04:00 today by premarket-scan cron)
- Z: share NOT accessible from Docker container via `/volume1/Docker/data` ❌
- `mount_status: "missing_today_watchlist"` in dashboard confirms it ❌
- Scanner currently running on DEFAULT_UNIVERSE (hardcoded stock list) — no gap-up watchlist input

## Fix Required — DevOps Agent

**Two options (pick one):**

### Option A — Fix Portainer stack volume mount (preferred)
1. Go to Portainer at `http://10.8.0.10:9000`
2. Stacks → trading-agent → Editor
3. Change the data volume mount from:
   ```
   /volume1/Docker/data:/app/data
   ```
   To the Z: share path on the Synology filesystem. **You must find this path:**
   - Log into Synology DSM admin panel
   - Go to Control Panel → Shared Folders
   - Find the "Home backups" share (this is Z:)
   - Note the filesystem path (typically `/volume1/homes/backups/` or similar)
   - Update the mount to: `<Z_share_fs_path>/trading-agent-source/data:/app/data`
4. Recreate the container

### Option B — Create a symlink on the NAS
SSH to NAS as admin:
```bash
ln -s /<z_share_fs_path>/trading-agent-source/data /volume1/Docker/data
```
Then restart the Docker container.

### After the fix
- Redeploy the container so it picks up the corrected volume mount
- The `premarket_screener.py`'s existing `_sync_to_nas_share()` (→ Z: share) will then work
- Richard's `sync_watchlist_to_nas.ps1` (also → Z: share) will also work
- Dashboard `mount_status` should change from `missing_today_watchlist` to OK

## What's Working
- ✅ Dashboard alive on port 5050
- ✅ Scanner cron active (last ran yesterday 20:59)
- ✅ yfinance fallback (data layer healthy even without Fincept)
- ✅ Telegram alerts wired
- ✅ `premarket-scan` cron ran at 6 AM Berlin → generated 11-stock watchlist
- ✅ Z: share sync works (file exists on NAS)

## What's Broken
- ❌ Docker volume mount — container can't read Richard's watchlist from Z: share
- ❌ Scanner using hardcoded DEFAULT_UNIVERSE instead of today's gap-up watchlist
- ❌ Richard's premarket output not reaching Docker

## Cron Health
- `premarket-scan`: ✅ Ran today at 04:00 Berlin — generated watchlist_20260707.csv
- `scan-market`: ✅ Active (last scan yesterday 20:59)
- `pipeline-check`: ✅ Running now (this session)

## Today's Watchlist (11 stocks, generated 04:00 Berlin)
SPHL, LHSW, FXHO, YDES, PEW, SEER, CRE, WBX, ZCMD, SONM, GDEV
