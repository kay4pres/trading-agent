# Quick Multi-Timeframe Analysis
# Checks: Daily, 1H, 15m, 5m, 1m for any ticker
import yfinance as yf
import pandas as pd
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(r'E:\Me\TradingAgent\data')

INTERVALS = {
    'daily': '1d',
    '1hour': '1h',
    '15min': '15m',
    '5min': '5m',
    '1min': '1m',
}

def get_timeframe(ticker, interval, days=30):
    try:
        df = yf.download(ticker, period=f'{days}d', interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except:
        return None

def analyze_timeframe(df, name):
    if df is None or len(df) < 5:
        return None
    
    close = df['Close']
    
    # Trend: EMA alignment
    ema9 = close.ewm(span=9).mean()
    ema20 = close.ewm(span=20).mean()
    trend = 'BULLISH' if ema9.iloc[-1] > ema20.iloc[-1] else 'BEARISH'
    
    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]
    
    # Volume
    vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
    vol_now = df['Volume'].iloc[-1]
    vol_ratio = vol_now / vol_avg if vol_avg > 0 else 0
    
    # Recent change
    recent_change = ((close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100) if len(close) >= 5 else 0
    
    return {
        'name': name,
        'trend': trend,
        'rsi': round(rsi, 1),
        'vol_ratio': round(vol_ratio, 2),
        'recent_change': round(recent_change, 2),
        'last_price': round(close.iloc[-1], 2),
    }

def analyze_stock(ticker):
    print(f'\n{"="*60}')
    print(f'  {ticker}')
    print(f'{"="*60}')
    
    results = {}
    for name, interval in INTERVALS.items():
        # 1m max = 8 days, 5m max = 60 days, rest = 730 days
        if name == '1min':
            days = 7
        elif name == '5min':
            days = 30
        elif name == '15min':
            days = 60
        elif name == '1hour':
            days = 90
        else:
            days = 120
        df = get_timeframe(ticker, interval, days)
        r = analyze_timeframe(df, name)
        if r:
            results[name] = r
            print(f'  {name:<8} | Trend: {r["trend"]:<8} | RSI: {r["rsi"]:<6} | Vol: {r["vol_ratio"]:.1f}x | Chg: {r["recent_change"]:+.1f}%')
    
    # Overall signal
    if 'daily' in results and '1min' in results:
        daily = results['daily']
        intraday = results.get('5min', results.get('1min'))
        
        bullish_count = sum(1 for r in results.values() if r['trend'] == 'BULLISH')
        total = len(results)
        
        print(f'\n  📊 OVERALL: {bullish_count}/{total} timeframes BULLISH')
        
        # Entry check
        if intraday['rsi'] < 70 and intraday['rsi'] > 40:
            print(f'  ✅ RSI in entry zone: {intraday["rsi"]} (40-70 = good)')
        elif intraday['rsi'] >= 70:
            print(f'  ⚠️  RSI overheated: {intraday["rsi"]} (may pull back)')
        
        if daily['trend'] == 'BULLISH':
            print(f'  ✅ Daily trend BULLISH — aligns with intraday')
        else:
            print(f'  🔴 Daily trend BEARISH — reject intraday signals')
    
    return results

if __name__ == '__main__':
    import sys
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ['SOFI', 'AMD', 'GME', 'PLTR', 'RIVN']
    
    print(f'MULTI-TIMEFRAME ANALYSIS | {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    
    for ticker in tickers:
        try:
            analyze_stock(ticker)
        except Exception as e:
            print(f'  ⚠ {ticker}: {e}')
