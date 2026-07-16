# Slot F — Level 2 / Order Flow

## Sources investigated

### What Ross Cameron actually uses (research)
- Day Trade Dash (Ross's product) shows: Level 2 (time & sales), tape reading, bid/ask size, VWAP
- BUT: Ross has publicly said on Warrior Trading YouTube that he does NOT depend on Level 2; he watches candle patterns and time-and-sales tape + 1-min candles
- Warrior Trading course methodology emphasizes First Pullback on the 1-2 minute chart with VWAP + 9/20 EMA — NO Level 2
- Source: Ross Cameron YouTube + Warrior Trading courses 1+2 (Kay's transcripts in `trading_agent/quiz/`)

### Free Level 2 / Time-and-Sales options
- Finviz Elite ($24/mo) — only paid
- TradingView paid tier ($15-30/mo) for Level 2 — only paid
- Webull desktop app — FREE retail app with Level 2 — but not API-accessible
- TD Ameritrade thinkorswim — FREE Level 2 with brokerage account
- IBKR TWS — FREE Level 2 if you have funded account

### API-accessible free order flow
- Polygon.io — DISCONTINUED free Level 2
- Alpaca — NO Level 2 data; only NBBO top-of-book (free IEX) or full SIP (paid)
- IBKR via TWS API — possible but undocumented + market data subscription fee
- TradingView MCP — `get_quote` returns bid/ask + sizes (FREE tier), `get_price` for trades

### Can we live WITHOUT Level 2 for Ross's strategy?
- YES — Ross's published strategy is based on:
  1. Catalyst + Float + Gap (pre-market)
  2. First Pullback on 1-2 min candle
  3. Volume spike (RV >5x)
  4. VWAP + EMA crossovers
- Level 2 is a CONFIRMATION tool, not a primary signal
- Kay can manually check Level 2 in WeBull/TWS in parallel with our dashboard
- Time-and-Sales can be approximated from Alpaca's `trade` prints (free IEX)

## Verdict (Slot F)
- **Skip Level 2 API integration for v1**
- Use Alpaca IEX `trade` stream → derived time-and-sales list (last 100 prints per symbol)
- Use TradingView MCP `get_quote` for live bid/ask size (limited but free)
- Document Level 2 as a **manual fallback** in dashboard's "external tools" panel
- Revisit IF: post-Phase-2 if Kay decides he needs it

## Honest gap
- Real Level 2 (full depth of book) requires paid data
- Free alternatives: WeBull desktop, TWS, TD Ameritrade (manual, parallel use)
- This is NOT solvable with free APIs — call it out

## Score
- Fit: 3/5 (we can show top-of-book + trade tape from free feeds; Level 2 not needed for v1)
- Integration cost: 1/5 (already have the data, just expose it)
- Data cost: 1/5 (free; Level 2 depth is paid and out of scope)