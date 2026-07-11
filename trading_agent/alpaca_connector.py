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


def _read_secret_from_vault(vault_dir: str | None = None) -> str | None:
    """
    Read Alpaca secret from vault.

    Docker mode (vault_dir set):
        Checks {vault_dir}/ALPACA_SECRET_KEY.env — plain text written by entrypoint.sh.
    Windows mode (vault_dir None):
        Falls back to DPAPI-decrypted alpaca_secret.enc.
    """
    if vault_dir is None:
        vault_dir = str(Path(__file__).parent.parent / "vault")

    # Docker: plain-text env file written by entrypoint
    docker_secret_path = Path(vault_dir) / "ALPACA_SECRET_KEY.env"
    if docker_secret_path.exists():
        secret = docker_secret_path.read_text(encoding="utf-8").strip()
        if secret:
            return secret

    # Windows: DPAPI-decrypted vault (legacy path)
    vault_enc_path = Path(vault_dir) / "alpaca_secret.enc"
    if not vault_enc_path.exists():
        return None

    ps_script = fr'''
        $ErrorAction = 'Stop'
        try {{
            $secret = Get-Content '{vault_enc_path}' -Raw -Encoding UTF8
            $encrypted = [Convert]::FromBase64String($secret.Trim())
            $decrypted = [System.Security.Cryptography.ProtectedData]::Unprotect(
                $encrypted, $null,
                [System.Security.Cryptography.DataProtectionScope]::CurrentUser
            )
            Write-Output ([System.Text.Encoding]::UTF8.GetString($decrypted))
        }} catch {{
            exit 1
        }}
    '''
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _store_secret_to_vault(secret: str) -> bool:
    """
    Store Alpaca secret to DPAPI vault. Uses Python ctypes to call Windows DPAPI
    directly -- no PowerShell dependency.

    Entropy parameter (optional_entropy) defaults to None, meaning current-user-only
    scope. The same Windows user account is required to decrypt.
    """
    import ctypes
    from ctypes import wintype

    vault_path = Path(__file__).parent.parent / "vault" / "alpaca_secret.enc"
    vault_path.parent.mkdir(parents=True, exist_ok=True)

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintype.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]

    CRYPTPROTECT_UI_FORBIDDEN = 0x1

    try:
        # Load DLLs
        crypt32 = ctypes.WinDLL("Crypt32.dll")
        kernel32 = ctypes.WinDLL("Kernel32.dll")

        crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(DATA_BLOB),  # pDataIn
            ctypes.c_wchar_p,            # szDataDescr (optional, can be NULL)
            ctypes.POINTER(DATA_BLOB),  # pOptionalEntropy
            ctypes.c_void_p,            # pvReserved (must be NULL)
            ctypes.c_void_p,            # pPromptStruct (NULL = no UI)
            ctypes.DWORD,               # dwFlags
            ctypes.POINTER(DATA_BLOB),  # pDataOut
        ]
        crypt32.CryptProtectData.restype = wintype.BOOL

        kernel32.LocalFree.argtypes = [wintype.HLOCAL]
        kernel32.LocalFree.restype = wintype.HLOCAL

        # Build input blob
        secret_bytes = secret.encode("utf-16-le")  # DPAPI expects UTF-16 LE
        in_blob = DATA_BLOB(
            cbData=len(secret_bytes),
            pbData=(ctypes.c_byte * len(secret_bytes)).from_buffer_copy(secret_bytes),
        )

        out_blob = DATA_BLOB()

        ok = crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            None,  # no description
            None,  # no optional entropy
            None,  # reserved
            None,  # no prompt
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        )

        if not ok:
            raise ctypes.WinError()

        # Extract encrypted bytes from output blob
        encrypted = bytes(out_blob.pbData[:out_blob.cbData])
        kernel32.LocalFree(out_blob.pbData)

        # Encode to base64 for safe storage
        import base64
        b64 = base64.b64encode(encrypted).decode("ascii")
        vault_path.write_text(b64 + "\n", encoding="utf-8")
        return True

    except Exception as e:
        print(f"[_store_secret_to_vault] DPAPI failed: {e}")
        return False


