r"""
tradingview_connector.py
========================
Richard's direct link to TradingView Premium API.
Fetches Ross-style setups (price $2-20, gap >=10%, RV >=5x) with zero manual steps.

Token: E:\Me\TradingAgent\config\tv_session.enc (PowerShell SecureString, DPAPI)
"""

import subprocess
import pandas as pd
from pathlib import Path
from datetime import date
from typing import List, Dict, Any, Optional
import sys

# ── Token decryption ────────────────────────────────────────────────────────────
# Priority: Docker mount (/app/config) → Kay's host machine (E:\Me\TradingAgent\)
_TOKEN_PATHS = [
    # Docker container mount (./config:/app/config in docker-compose)
    Path('/app/config/tv_session.enc'),
    # Kay's Windows host machine
    Path(r'E:\Me\TradingAgent\config\tv_session.enc'),
]
TOKEN_PATH = next((p for p in _TOKEN_PATHS if p.exists()), _TOKEN_PATHS[0])


def _read_token() -> Optional[str]:
    """Decrypt PowerShell SecureString via PowerShell subprocess."""
    if not TOKEN_PATH.exists():
        return None
    try:
        raw = TOKEN_PATH.read_text(encoding='utf-8').strip()
    except Exception:
        return None
    if raw.startswith('\ufeff'):
        raw = raw[1:]
    escaped = raw.replace("'", "''")
    ps = (
        "$b = '%s'; "
        "$s = ConvertTo-SecureString $b; "
        "[System.Runtime.InteropServices.Marshal]::PtrToStringAuto("
        "[System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))"
    ) % escaped
    try:
        result = subprocess.run(
            ['powershell', '-Command', ps],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


# ── TV API ────────────────────────────────────────────────────────────────────

def fetch_ross_universe(min_price: float = 2, max_price: float = 20,
                        min_gap: float = 10, min_rv: float = 5,
                        limit: int = 20) -> pd.DataFrame:
    """
    Fetch Ross-style setups directly from TradingView Premium API.

    Filters: price $2–$20, gap ≥10%, RV ≥5×, US exchanges only.
    Returns a DataFrame with: ticker, short_name, price, gap_pct, rel_vol, volume.
    """
    session_id = _read_token()
    if not session_id:
        print("  [TV] No session cookie found — set tv_session.enc first")
        return pd.DataFrame()

    try:
        from tradingview_screener import Query, col
    except ImportError:
        print("  [TV] tradingview-screener not installed: pip install tradingview-screener")
        return pd.DataFrame()

    cookies = {'sessionid': session_id}

    # US exchanges only (NASDAQ + NYSE = premium Ross territory)
    exchanges = ['NASDAQ', 'NYSE']

    try:
        count, df = (
            Query()
            .select(
                'ticker', 'name', 'close', 'change',
                'volume', 'relative_volume_10d_calc',
                'market_cap_basic', 'exchange'
            )
            .where(
                col('close') > min_price,
                col('close') < max_price,
                col('change') > min_gap,
                col('relative_volume_10d_calc') > min_rv,
            )
            .order_by('relative_volume_10d_calc', ascending=False)
            .limit(limit)
            .get_scanner_data(cookies=cookies)
        )

        if df is None or not hasattr(df, 'shape') or df.shape[0] == 0:
            return pd.DataFrame()

        # Filter to US exchanges
        if 'exchange' in df.columns:
            df = df[df['exchange'].isin(exchanges)].copy()
        else:
            df = df.copy()

        # Remove duplicate columns (TV returns 'ticker' as both select field and index)
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]

        # Normalize ticker — TV returns 'NASDAQ:MIMI', strip prefix
        df['ticker'] = df['ticker'].apply(
            lambda x: x.split(':')[1] if isinstance(x, str) and ':' in x else x
        )
        df = df.rename(columns={
            'change': 'gap_pct',
            'relative_volume_10d_calc': 'rel_vol',
            'name': 'short_name',
        })
        df['gap_pct'] = df['gap_pct'].round(1)
        df['rel_vol'] = df['rel_vol'].round(1)
        df['price'] = df['close'].round(2)
        df['volume'] = df['volume'].astype('int64')

        # Drop duplicate 'ticker' column from select()
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]

        print(f"  [TV] {len(df)} real-time Ross setups fetched")
        return df

    except Exception as e:
        print(f"  [TV] API error: {e}")
        return pd.DataFrame()


def tv_to_signal_rows(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Convert TV DataFrame rows into the same dict format that
    load_tradingview_csv() produces (for seamless pipeline integration).
    """
    rows = []
    for _, row in df.iterrows():
        rows.append({
            'symbol':     str(row.get('ticker', '')).strip(),
            'short_name': str(row.get('short_name', '')),
            'price':      float(row.get('price', 0)),
            'gap_pct':    float(row.get('gap_pct', 0)),
            'rel_vol':    float(row.get('rel_vol', 0)),
            'volume':     int(row.get('volume', 0)),
            'tv_row':     row.to_dict(),
        })
    return rows


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 60)
    print(f"Richard TV Scanner — {date.today()} (Premium real-time)")
    print("=" * 60)

    df = fetch_ross_universe()
    if not df.empty:
        print()
        print(df[['ticker', 'short_name', 'price', 'gap_pct', 'rel_vol', 'exchange']].to_string(index=False))
    else:
        print("  No results — check session cookie or market is closed")
