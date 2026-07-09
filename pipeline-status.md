# Pipeline Status — 2026-07-09 15:00 (Berlin, UTC+2)

## Dashboard State
| Field | Value | Notes |
|---|---|---|
| `last_scan` | 14:41 | 🟡 Pre-market scan — market opens 15:30 Berlin |
| `market_open` | **true** | 🔴 STALE — bug: never resets to False after close (FIXED) |
| `watchlist` | 4 stocks | NVVE, IOTR, TVRD, ZTG (Jul 8 premarket — stale) |
| `signals` | 0 (manual scan) | Watchlist stocks not qualifying today — normal for thin Wed |
| `bull_bear` | `[]` | 🔴 Ran at 15:00 against stale Jul 8 signals → no debate |
| `mount_status` | `ok` | ✅ Today's watchlist CSV in container |
| `pillars` | `{}` (empty) | Normal for premarket_csv source |

## Two Bugs Found & Fixed — Container Rebuild Required ⚠️

### Bug 1 — `market_open` Never Resets to `False` 🔴 → ✅ FIXED
- **File:** `dashboard/app.py:scan_thread` (line ~589)
- **Root cause:** `state['market_open'] = True` only set inside `if market_status()`. Never reset when market closes.
- **Evidence:** Dashboard showed `market_open: true` at 15:05 Berlin (market opens 15:30). Stale from pre-market scan.
- **Fix:** Added `state['market_open'] = market_status()` every iteration outside the if-block. ✅
- **Commit:** `e0a0561` → Gitea `dev` → GitHub Actions auto-rebuild

### Bug 2 — Bull/Bear Cron Reads Stale Signals 🔴 → ✅ FIXED
- **File:** `scripts/bull_bear_runner.py:main()`
- **Root cause:** Cron fires at 15:00 Berlin. Scan_thread writes fresh `signals_live.json` ~15:01 (market opens 15:30 → scan runs → writes). Bull/Bear reads yesterday's file.
- **Evidence:** `bull_bear: []` — ran at 15:00 against Jul 8 signals (NVVE, IOTR, TVRD, ZTG). None qualified → empty results.
- **Fix:** Added `_signals_are_fresh()` guard — skips if `signals_live.json` >5 min old. Prints skip message. ✅
- **Commit:** `e0a0561` → Gitea `dev` → GitHub Actions auto-rebuild

### fincept_connector.py: ✅ HEALTHY
No "quote error" anywhere. yfinance fallback solid, None guards confirmed. No changes needed.

