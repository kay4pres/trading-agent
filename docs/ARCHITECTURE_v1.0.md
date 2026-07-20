# Trading Agent Architecture v1.0 — DTD-Replica Day Trading System
**Status:** DRAFT (Day 3, 2026-07-20)
**Supersedes:**
- `docs/TRADING_AGENT_ARCHITECTURE_v0.1.md` (alpha/beta single-position system, June 2026)
- `.hermes/plans/momentum-decision-cockpit.md` (8-cap read-only scope, July 2026)
**Replaces both with a phased build of a Day Trade Dash replica that trades live on €2K IBKR.**
**Author:** Hermes (Mavis Code) — orchestrator
**Course citation invariant:** Every architectural decision cites `[C1.ChXX.PX]` or is marked `[INFERRED — Kay sign-off]`.

---

## 0. TL;DR

Build a Day Trade Dash (DTD) replica — Ross Cameron's live product (`https://www.warriortrading.com/day-trade-dash/`) — adapted to trade live on Kay's €2K IBKR CapTrader paper → live account. Start with **top 10 of 24 DTD scanners** (5 watch list + 5 alert), close the remaining 14 after MVP. Use **10-second bars or IBKR consolidated tape event stream** as the live data path. Multi-position 1-3 dynamic. 4 AM ET premarket. Auto-trade with phased guardrails (paper → €500 → €2K, 10% daily loss limit, 21:00 Berlin P&L digest). Course-cited decisions, not "looks right."

## 1. Strategic context (why this exists)

### 1.1 What Kay has (verified)
- **TradingView paid** (`tradingview_connector.py` queries the same `tradingview-screener` library DTD uses) `[INFERRED — Kay sign-off: tier unknown, may need Ultimate for 10s charts]`.
- **IBKR CapTrader paper** — `DU1234567`, $1.078M net liq, IBGW relay live at `10.8.0.2:5055`. Consolidated SIP tape + Level 2 reachable via `ib_insync` extensions to the relay. `[C1.Ch6.P1]` (Level 2 + Time & Sales), `[C1.Ch6.P3]` (halts).
- **DTD subscription active** — direct access as golden reference.
- **LLM budget uncapped** — OpenAI Plus, MiniMax M2.7/M3, OpenCode GO, OpenRouter (FinGPT).

### 1.2 What's wrong with v0.1
v0.1 (`docs/TRADING_AGENT_ARCHITECTURE_v0.1.md`) was right for alpha (1 position, 1 trade/day, paper only) but cannot scale to live. The mode-A/mode-B split, the 30-second Trader polling, the 5-min scanner, and the 1-position cap are all misaligned with day trading on lower timeframes. v0.1 served its purpose; we outgrew it. `[INFERRED — Kay sign-off]`.

### 1.3 What's wrong with the cockpit charter
The `.hermes/plans/momentum-decision-cockpit.md` charter was scoped for 8 watchlist caps, read-only. We need 10-24 DTD scanner caps, event-driven auto-trade, multi-position. Charter is dead. `[INFERRED — Kay sign-off]`.

### 1.4 What we keep
- **Course-citation invariant** — every architectural decision cites `[C1.ChXX.PX]` or `[INFERRED — Kay sign-off]`. This is the operating discipline.
- **5 Pillars scoring** (price, gap, RV, catalyst, float) — `c4_part2_stock_types_rules.md`, `c3_part2_news_catalyst_rules.md`.
- **First Pullback entry** — `c5_intraday_patterns_rules.md`, `c5_reading_charts_rules.md`.
- **ATR-based stops** (entry − 2× intraday ATR, min $0.10) — backtest proven (2026-06-26), strict improvement over fixed $0.10 stop.
- **`positions.json` shared contract** between Richard and Trader.
- **DPAPI vault at `E:\Me\TradingAgent\vault/*.enc`** for all credentials.
- **`TRADING_DATA_DIR` env var** for path resolution (Docker + Windows).
- **Headroom** (token efficiency), **Ponytail** (code quality, NEW code only), **agency-agents** (specialists on demand), **Gstack** (verifier).

---

## 2. The 6 planes

```
  ┌─────────────────────────────────────────────────────────────┐
  │                    KAY (supervisor)                          │
  │              Telegram (dead) + workspace handoffs            │
  └─────────────────────────────────────────────────────────────┘
                              ▲
                              │ daily 21:00 Berlin P&L digest
                              │
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │  GUARDRAILS  │←→│  DASHBOARD   │←→│   EXECUTION  │←→│   DECISION   │
  │              │  │  (:5050)     │  │   (IBKR)     │  │  (Bull/Bear) │
  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
                              ▲                ▲                ▲
                              │                │                │
                              └────────────────┴────────────────┘
                                                │
                                          ┌──────────────┐
                                          │   SCANNER    │
                                          │  (DTD 10/24) │
                                          └──────────────┘
                                                ▲
                                                │
                                          ┌──────────────┐
                                          │    DATA      │
                                          │ (TV + IBKR)  │
                                          └──────────────┘
```

### 2.1 Data plane

