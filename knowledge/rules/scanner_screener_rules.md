# Scanner & Screener Rules — Ross Cameron Five Pillars
## Compiled from: Ch12 (Scanning 101), Ch13, Ch14, Ch15, Ch3 Part 5, Ch4 Part 1-2
## Status: Ch12 NOT YET TRANSCRIBED — audio exists, pending transcription
## Last Updated: 2026-06-26

---

## PART 1: THE THREE SCANNER TYPES

Ross uses exactly **3 scanner types** — nothing else:
1. **Small Cap High Day** — main trigger (stocks UP >20% today)
2. **Top Gainer** — gap-up identification
3. **Continuation** — stocks in established uptrends (not the fresh spike)

Ross quote: *"9 out of 10 times, the stock is hitting one of my scanners"*

### Scanner Column Priority (in order of importance)
1. **Name/Symbol** — what's running
2. **Price** — is it in the $2-$20 sweet spot?
3. **Volume** — total volume today (need >500K minimum)
4. **Float** — <20M acceptable, <5M ideal
5. **Relative Volume (RV)** — >5× minimum, >10× ideal

---

## PART 2: FIVE PILLARS OF STOCK SELECTION

Every stock must pass ALL FIVE pillars before considering a trade:

### P1 — Relative Volume (RV)
- **Minimum:** 5× average daily volume
- **Ideal:** 10× or higher
- **Why:** High RV = big supply/demand imbalance = explosive moves
- **How to get:** yfinance `volume` vs 30-day avg volume

### P2 — Catalyst (News)
- **Requirement:** Fresh breaking news (earnings, FDA, PR, contract, etc.)
- **Finnhub API:** `/news` endpoint with `minTime` = today 00:00 UTC
- **Filter:** only stocks with news in last 2 hours
- **In hot market:** no-news but obvious stock = acceptable as 2nd priority
- **News types that work:** earnings beats, FDA approvals, big contracts, sector news, M&A rumors

### P3 — Price Level
- **Acceptable range:** $2.00 - $20.00
- **Sweet spot:** $5.00 - $10.00 (best % gain potential)
- **Below $2:** penny stock risk, avoid unless exceptional
- **Above $20:** harder to move, less % gain, institutional names

### P4 — Float (Shares Available to Trade)
- **Acceptable:** < 20 million shares
- **Ideal:** < 5 million shares (micro/nano float)
- **Nano:** < 1M shares — explosive but highest risk
- **Micro:** 1-5M shares — Ross's preferred range
- **Low:** 5-20M shares — good
- **Medium:** 20-100M shares — harder to move
- **Large:** 100M+ shares — institutional, avoid (opposite of what we need)
- **Rule:** smaller float = easier to squeeze, bigger % moves

### P5 — Chart Pattern (Intraday)
- **First candle making new high** = entry confirmation
- **Bull flag / squeeze-up** = strong continuation pattern
- **Flat top breakout** = resistance break = momentum continuation
- **ABCD pattern** = measured move, valid but more advanced
- **Avoid:** stocks already extended with no pullback (chasing)
- **Avoid:** stocks with topping tails already on intraday

---

## PART 3: SWEET SPOT FILTER (Honey Crisp)

Within the Five Pillars, Ross specifically targets the "sweet spot":

| Filter | Minimum | IDEAL (Sweet Spot) |
|--------|---------|-------------------|
| Price | $2-$20 | **$5-$10** |
| Float | <20M | **<5M** |
| RV | >5× | **>10×** |
| % Up Today | >10% | **>50%** |
| Catalyst | Some news | **Fresh breaking news NOW** |

**Example of a LOW probability setup:**
- 19.99M float, $19.99 price, 5× RV, 10% up, news = technically passes all 5 pillars → but barely

**Example of HIGH probability setup:**
- 1M float, $7 price, 60% up today, 10× RV, breaking news right now = perfect

---

## PART 4: WATCHLIST BUILDING PROCESS (Ross's Daily Routine)

### 7-8 PM Berlin — After Hours Scan (Nightly)
- Pull up phone, check **after hours top gainers scanner**
- Look for: big moves after hours — flag these as tomorrow's candidates
- Warning: *"if you have a really big move after hours, by pre-market you've kind of missed the party"* (fade the gap)
- These become candidates to watch next morning

### 6:00 AM Berlin — Pre-Market Scan (MOST IMPORTANT)
- **Only thing Ross looks at at 6am**
- Top gainers / top losers pre-market
- Stocks that ran after hours often fade at open → wait for confirmation
- Apply filters immediately (see below)

### 7:00 AM Berlin — Build the Watchlist
- Narrow to **5-10 stocks max**
- Focus on quality over quantity
- These are your candidates for the trading day

