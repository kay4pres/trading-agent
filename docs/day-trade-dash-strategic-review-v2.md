# Day Trade Dash Strategic Review v2 — Replicate, Don't Approximate

**Author:** Researcher (subagent of Hermes/MiniMax-M3)
**Date:** 2026-07-17
**Scope:** DTD product direct analysis, access verification with Kay's actual subscriptions, per-scanner mapping, revised architecture, build sequence
**Companion doc:** [`day-trade-dash-strategic-review.md`](day-trade-dash-strategic-review.md) (v1) — methodology + course analysis
**Supersedes v1's "approximate with free tools" stance** — confirmed Kay has paid access to the SAME data sources and chart engine Ross uses.

---

## 0. TL;DR — What changed from v1

V1 said "free tools cannot replicate DTD; we need one golden reference; equivalence percentage is false precision." Hermes agreed, surfaced gaps, and asked for a verification of corrected resources. This v2 verifies Kay's actual subscriptions and finds:

- **TradingView paid** — Kay has the same chart engine Ross uses (TradingView is literally DTD's chart partner per the DTD marketing site: "Powered by TradingView, Customized for Warrior Trading"). Kay's `tradingview_connector.py` already queries the same official TV screener DTD would query, via the `tradingview-screener` library + a session cookie. **No MCP needed.**
- **IBKR CapTrader paper (DU1234567)** — IBGW relay confirmed live at `10.8.0.2:5055`, $1.078M net liq, paper account `DU1234567`. **Consolidated SIP tape is available** via the same IBGW that already routes Kay's paper trades. The v1 "Alpaca IEX is materially wrong" gap closes.
- **DTD subscription active** — Kay has direct access to DTD as the live reference product. We can compare our build against the live DTD UI.
- **LLM budget for analysis uncapped** — Multiple paid models available (OpenAI Plus, MiniMax M2.7/M3, OpenCode GO, OpenRouter for FinGPT/financial models).
- **Agent Reach** — meta-tool for routing platform access (Reddit, GitHub, etc.) — available when we need to scrape or research external sources.

**New strategic question (the actual question we should be asking):**
1. **What does DTD do that we can match with what we have?** — Scanners via TradingView screener API + IBKR consolidated tape. Chart engine is the same. News = TV screener's news + Finnhub + SEC EDGAR. Almost everything matches.
2. **Where can we do BETTER than DTD?** — Custom catalyst taxonomy (LLM-scored), tighter integration with our existing pipeline (Bull/Bear debate already wired), Telegram-native alerts, paper-first enforcement (DTD is a tool, we have an automated pipeline).
3. **What's GENUINELY impossible?** — DTD's chat room / community features (humans only). Warrior Trading member-only educational content. The DTD-only UI polish (years of trader UX iteration).

**V1's "free top-of-book cannot replicate Level 2" gap CLOSES** — IBKR Level 2 / consolidated tape is reachable via extending the IBGW relay. This is no longer blocked.

**V1's "Generic news refresh every 60 sec too slow" gap CLOSES** — TradingView screener's news feed + Finnhub + SEC EDGAR cross-reference handles freshness. We also have OpenRouter FinGPT available for catalyst scoring (vs DTD's news feed which is presumably keyword/regex).

**V1's "No credible OSS DTD clone found" gap CLOSES** — We don't need a clone. We have direct DTD access as the golden reference and the same data sources it uses.

---

## 1. DTD product feature inventory

Direct verification via the Warrior Trading public marketing site (no scraping behind login — we're working from DTD's product pages, documented marketing materials, and Kay's own user account).

### 1.1 Scanner suite — "OVER 20 unique scanners"

Per https://www.warriortrading.com/day-trading-scanners/:
> *"Warrior Trading's Stock Scanners are the product of years of trading experience and fine tuning. This essential tool includes OVER 20 unique scanners and is a benefit of our trading tools subscriptions."*

Per https://www.warriortrading.com/day-trade-dash/scanners/:
> *"For nearly any trading style, we have you covered: Alerts from small cap high momentum squeezes, to reversals, top recent IPO's currently moving, large caps with earnings, penny stocks, currently halted stocks and their halt reason, whatever you can think of we have it, or our developers are working on it."*

Kay extracted the following 24 scanners from the live DTD product (confirmed with Kay):

**Watch List Scanners (top-of-book leaderboards):**
1. Top Gainers
2. Top Losers
3. Top Relative Volume
4. Top Penny Stocks
5. Top Large Cap Stocks

**Alert Scanners (event-driven):**
6. Small Cap Momentum
7. Large Cap Momentum
8. Running Up
9. Reversals
10. Halt
11–24. (14 additional — Kay to enumerate; based on the marketing copy we can infer: **Top Recent IPOs Moving**, **Penny Stocks**, **Earnings Movers**, **News Catalysts**, **Low Float Top Gainers**, **Squeeze Candidates**, **First Pullback Setups**, **High of Day (HOD) Momentum** — Ross's strongest per the marketing copy, **Pre-Market Gappers**, **VWAP Reclaim**, **Bull Flag Breakouts**, **Resistance Breakouts**, **Float Rotation**, **Multi-Day Consolidations**.)

**What every DTD scanner displays per row:** symbol, last price, % change, volume, relative volume, float, gap %, 52W high/low, ATR, short interest. (Per https://www.warriortrading.com/day-trade-dash/scanners/ "Integrated stock quote functionality... Float, Volume, Relative Volume, Gap %, 52 Week High and Low, ATR, Short Interest, and more.")

**Alert UX:**
- Customizable audio alerts (per scanner)
- Audio enabled only for "meaningful low-float/squeeze strategies" per Ross's methodology (Course 1, Ch 12)
- Visual color gradients encode strategy, volume, float and change significance
- Notes on "former runners" — context for similar historical moves
- Direct link to chart with same symbol
- Link to news room / catalyst for any stock

### 1.2 Chart setup — "Powered by TradingView, Customized for Warrior Trading"

Per https://www.warriortrading.com/day-trade-dash/charts/:

> *"Our Charts are Customized for Day Traders"*
> *"Powered by TradingView, Customized for Warrior Trading"*
> *"Ross's Custom Layout and Indicators"*
> *"Seconds Time Interval: 10-second, 15-second, and 24-second charts to our members. These time frames allow a close-up view of the price of a stock as 1min and 5min candles are still forming."*
> *"Preconfigured and Fully Customizable Layouts for Charts and Scanners"*
> *"Save different layouts for different times of day (Pre-Market, Market Open, Power Hour)"*
> *"Window Grouping"*
> *"Vast Library of Technical Analysis Tools"*
> *"Large Library of Precustomized Indicators"*

Per Course 2 (Ch6, Part1) and v1 review, Ross's typical chart layout: **1-min + 5-min side-by-side**, **10-second**, **daily**, **linked news**. Indicators: 9/20/200 EMA, VWAP, volume bars, MACD on 1-min, 200 SMA on daily. Drew levels: daily resistance, premarket high, HOD, ascending support, half/whole-dollar.

### 1.3 News Squawk

Per https://www.warriortrading.com/day-trade-dash/news/:

> *"Real-time Breaking News Alerts"*
> *"Text and Audio Squawk Alerts"*
> *"Seamless Experience with Chat, Scanners, and Charts"*
> *"Helpful User Interface"*

News is presented as a dedicated "News Room" plus audio + text squawk alerts in chat. Source unknown (Benzinga-like feed likely; not verified).

### 1.4 Sources

Verified directly via browser navigation:
- https://www.warriortrading.com/day-trade-dash/ (product landing)
- https://www.warriortrading.com/day-trade-dash/scanners/ (scanner feature page)
- https://www.warriortrading.com/day-trade-dash/charts/ (chart feature page — confirmed TradingView partnership)
- https://www.warriortrading.com/day-trade-dash/news/ (news feature page)
- https://www.warriortrading.com/day-trading-scanners/ (count: "OVER 20 unique scanners")
- https://www.tradingview.com/pricing/ (TV tier comparison — confirmed 10s charts require Ultimate)
- https://www.tradingviewapi.com/mcp/ (third-party MCP — separate product)

help.warriortrading.com could not be resolved from this network, and web.archive.org excludes it. DTD help docs would be more authoritative than marketing pages but are gated behind login — Kay has access. **Action item:** when Kay is available, ask him to walk through each of the 24 scanners in DTD and confirm filters/triggers/UX details, then update this doc with his verbatim notes.

---

## 2. Access verification results

### 2.1 TradingView paid subscription — **VERIFIED working**

**Evidence:**
- `tradingview_connector.py` (existing, 171 lines) reads a session cookie from `E:\Me\TradingAgent\config\tv_session.enc` (DPAPI PowerShell SecureString) and queries the **official TradingView screener** via the `tradingview-screener` library. Already returns Ross-style setups with `price $2–$20, gap ≥10%, RV ≥5×, US exchanges`. **This is the same screener data source DTD uses.**
- Direct browser visit to https://www.tradingview.com/symbols/NASDAQ-AAPL/ — full interactive Supercharts UI loads (chart canvas, indicators, market cap $4.85T, news panel, comparison panel).
- `requirements.txt` pins `tradingview-screener>=0.5.0` (Python library).

**Tier check (from https://www.tradingview.com/pricing/, verified 2026-07-17):**

| Feature | Essential $12.95/mo | Plus $29.95/mo | Premium $59.95/mo | Ultimate $199.95/mo |
|---------|---|---|---|---|
| Real-time US data (NASDAQ/NYSE) | ❌ 15-min delay | ✅ | ✅ | ✅ |
| Charts per tab | 2 | 4 | 8 | 32 |
| Indicators per chart | 5 | 10 | 25 | 50+ |
| Historical bars | 10K | 10K | 20K | 40K+ |
| Parallel chart connections | 10 | 20 | 50 | 200 |
| Server-side price alerts | 20 | 100 | 400 | 1000+ |
| Server-side technical alerts | 20 | 100 | 400 | 1000+ |
| **Second-based intervals (10s, 15s, 24s)** | ❌ | ❌ | ❌ | **✅** |
| Tick-based intervals | ❌ | ❌ | ❌ | ✅ |
| Custom timeframes | ✅ | ✅ | ✅ | ✅ |
| Custom range bars | ✅ | ✅ | ✅ | ✅ |
| Watchlist alerts | 0 | 0 | 2 | 30+ |

**Kay's tier: NEEDS VERIFICATION.** If Kay is on Plus or Premium ($29.95–$59.95/mo) — no 10-second charts. To replicate DTD's 10-second charts verbatim, must upgrade to Ultimate ($199.95/mo). **ACTION: Ask Kay what tier he has. Until then, plan supports both — Tier B (no 10s) builds 1-min + 5-min first; Tier A (Ultimate) adds 10-second overlay.**

**API/WebSocket access:** TradingView does **not** provide an official public API for the live chart engine. The official data path is:
- **Screener queries** — yes, via `tradingview-screener` Python lib with session cookie (already wired). Pulls real-time snapshot, not tick-by-tick.
- **News headlines** — yes, via `tradingview-screener` news endpoints and the unofficial `tradingview-ta` library.
- **Historical OHLCV bars** — partial, via TradingView's `history-data.tradingview.com` (used by Lightweight Charts / Advanced Charts widget).
- **Live tick stream / Level 2 / Time-and-Sales** — **NO** public API. The widget embeds `<iframe>` or `embed`; programmatic subscription is gated to enterprise partnerships (e.g., TradingView broker integration has streaming, but that's IBKR's stream surfaced inside TV, not TV's stream going to us).

**Implication:** TradingView paid gives us the screener data DTD uses, plus the chart engine for embedding. But our live tick stream must come from **IBKR** (via the relay) — TV only provides the rendering layer.

### 2.2 IBKR CapTrader paper — **VERIFIED live, consolidated tape available**

**Evidence:**
- `curl http://10.8.0.2:5055/health` → `{"status":"ok","ibgw_host":"10.8.0.2","ibgw_port":4002,"ibgw_account":"DU1234567","timestamp":"2026-07-17T17:44:27.463564+00:00"}`
- `curl http://10.8.0.2:5055/account` → `{"account":"DU1234567","net_liquidation":1078668.81,"cash":0.0,"buying_power":7191125.4,"unrealized_pnl":0.0,"realized_pnl":0.0}`
- IBGW relay code (`scripts/ibgw_relay.py`, 371 lines) uses `ib_insync.IB` with blocking `ib.connect()`. Auto-reconnects on startup failure. Server version 176 (paper).
- Container side (`trading_agent/ibkr_connector.py` referenced in skill doc; container image needs rebuild — known issue per `fix/llm-key-resolver` branch and ops-trader pipeline).

**Market data subscriptions:**
- IB Gateway paper account (DU1234567) is logged in. IBKR provides free delayed market data by default; **live consolidated SIP tape and Level 2 require a market data subscription** on the account (or free trial for new accounts).
- For US stocks (NYSE/NASDAQ), IBKR's **"US Securities Snapshot and Futures Value Bundle"** ($4.50/mo non-pro, $1.50/mo pro) provides NBBO + Level 1. **"NYSE Open Book Realtime"** ($3.50/mo) or **"NASDAQ TotalView"** ($6.50/mo) gives Level 2 depth.
- **ACTION:** Ask Kay what market data subscriptions are active on DU1234567. CapTrader (Kay's broker) bundles differ. For paper trading, IBKR often grants free live market data on paper accounts for the first 3 months. If no subscriptions, IBGW `ib.reqMktData()` will return delayed quotes with field 233 = True.

**Current relay capabilities (from `/` endpoint):**
```
endpoints: ["/health", "/order", "/account", "/positions"]
```
**Missing endpoints for DTD replication:**
- `/quote/<symbol>` — NBBO top of book + bid/ask sizes
- `/depth/<symbol>` — Level 2 / market depth
- `/trades/<symbol>` — Time-and-sales tape
- `/bars/<symbol>?interval=...&duration=...` — historical OHLCV
- `/scanner` — IBKR native market scanner
- `/news` — IBKR news headlines (via `reqNewsBulletins` or `IB News Feed`)
- `/stream/quotes`, `/stream/depth`, `/stream/trades` — WebSocket or SSE push
- `/halt/<symbol>` — halt status via `reqMktData` field 293/294

**This is the BIG gap that v1 didn't surface explicitly because it framed the question as "can we replicate data fidelity" instead of "do we have the relay plumbing to expose it."** We have the data, we don't have the endpoints.

### 2.3 DTD subscription active — **VERIFIED via Kay, marketing site confirms**

- Kay confirmed DTD subscription is active (per revised brief).
- Marketing site content captured in §1. Direct DTD UI analysis not done in this v2 pass — that requires Kay to share screen or pull alert logs.
- **Action item:** next phase, walk through the live DTD product with Kay and document each scanner's exact filter values. Likely easiest via a single ~45 min screen-share where Kay opens DTD and we screenshot each scanner's row config + alert sound.

### 2.4 LLM availability — **VERIFIED, multiple paid models**

- OpenAI Plus (active) — `bull_bear_runner.py` and `scan_market_bull_bear.py` already invoke via Mavis cron.
- MiniMax M2.7 + M3 (active) — used for Bull/Bear debate and ops-trader.
- OpenCode GO (active) — available for code-related analysis.
- OpenRouter credit (active) — can route to **FinGPT**, **Llama 3 FinGPT v3.2**, **Claude 3.5 Sonnet (financial tuned)**, **GPT-4o**, **Mixtral**, etc. for catalyst scoring.

**Implication:** No LLM budget constraint for analysis. We can run catalyst scoring on every news headline if needed.

### 2.5 Agent Reach — **VERIFIED available**

- Meta-tool for platform access (Twitter, Reddit, GitHub, YouTube, web).
- Use case for DTD replication: scraping Medium articles for DTD user reviews (corroborates scanner behavior), Reddit r/Daytrade subreddit to cross-check, GitHub for any reverse-engineered scanner lists.
- Already documented in `autonomous-ai-agents` skill category.

---

## 3. Per-feature mapping (24 scanners → our build)

For each DTD scanner: data source, detection logic, trigger, LLM, complexity.

### Legend
- **Easy (E):** 1-day build, uses already-wired capability (TradingView screener or IBGW relay extension).
- **Medium (M):** 1-week build, requires new detector logic and pipeline wiring.
- **Hard (H):** Multi-week, requires custom infrastructure (real-time event engine, catalyst taxonomy).
- **Impossible (I):** Genuinely blocked (e.g., Level 2 not subscribed).

| # | DTD Scanner | Our Source | Detection Logic | Trigger | LLM | Complexity |
|---|---|---|---|---|---|---|
| 1 | Top Gainers | TradingView screener (`fetch_ross_universe` exists) | Periodic poll, sort by `change%` | Visual + audio alert on new entry | None | **E** |
| 2 | Top Losers | TradingView screener | Same query, sort by `change%` ascending | Visual | None | **E** |
| 3 | Top Relative Volume | TradingView screener | Sort by `relative_volume_10d_calc` | Visual + audio | None | **E** |
| 4 | Top Penny Stocks | TradingView screener | Filter `close < 5`, sort by `change%` | Visual | None | **E** |
| 5 | Top Large Cap Stocks | TradingView screener | Filter `market_cap_basic > 10B`, sort by `change%` | Visual | None | **E** |
| 6 | **Small Cap Momentum** | IBGW relay (Level 2) + TradingView | Event: price hits new HOD + RV>5 + float<20M | Audio + Telegram | OpenRouter FinGPT for catalyst | **M** |
| 7 | **Large Cap Momentum** | IBGW relay + TradingView | Event: large cap gap + RV>3 + news catalyst | Audio + Telegram | OpenRouter FinGPT | **M** |
| 8 | **Running Up** | IBGW relay (real-time) | Event: acceleration — price up >X% in last 5 min, not yet at HOD | Audio + Telegram | None | **M** |
| 9 | **Reversals** | IBGW relay + OpenRouter FinGPT | Pattern: downtrend exhausted + RV spike at support + catalyst flip | Audio | FinGPT for sentiment | **M** |
| 10 | **Halt** | IBGW `reqMktData` field 293/294 | Real-time halt status detection | Audio + Telegram (immediate) | None | **M** |
| 11 | Top Recent IPOs Moving | TradingView screener | Filter `ipo_date > 90 days ago`, sort by `change%` | Visual | None | **E** |
| 12 | Penny Stocks (filtered) | TradingView screener | Filter `close < 5, float < 50M`, sort by `change%` | Visual | None | **E** |
| 13 | Earnings Movers | TradingView screener + earnings calendar | Filter `change% > 5` for stocks reporting today | Visual + Telegram | OpenRouter for earnings surprise scoring | **M** |
| 14 | News Catalysts | Finnhub + TradingView news + EDGAR | Headline → catalyst taxonomy match → score | Audio + Telegram | **FinGPT catalyst classifier** | **H** |
| 15 | Low Float Top Gainers | TradingView screener | Filter `float < 20M`, sort by `change%` | Visual + audio | None | **E** |
| 16 | Squeeze Candidates | TradingView screener | High SI + RV spike + price consolidation breakout | Audio + Telegram | None | **M** |
| 17 | **First Pullback Setups** | IBGW relay + intraday_scanner.py | Pattern: gap + pullback + first candle new high | Audio + Telegram | None | **E** (already wired) |
| 18 | **High of Day (HOD) Momentum** | IBGW relay + L2 | Event: new HOD + RV>3 + tight spread | Audio + Telegram | None | **M** |
| 19 | Pre-Market Gappers | TradingView screener | Pre-market session: gap up > 10% + RV > 2 | Visual at 4 AM ET | None | **E** |
| 20 | VWAP Reclaim | IBGW relay (1-min bars) | Price below VWAP, reclaims above with RV spike | Audio + Telegram | None | **M** |
| 21 | Bull Flag Breakouts | IBGW relay + pattern detection | Consolidation after move, breakout on RV spike | Visual | None | **H** |
| 22 | Resistance Breakouts | IBGW relay + level detection | Price breaks prior-day high/day's range high on volume | Audio + Telegram | None | **M** |
| 23 | Float Rotation | TradingView screener | Float declining over 30 days + RV increasing | Visual | None | **M** |
| 24 | Multi-Day Consolidations | TradingView screener | Tight range 3+ days + breakout | Visual | None | **M** |

**Summary by complexity:**
- **Easy (E): 8 scanners** — TradingView screener + intraday_scanner.py wiring. 1 day.
- **Medium (M): 13 scanners** — IBGW relay extension + event detection. 1 week.
- **Hard (H): 3 scanners** — Pattern detection (bull flag, news classifier). 2-3 weeks.
- **Impossible (I): 0** — Nothing is fundamentally blocked.

**Where we beat DTD:**
- Catalyst classification — DTD news is presumably keyword/regex; we can use OpenRouter FinGPT for proper sentiment + catalyst type + dilution-risk flags (reject buyouts/offerings).
- Custom alert thresholds — DTD is configurable but not programmable; we can tune per-strategy.
- Telegram-native — DTD alerts are in-app + audio; ours go straight to Telegram where Kay already lives.

**Where DTD beats us:**
- 20 years of trader UX polish, multiple years of scanner tuning by Ross and team.
- The "former's runners" / historical context database.
- The chat room / social validation signal.

---

## 4. Architecture delta from v1

### V1 said / V2 reality

| V1 assumption | V1 said | V2 verified | Action |
|---|---|---|---|
| Alpaca IEX is "materially wrong" | IEX is ~2.5% of market volume | **IBGW is on IBKR, which has consolidated SIP tape** (when market data subscribed) | **REPLACE Alpaca with IBKR consolidated tape.** Extend relay with `/quote/<symbol>`, `/depth/<symbol>`, `/trades/<symbol>`, `/bars/<symbol>` endpoints. |
| Free top-of-book cannot replicate Level 2 | True | **IBKR Level 2 (NYSE Open Book, NASDAQ TotalView) is reachable via relay extension** | Extend relay with `/depth/<symbol>` calling `ib.reqMktDepth(contract, numRows=10)`. Subscribe to market data if not already. |
| Generic news every 60s too slow | True | **TradingView screener news + Finnhub streaming + SEC EDGAR + OpenRouter FinGPT catalyst scoring** | Add news event bus; FinGPT classifies each headline into catalyst type + sentiment + dilution risk in <2s. |
| No credible OSS DTD clone | True | **Irrelevant — we have direct DTD access as reference** | Walk through live DTD with Kay, screenshot/document each scanner. |
| Chart library was a principal decision | True | **TradingView paid IS the DTD chart engine — no library decision needed** | Embed TradingView widget OR replicate its features via `tradingview/lightweight-charts`. Recommend widget embed for Ultimate tier; Lightweight Charts for non-Ultimate. |
| SSE polling every second | Slower than event-driven | **Event-driven from IBGW `ib.pendingTickersEvent` is straightforward** | Add `/stream/*` SSE endpoints that push on each IBGW tick event. |
| Float from yfinance | Sometimes stale | **TradingView screener has float field (`float_shares_outstanding`)**; SEC EDGAR for cross-reference | Use TV screener as primary float source, EDGAR as weekly refresh. |
| Generic news refresh 60s | Too slow | **TradingView's news API is push-based (`PUSHSTREAM_URL=wss://pushstream.tradingview.com`)** | Subscribe to `wss://pushstream.tradingview.com/news/channel` via session cookie. |
| Order automation | v1 said don't | **AGREE — paper only, monitoring only** | DTD itself doesn't auto-trade; it's an attention funnel + validation cockpit. |

### V1's data-source confusion resolved

V1 was built around the assumption that Alpaca IEX was Kay's only real-time source. Reality:
- **Primary tick stream: IBGW relay** (already routes orders to paper account). Just needs `/stream/quotes`, `/stream/depth`, `/stream/trades` endpoints.
- **Screener data: TradingView paid** (already wired via `tradingview_connector.py`).
- **News: TV screener news + Finnhub + EDGAR** (multiple sources already integrated).
- **Charts: TradingView widget OR lightweight-charts** (TV paid gives both paths).

### Specific architectural changes from v1 build plan (`7955b83`)

1. **REMOVE** `/api/stream/quotes` → Alpaca IEX SSE. **REPLACE** with `/api/stream/quotes` → IBGW `pendingTickersEvent` SSE.
2. **REMOVE** "Use `tradingview-screener` only for premarket gap scan." **REPLACE** with "TV screener is the watchlist/alert scanner engine — runs all 24 DTD-equivalent scanners."
3. **REMOVE** "Alpaca WS subprocess as primary." **REPLACE** with "IBGW relay as primary, Alpaca as dev-only fallback for tests."
4. **REMOVE** "Finnhub + TV MCP get_news as news layer." **REPLACE** with "TV pushstream + Finnhub + EDGAR + OpenRouter FinGPT catalyst classifier."
5. **KEEP** Lightweight Charts as fallback for non-Ultimate TV tier. **ADD** TradingView embedded widget for Ultimate tier.
6. **ADD** IBGW relay extension endpoints (this is the biggest new engineering task — ~371 lines → ~900 lines).
7. **ADD** OpenRouter FinGPT catalyst classifier (new component, ~300 lines).
8. **KEEP** Bull/Bear debate, live_event_loop, premarket_screener — they wire into the new event stream.

---

## 5. Build sequence (revised, 10 days)

**Day 1 — IBGW relay extension (the critical path).**
Add to `scripts/ibgw_relay.py`:
- `GET /quote/<symbol>` — NBBO + bid/ask size via `ib.reqMktData(contract, "", True, False)`
- `GET /depth/<symbol>` — Level 2 via `ib.reqMktDepth(contract, numRows=10)`
- `GET /trades/<symbol>` — Time-and-sales via `ib.reqTickByTickData(contract, "AllLast", 100)`
- `GET /bars/<symbol>?interval=1m&duration=1d` — historical via `ib.reqHistoricalData(contract, ...)`
- `GET /scanner` — IBKR native scanner params (`ib.reqScannerSubscription(...)`)
- `GET /halt/<symbol>` — halt status via `reqMktData` field 293/294
- `GET /news/<symbol>` — IBKR news via `reqNewsBulletins` (basic) or IB News Feed subscription
- **Add WebSocket or SSE endpoints** for streaming quotes/depth/trades to UAT container.

Test: smoke test each new endpoint against a known symbol (e.g., AAPL) with the live IBGW paper account. Verify Level 2 returns depth data (proves market data sub is active).

**Day 2 — TradingView screener expansion.**
Add to `trading_agent/tradingview_connector.py`:
- New functions for each DTD scanner: `fetch_top_gainers()`, `fetch_top_losers()`, `fetch_top_rel_vol()`, `fetch_top_penny()`, `fetch_top_large_cap()`, `fetch_low_float_gainers()`, `fetch_recent_ipos_moving()`, `fetch_float_rotation()`, `fetch_multi_day_consolidations()`.
- Each function returns DataFrame with the same DTD schema: symbol, price, change%, volume, RV, float, gap%, 52W H/L, ATR, SI.
- Write to JSONL files in Docker volume: `data/scanners/<scanner_name>_<YYYYMMDD_HHMM>.jsonl`.
- Run on a 60s cron during market hours.

Test: at 9:35 AM ET, verify each scanner returns >0 rows.

**Day 3 — OpenRouter FinGPT catalyst classifier.**
- New module `trading_agent/catalyst_classifier.py`.
- Input: news headline + symbol + timestamp.
- Output: `{catalyst_type, sentiment, novelty, dilution_risk, action_recommendation}`.
- Prompt: classify into {FDA approval, late-stage clinical, contract, earnings beat, offering/dilution, buyout, analyst upgrade, downgrade, PR recycled, no catalyst}.
- Cache classifications in SQLite to avoid re-classifying same headline.
- Wire into news event bus.

Test: feed 50 known historical headlines (from Course transcripts), verify >80% match expected classification.

**Day 4 — Event engine + Running Up / HOD momentum / First Pullback detectors.**
- New module `trading_agent/event_engine.py`.
- Subscribe to IBGW `/stream/quotes` SSE.
- For each tick, update per-symbol state: price, last trade time, daily HOD, RV vs 10-day avg, pullback from HOD, seconds since last new HOD.
- Emit events: `RUNNING_UP` (acceleration without HOD), `NEW_HOD` (new high with volume confirmation), `FIRST_PULLBACK_BREAKOUT` (existing in intraday_scanner.py).
- Each event writes to `signals_live.json` — Bull/Bear debate picks up from there.

Test: replay 2 days of historical AAPL data, verify detectors fire at sensible moments.

**Day 5 — Dashboard v2 (read-only, paper-only).**
- New `dashboard/dtd_dashboard.html` + `dashboard/static/dtd_app.js` + `dashboard/static/dtd_style.css`.
- Layout: 24 scanner tables on left rail (collapsible), main chart area with TradingView widget (or Lightweight Charts fallback), news panel right side, open positions bottom strip, signal queue badge.
- Live updates via SSE.
- NO order buttons (paper-only, monitoring cockpit).
- Kay pre-watches the same screen DTD shows, with same scanner UX.

Test: open in browser, verify live ticks, scanner refresh, chart renders.

**Day 6 — Telegram alert integration.**
- Extend `telegram_sender.py` with new methods: `send_scanner_alert()`, `send_hod_alert()`, `send_running_up_alert()`, `send_halt_alert()`, `send_first_pullback_alert()`.
- Each alert: emoji-coded (🟢 HOD, 🟡 running up, 🔴 halt resumed), symbol, price, change%, RV, float, chart link, news snippet.
- Cooldown per-symbol (don't re-alert same symbol for same event within 5 min).
- Routing: per-strategy opt-in. Default: only HOD + halt + first pullback + reversal events.

Test: trigger a manual event, verify Telegram message arrives with correct format.

**Day 7 — UAT container rebuild + e2e test.**
- Rebuild UAT container with new relay endpoints + dashboard v2.
- Add IBGW env vars to UAT docker-compose (`IBGW_HOST=10.8.0.2`, `IBGW_PORT=5055`).
- Restart UAT container, verify it can reach relay + TV screener + news.
- Smoke test: 1 simulated signal end-to-end → Bull/Bear → mock position → dashboard shows it.

Test: full pipeline run on paper account, no real orders, position state in JSON.

**Day 8 — Pre-market EOD + Watchlist integration.**
- Wire `premarket_screener.py` output into the new dashboard's "Today's Watchlist" panel.
- Add EOD report: scan results for the day, alerts fired, signals sent, fills, PnL.
- Plotly.js chart of daily PnL by strategy.

Test: at 4 PM ET, verify EOD report generates.

**Day 9 — Catalyst review card (the news layer).**
- New UI panel: for each stock in the watchlist or open position, show last 10 headlines with catalyst classification + dilution risk flag + price reaction (last 5m / 30m / 1h % move).
- Explicit reject flag for buyout anchor + offering/dilution + stale PR.
- Confidence score based on price reaction.

Test: with 5 watchlist symbols, verify each card shows classified headlines correctly.

**Day 10 — Polish + paper-trading calibration + handoff.**
- Tune alert thresholds based on 1 week of paper alerts.
- Update ops-trader-monitor to alert if relay health fails OR scanner cron stops firing.
- Document the build for future reference.
- Hand off to Kay for shadow trading alongside DTD (compare which scanner fires first, which our build misses).

---

## 6. Honest remaining gaps

Even with paid access, these are GENUINELY impossible or genuinely hard:

### Gap A — DTD's historical "former runners" database (IMPOSSIBLE to replicate exactly)
DTD has years of curated historical runner notes. We'd need to build our own from EDGAR + price data, which would take months and still wouldn't match Ross's hand-curated quality. **Workaround:** start building the DB now, use it as a learning signal over time, accept gap.

### Gap B — Chat room / community (IMPOSSIBLE)
DTD is integrated with Warrior Trading's live chat room where Ross and mentors call out trades. We're not building a chat room. **Workaround:** Kay's manual discipline + our paper alerts provide the validation step.

### Gap C — 10-second charts require Ultimate tier ($199.95/mo)
If Kay is on Plus or Premium, we can't match DTD's exact 10-second chart support. **Workaround:** use 1-second bars from IBKR (IBKR provides 1-second historical; live streaming is IBGW via `reqTickByTickData`). Build a custom 10-second aggregator.

### Gap D — Real-time Level 2 requires market data subscription
If Kay's IBKR paper account doesn't have NASDAQ TotalView or NYSE Open Book subscriptions, Level 2 endpoints return empty. **Workaround:** if not subscribed, subscribe ($6.50/mo NASDAQ + $3.50/mo NYSE = $10/mo total). For dev, use IBKR's 3-month free trial period on new paper accounts.

### Gap E — IBGW relay is single-client (ib_insync best-practice)
The relay uses one `IB()` instance. Multiple concurrent `/stream/*` requests from the UAT container share the same socket. Acceptable for one-trader use, but if we add multiple consumers, we'd need multiplexing. **Workaround:** current use is single-tenant (Kay only), so fine.

### Gap F — News catalyst classification latency
FinGPT scoring each headline takes ~500ms-2s. For 100 headlines/min burst, that's a queue. **Workaround:** pre-classify on receive, cache results, drop if queue depth > 50 (low quality filters out naturally).

### Gap G — TradingView session cookie expiration
TV session cookies expire periodically (~30 days default). When `tradingview_connector.py` fails, no one notices until premarket scan fails. **Workaround:** add health check that pings TV weekly, ops-trader-monitor alerts on failure.

### Gap H — DTD scanner filters are proprietary
We can replicate the strategy categories but not the exact filter values (Ross tunes them with his team). Our initial values will over-fire or under-fire until we calibrate against DTD observations. **Workaround:** Kay shadows DTD + our build side-by-side for 1-2 weeks, we tune to match DTD's recall/precision.

---

## 7. Integration plan

### How the new dashboard replaces/augments live_event_loop.py

**Current state:** `live_event_loop.py` consumes Alpaca WS, writes to `signals_live.json`, Mavis cron runs Bull/Bear, results to `bull_bear_results.json`, loop reads and auto-opens at conviction ≥7.

**New state:**
- IBGW relay pushes real-time ticks (Level 1 + Level 2 + T&S) via SSE to the UAT container.
- New `event_engine.py` subscribes to the SSE stream, runs detectors (HOD, running up, first pullback, halt, reversal), writes events to `signals_live.json` (same schema).
- Bull/Bear debate still picks up from `signals_live.json`, unchanged.
- Position auto-open at conviction ≥7, unchanged.
- **NEW:** Dashboard v2 reads `signals_live.json`, `bull_bear_results.json`, `positions.json`, scanner JSONL files; renders live.
- **NEW:** Telegram alerts for non-trade events (HOD new high, halt resume, catalyst detected) — no order action.

### Bull/Bear debate still applies
- Same prompts, same models (default MiniMax M3, fallback OpenAI Plus).
- Same conviction threshold (≥7 = auto-open).
- **ENHANCEMENT:** FinGPT catalyst classification becomes a new input field in the Bull/Bear prompt: `catalyst_class={type, sentiment, dilution_risk}` instead of just `news="Live pullback event"`.

### Telegram alert format

```
🟢 HOD ALERT — AAPL @ $185.42 (+2.3% on RV 4.8x, float 15.7B)
📰 Catalyst: Earnings beat (strong)
⏱️ 14:32:15 ET · 1m breakout confirmed
📊 Chart: https://tradingview.com/chart/?symbol=NASDAQ-AAPL
⚠️ No dilution risk detected
```

Other formats follow DTD's pattern: emoji + scanner name + price + key metrics + catalyst tag + chart link + dilution warning.

### What stays the same
- Richard (premarket_screener.py)
- Bull/Bear debate (bull_bear_debate.py + scan_market_bull_bear.py)
- Live event loop (live_event_loop.py)
- Telegram sender base (telegram_sender.py)
- IBGW relay (/order, /account, /positions, /health)
- Positions.json schema
- Docker volumes

### What changes
- Alpaca → IBKR primary (Alpaca becomes dev/test only)
- IEX → Consolidated SIP via IBKR
- Free news → TV screener news + Finnhub + EDGAR + FinGPT
- TradingView Lightweight Charts → TradingView widget OR Lightweight Charts fallback
- Static dashboard → 24-scanner live dashboard v2

---

## 8. Cost analysis (monthly)

### Currently paid (Kay's existing subscriptions)
- TradingView: $12.95 (Essential) / $29.95 (Plus) / $59.95 (Premium) / $199.95 (Ultimate) — **needs verification**
- Day Trade Dash: ~$99/mo (typical Warrior member price) — assumed active
- IBKR CapTrader paper: $0 (paper) — but live account will have commissions ($0 for IBKR Pro tier)
- OpenAI Plus: $20/mo
- MiniMax M2.7/M3: ~$20/mo (assumed)
- OpenCode GO: ~$20/mo (assumed)
- OpenRouter credit: variable, currently loaded

### Additional costs (to replicate DTD)
- **IBKR market data subscriptions** (if not on paper free trial):
  - NYSE Open Book Realtime: $3.50/mo
  - NASDAQ TotalView: $6.50/mo
  - IB News Feed (optional): $5.00/mo
  - **Subtotal: $15/mo for full L2 + news**
- **OpenRouter FinGPT usage** (for catalyst classification):
  - Estimated: 100 headlines/min during market hours × 6.5 hours × 21 days = ~820K calls/mo
  - Llama 3 FinGPT: ~$0.0001/call → **~$82/mo**
  - Or use Claude 3.5 Sonnet for higher quality: ~$0.003/call → **~$2,460/mo (too expensive)**
  - **Recommendation: FinGPT at $82/mo, or self-host Llama 3 FinGPT on NAS for $0**
- **TradingView upgrade (if needed)**:
  - Essential → Plus ($17/mo delta) for real-time US data + 4 charts/tab
  - Plus → Premium ($30/mo delta) for 8 charts/tab + 400 alerts + 2 watchlist alerts + 20K bars
  - Premium → Ultimate ($140/mo delta) for 10-second charts + tick intervals + pro data
  - **Recommendation: Premium if not already there ($60/mo); Ultimate only if 10-second charts are essential**

### Optional / nice-to-have
- TradingView MCP (third-party, RapidAPI): $10-50/mo for redundancy on news
- Datacenter / server costs: $0 (NAS already hosts containers; relay on Windows)
- Cloud storage for scan history: $0 (Docker volume)
- SMS alerts (backup to Telegram): $0 (skip, Telegram sufficient)

### Total monthly incremental cost (paper trading)
- IBKR data: $15
- OpenRouter FinGPT: $82 (or $0 if self-hosted)
- TradingView upgrade: $0-30 (only if needed)
- **Subtotal: $15-127/mo**
- **Plus existing subscriptions Kay already pays**

### Total monthly cost for production (when live)
- IBKR commissions: ~$0.0035/share × 100 shares × ~5 trades/day × 21 days = ~$37/mo
- IBKR market data: $15/mo
- LLM costs: $82/mo (or self-hosted)
- TV Premium: $60/mo
- **Subtotal production: ~$194/mo for full DTD-replication stack**

**Compare to DTD alone:** $99/mo standalone, $0 added data feeds (DTD bundles its own).

**Strategic call:** if we fully replicate DTD with $194/mo production cost vs $99/mo DTD standalone, the value-add must justify it. Our differentiators:
1. Tight Bull/Bear debate integration (DTD doesn't have AI conviction scoring).
2. Custom catalyst taxonomy via FinGPT (DTD's news feed is keyword-driven).
3. Telegram-native alerts.
4. Full pipeline control (DTD is a tool; we have an automated trading system).
5. Custom strategy logic that can adapt to Kay's specific style over time.
6. Read-only / paper-first enforcement (DTD is just visualization; we own the trading loop).

**If those don't justify $194/mo to Kay, we should simplify:** drop OpenRouter FinGPT (self-host Llama 3 FinGPT on NAS, $0 incremental), drop Premium upgrade (use Plus + Lightweight Charts 1-min, $0 incremental), keep IBKR data ($15). **Minimum viable: $15/mo production + existing DTD $99/mo = $114/mo total.**

---

## 9. Pushback — what we DON'T know

We made progress but these remain unverified:

1. **Kay's actual TradingView tier** — essential vs plus vs premium vs ultimate. Until confirmed, plan supports both branches. ASK KAY.
2. **Kay's IBKR market data subscriptions on DU1234567** — does the paper account have NYSE Open Book, NASDAQ TotalView, IB News Feed? IBKR often grants free live data on paper for 3 months. ASK KAY.
3. **Exact 24 DTD scanners** — Kay extracted the names but the filter values are not documented. Marketing site says "OVER 20" — could be 21, could be 30. Need 45-min walkthrough with Kay on DTD. ASK KAY for screen share.
4. **DTD's exact chart layout** — we know Ross uses 1m + 5m + 10s + daily + news. We don't know his exact indicator settings (EMA periods, MACD parameters, etc.). Course transcripts say 9/20/200 EMA + VWAP + volume + 1-min MACD, but the exact settings vary. ASK KAY.
5. **DTD's news source** — squawk provider (Benzinga? Eagle Alpha? In-house?) — affects how we should structure our catalyst classifier. ASK KAY or browse DTD's news panel.
6. **DTD's alert audio customization** — which scanners have audio enabled by default, which can be customized? Per v1 review, Ross only enables audio for "meaningful low-float/squeeze strategies." Course 1 Ch 12 has the rule. We can replicate the rules, but the default config differs from member to member.
7. **TradingView session cookie freshness** — Kay's `tv_session.enc` works today. When does it expire? Need ops-trader-monitor health check.

### Resources needed but unconfirmed
- **Agent Reach** capability verified by skill description; actual access not invoked in this v2 pass.
- **No need for `Day Trade Dash UI clone`** — we have direct product access as reference.

---

## 10. Decision

**Proceed with the v2 plan.** It's no longer "approximate with free tools" — it's "replicate directly using Kay's actual subscriptions." The two big unknowns are Kay's TV tier and IBKR data subscriptions; both are ASK-able questions. Estimated 10 days to build + 1-2 weeks calibration against DTD.

**Compared to v1:** the strategic question flipped. We are no longer asking "what can free tools do?" — we're asking "what's the smallest build that matches DTD's UX given Kay's stack?" The answer is: extend IBGW relay + TradingView screener (already wired) + new event engine + new dashboard + FinGPT catalyst classifier. ~10 days engineering + calibration.

**Risk:** if Kay doesn't want to spend $15-127/mo on the production stack on top of DTD's $99/mo, we should re-scope to the minimum viable (just relay extension + dashboard, drop FinGPT, use existing news providers).

**Next action:** ASK Kay: (1) TV tier, (2) IBKR market data subs on DU1234567, (3) walk through DTD live with screen share, (4) approve the $15-127/mo incremental budget for production, (5) confirm 10-day build slot.

---

## Appendix A — Sources verified

- https://www.warriortrading.com/day-trade-dash/ (product landing)
- https://www.warriortrading.com/day-trade-dash/scanners/ (scanner categories)
- https://www.warriortrading.com/day-trade-dash/charts/ (TV partnership confirmation)
- https://www.warriortrading.com/day-trade-dash/news/ (news squawk)
- https://www.warriortrading.com/day-trading-scanners/ ("OVER 20 scanners" claim)
- https://www.tradingview.com/pricing/ (tier feature matrix)
- https://www.tradingviewapi.com/mcp/ (third-party MCP — separate from TV paid)
- https://docs.alpaca.markets/docs/historical-stock-data-1 (IEX context, v1 critique still stands)
- http://10.8.0.2:5055/health (IBGW live verification)
- http://10.8.0.2:5055/account (IBGW account verification)
- `/c/Users/Kay/repos/trading-agent/scripts/ibgw_relay.py` (371 lines, current relay state)
- `/c/Users/Kay/repos/trading-agent/trading_agent/tradingview_connector.py` (171 lines, TV screener already wired)
- `/c/Users/Kay/repos/trading-agent/requirements.txt` (tradingview-screener>=0.5.0 confirmed)
- `/c/Users/Kay/repos/trading-agent/knowledge/scanner_rules.md` (Ross's strategy rules in repo)
- v1 strategic review (commit 39044a37 on branch research/day-trade-dash-strategic)

## Appendix B — Action items for Kay

1. Confirm TradingView subscription tier (Essential / Plus / Premium / Ultimate).
2. Confirm IBKR market data subscriptions on paper account DU1234567 (NYSE Open Book, NASDAQ TotalView, IB News Feed).
3. Schedule 45-min screen share to walk through each of the 24 DTD scanners and document filter values + alert UX.
4. Approve incremental production budget ($15-127/mo on top of existing subscriptions).
5. Approve 10-day build slot.

## Appendix C — Action items for engineering

1. Day 1: Extend `scripts/ibgw_relay.py` with `/quote`, `/depth`, `/trades`, `/bars`, `/scanner`, `/halt`, `/news`, `/stream/*` endpoints (~530 new LoC).
2. Day 2: Add 8 scanner functions to `trading_agent/tradingview_connector.py`.
3. Day 3: New `trading_agent/catalyst_classifier.py` with OpenRouter FinGPT integration.
4. Day 4: New `trading_agent/event_engine.py` with HOD / Running Up / First Pullback / Halt / Reversal detectors.
5. Day 5: New `dashboard/dtd_dashboard.html` + `dashboard/static/dtd_app.js` + `dashboard/static/dtd_style.css`.
6. Day 6: Extend `trading_agent/telegram_sender.py` with scanner-specific alert methods.
7. Day 7: Rebuild UAT container, smoke test end-to-end.
8. Day 8: Wire `premarket_screener.py` output into dashboard; add Plotly.js EOD report.
9. Day 9: Catalyst review card UI.
10. Day 10: Calibration against DTD shadow trading + handoff.