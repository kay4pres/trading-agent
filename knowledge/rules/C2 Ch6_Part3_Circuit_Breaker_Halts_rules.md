# Day Trading Strategies — Level 2 & Tape Reading — Extracted Rules
# Source: Part3_Circuit_Breaker_Halts.txt
# Date: 2026-06-29

## RULES EXTRACTED FROM TRANSCRIPT (preliminary)

## Volume Analysis
- Relative Volume (RV): look for 5x+ above average.
- Volume confirmation required for breakouts.

### Volume Patterns (2 mentions)
- Keywords found: relative volume, RV

## Risk Management
- Max loss defined BEFORE entering — never adjust mid-trade.
- Stop placement: based on ATR or recent volatility.
- 1:2 risk/reward minimum; 2:1 target.
- Risk 1-2% of account per trade max.

### Risk Management (1 mentions)
- Keywords found: 2:1

## First Pullback Setup
- Entry: first candle making a NEW HIGH after the pullback.
- Skip if pullback >4 candles or >50% retracement.

### First Pullback (3 mentions)
- Keywords found: pull back, resting, setup

## Order Types
- Market Order: immediate fill, no price guarantee.
- Limit Order: fill at specified price or better.
- Stop Order: triggers market order when price reached.
- Bracket Order: entry + take-profit + stop-loss in one.

### Order Types (1 mentions)
- Keywords found: market order

## Hot Keys & Buttons
- Hot keys: single-key actions for speed (SCR, scale out, reverse).
- Scale out: reduce size as trade moves in your favor.
- Reverse: close and flip position direction.

### Hot Keys (3 mentions)
- Keywords found: hot key, SCR, reverse

## Stock Halts
- LULD (Limit Up / Limit Down): automatic trading pause on rapid moves.
- T1 Halt: 5 min pause; T2 Halt: 10 min pause.
- Resume conditions: price within LULD bands for 15 seconds.
- Ross: never hold through a halt — exit before T1.

### Stock Halts (8 mentions)
- Keywords found: halt, LULD, circuit breaker, Limit Up, Limit Down, resume, halted, T2

## Level 2 & Time & Sales
- Level 2: shows bid/ask depth — MM activity visible.
- Time & Sales (T&S): every print with time/size/price.
- ADFN: alternative data feed, shows dark pool prints.
- Prints: trades happening at specific price levels.

### Level2 (6 mentions)
- Keywords found: level 2, bid, spread, ADFN, MM, maker

## Market Makers & PFOF
- Market Makers (MM): provide liquidity, must maintain fair and orderly markets.
- PFOF: brokers sell order flow to MMs (e.g., Citadel, Virtu).
- Direct Access: route orders directly to exchange, bypass PFOF.
- Internalization: broker fills order internally at NBBO.

### Market Makers (2 mentions)
- Keywords found: market maker, MM

## Stock Types by Float
- Nano Cap: <10M shares float.
- Micro Cap: 10-50M shares.
- Low Float: 50-100M shares.
- Medium Float: 100-200M shares.
- Large Float: >200M shares.
- Small float = bigger % moves, harder to trade.

### Stock Types (1 mentions)
- Keywords found: float

## Trading Platform Setup
- Pattern Day Trader (PDT): >3 day trades in 5 business days with <$25k.
- Routing: SMART routing, IEX routing available on some platforms.
- Clearing: ensure same-day or next-day settlement.

### Trading Platform (3 mentions)
- Keywords found: broker, platform, routing
