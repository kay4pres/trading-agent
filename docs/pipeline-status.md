# Pipeline Status
## Updated: 2026-07-01 17:30 Berlin (UTC+2)

---

## Overall Status: ⚠️ NAS Down — Scanner Running Locally

NAS (10.8.0.10) is unreachable — SSH port 22 closed. Dashboard container offline. Scanner running fine locally (17:15 scan ✅). Bull/Bear live loop still offline pending Alpaca secret.

---

## Component Health

| Component | Status | Notes |
|-----------|--------|-------|
| NAS Host | ❌ DOWN | SSH port 22 closed, unreachable — likely sleeping/offline |
| Dashboard (`/api/state`) | ❌ UNREACHABLE | Container can't be reached via http://10.8.0.10:5050 |
| Fincept Connector | ✅ HEALTHY | Fallback to yfinance active, no quote errors |
| Scanner Cron (15:30–21:00) | ✅ RAN | 17:15 scan complete, 29 signals, no quote errors |
| Scanner Output (local) | ✅ FRESH | `signals_20260701_1715.json` — JEM + GVH gap data |
| Richard Premarket | ✅ RAN | `watchlist_20260701.csv` saved at 14:02, 7 stocks |
| Bull/Bear Live Loop | ❌ OFFLINE | `alpaca_secret.enc` missing from vault |
| Alpaca WebSocket Feed | ⚠️ BLOCKED | Can't start without secret |
| TV Premium API | 🔍 UNKNOWN | Dashboard offline, can't verify |

---

## Today's Watchlist (from Richard's premarket, 14:02)

| Symbol | Premarket Gap | Current Status | Action |
|--------|--------------|----------------|--------|
| JEM | +267% | +98.9% (pulled back ~60%) | APPROVED — HALT_RISK flagged |
| PMN | +22.4% | -2.2% (reversed) | APPROVED — not actionable |
| PAVS | +20.8% | -14.4% (reversed) | WATCH — mixed TF |
| GVH | +36.8% | +7.1% (running) | REJECTED — daily BEARISH |
| INTJ | +19.5% | -13.7% (reversed) | REJECTED — daily BEARISH |
| SSII | +17.6% | -10.1% (reversed) | REJECTED — float 40.3M > 20M |
| XTLB | +15.7% | -8.4% (reversed) | REJECTED — relvol 1.7x < 5x |

**Note:** All premarket stocks reversed after open except JEM (halted/running hot) and GVH (daily bearish). No new intraday setups triggered.

---

## Bull/Bear Intraday Signals (from scanner)

- **29 signals found at 17:15** — all historical (2026-06-26/29/30). JEM (score 5) and GVH (score 5) ranked top.
- ⚠️ **yfinance intraday staleness**: scanner shows bars from 2026-06-26–30, not today's. This is a known limitation — yfinance delays intraday data.
- ⚠️ Bull/Bear live loop still offline — no event-driven alerts without Alpaca secret

---

## Open Positions

**None.** CTW position from earlier was approved @ $2.82, no open position currently.

---

## Issues & Action Items

### 🔴 Critical: NAS (10.8.0.10) Unreachable

**Problem:** NAS is down — SSH port 22 is closed. Dashboard at http://10.8.0.10:5050 is unreachable.

**Impact:**
- Dashboard (`app.py`) is offline — Kay can't view signals in browser
- Scanner is still running locally via cron (signals_20260701_1715.json ✅)
- Bull/Bear live loop was running on NAS — also offline

**Fix:** Wake the NAS (WOL or physically). Once it's back online, `docker ps` should show the dashboard container. SSH: `ssh admin@10.8.0.10` then `docker ps`.

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

**Checked 2026-07-01 17:30**: No "quote error" anywhere in scanner outputs (`signals_20260701_*.json`). `fincept_connector.py` is healthy — yfinance fallback working correctly. No fix needed.

---

## Cron Jobs

| Cron | Schedule | Last Run | Status |
|------|----------|----------|--------|
| Richard premarket | 14:00 Mon–Fri | 14:02 today | ✅ |
| Scan-market | 15:30–21:00 /30min | 17:00 | ✅ |
| PM-Agent | 14:00 Mon–Fri | — | — |

---

## Next Steps (Priority Order)

1. **Run `store_alpaca_secret.ps1`** — unlock live loop (5 min, Kay does manually)
2. Monitor tomorrow's premarket — JEM/PMN/PAVS all had strong gaps but reversed; scanner should fire on fresh setups
3. Consider wiring Richard's premarket watchlist into dashboard's `run_scan()` directly so they share state
4. Remove dead code from `intraday_scanner.py:341-342`
