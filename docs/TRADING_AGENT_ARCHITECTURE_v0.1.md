# Kay's Trading Agent — Architecture Design v0.1
**Status:** First draft for discussion
**Date:** 2026-06-26
**Based on:** TradingAgents (TauricResearch), ai-hedge-fund (virattt), Ross Cameron Warrior Trading methodology

---

## Overview

The system is a multi-agent day trading setup for US equities, paper trading during alpha phase. 
It operates in two distinct modes:

- **Signal Generation Mode** (Richard): Premarket watchlist + intraday scanner for entry setups
- **Position Management Mode** (Trader): Always-on monitoring of open positions for exit decisions

Agents communicate via shared state files — no message bus, no LangGraph, no external orchestration. 
Keep it simple, keep it cheap.

---

## Shared State

### `positions.json` — Single source of truth for open positions

```json
{
  "positions": [
    {
      "symbol": "PTLE",
      "action": "LONG",
      "entry_price": 6.06,
      "entry_time": "2026-06-25T16:37:00+02:00",
      "quantity": 100,
      "stop": 5.96,
      "target": 6.26,
      "status": "OPEN",
      "notes": "First pullback, gap +20.2%, RV 7.7x"
    }
  ],
  "history": [
    {
      "symbol": "PTLE",
      "action": "LONG",
      "entry_price": 6.06,
      "exit_price": 6.31,
      "exit_reason": "TARGET_HIT",
      "pnl": 25.00,
      "pnl_pct": 4.13,
      "closed_at": "2026-06-25T16:55:00+02:00"
    }
  ]
}
```

### `signals.json` — Active signals from Richard's scanner

```json
{
  "signals": [
    {
      "symbol": "MIMI",
      "score": 4.2,
      "gap_pct": 19.6,
      "rel_vol": 8.2,
      "price": 4.85,
      "source": "premarket",
      "found_at": "2026-06-25T14:00:00+02:00",
      "debated": false,
      "decision": null
    }
  ]
}
```

### `debate_history.json` — Bull/Bear debate log

```json
{
  "debates": [
    {
      "symbol": "PTLE",
      "round": 1,
      "bull_argument": "...",
      "bear_argument": "...",
      "research_manager_verdict": "BUY",
      "decided_at": "2026-06-25T16:37:00+02:00"
    }
  ]
}
```

---

## Agent 1 — Richard (Researcher)

**Role:** Find setups. Owns the signal generation pipeline.

**Trigger:** 
- Cron: 14:00 Berlin Mon–Fri (premarket watchlist)
- Cron: 15:30–21:00 every 15 min during market (intraday scan)

**Responsibilities:**
1. Build premarket watchlist from TradingView Premium API
2. Run Five Pillars scoring on intraday candidates
3. Check Finnhub/Alpha Vantage for news catalyst scoring
4. Apply Course 2 risk filters (halt, wide range, large cap)
5. Write qualifying signals to `signals.json`
6. Check `positions.json` before alerting — if symbol is already open, mark `in_position: true` but don't fire a new alert

**Tools:**
- TradingView Premium API (gap, RV, price filters)
- Finnhub news API (catalyst scoring)
- Alpha Vantage (fallback news)
- yfinance (price, float, volume)

**Output:** `signals.json` updated with new candidates

**Constraints:**
- Max 1 open position at a time (alpha rule)
- Only flag stocks not already in `positions.json`
- Respect Finnhub rate limits (60 req/min), AV quota guard (25/day)

---

## Agent 2 — Bull Researcher

**Role:** Build the case FOR the trade. Stress-test the bullish thesis.

**Trigger:** Fired when Richard writes a new signal to `signals.json` AND the symbol is not already in a position.

**Single LLM call per signal.** Not polling. Event-driven.

