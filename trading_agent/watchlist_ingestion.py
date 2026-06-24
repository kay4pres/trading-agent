# TradingView Watchlist Ingestion Script
# Reads Kay's TradingView scanner export, merges with yfinance data, outputs ranked watchlist
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import json

DATA_DIR = Path(r'E:\Me\TradingAgent\data')

# Five Pillars thresholds
PILLARS = {
    'price_min': 2.0,
    'price_max': 20.0,
    'min_gap_pct': 10.0,
    'min_rel_vol': 5.0,
    'max_float': 20_000_000,  # 20M shares
}

def parse_tradingview_export(filepath):
    """
    Parse TradingView scanner CSV export.
    Kay exports columns: Ticker, Price, Change%, Volume, Rel Volume, Float, News, etc.
    Adjust column names based on Kay's actual export format.
    """
    try:
        df = pd.read_csv(filepath)
        print(f'  TradingView export: {len(df)} rows loaded')
        
        # Find ticker column (TradingView usually uses 'Ticker' or 'Symbol')
        ticker_col = None
        for col in ['Ticker', 'Symbol', 'Ticker (Plain)', 'Description']:
            if col in df.columns:
                ticker_col = col
                break
        
        if ticker_col is None:
            print(f'  ⚠ Unknown format. Columns: {list(df.columns)}')
            # Try first column
            ticker_col = df.columns[0]
        
        df = df.rename(columns={ticker_col: 'Ticker'})
        
        # Standardize column names (TradingView export variations)
        col_map = {}
        for col in df.columns:
            lower = col.lower()
            if 'price' in lower or 'last' in lower:
                col_map[col] = 'Price'
            elif 'change' in lower or 'gain' in lower or 'loss' in lower:
                col_map[col] = 'Change'
            elif 'volume' in lower and 'rel' not in lower and 'relative' not in lower:
                col_map[col] = 'Volume'
            elif 'relative' in lower or 'rel vol' in lower or 'rv' in lower:
                col_map[col] = 'RelVolume'
            elif 'float' in lower:
                col_map[col] = 'Float'
            elif 'news' in lower:
                col_map[col] = 'News'
        
        df = df.rename(columns=col_map)
        
        # Ensure Change is numeric (TradingView shows % change)
        if 'Change' in df.columns:
            df['Change'] = df['Change'].astype(str).str.replace('%', '').str.replace('+', '').str.replace(',', '')
            df['Change'] = pd.to_numeric(df['Change'], errors='coerce')
        
        # Ensure numeric columns
        for col in ['Price', 'RelVolume', 'Volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        print(f'  Columns found: {list(df.columns)}')
        return df[['Ticker', 'Price', 'Change', 'RelVolume', 'Float', 'News']] if 'News' in df.columns else df[['Ticker', 'Price', 'Change', 'RelVolume', 'Float']]
    
    except Exception as e:
        print(f'  ⚠ Could not parse TradingView export: {e}')
        return None

def enrich_with_yfinance(df):
    """Add RSI, EMA, gap%, and validate against Five Pillars"""
    enriched = []
    
    for _, row in df.iterrows():
        ticker = row['Ticker']
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period='5d')
            
            if len(hist) < 2:
                print(f'  ⚠ {ticker}: no data')
                continue
            
            close = hist['Close']
            
            # RSI
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = (100 - (100 / (1 + rs))).iloc[-1]
            
            # EMA
            ema9 = close.ewm(span=9).mean().iloc[-1]
            ema20 = close.ewm(span=20).mean().iloc[-1]
            
            # Gap
            today_close = close.iloc[-1]
            yesterday_close = close.iloc[-2]
            gap_pct = ((today_close - yesterday_close) / yesterday_close) * 100
            
            # Volume ratio
            vol_avg = hist['Volume'].rolling(20).mean().iloc[-1]
            vol_now = hist['Volume'].iloc[-1]
            vol_ratio = vol_now / vol_avg if vol_avg > 0 else 0
            
            # Use TradingView data if available, else yfinance
            price = row.get('Price', today_close) if not pd.isna(row.get('Price')) else today_close
            rel_vol = row.get('RelVolume', vol_ratio) if not pd.isna(row.get('RelVolume')) else vol_ratio
            float_shares = row.get('Float', None)
            
            # Five Pillars score
            score = 0
            pillars = []
            reasons = []
            
            if PILLARS['price_min'] <= price <= PILLARS['price_max']:
                score += 1
                pillars.append('P1')
            else:
                reasons.append(f'Price ${price:.2f} out of range')
            
            if abs(gap_pct) >= PILLARS['min_gap_pct']:
                score += 1
                pillars.append('P2')
            elif abs(gap_pct) >= 5:
                score += 0.5
                pillars.append('P2b')
            else:
                reasons.append(f'Gap {gap_pct:.1f}% below threshold')
            
            if rel_vol >= PILLARS['min_rel_vol']:
                score += 1
                pillars.append('P3')
            elif rel_vol >= 2:
                score += 0.5
                pillars.append('P3b')
            
            if rsi > 50 and rsi < 70:
                score += 1
                pillars.append('P4')
            
            if float_shares and float_shares < PILLARS['max_float']:
                score += 1
                pillars.append('P5')
            elif float_shares is None or pd.isna(float_shares):
                # Can't confirm float — neutral
                pillars.append('P5?')
            
            trend = 'BULLISH' if ema9 > ema20 else 'BEARISH'
            
            enriched.append({
                'Ticker': ticker,
                'Price': round(price, 2),
                'GapPct': round(gap_pct, 2),
                'RelVolume': round(rel_vol, 2),
                'RSI': round(rsi, 1),
                'EMA_9': round(ema9, 2),
                'EMA_20': round(ema20, 2),
                'Trend': trend,
                'Float': float_shares,
                'Score': round(score, 1),
                'Pillars': '/'.join(pillars),
                'Notes': '; '.join(reasons) if reasons else 'All pillars met',
            })
            
            print(f'  ✅ {ticker}: Score {score}/5 | Gap {gap_pct:+.1f}% | RSI {rsi:.0f} | Vol {vol_ratio:.1f}x | {trend}')
            
        except Exception as e:
            print(f'  ⚠ {ticker}: {e}')
    
    return pd.DataFrame(enriched)