def get_secret_from_kay(vault_dir: str | None = None) -> str:
    """
    Get the Alpaca secret key.
    First checks vault (Docker .env file or Windows DPAPI, no popup).
    Falls back to InputBox popup if vault is empty.
    """
    # Try vault first (auto-start path)
    vault_secret = _read_secret_from_vault(vault_dir=vault_dir)
    if vault_secret:
        return vault_secret

    # Fall back to interactive popup
    import tempfile, os
    prompt_script = r"""
Add-Type -AssemblyName Microsoft.VisualBasic
$title = 'Alpaca Secret Key'
$msg = 'Enter your Alpaca Secret Key:'
$secret = [Microsoft.VisualBasic.Interaction]::InputBox($msg, $title, '')
if ([string]::IsNullOrWhiteSpace($secret)) {
    Write-Error "No secret entered"
    exit 1
}
Write-Output $secret
"""
    tmp = tempfile.NamedTemporaryFile(suffix=".ps1", delete=False, mode="w", encoding="utf-8")
    tmp.write(prompt_script)
    tmp.close()

    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", tmp.name],
        capture_output=True, text=True, timeout=60
    )
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
        Uses nest_asyncio to allow asyncio.run() inside the Mavis daemon's
        existing event loop without conflicts.
        """
        import asyncio
        import nest_asyncio
        nest_asyncio.apply()  # allow nested event loops

        async def _async_stream():
            wss = "wss://stream.data.alpaca.markets/v2/iex"
            stream = StockDataStream(api_key=self.api_key, secret_key=self.secret)

            async def handler(quote: Quote):
                callback(quote.symbol, float(quote.bid_price),
                         float(quote.ask_price), quote.timestamp)

            stream.subscribe_quotes(handler, *symbols)
            print(f"[Alpaca WS] Connecting to {wss} for quotes: {symbols}")
            await stream.run()

        asyncio.run(_async_stream())


# ── Alpaca Trading Client ──────────────────────────────────────────────────────

try:
    from alpaca.trading import TradingClient, MarketOrderRequest, OrderSide, TimeInForce
    from alpaca.trading.enums import OrderType as AlpacaOrderType
    ALPACA_TRADING_AVAILABLE = True
except ImportError:
    ALPACA_TRADING_AVAILABLE = False


class AlpacaTrading:
    """
    Alpaca paper trading client — submits real orders via alpaca-py.

    Reads ALPACA_API_KEY and ALPACA_SECRET_KEY from environment variables,
    which are set by docker-compose from Portainer Docker Secrets.
    Falls back to vault file written by entrypoint.py (ALPACA_SECRET_KEY.env).
    """

    _client: TradingClient | None = None

    @classmethod
    def get_client(cls) -> TradingClient:
        if cls._client is not None:
            return cls._client

        if not ALPACA_TRADING_AVAILABLE:
            raise ImportError("alpaca-py is not installed. Run: pip install alpaca-py")

        api_key = os.environ.get("ALPACA_API_KEY")
        secret  = os.environ.get("ALPACA_SECRET_KEY")

        # Fallback: secret from vault file written by entrypoint
        if not secret:
            vault_dir = Path(__file__).parent.parent / "vault"
            secret_path = vault_dir / "ALPACA_SECRET_KEY.env"
            if secret_path.exists():
                secret = secret_path.read_text(encoding="utf-8").strip()

        if not api_key or not secret:
            raise RuntimeError(
                "Alpaca API keys not found. Set ALPACA_API_KEY and ALPACA_SECRET_KEY "
                "in Docker Secrets / environment, or ensure vault/ALPACA_SECRET_KEY.env "
                "is written by entrypoint.py"
            )

        cls._client = TradingClient(
            api_key=api_key,
            secret_key=secret,
            paper=True,   # Always use paper trading
        )
        return cls._client

    @classmethod
    def submit_market_order(
        cls,
        symbol: str,
        qty: int | float,
        side: str,   # "buy" or "sell"
        dry_run: bool = False,
    ) -> dict:
        """
        Submit a market order to Alpaca paper trading.

        Args:
            symbol:    Ticker symbol, e.g. "AAPL"
            qty:       Number of shares to buy/sell
            side:      "buy" or "sell"
            dry_run:   If True, log the order but do NOT submit to broker

        Returns:
            dict with keys: order_id, status, symbol, qty, side, submitted_at
            Raises on failure.
        """
        if dry_run:
            order_id = f"dry_run_{symbol}_{int(time.time())}"
            print(f"[AlpacaTrading:DryRun] {side.upper()} {qty} {symbol} @ market")
            return {
                "order_id": order_id,
                "status":   "dry_run",
                "symbol":   symbol,
                "qty":      qty,
                "side":     side,
                "submitted_at": datetime.now().isoformat(),
            }

        client = cls.get_client()

        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

        order = MarketOrderRequest(
            symbol=symbol.upper(),
            qty=qty,
            side=side_enum,
            time_in_force=TimeInForce.DAY,
        )

        submitted = client.submit_order(order)
        print(
            f"[AlpacaTrading] Submitted: {submitted.id} | "
            f"{side.upper()} {qty} {symbol} | status={submitted.status}"
        )
        return {
            "order_id":     submitted.id,
            "status":       str(submitted.status),
            "symbol":       submitted.symbol,
            "qty":          float(submitted.qty),
            "side":         side.lower(),
            "submitted_at": submitted.submitted_at.isoformat()
                           if submitted.submitted_at else datetime.now().isoformat(),
        }

    @classmethod
    def get_account(cls) -> dict:
        """Return paper account info."""
        client = cls.get_client()
        acct = client.get_account()
        return {
            "cash":          float(acct.cash),
            "buying_power":  float(acct.buying_power),
            "status":        str(acct.status),
            "currency":      str(acct.currency),
        }


# ── CLI ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Alpaca live data connector")
    parser.add_argument("--test", action="store_true", help="Test connection with a quote")
    parser.add_argument("--secret", action="store_true", help="Prompt for secret key, test connection, store to vault")
    parser.add_argument("--store-secret", dest="store_secret", metavar="SECRET", help="Store secret to vault non-interactively")
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
            # Store secret to vault on successful connection
            secret = data.secret
            if secret and _store_secret_to_vault(secret):
                print("[Alpaca] Secret stored to vault ✅")
            print(f"[Alpaca] Connected! {quote['symbol']}: bid=${quote['bid']:.2f} ask=${quote['ask']:.2f}")
        else:
            print("[Alpaca] Connection failed — check key and secret")

    elif args.store_secret:
        secret = args.store_secret
        if _store_secret_to_vault(secret):
            print(f"[Alpaca] Secret stored to vault ✅")
            # Verify it reads back correctly
            from alpaca_connector import _read_secret_from_vault
            stored = _read_secret_from_vault()
            if stored == secret:
                print("[Alpaca] Vault verification: PASS ✅")
            else:
                print("[Alpaca] Vault verification: FAIL — read back mismatch")
        else:
            print("[Alpaca] Store failed — check PowerShell DPAPI access")

    else:
        parser.print_help()
