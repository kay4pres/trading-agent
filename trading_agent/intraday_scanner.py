# Multi-Stock Intraday Scanner & Signal Ranker
# Scans gap-up stocks, scores 5-min bars, ranks actionable signals
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
import json
import os

# Config — UTA/Docker: TRADING_DATA_DIR env var; Local: E:\Me\TradingAgent\data
_DATA_ROOT = os.environ.get('TRADING_DATA_DIR', '').strip()
DATA_DIR = Path(_DATA_ROOT) if _DATA_ROOT else Path(r'E:\Me\TradingAgent\data')
DATA_DIR.mkdir(parents=True, exist_ok=True)
WATCHLIST_DIR = DATA_DIR / 'watchlists'
WATCHLIST_DIR.mkdir(parents=True, exist_ok=True)

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

# === POSITIONS GUARD — skip alerts on stocks we already hold ===
POSITIONS_FILE = DATA_DIR / 'positions.json'

def get_open_symbols():
    """Return set of symbols currently in an open position."""
    if not POSITIONS_FILE.exists():
        return set()
    try:
        with open(POSITIONS_FILE) as f:
            state = json.load(f)
        return {
            sym for sym, pos in state.get("positions", {}).items()
            if pos.get("status") == "OPEN"
        }
    except Exception:
        return set()

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
    FIXED: Use INTRADAY HIGH of today's session vs yesterday's daily close.
    yfinance's "daily close" during market hours = current pullback level, not the gap.
    Using intraday high captures the real gap-up even if price has pulled back.
    """
    stocks = []
    market_open_flag = is_market_open()
    today_actual = datetime.now().date()
    yesterday = today_actual - timedelta(days=1)

    for ticker in WATCHLIST:
        try:
            # Get yesterday's daily close (the true reference for gap calculation)
            daily = yf.download(ticker, period='3d', interval='1d', progress=False)
            if isinstance(daily.columns, pd.MultiIndex):
                daily.columns = daily.columns.get_level_values(0)
            if len(daily) < 2:
                continue
            # Find the bar closest to yesterday's date
            daily = daily[daily.index.date <= today_actual]  # only today and earlier
            if len(daily) < 2:
                continue
            yesterday_close = daily['Close'].iloc[-2]  # second-to-last daily bar

            # Get today's intraday bars — use HIGH for gap detection (captures the real gap)
            intraday = yf.download(ticker, period='5d', interval='5m', progress=False)
            if isinstance(intraday.columns, pd.MultiIndex):
                intraday.columns = intraday.columns.get_level_values(0)
            if len(intraday) < 5:
                continue

            # Get today's intraday bars (yfinance labels today's session with today's date or yesterday)
            today_intraday = intraday[intraday.index.date == today_actual]
            if len(today_intraday) == 0:
                # Fallback: use bars labeled as yesterday (yfinance quirk — today's session labeled as yesterday)
                today_intraday = intraday[intraday.index.date == yesterday]
            if len(today_intraday) == 0:
                continue

            # Use intraday HIGH as today's "gap price" — captures real gap even after pullback
            today_gap_price = today_intraday['High'].max()
            # Use intraday CLOSE as current price (where price is now after pullback)
            today_close = today_intraday['Close'].iloc[-1]

            gap_pct = ((today_gap_price - yesterday_close) / yesterday_close) * 100

            # During market hours: scan everything that's up from yesterday
            # Before market: only scan actual gap-ups
            if market_open_flag:
                if gap_pct >= INTRADAY_PARAMS['min_gap_pct']:
                    stocks.append({
                        'ticker': ticker,
                        'today_close': today_close,
                        'yesterday_close': yesterday_close,
                        'gap_pct': gap_pct,
                        'status': 'GAP_UP'
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

def first_pullback_filter(row, today_bars, atr):
    """
    Ross's First Pullback filter — is this a VALID first pullback entry?

    Rules:
    1. Pullback depth: stock must be 1.5×–3× ATR below intraday high.
       Below 1.5× ATR = pullback not deep enough (no entry discount).
       Above 3× ATR = pullback too deep, ATR stop too tight, skip.
    2. Recovery: price above EMA_9 (not still falling).
    3. RSI recovering: 40–70 (not oversold panic, not overheated).
    4. NOT extended: pullback must be ≤ 30% of the gap from yesterday.

    Returns (is_valid, reason_str).
    """
    intraday_high = today_bars['High'].max()
    intraday_low  = today_bars['Low'].min()

    # Pullback depth in $ and as % of gap
    pullback_dollar = intraday_high - row['Close']
    pullback_pct    = pullback_dollar / intraday_high if intraday_high > 0 else 0

    today_gap = intraday_high  # today's high from yesterday's close (approx)
    if atr <= 0:
        return False, "no ATR data"

    # Rule 1: pullback must be 1.5×–3× ATR (enough discount, not too deep)
    if pullback_dollar < 1.5 * atr:
        return False, f"pullback too shallow ({pullback_dollar:.2f} < 1.5× ATR {atr:.2f})"
    if pullback_dollar > 3.0 * atr:
        return False, f"pullback too deep ({pullback_dollar:.2f} > 3× ATR {atr:.2f})"

    # Rule 2: price recovering — above EMA_9
    if row['Close'] <= row['EMA_9']:
        return False, "price below EMA_9 (still falling)"

    # Rule 3: RSI recovering, not overheated
    rsi = row.get('RSI', 50)
    if rsi < 40 or rsi > 75:
        return False, f"RSI {rsi:.0f} out of recovery range (40–75)"

    # Rule 4: not extended — pullback ≤ 30% of gap
    gap_range = intraday_high - intraday_low
    if gap_range > 0 and pullback_pct > 0.30:
        return False, f"pullback {pullback_pct:.1%} > 30% of intraday range"

    return True, "valid first pullback"


def scan_intraday(ticker, gap_pct):
    """Scan 5-min bars for a single stock"""
    try:
        stock = yf.download(ticker, period=LOOKBACK_PERIOD, interval=INTERVAL, progress=False)
        if isinstance(stock.columns, pd.MultiIndex):
            stock.columns = stock.columns.get_level_values(0)

        if len(stock) < 30:
            return []

        # === FRESHNESS GATE — skip if last bar is > 30 min old during market hours ===
        # yfinance returns stale data during active trading; detect and skip silently
        if len(stock) > 0:
            last_bar_time = stock.index[-1]
            # Normalize: yfinance bars are UTC, make both naive for comparison
            if last_bar_time.tzinfo is not None:
                last_bar_time = last_bar_time.replace(tzinfo=None)
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)  # UTC naive, matches yfinance bar format
            market_open_today = datetime.combine(now_utc.date(), time(14, 30))   # 14:30 UTC = 9:30 ET
            market_close_today = datetime.combine(now_utc.date(), time(21, 0))    # 21:00 UTC = 4:00 ET
            # Only enforce freshness gate during market hours
            if market_open_today <= now_utc <= market_close_today:
                age_minutes = (now_utc - last_bar_time).total_seconds() / 60
                if age_minutes > 30:
                    # Last bar is > 30 min old — likely yfinance cache lag, skip ticker
                    return []

        stock = calculate_intraday_indicators(stock)

        signals = []
        for idx, row in stock.iterrows():
            if pd.isna(row['RSI']) or pd.isna(row['Vol_Ratio']):
                continue

            score, details = score_bar(row, ticker, gap_pct)

            if score >= INTRADAY_PARAMS['score_threshold']:
                bar_idx = stock.index.get_loc(idx)

                # Need at least 10 bars of history for meaningful ATR
                if bar_idx < 10:
                    continue

                # yfinance labels the current session's bars with yesterday's date
                # (e.g. July 2 trading session bars labeled as 07/01 until midnight ET crosses)
                # Accept bars from today's calendar date OR yesterday's session
                actual_today = datetime.now().date()
                yesterday = actual_today - timedelta(days=1)
                bar_cal_date = idx.date()
                if bar_cal_date != actual_today and bar_cal_date != yesterday:
                    continue
                # Use the bar's labeled date for intraday high/low (consistent with yfinance)
                today_bars = stock[stock.index.date == bar_cal_date]

                if len(today_bars) == 0:
                    continue

                atr = row.get('ATR', 0)
                if atr <= 0:
                    continue

                # Compute intraday high for pullback context
                intraday_high = today_bars['High'].max()
                intraday_low  = today_bars['Low'].min()

                # First Pullback filter — replaces hardcoded % check
                is_valid, reason = first_pullback_filter(row, today_bars, atr)
                if not is_valid:
                    continue

                signals.append({
                    'datetime': idx,
                    'ticker': ticker,
                    'price': row['Close'],
                    'score': score,
                    'rsi': row['RSI'],
                    'volume_ratio': row['Vol_Ratio'],
                    'gap_pct': gap_pct,
                    'atr': atr,
                    'ema_9': row['EMA_9'],
                    'pillars': details,
                    'pattern': 'FIRST_PULLBACK',
                    'intraday_high': round(float(intraday_high), 3),
                    'pullback_dollar': round(float(intraday_high) - row['Close'], 3),
                    'pullback_atr_ratio': round((float(intraday_high) - row['Close']) / atr, 1) if atr > 0 else 0,
                    'intraday_low': round(float(intraday_low), 3),
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
    
    # Step 3: Filter out stocks we already hold, then rank signals
    print(f'\n📊 Step 3: Ranking {len(all_signals)} total signals...')

    held = get_open_symbols()
    if held:
        before = len(all_signals)
        all_signals = [s for s in all_signals if s['ticker'] not in held]
        print(f'  [SKIP] Already in position: {held} — filtered {before - len(all_signals)} signal(s)')

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
