# Slot A — Universe Enumeration (daily refresh of US small caps with float)

## Sources investigated (verified via GitHub API + web search)

### Existing in pipeline (REUSE)
- `trading_agent/finviz_screener.py` — uses Finviz scrape with f=sh_price_2-20,sh_relvol_o2,ta_schange_o10
  - Pro: works today, no API key
  - Con: HTML scrape (Finviz blocks frequent requests, no float column without Elite)
  - Con: Returns 20-40 rows max per page; no pagination
- `trading_agent/tradingview_connector.py` — `fetch_ross_universe()` already filters NASDAQ+NYSE, price $2-20, gap >=10%, RV >=5x
  - Pro: live, designed for Ross-style screening
  - Con: requires TV sessionid cookie in `E:\Me\TradingAgent\config\tv_session.enc` (DPAPI)
  - Con: TV doesn't expose float in screener columns (limited columnset without paid tier)

### TradingView MCP (NEW option)
- 11 tools, including `get_leaderboard` (gainers, losers, most active), `search_market`, `get_metadata`
- Pro: standard JSON-RPC 2.0 over HTTPS, JWT auth (RapidAPI), can return screener metadata
- Con: docs unclear if float is exposed in screener metadata; likely NOT in free tier
- Source: https://www.tradingviewapi.com/mcp/ — verified live 2026-07-16
- Free tier via RapidAPI: see https://rapidapi.com/hypier/api/tradingview-data1 (pricing varies)

### NASDAQ Trader free screeners (public)
- Source: https://www.nasdaq.com/market-activity/stocks/screener
- Pro: FREE public screener with float column, market cap, sector, country
- Con: rate-limited (no formal API; scrape risk), 1-day stale, US only
- Pro: provides ~8,000+ US tickers with float — perfect for daily universe rebuild
- Real flow proven via Python + BeautifulSoup (community pattern)

### SEC EDGAR full-submission pull
- Source: https://www.sec.gov/cgi-bin/browse-edgar
- Pro: free, authoritative float (from latest 10-Q/10-K), quarterly refresh
- Con: ~1.5M filings/year, slow, need to parse XBRL or HTML; not daily
- Use case: enrich watchlist float on weekly cadence, NOT daily universe generation

### yfinance `info` dict
- Source: ranaroussi/yfinance ★24.7k Apache-2.0, last push 2026-07-16 (alive)
- Pro: free, `.info` returns `floatShares` directly per ticker; we already use it
- Con: rate-limited (Yahoo throttles); batch via `Tickers` class for ~50 at a time
- Con: `floatShares` missing for many low-float names (returns None)
- Status: already imported via `fincept_connector._fallback_yfinance()`

### Alpaca `get_assets()` + fundamentals
- Source: alpacahq/alpaca-py ★1.4k Apache-2.0, last push 2026-07-16 (alive)
- Pro: full US asset list with `easy_to_borrow`, `shortable`, `marginable`, `exchange`, `status`
- Con: NO float column (fundamentals not on Alpaca basic)
- Pro: free tier for paper account; Kay already has DEV container on Alpaca
- URL: https://alpaca.markets/docs/api-references/trading-api/assets/

## Verdict (Slot A)
- **Primary**: NASDAQ Trader daily scrape + yfinance `floatShares` enrichment + Alpaca `get_assets()` for status
- **Secondary**: TradingView MCP `get_leaderboard` (gainers) for intraday refresh
- **Existing reuse**: `finviz_screener.py` (Ross filter) as filter layer on top
- **Refresh cadence**: 06:00 ET daily (premarket window); cache to `data/universe_latest.csv`

## Score
- Fit: 4/5 (NASDAQ + yfinance covers Ross needs; free; daily cadence proven)
- Integration cost: 2/5 (small Python module, ~200 LoC)
- Data cost: 1/5 (free, public)