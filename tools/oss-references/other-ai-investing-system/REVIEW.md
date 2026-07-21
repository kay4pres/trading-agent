# other-ai-investing-system — REVIEW

**Reviewed:** 2026-07-21 (Day 4)
**Source:** `E:\Me\TradingAgent\tools\oss-references\other-ai-investing-system\`
**Vendor:** Lewis Jackson / 01 Accelerator — `jackson-video-resources/skills` on GitHub
**License:** Mixed (skill code MIT-style, framework attributions to Roan @RohOnChain, Karpathy autoresearch pattern, Lewis Jackson refactor)
**Verdict:** ADOPT-3, FORK-3, SKIP-7, WATCH-4 — high-quality, complementary, NOT a replacement

---

## TL;DR

This is a **"House-vs-Gambler" trading system**: the strategy is a plug-in, the system
validates it → sizes it → approves/blocks it → executes it → watches and learns. The
house (system) has veto power. The gambler (strategy) only proposes. This framing
is the opposite of ours: we built scanner-as-strategy + thin wrapper, theirs is
strategy-as-plug-in + system-as-authority.

The system is **broker-agnostic** (Alpaca, ccxt, ib_async, paper), **Python-only**,
**paper-first with hard gates** (ALLOW_TRADING=1 env + typed human confirmation per
order), and **self-learning via a monthly closed cadence** (one variable at a time,
keep-or-revert gate against a benchmark).

It is **NOT** a Day Trade Dash replica, not Ross-Cameron style, not multi-position
day trading, not 10s bars, not a market scanner. It is closer to a quant research
+ portfolio management system, retrofitted to a CLI agent.

**For our project:** it's a **complement, not a replacement**. We keep our 6-plane
arch (data/scanner/decision/execution/dashboard/guardrails) and our DTD-replica
identity. We add 3 small modules (validation, learning, safety-gate wrapper) that
upgrade our Execution plane from advisory to blocking and add a closed learning
loop that we currently lack.

---

## What the system is — the 5 stages

From the README + the one-shot onboarding prompt + the 5b/5a "Edge Machine":

```
FOUNDATIONS · TradingView MCP + Alpha Vantage MCP + mcp-builder + claude-api
1 · RESEARCH & VALIDATION (is the edge real?)
    strategy-audit · pbo-deflated-sharpe · backtesting-frameworks · backtest
    alpha-combine · regime · pine-developer / pine-debugger / pine-backtester
2 · RISK ENGINE (the authority)
    risk-manager · capital-allocator (Kelly) · news-guard (NFP/FOMC/CPI blackout)
3 · EXECUTION (the safety gate)
    execution-safety (4-step pipeline: mode → risk limits → typed confirm → audit)
4 · MONITOR & REVIEW + LEARNING LOOP
    tear-sheet (QuantStats) · trade-journal · trading-loop (closed cadence)
    autoresearch (plan → act → measure → keep-winners)
