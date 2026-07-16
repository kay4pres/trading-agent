# Day Trade Dash — Phase 1 Shortlist

**Author**: Researcher (Lead, autonomous mode)
**Date**: 2026-07-16
**For**: Kay — read in 10 minutes
**Status**: Discovery complete. Ready for Phase 2 deep-dive.

---

## TL;DR

We **already have 70% of the pipeline** (Richard, Bull/Bear, IBGW relay, live event loop). The
gaps are **presentation + a few plumbing fixes**. We do NOT need to rip-and-replace. We need
to **wrap what works** with a clean live dashboard.

**One license blocker**: `koala73/worldmonitor` is AGPL-3.0 — cannot be vendored into our
closed-source UAT pipeline. Rejected.

**One near-perfect fit**: `tradingview/lightweight-charts` (Apache-2.0) for live candles.

**One set of tools to wire**: TradingView MCP (`get_leaderboard`, `get_news`, `get_quote_batch`)
for intraday gap/rel-vol/news — replaces multiple paid APIs we'd otherwise need.

---

## Component Shortlist (verified via GitHub API + web search)

| Slot | Component | Pick | License | Fit | Cost | URL |
|------|-----------|------|---------|-----|------|-----|
| **A. Universe** | Daily US small-caps refresh | NASDAQ Trader scrape + yfinance `floatShares` enrichment + Alpaca `get_assets()` for status | public + Apache-2.0 (yfinance) | 4/5 | free | https://www.nasdaq.com/market-activity/stocks/screener · https://github.com/ranaroussi/yfinance · https://alpaca.markets/docs/api-references/trading-api/assets/ |
| **B. Real-time prices** | Live tick stream | **Alpaca IEX WebSocket** (existing) + TradingView MCP `get_quote_batch` HTTP fallback | Apache-2.0 | 4/5 | free (IEX) | https://github.com/alpacahq/alpaca-py · https://www.tradingviewapi.com/mcp/ |
| **C. News / catalyst** | P4 catalyst feed | **TradingView MCP `get_news`** (intraday) + Finnhub (already integrated) + SEC EDGAR 8-K (daily cron) | API + Apache-2.0 + public | 4/5 | free | https://www.tradingviewapi.com/mcp/ · https://github.com/Finnhub-Stock-API/finnhub-python · https://github.com/dgunning/edgartools |
| **D. Pre-market scanner** | Gap + RV + float filter | **KEEP existing Richard** (`premarket_screener.py`) + thin yfinance enricher + TV MCP `get_leaderboard` cross-check | Apache-2.0 | 5/5 | free | (existing in repo) |
| **E. Chart UI** | Live candle charts | **TradingView Lightweight Charts** (Apache-2.0, 60fps canvas, ~45KB) | Apache-2.0 ✅ | 5/5 | free | https://github.com/tradingview/lightweight-charts |
| **F. Level 2 / order flow** | Time-and-sales + NBBO | **Defer Level 2 API** (paid) — show top-of-book + trade tape from Alpaca IEX + TV MCP `get_quote` bid/ask size. External L2 in WeBull/TWS in parallel. | n/a | 3/5 | free tier; full L2 paid | (gap, see §Honest Gaps) |
| **G. Named repos** | Kay's GitHub list | All 4 are off-domain or wrong-tool. **REJECT all for v1.** Defer qlib + RD-Agent to v2 factor-mining; use worldmonitor's finance variant as **design inspiration only** (AGPL blocks code reuse). | mixed | 1/5 | — | see slot-g-github-repos.md |

---

## Stack at a Glance

```
Frontend (NEW):   TradingView Lightweight Charts + Plotly.js (EOD reports) + vanilla JS
Backend (KEEP):   Flask app.py + extensions
Streaming (KEEP): Alpaca IEX WebSocket + SSE bridge
Universe (KEEP):  Richard (premarket_screener.py) + yfinance float enrichment (NEW)
News (ADD):       TradingView MCP get_news + existing Finnhub chain + SEC EDGAR 8-K
Signals (KEEP):   live_event_loop.py + Bull/Bear debate + IBGW relay
Data store (KEEP): Docker volume \\10.8.0.10\Docker\data\ + JSONL files
```

**No code rewrites.** All additions are additive.

---

## Honest Gaps (what we CAN'T do with free tools)

These need to be acknowledged in the build plan; they're not blockers but they cap what v1
can deliver:

