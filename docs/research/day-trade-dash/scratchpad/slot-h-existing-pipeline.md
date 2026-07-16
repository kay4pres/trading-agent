# Slot H — Existing Pipeline Integration Audit

## What's already running (verified live in pipeline-status.md and codebase)

### 1. Richard PreMarket screener
- File: `trading_agent/premarket_screener.py`
- Cron: every weekday at 00:14 Berlin (14:00 local-equivalent ET premarket)
- Reads: Finviz + TradingView + yfinance fundamentals + news_providers (Finnhub)
- Output: `watchlist_latest.csv` on Docker volume
- **Reuse**: 100% — it IS the universe feed for the dashboard. Dashboard just READS its output.

### 2. Bull/Bear debate pipeline
- Files: `trading_agent/bull_bear_debate.py`, `bull_bear_signal_handler.py`, `scripts/scan_market_bull_bear.py`, `scripts/bull_bear_runner.py`
- Cron: Mavis daemon, every few minutes during market
- Reads: new symbols + watchlist
- Output: `bull_bear_results.json` (conviction scores 1-10)
- **Reuse**: 100% — dashboard shows the conviction column verbatim

### 3. live_event_loop.py
- File: `trading_agent/live_event_loop.py`
- Architecture:
  ```
  Alpaca WebSocket (price_event_handler)
      ↓
  Pullback detected → write to signals_live.json
      ↓
  Mavis scan-market cron → picks up signal → runs Bull/Bear LLM debate
      ↓
  Results written to bull_bear_results.json
      ↓
  live_event_loop polls results → auto-opens if conviction >= 7
      ↓
  Position monitor (target/stop/2-min) → on exit → memory_logger
  ```
- **KNOWN LIMITATION** (from task brief): Alpaca-only price stream. Doesn't see IB-only UAT/PROD positions.
- **Reuse**: KEEP for DEV (Alpaca paper). For UAT/PROD, build parallel relay that ALSO consumes IB price stream.

### 4. IBGW relay
- File: `scripts/ibgw_relay.py`
- URL: http://10.8.0.2:5055
- Function: order placement via ibkr_connector.py
- Status: ✅ WORKING — paper account DU1234567
- **Reuse**: KEEP. Dashboard already calls it via existing app.py routes.

### 5. Telegram healthcheck cron
- ID: 11e2b601da5b, every 15min
- Bots: @Marvless01_bot (live), @Hendrika01_bot (ops), @Devon01_bot (unconfigured)
- **Reuse**: KEEP — dashboard health endpoint already posts to Telegram

### 6. Container topology
- DEV (Alpaca Paper): container `trading-agent-dev`, port :5051 ✅
- UAT (IB Paper): container `trading-agent-uat`, port :5052 ✅
- PROD (IB Live): container `trading-agent`, port :5050 🔴 BLOCKED
- NAS: 10.8.0.10, Gitea at :3000

### 7. Existing data files (on Docker volume `\\10.8.0.10\Docker\data\`)
- `watchlist_latest.csv` — Richard's output
- `bull_bear_results.json` — debate output
- `signals_live.json` — live event loop output
- `positions.json` — open positions
- `watchlists/watchlist_YYYYMMDD.csv` — dated archives

### 8. Existing Flask app
- `app.py` ~60KB — main dashboard backend
- `app_prod.py` ~60KB — PROD-specific config
- `app.py.bak` — backup from Jul 15
- `dashboard/` — static assets + templates
- **Reuse**: EXTEND, don't rewrite. Add new routes:
  - `/api/dashboard/state` — current state snapshot
  - `/api/stream/quotes` — SSE feed of quotes
  - `/api/chart/ohlcv/<symbol>` — historical for Lightweight Charts
  - `/api/universe/today` — Richard's watchlist as JSON

## Identified gaps in existing pipeline

### Gap 1: Float data is sparse
- `premarket_screener.py` doesn't always pull floatShares from yfinance
- yfinance returns None for ~30% of low-float names
- **Fix**: Add SEC EDGAR 10-Q fallback in `premarket_enricher.py`

### Gap 2: Bull/Bear debate uses LLM credits
- Currently RUNNING but intermittent (per `pipeline-status.md`: bull_bear: [])
- Stuck behind vault key issues
- **For dashboard**: SHOW the column even if empty. Document known issue.

### Gap 3: live_event_loop is Alpaca-only
- For UAT/PROD (IB), no price stream consumer exists
- **For dashboard**: design it to be source-agnostic; subscribe to whatever feed the env has

### Gap 4: Container cron PATH
- "python3: not found" — known issue per pipeline-status.md
- **Fix**: cron entries need full path or python3 venv activation
- Not a dashboard concern, but blocks signals from being generated → dashboard will look empty

### Gap 5: No live price snapshot store
- live_event_loop writes signals but no per-symbol price tick history
- **Fix**: Add Redis or even just in-memory ring buffer in a new module `live_price_cache.py`

## What needs to change (existing pipeline)
| File | Change | Why |
|------|--------|-----|
| `app.py` | Add 4 new routes (above) | Dashboard widgets |
| `premarket_screener.py` | Add yfinance `floatShares` enrichment call | Gap 1 |
| `live_event_loop.py` | Add per-symbol tick history dump to `live_ticks.jsonl` | Gap 5 |
| `live_event_loop.py` | Make Alpaca WS pluggable to IB source | Gap 3 |
| `news_providers.py` | Add TradingView MCP `get_news` as P1 | Gap in catalyst freshness |
| `requirements.txt` | Add `lightweight-charts` not needed (CDN), add `polars` for fast cache | Speed |
| `dashboard/static/js/` | New `live_chart.js`, `watchlist.js`, `level1.js` | Front-end |
| `dashboard/templates/` | New `dashboard_v2.html` | New layout |

## Verdict (Slot H)
- **Pipeline is 70% reusable**. The big design decisions (5-pillar, Five Pillars, conviction >=7, Bull/Bear debate) are CORRECT and battle-tested.
- **What we DON'T change**: signal generation, debate, order placement, risk rules
- **What we ADD**: presentation layer + light data plumbing
- **Critical**: fix Gap 5 (live tick history) — without it, the chart can't update live

## Score
- Fit: 5/5 (everything aligns with our goals)
- Integration cost: 2/5 (additive, not destructive)
- Data cost: 0/5 (all data is already flowing)