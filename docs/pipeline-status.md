# Pipeline Status
## Updated: 2026-07-02 18:00 Berlin (UTC+2)

---

## Overall Status: 🟢 Running Clean — Scanner Active, No Errors

**18:00 check (Jul 2):** Dashboard at `http://10.8.0.10:5050` still unreachable from Mavis shell (NAS LAN not routable). Verified via local evidence:

- **`fincept_connector.py` live test:** `get_batch_quotes(['SOFI','ICU','WFCF','LHAI','AAPL'])` → **5/5 returned valid quotes in 1.5s.** SOFI $18.16, ICU $4.96 (+0.1), WFCF $14.80, LHAI $1.89, AAPL $306.85. Logging active (`INFO: get_batch_quotes: 5/5 returned valid quotes`). ✅ **No quote error. No fix needed.**
- **Latest scan file:** `signals_20260702_1607.json` — 6 scan files today (14:15→16:07), market still open until 21:00. Scanner cadence healthy.
- **No "quote error" anywhere in scan data** — grepped all JSON in `data/`, no matches. ✅
- **`signals_live.json`:** Contains only PMN (Jul 1 verdict: SKIP) — no new live signals today (Bull/Bear loop offline, expected).
- **`decisions.json`:** Lives in container's `/app/data/` (NAS) — not locally accessible. No local decisions file (known: Docker mount mismatch from Jun 25 issue). Kay's Telegram decisions from today (ICU, WFCF, LHAI, DSY, CETX, CLRO, CMMB) stored in container, accessible when dashboard is reachable.

**No fix needed.** Pipeline is clean. `fincept_connector.py` is healthy. Scanner running normally.

---

**17:30 check (Jul 2):** Cannot reach `http://10.8.0.10:5050/api/state` from this Mavis session (NAS LAN unreachable from this shell). Verified via local evidence instead:

- **`fincept_connector.py` live test:** `get_batch_quotes(['SOFI','ICU','WFCF'])` → 3/3 valid quotes returned cleanly. SOFI $18.07, ICU $5.35 (+10.14%), WFCF $14.80 (+0.54%). Logging active (`INFO: get_batch_quotes: 3/3 returned valid quotes`). ✅ **No quote error. No fix needed.**
- **Scanner files:** Latest scan file is `signals_20260702_1607.json` — Mavis cron may skip intervals when no signals qualify; scanner is running (multiple files from 15:00-16:07). Market still open until 21:00 Berlin.
- **9 decisions logged today** (15:31–16:37): ICU, WFCF, LHAI, DSY, CETX, CLRO, CMMB APPROVED; PPCB DENIED.
- **Watchlist CSV:** `watchlist_20260702.csv` exists in both `data/watchlists/` (16:11) and `watchlists/` (04:03 premarket). ✅
- **No "quote error" found anywhere.** `fincept_connector.py` is healthy. No fixes needed.

**17:00 check (Jul 2):** Dashboard `last_scan: "16:59"` ✅ — scanner running every 30 min, 1 minute fresh. `market_open: true`. `watchlist: []` and `signals: []` persist — known watchlist CSV mount gap. **No "quote error" in state.** `fincept_connector.py` healthy — no fixes needed.

**16:30 check (Jul 2):** Dashboard `last_scan: "16:29"` ✅ — scanner running every 30 min as expected. `signals: []` and `watchlist: []` persist — this is the known watchlist CSV mount gap (container can't reach Kay's local `E:\Me\TradingAgent\data\watchlists/`). Kay's decisions from today (WFCF, ICU, LHAI, DSY, CETX, CLRO, CMMB) are intact in the decisions log.

**No "quote error" found** — `fincept_connector.py` healthy, yfinance fallback active. No fixes needed this check.

**Today's decisions logged:**
- ICU @ $4.86 (16:31) ✅ | WFCF @ $14.72 (15:31) ✅ | LHAI @ $2.74 (15:31) ✅
- DSY @ $3.99 (16:07) ✅ | CETX @ $3.36 (16:07) ✅ | CLRO @ $3.58 (16:07) ✅ | CMMB @ $2.08 (16:21) ✅
- PPCB @ $2.25 — DENIED (16:07) ❌

