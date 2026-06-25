# Trading Agent Backtesting Engine
# Own system - no TradingView dependency
# Designed to integrate with real trading pipeline

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path

# === CONFIGURATION ===
DATA_DIR = Path(r'E:\Me\TradingAgent\data')
DATA_DIR.mkdir(exist_ok=True)

# === FIVE PILLARS PARAMETERS ===
# ⚠️ FIXED 2026-06-25: Was requiring 5/5 score + EMA cross-up = almost no trades
# Relaxed to match the intraday scanner's signal quality
PILLARS = {
    'price_min': 2.0,
    'price_max': 50.0,
    'min_gain_percent': 3.0,      # FIXED: was 5.0 — SOFI regularly gaps 3-4%, 5% too restrictive
    'volume_multiplier': 2.0,     # 2x average volume
    'adx_threshold': 15.0,       # FIXED: was 20.0 — lowered for more signal capture
    'rsi_length': 14,
    'rsi_overbought': 70,
    'rsi_oversold': 30,
}

# === DATA FUNCTIONS ===
def download_stock_data(ticker, period='3mo'):
    """Download historical data from Yahoo Finance"""
    print(f"📥 Downloading {ticker} data...")
    stock = yf.Ticker(ticker)
    df = stock.history(period=period)
    df.to_csv(DATA_DIR / f'{ticker}.csv')
    print(f"✅ Saved {len(df)} rows to {ticker}.csv")
    return df

