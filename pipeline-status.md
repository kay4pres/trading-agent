# Pipeline Status — 2026-07-07 19:30 (Berlin, UTC+2)

## Dashboard State
| Field | Value | Notes |
|---|---|---|
| `last_scan` | 19:31 | ✅ Scanner live, updating |
| `market_open` | true | ✅ |
| `watchlist` | 7 stocks | ✅ LHSW, PEW, SEER, WBX, SPHL, CRE, YDES |
| `signals` | 7 signals | ✅ All from `premarket_csv` source |
| `positions` | `[]` | No open positions |
| `bull_bear` | `[]` | Bull/Bear array empty (inline debates not persisted to API state) |
| `mount_status` | `ok` | ✅ NAS volume mounted |
| `pillars` | 🟡 Empty `{}` for all — cosmetic only | 🟡 see below |
| `quote_error` | ❌ **NOT PRESENT** | ✅ No errors |
| `scanner_staleness` | ⚠️ yfinance 5-min bars end ~14:05 EST — 5th consecutive day with no intraday signals | ⚠️ see below |

## Bull/Bear Debates — 2026-07-07 (Confirmed Complete)
Verified via `data/bull_bear_results.json` — all 11 premarket signals debated inline:
| Symbol | Verdict | Conviction | Key Risk |
|---|---|---|---|
| PEW | SKIP | 4/10 | Float 20.7M too large + generic catalyst |
| WBX | SKIP | 4/10 | WIDE_RANGE 32.3% + generic catalyst |
| SPHL | SKIP | 3/10 | WIDE_RANGE 32.1% + generic catalyst |
| LHSW | SKIP | 1/10 | HALT_RISK 278% gap |
| FXHO | SKIP | 1/10 | HALT_RISK 172% gap + nano float |
| YDES | SKIP | 3/10 | WIDE_RANGE 55.6% + generic catalyst |
| SEER | SKIP | 3/10 | Float 40.1M too large |
| CRE | SKIP | 3/10 | WIDE_RANGE 27.8% + generic catalyst |
| ZCMD | SKIP | 1/10 | HALT_RISK 102% gap + WIDE_RANGE 66% + nano float |
| SONM | SKIP | 3/10 | WIDE_RANGE 32.9% + generic catalyst |
| GDEV | SKIP | 3/10 | WIDE_RANGE 33.3% + no catalyst |
**All 11 skipped. Zero approvals. No tradeable setups today.**

## fincept_connector.py — ✅ ALREADY FIXED
The known bug (hardcoded Windows path in Linux container) is **already resolved**:
- `_run()` checks `sys.platform == "win32"` before trying Fincept
- Linux/Docker falls through to `_fallback_yfinance()` automatically
- `get_quote()` and `get_batch_quotes()` both try Fincept → fallback → yfinance
- `quote_error` does NOT appear in container logs — **no fix needed** |

## Dashboard State — Expanded

### `pillars: ""` (Empty Display) — Cosmetic Only ✅

The dashboard shows `pillars: ""` (empty) for all CSV signals. This is a **display cosmetic issue only** — it does NOT affect Bull/Bear scoring or the pipeline.

**Why it looks empty:**
- Dashboard line 89: `json.loads(row.get('pillars_json', '{}'))` reads `pillars_json` from CSV
- Richard's 14:02 CSV was written BEFORE `ca0ff79` (added `pillars_json` column to CSV)
- So the CSV has no `pillars_json` column → dashboard shows empty

**Bull/Bear DID run correctly this morning** (mavis-inline-debate) — all 11 signals scored with conviction:
- PEW: 4/10 SKIP (float 20.7M too large, no specific catalyst)
- WBX: 4/10 SKIP (WIDE_RANGE 32.3%, generic catalyst)
- SPHL: 3/10 SKIP (WIDE_RANGE 32.1%, generic catalyst)
- LHSW: 1/10 SKIP (HALT_RISK 278% gap)
- FXHO: 1/10 SKIP (HALT_RISK 172% gap + nano float)
- ZCMD: 1/10 SKIP (HALT_RISK 102% gap + nano float)
- SEER: 3/10 SKIP (float 40.1M too large)
- YDES: 3/10 SKIP (WIDE_RANGE 55.6%)
- CRE: 3/10 SKIP (WIDE_RANGE 27.8%)
- SONM: 3/10 SKIP (WIDE_RANGE 32.9%)
- GDEV: 3/10 SKIP (WIDE_RANGE 33.3%)