```

The pipeline is: **validate edge first → size with Kelly → gate with risk
manager → block with execution-safety → log with trade-journal → improve with
trading-loop.** Live is OFF by default; paper is the path.

---

## Cross-reference with our `ARCHITECTURE_v1.0.md` [C-1]

| Our plane        | Their equivalent             | Verdict |
|------------------|------------------------------|---------|
| data/            | MCPs (TV, Alpha Vantage)     | SKIP — we have IBKR + Fincept + locally-built data plane |
| scanner/         | (none — they have no scanner) | KEEP — our 25 DTD scanners are unique value |
| decision/        | strategy-audit + alpha-combine + trading-loop | FORK — port the *pattern* (audit before deploy, closed learning loop) |
| execution/       | execution-safety             | ADOPT — drop-in wrapper, harden our IBGW client |
| dashboard/       | tear-sheet (QuantStats)      | FORK — add one-shot post-mortem per cycle |
| guardrails/      | news-guard + risk-manager + regime | FORK — port pieces, keep our conviction gate |

### Gaps in our arch that this system covers

1. **No validation pipeline before live** — we have backtests but no PBO/deflated
   Sharpe/deflated overfitting check, no walk-forward, no regime check.
2. **No closed learning loop** — we have a `trade_journal.md` plan but no
   keep/revert gate, no "one variable at a time" rule, no benchmark tracking.
3. **News blackout is narrow** — we have Finnhub headlines but no scheduled
   macro event calendar (NFP/FOMC/CPI).
4. **Execution is advisory** — our position-size logic suggests, doesn't block.
5. **No R-multiple journaling** — we have positions.json but no per-trade
   `r_multiple`, `rule_compliance`, `session`, `setup` fields.
6. **No tear-sheet** — no QuantStats HTML report per cycle.

### Gaps in this system that our arch covers

1. No scanners (DTD 25) — they have no market scan capability
2. No 10s bars — they use daily yfinance or TV charts
3. No multi-position 1-3 — single-strategy + portfolio of strategies
4. No pattern detectors (Bull Flag / First Pullback / VWAP) — these live in
   *user-supplied strategy*, not as ready-made skills
5. No 4 AM ET premarket — no premarket scanner cron
6. No float / relative volume / gap filters — these are scanner-side
7. No sound alerts / halt / SSR detection — not in their skill set
8. No IBKR-specific extensions (10s bars `/bars?interval=10s`)
9. No auto-trade with conviction threshold — paper-first with manual confirm
10. No 21:00 Berlin P&L digest — they have tear-sheet but as a one-off, not daily

---

## Adopt / Fork / Skip breakdown

### ADOPT (drop-in, low risk, high value)

#### 1. `execution-safety` — execution gate wrapper [A-1]

**File:** `3b.trading-suite/skills/execution-safety/execution_safety.py` (5.1 KB)
**Tests:** 9 passing, stdlib only
**Why:** Their 4-step pipeline (`mode check → hard risk limits → typed
confirmation → audit log`) is the exact gap in our execution plane. They
use a two-lock pattern: `ALLOW_TRADING=1` in the shell (human action) AND
`live=True` on the call (caller action) AND exact typed token (e.g.
`CONFIRM SELL 100 SPY @ market`). Miss any → block or paper.

**How to adopt:** port `execution_safety.py` to `E:\Me\TradingAgent\trading_agent\execution_safety\`.
Wrap our `ibgw.place_order()` call with `guard_order(order, profile)`. The
broker-agnostic design means we can have `IBKRLiveAdapter` (real), `PaperAdapter`
(simulated), `StubLiveAdapter` (test). All 9 tests should pass locally.

**Code-quality check:** the `RiskProfile` dataclass has a clean fail-closed
allowlist, the `check_risk_limits()` function returns ALL breaches (not just
the first), the audit log writes one JSON line per decision with `audit_id`
(uuid), `ts` (epoch), `decision`, `reason`, and the order context. This is
production-grade.

#### 2. `news-guard` — economic event blackout [A-2]

**File:** `3b.trading-suite/skills/news-guard/news_guard.py` (4.2 KB) + `events.csv` fallback
**Tests:** 9 passing
**Why:** They fetch free Forex Factory weekly JSON (no API key), fall back to
bundled CSV when offline. Maps instrument to currencies/regions, blacks out
only HIGH-impact events inside configurable window (default 30 min before,
15 min after). Returns `{decision, reason, next_event, minutes_until, source}`.
Optional Twilio SMS on block (env-var creds, no file storage).

**How to adopt:** port `news_guard.py` + `events.csv` to
`E:\Me\TradingAgent\trading_agent\data_plane\news_guard\`. Wire it into our
premarket pipeline (4 AM ET cron) and into `trader_agent.open_position()` as
a pre-trade gate. The currency-mapping table covers FX + indices + crypto
out of the box.

**Mapping to our arch v1.0 §5 Guardrails plane:** exact match. We had "news
catalyst via Finnhub" but no scheduled macro event detection. This plugs
that gap.

#### 3. `trade-journal` schema — R-multiple, rule_compliance, session, setup [A-3]

**File:** `3b.trading-suite/skills/trade-journal/SKILL.md` (schema spec only,
no code in this skill — `trading-loop` consumes it)
**Why:** Our `positions.json` tracks entry/exit/qty/symbol but lacks the
fields needed to drive the learning loop. We need: `r_multiple` (reward /
planned risk), `rule_compliance` (true/false), `session` (e.g. "premarket",
"open", "midday", "close"), `setup` (e.g. "First Pullback", "Bull Flag"),
`emotional_state`, `entry_reason`, `exit_reason`.

**How to adopt:** extend `positions.json` schema (additive, non-breaking) so
each closed position record carries these fields. On exit, compute
`r_multiple = (exit - entry) / (entry - stop)` for longs (sign-flipped for
shorts) and persist.

**Critical invariant:** schema must match exactly what `trading-loop` expects
(see `engine.py:96-115 _r_multiple()`). Use their column names verbatim.

### FORK (port the pattern, rewrite in our stack)

#### 4. `trading-loop` — closed cadence self-learning [F-1]

**File:** `3b.trading-suite/skills/trading-loop/trading_loop/engine.py` (19.7 KB)
**Tests:** 5 passing, numpy + stdlib only
**Why:** This is **the missing piece** in our arch. We have a
`knowledge/memory/trade_journal.md` plan but no mechanism. The engine runs
a closed 6-stage loop:

1. Hypothesis (falsifiable edge + primary metric)
2. Paper-trade window (CSV trade log, ~1 month / 20+ trades)
3. Measure (win rate, expectancy R, profit factor, max consecutive losses, Sharpe)
4. Loss autopsy (5 categories: psychology, timing, setup quality, risk management, market context)
5. Adjust — ONE variable only (hard rule, enforced in code)
6. Gate (keep/revert) against the previous window's benchmark

The gate logic is the value: `if metric improved → keep, else → revert +
lock variable so loop never tries it again`. Reverted locks are persisted,
so the loop converges.

**How to fork:** port the engine to `E:\Me\TradingAgent\trading_agent\learning\`.
Replace the CSV ingest with a JSONL appender (our `positions.json` extended
with the journal schema). Keep the same gate semantics. Wire it to a
monthly cron (1st of month, 22:00 Berlin after 21:00 P&L digest).

**Why fork not adopt:** they read CSV, we want JSONL. They use numpy arrays,
we can use the same. Their hypothesis is text — ours can pull from
`knowledge/rules/` automatically.

#### 5. `risk-manager` — pre-trade gate that BLOCKS [F-2]

**File:** `3b.trading-suite/skills/risk-manager/SKILL.md` (6 modes, all SKILL.md no code)
**Why:** Our `trader_agent.open_position()` has a conviction check but the
risk logic is advisory (logs warnings, doesn't block). Their `risk-manager`
has 6 modes: pre-trade gate, rule builder, circuit breaker, portfolio
audit, position sizing, daily dashboard. Mode #1 (pre-trade gate) is the
relevant one.

**How to fork:** implement Mode #1 + Mode #3 (circuit breaker) in Python as
part of `trading_agent/risk/`. Wire the 7 BLOCK conditions (daily loss, max
positions, same-asset, position size, stale signal, news blackout, R:R) into
`open_position()` so they hard-fail, not warn. The `execution-safety`
adoption (item 1) is the seam where this plugs in.

**Why fork not adopt:** they are SKILL.md only — the actual logic must be
re-implemented. We can borrow the 7-condition list verbatim and the
`RiskProfile` dataclass.

#### 6. `regime` — Markov regime detection [F-3]

**File:** `3b.trading-suite/skills/regime/scripts/markov_regime.py` (refactored
by Lewis from Roan @RohOnChain's framework)
**Why:** They compute a 3-state Markov (Bull/Bear/Sideways) with transition
matrix, persistence diagonal, stationary distribution, n-step forecast, and
walk-forward Sharpe. JSON contract: `signal = bull_prob − bear_prob` in
`[-1, 1]`, magnitude = conviction.

**How to fork:** port the script to `E:\Me\TradingAgent\trading_agent\data_plane\regime\`.
Run on SPY (market proxy) daily at 9:30 ET open. Wire as a hard filter on
our scanners: "Don't take first-pullback long if regime signal < 0". This
becomes a new rule in our `knowledge/rules/c1_chXX_px.md` files.

**Why fork not adopt:** the script uses `--ticker BTC-USD` (yfinance) and
`--csv` (user-supplied). We want to call it programmatically with our
already-fetched data. We can wrap it in a small Python module that
injects our `data_plane/quotes.py` data instead.

### WATCH (lower priority, evaluate later)

#### 7. `tear-sheet` (QuantStats) [W-1]
One-shot post-mortem per cycle. We don't have a performance report yet. After
30+ paper trades, run this on the `trade-journal` data and we get CAGR,
Sharpe, max drawdown, win rate. Defer until Phase 2 has data.

#### 8. `alpha-combine` (signal combination) [W-2]
11-step institutional alpha combination. Could power our "conviction score"
combining 5-pillars into a single signal. But we don't have 5+ signal
families yet — our conviction is still 1-strategy × 5-pillars. Revisit
when we have 3+ independent alpha sources.

#### 9. `strategy-audit` (6-test stress audit) [W-3]
Six tests: walk-forward, Monte Carlo, sensitivity, slippage, drawdown. We
have basic backtests. Add this when we want to validate a new filter
variant before deploying. Pre-deploy gate, not continuous.

#### 10. Edge Machine (`5a`/`5b`) [W-4]
Slot-machine UI for generating random edge hypotheses. Fun idea generator
but not a serious tool. Could become a "Discovery Friday" routine — pull
the lever, backtest the hypothesis. Low priority.

### SKIP (not aligned with our project)

- **TradingView MCP / Alpha Vantage MCP** — we have IBKR + Fincept + locally-built data plane
- **Pine trio** (pine-developer, pine-debugger, pine-backtester) — we're Python
- **`claude-api`** — we use MiniMax / Mavis
- **`mcp-builder`** — we have our own agent framework
- **Onboarding prompts (1, 3a, 3c, 4)** — not for our use case (we're not a Claude Code user)
- **Risk manager Modes #2, #4, #5, #6** — covered by our existing backtest engine
- **Capital allocator Modes #1-#4, #6** — multi-strategy portfolio mgmt, we run single-strategy
- **Workbook PDF (`2.workbook.pdf`)** — not reviewed, not needed
- **All on-camera demo files** — not relevant

---

## What this means for our `ARCHITECTURE_v1.0.md` patch [C-2]

**Recommended arch patch (low-risk additive):**

```
NEW: validation_plane/  (between research and decision)
    strategy_audit.py     (6-test stress audit, port)
    pbo_deflated_sharpe.py (overfitting check, port)
    regime.py             (Markov detection, port)
    validator.py          (orchestrator: run all 3 before allowing paper trading)

