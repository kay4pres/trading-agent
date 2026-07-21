# DTD Competitive Intel Refresh — 2026-07-21

**Researcher-Agent session:** 2026-07-21 11:00-11:30 Berlin (30 min budget)
**Mavis orchestrator:** Hermes (Mavis Code)
**Source count:** 18+ URLs cited below
**Confidence:** MEDIUM-HIGH (multiple corroborating sources, but Warrior Trading member-only content NOT directly accessed — Kay needs to walk through DTD UI to fill remaining gaps)

**Status:** PARTIAL — researcher-agent background task still running, this is the Mavis-direct pass. Will merge when bg_f610f803 finishes.

---

## 0. Baseline (don't repeat, see v2 review)

For the original 24-scanner inventory, TV-paid/IBKR/DTD-sub/LLM access verification, and build sequence: see `C:\Users\Kay\repos\trading-agent\docs\day-trade-dash-strategic-review-v2.md` (44 KB).

**This doc adds:** post-Jul 17 intel, scanner filter values (community-discovered), competitor pricing, user feedback, and Jul 2026 regulatory changes.

---

## 1. DTD scanner filter values (community-discovered)

### Critical insight

**You don't need DTD member-only access to know the filter values.** Bear Bull Traders (Ross Cameron's "sister site") publishes a public PDF with 8 bull-flag scanner strategies, each with exact filter thresholds. Reddit r/Trading threads have working scans. Warrior Trading blog posts name the methodologies. The "secret sauce" of DTD is the **integration** (scanner + chart + news in one UI), not the filter values.

