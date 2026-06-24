# Trading Agent

AI-powered day trading agent built on Warrior Trading methodology.

## What It Does
- Learns from Warrior Trading course material
- Scans for stocks matching the "Five Pillars" criteria
- Backtests strategies on historical data
- Generates trading signals via Pine Script on TradingView

## Five Pillars of Stock Selection
1. **Price**: $2–$20
2. **Gap Up**: Up ≥10% from yesterday
3. **Volume**: Relative volume > 5x average
4. **Catalyst**: News catalyst present (manual)
5. **Float**: < 20M shares (manual)

## Key Files
- `trading_agent/backtest_engine.py` — Python backtesting engine
- `trading_agent/trader_pine_script_v3.txt` — TradingView Pine Script
- `knowledge/extracted/Chapter*_extracted.txt` — Course transcripts

## Status
- Day 3 of ~33 (deadline July 25)
- Course 1: Day Trading The Basics ✅ COMPLETE
- Course 2: Day Trading Strategies & Scaling — NEXT

## Setup
```bash
pip install yfinance pandas numpy whisper openai ib-insync tradingview-ta
```