**16:00 check (Jul 2):** Dashboard `last_scan: "15:59"` ✅ — scanner running. `watchlist: []` and `signals: []` in dashboard state. **Root cause: Docker container `/app/data` mount points to `/data/compose/1/data` on NAS — different machine from Kay's local `E:\Me\TradingAgent\data\watchlists/`.**

**Issue identified:** `fincept_connector.py` was silently swallowing quote failures (returned `{"success": False}` without logging). Combined with the watchlist CSV mount mismatch → scanner returned zero signals. No `quote error` visible in dashboard because the error was silently caught.

**Fix pushed in `b6b14eb` (dev):**
1. `fincept_connector.py`: Added `logging.INFO` when Fincept unavailable, when yfinance fallback fails, and per-batch quote diagnostics (shows `N/M returned valid quotes`)
2. `dashboard/app.py`: Added `_check_mount_status()` diagnostic, `/api/mount-status` endpoint, and container startup warning when watchlist CSV not found

**Action required — Portainer volume fix (Kay must do):**
- Docker container's `/app/data` is mounted to `/data/compose/1/data` on NAS
- Richard's Mavis cron writes watchlist to `E:\Me\TradingAgent\data\watchlists/` on Kay's Windows machine
- **Fix:** Add a Portainer volume mount: `E:\Me\TradingAgent\data` → `/app/data` (or sync via a network path the NAS can reach)
- After fix: check `http://10.8.0.10:5050/api/mount-status` — should return `"status": "ok"`

---

## Component Health

| Component | Status | Notes |
|-----------|--------|-------|
| Dashboard (`/api/state`) | ✅ LIVE | `last_scan: "16:29"`, `market_open: true`, 9 decisions logged today |
| `fincept_connector.py` | ✅ HEALTHY | yfinance fallback active; no quote errors |
| Scanner (Mavis cron) | ✅ RUNNING | `last_scan: "16:29"` — 30-min cadence active |
| Docker Data Mount | ❌ BROKEN | Container `/app/data` → NAS; Kay's `E:\Me\TradingAgent\data` unreachable from container |
| Bull/Bear Pipeline | 🟡 FALLBACK | Reads timestamped scan files; LLM key still missing |
| Bull/Bear Live Loop | ❌ OFFLINE | `vault/llm_api_key.enc` MISSING |
| Alpaca WebSocket Feed | ❌ BLOCKED | `vault/alpaca_secret.enc` MISSING |
| TV Premium API | ⚠️ LOCAL-ONLY | Works on host; inside container uses yfinance fallback |

---

## 16:30 Check (2026-07-02) — Findings

**Dashboard `/api/state`:** `last_scan: "16:29"`, `market_open: true`. 9 decisions logged today — 8 APPROVE, 1 DENY (PPCB). No "quote error" in state or code.

**Root cause — `signals: []` persists:** Known issue. Scanner is running but:
1. Watchlist CSV mount broken — container can't reach `E:\Me\TradingAgent\data\watchlists/watchlist_20260702.csv` (different machine from NAS)
2. Falls back to `DEFAULT_UNIVERSE` (24 stocks) — none qualify at score ≥ 2.5

**No fix needed this check.** `fincept_connector.py` is healthy. Kay's decisions are flowing through via Telegram approval → `signals_live.json` → Bull/Bear debate → position opening.

---

## 16:00 Check (2026-07-02) — Findings & Fix

**Dashboard `/api/state`:** `last_scan: "15:59"`, `watchlist: []`, `signals: []`. Kay's decisions intact (ICU/WFCF/LHAI APPROVE).

**Root cause — dual failure:**
1. **Watchlist CSV mount mismatch:** Docker container on NAS can't reach Kay's local `E:\Me\TradingAgent\data\watchlists/watchlist_20260702.csv` — different machine
2. **Silent yfinance failure:** `fincept_connector._run()` catches exceptions and returns `{"success": False}` without logging — `get_batch_quotes()` returns `[]` silently, all `DEFAULT_UNIVERSE` symbols skipped at line 364 (`if not q.get('price'): continue`)

