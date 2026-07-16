# Slot D — Pre-market Screening (gap %, rel vol, float filtering)

## Sources investigated

### Existing in pipeline (REUSE — primary path)
- `trading_agent/premarket_screener.py` ("Richard") — runs at 00:14 Berlin Mon-Fri
- Reads Finviz scrape + TradingView universe + yfinance fundamentals
- Applies Five Pillars + Ch2 Risk Rules → ranked watchlist CSV
- Status: working in DEV; container cron 11e2b601da5b
- Output: `\\10.8.0.10\Docker\data\watchlist_latest.csv` (Docker volume)

### GitHub repos found for "small cap screener"
Searched via API: `https://api.github.com/search/repositories?q=small+cap+screener+language:python&sort=stars`
Results (low signal — none Ross-tuned):
- `MaximeFARRE/small-cap-screener` ★1 MIT — French small-cap, NOT US
- `Marc-Chia/streamlit-screener` ★1 — Alpaca-based, momentum screener (could inform UI)
- `bastdg/python-smid-alpha-screener` ★1 — fundamental, no real-time
- `cvvsi/SectorScope` ★1 — liquid leaders across sectors (interesting, BUT no Ross filter)
- `patw47/smallcaps-screener` ★0 — FastAPI+React+Claude, US but unmaintained
- `BenPollock/small-cap-screener` ★0 — fundamental only
- `taiyakiinvest/stocks-screener` ★0 — generic
- **`danderfer/Comp_Sci_Sem_2` ★190** — NOT a screener, false positive (school project)
- Most have 0-1 stars and are toy repos
- **VERDICT**: NO community repo matches Ross Cameron style + free + alive

### Finviz (free tier, scraping)
- Source: `trading_agent/finviz_screener.py` already scrapes
- Pro: native UI for Ross-style "up >20% today, $2-20, RV >2x" filters
- Con: Elite subscription ($24/mo) needed for float filter and screener API
- Verdict: KEEP existing scrape; don't pay for Elite

### TradingView free screener (via TV MCP `get_leaderboard`)
- Already documented in Slot A
- Pro: free leaderboard for gainers/losers; works pre-market on US-only filter
- Con: doesn't combine gap + RV + float in one query (no AND across column sets in basic tier)

### Yahoo Finance pre-market data
- yfinance has `preMarketPrice`, `preMarketChange`, `preMarketChangePercent` in `.info` (post-2024)
- Pro: free, batch via Tickers class
- Con: only ~30-50 stocks have pre-market data populated; sparse
- Verdict: useful for top-of-list cross-check, not for full universe

## Verdict (Slot D)
- **Primary**: KEEP `premarket_screener.py` (Richard) AS-IS. Already does the work.
- **Add**: a thin wrapper `premarket_enricher.py` that pulls yfinance `floatShares` per watchlist row (1 call per stock)
- **Add**: TradingView MCP `get_leaderboard` cross-check at 06:30 ET for gap confirmation
- **Avoid**: the 0-star community repos — they will be maintenance debt
- **DO NOT**: rewrite Richard. The pipeline already runs.

## Score
- Fit: 5/5 (Richard is the right design; just enrich with float)
- Integration cost: 1/5 (small enricher module)
- Data cost: 1/5 (free)