**Prompt (core):**
```
You are a Bull Analyst for [SYMBOL]. A scanner has identified this as a potential 
First Pullback setup:

Signal data:
- Gap: [GAP_PCT]%
- Relative Volume: [RV]x
- Price: $[PRICE]
- Catalyst score: [P1-P4 breakdown]
- Float: [FLOAT]M

Your job: Build the strongest evidence-based case FOR entering this trade.
Focus on:
- Why the gap is sustainable (catalyst, news, sector momentum)
- Why the pullback is a re-entry opportunity, not a reversal
- Volume profile supporting continuation
- Technical setup (Five Pillars alignment)
- Any bullish context from recent news

Be specific. Use the data provided. Do not be vague.
```

**Output:** Writes `bull_argument` to `debate_history.json`, advances state.

---

## Agent 3 — Bear Researcher

**Role:** Poke holes in the setup. What could go wrong?

**Trigger:** After Bull finishes (same signal).

**Single LLM call per signal.**

**Prompt (core):**
```
You are a Bear Analyst for [SYMBOL]. A bullish case has been made:

Bull's argument:
[BULL_ARGUMENT]

Your job: Stress-test this setup ruthlessly. Find the reasons NOT to enter.
Focus on:
- Why the gap could fail (weak catalyst, no news support)
- Why the pullback could become a reversal
- Risk of halt, wide-range expansion, large-cap drift
- Volume red flags
- Any bearish signals in the data
- Whether the risk/reward actually justifies entry

Engage directly with the bull's points. Counter them specifically.
```

**Output:** Writes `bear_argument` to `debate_history.json`, advances state.

---

## Agent 4 — Research Manager (Synthesis)

**Role:** Read both sides, make a verdict. Should we trade this or not?

**Trigger:** After Bear finishes.

**Single LLM call per signal.**

**Prompt (core):**
```
Debate on [SYMBOL]:

Bull's argument:
[BULL_ARGUMENT]

Bear's argument:
[BEAR_ARGUMENT]

Signal data:
- Gap: [GAP_PCT]%, Price: $[PRICE], RV: [RV]x, Float: [FLOAT]M
- Catalyst: [P1-P4 scoring]
- Entry target: $[ENTRY_PRICE], Stop: $[STOP], Target: $[TARGET]
- Risk/Reward ratio: [RR]

Based on the debate, make a clear call:

RECOMMENDATION: BUY / SKIP

If BUY: State the entry price, stop, and position size (100 shares alpha rule).
If SKIP: State the primary reason (failed catalyst, poor R/R, risk flags).

Be decisive. Do not hedge.
```

**Output:** Writes `research_manager_verdict` to `debate_history.json`. 
If BUY: creates a trade proposal in `debate_history.json`.

**Note:** This is the last LLM call before entry. The verdict is binary.

---

## Agent 5 — Trader (Position Manager)

**Role:** Owns open positions. Monitors exits. Fires automatically.

**Trigger:** Always-on loop, polling every 30 seconds during market hours.

**Responsibilities:**
1. Read `positions.json` on every cycle
2. Pull live price for each open position
3. Check exit conditions in priority order:
   - **Stop hit** → close immediately, log as `STOP_HIT`
   - **2-min rule** → close immediately, log as `TWO_MIN_RULE`
   - **Target hit** → close immediately, log as `TARGET_HIT`
   - **Market close** (21:00 Berlin / 4 PM ET) → close all positions
4. Calculate unrealized P&L in real time
5. Send Telegram notification after each exit
6. Never open a new position while one is already open (alpha rule)

**Exit Logic (deterministic, zero LLM cost):**

```
IF current_price <= entry_price - 0.10:      # Stop hit
    close_position("STOP_HIT")
    send_telegram(f"STOP HIT on {symbol} @ {price}, loss ${loss}")

ELIF price_broke_2min_low_since_entry:       # 2-min rule
    close_position("TWO_MIN_RULE")
    send_telegram(f"2-MIN RULE on {symbol} @ {price}")

ELIF current_price >= entry_price + 0.20:   # Target hit
    close_position("TARGET_HIT")
    send_telegram(f"TARGET HIT on {symbol} @ {price}, gain ${gain}")

ELIF berlin_time >= "21:00":                  # Market close
    close_all_positions("MARKET_CLOSE")
    send_telegram("Market close — all positions closed")
```