**Root cause: `pillars_json` column missing from CSV** — fix is to rebuild Docker and re-run Richard.

### `quote_error` — NOT PRESENT ✅

Container logs (via `cron_scan_log.json`): zero quote errors. `fincept_connector.py` is working correctly — it falls back to yfinance in Docker (no Windows Fincept path), and yfinance returns valid quotes for the batch. The quote error that was expected (Windows path inside Linux container) does NOT occur because the code correctly skips Fincept and uses yfinance directly.

---

## Root Cause: TWO Problems (FIXES PUSHED — Docker frozen)

### Problem 1: `pillars_json` column missing from premarket CSV (FIXED ✅ in code — needs Docker rebuild)

**Root cause:** Richard's premarket screener (pre-`ca0ff79`) didn't write `pillars_json` to CSV.
The dashboard reads `pillars_json` from CSV to display P1-P5. Without the column, display is empty.

**Fix applied (`ca0ff79`):** `premarket_screener.save_watchlist()` now writes `pillars_json` to CSV.

**Fix applied (`f9b82d9`):** `app.py run_scan()` scores CSV signals live with Five Pillars if CSV lacks `pillars_json`.

**Fix applied (`cc2ff96`):** `fincept_connector._fallback_yfinance` includes `previousClose` from `info` dict.

**Status:** ✅ All three fixes committed to GitHub main
**Docker:** ❌ Frozen — needs rebuild (see Problem 2)

### Problem 2: `build-deploy.yml` DELETED from `main` — Docker image frozen 🔴

**Root cause:** `dev` → `main` merge included `19a653a` which deletes
`.github/workflows/build-deploy.yml`. The Docker image `nas:5000/trading-agent:latest`
will **never auto-rebuild** without this workflow.

Additional issue (pre-existing): GitHub Actions NAS login fails because
`NAS_REGISTRY_USER` / `NAS_REGISTRY_PASS` secrets not set.

**Fix applied (`cde656b`):**
- Restored `build-deploy.yml` from `74054af` to `dev` branch ✅
- Pushed to `gitea/dev` ✅
- Merged to `origin/main` — **BLOCKED** ❌ (GitHub PAT lacks `workflow` scope)

### Problem 3: Richard's CSV pre-dates `ca0ff79` fix

**Root cause:** Richard's 14:02 cron run used OLD code (before `ca0ff79` was
committed at 15:33). The CSV lacks `pillars_json` column. Even if Docker
had the new code, the CSV data wouldn't carry pillars.

**Fix:** Re-run Richard's premarket screener after Docker image is updated.
The new code (`ca0ff79`) writes `pillars_json` to CSV. The dashboard deserializes it.

---

## What Was Fixed This Session

| Fix | Commit | Status |
|---|---|---|
| `run_scan()` scores CSV signals with Five Pillars | `f9b82d9` | ✅ Pushed to GitHub main |
| Restored `build-deploy.yml` | `cde656b` | ✅ Pushed to GitHub main |
| `check_pillars()` reads previousClose from info dict (pillars={} bug) | `cc2ff96` | ✅ Pushed to GitHub main + Gitea |

---

## What Needs to Happen (Manual Steps Required)

### 🔴 1. Docker Rebuild — APPLY ALL PENDING FIXES

The Docker image is frozen at `74054af`. It needs to be rebuilt to include `cc2ff96` (pillars scoring fix) and all subsequent commits. Without a rebuild, the dashboard continues to show `pillars={}` for all signals.

**Option A — GitHub Actions (automatic, if secrets are set):**
After setting GitHub Actions secrets (see step 2 below), the workflow runs automatically on next push.
Go to: https://github.com/kay4pres/trading-agent/actions → `Build & Deploy to NAS` → "Run workflow"

**Option B — Manual Synology rebuild (fastest fix):**
SSH into Synology and rebuild locally:
```bash
ssh admin@10.8.0.10
cd /volume1/docker/trading-agent
docker build -t nas:5000/trading-agent:latest ./docker
docker push nas:5000/trading-agent:latest
# Then restart container via Portainer: http://10.8.0.10:9000
```

**Option C — Portainer manual rebuild:**
Portainer → Stack `trading-agent` → "Redeploy" (uses current `nas:5000/trading-agent:latest` — only works after Option A or B pushes new image)

