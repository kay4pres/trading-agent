import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

# Finviz screener parameters
# f = filter string: sh_price_2-20 = price $2-20, sh_relvol_o2 = relvol >2, ta_schange_o10 = change >10%
# o = sort: -change = by change descending
# v = view: 111 = overview

def scrape_finviz_screener():
    url = 'https://finviz.com/screener.ashx'
    params = {
        'v': '111',
        'f': 'sh_price_2-20,sh_relvol_o2,ta_schange_o10',  # Matches Five Pillars
        'o': '-change'
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print('Fetching Finviz screener...')
    r = requests.get(url, params=params, headers=headers, timeout=15)
    
    if r.status_code != 200:
        print(f'Error: {r.status_code}')
        return None
    
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Find the results table
    table = soup.find('table', {'id': 'screener-content'})
    if not table:
        print('Could not find screener table')
        print('Trying alternate...')
        tables = soup.find_all('table')
        for t in tables:
            headers_row = t.find('tr')
            if headers_row and 'Ticker' in headers_row.text:
                table = t
                break
    
    if not table:
        print('No table found')
        return None
    
    # Parse table
    rows = table.find_all('tr')
    data = []
    
    for row in rows:
        cols = row.find_all('td')
        if len(cols) > 1:
            # Skip header rows (have no links)
            ticker_link = row.find('a')
            if ticker_link and '/quote.ashx' in str(ticker_link):
                ticker = ticker_link.text
                row_data = [td.text.strip() for td in cols]
                data.append(row_data)
    
    if not data:
        print('No data rows found')
        return None
    
    # Get headers from first data row count
    print(f'Found {len(data)} stocks')
    
    # Standard Finviz overview columns
    columns = ['No.', 'Ticker', 'Company', 'Sector', 'Industry', 'Country', 
               'Market Cap', 'P/E', 'Price', 'Change', 'Volume']
    
    # Trim if more/less columns
    df = pd.DataFrame(data)
    if len(df.columns) < len(columns):
        columns = columns[:len(df.columns)]
    df.columns = columns[:len(df.columns)]
    
    # Parse numeric columns
    df['Price'] = pd.to_numeric(df['Price'].str.replace('$', ''), errors='coerce')
    df['Change'] = pd.to_numeric(df['Change'].str.replace('%', '').str.replace('+', ''), errors='coerce')
    df['Volume'] = pd.to_numeric(df['Volume'].str.replace(',', ''), errors='coerce')
    
    print(df[['Ticker', 'Price', 'Change', 'Volume']].head(10))
    return df

if __name__ == '__main__':
    result = scrape_finviz_screener()
    if result is not None:
        result.to_csv(r'E:\Me\TradingAgent\data\finviz_screener.csv', index=False)
        print('Saved to finviz_screener.csv')