**Contract:** Source-agnostic market data. Three input paths:
- **A. TradingView paid** — `tradingview-screener` library with session cookie (`E:\Me\TradingAgent\config\tv_session.enc`, DPAPI). Same screener DTD uses. Returns: symbol, last, %change, volume, relative volume, float, gap %, 52W high/low, ATR, short interest.
- **B. IBKR consolidated tape** via IBGW relay at `http://10.8.0.2:5055`. Extends existing relay with new endpoints: `/quote/<sym>` (NBBO), `/depth/<sym>` (Level 2), `/trades/<sym>` (T&S), `/bars/<sym>?interval=10s&duration=1d` (10-second OHLCV), `/halt/<sym>` (halt status field 293/294). `ib_insync` blocking `ib.reqMktData()`.
- **C. yfinance / Finnhub / SEC EDGAR / Alpha Vantage** — fallback + cross-reference for news, fundamentals, and historical bars. Free tier.

**Why three paths:** Redundancy = reliability. TV is the same data DTD uses (gold standard for scanners); IBKR is the only path to live tick stream + Level 2 + halt info; yfinance/Finnhub are free fallbacks when TV cookie expires or IBGW is down. `[C1.Ch6.P1]` (Level 2 = direct exchange feed, not free top-of-book).

**Timeframe decision (10s vs 1m vs 5m):** Per `c5_intraday_patterns_rules.md` + `c5_reading_charts_rules.md`, Ross's intraday pattern detection uses lower timeframes (1-min, 2-min, 5-min, 10-sec). The "Mark" concept from Ch1 says stock can explode on tick; 5-min polling misses it. **Decision: 10-second bars via IBKR `/bars` endpoint as primary; 1-min bars as fallback if 10s not subscribed.** `[C1.Ch6.P1]`, `[INFERRED — Kay sign-off on TV Ultimate upgrade for 10s overlay]`.

**Owner:** Mavis (orchestrator) coordinates; data access wrapped in `trading_agent/data_plane/` modules.
- `data_plane/tv_screener.py` — TradingView screener queries
- `data_plane/ibkr_quote.py` — IBKR NBBO + Level 2 + T&S
- `data_plane/ibkr_bars.py` — 10s / 1m / 5m OHLCV bars
- `data_plane/yfinance_fallback.py` — yfinance + Finnhub + EDGAR fallback
- `data_plane/cache.py` — Redis-like in-memory cache (TTL per data type: 1s for tick, 60s for screener, 1d for historical)

**Files:** New: `trading_agent/data_plane/` (5 files). Modified: `scripts/ibgw_relay.py` (add `/quote`, `/depth`, `/trades`, `/bars`, `/halt` endpoints). Migrate from: `trading_agent/fincept_connector.py` (broken in Docker, see Known Bugs).

**Tests:**
- Unit: each data source mock + verify contract (shape, freshness, fallback chain).
- Integration: TV + IBKR return matching last price for AAPL within $0.01; IBGW `/bars?interval=10s` returns ≥300 bars for liquid stock.
- Adversarial: TV session cookie expired → fallback to yfinance; IBGW relay down → fallback to yfinance; yfinance rate-limited → fallback to Finnhub; all down → alert Kay + paper-only mode.
- Live: Backtest on 30 days of historical 10s bars, verify First Pullback detection matches Ross's definitions.

**Citations:** `[C1.Ch6.P1]`, `[C1.Ch6.P2]`, `[C1.Ch6.P3]`, `[C1.Ch11]` (halts), `[INFERRED — Kay sign-off on data path priority]`.

---

### 2.2 Scanner plane

**Contract:** Event-driven candidate generation. Two modes:
- **Watch List Scanners (5 of 5 MVP)** — top-of-book leaderboards, refresh every 5 sec during market hours. Top 50 per scanner, sorted by composite score.
- **Alert Scanners (5 of ~19 MVP)** — event-driven push notifications, debounced per symbol. Each alert carries: symbol, scanner_type, score, price, RV, float, gap %, catalyst, timestamp, entry_window_until.

**MVP Top 10 (DTD-aligned):**