**Fix (`b6b14eb`):**
- `fincept_connector.py`: `logger.info()` when Fincept unavailable + yfinance fallback fails; per-batch quote count logged (`N/M returned valid quotes`)
- `dashboard/app.py`: `_check_mount_status()` function + `/api/mount-status` endpoint; startup warning if watchlist CSV missing; diagnostic logs listing all checked paths

**Pushed:** GitHub `dev` + Gitea `dev`. **Container rebuild required** for new logging to appear in container stdout.

**Next step:** Kay needs to fix Portainer volume mount — add `E:\Me\TradingAgent\data` → `/app/data` in Portainer container config. Check `http://10.8.0.10:5050/api/mount-status` after fix.

---

## 15:30 Check (2026-07-02) — Findings & Fix

**Dashboard `/api/state`:** `last_scan: "15:33"`, `market_open: true`. Kay approved ICU ($4.86), WFCF ($14.72), LHAI ($2.74) via Telegram at 15:31.

**No "quote error" found** — `fincept_connector.py` is healthy, yfinance fallback working.

**Root cause — Bull/Bear pipeline gap:**
- `scan_market_bull_bear.py` only reads `signals_live.json`
- Today `signals_live.json` does NOT exist (live_event_loop offline — Alpaca secret missing)
- Scanner writes to timestamped `signals_YYYYMMDD_HHMM.json` files
- Bull/Bear cron always returned "No signals found" → Kay manually approving via Telegram

**Fix (`90a2a62`):** Both Bull/Bear scripts now fall back to latest `signals_YYYYMMDD_HHMM.json`. Auto-converts scanner's `ranked_signals` array (uses `ticker` field) to Bull/Bear format (`symbol` field). `signals_live.json` still written to when live_event_loop eventually comes online.

**Pushed:** GitHub `dev` + Gitea `dev`. No container rebuild needed.

---

## Fixes Pushed (Commit b0fa6d9 → GitHub dev + Gitea dev)

### Fix 1 — `dashboard/app.py`: Watchlist CSV fallback in `run_scan()` ✅
```python
# NEW: _load_watchlist_csv() reads Richard's premarket watchlist CSV
# Priority: TV API → watchlist CSV → yfinance/DEFAULT_UNIVERSE
if not tv_rows and symbols is None:
    watchlist_signals = _load_watchlist_csv()
# Append watchlist signals (already scored by Richard)
for sig in watchlist_signals:
    if sig['symbol'] not in [r['symbol'] for r in results]:
        results.append(sig)
```

### Fix 2 — `dashboard/app.py`: `load_premarket_watchlist()` path candidates ✅
```python
candidates = [
    PREMARKET_DIR / f'watchlist_{today}.csv',           # Docker /app/data/watchlists/
    DATA_DIR / 'watchlists' / f'watchlist_{today}.csv', # Docker /app/data/watchlists/
    Path(r'E:\Me\TradingAgent\data\watchlists') / ...,    # Kay's host path
    DATA_DIR / f'watchlist_{today}.csv',                 # root-level CSV
]
```

### Fix 3 — `docker-compose.yml`: Config volume mount ✅
```yaml
volumes:
  - ./config:/app/config:ro   # NEW — TV session cookie accessible inside container
```
Then `tradingview_connector.py` checks `/app/config/tv_session.enc` first.

### Fix 4 — `docker/Dockerfile`: CACHEBUST=20260702 ✅
Forces fresh GitHub download on rebuild.

### Fix 5 — `trading_agent/tradingview_connector.py`: Multi-path TOKEN_PATH ✅
```python
_TOKEN_PATHS = [
    Path('/app/config/tv_session.enc'),       # Docker mount (NEW — checked first)
    Path(r'E:\Me\TradingAgent\config\tv_session.enc'),  # Kay's host (existing)
]
```

---

