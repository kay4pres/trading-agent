# Pipeline Status
## Updated: 2026-07-01 16:30 Berlin (UTC+2)

---

## Overall Status: ⚠️ Running (degraded)

Pipeline is functional but the Bull/Bear live loop is offline — see action item below.

---

## Component Health

| Component | Status | Notes |
|-----------|--------|-------|
| Dashboard (`/api/state`) | ✅ UP | Responding, last_scan 16:29 |
| Fincept Connector | ✅ HEALTHY | AAPL/CTW/ILLR/MIMI returning live quotes |
| Richard Premarket | ✅ RAN | `watchlist_20260701.csv` saved at 14:02, 7 stocks |
| Scanner Cron (15:30–21:00) | ✅ RUNNING | signals files every 30 min |
| Bull/Bear Live Loop | ❌ OFFLINE | `alpaca_secret.enc` missing from vault |
| Alpaca WebSocket Feed | ⚠️ BLOCKED | Can't start without secret |
| TV Premium API | 🔍 UNKNOWN | Dashboard falls back to yfinance |

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

- **JEM**: Score 5/5, FIRST_PULLBACK pattern, RSI 58, +34% gap — confirmed on 2026-06-29
- **GVH**: Score 4-5/5, FIRST_PULLBACK patterns — confirmed on 2026-06-30
- 23 total historical signals in `signals_20260701_1631.json`
- ⚠️ All signals are from previous trading days (yfinance intraday lag ~15 min; post-market = no new bars)

---

## Open Positions

**None.** CTW position from earlier was approved @ $2.82, no open position currently.

---

## Issues & Action Items

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

No "quote error" found anywhere in the pipeline.

---

## Cron Jobs

| Cron | Schedule | Last Run | Status |
|------|----------|----------|--------|
| Richard premarket | 14:00 Mon–Fri | 14:02 today | ✅ |
| Scan-market | 15:30–21:00 /30min | 16:30 | ✅ |
| PM-Agent | 14:00 Mon–Fri | — | — |

---

## Next Steps (Priority Order)

1. **Run `store_alpaca_secret.ps1`** — unlock live loop (5 min, Kay does manually)
2. Monitor tomorrow's premarket — JEM/PMN/PAVS all had strong gaps but reversed; scanner should fire on fresh setups
3. Consider wiring Richard's premarket watchlist into dashboard's `run_scan()` directly so they share state
4. Remove dead code from `intraday_scanner.py:341-342`