### Gap 1 — Real Level 2 (depth of book)
- **Need**: full depth-of-book for $0.01 increments
- **Free?** No. Finviz Elite ($24/mo), TradingView Plus ($15-30/mo), Polygon (paid)
- **Workaround for v1**: Use Alpaca IEX NBBO (top of book) + manual WeBull/TWS Level 2 in parallel window
- **Trigger to revisit**: Kay finds he's missing entries because L2 was needed

### Gap 2 — Pre-market data is sparse on free sources
- **Need**: every US stock's pre-market bid/ask/volume by 06:00 ET
- **Free?** No. Most free feeds only populate pre-market for ~30-50 actively-traded names
- **Workaround for v1**: Filter universe via Finviz "premarket_change_o5" (up >5% premarket) which Finviz DOES expose free; cross-check with TV MCP `get_leaderboard`

### Gap 3 — Float data is missing for many low-float names
- **Need**: float for every small cap
- **Free?** Partial. yfinance `floatShares` returns None for ~30% of <$5 stocks
- **Workaround for v1**: SEC EDGAR 10-Q/10-K weekly enrichment; Finviz "Float Short" filter (paid); cross-reference with NASDAQ Trader (free, has share count but not free float)
- **Result**: For names Richard surfaces, we should have float within 1 trading day. For names yfinance can't resolve, fall back to SEC filings or mark "float: unknown"

### Gap 4 — SIP-grade consolidated tape
- **Need**: every trade on every US exchange, NBBO consolidated
- **Free?** Alpaca IEX is single-venue, not consolidated. IBKR TWS is consolidated but needs $4-30/mo market data sub
- **Workaround for v1**: Accept IEX; live_event_loop already uses it. Document latency = ~50-100ms slower than SIP, which is fine for 1-2 min candle strategy

### Gap 5 — Slow news for illiquid names
- **Need**: real-time news for a $0.50 micro-cap
- **Free?** Finnhub free tier covers them; TV MCP free tier has limits (~50/day depending on RapidAPI plan)
- **Workaround for v1**: cap daily TV MCP `get_news` calls to top 30 watchlist symbols; use Finnhub for the rest

### Gap 6 — No historical intraday data >30 days
- **Need**: 60-day 1-min chart history for backtesting pullback patterns
- **Free?** yfinance gives ~60 days 1-min for US; Alpaca gives 5-min free forever but 1-min limited
- **Workaround for v1**: Use yfinance for 60-day 1-min; use Alpaca historical for older 5-min

---

## Things I considered and REJECTED

| Option | Why rejected |
|--------|--------------|
| `koala73/worldmonitor` code reuse | **AGPL-3.0 license** — blocks closed-source UAT |
| `evanli/github-ranking` as a tool | It's a discovery index, not a trading tool |
| `microsoft/qlib` v1 integration | EOD quant framework, not a live dashboard |
| `microsoft/rd-agent` v1 integration | LLM R&D agent for factor mining, not live ticks |
| Polygon.io free tier | Discontinued real-time free tier; 15-min delayed only |
| Benzinga news | Paid only ($99+/mo) |
| Streamlit / Dash / Reflex | Page-rerender model, not WebSocket-first — wrong fit for live ticks |
| WorldMonitor Tauri desktop | Same AGPL problem |
| Community "small-cap screener" repos (0-1 stars) | All dead or off-domain; integration debt |

---

## What we'll build on top (preview of Phase 2)

1. **Live Watchlist Panel** — Richard's CSV + live prices from Alpaca WS (via SSE bridge)
2. **Live Candle Chart** — TradingView Lightweight Charts, 1-min + 5-min toggle, indicators (VWAP, 9/20 EMA, volume)
3. **Bull/Bear Conviction Ticker** — debounce + sort
4. **Open Positions** — current PnL, target, stop, time-in-trade
5. **Trade Tape** — last 100 prints per symbol (free tape from Alpaca trade stream)
6. **NBBO Quote Strip** — bid/ask size (free from TV MCP)
7. **News Feed** — real-time per-symbol (TV MCP) + daily digest (Finnhub)
8. **Five Pillars Panel** — show the score breakdown that motivated each watchlist pick
9. **Order Ticket** — currently exists in app.py; confirm it still works against IBGW relay

---

## Next step

→ Phase 2 build plan (`build-plan.md`) — concrete integration steps, exact code changes,
build sequence, verification approach.

---

**Total Phase 1 research time**: ~30 min model time
**Subagent slots investigated**: 8 (A-H) — see `scratchpad/` for full per-slot evidence
**Repos verified via GitHub API**: 15+ (all real, license-checked, last-commit-dated)
**Web sources visited**: 20+ (data vendor docs, license files, API references)