### 15:30 Berlin (Market Open) — First Pullback Scanning
- Scan for stocks from watchlist pulling back to support
- Watch for first candle making new high = entry signal
- Richard should run scan every 15 minutes during 15:30-16:00 (highest volume window)

---

## PART 5: SCANNER FILTER PARAMETERS (Richard's Config)

### Pre-Market Scan Parameters
```
price_min: 2.00
price_max: 20.00
rv_min: 5.0
float_max: 20_000_000
volume_min: 500_000
pct_up_min: 10.0
catalyst_required: true  # unless market is hot
```

### Intraday (First Pullback) Scan Parameters
```
price_min: 2.00
price_max: 20.00
rv_min: 5.0
float_max: 20_000_000
volume_min: 500_000
in_watchlist: true  # only scan watchlist stocks
pattern: pullback   # looking for pullback from HOD
timeframe: 1m       # confirm on 1m chart
```

### Sweet Spot Overrides (apply after base filters)
```
# Auto-boost these in scoring:
if price >= 5.00 and price <= 10.00: score += 1
if float <= 5_000_000: score += 1
if rv >= 10.0: score += 1
if pct_up >= 50.0: score += 1
if catalyst_age_minutes <= 60: score += 2
```

---

## PART 6: WHAT TO SKIP (Red Flags)

### Skip if:
- [ ] Float > 20M shares (too hard to move)
- [ ] Price > $20 (institutional name, limited % gain)
- [ ] Price < $2 (penny stock, SEC regulations, manipulation risk)
- [ ] RV < 5× (no momentum, low supply/demand imbalance)
- [ ] Stock already up 100%+ today without pullback (chasing)
- [ ] Stock has been hitting scanner repeatedly for 30+ min with no resolution (tired move)
- [ ] No news catalyst AND market is cold
- [ ] Easy to Borrow (ETB) — indicates institutional/shortable, less squeeze potential
- [ ] Wide bid-ask spread (> $0.10)
- [ ] Level 2 shows stacked sellers, not buyers

---

## PART 7: SCANNER AUDIO ALERT DISCIPLINE

- **Turn audio ON** for: nano float (<1M), micro float (1-5M), <$20 price, >5× RV
- **Turn audio OFF** for: medium/large float, high-priced stocks
- **Rapid "ding ding ding"** = stock repeatedly hitting scanner = ACT NOW
- **Single alert** = check but don't激动, might be noise
- **Chatter/scanner going off constantly** on one stock = institutional involvement, be careful

---

## PART 8: POSITION TRACKING (Richard → Trader Handoff)

### Richard's Output (watchlist CSV)
```
ticker, price, float, rv, pct_up, catalyst, score, time
AAPL,   6.50,  1.2M,  8.5, 45%,  "FDA approval 09:32",  8,  09:45
```

### Before Alerting, Richard checks:
1. Read `positions.json`
2. If ticker is already in position with status=open → DO NOT alert again
3. If ticker is already in position with status=exited → OK to re-alert
4. Log alert timestamp to avoid duplicate alerts within 5 min

### Scanner → Alert Decision Tree
```
Is ticker in positions.json with status=open?
  → YES: Skip, already in position
  → NO: Does it pass all 5 pillars?
         → YES: Send alert to Kay's Trading Team
         → NO: Skip
```

---

## PART 9: ROSS'S COMPLETE SCANNER SET (from Ch12)

### The 8 Scanners Ross Uses
| # | Scanner Name | Type | Frequency | Purpose |
|---|-------------|------|-----------|---------|
| 1 | **Small Cap High Day** | Alert | Live | Stocks UP >20%, Market Cap <$50M — primary trigger |
| 2 | **Top Gapper** | List | Static @ 9:30am | Preserves gap picture at open |
| 3 | **Top Gainer** | List | Live 4am-8pm | Stocks up % vs prev close — main daily list |
| 4 | **Low Float Top Gainer** | List | Live | Top gainers with float <5M — Ross's sweet spot |
| 5 | **Recent Reverse Split** | List | Weekly | Watch for catalyst-triggered moves on reverse splits |
| 6 | **Recent IPO** | List | Weekly | Fresh stocks with no daily resistance = big upside potential |
| 7 | **Continuation** | List | Weekly | Stocks with biggest 2-week range — weekly temperature check |
| 8 | **After Hours Top Gainer** | List | EOD | Yesterday's strongest AH movers for pre-market prep |

### Alert vs List Scanners
- **Alert scanner**: fires when a stock FIRST meets criteria (ding = stock newly qualifying)
- **List scanner**: always-on view of all stocks currently meeting criteria
- **Audio alerts**: ON for nano/micro float (<5M), squeeze alerts; OFF for medium/large float

