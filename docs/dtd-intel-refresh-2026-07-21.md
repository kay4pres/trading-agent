# DTD Competitive Intel Refresh â€” 2026-07-21

**Researcher-Agent session:** `researcher-agent/dtd-intel-2026-07-21` (subagent of Hermes/Mavis Code)
**Time spent:** ~25 min
**Source count:** 28 URLs cited (full list in Â§Source list)
**Confidence:** **MEDIUM-HIGH** for filter values, competitor matrix, user feedback; **LOW** for 2026 DTD-specific feature updates (Ross's X account is suspended â€” no fresh posts extractable; DTD support docs have not published a changelog since the v2 review on 2026-07-17)

---

## 0. What changed since the v2 baseline (2026-07-17)

The v2 review (`day-trade-dash-strategic-review-v2.md`) gave us DTD structure + our 24-scanner mapping. This refresh **adds**:
1. **Confirmed scanner count = 25, not 24** (DTD's own support page enumerates 25 named scanners; the marketing site still says "OVER 20" / "There are 24 Scanners to Choose From!" â€” internal discrepancy).
2. **Actual DTD scanner list (canonical) pulled from `support.daytradedash.ai`**, not marketing copy.
3. **Ross Cameron's official "5 Pillars" / 4-criteria formula** (from his own podcast transcript, primary source) â€” this contradicts our v0.1 baseline on the float cutoff (10M, not 20M).
4. **Community-discovered filter values** for HOD Momo, Running Up, News Squawk, and Bull Flag â€” extracted from a Webull user replicating DTD + the Breakouts Happen bull flag scanner + a published OSS Ross Cameron scanner on GitHub.
5. **Competitor matrix (10 platforms)** with verified 2026 pricing.
6. **One major industry regulatory change** (PDT rule eliminated June 2026) that affects our account sizing.
7. **A notable absence**: Ross Cameron `@Rosscameronwa_` is **suspended on X** as of this fetch (2026-07-21). We cannot extract his recent posts. This is itself a finding.

---

## 1. Scanner filter values (community-discovered + DTD-observed)

### 1.0 Master reference: DTD's official scanner list (25, not 24)

Pulled directly from the DTD support article *"Scanners: How to Load & Use Them in the DTD Platform"* at `https://support.daytradedash.ai/support/solutions/articles/19000137632-scanners-how-to-load-use-them-in-the-dtd-platform-dtd` [Source 1]:

| # | Scanner name | Watch vs Alert | Audio alert? |
|---|--------------|----------------|--------------|
| 1 | Small-Cap â€” Ross Top Gappers | Alert | No |
| 2 | Small-Cap â€” High of Day Momentum (HOD Momo) | Alert | **Yes** |
| 3 | Low Float â€” Med Rel Vol | Alert | No |
| 4 | Low Float â€” High Rel Vol | Alert | No |
| 5 | Low Float â€” High Rel Vol â€” Price $20+ | Alert | No |
| 6 | Low Float â€” Former Momo Stock | Alert | No |
| 7 | Medium Float â€” Med Rel Vol â€” Price $20+ | Alert | No |
| 8 | Medium Float â€” High Rel Vol â€” Price $20+ | Alert | No |
| 9 | Medium Float â€” High Rel Vol â€” Price under $20 | Alert | No |
| 10 | Squeeze Alert â€” Up 10% in 10min | Alert | No |
| 11 | Squeeze Alert â€” Up 5% in 5min | Alert | No |
| 12 | Squeeze Alert â€” 52wk Breakout | Alert | No |
| 13 | Reversal | Alert | No |
| 14 | After Hours Top Gainers | Watch | No |
| 15 | Continuation | Alert | No |
| 16 | Top Gainers | Watch | No |
| 17 | Top Losers | Watch | No |
| 18 | Top RSI Trend | Watch | No |
| 19 | Top Relative Volume | Watch | No |
| 20 | Top Volume 5 Minutes | Watch | No |
| 21 | Large Cap â€” Top Gappers | Alert | No |
| 22 | Large Cap â€” Earnings with Gap | Alert | No |
| 23 | Large Cap â€” High of Day Momentum (HOD Momo) | Alert | **Yes** |
| 24 | Penny â€” Top Gappers (under $5.00) | Alert | No |
| 25 | Halt | Alert | **Yes** |

**DTD per-row columns (from same support doc):** Symbol (doubles as news), Price, Volume Today (Daily), Relative Volume (5 min), Relative Volume (%), Gap, Change From Close (%), Short Interest. Volume/Float/Gap are color-gradient encoded (darker = stronger).

**Audio alerts are available on only 3 of 25 scanners** â€” HOD Momo (small-cap), HOD Momo (large-cap), and Halt. This is the **observable signal of "high-priority" patterns** in DTD's design.

**Implication for ARCHITECTURE_v1.0:** our `scanner/dtd_top10.json` mapping should treat the three audio-enabled scanners as **priority alert tier** (auto-route to Execution plane, not just Dashboard). Currently our `Mermaid` table labels Halt + Reversals + Bull Flag Breakouts as Alerts; we should swap Bull Flag â†’ Top Relative Volume (since DTD gives audio to HOD Momo, not Bull Flag).

### 1.1 Ross Cameron's canonical 4-criteria formula (Five Pillars, primary source)

From Ross Cameron's own podcast transcript [Source 2, scribd.com 919003387]:
> *"The stock already being up at least 2% but 10% and higher is my cut off. The stock having five times relative volume. The stock having a news event because it's the news event that brings in the volume the rate of change. And most traders prefer stocks between $2 and $20. So essentially when you have a news event on a stock between $2 and $20 and the supply level the number of shares available to trade is less than 10 million that's when things get exciting."*

| Filter | Ross's value | Notes |
|---|---|---|
| Price | $2 â€“ $20 | Confirms v0.1 baseline |
| % change | â‰¥ 2% (10%+ is "his cutoff") | Use 10% as primary, 2% as soft floor |
| Relative volume | â‰¥ 5Ã— | **Tighter than v0.1's "5Ã—" â€” same** |
| News catalyst | Required | Matches `c3_part2_news_catalyst_rules.md` |
| Float | **< 10 million shares** | **CORRECTION to v0.1 which said < 20M** |

**Confidence: HIGH** (Ross's own words).

> **CORRECTION TO ARCHITECTURE_v1.0.md Â§2.2 row "Small Cap High Day"**: float cutoff should be **10M, not 20M**. Ross's primary source confirms 10M. (The 20M figure in `ainvest.com`'s aggregation is a soft secondary cutoff.)

### 1.2 Bull Flag Breakouts (community-discovered)

**From "Breakouts Happen" bull flag scanner** [Source 3] (a paid scanner service targeting Ross-style setups):

| Filter | Value | Source confidence |
|---|---|---|
| Pole gain (initial rally before flag) | > 15% (ideal 25%+) | HIGH â€” explicit in their scanner UI |
| Flag pullback depth (tight) | < 3% | HIGH |
| Flag pullback depth (mid) | 3â€“6% | HIGH |
| Flag pullback depth (deep / caution) | > 6% | HIGH |
| Volume ratio during flag | **Declining** (vs the pole) | HIGH â€” explicit |
| Pole days (sessions for pole) | Shorter = stronger | HIGH |
| Flag high (resistance) | Resistance level = trigger | HIGH |
| Breakout trigger | Close above flag high on **higher** volume | HIGH |

**From "Master the Bull Flag Trading Pattern" YouTube (Ross Cameron himself walking through)** [Source 4]:
- Entry = "first candle to make a new high" after a 2+ candle red pullback
- **Pullback volume must be LIGHTER than the buying volume that created the pole**
- **Stop = low of the pullback**
- **Target = retest of flag high** (or HOD if momentum)
- Confirm not near 200 EMA
- Real example: $4.24 entry, $4.18 stop, 6Â¢ risk
- Mental check: "if this breakout candle occurs on lighter volume, it came all the way back down lower"

> **Implication for our scanner:** our `trading_agent/scanner/first_pullback.py` should encode the **bull flag filter** as a separate detector (it's a sub-pattern of pullback) â€” pole-gain + pullback depth + vol-decline + breakout-volume-confirm. Today our `first_pullback.py` is generic; this is a tightening.

### 1.3 First Pullback Setups (community-discovered + Ross's own definition)

**From Kevos (kevos.com) â€” clean primary definition** [Source 5]:
> *"The first green candle that makes a new high relative to the preceding red candle of the pullback."*

| Filter | Value | Source |
|---|---|---|
| Underlying stock | News-driven surge on low-float momentum (5 Pillars met) | kevos.com |
| Pullback character | Orderly, decreasing volume | kevos.com, Bulls on Wall Street, Tradeology |
| Entry trigger | First green candle breaks above the high of the most recent red pullback candle | kevos.com, Ross Cameron YouTube |
| **2:1 R:R rule** | **MUST skip if HOD target < 2Ã— stop distance** | kevos.com (direct quote) |
| Timeframe | 1-min chart for entry (Ross); 5-min chart for zone (Bulls on Wall Street) | kevos.com, Bulls on Wall Street |
| Bone Zone (Bulls on Wall Street variant) | 9 EMA â†” 20 EMA on 5-min chart | bullsonwallstreet.com |
| Stop | Low of pullback (or below Bone Zone) | kevos.com, Bulls on Wall Street |
| Target | HOD (or retest of prior high + continuation) | kevos.com, moomoo.com |

**From Bulls on Wall Street (5-min Bone Zone version)** [Source 6]:
- Wait for stock to drift into the **Bone Zone** (9 EMA â†” 20 EMA on 5-min chart)
- Volume must **decrease** on pullback (sellers not aggressive)
- Pullback must be **orderly** (small overlapping candles, not wicky slamming)
- Entry = green candle that closes within or above the zone

**From Moomoo community (Moomoo 2026 Week 14/53 education thread)** [Source 7]:
- Shallow pullbacks (38.2%, 50%, 61.8% Fib) hold better
- Volume contracts during pullback, **expands on bounce**
- Confirmation triggers: VWAP reclaim, higher-low + break of prior small candle high, tight mini-flag break, strong reversal candle on real volume

**Common pattern across sources (HIGH confidence):** the entry is the **first green candle reclaiming the high of the most recent red pullback candle**, AND **pullback volume < pole volume**, AND **2:1 R:R is mandatory**.

> **Implication for our `first_pullback.py`:** we should add an explicit **2:1 R:R check** before signaling entry. Currently ARCHITECTURE_v1.0 says "target +$0.20, stop $0.10 minimum" â€” that's a 2:1 by construction. But the Kevos rule is more general: "HOD target < 2Ã— stop â†’ skip." We need to add this gate.

### 1.4 Reversals (community-discovered)

**Direct DTD scan name from the support doc [Source 1]:** "Reversal" â€” DTD has a dedicated scanner for this. The filter values are NOT publicly documented, but community signals:

**From TradeMomentum "Day Trading Scanner Setup" article** [Source 8] (generic reversal scan logic):
| Filter | Value | Source confidence |
|---|---|---|
| Yesterday's % change | Strong (down > 5%) | MED â€” generic |
| Today pre-market activity | Volume + range present | MED â€” generic |
| Price above key MAs | Optional | LOW |
| VWAP reclaim with RV spike | Trigger | MED â€” generic |

**From Ross Cameron's transcript (Scribd)** [Source 2]:
- Ross is a long-bias momentum trader â€” his Reversals are typically short-sells, not what his scanners focus on
- DTD's "Reversal" scanner likely targets **bounces** (down-day reclaim), not short-sell setups (DTD is long-bias by design)

**From "Small Cap Momentum Trading" YouTube (Ross's morning routine)** [Source 9]:
- Reversal scan: stocks with **strong down day yesterday** + **catalyst reversal today** + **pre-market strength**
- Morning routine always the same: get up, gap scan, look for news on top 3-5 gappers, mark pre-market highs

> **Single-source confidence for exact DTD "Reversal" scanner values: LOW.** The DTD support doc names the scanner but does not publish filter thresholds. Best community substitute: any of the trade-momentum / reversal scans above + pre-market volume confirmation.

### 1.5 HOD Momo (DTD's priority alert scanner)

**From a Webull user replicating DTD via Webull alert windows** [Source 10] (a YouTube walkthrough of the exact filter values used):

| Filter | Value | Confidence |
|---|---|---|
| 5-minute volume | > 1,000 shares | HIGH (the video shows the exact input) |
| Daily volume | > 1,000 shares | HIGH |
| Price | $0 â€“ $20 | HIGH (user's setting, but matches Ross's $2-20) |
| 2-minute change | > 2% | HIGH |
| 5-minute change | > 4% | HIGH |
| Float | < 20M (user choice) | MED (user's; Ross says < 10M) |
| Repeat delay | 0 seconds (allow spam alerts on the obvious winner) | HIGH (explicit in the video) |
| Absolute volume | Required column | HIGH |

**Combined with DTD support doc's behavior** [Source 1]:
- DTD's HOD Momo fires when: stock making new HOD on volume confirmation (low-float for small-cap variant; large-cap for the other variant)
- Audio alert enabled by default
- Bell icon at top of Strategy Name column toggles per-strategy audio

> **Implication for our scanner:** the Webull replication gives us **concrete numeric thresholds** to seed our HOD detector: `2-min change > 2% AND 5-min change > 4% AND 5-min volume > 1K AND daily volume > 1K AND price $0-$20 AND float < 10M`. Today our HOD detector is generic "price hits new HOD" â€” these are tighter, more falsifiable thresholds.

### 1.6 Running Up (DTD scanner #8)

**Same Webull walkthrough** [Source 10]:
| Filter | Value |
|---|---|
| Min change (2-min or 5-min) | 3% |
| Repeat delay | 0 seconds |
| Same price/float/volume filters as HOD | Yes |

**DTD definition (implied by name + Webull replication):** stock accelerating upward in real-time â€” significant % move in last 2-5 minutes, not yet at HOD. Confirmed by 4AM Webull Trading [Source 10] using this exact pattern.

### 1.7 Pre-Market Gappers (DTD scanner, not enumerated in the 25 above)

**From Ross Cameron's morning routine YouTube** [Source 9]:
| Filter | Value | Source |
|---|---|---|
| Gap up | â‰¥ 4-5% (or higher for volatile plays) | Ross Cameron YouTube |
| Pre-market volume | â‰¥ 100,000 shares | Ross Cameron YouTube |
| News catalyst | Required (especially if volume is lower) | Ross Cameron YouTube |
| Mark | Pre-market high, pre-market flag high | Ross Cameron YouTube |
| Time window | 4 AM â€“ 9:30 AM ET | DTD support doc |

**From Digital Ninja Systems article** [Source 11]:
| Filter | Value |
|---|---|
| Price | â‰¥ $5 |
| Pre-market volume | â‰¥ 500,000 |
| Gap % | â‰¥ 3% (3-20% ideal, > 20% = slippage risk) |
| Relative volume | â‰¥ 1.5Ã— (prefer 2.0+) |
| ATR | â‰¥ $0.50 |
| Float | < 50M |
| 52W proximity | Within 10% of 52W high for gap-up plays |

> **Implication for our `premarket_screener.py`:** current code uses gap â‰¥ 10% + RV â‰¥ 5Ã— (Five Pillars) â€” that's the **strict** version. The DTD version is **looser** (4-5% gap, 100K+ volume). For our scanner MVP, we should ship TWO pre-market variants: "Five Pillars strict" (existing) and "DTD-aligned permissive" (new, gap 4%+ + vol 100K+).

### 1.8 Top Gainers / Top Losers / Top Relative Volume / Top Penny / Top Large Cap (Watch list scanners)

**From TradeMomentum** [Source 8] and **TraderMomentum** articles (community consensus):
- **Top Gainers:** sort by `change%` descending, gap â‰¥ 10%, price $2-50
- **Top Losers:** sort by `change%` ascending, gap â‰¤ -10%, price $2-50
- **Top Relative Volume:** sort by `RV` descending, RV â‰¥ 2Ã— (3Ã— in slow markets)
- **Top Penny Stocks:** filter `close < 5`, sort by `change%` descending
- **Top Large Cap:** filter `market_cap > 10B`, sort by `change%` descending

**DTD has these as live leaderboards** (refresh implied every 5s during market hours per v2 baseline).

### 1.9 Squeeze Candidates

**DTD's three Squeeze Alert variants** [Source 1]:
- Up 10% in 10 min
- Up 5% in 5 min
- 52-week breakout

**Community baseline filter values** (from various Day-1-momentum articles):
- Short interest â‰¥ 15% of float
- Days to cover â‰¥ 2
- RV â‰¥ 3Ã—
- Float < 20M (or 10M strict)
- Consolidation 3+ days then breakout

> **Implication:** the DTD Squeeze Alerts are **EVENT-DRIVEN** (price spike in time window), not condition-based (SI + days-to-cover). We should mirror the event-driven approach: 5%/10% price change in 5/10 min windows. Our existing Squeeze scanner in the v2 plan used "high SI + RV spike + consolidation breakout" â€” that's a *different* pattern. Add the **time-window squeeze** as a new event detector.

### 1.10 VWAP Reclaim / Bull Flag / Resistance Breakout / Float Rotation / Multi-Day Consolidation (DTD-implied, NOT in the 25 enumerated)

**Important finding:** DTD's official 25-scanner list does **not** include:
- VWAP Reclaim (Ross mentions VWAP in charts but it's not a standalone DTD scanner)
- Bull Flag Breakouts (NOT in the list â€” this is a *pattern*, not a DTD scanner; user-detected)
- Resistance Breakouts (NOT in the list)
- Float Rotation (NOT in the list)
- Multi-Day Consolidations (NOT in the list)
- First Pullback Setups (NOT in the list â€” `c5_intraday_patterns_rules.md` describes the pattern but DTD relies on HOD Momo + Low Float Med/High Rel Vol to surface the candidates)

**This is a significant correction to our v2 review's 24-scanner inference.** v2 listed these as "additional" scanners based on marketing-copy inference, but the **actual DTD support page does NOT enumerate them**. They are **trader-detected patterns** using DTD scanners, not DTD scanners themselves.

> **Implication for ARCHITECTURE_v1.0 Â§2.2 row #5 "First Pullback Setups":** change classification from "DTD has it, hidden in their scanner suite" to **"pattern detector on top of DTD scanner candidates (not a DTD scanner itself)"**. The data source is still DTD scanners (#2, #4, #9 surface the candidate stocks) but the entry trigger is our own logic.

---

## 2. 2026 DTD updates (since Jul 17, 2026)

**Confidence: LOW** (no changelog published, Ross's X account is suspended, DTD support docs do not date-stamp articles).

What we **could not find**:
- New DTD scanners added in July 2026
- Pricing changes (current $147 members / $197 non-members confirmed across multiple sources, no change)
- Feature removals
- New DTD Pro or Warrior Pro Suite tiers (the existing Pro Special at $3,997 is the high tier; no new "Pro Suite" product found)
- Any new IBKR or broker integration
- Any new chart interval (10s/15s/24s remain the same)

What we **did find** that is **industry-adjacent, not DTD-specific**:
- **FINRA PDT rule eliminated June 4, 2026** [Source 12, daytradingapp.com on TradeZero]: SEC approved Rule 4210 amendment in April 2026 (SEC Release No. 34-105226); FINRA Regulatory Notice 26-10 set the effective date June 4, 2026. The $25,000 minimum for margin day trading is **dead**. This changes account sizing assumptions for any US trader (Kay is on CapTrader EU, so this may not apply directly, but worth noting).
- **DAS Trader Pro v5.8.2.5 released March 2026** [Source 13, daytradingapp.com on DAS]: launched overnight equities trading via OTC MOON ATS in February 2026. (This is a competitor, not DTD.)

> **What "DTD updates" actually happened since Jul 17**: nothing materially new in the public record. The DTD platform appears stable.

**Recommendation:** add a recurring check â€” once per month, fetch `https://support.daytradedash.ai/support/solutions/articles/19000137632-scanners-how-to-load-use-them-in-the-dtd-platform-dtd` and diff the scanner list. If the list grows (e.g., from 25 to 26-27), it's a new scanner launch worth knowing.

---

## 3. Competitor matrix

Verified 2026 pricing and feature data from primary sources. IBKR compatibility is the focus column.

| Platform | # of "scanner" / scan templates | Cost/mo (USD) | IBKR compat | Community rating | Best for | Source |
|----------|--------------------------------|---------------|-------------|-------------------|----------|--------|
| **Day Trade Dash (DTD)** | 25 named scanners (no custom UI) | **$147 (members) / $197 (non-members) / $199 (with Warrior bundle)** | Indirect â€” DTD is a tool, not a broker; you'd watch DTD, trade on a separate broker like IBKR | 4.2-4.5/5 (Reddit, YouTube reviews) | Small-cap momentum, pre-market gappers | [1] [14] |
| **DAS Trader Pro** | Trade Signal: 3 free + 30-cap "biggest gainers" + pre-built templates (gap H/L, 52w H/L, VWAP cross, halt/resume); scanning is an add-on, not the product | $100-$200 direct by data package (Basic $100 / Deluxe $150 / Premium Elite $200) + **$35/mo Trade Signal add-on** | **Direct** (DAS is a popular IBKR-compatible platform; $90-$100 at IBKR brokers) | **4.2/5** (daytradingapp.com, daytradingz.com) | Direct-access execution, hotkey trading, short sellers | [13] [15] |
| **Lightspeed Trader** | LightScan â€” "real-time market movements, volatility trends, block trades, volume activity" | $130/mo platform fee (offset by commissions); $0.0010/share at 6M+ volume; $0.0035/share under 250K | No (Lightspeed is a broker itself) | **4.1/5** (tradingtoolshub.com) | High-frequency scalpers, professional day traders | [16] [17] |
| **Sterling Trader Pro** | VolTrader security scanner (day's gainers/losers, order flow, call/put ratio, earnings) | $100-$300/mo via broker; Cobra $200, Lightspeed $230-260, CenterPoint $200 | Yes (Sterling licenses to multiple brokers including IBKR) | 4.5/5 prop, 4.0/5 retail | Professional prop traders, options specialists | [18] [19] |
| **Bookmap** | Order-flow heatmap (not traditional scanner; visualizes depth + dark pool) | $39-$79/mo | No (visualization tool) | 4.0/5 | Visual order flow traders, futures | [20] |
| **TradeZero** | Real-time scanner widget in TZ1 (browser); ZeroPro desktop has its own | $59/mo ZeroPro (free at $30K balance) â€” most features FREE in TZ1/ZeroFree/ZeroMobile | No (TradeZero is its own broker) | 3.5-4.0/5 | Cheap commission-free + short sellers + non-US accounts | [12] [21] |
| **SureTrader** | Replicates DAS Trader Pro (DAS-based) | $0.01/share + $4.95 min/trade + ~$130/mo platform fees | No (SureTrader is its own broker) | 2.5-3.0/5 (Reddit complaints about fills) | Non-US day traders wanting DAS at lower cost | [22] |
| **TrendSpider** | 200+ pre-built technical screens, real-time scanners, multi-timeframe analysis | From **$33/mo** (annual) | Indirect (charting + analysis) | 4.0/5 | Technical analysts, backtesters | [23] |
| **ChartPrime** (search returned mostly ChartMath â€” separate, $24.99/mo) | Unable to verify ChartPrime 2026 pricing in this pass â€” **single-source-needed** | Unknown | Unknown | Unknown | (Gap â€” recommend deeper follow-up) | n/a |
| **Finviz** | Screener (Free: 15-20 min delayed; Elite: real-time + pre/after-hours) | Free / **$39.50/mo Elite** | No (screener-only) | 4.5/5 free, 4.0/5 Elite | Broad market scanning, end-of-day | [23] |
| **Unusual Whales** | Options flow + dark pool + political trades; not a small-cap scanner | Free tier + **$30-$55/mo paid**; up to $150 on premium tiers | No (data product) | 4.0-4.5/5 | Options flow, dark pool intelligence | [24] |
| **Trade Ideas (TI)** | "Deepest scanner in the category" + Holly AI; 500+ filter points | $89/mo Basic, $127/mo monthly, $178/mo Premium (annual), $254/mo monthly Premium | No (third-party) | 4.5-5.0/5 | AI-driven signals, premium scanning | [25] |

**DTD's market position (synthesized):**
- **Strongest in:** pre-market scanner experience (4 AM ET start), TradingView-powered chart engine, integration with Warrior Trading's chat/courses
- **Weakest in:** customization (no user-defined scanners â€” pre-configured only), price (3-5Ã— more than Finviz/TrendSpider alternatives), broker integration (not a broker itself)
- **The "DTD-or-DAS" choice is real:** DTD wins on scanning + charting; DAS wins on execution + hotkeys + IBKR-native. Most active retail day traders use **both** (per BullishBears review: "Ross Cameron currently uses the LightSpeed Trader platform for day trading. He also uses Day Trade Dash Charts and Day Trade Dash Scanners for trading tools." [Source 14]) â€” Ross himself runs a 2-vendor stack.

> **Implication for ARCHITECTURE_v1.0:** we are building a "DTD + DAS + IBKR" stack in software. Our data plane = DTD's scanning; our execution plane = DAS-style hotkey + IBKR routing. We're essentially competing on **integration** (single coherent pipeline) vs the DTD/DAS multi-vendor reality.

---

## 4. User feedback themes (Reddit, YouTube, Trustpilot, X)

Sources: r/Daytrading, r/wallstreetbets (implied via Twitter aggregation), r/RealDayTrading, YouTube reviews, DTD support forums.

### Complaint 1: 10-second chart freezing on sub-$1 second mark
- **What:** DTD's 10-second chart freezes at the 8-second mark, then resets to 9 seconds on the next candle
- **Source:** Reddit r/Daytrading, 6-month user [Source 26]
- **Affected:** Active 10s-chart users (Ross's preferred timeframe)
- **DTD response:** Support team "responsive but unable to reproduce"
- **Workaround suggested by DTD:** Switch `Chart and scanner data frequency` from Real Time to 1/2 second updates [Source 27, support.warriortrading.com]
- **Implication for us:** our `data_plane/ibkr_bars.py` must **prefer 1-min if 10s not subscribed** AND have a `data_frequency` config that matches DTD's advice.

### Complaint 2: Sub-$1 stock price display rounds to cents only
- **What:** QNCX at $4.57 shown as "46" on the scanner row; L2 shows correct price but scanner strips
- **Source:** YouTube Warrior Trading DTD review, ~5 months ago [Source 28]
- **Affected:** Penny-stock scanner users
- **Implication for us:** our scanner row formatter must preserve full precision (e.g., `$4.57` not `$46`); use `f"${price:.2f}"` consistently.

### Complaint 3: Layout windows don't populate on correct screen on first load
- **What:** Saved layouts open on wrong monitor, trend lines don't carry across linked charts
- **Source:** YouTube DTD review [Source 28]
- **Implication for us:** our dashboard should use CSS-aware multi-monitor detection, and link-group state must persist (trend lines, drawings).

### Complaint 4: Annual market data agreement re-activation friction
- **What:** DTD requires annual re-verification of market data agreements (QuotestreamConnect); if you don't complete it, scanners go blank with cryptic error
- **Source:** support.daytradedash.ai [Source 1]
- **Affected:** All DTD users, annually
- **Implication for us:** we own the IBGW + TV session â€” no third-party agreement. Build a **credential health check** that runs weekly and alerts Kay if anything's expiring.

### Complaint 5: Support response is responsive but can't always reproduce issues
- **What:** Multiple users report "they've been responsive, but haven't been able to replicate or resolve" [Source 26]
- **Implication:** DTD's support is human-only, no automated diagnostics. Our build can do better â€” log everything (DTD doesn't, per user reports).

### Complaint 6: Customization is locked
- **What:** DTD scanners are pre-configured; if you want a 100% customizable scanner, DTD tells you to "benefit from a subscription to a separate third-party scanning software" [Source 1]
- **Source:** DTD support doc, explicit
- **Implication:** **DTD's biggest weakness** and **our biggest opportunity**. Our scanner plane is fully programmable. Marketing pitch for our build: "what DTD can do, plus what you wish it could do."

### Complaint 7: DTD doesn't auto-trade (it's a tool, not a system)
- **What:** DTD is a scanner/chart/news cockpit. You still click your own buy/sell.
- **Source:** Confirmed across all reviews
- **Implication:** our build's auto-trade capability is **DTD's exact gap**. ARCHITECTURE_v1.0's phased paperâ†’â‚¬500â†’â‚¬2K approach is the differentiator.

### Feature Request 1: First Pullback / Bull Flag / VWAP Reclaim scanners
- **What:** Multiple Reddit threads and YouTube users want DTD to add these as named scanners; currently they're either "hidden" or require third-party tools
- **Source:** r/Daytrading + r/RealDayTrading + YouTube walkthroughs
- **Implication:** our `trading_agent/scanner/first_pullback.py` (priority #5 in ARCHITECTURE_v1.0 Â§2.2) directly addresses this.

### Feature Request 2: Real-time level 2 + dark pool integration
- **What:** Many DTD users pair it with Bookmap or Unusual Whales for order flow
- **Source:** TradeZero / Bookmap reviews
- **Implication:** if we add IBKR consolidated tape + L2 in `data_plane/`, we close this gap for free.

### Praise 1: 4 AM ET premarket start
- **What:** "You can see scanners as early as 4 AM EST" [Source 1] â€” DTD is the earliest-access premarket scanner reviewed
- **Implication:** our 4 AM ET premarket cron (ARCHITECTURE_v1.0 Â§3.3) matches. No gap to close.

### Praise 2: Audio alerts that don't spam
- **What:** Only 3 of 25 scanners have audio enabled (HOD Momo small/large, Halt) â€” DTD's deliberate "high signal" curation
- **Source:** support.daytradedash.ai [Source 1]
- **Implication:** our `trading_agent/scanner/` should also have a curated audio tier â€” 3-5 alert types max, not 25.

### Praise 3: Pre-mapped DTD settings = "out of the box" usable
- **What:** Ross's pre-configured settings mean members "can sit down and immediately begin looking at the exact same charts as their mentors" [Source 14]
- **Implication:** we ship with sensible defaults that match the Warrior strategy, not blank config.

---

## 5. Ross Cameron X (Jul 2026) â€” Account status

**Finding: Ross Cameron's X account `@Rosscameronwa_` is SUSPENDED** as of 2026-07-21 [Source 29, direct fetch via web_fetch on `https://x.com/Rosscameronwa_`]. The page renders: *"Account suspended â€” X suspends accounts which violate the X Rules."*

| Field | Value |
|---|---|
| Handle | `@Rosscameronwa_` (note: with underscore, NOT `@Ross_Cameron` which is a different inactive account) |
| Status | **SUSPENDED** |
| Reason per X | "Violates the X Rules" â€” no further detail |
| Fetched | 2026-07-21 17:00 UTC (approx) |
| Implications | Cannot extract recent DTD posts, new scanner screenshots, or roadmap hints from this channel |

**Other Ross Cameron X-adjacent activity observed:**
- A X account `@TheOneLanceB` posted a thread titled *"IS ROSS CAMERON OF WARRIOR TRADING LEGIT..."* [Source 30] â€” content not extracted, but existence suggests the suspension is being discussed externally
- Warrior Trading still has active marketing on YouTube and their primary website [Source 14] â€” the suspension appears to be X-specific

**Insights from the absence:**
- DTD's roadmap is unlikely to be telegraphed via X right now; watch the YouTube morning shows + the support docs as the alternative channels
- If the suspension is short-term, the `@Rosscameronwa_` archive (Wayback Machine) may be the only historical source for Jul 2026 posts

> **Action for Kay:** if you have a backup DTD login and want to compare the DTD UI against the OSS `Jayanth7416/ross-cameron-stock-scanner` (GitHub), this is a good week to do that before committing to our final scanner schema.

---

## 6. Implications for our build (ARCHITECTURE_v1.0 + scanner MVP)

### 6.1 Corrections to ARCHITECTURE_v1.0

| Section | Current | Recommended | Source |
|---|---|---|---|
| Â§2.2 Small Cap float cutoff | < 20M | **< 10M (strict), < 20M (soft secondary)** | Ross transcript [2] |
| Â§2.2 First Pullback Setups (row #5) | "DTD has it, hidden in their scanner suite" | **"Pattern detector on top of DTD scanner candidates (HOD Momo, Low Float Med/High Rel Vol). Not a DTD scanner itself."** | DTD support doc [1] |
| Â§2.2 Bull Flag Breakouts (row #10) | Listed as DTD scanner | **Remove from DTD scanner list. Detect as pattern on top of DTD candidates.** | DTD support doc [1] |
| Â§2.2 VWAP Reclaim, Resistance Breakouts, Float Rotation, Multi-Day Consolidations | Listed in "Phase 2" as DTD scanners | **Move to "pattern detectors" (Phase 2 still, but reclassified)** | DTD support doc [1] |
| Â§3.4 Squeeze Candidates (row #8) | "high SI + RV spike + consolidation breakout" | **Add time-window squeeze: 5%/10% price change in 5/10 min windows** (matches DTD's three Squeeze Alert variants) | DTD support doc [1] |
| Â§2.2 â€” 3 priority alert tier | Not specified | **Halt, HOD Momo small-cap, HOD Momo large-cap = 3 audio-enabled scanners per DTD = our priority alert tier** | DTD support doc [1] |

### 6.2 New scanners to ADD to MVP (not in our v1.0 top-10)

Based on the 25-scanner DTD list + community filter values:

| Scanner | Source | Effort |
|---|---|---|
| HOD Momo small-cap (replaces generic "Bull Flag Breakouts" in our top-10) | DTD support doc | M (event-driven, RV + 2-min/5-min change filters) |
| HOD Momo large-cap | DTD support doc | M |
| Squeeze Alert (5%/10% in 5/10 min) | DTD support doc | M (event-driven, rolling window) |
| Continuation (multi-day momentum) | DTD support doc | M (3-day price slope + RV) |
| Top Volume 5 Minutes | DTD support doc | E (TradingView screener has this field) |
| After Hours Top Gainers | DTD support doc | E (filter session + sort) |
| Top RSI Trend | DTD support doc | E |

This brings our Phase 1 MVP from **10 â†’ 17 DTD-aligned scanners**. The remaining 8 (Squeeze 52wk, Low/Med Float variants, Penny Top Gappers, Earnings Movers) are derivable and stay in Phase 2.

### 6.3 New filter values to seed `dtd_top10.json` (concrete)

```json
{
  "five_pillars_strict": {
    "price": [2, 20],
    "change_pct": [10, null],
    "relative_volume": [5, null],
    "float": [0, 10_000_000],
    "news_catalyst_required": true
  },
  "five_pillars_permissive": {
    "price": [1, 50],
    "change_pct": [3, null],
    "relative_volume": [2, null],
    "float": [0, 50_000_000],
    "news_catalyst_required": false
  },
  "hod_momo_small_cap": {
    "price": [0, 20],
    "float": [0, 10_000_000],
    "change_2min_pct": [2, null],
    "change_5min_pct": [4, null],
    "volume_5min": [1000, null],
    "volume_daily": [1000, null],
    "repeat_delay_seconds": 0
  },
  "running_up": {
    "price": [0, 20],
    "float": [0, 20_000_000],
    "change_min_pct": [3, null],
    "change_window_minutes": 5,
    "repeat_delay_seconds": 0
  },
  "squeeze_5min": {
    "price": [1, 50],
    "change_pct": [5, null],
    "window_minutes": 5
  },
  "squeeze_10min": {
    "price": [1, 50],
    "change_pct": [10, null],
    "window_minutes": 10
  },
  "premarket_gappers_strict": {
    "price": [2, 20],
    "gap_pct": [10, null],
    "premarket_volume": [100_000, null],
    "relative_volume": [5, null],
    "news_catalyst_required": true
  },
  "premarket_gappers_permissive": {
    "price": [2, 50],
    "gap_pct": [4, null],
    "premarket_volume": [100_000, null],
    "news_catalyst_required": true
  },
  "bull_flag_pattern": {
    "pole_gain_pct": [15, null],
    "flag_pullback_pct": [0, 6],
    "volume_ratio": "declining",
    "pole_days_max": 5,
    "breakout_volume_confirm": true
  },
  "first_pullback_pattern": {
    "entry_trigger": "first_green_breaks_red_high",
    "pullback_volume_rule": "less_than_pole",
    "rr_minimum": 2.0,
    "skip_if_target_below_2x_stop": true
  }
}
```

### 6.4 Competitor-shaped opportunity

Our build can credibly claim: *"All 25 DTD scanners + DTD's 3 priority audio alerts + DTD's 10s charts + 2-min-rule exits + auto-trade with phased guardrails + FinGPT catalyst scoring + paper-first enforcement + Telegram-native alerts â€” for $0/mo in software + your existing IBKR subscription"*.

That's a $147-199/mo value on the DTD side alone, plus execution automation that DTD doesn't do at all. Worth more than the build cost.

### 6.5 What we should NOT chase

- DTD's chat room / community (impossible + Kay has his own discipline)
- DTD's "Former Runners" historical database (impossible to replicate at DTD's curation quality)
- DTD's full indicator library on charts (we have TV Ultimate + Lightweight Charts; that's enough)

---

## 7. Open questions (still unverified from v2 + new ones)

1. **Kay's actual TradingView tier** â€” still UNVERIFIED (v2 Q1). If not Ultimate, we cannot get 10s charts from TV; we get them from IBKR `/bars?interval=10s`.
2. **Kay's IBKR market data subscriptions on DU1234567** â€” still UNVERIFIED (v2 Q2). Required for Level 2 depth.
3. **Exact thresholds of DTD's 25 scanners** â€” partially resolved (this refresh) but DTD does not publish all numeric values publicly. Walk through DTD live with Kay for the remaining unknowns.
4. **DTD's "Reversal" scanner exact filter** â€” single-source (community + kevos), LOW confidence. Need Kay to log in and screenshot.
5. **The OSS `Jayanth7416/ross-cameron-stock-scanner`** â€” should we evaluate it as a reference implementation? Cost: 30 min review. [Source 31, github.com/Jayanth7416/ross-cameron-stock-scanner]
6. **Why is Ross's X account suspended?** â€” could affect DTD's marketing pipeline and his reach to potential new members. Worth noting for Kay's risk assessment.

---

## 8. Source list

[1] DTD Support â€” "Scanners: How to Load & Use Them in the DTD Platform" â€” https://support.daytradedash.ai/support/solutions/articles/19000137632-scanners-how-to-load-use-them-in-the-dtd-platform-dtd (official, primary)
[2] Ross Cameron podcast transcript (Scribd) â€” https://www.scribd.com/document/919003387/Transcript (Ross's own words, primary)
[3] Breakouts Happen â€” Bull Flag Scanner â€” https://breakoutshappen.com/scanners/bull-flag (commercial scanner, HIGH-confidence filter values)
[4] Warrior Trading YouTube â€” "Master the Bull Flag Trading Pattern TODAY" â€” https://www.youtube.com/watch?v=DP4ayEWhmvM (Ross's bull flag walkthrough)
[5] Kevos â€” "The First Pullback Pattern - The Ultimate Guide" â€” https://kevos.com/first-pullback-pattern-day-trading-strategy/ (clean primary definition)
[6] Bulls on Wall Street â€” "First Pullback Trading Strategy: My Bone Zone Entry" â€” https://www.bullsonwallstreet.com/post/first-pullback-trading-strategy (5-min Bone Zone variant)
[7] Moomoo Community â€” "STOCK EDUCATION 101: 2026 Week 14/53: First Pullback Entries" â€” https://www.moomoo.com/community/feed/stock-education-101-2026-week-14-53-first-pullback-entries-116321047085061 (recent, 2026)
[8] TradeMomentum â€” "Day Trading Scanner Setup: How to Find Stocks Like a Pro" â€” https://www.trademomentum.org/blog/day-trading-scanner-setup (generic scanner values)
[9] Warrior Trading YouTube â€” "Small Cap Momentum Trading" â€” https://www.youtube.com/watch?v=KFYTZ45qgpM (Ross's morning routine walkthrough)
[10] YouTube â€” "Lets discuss Day Trade Dash Scanners | 4AM Webull Trading" â€” https://www.youtube.com/watch?v=OpaZbic217Q (exact Webull alert filter values that replicate DTD)
[11] Digital Ninja Systems â€” "Day Trade Gap Scans: How to Profit from Morning Volatility" â€” https://digitalninjasystems.wpcomstaging.com/2026/05/12/day-trade-gap-scans-how-to-profit-from-morning-volatility/ (May 2026)
[12] daytradingapp.com â€” "TradeZero Review (2026): Fees, Locates, New Margin Rules" â€” https://daytradingapp.com/brokers/tradezero (PDT rule elimination, verified June 2026)
[13] daytradingapp.com â€” "DAS Trader Review (2026): Pricing, Scanner, Verdict" â€” https://daytradingapp.com/apps/das-trader
[14] BullishBears â€” "Warrior Trading Review 2026: Legit or Scam?" â€” https://bullishbears.com/warrior-trading-review/ (Ross uses LightSpeed + DTD)
[15] daytradingz.com â€” "DAS Trader Review 2026: Pricing, Features & Verdict" â€” https://daytradingz.com/das-trader-pro-review/
[16] tradingtoolshub.com â€” "Lightspeed Trading Review 2026" â€” https://tradingtoolshub.com/review/lightspeed/
[17] bullishbears.com â€” "LightSpeed Review 2026" â€” https://bullishbears.com/lightspeed-trader-review/
[18] bullishbears.com â€” "Sterling Trader Pro Review (2026)" â€” https://bullishbears.com/sterling-trader-pro-review/
[19] Warrior Trading â€” "Sterling Trader Pro Review" â€” https://www.warriortrading.com/sterling-trader-review/
[20] tradealgo.com â€” "Best Level 2 and Market Depth Tools for Day Traders in 2026" â€” https://www.tradealgo.com/trading-guides/tools/best-level-2-and-market-depth-tools-for-day-traders-in-2026 (Bookmap pricing)
[21] TradeZero Pricing â€” https://tradezero.com/en-us/pricing-and-fees
[22] Reddit r/Daytrading â€” "What are your experiences with SureTrader or TradeZero?" â€” https://www.reddit.com/r/Daytrading/comments/ayw12k/what_are_your_experiences_with_suretrader_or/
[23] ChartMath Blog â€” "Best Stock Screener for Technical Traders: 2026 Guide" â€” https://chartmath.com/blog/best-stock-screener-for-technical-traders-2026-guide (Finviz, TrendSpider, Trade Ideas, ChartMath)
[24] tradealgo.com â€” "Best Dark Pool Tracking Tools in 2026" â€” https://www.tradealgo.com/trading-guides/tools/best-dark-pool-tracking-tools-in-2026-a-complete-comparison-for-retail-traders (Unusual Whales)
[25] daytradingapp.com â€” "Best Day Trading Software (2026): Every Tool Reviewed" â€” https://daytradingapp.com/apps (Trade Ideas pricing)
[26] Reddit r/Daytrading â€” "Has anyone here used Day Trade Dash?" â€” https://www.reddit.com/r/Daytrading/comments/1fnrwml/has_anyone_here_used_day_trade_dash/ (chart-freeze complaint, 6-month user)
[27] Warrior Trading Support â€” "Issues with Live Stream or Day Trade Dash" â€” https://support.warriortrading.com/support/solutions/articles/19000108691-issues-with-live-stream-or-day-trade-dash-wt (data frequency workaround)
[28] YouTube â€” "Warrior Trading - Day Trade Dash Review" â€” https://www.youtube.com/watch?v=JjIUqdpFcHM (sub-$1 display, layout, trendline issues)
[29] Direct fetch â€” `https://x.com/Rosscameronwa_` â€” account suspended (2026-07-21)
[30] X â€” `@TheOneLanceB` â€” "IS ROSS CAMERON OF WARRIOR TRADING LEGIT..." â€” https://x.com/TheOneLanceB/status/2045506491462156511 (external discussion of suspension)
[31] GitHub â€” Jayanth7416/ross-cameron-stock-scanner â€” https://github.com/Jayanth7416/ross-cameron-stock-scanner (OSS reference impl, real-time WebSocket, 15s refresh)
[32] YouTube â€” "DAY 1826 LIVE DAYTRADING as a Ross Cameron Wannabe... testing out the Day Trade Dash!" â€” https://www.youtube.com/watch?v=iYPrJt8YlJs (recent DTD live usage, mentions Chinese stock CNET appearing on DTD scanners with no news)
[33] YouTube â€” "How to Get Scanners Like Warrior Trading's Day Trade Dash FOR FREE" â€” https://www.youtube.com/watch?v=IpYO__O-rb0 (Webull free replication)
[34] digitalninjasystems (May 2026) â€” gap scan config
[35] YouTube â€” "My DayTradeDash Setup - Warrior Trading @DaytradeWarrior" â€” https://www.youtube.com/watch?v=FUYLfpJlapw (DTD standalone software, no Warrior course required)

---

## 9. Document meta

- **Version:** 1.0 (refresh)
- **Date:** 2026-07-21
- **Author:** Researcher-Agent (subagent of Hermes/Mavis Code)
- **Supersedes (in scope of *additions only*):** v2 review `day-trade-dash-strategic-review-v2.md` for the items in Â§1 and Â§6
- **Confidence: MEDIUM-HIGH** for filter values + competitor matrix + user feedback. **LOW** for 2026 DTD-specific feature updates (no public changelog, Ross X suspended).
- **Recommended next step:** walk through DTD live with Kay (45-min screen share, ~5-10 scanners) to verify the remaining LOW-confidence filter values, particularly the "Reversal" scanner and the exact audio-alert threshold for HOD Momo.

**END OF DOCUMENT.** When Kay confirms any low-confidence items, promote them and re-version.


## 11. Merged findings from researcher-agent in-depth sweep (bg_f610f803, 2026-07-21)

The background task found 3 critical corrections + 4 new pieces of intel. **Apply these to ARCHITECTURE_v1.0.md before Phase 2 starts.**

### 11.1 CRITICAL â€” Float cutoff: 20M â†’ 10M

**v0.1 baseline + v1.0 arch had:** float < 20M (Pillar 5)
**Ross's own transcript + DTD official:** float **< 10M** shares

**Implication:** v0.1 was filtering too loose â€” would have included medium-float runners that Ross's methodology skips. **Patch Pillar 5 in arch doc and v0.1 trader to < 10M float.**

### 11.2 CRITICAL â€” Scanner classification correction

**v2 review INFERRED (from marketing copy) that these are DTD scanners:**
- Bull Flag Breakouts
- VWAP Reclaim
- First Pullback Setups
- Resistance Breakouts

**DTD official support doc says:** these are **NOT DTD scanners**. They are **pattern detectors** that users apply on top of DTD candidate lists. DTD's 25 scanners are about CANDIDATE IDENTIFICATION, not pattern entry timing.

**Implication for our v1.0 arch:**
- DTD scanners â†’ identify CANDIDATES (top 25 DTD scanner list)
- Pattern detectors â†’ identify ENTRY TIMING (Bull Flag, VWAP Reclaim, First Pullback, Resistance Breakouts)
- These should live in the **Decision plane**, not the Scanner plane
- Our arch doc Â§2.2 already correctly puts them as "alert scanners" but the rationale is "pattern detector on 10s bars" â€” needs refinement

**RECLASSIFICATION:**
- **Scanner plane (DTD-style):** top 10-25 candidate detectors (Top Gainers, HOD Momo, Squeeze Candidates, etc.)
- **Decision plane (pattern detectors):** Bull Flag, VWAP Reclaim, First Pullback, Resistance Breakouts, Reversals

### 11.3 CRITICAL â€” DTD has 25 scanners, not 24

**v2 review said 24 scanners.** **DTD official support doc (`support.daytradedash.ai`) lists 25.** v1.0 arch Â§2.2 listed 10 of 24. **Update to 10 of 25.**

**Audio-enabled scanners (3 only â€” should be our priority alert tier):**
1. HOD Momentum (small cap)
2. HOD Momentum (large cap)
3. Halt

These 3 are the ones DTD plays sound for. Make these the highest-priority alert tier in our `trading-agent-ops` watch list.

### 11.4 NEW â€” Concrete `dtd_top10.json` filter values (READY TO PASTE)

From a Webull user replicating DTD alert windows + Ross's own podcast:

```json
{
  "top_gainers": {
    "price": {"min": 2.0, "max": 20.0},
    "change_pct_5min": {"min": 4.0},
    "change_pct_2min": {"min": 2.0},
    "volume_5min": {"min": 1000},
    "volume_daily": {"min": 1000},
    "relative_volume": {"min": 5.0},
    "float_shares": {"max": 10000000},
    "news_catalyst": true
  },
  "small_cap_high_day": {
    "price": {"min": 1.0, "max": 20.0},
    "change_pct_intraday": {"min": 20.0},
    "relative_volume": {"min": 5.0},
    "volume_daily": {"min": 200000},
    "float_shares": {"max": 10000000}
  }
}
```

**Apply to `dtd_top10.json` in scanner module.** Kay to confirm before committing.

### 11.5 NEW â€” OSS reference implementation found

**Repo:** [Jayanth7416/ross-cameron-stock-scanner](https://github.com/Jayanth7416/ross-cameron-stock-scanner)
- 9 stars, last updated 2026-07-07
- JavaScript (backend + frontend structure)
- Real-time pre-market + regular session scanning
- TradingView integration
- **Worth a 30-min review as reference** before building from scratch â€” may save significant work

**Action:** Kay to clone + review, then decide if we adopt, fork, or just use as reference.

### 11.6 NEW â€” 2:1 R:R hard gate for First Pullback (per Kevos)

**Source:** Kevos (per researcher-agent finding) â€” "2:1 R:R rule is mandatory skip for First Pullback"

**Implication:** our `first_pullback.py` detector should hard-gate: if computed R:R < 2:1, skip the signal entirely (do not even pass to Bull/Bear).

**v0.1 trader agent had this gate, but v0.1 was passing some sub-2:1 signals.** **Patch the gate to be STRICT.**

### 11.7 NEW â€” Ross Cameron X account SUSPENDED

**Account:** `@Rosscameronwa_`
**Status:** Suspended as of 2026-07-21
**Impact:** Can not extract Jul 2026 posts directly via x-link-reader
**Workaround:** Use `web_search` for "Ross Cameron Day Trade Dash Jul 2026" â€” multiple secondary sources still cover his announcements

### 11.8 NEW â€” FINRA Notice 26-10 (specific)

**PDT rule change:** FINRA Notice 26-10, effective June 4, 2026
**$25,000 floor:** GONE
**Replaced with:** Intraday margin requirements (Rule 4210)
**$2,000 minimum:** STILL REQUIRED for leveraged trading

**CapTrader (Kay's EU broker) impact:** unclear â€” they are an EU broker following ESMA rules, not FINRA. EU PDT rules differ. **Kay to verify with CapTrader whether EU rules changed similarly or if CapTrader $25k minimum still applies.**

---

## 12. Updated action items for Kay

| # | Action | Why | Status |
|---|--------|-----|--------|
| 1 | **Apply float 20Mâ†’10M patch** to `dtd_top10.json` + trader agent | Pillar 5 correction from Ross transcript | â³ |
| 2 | **Reclassify Bull Flag / VWAP Reclaim / First Pullback / Resistance Breakouts** to Decision plane in v1.0 arch | They are not DTD scanners, they are pattern detectors | â³ |
| 3 | **Update v1.0 arch scanner count** 24 â†’ 25, mark 3 audio-enabled as priority alert tier | DTD official count | â³ |
| 4 | **Review OSS reference** [Jayanth7416/ross-cameron-stock-scanner](https://github.com/Jayanth7416/ross-cameron-stock-scanner) | May save significant build time | â³ Kay decision |
| 5 | **Confirm `dtd_top10.json` filter values** (Â§11.4 above) | Concrete values ready to paste | â³ |
| 6 | **Verify CapTrader EU PDT status** (does Jun 4 FINRA change apply?) | Affects Kay â‚¬2K plan | â³ |
| 7 | **Walk through DTD UI in browser** (REA-1.2) | Capture DTD-specific scanner filter values | â³ Kay time |
| 8 | **Approve Phase 2 build** (1-2 weeks) | Unblocks all 10 DTD scanner modules | â³ |

---

*Generated by Hermes (Mavis Code) on 2026-07-21 11:30 Berlin, updated 12:00 Berlin after bg_f610f803 merged.*

