# Scanner & Screener Rules — Course 1 (Chapters 12–15)

> Consolidated from Warrior Trading Day Trading The Basics, Chapters 12–15.
> Last updated: 2026-06-24

---

## Core Philosophy

> *"We are hunters of volatility, and managers of risk."*
> — Ross

**Scanners find volatility. You manage the risk.**

Don't use social media to find stocks — it is inconsistent and unreliable.
Don't pay $2,000/month for Bloomberg. Use scanners + free tools.

---

## Chapter 12: Scanning 101 — Key Rules

### The Scanning Framework

1. **Pre-Market Scan** (before 9:30 ET)
   - Find gap-up stocks
   - Filter by Five Pillars
   - Confirm with news catalyst
   - Build ranked watchlist

2. **Intraday Scan** (every 15 min during market hours)
   - Monitor watchlist stocks
   - Look for First Pullback entries
   - Track Level 2 for order flow confirmation

3. **Post-Market Review**
   - Log what worked / what didn't
   - Update tomorrow's watchlist

### Scanner Filters (from Ross's approach)

**Pre-Market (Gap-Up Scan):**
- Price: $2–$20
- Gap Up: ≥10% from yesterday's close
- Relative Volume: ≥2x average (ideally 5x+)
- News Catalyst: Must have fresh news
- Float: < 20M shares (if available)
- Market Cap: $50M–$2B (small/mid cap focus)

**Intraday (First Pullback Scan):**
- Already on today's gap-up watchlist
- Price within 2% of EMA 9
- RSI: 50–70 (momentum alive, not overheated)
- Volume Ratio: ≥2x average
- First candle making new highs after pullback = BUY signal

### Scanner Sources

| Source | Use | Cost |
|--------|-----|------|
| TradingView Premium | Primary — 50+ custom filters | Subscription |
| Finviz | Free screener backup | Free |
| yfinance | Free data for all stocks | Free |
| Alpha Vantage | Float, fundamentals | Free tier |
| Finnhub | News, sentiment | Free tier |

---

## Chapter 13: Psychology of Trading — Scanner Discipline

### Mental Rules for Using Scanners

1. **Don't chase.** If a stock already ran 20%+ from your scanner alert, skip it.
2. **One setup at a time.** Don't scan for 10 things. Stick to the Five Pillars.
3. **Trust the scanner, but verify.** Scanner says buy → check Level 2 → check news.
4. **Log everything.** Track what the scanner found vs. what actually worked.
5. **No emotion.** A scanner signal is just data. Your rules decide if you trade.

### Common Psychology Traps with Scanners

- **Over-scanning**: Seeing too many setups, taking too many trades → spread focus thin
- **Revenge trading**: Scanner finds a loser stock, you buy it again immediately
- **FOMO**: Stock flew past your buy point while you hesitated → don't chase
- **Analysis paralysis**: Too many indicators → simplify

---

## Chapter 14: Preparing to Start Trading — Review of the System

### What You've Learned

1. **Stock Selection**: Five Pillars filter
2. **Fundamental Analysis**: Reading charts, support/resistance
3. **Technical Analysis**: Candlesticks, patterns, EMA, RSI
4. **Platform Skills**: Level 1/Level 2 data, order types, hotkeys
5. **Stock Halts**: Know when a halt kills your position
6. **Psychology**: Discipline and emotional control
7. **Scanning**: Finding setups in real time

### The ONE Strategy (from Ch14)

You leave this course with **ONE strategy** to implement in the simulator:
> **First Pullback** — Gap up + catalyst + pullback + first candle making new highs

This is what the scanner looks for. This is what you practice.

---

## Chapter 15: Trading Plan & Day Trading Strategy — Entry System

### Ross's 5-Step Entry System

1. **Find stock via scanner** — momentum / gap-up scanners
2. **Check catalyst** — news confirmed
3. **Check DAILY chart → then INTRADAY chart** — multi-timeframe validation
4. **Check Level 2** — order book, bid/ask, size
5. **Execute first pullback** — gap up + pullback + first candle making new highs

### 7-Phase Scaling Plan (Alpha → Beta → Live)

