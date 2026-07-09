# Pipeline Status — 2026-07-09 17:00 (Berlin, UTC+2)

## Dashboard State
| Field | Value | Notes |
|---|---|---|
| `last_scan` | 16:25 | 🟢 Today — scanner ran, Bull/Bear debates active |
| `market_open` | true | Scanner active (15:30–21:00 Berlin) |
| `watchlist` | 4 stocks | Today's premarket: NVVE, IOTR, TVRD, ZTG |
| `signals` | `[]` | ✅ Correct — all 4 stocks filtered by risk rules |
| `positions` | `[]` | No open positions |
| `bull_bear` | 4 debates | NVVE/IOTR/TVRD/ZTG all SKIP (HALT_RISK/WIDE_RANGE) |
| `mount_status` | `ok` | ✅ NAS Z: volume mounted |
| `pillars` | working | ✅ Bull/Bear debates enrich pillars via yfinance fallback |

## fincept_connector.py — Status: ✅ HEALTHY, no fix needed

The `quote error` in `dashboard/app.py:367` is the outer exception handler for yfinance failures.
The connector already has a complete fallback chain:

1. **Docker/Linux**: `fincept_connector._run()` detects non-Win32 → calls `_fallback_yfinance()` directly.
   yfinance is installed in the container. ✅
2. **Windows host**: tries `C:\Program Files\FinceptTerminal\scripts\yfinance_data.py` if exists,
   then falls back to yfinance. ✅

Today's Bull/Bear debates at 16:24 confirm yfinance is working — 4 stocks fetched live
(NVVE, IOTR, TVRD, ZTG) with price, gap, float, rel_vol data. No "quote error" in evidence
from today's run. The `quote error` print at line 367 is a **graceful fallback catch** — it
fires only if all sources fail, and in that case it still returns whatever watchlist signals
were already loaded. Scanner does not die from it.

## Bull/Bear Debates Today (16:24 Berlin)
All 4 premarket stocks filtered by risk rules — no quote errors, system working correctly:

| Symbol | Price | Gap | Float | RelVol | Risk Flags | Verdict |
|---|---|---|---|---|---|---|
| NVVE | $8.49 | +64% | 0.2M | 791× | HALT_RISK, WIDE_RANGE 143% | SKIP |
| IOTR | $3.54 | +41% | 1.0M | 45× | WIDE_RANGE 23% | SKIP |
| TVRD | $5.00 | +61% | 5.7M | 5× | HALT_RISK, WIDE_RANGE 88% | SKIP |
| ZTG | $2.85 | +25% | N/A | 6× | WIDE_RANGE 40%, UNKNOWN_FLOAT | SKIP |

No APPROVE signals today. Scanner discipline holding — gap >50% stocks correctly filtered.

## Root Cause Analysis (updated)

### Container Rebuilt ✅
Recent commits show container IS now running the latest code:
- `e0a0561` fix: market_open state sync + Bull/Bear freshness guard
- `9b0b1f1` Fix: reload premarket CSV each cycle if watchlist empty
- `763ffab` Fix: preserve premarket CSV watchlist when run_scan() returns empty
- `53fc272` docs: pipeline-status 2026-07-09 16:30 check

Container appears to have been rebuilt since the last status check. Bull/Bear freshness guard
(now checking `debated_at` freshness) is active and preventing stale debates.

### Bull/Bear LLM Key — Still Missing
`vault/llm_api_key.enc` not stored — debates run inline in Mavis session (simulated mode).
Kay needs to run: `E:\Me\TradingAgent\vault\store_llm_key.ps1` once to enable real LLM debates.

## What IS Working
- ✅ Dashboard alive on port 5050 (NAS: 10.8.0.10)
- ✅ NAS Z: volume mount OK
- ✅ Telegram alerts wired
- ✅ `market_status()` correctly gates scan_thread 15:30–21:00 Berlin
- ✅ Bull/Bear debates firing each cycle (watchlist→debate pipeline active)
- ✅ Risk rules (HALT_RISK, WIDE_RANGE, UNKNOWN_FLOAT) correctly filtering stocks
- ✅ fincept_connector.py yfinance fallback healthy — no quote errors today
- ✅ Richard premarket ran today at 14:10 (watchlist_20260709.csv ✅)

## What IS NOT Working
- 🟡 Bull/Bear LLM vault key missing — debates in simulated mode (Kay: run `vault/store_llm_key.ps1`)
- 🔴 GitHub Actions NAS secrets — if another rebuild is needed, workflow will fail again

## What's Still Pending
- 🟡 Bull/Bear LLM vault key (Kay: run `vault/store_llm_key.ps1`)
- ⏳ Trader agent — position tracking, deterministic exits
- ⏳ Bull/Bear full Bull/Bear/Bear/RM synthesis with conviction scoring (currently skip-only)