def calculate_indicators(df):
    """Calculate RSI, ADX, Volume, etc."""
    # RSI
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=PILLARS['rsi_length']).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=PILLARS['rsi_length']).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # ADX (simplified - using momentum as proxy)
    df['High_Low'] = df['High'] - df['Low']
    df['High_Close'] = abs(df['High'] - df['Close'].shift())
    df['Low_Close'] = abs(df['Low'] - df['Close'].shift())
    df['TR'] = df[['High_Low', 'High_Close', 'Low_Close']].max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()
    
    # +DM and -DM
    df['High_Diff'] = df['High'].diff()
    df['Low_Diff'] = -df['Low'].diff()
    df['+DM'] = df['High_Diff'].where((df['High_Diff'] > df['Low_Diff']) & (df['High_Diff'] > 0), 0)
    df['-DM'] = df['Low_Diff'].where((df['Low_Diff'] > df['High_Diff']) & (df['Low_Diff'] > 0), 0)
    
    # ADX
    df['+DI'] = (df['+DM'].rolling(window=14).mean() / df['ATR']) * 100
    df['-DI'] = (df['-DM'].rolling(window=14).mean() / df['ATR']) * 100
    dx = (abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI'])) * 100
    df['ADX'] = dx.rolling(window=14).mean()
    
    # Volume
    df['Volume_MA20'] = df['Volume'].rolling(window=20).mean()
    df['Volume_Ratio'] = df['Volume'] / df['Volume_MA20']
    
    # % Gain from previous close
    df['Percent_Gain'] = ((df['Close'] - df['Close'].shift(1)) / df['Close'].shift(1)) * 100
    
    # Moving Averages
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
    
    return df

# === FIVE PILLARS SCORING SYSTEM ===
def score_five_pillars(row):
    """
    Score each pillar 0-1, total score = 0-5
    Score 4+ = Strong candidate
    Score 3 = Moderate candidate
    Score 2 = Weak candidate
    """
    score = 0
    details = {}
    
    # Pillar 1: Price $2-$50 = 1 point
    if PILLARS['price_min'] <= row['Close'] <= PILLARS['price_max']:
        score += 1
        details['P1'] = '✅'
    else:
        details['P1'] = '❌'
    
    # Pillar 2: Up % from yesterday - bonus for higher %
    if row['Percent_Gain'] >= PILLARS['min_gain_percent']:
        score += 1
        if row['Percent_Gain'] >= 15:
            details['P2'] = '🔥🔥'
        else:
            details['P2'] = '✅'
    else:
        details['P2'] = '❌'
    
    # Pillar 3: Relative Volume - bonus for much higher volume
    if row['Volume_Ratio'] >= PILLARS['volume_multiplier']:
        score += 1
        if row['Volume_Ratio'] >= 5:
            details['P3'] = '🔥🔥'
        else:
            details['P3'] = '✅'
    else:
        details['P3'] = '❌'
    
    # Pillar 4: Momentum (RSI > 50, ADX rising)
    if row['RSI'] > 50 and row['ADX'] > PILLARS['adx_threshold']:
        score += 1
        details['P4'] = '✅'
    else:
        details['P4'] = '❌'
    
    # Pillar 5: Pullback (price near EMA but above it)
    if row['Close'] > row['EMA_20'] and (row['Low'] <= row['EMA_20'] * 1.02):
        score += 1
        details['P5'] = '✅'
    else:
        details['P5'] = '❌'
    
    return score, details

# === BACKTESTING ENGINE ===
def backtest_strategy(df, ticker, initial_capital=10000):
    """Run backtest on historical data using scoring system"""
    print(f"\n{'='*60}")
    print(f"BACKTESTING: {ticker} - SCORING SYSTEM")
    print(f"{'='*60}")
    
    df = calculate_indicators(df)
    
    # Initialize tracking
    capital = initial_capital
    position = 0
    position_price = 0
    trades = []
    
    # Score statistics
    score_distribution = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    score_stats = {'avg_score': [], 'strong_days': 0, 'moderate_days': 0}
    
    for i, (date, row) in enumerate(df.iterrows()):
        if i < 30:  # Skip first 30 days (not enough data)
            continue
        
        # Get pillar score
        score, details = score_five_pillars(row)
        score_distribution[score] += 1
        score_stats['avg_score'].append(score)
        
        if score >= 4:
            score_stats['strong_days'] += 1
        elif score >= 3:
            score_stats['moderate_days'] += 1
        
        # Entry signal: Score 3+ (relaxed from 4+ — EMA cross requirement removed)
        # First Pullback pattern: pullback to EMA + first candle making new highs
        # Relaxed 2026-06-25: was requiring score>=4 AND ma_cross_up — too restrictive
        in_pullback = (row['Close'] <= row['EMA_9'] * 1.02)  # Within 2% of EMA 9

        # Exit signal
        rsi_overbought = row['RSI'] > PILLARS['rsi_overbought']
        price_target_hit = row['Close'] >= row['EMA_9'] * 1.02  # +2% from EMA = target
        
        # === EXECUTE TRADES ===
        # FIXED: score >= 3 + in pullback (was score >= 4 + ma_cross_up)
        if score >= 3 and in_pullback and position == 0:
            # BUY SIGNAL - Strong candidate
            shares = int(capital * 0.1 / row['Close'])
            cost = shares * row['Close']
            position = shares
            position_price = row['Close']
            capital -= cost
            
            pillar_str = ' '.join([details[k] for k in ['P1', 'P2', 'P3', 'P4', 'P5']])
            
            trades.append({
                'date': date,
                'type': 'BUY',
                'price': row['Close'],
                'shares': shares,
                'value': cost,
                'score': score,
                'pillars': pillar_str,
                'rsi': row['RSI'],
                'volume_ratio': row['Volume_Ratio'],
                'percent_gain': row['Percent_Gain'],
            })
            print(f"🟢 BUY  {date.date()} | ${row['Close']:.2f} | Score: {score}/5 | {pillar_str}")
        
        elif position > 0 and (price_target_hit or rsi_overbought):
            # SELL SIGNAL
            revenue = position * row['Close']
            pnl = revenue - (position * position_price)
            capital += revenue
            
            trades.append({
                'date': date,
                'type': 'SELL',
                'price': row['Close'],
                'shares': position,
                'value': revenue,
                'pnl': pnl,
                'pnl_pct': (pnl / (position * position_price)) * 100 if position > 0 else 0,
                'rsi': row['RSI'],
            })
            print(f"🔴 SELL {date.date()} | ${row['Close']:.2f} | P&L: ${pnl:.2f}")
            position = 0
            position_price = 0
    
    # === GENERATE REPORT ===
    print(f"\n{'='*60}")
    print(f"BACKTEST RESULTS: {ticker}")
    print(f"{'='*60}")
    
    # Score distribution
    total_days = len(df) - 30
    print(f"\n📊 SCORE DISTRIBUTION (out of {total_days} trading days):")
    print(f"   Score 5 (🔥🔥🔥): {score_distribution[5]} days ({score_distribution[5]/total_days*100:.1f}%)")
    print(f"   Score 4 (🔥🔥):  {score_distribution[4]} days ({score_distribution[4]/total_days*100:.1f}%)")
    print(f"   Score 3 (🔥):     {score_distribution[3]} days ({score_distribution[3]/total_days*100:.1f}%)")
    print(f"   Score 2:         {score_distribution[2]} days ({score_distribution[2]/total_days*100:.1f}%)")
    print(f"   Score 1:         {score_distribution[1]} days ({score_distribution[1]/total_days*100:.1f}%)")
    print(f"   Score 0:         {score_distribution[0]} days ({score_distribution[0]/total_days*100:.1f}%)")
    print(f"   ─────────────────────────────────────────")
    print(f"   STRONG (4-5):     {score_stats['strong_days']} days ({score_stats['strong_days']/total_days*100:.1f}%)")
    print(f"   MODERATE (3):    {score_stats['moderate_days']} days ({score_stats['moderate_days']/total_days*100:.1f}%)")
    print(f"   Avg Score:       {np.mean(score_stats['avg_score']):.1f}")
    
    # Trade statistics
    buy_trades = [t for t in trades if t['type'] == 'BUY']
    sell_trades = [t for t in trades if t['type'] == 'SELL']
    
    print(f"\n📈 TRADE STATISTICS:")
    print(f"   Total Trades: {len(buy_trades)}")
    if sell_trades:
        winners = [t for t in sell_trades if t.get('pnl', 0) > 0]
        win_rate = len(winners) / len(sell_trades) * 100 if sell_trades else 0
        print(f"   Win Rate: {win_rate:.1f}%")
        pnls = [t['pnl'] for t in sell_trades]
        print(f"   Total P&L: ${sum(pnls):.2f}")
        print(f"   Best Trade: ${max(pnls):.2f}")
        print(f"   Worst Trade: ${min(pnls):.2f}")
        print(f"   Avg Trade: ${np.mean(pnls):.2f}")
    else:
        print(f"   Win Rate: N/A (no closed trades)")
    
    # Final equity
    final_equity = capital + (position * df['Close'].iloc[-1]) if position > 0 else capital
    total_return = (final_equity - initial_capital) / initial_capital * 100
    
    print(f"\n💰 FINAL RESULTS:")
    print(f"   Starting Capital: ${initial_capital:,.2f}")
    print(f"   Final Equity: ${final_equity:,.2f}")
    print(f"   Total Return: {total_return:.2f}%")
    
    # Save to file
    results = {
        'ticker': ticker,
        'period': str(df.index[0].date()) + ' to ' + str(df.index[-1].date()),
        'initial_capital': initial_capital,
        'final_equity': final_equity,
        'total_return_pct': total_return,
        'total_trades': len(buy_trades),
        'score_distribution': score_distribution,
        'score_stats': {
            'strong_days': score_stats['strong_days'],
            'moderate_days': score_stats['moderate_days'],
            'avg_score': np.mean(score_stats['avg_score']),
        },
        'trades': trades,
    }
    
    with open(DATA_DIR / f'{ticker}_backtest.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n✅ Results saved to {DATA_DIR / f'{ticker}_backtest.json'}")
    
    return results

# === MAIN ===
if __name__ == "__main__":
    import sys
    
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SOFI"
    period = sys.argv[2] if len(sys.argv) > 2 else "3mo"
    
    # Download data
    df = download_stock_data(ticker, period)
    
    # Run backtest
    results = backtest_strategy(df, ticker)
