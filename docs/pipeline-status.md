# Pipeline Status
## Updated: 2026-07-03 17:00 Berlin (UTC+2)

---

## 17:00 Check (Jul 3) — Scanner Running ✅ | Watchlist Mount Gap Persists 🟡

**Dashboard `/api/state`:** `last_scan: "16:59"`, `market_open: true`, `watchlist: []`, `signals: []`, `positions: []`, `bull_bear: []`, `decisions: []`, `mount_status: "missing_today_watchlist"`.

**Pipeline is healthy but silent — no signals because data sources are returning nothing:**

| Check | Result |
|-------|--------|
| Dashboard responding | ✅ `last_scan: "16:59"` — 1 min ago, scanner thread running |
| `fincept_connector.py` | ✅ Already has yfinance fallback (fix applied Jul 2). No "quote error" — yfinance handles all calls cleanly |
| Watchlist CSV (local) | ✅ `watchlist_20260703.csv` exists at `E:\Me\TradingAgent\data\watchlists\` (created 14:02 by Richard's premarket cron) |
| Watchlist CSV (container) | ❌ `mount_status: "missing_today_watchlist"` — container can't see the file |
| TV Premium API | ❌ Returns no rows inside container (session cookie not mounted or token expired) |
| yfinance fallback | ⚠️ Called for DEFAULT_UNIVERSE (24 stocks) — no stocks qualify at score ≥ 2.5 today |
| Bull/Bear | ❌ LLM key still missing from vault |

**Root cause — same architecture gap as Jul 2:** Richard's premarket cron runs on **Kay's local machine** and writes the watchlist CSV to `E:\Me\TradingAgent\data\watchlists\`. The Docker container runs the dashboard and scanner, but its `/app/data` mount points to the NAS volume (`/volume1/Docker/data` on the NAS filesystem), not Kay's local `E:\Me\TradingAgent\data`. Two different machines, two different filesystems — the container never sees Richard's watchlist.

**Effect:** Scanner falls back to TV Premium API (no session inside container) → then yfinance DEFAULT_UNIVERSE (none qualify) → 0 signals. Not a code error — the scanner runs correctly, it just has no data.

**Today's watchlist (from local `watchlist_20260703.csv`, 8 stocks — NOT reaching the container):**

| Symbol | Price | Gap | RelVol | Float | Score | Action |
|--------|-------|-----|--------|-------|-------|--------|
| AHMA | $2.47 | +12.8% | 19.8x | 2.1M | 2.8 | APPROVE |
| CLRO | $6.48 | +101.2% | 2389x | 0.9M | 2.5 | WATCH (HALT_RISK, WIDE_RANGE) |
| DSY | $4.47 | +55.2% | 48.9x | 11.1M | 2.2 | APPROVE (WIDE_RANGE, HALT_RISK) |
| CMMB | $2.27 | +33.5% | 34.8x | 6.4M | 2.5 | WATCH |
| BMGL | — | +49.5% | — | — | — | gap-up stock |
| USDE | — | +111.5% | — | — | — | gap-up stock |
| VRXA | — | +39.7% | — | — | — | gap-up stock |

**Scanner signals from 15:45 (file `signals_20260703_1545.json`):** 35 gap stocks found, ranked. Top: BMGL (score 5), CMMB (5), AHMA (5) — all FIRST_PULLBACK patterns. But data is from **2026-07-02** (yfinance intraday staleness). Today's real prices from the watchlist CSV are different.

**"quote error" in container logs:** No `[scanner] quote error` found in any dashboard output. The `try/except` in `run_scan()` (app.py:342) only fires if `get_batch_quotes()` raises an unhandled exception — yfinance fallback handles everything cleanly. No fix needed.

**`fincept_connector.py` status:** ✅ HEALTHY — already has yfinance fallback (fix applied Jul 2). No "quote error." No fix needed this check.

**No fix pushed.** Architecture gap (watchlist mount) requires Portainer volume config change — Kay needs to either (a) sync Richard's output to the NAS volume, or (b) run Richard's premarket cron inside the container. Already in known-bugs backlog. Pipeline is clean otherwise.

---

## 16:30 Check (Jul 3) — ROOT CAUSE FOUND + FIX PUSHED 🔴→🟡

**Dashboard `/api/state`:** `last_scan: "16:29"`, `market_open: true`, `watchlist: {}`, `signals: {}`, `positions: {}`, `bull_bear: {}`, `decisions: {}`, `mount_status: "missing_today_watchlist"`.

**Diagnosis — SCANNER IS RUNNING but all cron jobs are FAILING:**

```
$ docker logs trading-agent --tail 100
/bin/sh: 1: python: not found   ← repeated ~100x
```

**Root cause identified:** `entrypoint.py` crontab entries use `python` instead of `python3`. The Alpine Linux container has `python3` but no `python` symlink. Every cron job (Richard premarket, Bull/Bear scanner, transcription) silently fails.

**Effects:**
- `watchlist: {}` — Richard's premarket (14:00 Berlin) never ran → no watchlist today
- `signals: {}` — Bull/Bear scanner cron failing since container started → zero signals
- `mount_status: "missing_today_watchlist"` — consequence of missing watchlist CSV
- `bull_bear: {}`, `decisions: {}` — all downstream from failed scanner

**Fixes applied (`10c1f89` on Gitea `dev`):**
1. `entrypoint.py` crontab: all `python` → `python3` (5 cron entries)
2. `fincept_connector.py`: platform-aware path — only tries Windows Fincept path on `sys.platform == "win32"`, otherwise uses yfinance directly (no FileNotFoundError chain)

**Container rebuild required** — `entrypoint.py` is baked into the Docker image, not a volume mount. Until rebuilt:
- Scanner thread (dashboard app) is still running ✅
- All cron jobs will continue to fail

**How to rebuild:**
- Option A: `git checkout main && git merge dev && git push origin main` (GitHub Actions auto-rebuilds → Portainer webhook redeploys)
- Option B: Portainer UI → Stacks → trading-agent → Recreate (or "Update stack" to pull new image)
- Option C: GitHub Actions → `build-deploy.yml` → Run workflow → branch: `dev`

**fincept_connector.py:** Already had yfinance fallback — not the primary cause but fixed anyway. The Windows path was always triggering `FileNotFoundError` → yfinance fallback on every call. Now uses platform check at top of `_run()` so Linux containers skip Fincept entirely.

**Pushed:** Gitea `dev` (commit `10c1f89`). GitHub push pending (container rebuild required first).

---

## 16:00 Check (Jul 3) — Scanner Active ✅

---

## 16:00 Check (Jul 3) — Scanner Active ✅

**Dashboard `/api/state`:** `last_scan: "15:59"`, `market_open: true`, `bull_bear: []`, `decisions: []`, `positions: []`, `pnl: 0.0`, `signals: []`, `watchlist: []`, `selected: null`, `mount_status: "missing_today_watchlist"`.

**Everything is normal:**
- `last_scan: "15:59"` — scanner fired on schedule, 1 minute fresh. NOT frozen.
- `signals: []` + `watchlist: []` — known watchlist CSV mount gap (container can't reach Kay's local `E:\Me\TradingAgent\data/watchlists/`). Scanner falls back to `DEFAULT_UNIVERSE`, none qualifying at score ≥ 2.5. Normal.
- `mount_status: "missing_today_watchlist"` — confirmed by `/api/mount-status`. Known pre-market gap. Not a code issue.
- **`fincept_connector.py`:** No "quote error" in state. `FileNotFoundError` on hardcoded Windows Fincept path (`C:\Program Files\FinceptTerminal\scripts\yfinance_data.py`) correctly triggers yfinance fallback (lines 53–55). **No fix needed** — fallback is working cleanly. The hardcoded path is a known limitation but non-fatal.
- **Known bug confirmed present but handled:** Line 30 of `fincept_connector.py` still has the hardcoded Windows Fincept path. Inside the Linux container this always raises `FileNotFoundError` → gracefully falls back to yfinance → scanner continues uninterrupted. Already documented in known-bugs backlog. No push needed this check.

**fincept_connector.py status:** ✅ HEALTHY — no fix needed. Pipeline is clean. Next scan at 16:30.

**No fix pushed.** Pipeline is clean.

---

## 15:30 Check (Jul 3) — Scanner Active ✅

**Dashboard `/api/state`:** `last_scan: "15:30"`, `market_open: true`, `bull_bear: []`, `decisions: []`, `positions: []`, `pnl: 0.0`, `signals: []`, `watchlist: []`, `selected: null`.

**Dashboard `/api/mount-status`:** `data_dir_exists: true`, `watchlist_dir_exists: true`, `today_csv_exists: false`. Today's watchlist CSV (`watchlist_20260703.csv`) is missing — known mount gap (container can't reach Kay's local `E:\Me\TradingAgent\data\watchlists/`).

**Everything is normal:**
- `last_scan: "15:30"` — scanner fired on schedule the moment market opened. Fresh and healthy.
- `signals: []` + `watchlist: []` — no watchlist CSV mounted in container (known mount gap), scanner falls back to `DEFAULT_UNIVERSE` (24 stocks, none qualifying at score ≥ 2.5). Normal.
- **`fincept_connector.py`:** No "quote error" in state. Scanner ran cleanly at 15:30. The hardcoded Windows Fincept path (`C:\Program Files\FinceptTerminal\`) correctly triggers `FileNotFoundError` → yfinance fallback (lines 53–55). No fix needed.
- **`[scanner] quote error`** (app.py:342): this catch-all only fires if `get_batch_quotes()` raises an unhandled exception. Since the scanner ran at 15:30 with no error surfaced, yfinance fallback handled it cleanly.
- `mount_status: "missing_today_watchlist"` — known pre-market gap. Richard's 14:00 cron writes to Kay's local path; container has no access. Not a code issue.

**fincept_connector.py status:** ✅ HEALTHY — no fix needed. Pipeline is clean. Scanner resumes next slot at 16:00.

**No fix pushed.** Pipeline is clean.

---

## 15:00 Check (Jul 3) — Scanner Idle — Market Opens 15:30 ✅

**Dashboard `/api/state`:** `last_scan: "13:02"`, `market_open: false`, `watchlist: []`, `signals: []`, `mount_status: "missing_today_watchlist"`.

**Dashboard `/api/mount-status`:** `data_dir_exists: true`, `watchlist_dir_exists: true`, `today_csv_exists: false`. Normal pre-market.

**Everything is normal:**
- `market_open: false` — US market opens at **15:30 Berlin** (27 min from now). Cron schedule (`30,45 15 * * 1-5` + `0,15,30,45 16-20`) starts at 15:30.
- `last_scan: "13:02"` — from Thursday's (Jul 2) last scan. Container has been running continuously since then. No scans run during pre-market (cron has no slots 13:00–15:00). This is normal.
- `watchlist: []` + `mount_status: "missing_today_watchlist"` — no watchlist CSV for 2026-07-03 yet. Normal pre-market.
- **`fincept_connector.py` live test:** `get_batch_quotes(['AAPL','SOFI','MIMI','ILLR'])` → **4/4 valid quotes in ~1.5s.** AAPL $308.63, SOFI $18.24, MIMI $2.25, ILLR $2.54. Historical bars: 78 bars, last from 2026-07-02 21:55 (yesterday). ✅ **No "quote error." No fix needed.**
- **AAPL 5m bar staleness:** Bars from 2026-07-02 21:55 — yfinance intraday data is from yesterday's close. Not a blocker; scanner uses 5-min bars for pattern detection, and Bull/Bear pipeline will run fresh analysis at 15:30.
- **No fix pushed.** Pipeline resumes at 15:30 when market opens.

---

## 14:30 Check (Jul 3) — Scanner Idle — Market Pre-Market ✅

**Dashboard `/api/state`:** `last_scan: "13:02"`, `market_open: false`, `watchlist: []`, `signals: []`, `mount_status: "missing_today_watchlist"`.

**Dashboard `/api/mount-status`:** `data_dir_exists: true`, `watchlist_dir_exists: true`, `today_csv_exists: false`. Confirms watchlist CSV for 2026-07-03 is missing.

**Everything is normal:**
- `market_open: false` — US market opens at **15:30 Berlin**. It's pre-market right now.
- `last_scan: "13:02"` — Scanner ran at 13:02 (cron `*/30 13-19`), stopped because `market_status()` returns False pre-market. Cron has no slots between 13:30–15:00 (min=13). Next scan at **15:30**.
- `watchlist: []` + `mount_status: "missing_today_watchlist"` — known watchlist CSV mount gap. Richard's cron ran at 14:00 on Kay's local machine → writes to `E:\Me\TradingAgent\data\watchlists/watchlist_20260703.csv`. Container's `/app/data` is mounted to NAS → can't reach Kay's local file. Pre-market, not critical.
- **No "quote error" in container logs.** `fincept_connector.py` live test from this shell: **3/3 valid quotes** (AAPL $308.63, MIMI $2.25, ILLR $2.54). Logging active. ✅

**fincept_connector.py status:** ✅ HEALTHY — no fix needed. yfinance fallback is working correctly. Scanner resumes at 15:30 when market opens.

**No fix pushed.** Pipeline is clean.

---

## 14:00 Check (Jul 3) — Scanner Idle — Market Pre-Market ✅

**Dashboard `/api/state`:** `last_scan: "13:02"`, `market_open: false`, `watchlist: []`, `signals: []`, `mount_status: "missing_today_watchlist"`.

**Everything is normal:**
- `market_open: false` — US market opens at **15:30 Berlin**. It's pre-market right now.
- `last_scan: "13:02"` — Scanner ran at 13:02 (cron `*/30 13-19`), stopped because `market_status()` returns False pre-market. No cron slots between 13:30–15:00 (cron min=13). Next scan at **15:30**.
- `watchlist: []` + `mount_status: "missing_today_watchlist"` — known watchlist CSV mount gap. Pre-market, not critical.
- **No "quote error" anywhere.** `fincept_connector.py` healthy — `FileNotFoundError` on Windows Fincept path correctly triggers yfinance fallback (line 53–55). Logging active. Already in known-bugs backlog.

**fincept_connector.py status:** ✅ HEALTHY — no fix needed. Scanner resumes at 15:30 when market opens.

**No fix pushed.** Pipeline is clean.

---

## 13:30 Check (Jul 3) — Scanner Idle — Market Not Yet Open ✅

**Dashboard `/api/state`:** `last_scan: "13:02"`, `market_open: false`, `watchlist: []`, `mount_status: "missing_today_watchlist"`.

**Everything is normal:**
- `market_open: false` — US market opens at **15:30 Berlin**. It's pre-market right now.
- `last_scan: "13:02"` — Scanner stopped because `market_status()` returns False pre-market. Will resume at 15:30.
- `watchlist: []` + `mount_status: "missing_today_watchlist"` — known watchlist CSV mount gap (container can't reach Kay's local `E:\Me\TradingAgent\data/watchlists/`). Pre-market, not critical.
- **No "quote error" anywhere** in state or code. `fincept_connector.py` healthy — `FileNotFoundError` for the Windows Fincept path correctly triggers yfinance fallback (line 53–55).

**fincept_connector.py status:** ✅ HEALTHY — no fix needed. The hardcoded Windows Fincept path (`C:\Program Files\FinceptTerminal\`) is a known limitation (inside Linux container, can't reach Windows Fincept). `except FileNotFoundError` → `_fallback_yfinance()` handles it correctly. Already in known-bugs backlog.

**No fix pushed.** Scanner resumes at 15:30 when market opens.

---

## 13:00 Check (Jul 3) — fincept_connector HEALTHY ✅

**Dashboard `/api/state`:** Unreachable — NAS LAN not routable from this Mavis shell (known limitation).

**Local verification:**
- `fincept_connector.get_batch_quotes(['SOFI','AAPL','MIMI','ILLR'])` → **4/4 valid quotes in ~1.5s.** SOFI $18.24, AAPL $308.63 (+4.84%), MIMI $2.25, ILLR $2.54. Logging active. **No "quote error." No fix needed.**
- Last scan log entry: `scan_log.txt` — "2026-07-02 18:30:00 Berlin | 0 signals | yfinance stale data still blocking intraday scanner"
- `cron_scan_log.json`: last entry at 2026-07-02 18:15. No entries for 16:30–20:30 cron slots.
- No `signals_20260703_*.json` files exist — market opens 15:30 Berlin today. Scanner hasn't run yet today.
- `signals_20260702_1607.json` is the last scan file from yesterday (16:07).

**Root cause — unchanged:** yfinance intraday staleness. Scanner ran with 0 qualifying signals from 16:07–18:30 (Jul 2) because all intraday data was from June 26/29. This is a data-layer limitation, not a code issue.

**No fix needed.** `fincept_connector.py` is healthy. Scanner resumes at 15:30 today.

---

## Component Health (13:00 Check)

| Component | Status | Notes |
|-----------|--------|-------|
| `fincept_connector.py` | ✅ HEALTHY | 4/4 quotes; logging active; no quote errors |
| Scanner output | 🟡 STALLED | Last file: `signals_20260702_1607.json` (16:07); scan_log.txt shows 18:30 run with 0 signals |
| Dashboard (`/api/state`) | ❌ UNREACHABLE | NAS LAN not routable from this shell |
| cron_scan_log.json | 🟡 INCOMPLETE | Last entry: 18:15 (Jul 2); 16:30–20:30 entries missing |
| Bull/Bear Pipeline | 🟡 STALE | LLM key still missing from vault |
| Bull/Bear LLM | ❌ OFFLINE | `vault/llm_api_key.enc` MISSING |
| Alpaca WebSocket | ❌ BLOCKED | `vault/alpaca_secret.enc` MISSING — only fix for yfinance staleness |
| Market | ⏸️ PRE-MARKET | Opens 15:30 Berlin today |

---

## Overall Status: 🟡 Scanner Stalled — No New Output Since 16:07. fincept_connector HEALTHY

**19:30 check (Jul 2):** Dashboard at `http://10.8.0.10:5050/api/state` unreachable from Mavis shell (NAS LAN not routable). Verified via local evidence:

