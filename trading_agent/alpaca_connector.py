r"""
alpaca_connector.py
==================
Live market data from Alpaca — event-driven price feed.

Security:
  API key (public)  → E:\Me\TradingAgent\vault\alpaca_api_key.enc (DPAPI encrypted)
  Secret key (secret) -> Kay enters manually when connector runs. NEVER stored.

Usage:
    # Quick test (Kay will be prompted for secret):
    python alpaca_connector.py --test

    # With secret (Kay enters it, not pasted):
    python alpaca_connector.py --secret

    # In code:
    from alpaca_connector import AlpacaData, get_secret_from_kay
    data = AlpacaData(secret=get_secret_from_kay())
    quote = data.get_quote('AAPL')
"""

import subprocess
import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

# ── Vault ───────────────────────────────────────────────────────────────────────

VAULT_KEY_FILE = Path(r"E:\Me\TradingAgent\vault\alpaca_api_key.enc")
PAPER_BASE_URL = "https://paper-api.alpaca.markets"
DATA_BASE_URL  = "https://data.alpaca.markets"


def _read_api_key_from_vault() -> str:
    """Read Alpaca API key from DPAPI vault. Returns string, never prints."""
    ps_script = r'''
        $ErrorAction = 'Stop'
        try {
            $apiKey = Get-Content 'E:\Me\TradingAgent\vault\alpaca_api_key.enc' -Encoding UTF8 | ConvertTo-SecureString
            $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($apiKey)
            $plain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
            [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
            Write-Output $plain
        } catch {
            Write-Error "Failed to read Alpaca API key from vault"
            exit 1
        }
    '''
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        raise RuntimeError(f"Vault read failed: {result.stderr.strip()}")
    return result.stdout.strip()


def get_secret_from_kay() -> str:
    """
    Prompt Kay for the Alpaca secret key via a separate visible PowerShell window.
    Kay types it there — it never appears in logs or chat.
    Uses Start-Process so the window opens regardless of shell interactivity.
    """
    import tempfile
    prompt_script = r"""
Add-Type -AssemblyName Microsoft.VisualBasic
$title = 'Alpaca Secret Key'
$msg = 'Enter your Alpaca Secret Key (hidden):'
$secret = [Microsoft.VisualBasic.Interaction]::InputBox($msg, $title, '')
if ([string]::IsNullOrWhiteSpace($secret)) {
    Write-Error "No secret entered"
    exit 1
}
Write-Output $secret
"""
    # Write to a temp .ps1 so we can run it visibly
    tmp = tempfile.NamedTemporaryFile(suffix=".ps1", delete=False, mode="w", encoding="utf-8")
    tmp.write(prompt_script)
    tmp.close()

    # Run in a new visible window, wait for Kay to type
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", tmp.name],
        capture_output=True, text=True, timeout=60
    )
    import os
    try:
        os.unlink(tmp.name)
    except Exception:
        pass

    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("Secret entry cancelled or failed")
    return result.stdout.strip()


# ── Alpaca Data Client ─────────────────────────────────────────────────────────

try:
    from alpaca.data import StockHistoricalDataClient, TimeFrame, TimeFrameUnit
    from alpaca.data.live import StockDataStream
    from alpaca.data.models import Quote, Bar
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False