def rank_signals(df):
    """Rank signals by score, trend alignment, and volume"""
    if df is None or len(df) == 0:
        return None
    
    # Filter: bearish stocks go to bottom
    df['TrendScore'] = df['Trend'].map({'BULLISH': 2, 'BEARISH': 0})
    
    # Sort: score desc, trend desc, rel vol desc
    df = df.sort_values(['Score', 'TrendScore', 'RelVolume'], ascending=[False, False, False])
    
    # Signal label
    def signal_label(row):
        if row['Score'] >= 4 and row['Trend'] == 'BULLISH':
            return '🔥 HIGH CONFIDENCE'
        elif row['Score'] >= 3:
            return '✅ ACTIONABLE'
        elif row['Score'] >= 2:
            return '⚠️ WATCH'
        else:
            return '❌ BELOW THRESHOLD'
    
    df['Signal'] = df.apply(signal_label, axis=1)
    
    return df

def run():
    today = datetime.now().strftime('%Y%m%d')
    tv_export = DATA_DIR / f'tradingview_export.csv'
    
    print('='*70)
    print(f'WATCHLIST INGESTION  |  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('='*70)
    
    # Step 1: Try TradingView export
    if tv_export.exists():
        print(f'\n📥 Step 1: Loading TradingView export...')
        df_tv = parse_tradingview_export(tv_export)
    else:
        print(f'\n⚠ No TradingView export found at {tv_export}')
        print('   Will build watchlist from yfinance only.')
        df_tv = None
    
    # Step 2: Enrich with yfinance
    print(f'\n📊 Step 2: Enriching with yfinance data...')
    if df_tv is not None:
        df = enrich_with_yfinance(df_tv)
    else:
        print('   Skipped — no TV export to enrich')
        df = None
    
    # Step 3: Rank
    print(f'\n🎯 Step 3: Ranking signals...')
    df_ranked = rank_signals(df)
    
    if df_ranked is None or len(df_ranked) == 0:
        print('   No candidates passed Five Pillars filter.')
        return None
    
    # Step 4: Save
    output = DATA_DIR / f'watchlist_{today}.csv'
    df_ranked.to_csv(output, index=False)
    print(f'\n✅ Watchlist saved: {output}')
    
    # Summary
    print('\n' + '='*70)
    print('📋 TODAY\'S WATCHLIST')
    print('='*70)
    
    print(f'\n{"Ticker":<8} {"Price":<8} {"Gap%":<7} {"Vol":<6} {"RSI":<5} {"Trend":<9} {"Score":<6} {"Signal"}')
    print('-'*70)
    
    for _, row in df_ranked.iterrows():
        print(f'{row["Ticker"]:<8} ${row["Price"]:<7.2f} {row["GapPct"]:>+6.1f}% {row["RelVolume"]:<5.1f}x {row["RSI"]:<5.1f} {row["Trend"]:<9} {row["Score"]:<6.1f} {row["Signal"]}')
    
    # Top picks
    top = df_ranked[df_ranked['Score'] >= 3].head(5)
    if len(top) > 0:
        print(f'\n🔥 TOP PICKS:')
        for i, (_, row) in enumerate(top.iterrows(), 1):
            print(f'  {i}. {row["Ticker"]} — {row["Signal"]} | Score {row["Score"]}/5 | {row["Trend"]}')
    
    return df_ranked

if __name__ == '__main__':
    result = run()