## Scanner Status
- `last_scan: 14:41` → pre-market scan from yesterday evening session. Scanner alive.
- Manual `/api/scan` POST at 15:04 → 0 signals (watchlist stocks don't qualify today — normal).
- Bull/Bear cron: fires every 30 min 15:00–20:45 Berlin. Freshness guard now prevents stale reads.

## Actions
- ✅ Both bugs fixed: `e0a0561` on Gitea `dev`
- ⚠️ Container rebuild needed — GitHub Actions auto-rebuilds from Gitea `dev` push
- No IM notification needed — rebuild picks fixes up automatically

---

# Pipeline Status — 2026-07-08 14:00 (Berlin, UTC+2)

## Dashboard State
| Field | Value | Notes |
|---|---|---|
| `last_scan` | 20:59 | 🟡 Yesterday — scanner died at market close, not yet recovered |
| `market_open` | false | 🔴 Too early — scanner activates at 15:30 Berlin |
| `watchlist` | 7 stocks | 🟡 Yesterday's premarket signals (LHSW, PEW, SEER, WBX, SPHL, CRE, YDES) |
| `signals` | 7 signals | Same as watchlist — all from `scan_time: 20260707` |
| `positions` | `[]` | No open positions |
| `bull_bear` | `[]` | No debates today |
| `mount_status` | `ok` | ✅ NAS volume mounted |
| `pillars` | `{}` (empty) | 🔴 Will auto-fix once container is rebuilt (see below) |

## Root Cause Analysis

### Why `last_scan` Is Stuck at Yesterday (20:59)

The `scan_thread` in `dashboard/app.py` was dying silently — no outer try/except guard existed
in the old container image. When the thread crashed at or after market close yesterday (20:59),
Docker auto-restarted it (compose has `restart: unless-stopped`), but the thread loop had no
guard, so it could die again on the next iteration.

**The fix IS on `origin/main`** — commit `42f7915` ("fix(dashboard): scan_thread outer try/except —
prevent silent daemon death"). This was pushed in the `4fc50bf` merge to main this morning.

### Why `pillars` Are Empty

The `pillars: {}` empty state on all signals has two contributing factors:
1. `ca0ff79` + `f9b82d9` added live Five Pillars scoring — commits are on `origin/main` ✅
2. **Container hasn't been rebuilt** — Docker is still running SHA `4fc50bf` minus the latest changes

### Why Container Hasn't Been Rebuilt

GitHub Actions workflow (`build-deploy.yml`) fails at "Docker login to NAS registry" because:
- `NAS_REGISTRY_USER` secret: **NOT SET** in GitHub Actions
- `NAS_REGISTRY_PASS` secret: **NOT SET** in GitHub Actions
- `PORTAINER_WEBHOOK_URL` secret: **NOT SET** in GitHub Actions

The image is on GitHub (`kay4pres/trading-agent`) but cannot be pushed to `nas:5000`.

## Code Status (git)
| Commit | Branch | In Docker? | Notes |
|---|---|---|---|
| `91ec0c9` | `dev` | ❌ NO | scan_thread outer guard + docs — NOT on main yet |
| `42f7915` | `origin/main` | ❌ NO | scan_thread outer try/except — fix committed, not deployed |
| `f9b82d9` | `origin/main` | ❌ NO | live Five Pillars scoring for CSV signals |
| `ca0ff79` | `origin/main` | ❌ NO | pillars_json CSV column fix |
| `4fc50bf` | `origin/main` | ⚠️ RUNNING | current container SHA (pre-fix) |

## What's NOT Working Right Now

### 🔴 Container Not Rebuilt (blocks everything)
The Docker image on `nas:5000/trading-agent:latest` is frozen at an old SHA.
All recent fixes (scan_thread guard, pillars_json) are committed but not deployed.
**Fix options (in priority order):**

#### Option A: Set GitHub Actions Secrets (best)
1. Go to: https://github.com/kay4pres/trading-agent/settings/secrets/actions
2. Add `NAS_REGISTRY_USER` — Synology NAS username
3. Add `NAS_REGISTRY_PASS` — Synology NAS password
4. Add `PORTAINER_WEBHOOK_URL` — get from Portainer → Stack → trading-agent → Webhooks
5. Trigger workflow: `gh workflow run build-deploy.yml --repo kay4pres/trading-agent`
   (or manually from GitHub Actions UI)
6. Portainer webhook recreates container → new image pulled → fixes deployed

#### Option B: Manual NAS rebuild (if NAS credentials differ from registry)
On Synology NAS, run:
```bash
cd /volume1/docker/trading-agent
git pull origin main
docker build -t nas:5000/trading-agent:latest ./docker
docker push nas:5000/trading-agent:latest
```
Then Portainer → Containers → trading-agent → Recreate

#### Option C: Skip Docker rebuild — run scanner from Windows directly
If NAS can't be reached, run `scripts/scan_market_bull_bear.py` from Windows at 15:30.
This bypasses the container entirely for the Bull/Bear pipeline.

### 🟡 Bull/Bear LLM Key (blocks live debate)
`vault/llm_api_key.enc` — status unknown (permission denied to check).
Kay needs to run: `E:\Me\TradingAgent\vault\store_llm_key.ps1`
Without this, Bull/Bear debates run in "simulated" mode (no real LLM).

## What IS Working
- ✅ Dashboard alive on port 5050
- ✅ NAS volume mount OK
- ✅ Telegram alerts wired
- ✅ `market_status()` correctly returns False before 15:30 Berlin

## Timeline
- **14:00** (now): `market_status()` = False → scan_thread idle
- **15:30**: `market_status()` becomes True → scan_thread activates (with current old image)
- **15:30**: If container not rebuilt — scan_thread may still die silently (old code, no guard)
- **15:30**: Richard premarket (on Synology cron) should produce `watchlist_20260708.csv`

## Today's Signals (7 stocks, 2026-07-07 premarket — stale)
| Symbol | Price | Gap | RelVol | Float | Score | P4 |
|---|---|---|---|---|---|---|
| LHSW | $6.80 | +278% | 49.8× | 0.3M | 3.0 | 1.0 |
| PEW | $2.85 | +21% | 36.0× | 20.7M | 3.0 | 1.0 |
| SEER | $2.19 | +35% | 28.5× | 40.1M | 3.0 | 1.0 |
| WBX | $5.62 | +35% | 14.3× | 3.5M | 3.0 | 1.0 |
| SPHL | $2.96 | +16% | 146.3× | 1.0M | 2.8 | 0.75 |
| CRE | $2.75 | +10% | 21.8× | 1.1M | 2.8 | 0.75 |
| YDES | $2.34 | +23% | 37.8× | 0.3M | 2.5 | 0.5 |

## What's Still Pending
- 🔴 GitHub Actions NAS secrets (blocking ALL container rebuilds)
- 🔴 Container rebuild needed (scan_thread guard + pillars fixes not deployed)
- 🔴 Bull/Bear LLM vault key (Kay: run `vault/store_llm_key.ps1`)
- 🟡 Richard premarket scan (14:00 Berlin cron on Synology — may have run today)
- ⏳ Trader agent — position tracking, deterministic exits
- ⏳ Bull/Bear debate design — adapt TradingAgents pattern for Ross Cameron rules