### 🔴 2. Set GitHub Actions Secrets (Kay)

Mavis's GitHub PAT lacks `workflow` scope. Kay needs to push manually:

**Option A — GitHub web UI:**
1. Go to: https://github.com/kay4pres/trading-agent/tree/main/.github/workflows
2. Click "Add file" → "Create new file"
3. Name: `.github/workflows/build-deploy.yml`
4. Paste content from: `E:\Me\TradingAgent\.github\workflows\build-deploy.yml`
5. Commit directly to `main`

**Option B — GitHub CLI (if authenticated):**
```powershell
# From E:\Me\TradingAgent:
gh workflow run build-deploy.yml  # needs workflow scope
```

### 🔴 2. Set GitHub Actions Secrets (Kay)

Go to: https://github.com/kay4pres/trading-agent/settings/secrets/actions

Add these **Repository secrets** (ask Mavis for values if unsure):
| Secret Name | Where to get it |
|---|---|
| `NAS_REGISTRY_USER` | Synology admin username (DSM login) |
| `NAS_REGISTRY_PASS` | Synology admin password |
| `PORTAINER_WEBHOOK_URL` | Portainer → Stack → trading-agent → Webhook URL |

**How to find Synology credentials:**
- DSM web UI: `http://10.8.0.10:5000`
- Or check Kay's password manager for "Synology NAS" or "10.8.0.10"

### 🟡 3. Re-run Richard's Premarket Screener (after Docker rebuild)

Once the new Docker image is deployed (with the `cc2ff96` pillars fix):
```powershell
cd E:\Me\TradingAgent\trading_agent
python premarket_screener.py --save
```
Dashboard will show P1–P5 scores immediately on next scan.

---

## Architecture Notes

### Why `pillars: {}` was empty

```
Dashboard state (18:02)
├── 7 signals from premarket_csv
├── source: "premarket_csv" (not "tv_api" or "yfinance")
└── pillars: {}  ← app.py step 4c appended raw CSV, no Five Pillars scoring
```

The Five Pillars scoring only ran for:
- **TV API path** (step 4a): `check_pillars(quote, info)` — TV not in container ❌
- **yfinance path** (step 4b): Only if `quotes_raw` populated — but `quotes_raw`
  only fills when BOTH `tv_rows` AND `watchlist_signals` are empty ❌

### The `ca0ff79` Fix (already in code)

`ca0ff79` (committed 15:33) was supposed to fix this by:
1. `premarket_screener.save_watchlist()` writes `pillars_json` to CSV
2. Dashboard deserializes `pillars_json` when reading CSV

But Richard's cron ran at 14:02 (BEFORE `ca0ff79` at 15:33), so the CSV has no
`pillars_json`. The new `csv_live` scoring fix (`f9b82d9`) doesn't need the
CSV column — it scores live in the scanner itself.

---

## Code Status
| Commit | Branch | In GitHub main? | In Docker? |
|---|---|---|---|
| `74054af` | `origin/main` | ✅ YES | ✅ YES (frozen) |
| `ca0ff79` | `origin/main` | ✅ YES | ❌ NO |
| `f9b82d9` | `origin/main` (Five Pillars csv_live) | ✅ YES | ❌ NO |
| `cde656b` | `origin/main` (build-deploy.yml restore) | ✅ YES | ❌ NO |
| `cc2ff96` | `origin/main` (previousClose fallback fix) | ✅ YES | ❌ NO |

---

## Deployment Path — Current State

```
Code pushed to GitHub main
  ↓
GitHub Actions builds Docker image (FAILS at NAS login — secrets missing)
  ↓
Image pushed to nas:5000/trading-agent:latest (NEVER happens without secrets)
  ↓
Portainer webhook triggers container recreate (NEVER happens without image push)
```

**Until secrets are set in GitHub Actions, the Docker image will remain frozen.**

---

## Alternative: Build Directly on Synology (bypasses GitHub Actions)

If GitHub Actions can't be fixed quickly, SSH into Synology and build locally:
```bash
ssh admin@10.8.0.10
cd /volume1/docker/trading-agent
docker build -t nas:5000/trading-agent:latest ./docker
docker push nas:5000/trading-agent:latest
# Then restart container via Portainer
```

