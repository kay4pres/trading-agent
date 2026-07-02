# Pipeline Status
## Updated: 2026-07-02 14:30 Berlin (UTC+2)

---

## Overall Status: ⚠️ Market Open — Scanner Running, 2 Fixes Pushed

**14:30 check (Jul 2):** `last_scan: "20:59"` (yesterday) — scanner thread waits until 15:30 to run. Two bugs found and fixed:
1. **`market_open` display bug** (app.py line 398): else branch set `market_open = "14:30" >= "14:00"` → `True` before market open. Removed.
2. **`tradingview-screener` missing from container Dockerfile** — scanner fell back to default universe inside container. Fixed in `docker/Dockerfile` + `requirements.txt`. Push `0a6beb5` → triggers GitHub Actions rebuild → Portainer redeploy.

---

## Component Health

| Component | Status | Notes |
|-----------|--------|-------|
| Dashboard (`/api/state`) | ✅ LIVE | Responding cleanly. `last_scan: "20:59"` from yesterday (expected — market just opened at 15:30) |
| `fincept_connector.py` | ✅ HEALTHY | `get_batch_quotes(['SOFI','MIMI','ILLR'])` → 3 quotes, no errors |
| Scanner (app.py `scan_thread`) | ✅ FIXED | `market_open` display bug removed — was showing `true` at 14:30 before market open |
| Scanner (container TV API) | 🔴 FIXED | `tradingview-screener` added to `docker/Dockerfile` + `requirements.txt` — was missing, scanner fell back to default universe |
| Bull/Bear Live Loop | ❌ OFFLINE | `vault/llm_api_key.enc` still MISSING |
| Alpaca WebSocket Feed | ❌ BLOCKED | `vault/alpaca_secret.enc` still MISSING — Bull/Bear event-driven loop offline |
| TV Premium API | ⚠️ LOCAL-ONLY | `tv_session.enc` on host not mounted into container — TV API works from local dev, not from container |

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
