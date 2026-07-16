# Slot B — Real-time Price Stream (WebSocket / live ticks)

## Sources investigated

### Alpaca WebSocket (existing in pipeline)
- `trading_agent/alpaca_ws_subprocess.py` and `live_event_loop.py`
- Status: working in DEV container; uses `stream = Stream(alpaca_key, alpaca_secret, base_url=URL, data_feed='iex')`
- Pro: IEX feed is FREE for paper, SIP feed is paid. 200 symbols free in IEX.
- Con: IEX = inverted venue, slightly slower vs SIP (good enough for day trading)
- Library: `alpaca-py` ★1.4k Apache-2.0, last push 2026-07-16

### IB Gateway market data
- Source: Interactive Brokers via ib_insync (erdewit/ib_insync ★3.2k BSD-2-Clause, last push 2024-03-14)
- Status: ibgw_relay.py at 10.8.0.2:5055 working for ORDER placement
- Pro: real-time US tape data (subject to IB market data subscription)
- Con: IB market data subscription costs $4-30/mo per exchange
- Con: Kay's existing relay only does orders, NOT streaming market data
- Status: would need additional relay code (reqMarketDataType + reqMktData stream)

### TradingView MCP WebSocket (NEW option)
- Source: https://www.tradingviewapi.com/websocket/ — distinct from MCP, full-duplex
- Pro: real-time streaming, low latency, 250+ exchanges, no exchange fees
- Con: paid RapidAPI tier for WebSocket (HTTP MCP is the lower-cost option)
- Status: separate endpoint, requires additional subscription

### TradingView MCP HTTP polling (fallback)
- 11 tools over HTTPS; `get_quote` and `get_quote_batch` return last-trade + bid/ask
- Pro: simple, just HTTP, easy to cache to Redis/disk
- Con: NOT a true stream; ~1s polling rate = 1s latency (Ross uses 1-2s candles)
- Verdict: viable for non-streaming use; can't replace WebSocket for HFT-grade ticks

### Finnhub WebSocket
- Source: Finnhub-Stock-API/finnhub-python ★1k Apache-2.0
- Pro: free tier WS for US trades; ~50 symbols subscribe limit on free
- Con: 50 symbols free is too low for a 200-symbol universe
- Pro: includes NBBO (bid/ask)

### Polygon.io WebSocket
- Status: Polygon now requires a paid plan for real-time WebSocket
- Free tier: delayed 15-min only, no WS access
- Source: https://polygon.io/pricing (verified 2026-07-16, free tier limitations)

## Verdict (Slot B)
- **Primary**: Alpaca WebSocket via IEX (already wired, free, sufficient for Ross-grade signals)
- **Secondary**: TradingView MCP `get_quote_batch` for HTTP fallback (price every 2-5s)
- **Existing reuse**: `live_event_loop.py` and `alpaca_ws_subprocess.py` — keep them as-is, route new dashboard widget to consume their already-streamed data via Redis pub/sub
- **UAT/PROD gap**: build the same Alpaca WS adapter for UAT PROD; for IB-only future, add a parallel IB market data relay (out of scope for v1)

## Score
- Fit: 4/5 (Alpaca IEX is enough; we accept 200-symbol limit)
- Integration cost: 2/5 (already integrated; just wire consumer to it)
- Data cost: 1/5 (free IEX)