| # | Type | Scanner | DTD equivalent | Refresh | Course citation |
|---|------|---------|----------------|---------|-----------------|
| 1 | Watch | Top Gainers | "Top Gainers" | 5s | `[C1.Ch12]` |
| 2 | Watch | Top Relative Volume | "Top Relative Volume" | 5s | `[C1.Ch12]`, `[c4_part2]` |
| 3 | Watch | Small Cap High Day | "Small Cap High Momentum" | 5s | `[C1.Ch12]`, `[C4.Ch2.P1]` (small float = under 20M) |
| 4 | Watch | Pre-Market Gappers | "Pre-Market Gappers" | 60s (4-9 AM ET) | `[c3_part5_watchlist_rules.md]` (Ross's 6 AM pre-market scan) |
| 5 | Watch | First Pullback Setups | DTD has it, hidden in their scanner suite | 10s (event-driven from bars) | `[C1.Ch5.intraday_patterns]`, `[C1.Ch6.P1]` |
| 6 | Alert | Halt Status | "Halt" | event (IBGW field 293/294) | `[C1.Ch11]`, `[C2.Ch6.P3]` |
| 7 | Alert | News Catalyst | "News Catalysts" | event (Finnhub + TV news) | `[c3_part2_news_catalyst_rules.md]` |
| 8 | Alert | Squeeze Candidates | "Squeeze Candidates" | 60s (yfinance SI) | `[C1.Ch12]`, `[c3_part2]` (short squeeze) |
| 9 | Alert | Reversals | "Reversals" | 10s (intraday) | `[c5_intraday_patterns_rules.md]` |
| 10 | Alert | Bull Flag Breakouts | "Bull Flag Breakouts" | 10s (intraday) | `[c5_intraday_patterns_rules.md]` |

**Phase 2 (close the 14 after MVP):** Top Losers, Top Penny Stocks, Top Large Cap, Top Recent IPOs Moving, Penny Stocks, Earnings Movers, Low Float Top Gainers, High of Day (HOD) Momentum, VWAP Reclaim, Resistance Breakouts, Float Rotation, Multi-Day Consolidations, Large Cap Momentum, Running Up. Each gets its own subdoc + 5s refresh interval.

**Why top-10 first, not all-24:** YAGNI + Boil the Lake balance. 10 covers the core Ross strategy (gap + RV + catalyst + first pullback + halt awareness). The other 14 are derivable patterns. We earn them after MVP. `[INFERRED — Kay sign-off on top-10 selection]`.

**Owner:** Richard (Mavis agent) owns the scanner plane. Mavis (root) does not poll; Richard fires alerts.
- `trading_agent/scanner/watch_list.py` — 5 watch list scanners, refresh 5s
- `trading_agent/scanner/alert_scanners.py` — 5 alert scanners, event-driven
- `trading_agent/scanner/first_pullback.py` — pattern detector on 10s bars, scores 0-5
- `trading_agent/scanner/score.py` — composite scorer (Five Pillars + catalyst + RV)
- `trading_agent/scanner/dedup.py` — signal_dedup_open_positions skill integration
- `trading_agent/scanner/dtd_top10.json` — config: scanner definitions, thresholds, refresh intervals

**Files:** New: `trading_agent/scanner/` (6 files). Modified: `trading_agent/premarket_screener.py` (merge into watch list scanner #4), `trading_agent/intraday_scanner.py` (merge into first_pullback detector).

**Tests:**
- Unit: each scanner's filter returns correct candidates from mock data.
- Integration: 10 scanners fire simultaneously → no race on `signals_live.json`; dedup against `positions.json` works.
- Adversarial: stale TV data + fresh IBKR data → which wins? (Decision: IBKR for live, TV for screener.)
- Live: Paper-trade mode, observe 5 trading days, log which scanners fired and which signals became trades.

**Citations:** `[C1.Ch12]`, `[C1.Ch5]`, `[C1.Ch11]`, `[c3_part2_news_catalyst_rules.md]`, `[c3_part5_watchlist_rules.md]`, `[c4_part2_stock_types_rules.md]`, `[c5_intraday_patterns_rules.md]`, `[c5_reading_charts_rules.md]`, `[scanner_screener_rules.md]`, `[INFERRED — Kay sign-off on top-10 selection]`.

---

### 2.3 Decision plane

**Contract:** Event-driven, single-pass decision per signal. Bull → Bear → Research Manager → trade proposal OR skip. Zero LLM calls in monitoring loop.

**Pipeline:**
```
  Signal arrives (from scanner or TV webhook)
      ↓
  Check positions.json — already open? → log + skip
      ↓
  Bull Researcher — 1 LLM call (MiniMax M2.7 or M3, ~800 tokens)
      ↓
  Bear Researcher — 1 LLM call (~800 tokens)
      ↓
  Research Manager — 1 LLM call (~1,200 tokens) → BUY or SKIP
      ↓
  If BUY + conviction ≥ 7 → execute via Execution plane
  If BUY + conviction < 7 → queue for Kay's manual review
  If SKIP → log + move on
```

**Why this is event-driven, not polling:** v0.1 polled every 15 min via `scan-market` cron. That's batch mode — misses the burst. v1 fires on every scanner alert (debounced 60s per symbol). Same Bull/Bear structure as TradingAgents but compressed to 3 calls vs 8-12. `[INFERRED — Kay sign-off on conviction threshold]`.

**Conviction threshold:** Per `c15_trading_plan_rules.md`, Ross's "high-probability setup" requires: gap ≥10% + RV ≥5× + catalyst confirmed + float <20M + first pullback identified. Bull/Bear/Research Manager debate yields conviction 1-10. Auto-execute ≥7, queue for review 5-6, skip <5. `[C1.Ch15]`, `[INFERRED — Kay sign-off on threshold]`.

**Owner:** Bull/Bear are inline LLM calls orchestrated by the Decision plane runner.
- `trading_agent/decision/pipeline.py` — orchestrator (Bull → Bear → RM → conviction check)
- `trading_agent/decision/prompts.py` — prompt templates (extracted from `bull_bear_debate.py`)
- `trading_agent/decision/conviction.py` — score 1-10, decide auto vs queue vs skip
- `trading_agent/decision/cost_logger.py` — append every LLM call to `data/cost_log.csv`
- `trading_agent/decision/llm_resolver.py` — vault key first, config fallback, inline session last

**Files:** New: `trading_agent/decision/` (5 files). Migrate from: `trading_agent/bull_bear_debate.py`, `trading_agent/bull_bear_signal_handler.py`, `scripts/bull_bear_runner.py`, `scripts/scan_market_bull_bear.py` (all consolidated into `decision/pipeline.py`).

**Tests:**
- Unit: each prompt template renders correct with sample input.
- Integration: 10 mock signals → pipeline produces 10 verdicts in expected order; cost log accurate.
- Adversarial: LLM call fails (401, timeout) → fallback to next provider OR skip + alert; conviction = 0 from LLM (unparseable) → skip; multiple signals for same symbol within 60s → only first triggers.
- Live: 30-day backtest of Bull/Bear/RM on historical 10s bars, measure conviction vs realized P&L.

**Citations:** `[C1.Ch15]`, `[C1.Ch12]`, `[c3_part2_news_catalyst_rules.md]`, `[c5_intraday_patterns_rules.md]`, `[INFERRED — Kay sign-off on conviction threshold]`.

---

### 2.4 Execution plane

**Contract:** Deterministic position lifecycle. Zero LLM cost. State machine: `IDLE → ENTRY_PENDING → POSITION_OPEN → EXIT_PENDING → CLOSED → IDLE`. File-based shared state via `positions.json` with file locking.

**Entry (auto, conviction ≥ 7):**
1. Read `positions.json` — if max positions (1-3) reached → skip + log.
2. Read daily P&L from `data/daily_pnl.json` — if −10% of account → skip + alert.
3. Compute position size: `min(¼ × buying_power, 100 × price)` for alpha; scale per Course 2.
4. Submit market order via IBKR `placeOrder()` to `DU1234567` (paper) or live account.
5. Wait for fill confirmation (max 5s).
6. Compute ATR-based stop: `entry − max(2 × intraday_ATR, 0.10)`.
7. Compute target: `entry + 0.20` (Ross minimum, guarantees 2:1 R:R when stop ≥ $0.10).
8. Submit stop + target as attached orders (IBKR supports OCA group).
9. Write position to `positions.json` (atomic write with lock).
10. Telegram alert: `ENTRY: SYM @ $X | Target $X.20 | Stop $X.10 | Size 100 | R:R 2:1`.

**Exit (deterministic, 4 priority order):**
1. **Stop hit** → close immediately, log `STOP_HIT`.
2. **2-min rule** (price breaks 2-min low since entry) → close immediately, log `TWO_MIN_RULE`.
3. **Target hit** → close immediately, log `TARGET_HIT`.
4. **Market close** (21:00 Berlin / 4 PM ET) → close all positions, log `MARKET_CLOSE`.
5. **Daily loss limit** (−10%) → close all positions + halt trading for the day, log `DAILY_LOSS_HALT`.

**Monitoring loop:** Tick-level via IBKR consolidated tape WebSocket (when relay SSE/WS added) or 1-sec poll on `/quote` endpoint. Per `c5_intraday_patterns_rules.md`, the "Mark" requires sub-second response. 5-min polling is dead. `[C1.Ch6.P1]`, `[C1.Ch5]`.

**Position sizing — multi-position 1-3:** Alpha = max 1, beta = max 3, scaled by account size. Per `c15_trading_plan_rules.md`, "¼ size start" means first trade = ¼ of normal size, scale up on consecutive wins. `[C1.Ch15]`.

**Why file-based state, not a DB:** `positions.json` is the shared contract between Richard and Trader (and the dashboard). JSON is human-readable, diff-able, git-trackable. Use file locking (`fcntl.flock` on Linux, `msvcrt.locking` on Windows) for concurrent access. `[INFERRED — Kay sign-off]`.

**Owner:** Trader (Mavis agent) owns the Execution plane. Mavis (root) does not poll.
- `trading_agent/execution/position_manager.py` — entry/exit logic, file locking
- `trading_agent/execution/ibkr_orders.py` — IBKR `placeOrder`, `cancelOrder`, OCA groups
- `trading_agent/execution/stop_target.py` — ATR-based stop, target computation
- `trading_agent/execution/monitor_loop.py` — tick-level position monitor
- `trading_agent/execution/daily_pnl.py` — daily P&L tracking, 10% loss halt
- `trading_agent/execution/scale_in.py` — Course 2 ¼-size start, scale-in on confirmation

**Files:** New: `trading_agent/execution/` (6 files). Migrate from: `trading_agent/trader_agent.py` (consolidate + add tick monitoring), `trading_agent/live_event_loop.py` (split: data goes to data_plane, decision goes to decision, execution stays here).

**Tests:**
- Unit: each exit condition triggers correct action with mock prices.
- Integration: simulated fill → monitor loop sees price change → exits correctly. Race between two signals for same symbol → only one fills. Multiple positions open simultaneously → independent stops/targets.
- Adversarial: IBKR rejects order → alert + don't write to positions.json. Fill price differs from expected by >$0.10 → use actual fill price. Position in positions.json but no IBKR position (orphan) → reconcile or alert. Stop triggered but IBKR order fails → market sell as fallback.
- Live: Paper trade 5 days, verify all exits happen within 1s of condition met.

**Citations:** `[C1.Ch6]` (order types), `[C1.Ch11]` (halts), `[C1.Ch15]` (scaling), `[C2.Ch2]` (risk management), `[c5_intraday_patterns_rules.md]`, `[c15_trading_plan_rules.md]`, `[INFERRED — Kay sign-off on multi-position cap]`.

---

### 2.5 Dashboard plane

**Contract:** Read-only views + manual override. Flask app on `:5050` (PROD), `:5051` (DEV), `:5052` (UAT). Three primary views: Live, Watch List, History.

**Live view:**
- Open positions: symbol, entry, current, P&L, time held
- Today's closed trades: count, win rate, total P&L
- Account equity curve (intraday, refresh 30s)
- Live tape of scanner alerts (top 10 only, deduped)
- Manual kill switch: "Halt all trading for today"
- Manual override: "Close position SYM at market"

**Watch List view:**
- All 10 scanners, side-by-side
- Click symbol → opens TradingView chart (deep link)
- Color-coded rows: green = new alert <60s, yellow = active signal, gray = already in `positions.json`
- Auto-refresh 5s

**History view:**
- Closed trades: date, symbol, entry, exit, P&L, exit reason
- Daily P&L chart (calendar heatmap)
- Win rate by exit reason
- Reflections from `trading_memory.md` (append-only journal)

**Why Flask, not React:** Kay's not a frontend dev. Flask + vanilla JS + Chart.js is enough. Don't over-engineer. `[INFERRED — Kay sign-off]`.

**Owner:** Dashboard is owned by Hermes (Mavis) with input from Richard (watch list) and Trader (positions). No LLM calls in dashboard.
- `dashboard/app.py` — Flask app, routes
- `dashboard/templates/` — Jinja2 templates
- `dashboard/static/` — JS + CSS + Chart.js
- `dashboard/api/state.py` — `/api/state` JSON endpoint
- `dashboard/api/kill_switch.py` — manual halt + override endpoints
- `dashboard/api/tv_webhook.py` — `POST /webhook/tradingview` (kept from v0.1)

**Files:** Modified: `dashboard/app.py` (rewrite as proper view), `dashboard/templates/*` (new). New: `dashboard/api/*` (3 modules).

**Tests:**
- Unit: each route returns correct JSON.
- Integration: end-to-end browser test (Selenium if available, manual otherwise) — load `:5050`, verify watch list shows scanners, open position visible in live view.
- Adversarial: dashboard down but pipeline up → pipeline continues, alerts go to file fallback. Pipeline down but dashboard up → dashboard shows stale data + "last update" timestamp + warning.
- Live: visual review by Kay every Monday.

**Citations:** `[INFERRED — Kay sign-off]`.

---

### 2.6 Guardrails plane

**Contract:** Hard limits that cannot be overridden by any other plane. The only plane with veto power.

**Hard limits:**
- **Daily loss cap:** −10% of starting equity → close all positions + halt trading for the day. File: `data/guardrails/daily_pnl.json`. `[C2.Ch2]` (5 types of risk).
- **Max positions:** alpha = 1, beta = 3. Hard cap, not soft. `[C1.Ch15]`, `[INFERRED — Kay sign-off]`.
- **Per-trade risk:** max 1% of account on stop hit. ATR stop guarantees this when stop ≥ $0.10. `[C2.Ch2]`.
- **Halt awareness:** no entry into halted stock. Wait for resume or skip. `[C1.Ch11]`, `[C2.Ch6.P3]`.
- **SSR (Short Sale Restriction):** no shorting on SSR days. Day-only. `[C1.Ch11]`.
- **Wide-range bar:** if today's range > 2× ATR, skip — too volatile for our stops. `[C1.Ch5]`.
- **Large-cap drift:** if symbol > $20 OR market cap > $2B, skip — not Ross's zone. `[C1.Ch2.P1]`, `[C4.Ch2.P1]`.
- **Float check:** if float > 20M, skip — not small cap. `[C4.Ch2.P1]`.
- **End-of-day discipline:** close all positions at 21:00 Berlin (4 PM ET). No overnight holds in alpha. `[C1.Ch15]`.

**Soft limits (warnings, not blocks):**
- Win rate < 50% over 10 trades → reduce size by 50%.
- 3 consecutive losses → pause new entries for 30 min.
- LLM cost > $5/day → switch to local model fallback.
- Daily trades > 5 → require Kay's manual review per trade (was 1 in alpha).

**Why a separate plane:** The Execution plane should not be able to disable its own guardrails. The Guardrails plane has veto power over Entry. `[C2.Ch2]`, `[INFERRED — Kay sign-off]`.

**Owner:** Hermes (Mavis root) owns the Guardrails plane. Every other plane must check guardrails before action.
- `trading_agent/guardrails/limits.py` — hard + soft limits, configuration
- `trading_agent/guardrails/daily_pnl.py` — daily P&L tracker, 10% halt logic
- `trading_agent/guardrails/position_cap.py` — multi-position cap enforcement
- `trading_agent/guardrails/halt_check.py` — pre-entry halt + SSR + wide-range check
- `trading_agent/guardrails/eod.py` — 21:00 Berlin close-all

**Files:** New: `trading_agent/guardrails/` (5 files). Migrate from: stop/target logic in `trader_agent.py` (move to `execution/stop_target.py` but cap enforcement stays in guardrails).

**Tests:**
- Unit: each limit triggers correctly with mock state.
- Integration: simulate daily loss → halt triggers → next entry rejected. Simulate 3 positions open → 4th entry rejected.
- Adversarial: race between guardrail check and entry execution → atomic write to `positions.json` wins. Guardrail config corruption → fail safe (halt everything).
- Live: paper-trade through a -10% day, verify auto-halt fires.

**Citations:** `[C1.Ch2.P1]`, `[C1.Ch11]`, `[C1.Ch15]`, `[C2.Ch2]`, `[C2.Ch6.P3]`, `[C4.Ch2.P1]`, `[INFERRED — Kay sign-off on limit values]`.

---

## 3. Cross-cutting concerns

### 3.1 Timeframe — 10s primary, 1m fallback
Per `c5_intraday_patterns_rules.md`, the First Pullback pattern is most reliably identified on lower timeframes. 5-min bars miss the move. 10-second bars from IBKR `/bars?interval=10s&duration=1d` is the primary. 1-minute bars as fallback if 10s not subscribed. `[C1.Ch6.P1]`, `[INFERRED — Kay sign-off on subscription]`.

### 3.2 Multi-position — 1 (alpha) → 3 (beta) dynamic
Per `c15_trading_plan_rules.md`, "¼ size start" applies to both per-trade size and number of concurrent positions. Alpha = 1, prove profitability, then scale. Beta = 3 with per-trade size = 1% of account. Auto-scale based on rolling 10-trade win rate (≥60% → +1 position, ≤40% → −1 position). `[C1.Ch15]`, `[INFERRED — Kay sign-off]`.

### 3.3 Premarket — 4 AM ET = 10:00 Berlin
Per `c3_part5_watchlist_rules.md`, Ross's daily routine: 7 PM after-hours scan, 6 AM pre-market scan, 7 AM watchlist build. v0.1's 14:00 Berlin (= 8 AM ET) cron was too late for Ross's 6 AM scan. v1 cron: 4 AM ET (10:00 Berlin) for the pre-market gapper scan, 6:30 AM ET (12:30 Berlin) for the full watch list. `[C3.P5]`, `[INFERRED — Kay sign-off on timezone]`.

### 3.4 Auto-trade — yes, with phased guardrails
Per v0.1 + alpha results, paper trading has worked. v1: paper (1 month) → €500 live (1 month) → €2K live (3 months). Each phase requires ≥60% win rate over 20 trades. Auto-trade enabled in all phases. Kay reviews daily 21:00 Berlin P&L digest. Manual kill switch in dashboard. `[C1.Ch15]`, `[INFERRED — Kay sign-off on phase gates]`.

### 3.5 Daily P&L digest — 21:00 Berlin
End-of-day Telegram message (or file fallback) to Kay:
```
EOD 2026-07-20
  Trades: 3 (2W 1L)
  Net P&L: +$45 (+1.5%)
  Win rate (10d): 58%
  Open positions: 0
  Tomorrow's plan: continue beta phase
```

If Telegram is dead (per 2026-07-20 status), write to `data/daily_pnl/YYYY-MM-DD.md` for workspace handoff. `[INFERRED — Kay sign-off on format]`.

### 3.6 LLM access pattern
Three-tier fallback:
1. **Vault key** (`E:\Me\TradingAgent\vault/llm_api_key.enc`, DPAPI) — primary, called via subprocess to avoid leaking to chat.
2. **Environment variable** (`MINIMAX_API_KEY` in Portainer) — Docker fallback.
3. **Inline session** (Mavis current session) — last resort, when vault + env both fail.

`llm_call.py` reads `config.yaml` which has placeholder `sk-xxx` — that's a known broken path. Fix: `decision/llm_resolver.py` chains vault → env → inline. `[INFERRED — Kay sign-off on resolver order]`.

### 3.7 Telegram status (2026-07-20)
**Token 401 — DEAD.** Kay confirmed do not pursue. v1 has Telegram as a soft dependency, not hard. All alerts have file fallbacks. Future Telegram is a "store new token" project, not a fix. `[INFERRED — Kay sign-off]`.

### 3.8 Memory log
Append-only journal at `knowledge/memory/trade_journal.md`:
```
[2026-07-20 | PTLE | BUY | +4.13%]
DECISION: gap +20%, RV 7.7x, first pullback, conviction 8
ENTRY: $6.06 | EXIT: $6.31 | P&L: +$25
EXIT REASON: TARGET_HIT
REFLECTION: target hit cleanly. entry on pullback optimal. would trade same way.
```
1 LLM call per day for reflection, post-EOD. `[C1.Ch15]`, `[INFERRED — Kay sign-off on prompt]`.

### 3.9 Tool stack integration
- **Ponytail** (NEW code only, 54% LOC reduction) — applies to all 6 planes' new files. "Lazy senior dev" rules: YAGNI, reuse, stdlib, deletion over addition.
- **Headroom** (token efficiency, 60-95% reduction on JSON) — applies to scanner output, LLM prompts, daily P&L digest. Sandbox-tested 2026-07-20, works.
- **agency-agents** (specialists on demand) — spawn `engineering-multi-agent-systems-architect` for arch review, `trading-system-architect` for strategy review.
- **Gstack (Mavis port)** (`tools/gstack-mavis-port/plan-ceo-review.md` + `review.md`) — strategic plan review + pre-landing PR review.

### 3.10 Course citation invariant
**HARD RULE:** Every architectural decision cites `[C1.ChXX.PX]` or `[C2.ChXX.PX]` or is marked `[INFERRED — Kay sign-off]`. This applies to:
- All plane contracts
- All code comments on non-obvious logic
- All PRD/ADR files
- All commit messages touching architecture

Kay's role: review the `[INFERRED]` markers weekly, promote them to course citations where possible, sign off on the rest.

---

## 4. Build phases

### Phase 0 — Tool baseline (DONE 2026-07-20)
- [x] Headroom installed, sandbox-tested
- [x] Ponytail persona adopted (NEW code only)
- [x] agency-agents cloned
- [x] Gstack Mavis Code port (plan-ceo-review + review)
- [x] Gitea repos created
- [x] Telegram diagnosed dead (do not pursue)
- [x] Hermes 402 fix verified

### Phase 1 — DTD-replica architecture (Day 3, this doc)
- [x] ARCHITECTURE_v1.0.md drafted
- [ ] Apply `/plan-ceo-review` SCOPE EXPANSION mode (top-10 vs all-24, conviction threshold)
- [ ] Apply `/plan-ceo-review` HOLD SCOPE mode (architecture rigor, error/rescue map, security review)
- [ ] Verifier review via `verifier` agent
- [ ] Security architect review via `security-architect` agent
- [ ] Push to Gitea `trading/trading-agent` `dev` branch
- [ ] ARCHITECTURE_v1.0.md ratified by Kay

### Phase 2 — Data + Scanner MVP (Days 4-10)
- [ ] IBGW relay extensions: `/quote`, `/depth`, `/trades`, `/bars?interval=10s`, `/halt`
- [ ] `data_plane/` module (5 files)
- [ ] `scanner/` module — top 10 scanners (5 watch list + 5 alert)
- [ ] Unit + integration tests
- [ ] Paper mode, 5 trading days observation

### Phase 3 — Decision + Execution MVP (Days 11-20)
- [ ] `decision/pipeline.py` — Bull/Bear/RM with conviction check
- [ ] `execution/` module — entry, monitoring, exits, scale-in
- [ ] `guardrails/` module — hard + soft limits
- [ ] File locking for `positions.json`
- [ ] End-to-end paper trade test
- [ ] Verifier review of full execution path

### Phase 4 — Dashboard rewrite (Days 21-25)
- [ ] `dashboard/app.py` rewrite with 3 views (Live, Watch List, History)
- [ ] Manual kill switch + override
- [ ] Daily P&L digest generator
- [ ] End-to-end browser test

### Phase 5 — Paper month (Days 26-55, ~1 month)
- [ ] Run full pipeline, paper mode
- [ ] Daily review of P&L digest
- [ ] Weekly review of conviction accuracy
- [ ] Iterate on scanner thresholds

### Phase 6 — Live beta €500 (Days 56-85, ~1 month)
- [ ] Switch Execution plane to live account
- [ ] All guardrails active
- [ ] Daily P&L review with Kay
- [ ] Win rate ≥ 60% over 20 trades → advance

### Phase 7 — Live beta €2K (Days 86-175, ~3 months)
- [ ] Scale position size
- [ ] Multi-position 3 active
- [ ] Win rate ≥ 60% sustained → ready for autonomy

### Phase 8 — Close remaining 14 scanners (parallel with Phase 5+)
- [ ] Top Losers, Top Penny Stocks, Top Large Cap, etc.
- [ ] Each gets its own subdoc + integration test

### Phase 9 — Autonomy (Day 176+)
- [ ] Kay reviews weekly, not daily
- [ ] System self-corrects based on rolling metrics
- [ ] Reflections in `trading_memory.md` feed back into prompt tuning

---

## 5. Open questions for Kay

1. **TradingView tier:** Plus, Premium, or Ultimate? Determines whether 10s charts are in scope. If not Ultimate, primary timeframe is 1m from IBKR.
   - **Default if no answer:** Use 1m bars from IBKR, 10s overlay only if TV Ultimate is confirmed.
2. **IBKR market data subscriptions:** What is active on DU1234567? Determines whether Level 2 is real-time or delayed.
   - **Default if no answer:** Assume delayed, plan to subscribe if not.
3. **Conviction threshold (auto-execute):** Is ≥7 the right cut? Or should alpha use ≥8 (more conservative)?
   - **Default if no answer:** ≥7 auto, 5-6 queue, <5 skip.
4. **Multi-position cap:** Alpha=1, beta=3. Is the scaling rule (≥60% win rate over 10 trades) correct?
   - **Default if no answer:** Yes, scale ±1 position based on rolling 10-trade win rate.
5. **Phase gate criteria:** Paper → €500 → €2K. Is "20 trades at ≥60% win rate" the right gate? Or 10 trades? Or 1 month of trading?
   - **Default if no answer:** 20 trades at ≥60% win rate.
6. **Daily P&L digest format:** Telegram is dead. File-only handoff at `data/daily_pnl/YYYY-MM-DD.md`. Acceptable?
   - **Default if no answer:** Yes, file-only.
7. **Top-10 vs all-24 scanners:** Are the 10 selected (5 watch list + 5 alert) the right MVP? Or do you want to swap one?
   - **Default if no answer:** Yes, top-10 as listed.
8. **Telegram future:** Do you want to store a new token in the next 30 days? Or fully deprecate and use Discord/email/workspace handoffs?
   - **Default if no answer:** Fully deprecate, workspace handoffs only.

---

## 6. Risk register

| # | Risk | Severity | Mitigation | Owner |
|---|------|----------|------------|-------|
| 1 | LLM cost overrun | Medium | Daily cap $5, switch to local fallback, log every call | Decision plane |
| 2 | IBGW relay down during market | Critical | yfinance fallback + alert + paper-only mode | Data plane |
| 3 | TV session cookie expired | High | yfinance + Finnhub fallback for screener | Scanner plane |
| 4 | Daily loss > 10% (alpha exploit) | Critical | Hard halt in Guardrails plane, tested daily | Guardrails |
| 5 | Race on `positions.json` | High | File locking with `fcntl.flock` / `msvcrt.locking` | Execution |
| 6 | LLM produces invalid JSON | Medium | Parse with retry, fall back to "skip" verdict | Decision |
| 7 | Telegram dead (confirmed 2026-07-20) | Low | File fallbacks already in place | All planes |
| 8 | 10s bars not subscribed | Medium | 1m bars fallback (degraded but works) | Data plane |
| 9 | `vault/llm_api_key.enc` not present | Medium | env var → inline session fallback | Decision |
| 10 | False signal storm (many alerts, all false) | High | Conviction threshold + daily trade cap | Decision + Guardrails |

---

## 7. ADR log (architecture decisions)

- **ADR-001:** Supersede v0.1 architecture with this v1.0 DTD-replica. [INFERRED — Kay sign-off]
- **ADR-002:** Data path = IBKR consolidated tape primary, TradingView paid secondary, yfinance/Finnhub tertiary. [INFERRED — Kay sign-off]
- **ADR-003:** 10s bars primary, 1m fallback. [INFERRED — Kay sign-off on TV tier]
- **ADR-004:** Top 10 of 24 DTD scanners for MVP. [INFERRED — Kay sign-off]
- **ADR-005:** Multi-position 1-3 dynamic, scale on rolling 10-trade win rate. [C1.Ch15]
- **ADR-006:** Auto-trade with phased guardrails (paper → €500 → €2K). [C1.Ch15]
- **ADR-007:** 4 AM ET premarket cron. [C3.P5]
- **ADR-008:** Daily 21:00 Berlin P&L digest (file fallback if Telegram dead). [INFERRED — Kay sign-off]
- **ADR-009:** Telegram is dead, do not pursue. Use file fallbacks only. [INFERRED — Kay sign-off 2026-07-20]
- **ADR-010:** Course citation invariant on every architectural decision. [INFERRED — Kay sign-off]

---

## 8. What's next (Day 3 work)

1. **Day 3a** (this doc) — drafted.
2. **Day 3b** — apply `/plan-ceo-review` SCOPE EXPANSION mode on this doc. Specifically challenge:
   - Top-10 vs all-24 (5 watch + 5 alert).
   - Conviction threshold ≥7.
   - 10s vs 1m bars.
   - Multi-position 1-3.
3. **Day 3c** — apply `/plan-ceo-review` HOLD SCOPE mode for rigor on the 6 planes (error/rescue map, security, observability).
4. **Day 3d** — `verifier` agent runs `/review` skill on this doc + draft code structure.
5. **Day 3e** — `security-architect` agent reviews threat model.
6. **Day 3f** — push to Gitea `trading/trading-agent` `dev` branch via `gitea-agent`.
7. **Day 3g** — write `tools/DAY-3-END-OF-DAY-2026-07-20.md` handoff.
8. **Day 4+** — Phase 2: Data + Scanner MVP.

---

## 9. Document meta

- **Version:** 1.0 (DRAFT)
- **Date:** 2026-07-20
- **Author:** Hermes (Mavis Code)
- **Reviewers needed:** Kay (final sign-off), verifier (rigor), security-architect (threat model)
- **Supersedes:** v0.1 (alpha single-position), momentum-decision-cockpit (8-cap read-only)
- **Next revision:** After Day 3 SCOPE EXPANSION + HOLD SCOPE reviews
- **Source of truth:** `docs/ARCHITECTURE_v1.0.md` in `C:\Users\Kay\repos\trading-agent\`

---

**END OF DOCUMENT.** When ratified by Kay, this becomes the contract for all future work on the trading-agent project. Any deviation requires a new ADR with course citation or `[INFERRED — Kay sign-off]`.