**Alpha Phase** (current — paper trading):
- Trade 1 stock/day max
- 100 shares per trade
- Paper/simulator only
- Goal: prove the strategy works 10+ times

**Beta Phase**:
- Scale to $1,000/day target
- Increase share count
- Add 1 strategy from Course 2

**Live Trading**:
- Real money with proven track record
- Full position sizing

### First Pullback Entry Checklist

- [ ] Stock gapped up ≥10% from yesterday
- [ ] Fresh news catalyst confirmed
- [ ] Daily chart: uptrend confirmed
- [ ] Price pulled back to EMA 9 area
- [ ] Level 2 shows buying pressure (bid size > ask size)
- [ ] RSI: 50–70 (not overheated)
- [ ] Volume: above average (≥2x)
- [ ] First candle makes new highs after pullback → BUY
- [ ] Target: +$0.20/share
- [ ] Stop: $0.10–0.15/share
- [ ] Minimum Risk/Reward: 2:1

---

## Current Scanner Implementation Summary

### Daily/Pre-Market Scanner (`watchlist_ingestion.py` + `finviz_screener.py`)

| Filter | Threshold | Source |
|--------|-----------|--------|
| Price | $2–$20 | yfinance/Finviz |
| Gap Up | ≥10% | yfinance |
| Relative Volume | ≥5x avg | yfinance |
| News Catalyst | Fresh news today | Finnhub |
| Float | < 20M shares | Alpha Vantage |

### Intraday Scanner (`intraday_scanner.py`) — Five Pillars Scoring

| Pillar | Check | Threshold | Points |
|--------|-------|-----------|--------|
| P1 — Price | Stock in range | $2–$50 | 1 |
| P2 — Gap Up | Already confirmed gap-up | ≥5% (intraday) | 1 |
| P3 — Volume | Relative volume | ≥2x avg | 1 |
| P4 — Momentum | RSI in sweet spot | 50–70 | 1 |
| P5 — Pullback | Near EMA 9 support | ≤2% from EMA | 1 |

**Score ≥ 4 = Strong candidate**
**Score ≥ 3 = Actionable**
**Pattern: FIRST_PULLBACK** (pullback + first candle making new highs)

### Watchlist (`intraday_scanner.py`)

```
SOFI, AMD, GME, RIVN, PLTR, NVDA, TSLA, NIO, SNAP, ROKU, COIN, MSTR, SMCI, DXYN
```

---

## Backtest Results (SOFI, Dec 2025–Jun 2026) ⚠️

**File:** `data/SOFI_backtest.json`

| Metric | Value |
|--------|-------|
| Initial Capital | $10,000 |
| Final Equity | $9,873 (-1.27%) |
| Total Trades | **1** (in 6 months!) |
| Score Distribution | 61× score-1, 23× score-2, 7× score-3, 2× score-4, 0× score-5 |
| Avg Score | 1.46/5 |

**The one trade:** BUY SOFI @ $18.22 (54 shares) → SELL @ $15.87 = **-$126.90 (-12.9%)**

**Root cause:** `backtest_engine.py` requires score = 5/5 to trigger trades. P2 (Gap Up ≥5%) is too strict — SOFI regularly gaps 3-4% in this period. The intraday scanner found **92 signals in 5 days**, but the backtest traded once.

**Action required:**
- [ ] Lower trade trigger from 5/5 → 4/5 (score ≥ 4 = actionable per rules)
- [ ] Loosen P2 threshold: 5% → 3% for intraday validation
- [ ] Run backtest on AMD, GME, RIVN, PLTR (not just SOFI)

---

## TODO — Scanner Improvements

- [ ] Richard's premarket workflow: pull TradingView export → ingest → analyze → save watchlist
- [ ] Alpha Vantage integration for float data in watchlist
- [ ] Finnhub integration for news catalysts
- [ ] Finviz: automate daily scrape and merge with yfinance
- [ ] TradingView scanner CSV ingestion pipeline
- [ ] Expand watchlist beyond current 14 stocks (add more gap-up candidates)
- [ ] Backtest on multiple stocks (not just SOFI) to validate Five Pillars