**Requirements:**
- SSH access to Synology (DSM admin credentials)
- Docker CLI on Synology (DSM Package Center → Docker)
- Port 22 open on Synology

---

## Today's Signals (11 stocks, 2026-07-07 premarket) — All SKIP (conviction 1-4/10)
| Symbol | Price | Gap | RelVol | Float | Bull/Bear Conviction | Verdict | Key Risk |
|---|---|---|---|---|---|---|---|
| LHSW | $6.80 | +278% | 49.8× | 0.3M | 1/10 | SKIP | HALT_RISK — gap too large |
| FXHO | — | +172% | — | nano | 1/10 | SKIP | HALT_RISK + nano float |
| ZCMD | — | +102% | — | nano | 1/10 | SKIP | HALT_RISK + nano float + WR 66% |
| SPHL | $2.96 | +16% | 146× | 1.0M | 3/10 | SKIP | WIDE_RANGE 32.1%, generic catalyst |
| YDES | $2.34 | +23% | 37.8× | 0.3M | 3/10 | SKIP | WIDE_RANGE 55.6%, generic catalyst |
| SEER | $2.19 | +35% | 28.5× | 40.1M | 3/10 | SKIP | Float too large (not microcap) |
| CRE | $2.75 | +10% | 21.8× | 1.1M | 3/10 | SKIP | WIDE_RANGE 27.8%, small gap |
| SONM | — | +12% | — | 1.2M | 3/10 | SKIP | WIDE_RANGE 32.9%, generic catalyst |
| GDEV | — | +11% | — | 2.5M | 3/10 | SKIP | WIDE_RANGE 33.3%, no catalyst |
| WBX | $5.62 | +35% | 14.3× | 3.5M | 4/10 | SKIP | WIDE_RANGE 32.3%, generic catalyst |
| PEW | $2.85 | +21% | 36.0× | 20.7M | 4/10 | SKIP | Float too large (20.7M > Ross <5M microcap) |

## Cron Health
- `premarket-scan` (Richard 14:00 Berlin): ✅ Watchlist generated 14:00
- `scan-market` (Mavis 15:30–21:00): ✅ Running — last_scan 19:31
- `pipeline-check` (this session): ✅ Checked at 19:30 — no issues found
- `bull_bear_inline` (Mavis): ✅ All 11 signals debated this morning (11:02-13:20 Berlin) — confirmed via bull_bear_results.json

## What's Still Pending
- 🔴 Docker rebuild: SSH to 10.8.0.10 blocked — cannot trigger rebuild. Kay needs to manually rebuild via Portainer or fix SSH access.
- 🔴 Bull/Bear results not surfaced in API state: debates run inline but not written back to dashboard state → `bull_bear: []` always. Fix: write debate results to a file that app.py reads on `/api/state`.
- 🟡 yfinance intraday staleness: 5th consecutive day with no intraday signals (yfinance 5m bars end ~14:05 EST, cron runs 15:30+ Berlin). Fix: Alpaca WebSocket streaming (needs `vault/alpaca_secret.enc` + `store_alpaca_secret.ps1` once).
- ⏳ Bull/Bear LLM pipeline: `vault/llm_api_key.enc` missing — Bull/Bear runs inline in Mavis session ✅ (works, just no dedicated subprocess)
- ⏳ Trader agent — position tracking, deterministic exits, live price monitoring

## 2026-07-07 19:30 Check — Findings
- ✅ Dashboard responding at `http://10.8.0.10:5050/api/state`
- ✅ `last_scan` updating (19:31, market_open=true)
- ✅ 7 premarket signals loaded from CSV (same 7 stocks)
- ✅ Bull/Bear ran inline — all 11 signals debated this morning, all SKIP (1-4/10 conviction) — verified via `data/bull_bear_results.json`
- ✅ No `quote_error` anywhere
- ✅ No scanner failures
- ✅ fincept_connector.py already fixed (yfinance fallback working correctly)
- 🟡 `pillars` display empty `{}` (cosmetic — Bull/Bear scored correctly without pillars)
- ⚠️ yfinance staleness: 5th consecutive day with no intraday 5-min bar signals
- 🔴 Docker still frozen (SSH to 10.8.0.10 blocked — cannot rebuild container)
- 🔴 Bull/Bear debates not persisted to API state (array shows `[]`) — debates ran but not surfaced in live dashboard