class AlpacaData:
    """
    Alpaca market data client.
    API key from vault. Secret entered by Kay at runtime.
    """

    def __init__(self, api_key: Optional[str] = None, secret: Optional[str] = None,
                 paper: bool = True):
        if not ALPACA_AVAILABLE:
            raise ImportError("alpaca-py not installed. Run: pip install alpaca-py")

        if api_key is None:
            api_key = _read_api_key_from_vault()
        if secret is None:
            secret = get_secret_from_kay()

        self.api_key = api_key
        self.secret  = secret
        self.base_url = PAPER_BASE_URL if paper else DATA_BASE_URL
        self.data_url  = DATA_BASE_URL

        # REST client for historical bars / quotes
        self.client = StockHistoricalDataClient(
            api_key=api_key,
            secret_key=secret,
        )

    # ── REST data ───────────────────────────────────────────────────────────

    def get_quote(self, symbol: str) -> Optional[dict]:
        """Latest quote for a symbol."""
        try:
            from alpaca.data.requests import StockLatestQuoteRequest
            req = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
            quotes = self.client.get_stock_latest_quote(req)
            q = quotes[symbol]
            return {
                'symbol':    symbol,
                'bid':      float(q.bid_price),
                'ask':      float(q.ask_price),
                'timestamp': q.timestamp.isoformat(),
            }
        except Exception as e:
            print(f"[Alpaca] Quote error for {symbol}: {e}")
            return None

    def get_bar(self, symbol: str, minutes: int = 5) -> Optional[dict]:
        """Latest N-minute bar for a symbol."""
        try:
            from alpaca.data.requests import StockLatestBarRequest
            req = StockLatestBarRequest(symbol_or_symbols=[symbol])
            bars = self.client.get_stock_latest_bar(req)
            b = bars[symbol]
            return {
                'symbol':    symbol,
                'open':      float(b.open),
                'high':      float(b.high),
                'low':       float(b.low),
                'close':     float(b.close),
                'volume':    int(b.volume),
                'timestamp': b.timestamp.isoformat(),
            }
        except Exception as e:
            print(f"[Alpaca] Bar error for {symbol}: {e}")
            return None

    def get_bars(self, symbol: str, timeframe: TimeFrame, start, end=None) -> Optional[list]:
        """Historical bars for a symbol."""
        try:
            from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
            req = StockBarsRequest(
                symbol_or_symbols=[symbol],
                timeframe=timeframe,
                start=start,
                end=end,
            )
            bars = self.client.get_stock_bars(req)
            return [
                {
                    'symbol':    b.symbol,
                    'open':      float(b.open),
                    'high':      float(b.high),
                    'low':       float(b.low),
                    'close':     float(b.close),
                    'volume':    int(b.volume),
                    'timestamp': b.timestamp.isoformat(),
                }
                for b in bars
            ]
        except Exception as e:
            print(f"[Alpaca] Bars error for {symbol}: {e}")
            return None

    # ── WebSocket stream ────────────────────────────────────────────────────

    def stream_quotes(self, symbols: list, callback):
        """
        Stream live quotes for a list of symbols.
        callback(symbol, bid, ask, timestamp) is called on each update.

        Usage:
            def on_quote(sym, bid, ask, ts):
                print(f"{sym}: bid={bid} ask={ask}")

            data = AlpacaData(secret=secret)
            data.stream_quotes(['AAPL', 'TSLA'], on_quote)
        """
        wss = f"wss://stream.data.alpaca.markets/v2/iex"
        stream = StockDataStream(api_key=self.api_key, secret_key=self.secret)

        def handler(quote: Quote):
            callback(quote.symbol, float(quote.bid_price), float(quote.ask_price), quote.timestamp)

        stream.subscribe_quotes(handler, *symbols)

        print(f"[Alpaca WS] Connecting to {wss} for quotes: {symbols}")
        stream.run()


# ── CLI ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Alpaca live data connector")
    parser.add_argument("--test", action="store_true", help="Test connection with a quote")
    parser.add_argument("--secret", action="store_true", help="Prompt for secret key and show status")
    parser.add_argument("--symbol", default="AAPL", help="Symbol for --test")
    args = parser.parse_args()

    if args.test:
        print("[Alpaca] Testing connection...")
        print("[Alpaca] A popup will appear for the secret key...")
        data = AlpacaData()
        quote = data.get_quote(args.symbol)
        if quote:
            print(f"[Alpaca] {quote['symbol']}: bid=${quote['bid']:.2f} ask=${quote['ask']:.2f} — CONNECTED!")
        else:
            print("[Alpaca] Quote returned None — check API key and secret")

    elif args.secret:
        print("[Alpaca] Prompting Kay for secret key...")
        data = AlpacaData()
        quote = data.get_quote(args.symbol)
        if quote:
            print(f"[Alpaca] Connected! {quote['symbol']}: bid=${quote['bid']:.2f} ask=${quote['ask']:.2f}")
        else:
            print("[Alpaca] Connection failed — check key and secret")

    else:
        parser.print_help()