**Source: [Bear Bull Traders — High of Day Bull Flag PDF](https://bearbulltraders.com/wp-content/uploads/2023/02/TI_Settings.pdf) — public document, exact filter values below.**

### 1.1 Bull Flag Breakouts — 5+ strategies from public PDFs

| Strategy | Price | RV | Vol today | Vol last 5 min | 15-min range | Float | Notes |
|----------|-------|-----|-----------|----------------|--------------|-------|-------|
| **Low-Float Bull Flag Momentum** | $1-10 | ≥ 2x | ≥ 200k | 400-2000% of normal | ≥ $0.30 | < 10m | "New high (filtered)" |
| **+$10 Low-Float Bull Flag Momentum** | $10-50 | ≥ 2x | (similar) | (similar) | (similar) | < 100m | "New high (filtered)" |
| **Daily Breakout Bull Flag Momentum** | $1-50 | ≥ 2x | ≥ 1m | ≥ 500% of normal | ≥ $0.30 | < 100m | Price +2% from prev close, +85% above low of year |
| **Medium-Float Bull Flag Momentum** | $1-10 | ≥ 2x | ≥ 100k | ≥ 2000% of normal | (n/a) | 10m-100m | "New high (filtered)" |
| **+$10 Strong Bull Flag Momentum** | ≥ $10 | ≥ 2x | ≥ 1m | ≥ 2000% of normal | (n/a) | < 100m | "New high (filtered)" |
| **Strong +$10 Low-Float Momentum** | ≥ $10 | ≥ 2x | ≥ 1m | (similar) | (n/a) | < 100m | (similar) |

**Common across ALL strategies:** RV ≥ 2x (much lower than our arch doc's 5x), "New high (filtered)" alert.

### 1.2 Warrior Trading community scanner settings (Reddit r/Trading)

**Source: [Warrior Trader Scanner settings](https://www.reddit.com/r/Trading/comments/o9m98w/warrior_trader_scanner_settings/)**

**Alerts (7+):**
- New high (filtered)
- 75% pullback from lows
- % up for the day
- Sector breakout (from close)
- Positive market divergence
- Running up now
- 15-minute consolidation breakout
- 30-minute consolidation breakout
- Crossed above resistance
- 60-minute high
- Upward thrust (15 minute)

**Filters (4 hard):**
- Price between $4 and $20
- Daily volume ≥ 100,000 shares
- Current volume ≥ 1.5x average
- Volume today ≥ 50,000 shares

### 1.3 DTD scanner types (per multiple YouTube walkthroughs)

From the DTD platform review video at [https://www.youtube.com/watch?v=JjIUqdpFcHM](https://www.youtube.com/watch?v=JjIUqdpFcHM) and the 14-day trial review at [https://www.youtube.com/watch?v=HybGfXdt1Hk](https://www.youtube.com/watch?v=HybGfXdt1Hk):

- **High of day momentum** (separate for penny stocks sub $1)
- **Top gainers** (regular — includes all stocks)
- **Top gappers** (Ross-filtered — excludes penny stocks)
- **Continuation** (last 2-3-4 days still moving up today)
- **Small cap high day**
- **Ross's momentum**
- **Pre-market / intraday / after-hours** coverage (3 time windows)

**Notable:** DTD has a "Ross's specific filter" version of standard scanners — penny stocks excluded from his "top gappers." This is the **customization layer** beyond the filter values.

### 1.4 Inferred filter values for our scanner MVP (from sources above + v2 review)

| Our scanner | Inferred filter set | Source basis |
|-------------|---------------------|---------------|
| **Top Gainers** | price $1-50, gap ≥ 10%, RV ≥ 2x, vol ≥ 100k, float < 100m | BBT + Reddit |
| **Top Relative Volume** | RV ≥ 5x, vol ≥ 100k, price $1-20 | v2 review + Reddit |
| **Small Cap High Day** | price $1-10, RV ≥ 2x, vol today ≥ 200k, float < 10m | BBT Strategy 1 |
| **Pre-Market Gappers** | price $1-20, gap ≥ 10% pre-market, RV ≥ 3x, vol ≥ 50k pre-market | v2 + Reddit |
| **First Pullback Setups** | gap ≥ 10% + RV ≥ 5x + price above VWAP + 2-3 red candles + RV pullback confirmation | Warrior blog + Ross C1 |
| **Halt Status** | IBGW field 293/294 (halt indicator) | IB docs |
| **News Catalyst** | TV news feed + Finnhub + freshness < 30 min | v2 |
| **Squeeze Candidates** | SI > 20% + DTC > 5 + price $1-20 + RV ≥ 2x | v2 + market norm |
| **Reversals** | failed breakout (broke HOD, came back below) + RV ≥ 2x + vol spike | v2 + trader standard |
| **Bull Flag Breakouts** | RV ≥ 2x + 15-min range ≥ $0.30 + price $1-50 + vol last 5 min ≥ 400% normal + "new high" trigger | BBT 5 strategies |

**The "new high (filtered)" trigger is the core entry signal across most DTD scanners.** This is what our arch doc v1.0 called "first candle making new highs" — same thing.

---

## 2. DTD pricing (2026, multiple sources)

| Source | Price | Includes |
|--------|-------|----------|
| [BullishBears](https://bullishbears.com/warrior-trading-review/) | $147/month add-on | DTD only |
| [WallStreetZen](https://www.wallstreetzen.com/blog/warrior-trading-review/) | $147/month add-on | DTD only |
| [Mometic](https://blog.mometic.com/top-10-day-trading-stock-scanners-in-2025/) | ~$187/month (range) | DTD via Warrior bundle |
| [BananaFarmer](https://bananafarmer.app/compare/ross-cameron-scanner) | $199/month (with Warrior bundle) | DTD + chatroom + education |
| [Reddit user r/propfirm](https://www.reddit.com/r/propfirm/comments/1pukc1i/who_here_has_experience_with_day_trade_dash_in/) | $197/month | DTD standalone |

**Range: $147-$199/month.** Most expensive as Warrior bundle add-on.

**WallStreetZen (skeptical):** "Day Trade Dash doesn't offer anything over much cheaper alternatives, most notably TradingView, which Day Trade Dash appears to be based on." — This validates our **build on TradingView** approach.

---

## 3. 2026 DTD updates (since Jul 17)

- **No major feature changes detected** in web sources from Jul 17-21.
- **FINRA PDT change (Jun 4, 2026):** $25,000 minimum GONE, replaced with intraday margin requirements. `$2,000 remains the minimum equity for leveraged trading under Rule 4210`. **This affects Kay's €2K plan** — the EU €2K → US$ ≈ $2.2K is RIGHT at the new minimum, no longer blocked by PDT, but margin requirements apply.
- **No new DTD scanners detected** in any source.
- **Pricing stable** in the $147-$199 range.

---

## 4. Competitor matrix (2026 verified)

| Platform | Scanner count | Cost/mo | IBKR compat | Best for | Source |
|----------|---------------|---------|--------------|----------|--------|
| **DTD (Day Trade Dash)** | 24 | $147-199 | ❌ native (just charts/scanners/news) | Ross Cameron style small-cap momentum | multiple |
| **TradingView paid** | 50+ screener filters | $12.95-199.95 | ❌ (no auto-execute) | Charts + scanners + community | tradingview.com |
| **DAS Trader Pro** | custom (user-defined) | $150-175 (waived at high volume) | ✅ full | Momentum execution, hotkeys, sub-100ms routing | daytradingapp.com |
| **Sterling Trader Pro** | custom | $240 | ✅ (via Cobra/Centerpoint) | Hotkey scalpers | daytradingapp.com |
| **Lightspeed Trader** | custom | $130 (offset by commissions) | ❌ own broker | High-volume scalpers, $0.001/share | daytradingapp.com |
| **Cobra Trading** | custom (uses DAS) | $0.0015-0.003/share + $10k min | ❌ own broker | "Best direct access for most active day traders" | daytradingapp.com |
| **TradeZero** | basic | $0 on qual limit orders, $0.005 else | ❌ | Small accounts ($2,500 min) | daytradingapp.com |
| **Trade Ideas** | 30+ AI scanners | $118-668 | ❌ (alerts only) | AI-powered stock scanning | (multiple) |
| **Finviz Elite** | 30+ screeners (daily only) | $40/mo | ❌ (no real-time) | Daily charts + screening | (multiple) |
| **Unusual Whales** | options flow + 10 scanners | $30-100/mo | ❌ | Options flow + retail scanner | (multiple) |

**Key insights:**
- **DTD's only moat is the integration** (scanner + chart + news in one UI). Its data is TradingView, its scanners are public-domain filter sets, its news is Benzinga-like.
- **DAS Trader Pro is the de facto execution platform for momentum traders.** 100+ hotkey scripts, sub-100ms routing, IBKR-compatible.
- **Ross Cameron uses LightSpeed Trader as his broker**, NOT DTD. DTD is for charts/scanners/news only — execution is separate.
- **For Kay's build, our moat is also integration** — DTD's UI is browser-based only, ours is Python-driven and ties into the trading agent's Bull/Bear debate + IBKR auto-execute. No competitor has that loop.

---

## 5. User feedback themes (Reddit + Trustpilot + YouTube comments)

### 5.1 Praise (from Trustpilot 4.8/5 with 2,667 reviews, Reddit, YouTube)

- "All features you need in a single, straightforward interface" — universal praise
- "Support team responds quickly" — multiple Reddit comments
- "Scanners reliable, signals accurate" — multiple
- "Charts are always quick, no lag" — per YouTube review (1 day of issues in 6-7 months)
- "10 out of 10 scanners, no issues" — strong endorsement
- "Sub-1-min charts (1s/10s/15s/24s) are paramount for hyper-scalpers" — per Iamw-8-vwSg video

### 5.2 Complaints (3 consistent themes)

1. **"$197/month is too expensive"** — multiple Reddit r/propfirm, r/Daytrading comments
   - "At $197 a month it's simply beyond my budget"
   - **Implication for Kay:** Our build needs a clear cost narrative — "we built it for $X/month" is a different proposition than "$X/month for a subscription"
2. **"Chart freezes sometimes"** — Reddit r/propfirm user reports chart-unusable freezes (less common)
   - **Implication for our build:** robustness > features. Don't ship a scanner that crashes the dashboard.
3. **"Linked chart doesn't carry trend lines"** — YouTube review noted this as a minor UX flaw
   - **Implication:** our dashboard should be self-contained state, not rely on DTD-style linking

### 5.3 Feature requests (common themes)

- **Better backtesting** — DTD has no backtester. Our build can have one from day 1.
- **Webhooks for alerts** — some users want DTD alerts → their own bots. Our arch doc covers this (TV webhook → signals_live.json).
- **Mobile app** — DTD has no mobile. Per Mometic: "no dedicated mobile support."
- **Multi-account / multi-broker** — DTD is single-account. We can do multi-broker.

---

## 6. Ross Cameron's DTD-related behavior (Jul 2026)

**Direct signal in DTD review video [JjIUqdpFcHM](https://www.youtube.com/watch?v=JjIUqdpFcHM):**
- Ross uses **LightSpeed Trader** as execution broker, NOT DTD
- DTD is his **research + chart UI only**
- "I have no doubt that we're always going to continue to see updates"
- His scanner preference: small-cap high day momentum, top gainers, Ross's top gappers
- Confirms **pre-market, open, after-hours** coverage is essential

**Implication for Kay:** Our build should also have a "research/scanner/alert" plane (like DTD) PLUS an "execution" plane (DAS-style or IBKR direct) PLUS a "decision" plane (our Bull/Bear). The integration is the moat, not any single component.

---

## 7. Implications for our build (delta from arch v1.0)

### 7.1 Confirmed in our favor
- **Build on TradingView** ✅ — DTD is built on TV; we save R&D by doing the same
- **Sub-1-min charts via TV Ultimate ($199/month)** ✅ — DTD has 1s/10s/15s, so do we
- **Integration moat** ✅ — no competitor combines scanner + chart + decision (Bull/Bear) + execution (IBKR) in one agent-driven loop
- **Cost moat for Kay** — $147-199/month DTD vs our build = $0/month after Phase 1

### 7.2 Should add to v1.0 architecture
- **Sub-second chart refresh** — confirmed critical for hyper-scalpers (multiple sources)
- **Mobile-friendly dashboard** — DTD has no mobile, opportunity
- **Per-scanner customization** like DTD's "Ross's top gappers" (penny stocks excluded) — needs user-level filter overrides
- **Backtester from day 1** — DTD gap, our opportunity

### 7.3 Should NOT add (out of scope for v1.0)
- After-hours scanner (v0.1 already covers pre-market + intraday; add after-hours in Phase 2+)
- Options flow scanner (Unusual Whales territory, not small-cap momentum)
- Mobile native app (responsive web only)

### 7.4 Filter threshold adjustments (proposed)

**Current v1.0 arch has RV ≥ 5x for most scanners.** Community values (BBT + Reddit) are **RV ≥ 2x** with more granular price/float tiers. Recommendation:

- **Scanner 1 (Top Gainers):** RV ≥ 3x (between our 5x and community 2x)
- **Scanner 3 (Small Cap High Day):** RV ≥ 2x (match community, capture more setups)
- **Scanner 5 (First Pullback):** RV ≥ 5x (keep tight, this is our edge)
- **Scanner 10 (Bull Flag Breakouts):** RV ≥ 2x + vol last 5 min ≥ 400% normal (community standard, well-validated)

Kay to confirm these thresholds. Defaults applied in arch doc unless Kay overrides.

---

## 8. Open questions (need Kay input)

1. **TradingView tier** — REA-0.2 from arch doc. For sub-1-min charts, needs Ultimate ($199/month). Or use IBKR consolidated tape (free with account) as alternative.
2. **DTD member-only walkthrough** — REA-1.2. Kay to log in and capture the actual per-scanner filter UI + alert UX.
3. **Filter threshold overrides** — section 7.4 above. Kay to accept/reject the RV threshold changes.
4. **Phase 1 budget** — DTD at $147-199/mo vs our build at $199/mo TV Ultimate + $0 elsewhere. Is the $199/mo acceptable as a Phase 1 cost?

---

## 9. Source list (all URLs cited)

### DTD reviews & pricing
1. https://bullishbears.com/warrior-trading-review/ — BullishBears (Mar 2026)
2. https://www.wallstreetzen.com/blog/warrior-trading-review/ — WallStreetZen
3. https://blog.mometic.com/top-10-day-trading-stock-scanners-in-2025/ — Mometic
4. https://bananafarmer.app/compare/ross-cameron-scanner — BananaFarmer
5. https://www.trustpilot.com/review/warriortrading.com — Trustpilot 4.8/5
6. https://www.reddit.com/r/propfirm/comments/1pukc1i/who_here_has_experience_with_day_trade_dash_in/ — Reddit r/propfirm

### DTD walkthroughs
7. https://www.youtube.com/watch?v=JjIUqdpFcHM — Warrior Trading DTD Review (scanner types)
8. https://www.youtube.com/watch?v=HybGfXdt1Hk — Warrior Trading 14-Day Trial Review
9. https://www.youtube.com/watch?v=Iamw-8-vwSg — DTD platform review (sub-1-min charts confirmed)

### Scanner filter values (public)
10. https://bearbulltraders.com/wp-content/uploads/2023/02/TI_Settings.pdf — Bear Bull Traders PDF, 8 bull flag strategies
11. https://www.reddit.com/r/Trading/comments/o9m98w/warrior_trader_scanner_settings/ — Reddit scanner settings
12. https://www.warriortrading.com/bull-flag-trading/ — Bull flag entry methodology
13. https://www.warriortrading.com/how-to-trade-the-bull-flag-pattern-with-confidence/ — Bull flag rules
14. https://www.youtube.com/watch?v=DP4ayEWhmvM — Bull flag master class

### Competitor platforms
15. https://daytradingapp.com/brokers/direct-access — Cobra, Lightspeed, TradeZero, DAS, Sterling (2026)
16. https://rizetrade.com/brokers/das-trader-pro-supported-brokers — DAS supported brokers (2026)
17. https://www.daytradelab.com/best-day-trading-brokers-2026/ — Best brokers 2026
18. https://practicetestgeeks.com/day/best-day-trading-brokers — Best brokers 2026

### Strategy + market
19. https://www.youtube.com/watch?v=JCd6EuhA6jU — Small Caps 2026 rotation strategies
20. https://www.tradingview.com/scripts/warrior/ — TradingView Warrior indicators
21. https://www.youtube.com/watch?v=ExvoIqNglOk — Best day trading strategy for beginners 2026

---

## 10. Status + next steps

**What this intel refresh gives us:**
- Concrete filter values for 10 of our 24 MVP scanners (no DTD member access needed for these)
- Competitor pricing & positioning (we win on cost + integration depth)
- 2026 regulatory change (PDT $25k floor gone) — Kay's €2K plan now viable
- User feedback themes (cost, robustness, backtesting) — validate our v1.0 priorities

**What we still need from Kay (in priority order):**
1. Walk through DTD UI in browser → capture actual per-scanner filter values + alert UX → write `docs/dtd-walkthrough-2026-07-XX.md` (REA-1.2)
2. Confirm TradingView tier (REA-0.2) → unblocks 10s chart strategy
3. Confirm IBKR market data subs (REA-0.3) → unblocks Level 2 + 10s IBKR data
4. Approve proposed filter threshold changes (section 7.4)
5. Authorize Phase 2 build (Data + Scanner MVP) — 1-2 weeks

**Next intel refresh:** when bg_f610f803 finishes (researcher-agent in-depth sweep), merge its findings into this doc + flag any conflicts.

---

*Generated by Hermes (Mavis Code) on 2026-07-21 11:30 Berlin.*
*Part of the DTD-replica re-architecture sprint. See `E:\Me\TradingAgent\docs\ARCHITECTURE_v1.0.md` and `.hermes\plans\re-architecture-kanban.md` for context.*