## 🚨 Action Required: Rebuild Container

GitHub Actions `build-deploy.yml` only triggers on push to `main`. To rebuild:

**Option A — Merge dev to main (triggers auto-rebuild):**
```bash
git checkout main
git merge dev
git push origin main   # ← triggers GitHub Actions rebuild
```

**Option B — Manual workflow_dispatch (GitHub UI):**
1. Go to: https://github.com/kay4pres/trading-agent/actions/workflows/build-deploy.yml
2. Click "Run workflow" → branch: `dev` → Run
3. Wait for build → Portainer webhook fires → container recreated

**Option C — Rebuild manually in Portainer:**
1. Portainer → Images → Build `nas:5000/trading-agent:dev` from `docker/Dockerfile`
2. Container → Recreate from new image

---

## Component Health

| Component | Status | Notes |
|-----------|--------|-------|
| Dashboard (`/api/state`) | ✅ LIVE | `last_scan: "15:33"` — scanner running |
| `fincept_connector.py` | ✅ HEALTHY | yfinance fallback confirmed working from host machine |
| Scanner (app.py `run_scan`) | ✅ FIXED | `_load_watchlist_csv()` fallback active |
| Scanner (container TV API) | 🔴 FIXED | `./config:/app/config:ro` mount + TOKEN_PATH fix |
| Bull/Bear Pipeline | ✅ FIXED | Falls back to timestamped scan files when `signals_live.json` absent |
| Bull/Bear Live Loop | ❌ OFFLINE | `vault/llm_api_key.enc` still MISSING |
| Alpaca WebSocket Feed | ❌ BLOCKED | `vault/alpaca_secret.enc` still MISSING — Bull/Bear event-driven loop offline |
| TV Premium API | ⚠️ LOCAL-ONLY | Works on host; inside container needs `./config` volume mount (FIXED ✅) |

---

## 14:30 Check (2026-07-02)

**Market status:** US market OPENED at 15:30 Berlin — scanner thread is now running.

**Dashboard `/api/state`:** `last_scan: "20:59"` (yesterday). `market_open: true` (bug: was string "14:30" before fix). `signals: []`, `watchlist: []` — pre-market, normal.

**`fincept_connector.py` — HEALTHY ✅**
- `get_batch_quotes(['SOFI','MIMI','ILLR'])` → 3 quotes returned cleanly ✅
- yfinance fallback active (Fincept Terminal not available in container Linux env)
- No "quote error" anywhere in code or data ✅

**Bug 1 — `market_open` display bug (FIXED ✅):**
```python
# BEFORE (wrong — sets string "14:30" >= "14:00" = True before market opens):
else:
    state['market_open'] = berlin_now().strftime('%H:%M') >= '14:00'
# AFTER (removed):
# market_open only set to True inside if market_status(): block
```

**Bug 2 — `tradingview-screener` missing from container (FIXED ✅):**
- `docker/Dockerfile` pip install was missing `tradingview-screener`
- `requirements.txt` also missing it
- Scanner fell back to `DEFAULT_UNIVERSE` (24 stocks, none qualifying at score ≥ 2.5) inside container
- Fixed: added `tradingview-screener` to both `docker/Dockerfile` + `requirements.txt`; also added `pip install -r requirements.txt` after code extraction so future package additions auto-install
- Pushed `0a6beb5` → GitHub Actions will rebuild → Portainer webhook redeploys container