**Tools:**
- yfinance (live price, 30-sec polling)
- Telegram API (exit notifications)
- `positions.json` (read/write)

**Constraints:**
- Zero LLM calls during monitoring — pure deterministic logic
- Log every price check to `trader_log.json` for backtesting later
- If yfinance fails, retry 3x with 5-sec delay, then alert Kay

**Position state machine:**

```
IDLE → (Research Manager says BUY) → POSITION_OPEN
POSITION_OPEN → (exit condition met) → TRADE_CLOSED
TRADE_CLOSED → (Market next day, 14:00) → IDLE
```

---

## Agent 6 — Memory (Learning System)

**Role:** Append-only log of all trades. Generates reflections after each trading day.

**Trigger:** After market close (21:00 Berlin), or when all positions are flat.

**Responsibilities:**
1. For each closed trade in `positions.json.history`:
   - Fetch realized return from yfinance
   - Generate reflection: what worked, what didn't
   - Append to `trading_memory.md`
2. On next signal for the same symbol, inject past context into Bull/Bear prompt

**Memory log format (append-only, per TradingAgents pattern):**

```
[2026-06-25 | PTLE | BUY | pending]
DECISION:
**Rating**: BUY
**Entry**: $6.06 | **Exit**: $6.31 | **P&L**: +$25.00 (+4.13%)
**Exit reason**: TARGET_HIT
**Reflection**: (filled after realized return confirmed)
```

After reflection:
```
[2026-06-26 | PTLE | BUY | +4.13% | +2.1% alpha | 1d]
DECISION:
**Rating**: BUY
...
REFLECTION:
Target hit cleanly at +$0.25. 2:1 ratio achieved. News catalyst (PTLE earnings 
beat) confirmed the morning gap. The pullback entry at $6.06 was optimal — 
stock was already pulling back to the 9:30 EMA when the first 5-min candle 
confirmed. Lesson: wait for the first candle making new highs after pullback 
rather than entering on the pullback itself. Would enter same way next time.
```

**Reflection prompt (lightweight, one LLM call per day):**
```
A trade was executed on [DATE] for [SYMBOL]:
- Entry: $[ENTRY], Exit: $[EXIT], P&L: $[P&L] ([P&L_PCT]%)
- Exit reason: [REASON]
- Signal quality: gap [GAP_PCT]%, RV [RV]x, catalyst score [P4_SCORE]
- Course 2 rules applied: [RISK_FLAGS]

Generate a 2-3 sentence reflection: what did the trade teach us? 
What would we do differently? Be specific and actionable.
```

---

## Data Flow Diagram

```
14:00 BERLIN ─────────────────────────────────────────────────────
│
├── Richard (premarket)
│   ├── TV Premium API → watchlist candidates
│   ├── Finnhub/AV news → catalyst scoring
│   ├── Ch2 risk rules → filter
│   └── Write to signals.json
│
15:30 BERLIN ─────────────────────────────────────────────────────
│
├── Richard (intraday scanner, every 15 min)
│   ├── TV API → live candidates
│   ├── Finnhub/AV → catalyst
│   ├── Check positions.json → skip if already open
│   └── New signal? → Fire Bull/Bear/Research Manager pipeline
│
├── Bull Researcher (per signal, 1 LLM call)
│   └── Write bull_argument → debate_history.json
│
├── Bear Researcher (per signal, 1 LLM call)
│   └── Write bear_argument → debate_history.json
│
├── Research Manager (per signal, 1 LLM call)
│   └── BUY verdict? → Open position → positions.json
│       └── Telegram alert: "ENTRY: {symbol} @ ${price}"
│
├── Trader (always-on, 30-sec polling)
│   ├── Read positions.json
│   ├── yfinance live price
│   ├── Check exit conditions (deterministic)
│   └── Exit fired? → Update positions.json → Telegram alert
│
21:00 BERLIN ─────────────────────────────────────────────────────
│
├── Trader: close all positions (MARKET_CLOSE)
├── Memory: fetch realized returns → generate reflections → append to trading_memory.md
└── Reset for next day
```

