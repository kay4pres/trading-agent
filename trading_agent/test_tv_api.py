"""Test TradingView API with session cookie."""
import subprocess
import pandas as pd
from pathlib import Path

# ── Decrypt session cookie ──────────────────────────────────────────────
token_path = Path(r'E:\Me\TradingAgent\config\tv_session.enc')
raw = token_path.read_text(encoding='utf-8').strip()
if raw.startswith('\ufeff'):
    raw = raw[1:]

escaped = raw.replace("'", "''")
ps = (
    "$b = '%s'; "
    "$s = ConvertTo-SecureString $b; "
    "[System.Runtime.InteropServices.Marshal]::PtrToStringAuto("
    "[System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))"
) % escaped

result = subprocess.run(
    ['powershell', '-Command', ps],
    capture_output=True, text=True, timeout=15
)
session_id = result.stdout.strip()
print("Cookie raw:", repr(session_id))
print("Cookie length:", len(session_id))

# ── Ross-style screener query ───────────────────────────────────────────
from tradingview_screener import Query, col

cookies = {'sessionid': session_id}

try:
    result = (
        Query()
        .select(
            'ticker', 'name', 'close', 'change',
            'volume', 'relative_volume_10d_calc',
            'market_cap_basic', 'exchange'
        )
        .where(
            col('close') > 2,
            col('close') < 20,
            col('change') > 10,
            col('relative_volume_10d_calc') > 5,
        )
        .order_by('relative_volume_10d_calc', ascending=False)
        .limit(15)
        .get_scanner_data(cookies=cookies)
    )
    print("Return type:", type(result))
    print("Return length:", len(result) if hasattr(result, '__len__') else 'N/A')

    # Handle different return formats
    if isinstance(result, tuple):
        count = result[0]
        df = result[1] if len(result) > 1 else None
    else:
        count = None
        df = result

    print("Count:", count)
    print("df type:", type(df))
    if hasattr(df, 'columns'):
        print("Rows:", len(df))
        print("Columns:", list(df.columns))
        print(df[['ticker', 'name', 'close', 'change', 'relative_volume_10d_calc', 'exchange']].head(15).to_string(index=False))
    else:
        print("df content:", df)
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()


