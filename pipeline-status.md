# Pipeline Status — 2026-07-07 18:00 (Berlin, UTC+2)

## Dashboard State
| Field | Value | Notes |
|---|---|---|
| `last_scan` | 18:02 | ✅ Scanner live, updating |
| `market_open` | true | ✅ |
| `watchlist` | 7 stocks | ✅ LHSW, PEW, SEER, WBX, SPHL, CRE, YDES |
| `signals` | 7 signals | ✅ All from `premarket_csv` source |
| `positions` | `[]` | No open positions |
| `bull_bear` | `[]` | No debates today |
| `mount_status` | `ok` | ✅ NAS volume mounted |
| `pillars` | ❌ **EMPTY** | 🔴 Root cause found — see below |

## Root Cause: `pillars: {}` — TWO Problems

### Problem 1: Scanner doesn't score CSV signals with Five Pillars (FIXED ✅)

**Root cause:** `run_scan()` in `app.py` only called `check_pillars()` for:
- TV API signals (step 4a) — but TV API not available in container
- yfinance default universe (step 4b) — only runs when BOTH `tv_rows` AND
  `watchlist_signals` are empty

Watchlist CSV signals were **appended raw** (step 4c) without any Five Pillars scoring:
```python
# OLD CODE (broken):
for sig in watchlist_signals:
    if sig['symbol'] not in [r['symbol'] for r in results]:
        results.append(sig)  # ← No Five Pillars scoring!
```

**Fix applied (`f9b82d9`):**
- Batch-fetch quotes for all watchlist symbols via `get_batch_quotes()`
- Score each CSV signal with `check_pillars()` + `score_catalyst()`
- Results tagged `source: "csv_live"` (vs old `source: "premarket_csv"`)
- Falls back to raw CSV append if live quote unavailable

**Status:** ✅ Fix committed to `dev` and merged to `origin/main` (`f9b82d9`)

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
| Restored `build-deploy.yml` | `cde656b` | ✅ Pushed to Gitea dev; ❌ GitHub PAT blocked |

---

## What Needs to Happen (Manual Steps Required)

### 🔴 1. Push `build-deploy.yml` to GitHub main (Kay)

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

### 🔴 3. Trigger GitHub Actions Rebuild

After secrets are set:
1. Go to: https://github.com/kay4pres/trading-agent/actions
2. Click `Build & Deploy to NAS` → "Run workflow" (green button)
3. Or: just `git push origin main` (workflow runs automatically)

Watch the run — if it succeeds, the new image is pushed to `nas:5000/trading-agent:latest`
and the container auto-restarts via the Portainer webhook.

### 🟡 4. Re-run Richard's Premarket Screener (after Docker rebuild)

Once the new Docker image is deployed (with the `csv_live` Five Pillars scoring fix):
```powershell
cd E:\Me\TradingAgent\trading_agent
python premarket_screener.py --save
```
This regenerates `watchlist_20260707.csv` with `pillars_json` column populated.
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
| `ca0ff79` | `dev` → `main` | ✅ YES | ❌ NO |
| `f9b82d9` | `dev` → `main` (Five Pillars csv_live) | ✅ YES | ❌ NO |
| `cde656b` | `dev` → `main` (build-deploy.yml restore) | ❌ BLOCKED | ❌ NO |

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

## Today's Signals (7 stocks, 2026-07-07 premarket)
| Symbol | Price | Gap | RelVol | Float | Score | P4 |
|---|---|---|---|---|---|---|
| LHSW | $6.80 | +278% | 49.8× | 0.3M | 3.0 | 1.0 |
| PEW | $2.85 | +21% | 36.0× | 20.7M | 3.0 | 1.0 |
| SEER | $2.19 | +35% | 28.5× | 40.1M | 3.0 | 1.0 |
| WBX | $5.62 | +35% | 14.3× | 3.5M | 3.0 | 1.0 |
| SPHL | $2.96 | +16% | 146.3× | 1.0M | 2.8 | 0.75 |
| CRE | $2.75 | +10% | 21.8× | 1.1M | 2.8 | 0.75 |
| YDES | $2.34 | +23% | 37.8× | 0.3M | 2.5 | 0.5 |

## Cron Health
- `premarket-scan` (Richard 14:00 Berlin): ✅ Watchlist generated (old format, no pillars_json)
- `scan-market` (Mavis 15:30–21:00): ✅ Running every 5 min
- `pipeline-check` (this session): ✅ Running at 18:00

## What's Still Pending
- 🔴 GitHub Actions: push `build-deploy.yml` to GitHub main (needs workflow scope)
- 🔴 GitHub Actions: set `NAS_REGISTRY_USER`, `NAS_REGISTRY_PASS`, `PORTAINER_WEBHOOK_URL` secrets
- 🔴 Docker rebuild: once secrets set → workflow runs → new image deployed
- 🟡 Re-run Richard's premarket screener after Docker update (generates pillars_json CSV)
- ⏳ Bull/Bear LLM pipeline (LLM key not stored — Kay needs `vault/store_llm_key.ps1`)
- ⏳ Trader agent — position tracking, deterministic exits