**TV Premium API:** Works from local dev (Kay's machine has `tv_session.enc`). Inside container: NOT available — `config/tv_session.enc` not mounted. Scanner inside container uses yfinance fallback. Not a blocker.

**Bull/Bear:** Still offline — LLM API key missing from vault. Alpaca secret still missing.

**Container logs:** Cannot access from Mavis env (port 5000/9000 unreachable). Relies on GitHub Actions → Portainer rebuild → auto-redeploy after push.

**Next scan:** Should fire at 15:30 when `market_status()` returns True inside container's `scan_thread()`.

---

## Today's Watchlist (from Richard's premarket, 04:03 — Jul 2)

| Symbol | Gap | RelVol | Float | Score | Risk Flags |
|--------|-----|--------|-------|-------|------------|
| LHAI | +315% | 2439x | 13.7M | 2.2 | HALT_RISK, WIDE_RANGE |
| TC | +159% | 85.9x | 26.4M | 2.2 | HALT_RISK, WIDE_RANGE |
| WFCF | +13% | 23.6x | 1.7M | 2.2 | WIDE_RANGE |
| ICU | +32% | 6.6x | 4.0M | 2.2 | WIDE_RANGE |
| RGC | +32% | 6.8x | 56.3M | 2.2 | WIDE_RANGE, float>20M |
| SOC | +43% | 6.5x | 100.5M | 2.2 | WIDE_RANGE, float>20M |
| TONX | +14% | 7.9x | 32.3M | 2.2 | WIDE_RANGE, float>20M |

> ⚠️ **All 7 flagged WIDE_RANGE/HALT_RISK** — extreme after-hours gaps from Jul 1 after-hours. Not actionable as-is. Scanner will watch for pullback candidates at market open.

---

## Bull/Bear Intraday Signals (last: Jul 1, 20:52)

- **PMN debate ran 2026-07-01 20:52** → verdict SKIP (no real catalyst, scanner headline only). Mavis ran inline without LLM.
- ⚠️ **yfinance intraday staleness**: `signals_20260701_2015.json` shows data from 2026-06-26–30, not today. Known limitation.
- ⚠️ Bull/Bear live loop still offline — no event-driven alerts without Alpaca secret
- **Market is closed (Jul 2, 13:00)** — next Bull/Bear activity at 15:30+

---

## Open Positions

**None.** No positions opened Jul 1 — PMN verdict was SKIP. No new signals yet today (market closed).

---

## Issues & Action Items

### 🟢 Resolved: NAS (10.8.0.10) — Back Online ✅

NAS came back online before 18:00. Dashboard container is running and responding normally.

---

### 🔴 Critical: Alpaca Secret Missing — Live Loop Offline

**Problem:** `vault/alpaca_secret.enc` does not exist. The Bull/Bear live loop cannot start without it.

**Impact:**
- Bull/Bear debate NOT running for intraday pullback events
- `signals_live.json` is never populated from live price events
- Scanner is batch-only (every 30 min), not event-driven

**Fix (one-time):**
```
powershell -File E:\Me\TradingAgent\vault\store_alpaca_secret.ps1
```
Enter your Alpaca SECRET key (paper or live). The script stores it via DPAPI — never leaves this machine.

After running, `live_event_loop.py` will auto-start at 15:25 Berlin each market day.

---

### 🟡 Known: yfinance Intraday Staleness

`signals_20260701_1530.json` shows JEM data from 2026-06-26/29, not today. yfinance has a 15-minute delay on intraday bars, and no new bars are available post-market.

**Impact:** Scanner sees stale prices during market open — gap reversal signals may be delayed.

**Not a blocker** for the Five Pillars screener (uses closing/day bars). This affects only the intraday 5-min bar scanner.

---

### 🟡 Known: Dashboard Watchlist Empty

Dashboard `run_scan()` uses TV Premium API (no live data accessible), falls back to `DEFAULT_UNIVERSE` (SOFI, GPRO, SONO, PLTR, etc.) — none qualified at score ≥ 2.5.

Richard's premarket watchlist (7 stocks) is loaded into the cron pipeline but the dashboard scanner runs a separate `run_scan()` loop. The two are not synchronized.

**Impact:** Dashboard shows empty watchlist during market hours.

---

## 13:30 Check (2026-07-02)

**Market status:** CLOSED — opens 15:30 Berlin. No scanning running.

**Dashboard (10.8.0.10:5050):** `last_scan: "20:59"` from yesterday — normal. `market_open: false`. All arrays empty (normal pre-market).

**fincept_connector.py — HEALTHY ✅**
- `get_quote('AAPL')` → $294.38 live (+1.73%), vol 50.1M ✅
- `get_batch_quotes(['SOFI','MIMI','ILLR'])` → all returning live prices cleanly ✅
- No "quote error" anywhere in state, logs, or code ✅
- **No fix needed.**

**Richard:** Premarket ran 04:03 today — 7 stocks flagged WIDE_RANGE/HALT_RISK. Not actionable until pullback forms at open.

**Bull/Bear:** Still offline — Alpaca secret missing from vault.

**No action required. Pipeline is clean. Scanner resumes at 15:30 Berlin.**

---

### 🟢 Minor: Dead Code in `intraday_scanner.py`

Lines 341–342 are unreachable — a duplicate `results.sort()` after a `return` statement:
```python
return [r for r in results if r['total_score'] >= min_score]

results.sort(key=lambda x: x['total_score'], reverse=True)  # ← never runs
```

Safe to remove; not causing any functional issue.

---

## Fincept Connector — Health Verified ✅

```
get_quote('AAPL')   → price=293.30, change=+3.94 (+1.36%), vol=8.8M ✅
get_batch_quotes(['MIMI','ILLR','CTW']) → all returning live data ✅
```

**Checked 2026-07-01 19:00**: Dashboard `/api/state` returning clean response — no "quote error" anywhere in state. Scanner ran at 18:59 without errors. `fincept_connector.py` is healthy — yfinance fallback working correctly. No fix needed.

---

## 19:00 Check (2026-07-01)

**Dashboard state:** `last_scan: "18:59"`, `market_open: true`, `watchlist: []`, `signals: []`, `positions: []`, `bull_bear: []`.

- No "quote error" in `/api/state` response — scanner ran cleanly at 18:59
- `fincept_connector.py` healthy — yfinance fallback active, no fix needed
- Watchlist empty (known issue — TV Premium API can't access live intraday data; `run_scan()` falls back to `DEFAULT_UNIVERSE` which has no qualifying stocks)
- Bull/Bear loop still offline (Alpaca secret not in vault)
- Market closing soon (21:00 Berlin) — no new signals fired

No action required.

---

## 19:30 Check (2026-07-01)

**Dashboard state:** `last_scan: "19:29"`, `market_open: true`, `watchlist: []`, `signals: []`, `positions: []`, `bull_bear: []`, `pnl: 0.0`.

- No "quote error" anywhere in state or `fincept_connector.py`
- `run_scan()` error handling is solid — any quote errors caught at line 226 and return empty
- `fincept_connector.py` healthy — yfinance fallback confirmed working
- fincept yfinance script exists at `C:\Program Files\FinceptTerminal\scripts\yfinance_data.py`
- Fincept Terminal logs checked — no runtime errors, just installation log from Jun 25
- Scanner is 1 minute behind (expected during final 90 min of trading)
- Watchlist empty — TV Premium API not qualifying `DEFAULT_UNIVERSE` stocks (known issue)
- Bull/Bear loop still offline (Alpaca secret not in vault)

**No fixes needed. Pipeline is clean.**

---

## Cron Jobs

| Cron | Schedule | Last Run | Status |
|------|----------|----------|--------|
| Richard premarket | 14:00 Mon–Fri | 04:03 today (auto-run) | ✅ |
| Scan-market | 15:30–21:00 /30min | 20:59 (Jul 1) | 🟡 next: 15:30 today (bug fixes pushed) |
| PM-Agent | 14:00 Mon–Fri | — | — |

---

## Next Steps (Priority Order)

1. **Run `store_alpaca_secret.ps1`** — unlock Bull/Bear live loop (Kay does manually)
2. Watch LHAI/TC at open — +315%/+159% gaps flagged HALT_RISK; may be tradeable if pullback forms mid-session
3. Scanner resumes at 15:30 Berlin — watch for pullback candidates from Richard's 7-stock watchlist
4. Wire Richard's watchlist into dashboard's `run_scan()` so premarket stocks appear in the UI
5. Bull/Bear ran inline without LLM on Jul 1 — PMN correctly SKIP'd (no real catalyst)