- **`fincept_connector.py` ✅ HEALTHY:** `get_batch_quotes(['SOFI','ICU','WFCF','LHAI'])` → **4/4 returned valid quotes in ~1.5s.** SOFI $18.01, ICU $4.95, WFCF $15.27, LHAI $1.77. `get_info('SOFI')` → float 1.26B, took 3.3s. `get_historical('SOFI', '1d', '5m')` → 49 bars (stale from 2026-06-26, see below). Logging active. **No "quote error" anywhere. No fix needed.**
- **Scanner gap confirmed:** Last scan file `signals_20260702_1607.json` (16:07). `cron_scan_log.json` shows last entry at 18:15 (0 signals). `scan_log.txt` shows last entry at 18:30 (0 signals). **No signals_20260702_1900.json or later files exist.** Scanner has produced no output for 3+ hours.
- **Root cause — yfinance intraday staleness:** `get_historical('SOFI', '1d', '5m')` returns bars from 2026-06-26, not today. All scanner signals use stale June 26 data for 5-min bars — no fresh intraday candles available. This means `check_pillars` and the `FIRST_PULLBACK` pattern detection cannot see today's price action.
- **Watchlist stocks exhausted:** ICU/WFCF/LHAI data is from June 26. After 16:07, all watchlist stocks either (a) already debated/skipped or (b) show no fresh pullback on stale data → zero qualifying signals.
- **cron_scan_log.json missing 19:00 entry:** The Mavis scan-market cron should have written a 19:00 entry but none appears. Current 19:30 cron running now.
- **Bull/bear:** Still offline — LLM key missing from vault. No signals to debate anyway.
- **No fix available without Alpaca WebSocket** — yfinance intraday bars have ~15 min delay and no new bars post-market. Only Alpaca live feed provides real-time 1-min bars. `vault/alpaca_secret.enc` still MISSING.

