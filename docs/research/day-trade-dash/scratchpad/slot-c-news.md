# Slot C — News & Catalyst Ingestion

## Sources investigated

### Existing in pipeline (REUSE)
- `trading_agent/news_providers.py` already implements fall-through chain:
  1. Finnhub (60 req/min free) → 2. Alpha Vantage (25 req/day) → 3. Fincept/yfinance
- Status: working, used by `premarket_screener.py` for P4 catalyst scoring
- Source: Finnhub-Stock-API/finnhub-python ★1k Apache-2.0 (alive)

### SEC EDGAR (free, authoritative)
- Source: dgunning/edgartools ★2.5k MIT, last push 2026-07-09 (alive)
- Alternative: sec-edgar/sec-edgar ★1.4k Apache-2.0 (alive but older)
- Pro: 8-K filings = exact "catalyst" source for Ross P4; 10-Q = float confirmation
- Con: not daily refresh of news; filings are discrete events
- Use case: enrich catalyst score when 8-K detected in last 48h

### TradingView MCP `get_news` / `get_news_detail`
- Source: verified live 2026-07-16 at https://www.tradingviewapi.com/mcp/
- Pro: real-time financial news across 250+ exchanges; sentiment scoring built-in
- Pro: batchable per symbol
- Con: free tier on RapidAPI limits per-day calls (check tier)
- Verdict: best free option for INTRADAY news (catalyst alert in 5-min window)

### Benzinga
- Source: benzinga news API (paid only)
- Con: paid tier ($99+/mo); not free
- Verdict: not for v1

### Polygon news
- Source: Polygon news API (now paid tier only)
- Con: discontinued free tier
- Verdict: not for v1

### NewsAPI.org
- Source: newsapi.org (free tier: 100 req/day, 1-month old)
- Con: stale, low rate limit, NOT real-time
- Verdict: not useful

### Reddit / Twitter (alternative)
- Source: r/wallstreetbets, X/Twitter API
- Pro: where catalysts go viral first
- Con: scraping violates ToS; X API now paid
- Verdict: SKIP — risk vs value

### Nasdaq free news (nasdaq.com/articles)
- Source: nasdaq.com (public)
- Pro: free, focused on US equities
- Con: scrape risk; no API
- Verdict: backup if TradingView MCP unavailable

## Verdict (Slot C)
- **Primary**: TradingView MCP `get_news` + `get_news_detail` (intraday catalyst alerts)
- **Secondary**: Finnhub (already integrated; daily baseline + earnings calendar)
- **Tertiary**: SEC EDGAR 8-K scanner (free, authoritative; daily cron)
- **Existing reuse**: keep `news_providers.py` Finnhub chain; ADD a `tv_news.py` adapter that wraps the MCP `get_news` call

## Score
- Fit: 4/5 (TV MCP is enough for catalyst alerts; SEC EDGAR for fundamentals)
- Integration cost: 2/5 (~150 LoC TV MCP wrapper)
- Data cost: 1/5 (free tier covers ~50 symbols/day which is plenty for daily 4-6 stock watchlist)