### Small Cap High Day Settings (from Ch12)
```
Minimum % gain today: 20%+
Market cap: ≤ $50M
Float: strictest filter (no exceptions on this scan)
```
→ This is Ross's PRIMARY scanner. Every stock on it needs Five Pillars check.

### Top Gapper vs Top Gainer Difference
- **Top Gapper**: Stops at 9:30am, preserves a "snapshot" of gap at open
- **Top Gainer**: Runs live 4am-8pm, keeps updating
- Use Top Gapper to compare: "what was the market picture at 9:30 vs now?"

### Ross's Daily Watchlist Workflow (Ch12)
1. **6:30-6:45 AM** — Sit down, start building watchlist
2. **Top Gainers List** — Go through top 3-5 gainers one by one
   - Sort by % gain
   - Check: familiar with company? News timestamp? Price? Volume? Float? RV?
   - Filter to quality (Ch12 says: Ross casts wider net initially, strict on float)
3. **Low Float Top Gainer** — narrow to float <5M stocks only
4. **Add to watchlist** — usually only 2-3 stocks max
5. **8:00 AM** — Highest probability news release time
   - "Top and bottom of the hour" = 7:00, 7:30, 8:00, 8:30, 9:00
   - Ross watches scanner closely at these times
6. **High of Day Momentum Scanner** — stocks making NEW highs of day
7. **Running Up Scanner** — stocks MOVING without needing new high of day
8. **Alert fires** → run full due diligence (P1-P5, level 2, tape)

### Scanner Column Priorities (in order)
1. Name/Symbol
2. % Gain (sort by this first)
3. Price ($2-$20 sweet spot)
4. Volume (total volume today, need >500K minimum)
5. Float (<5M ideal)
6. Relative Volume
7. News timestamp (flame = fresh, yellow = older)
8. Short Interest (additional column)

### Five Pillars Flexibility Spectrum (Ch12 — new nuance)
| Pillar | Flexibility | Ross's Position |
|--------|------------|-----------------|
| Price | HIGH | $1.80 is fine if it'll cross $2 soon |
| % Gain | MEDIUM | 8% is OK if momentum is fast |
| Relative Volume | MEDIUM | 3× is OK if volume is building |
| News | MEDIUM | No-news momentum stock can work |
| **Float** | **LOW — strictest** | >5M float is a no-go on alert scanners |

### Screener vs Scanner Distinction (Ch12)
- **Screener (Finviz, ToS)**: static list, not real-time, runs on demand
- **Scanner (Warrior)**: dynamic, real-time, updates continuously
- Ross: "a screener is a picture of the past; a scanner is seeing the market right now"

### Key Ch12 Quotes for Richard's Pipeline
- *"I'm not trying to find stocks that are about to move — I'm trying to find stocks that have already started moving"*
- *"When a stock is up 20% on high RV, that tells me there's real conviction"*
- *"I prefer Day 1 of breaking news"*
- *"8:00 AM is the peak news release time — watch the scanners at top/bottom of hours"*

---

## PART 10: CURRENT GAPS — PENDING TRANSCRIPTION

### Ch13 — Psychology of Trading (PENDING)
- Audio: `knowledge/raw/1. Day Trading The Basics/Chapter13/Chapter 13 The Psychology of Trading.mp4`
- Expected content: hot buttons, emotional management, fear/greed cycles, trading journal
- Relevant for: Trader agent mindset + position sizing psychology

### Ch14 — Preparing to Start Trading (PENDING)
- Audio: `knowledge/raw/1. Day Trading The Basics/Chapter14/Chapter 14 Preparing to Start Trading.mp4`
- Expected content: broker selection, account setup, platform configuration, paper trading
- Relevant for: dashboard/Trader setup checklist

---

## Ch12-15 Status Summary
| Chapter | Content | Status | Transcript |
|---------|---------|--------|------------|
| Ch12 | Scanning 101 | ✅ COMPLETE | 290 lines |
| Ch13 | Psychology of Trading | ❌ NOT transcribed | Pending |
| Ch14 | Preparing to Start Trading | ❌ NOT transcribed | Pending |
| Ch15 | Trading Plan | ✅ COMPLETE | 2,132 lines |
| Ch3 P5 | Building Watchlist | ✅ Complete | 574 lines |
| Ch4 P1 | Daily Chart Patterns | ✅ Complete | 772 lines |
| Ch4 P2 | Daily Stock Types | ✅ Complete | 657 lines |

---

*This file is the authoritative scanner/screener reference for Richard's pipeline.*
*Last updated: 2026-06-26 after Ch12 transcription.*
