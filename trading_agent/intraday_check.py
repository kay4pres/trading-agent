# Quick intraday analysis
import yfinance as yf
import pandas as pd
from pathlib import Path

DATA_DIR = Path(r'E:\Me\TradingAgent\data')

print('Downloading SOFI intraday (5-min bars, last 5 days)...')
stock = yf.download('SOFI', period='5d', interval='5m', progress=False)

# Flatten columns if multi-index
if isinstance(stock.columns, pd.MultiIndex):
    stock.columns = stock.columns.get_level_values(0)

print(f'Got {len(stock)} rows')

# Volume analysis
stock['Vol_MA20'] = stock['Volume'].rolling(20).mean()
stock['Vol_Ratio'] = stock['Volume'] / stock['Vol_MA20']

# RSI
delta = stock['Close'].diff()
gain = delta.where(delta > 0, 0).rolling(9).mean()
loss = (-delta.where(delta < 0, 0)).rolling(9).mean()
rs = gain / loss
stock['RSI'] = 100 - (100 / (1 + rs))

print('')
print('INTRADAY ANALYSIS')
print('='*60)

# Count signals
high_vol = (stock['Vol_Ratio'] > 2).sum()
rsi_ok = ((stock['RSI'] > 50) & (stock['RSI'] < 70)).sum()
both = ((stock['Vol_Ratio'] > 2) & (stock['RSI'] > 50) & (stock['RSI'] < 70)).sum()

print(f'Total 5-min bars: {len(stock)}')
print(f'High Volume (2x+): {high_vol} bars ({high_vol/len(stock)*100:.1f}%)')
print(f'RSI 50-70 (good): {rsi_ok} bars ({rsi_ok/len(stock)*100:.1f}%)')
print(f'BOTH high vol + RSI 50-70: {both} bars ({both/len(stock)*100:.1f}%)')

print('')
print('TOP 10 SIGNALS:')
mask = (stock['Vol_Ratio'] > 2) & (stock['RSI'] > 50) & (stock['RSI'] < 70)
signals = stock[mask].head(10)
for idx, row in signals.iterrows():
    print(f'  {idx.strftime("%m/%d %H:%M")} | ${row["Close"]:.2f} | Vol: {row["Vol_Ratio"]:.1f}x | RSI: {row["RSI"]:.1f}')

stock.to_csv(DATA_DIR / 'SOFI_intraday.csv')
print('')
print('Saved to SOFI_intraday.csv')
