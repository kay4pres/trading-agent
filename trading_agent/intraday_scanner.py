# Multi-Stock Intraday Scanner & Signal Ranker
# Scans gap-up stocks, scores 5-min bars, ranks actionable signals
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time
from pathlib import Path
import json

DATA_DIR = Path(r'E:\Me\TradingAgent\data')
WATCHLIST_DIR = DATA_DIR / 'watchlists'
DATA_DIR.mkdir(exist_ok=True)

# === CONFIG ===

def load_todays_watchlist():
    """Load today's watchlist CSV if it exists, otherwise fall back to hardcoded list."""
    try:
        today_str = datetime.now().strftime('%Y%m%d')
        candidates = sorted(WATCHLIST_DIR.glob(f'watchlist_{today_str}.csv'))
        if candidates:
            df = pd.read_csv(candidates[-1])
            tickers = df['symbol'].dropna().tolist()
            print(f'Loaded {len(tickers)} stocks from {candidates[-1].name}')
            return tickers
    except Exception as e:
        print(f'Could not load watchlist: {e}')
    
    # Fallback
    return [
        'SOFI', 'AMD', 'GME', 'RIVN', 'PLTR', 'NVDA', 'TSLA',
        'NIO', 'SNAP', 'ROKU', 'COIN', 'MSTR', 'SMCI', 'DXYN'
    ]

WATCHLIST = load_todays_watchlist()

# 5-Minute bars config
INTERVAL = '5m'
LOOKBACK_PERIOD = '5d'  # Last 5 trading days

# Five Pillars (relaxed for intraday)
INTRADAY_PARAMS = {
    'price_min': 2.0,
    'price_max': 50.0,
    'volume_ratio_min': 2.0,    # 2x avg volume
    'rsi_min': 50,
    'rsi_max': 70,              # Not overheated
    'ema_tight_pct': 0.02,      # Within 2% of EMA = near support
    'min_gap_pct': 5.0,         # Gap up from yesterday
    'score_threshold': 3,       # Score 3+ = actionable
}

def is_market_open():
    """Check if US market is currently open (simplified)"""
    now = datetime.now()
    # EST: UTC-5 (or UTC-4 during DST)
    # NYSE hours: 9:30 - 16:00 EST
    market_open = time(14, 30)   # 14:30 UTC = 9:30 EST
    market_close = time(21, 0)   # 21:00 UTC = 16:00 EST
    current_utc = now.time()
    return market_open <= current_utc <= market_close and now.weekday() < 5

def get_gap_up_stocks():
    """
    Get stocks from watchlist that gapped up today OR are already running.
    FIXED: The gap happened at open — we want stocks that are UP from yesterday
    (they gapped, pulled back, and now might be ready for first pullback entry).
    During market hours, we scan ALL stocks in watchlist.
    """
    stocks = []
    market_open_flag = is_market_open()
    
    for ticker in WATCHLIST:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period='2d')
            if len(hist) < 2:
                continue
            
            today_close = hist['Close'].iloc[-1]
            yesterday_close = hist['Close'].iloc[-2]
            gap_pct = ((today_close - yesterday_close) / yesterday_close) * 100
            
            # Include if: (1) actively gapping NOW, OR (2) already up ≥5% from yesterday (gap happened)
            # During market hours: scan everything that's up from yesterday
            # Before market: only scan actual gap-ups
            if market_open_flag:
                # Market is open — scan ALL stocks that are up from yesterday
                if gap_pct >= INTRADAY_PARAMS['min_gap_pct']:
                    stocks.append({
                        'ticker': ticker,
                        'today_close': today_close,
                        'yesterday_close': yesterday_close,
                        'gap_pct': gap_pct,
                        'status': 'GAP_UP' if market_open_flag else 'PRE_MARKET'
                    })
                elif gap_pct >= 3.0:  # Also include moderately strong stocks
                    stocks.append({
                        'ticker': ticker,
                        'today_close': today_close,
                        'yesterday_close': yesterday_close,
                        'gap_pct': gap_pct,
                        'status': 'RUNNING'
                    })
            else:
                # Pre-market — only actual gap-ups
                if gap_pct >= INTRADAY_PARAMS['min_gap_pct']:
                    stocks.append({
                        'ticker': ticker,
                        'today_close': today_close,
                        'yesterday_close': yesterday_close,
                        'gap_pct': gap_pct,
                        'status': 'PRE_MARKET_GAP'
                    })
        except Exception as e:
            print(f'  ⚠ {ticker}: {e}')
    
    return stocks

