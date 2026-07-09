# Pipeline Status — 2026-07-09 16:30 (Berlin, UTC+2)

## Dashboard State
| Field | Value | Notes |
|---|---|---|
| `last_scan` | **16:30** | ✅ Live — scanner running every 5 min |
| `market_open` | `true` | ✅ Synced correctly (market open since 15:30) |
| `watchlist` | 4 stocks | NVVE, IOTR, TVRD, ZTG (Jul 9 premarket @ 14:10) |
| `signals` | **0** | ✅ Correctly rejecting all 4 (see below) |
| `bull_bear` | `[]` | ⏳ No new debates — nothing to debate |
| `mount_status` | `ok` | ✅ NAS volume mounted |
| `pillars` | populated | ✅ Live P1–P5 scoring from today's CSV |

## Why 0 Signals Today — NOT A Bug ✅

All 4 watchlist stocks today were rejected by Ross Cameron risk rules:

| Symbol | Gap | RelVol | Float | HALT_RISK | WIDE_RANGE |
|---|---|---|---|---|---|
| NVVE | +63.6% | 791× | 0.2M | 🚫 `gap=64%` | 🚫 143% |
| TVRD | +61.3% | 5.0× | 5.7M | 🚫 `gap=61%` | 🚫 88.4% |
| IOTR | +40.5% | 44.8× | 1.0M | ✅ | 🚫 23.0% |
| ZTG | +25.0% | 6.0× | unknown | ✅ | 🚫 40.3% |

**NVVE (+64%) and TVRD (+61%)**: Gaps >50% = HALT_RISK. Ross Cameron explicitly says: "If the stock is up 50% or more on the open, it's too dangerous to trade." Scanner correctly flagged and skipped them.

**IOTR, ZTG**: Wide range flags (23–40%) — excessive intraday volatility, lower probability setups.

**fincept_connector.py**: ✅ HEALTHY — yfinance fallback running cleanly inside container. No quote errors anywhere. The `WIDE_RANGE` and `HALT_RISK` flags come from the scanner's own rules, not from data failures.

## Bull/Bear Status
- `bull_bear_results.json` still shows Jul 1 debates (PMN, PEW) — no new debates today
- Cron fires every 30 min 15:00–20:45 — will trigger when/if a signal qualifies
- LLM unavailable: `vault/llm_api_key.enc` still missing → debates run in simulated mode

## Actions
- ✅ No fixes needed today — system working as designed
- 🟡 Bull/Bear LLM vault key still missing (`vault/llm_api_key.enc`)
- ⏳ Richard premarket cron ran successfully today (14:10 Berlin) ✅
- ⏳ Bull/Bear debate if any stock qualifies in next scan cycle

---# Pipeline Status — 2026-07-08 14:00 (Berlin, UTC+2)

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