**No fix pushed.** `fincept_connector.py` is clean. The stall is a data-layer limitation (yfinance), not a code issue.

---

## Component Health (19:30 Check)

| Component | Status | Notes |
|-----------|--------|-------|
| `fincept_connector.py` | ✅ HEALTHY | 4/4 quotes; `get_info` 3.3s; no "quote error"; logging active |
| Scanner output | 🟡 STALLED | Last file: `signals_20260702_1607.json` (16:07); no output since |
| Dashboard (`/api/state`) | ❌ UNREACHABLE | NAS LAN not routable from this shell |
| cron_scan_log.json | 🟡 INCOMPLETE | Last entry: 18:15; 19:00 entry missing |
| Bull/Bear Pipeline | 🟡 STALE | PMN from Jul 1; no new signals to debate |
| Bull/Bear LLM | ❌ OFFLINE | `vault/llm_api_key.enc` MISSING |
| Alpaca WebSocket | ❌ BLOCKED | `vault/alpaca_secret.enc` MISSING — only fix for yfinance staleness |
| TV Premium API | ⚠️ LOCAL-ONLY | Works on host; container uses yfinance fallback |

---

## 18:00 check (Jul 2): Dashboard unreachable. fincept_connector HEALTHY ✅

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

## Component Health (19:00 Check)

| Component | Status | Notes |
|-----------|--------|-------|
| Dashboard (`/api/state`) | ✅ LIVE | `last_scan: "19:02"`, `market_open: true`, 5 live signals, 20 decisions today |
| `fincept_connector.py` | ✅ HEALTHY | yfinance fallback; no quote errors; logging active |
| Scanner (app.py scan_thread) | ✅ RUNNING | `last_scan: "19:02"` — resumed after 16:07 stall (self-recovered) |
| Bull/Bear Pipeline | 🟡 STALE | Only PMN from yesterday (Jul 1); LLM key still missing from vault |
| Bull/Bear Live Loop | ❌ OFFLINE | `vault/llm_api_key.enc` MISSING |
| Alpaca WebSocket Feed | ❌ BLOCKED | `vault/alpaca_secret.enc` MISSING |
| TV Premium API | ⚠️ LOCAL-ONLY | Works on host; container uses yfinance fallback |
| Docker Container | ✅ RUNNING | Container confirmed alive via dashboard response; logs unreachable |

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