---

## Telegram Communication

All messages go to **Kay's Trading Team group** (ID: -5581171035).

| Event | Message |
|---|---|
| Entry (after Research Manager BUY) | `📋 ENTRY: {symbol} @ ${price}\nGap: {gap_pct}%\nTarget: ${target} (+$0.20)\nStop: ${stop} (-$0.10)\nQty: 100 shares | Paper` |
| Target Hit | `🎯 TARGET HIT: {symbol} @ ${price}\n+${gain} (+{pct}%)\nHeld {duration}` |
| Stop Hit | `🛑 STOP HIT: {symbol} @ ${price}\n-${loss} (-{pct}%)\nHeld {duration}` |
| 2-Min Rule | `⚡ 2-MIN RULE: {symbol} @ ${price}\n-${loss} (-{pct}%)` |
| Market Close | `🔔 MARKET CLOSE: All positions closed\nDaily P&L: ${pnl}` |

---

## Token Cost Analysis

| Agent | Trigger | LLM calls | Est. tokens/call | Cost/trade |
|---|---|---|---|---|
| Bull Researcher | Per new signal | 1 | 800 | ~$0.0008 |
| Bear Researcher | Per new signal | 1 | 800 | ~$0.0008 |
| Research Manager | Per new signal | 1 | 1,200 | ~$0.0012 |
| Reflection | Per closed trade | 1 | 600 | ~$0.0006 |
| **Total per trade** | | **3 LLM calls** | **~3,200 tokens** | **~$0.003/trade** |

Monthly cost estimate (5 signals/day × 20 trading days = 100 signals):
- 100 signals → ~50 result in a trade (filter rate)
- ~50 trades × $0.003 = **~$0.15/month**

Trader polling: **zero LLM cost** — deterministic code only.

This is the key efficiency gain over TradingAgents. We spend LLM tokens only on the entry decision. Everything else is code.

---

## Implementation Priority

### Phase 1 — Core loop (do this first)
1. `positions.json` schema
2. Trader agent (30-sec polling, deterministic exits)
3. Telegram notifications (entry/exit alerts)
4. Richard + positions.json integration (skip stocks already open)

### Phase 2 — Entry quality
5. Bull Researcher (1 LLM call per signal)
6. Bear Researcher (1 LLM call per signal)
7. Research Manager verdict (1 LLM call per signal)
8. `debate_history.json` log

### Phase 3 — Learning
9. Memory log (`trading_memory.md`)
10. Per-day reflection (1 LLM call after close)
11. Past context injection into Bull/Bear prompts

### Phase 4 — Polish
12. Backtest runner using `trader_log.json` (price check history)
13. Dashboard integration (show open positions, P&L)
14. Scale-in rules (from Course 2: ¼ size start)
15. Multi-position alpha (when alpha is proven)

---

## Open Questions for Discussion

1. **Re-alert rules:** When Richard finds PTLE while Trader already has PTLE open — what does Trader do?
   - Option A: No action (hold, just log it)
   - Option B: Scale in (add 50 shares on pullback)
   - Option C: Partial exit (sell half to lock profit, leave rest)
   - Option D: Full exit + reverse (close long, open short — rare)

2. **2-min rule detection:** How do we detect "price broke the 2-min low since entry"?
   - Store entry candle's 2-min low at entry time
   - On each polling cycle, compare current 2-min low vs entry 2-min low
   - Or: pull last 2 candles from yfinance, check if either made a new low below entry 2-min low

3. **Scale-in rules:** Course 2 says start at ¼ size. Does that mean:
   - Entry at 25 shares → scale to 100 if trade works?
   - Or just entry at 100 shares for alpha (already agreed)?
   - Scale in only on high-confidence signals (score ≥ 4.5)?

4. **Position limit:** Alpha rule is 1 open position. Should this be enforced by:
   - Richard (don't generate new signals while position is open)?
   - Trader (reject entry requests while position is open)?
   - Both?