def calculate_intraday_indicators(df):
    """Calculate RSI, EMA, Volume ratio for 5-min bars"""
    # RSI (9-period for faster response)
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(9).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(9).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # EMAs
    df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # Volume
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    df['Vol_Ratio'] = df['Volume'] / df['Vol_MA20']
    
    # ATR for context
    high_low = df['High'] - df['Low']
    high_close = abs(df['High'] - df['Close'].shift())
    low_close = abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()
    
    return df

def score_bar(row, ticker, gap_pct):
    """
    Score each 5-min bar 0-5 based on Five Pillars adapted for intraday
    Returns: (score, details_dict)
    """
    score = 0
    details = {}
    
    # P1: Price in range
    if INTRADAY_PARAMS['price_min'] <= row['Close'] <= INTRADAY_PARAMS['price_max']:
        score += 1
        details['P1'] = '✅'
    else:
        details['P1'] = '❌'
    
    # P2: Gap up % (already confirmed gap-up stock)
    # FIXED: use min_gap_pct config instead of hardcoded 10%
    if gap_pct >= 10:
        score += 1
        details['P2'] = '🔥'
    elif gap_pct >= INTRADAY_PARAMS['min_gap_pct']:
        score += 1  # was 0.5 — full point for meeting threshold
        details['P2'] = '✅'
    else:
        details['P2'] = '❌'
    
    # P3: Volume surge
    if row['Vol_Ratio'] >= 3:
        score += 1
        details['P3'] = '🔥'
    elif row['Vol_Ratio'] >= INTRADAY_PARAMS['volume_ratio_min']:
        score += 1
        details['P3'] = '✅'
    else:
        details['P3'] = '❌'
    
    # P4: RSI in sweet spot (momentum)
    if INTRADAY_PARAMS['rsi_min'] <= row['RSI'] <= INTRADAY_PARAMS['rsi_max']:
        score += 1
        details['P4'] = '✅'
    else:
        details['P4'] = '❌'
    
    # P5: Price near EMA (support test / pullback)
    ema_dist_pct = abs(row['Close'] - row['EMA_9']) / row['EMA_9']
    if ema_dist_pct <= INTRADAY_PARAMS['ema_tight_pct']:
        score += 1
        details['P5'] = '✅'  # Near EMA = potential pullback entry
    else:
        details['P5'] = '○'
    
    return score, details

def scan_intraday(ticker, gap_pct):
    """Scan 5-min bars for a single stock"""
    try:
        stock = yf.download(ticker, period=LOOKBACK_PERIOD, interval=INTERVAL, progress=False)
        if isinstance(stock.columns, pd.MultiIndex):
            stock.columns = stock.columns.get_level_values(0)
        
        if len(stock) < 30:
            return []
        
        stock = calculate_intraday_indicators(stock)
        
        signals = []
        for idx, row in stock.iterrows():
            if pd.isna(row['RSI']) or pd.isna(row['Vol_Ratio']):
                continue
            
            score, details = score_bar(row, ticker, gap_pct)
            
            if score >= INTRADAY_PARAMS['score_threshold']:
                # Check for FIRST PULLBACK pattern:
                # 1) Find today's opening bar (first bar of current trading day)
                # 2) Track intraday high since open
                # 3) Flag when price pulls back ≥3% from intraday high, then starts recovering
                bar_idx = stock.index.get_loc(idx)
                
                # Need at least 10 bars of history
                if bar_idx < 10:
                    continue
                
                # Identify today's bars (same date as current bar)
                current_date = idx.date()
                today_bars = stock[stock.index.date == current_date]
                
                if len(today_bars) == 0:
                    continue
                
                # Intraday high since today's open
                intraday_high = today_bars['High'].max()
                
                # Pullback: price has pulled back ≥3% from intraday high, now pushing up
                pullback_pct = (intraday_high - row['Close']) / intraday_high
                is_pullback = (pullback_pct >= 0.03) and (pullback_pct <= 0.12)
                
                # Is price recovering? (above EMA, RSI in range)
                ema_cross = row['Close'] > row['EMA_9']
                
                if is_pullback and ema_cross:
                    signals.append({
                        'datetime': idx,
                        'ticker': ticker,
                        'price': row['Close'],
                        'score': score,
                        'rsi': row['RSI'],
                        'volume_ratio': row['Vol_Ratio'],
                        'gap_pct': gap_pct,
                        'atr': row.get('ATR', 0),
                        'ema_9': row['EMA_9'],
                        'pillars': details,
                        'pattern': 'FIRST_PULLBACK',
                    })
        
        return signals
    
    except Exception as e:
        print(f'  ⚠ {ticker}: {e}')
        return []