NEW: learning_plane/  (after dashboard)
    trade_journal.py      (JSONL appender, R-multiple calc)
    trading_loop.py       (closed cadence engine, port engine.py)
    cycle_state.json      (persisted state: benchmark, reverted_locks, cycles)

REWRITTEN: execution_plane/ (harden existing)
    guard.py              (port execution_safety.py)
    risk_profile.py       (port RiskProfile dataclass)
    live_adapter_ibkr.py  (real IBGW adapter behind the gate)
    paper_adapter.py      (simulated)
    test_guard.py         (port 9 tests)

REWRITTEN: guardrails_plane/news_guard.py
    (port news_guard.py + events.csv)
```

**Total new code:** ~35 KB Python (engine.py 19.7 + execution_safety.py 5.1 +
news_guard.py 4.2 + schema/copy). All stdlib + numpy. Zero new dependencies.
**Migration cost:** low — additive only, no breaking changes to data_plane,
scanner_plane, dashboard_plane, or existing risk/conviction logic.

---

## Risk / sanity check

- **License:** MIT-style for skill code. Author attributions required
  (Roan @RohOnChain for regime/alpha-combine, Karpathy for autoresearch
  pattern, Lewis Jackson for the refactor). Include attributions in
  `trading_agent/learning/__init__.py` and `trading_agent/execution/__init__.py`.
- **No network deps** in their core skills (stdlib + numpy + optional yfinance).
- **No credentials in code** — env vars only (Twilio in news-guard).
- **Tests ship with the skill** — execution_safety (9), trading-loop (5),
  news-guard (9), alpha-combine, pbo-deflated-sharpe, tear-sheet. We can
  run them as-is before porting to verify behavior.

---

## Action items for Kay

1. [ ] **Sign off on ADOPT-3** (execution-safety, news-guard, trade-journal schema)
2. [ ] **Sign off on FORK-3** (trading-loop, risk-manager, regime) — all port to our stack
3. [ ] **Confirm arch v1.0 patch** — 3 new modules, 2 rewrites, ~35 KB total
4. [ ] **Defer WATCH-4** (tear-sheet, alpha-combine, strategy-audit, edge-machine) until Phase 2 has data
5. [ ] **Author attribution in `__init__.py`** for any ported code

---

## Course citations

- `[C-1]` Cross-reference table — based on `E:\Me\TradingAgent\docs\ARCHITECTURE_v1.0.md` §2-7 (6 planes)
- `[C-2]` Arch patch — based on `E:\Me\TradingAgent\docs\ARCHITECTURE_v1.0.md` §8 (open questions) + §10 (course citations)
- `[A-1]` execution-safety adoption rationale — based on their `SKILL.md` lines 1-50 + `execution_safety.py` lines 1-200
- `[A-2]` news-guard adoption — based on their `SKILL.md` lines 1-80 + `news_guard.py` (Forex Factory JSON, instrument mapping table)
- `[A-3]` trade-journal schema — based on their `SKILL.md` Mode #1 fields list + `trading-loop/engine.py:96-115 _r_multiple()`
- `[F-1]` trading-loop fork — based on their `SKILL.md` §"6-stage loop" + `engine.py:600-650 run_cycle()` (gate logic)
- `[F-2]` risk-manager fork — based on their `SKILL.md` Mode #1 (7 BLOCK conditions) + `RiskProfile` dataclass
- `[F-3]` regime fork — based on their `SKILL.md` §"Composition" patterns (a) and (b) + `markov_regime.py` JSON contract

[INFERRED — Kay sign-off required on items 1-3]