def run_pipeline():
    """Main pipeline: find gap-ups, scan intraday, rank signals"""
    print('='*70)
    print(f'INTRADAY SIGNAL PIPELINE  |  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('='*70)
    
    # Step 1: Find gap-up stocks
    print('\n📊 Step 1: Scanning watchlist for gap-ups...')
    gap_stocks = get_gap_up_stocks()
    
    if not gap_stocks:
        print('  No gap-up stocks found in watchlist. Market might be closed or no setups.')
        return []
    
    print(f'  Found {len(gap_stocks)} candidate stocks:')
    for s in sorted(gap_stocks, key=lambda x: x['gap_pct'], reverse=True):
        status = s.get('status', '?')
        print(f'    {s["ticker"]}: +{s["gap_pct"]:.1f}% (${s["today_close"]:.2f}) [{status}]')
    
    # Step 2: Scan each gap-up stock for 5-min signals
    print('\n📊 Step 2: Scanning 5-min bars for signals...')
    all_signals = []
    
    for stock in gap_stocks:
        ticker = stock['ticker']
        gap_pct = stock['gap_pct']
        print(f'  Scanning {ticker}...')
        signals = scan_intraday(ticker, gap_pct)
        all_signals.extend(signals)
        if signals:
            print(f'    Found {len(signals)} signal(s)!')
    
    # Step 3: Rank signals
    print(f'\n📊 Step 3: Ranking {len(all_signals)} total signals...')
    
    if not all_signals:
        print('  No signals meeting threshold. Pipeline complete.')
        return []
    
    # Sort by score descending, then by volume ratio
    ranked = sorted(all_signals, key=lambda x: (x['score'], x['volume_ratio']), reverse=True)
    
    # Step 4: Output
    print('\n' + '='*70)
    print('🔥 TOP SIGNALS — READY TO WATCH')
    print('='*70)
    
    print(f'\n{"Rank":<5} {"Ticker":<8} {"Time":<12} {"Price":<10} {"Score":<7} {"RSI":<6} {"Vol":<6} {"Gap%":<6}')
    print('-'*70)
    
    for i, sig in enumerate(ranked[:10], 1):
        dt = sig['datetime'].strftime('%m/%d %H:%M')
        pillars = ''.join([sig['pillars'][k] for k in sorted(sig['pillars'].keys())])
        print(f'{i:<5} {sig["ticker"]:<8} {dt:<12} ${sig["price"]:<9.2f} {sig["score"]:<7.1f} {sig["rsi"]:<6.1f} {sig["volume_ratio"]:<6.1f}x {sig["gap_pct"]:<6.1f}%')
    
    print(f'\n  Pattern: FIRST_PULLBACK')
    print(f'  Target: +$0.20/share | Stop: $0.10-0.15/share')
    print(f'  Risk/Reward: 2:1 minimum')
    
    # Save results
    results = {
        'run_time': datetime.now().isoformat(),
        'gap_stocks': gap_stocks,
        'total_signals': len(all_signals),
        'ranked_signals': ranked[:10],
    }
    
    output_path = DATA_DIR / f'signals_{datetime.now().strftime("%Y%m%d_%H%M")}.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f'\n✅ Results saved: {output_path}')
    
    return ranked

if __name__ == '__main__':
    import sys
    
    # Optional: override watchlist from CLI
    if len(sys.argv) > 1:
        WATCHLIST.clear()
        WATCHLIST.extend(sys.argv[1].split(','))
        print(f'Scanning custom watchlist: {WATCHLIST}')
    
    signals = run_pipeline()
