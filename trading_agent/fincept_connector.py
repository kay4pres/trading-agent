"""
fincept_connector.py
===================
Bridges Fincept Terminal's yfinance_data.py script to our trading pipeline.

Fincept gives us:
  - Standardized JSON output from yfinance (quotes, historical, news, info)
  - 100+ Fincept scripts for fundamental data, macros, sentiment, etc.
  - Fincept Terminal as a visual dashboard

Our scripts (Ross's rules) apply the strategy on top.
"""

import json
import logging
import subprocess
import sys
from datetime import datetime, date
from typing import List, Optional, Dict, Any

# Set up module logger so failures are visible in container logs
logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter('[%(name)s] %(levelname)s: %(message)s'))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

# Path to Fincept's yfinance wrapper script
# Try multiple locations — Windows host path, Linux container path, then skip
_FINCEPT_HOST = r"C:\Program Files\FinceptTerminal\scripts\yfinance_data.py"
_FINCEPT_CONTAINER = "/app/fincept/yfinance_data.py"
FINCEPT_YF = _FINCEPT_HOST  # keep for reference; actual path decided in _run()


# ─── Helpers ────────────────────────────────────────────────────────────────

def _run(args: List[str]) -> Dict[str, Any]:
    """Run Fincept script, return parsed JSON. Falls back to yfinance directly."""
    # Always use yfinance in Docker/Linux — Fincept is a Windows-only desktop app
    fincept_path = None
    try:
        import os
        # Only try Fincept if explicitly on Windows AND file exists
        if sys.platform == "win32" and os.path.exists(_FINCEPT_HOST):
            fincept_path = _FINCEPT_HOST
    except Exception:
        pass  # Fall through to yfinance on any error

    if fincept_path is None:
        return _fallback_yfinance(args)

    try:
        result = subprocess.run(
            [sys.executable, fincept_path] + args,
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            logger.warning(f"Fincept script error (rc={result.returncode}): {stderr[:200]}")
            return {"success": False, "error": stderr}
        raw = result.stdout.strip()
        if raw.startswith("{"):
            return json.loads(raw)
        elif raw.startswith("["):
            return {"success": True, "data": json.loads(raw)}
        else:
            return {"success": False, "error": f"Unexpected output: {raw[:200]}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout fetching data"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _fallback_yfinance(args: List[str]) -> Dict[str, Any]:
    """Fallback: use yfinance directly if Fincept is unavailable."""
    try:
        import yfinance as yf
        cmd = args[0]
        sym = args[1] if len(args) > 1 else ""

        if cmd == "quote":
            t = yf.Ticker(sym)
            # Use .info dict (not .fast_info) — fast_info returns None for
            # penny/nano-cap stocks during market hours; info dict has better
            # None guards and is more reliable for thinly-traded symbols.
            info = t.info
            price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("ask") or 0
            prev = info.get("regularMarketPreviousClose") or info.get("previousClose") or price
            change = price - prev
            volume = info.get("regularMarketVolume") or info.get("volume") or 0
            return {
                "symbol": sym.upper(),
                "price": round(price, 2),
                "change": round(change, 2),
                "change_percent": round(change / prev * 100, 2) if prev else 0,
                "volume": int(volume),
            }
        elif cmd == "batch_quotes":
            return [_fallback_yfinance(["quote", s]) for s in args[1:]]
        elif cmd in ("historical", "historical_period"):
            period = args[2] if cmd == "historical_period" else "5d"
            interval = args[3] if cmd == "historical_period" else args[4] if len(args) > 4 else "5m"
            t = yf.Ticker(sym)
            df = t.history(period=period, interval=interval)
            return {"success": True, "data": [
                {"timestamp": int(r.timestamp()), "open": round(r["Open"], 2),
                 "high": round(r["High"], 2), "low": round(r["Low"], 2),
                 "close": round(r["Close"], 2), "volume": int(r["Volume"])}
                for _, r in df.iterrows()
            ]}
        elif cmd == "info":
            t = yf.Ticker(sym)
            info = t.info
            return {
                "symbol": sym.upper(),
                "floatShares": info.get("floatShares", 0),
                "averageVolume": info.get("averageVolume", 0),
                "marketCap": info.get("marketCap", 0),
                "shortName": info.get("shortName", ""),
                # Used by check_pillars() to compute gap_pct when quote has no previous_close
                "previousClose": info.get("regularMarketPreviousClose") or info.get("previousClose") or 0,
            }
        else:
            return {"success": False, "error": f"Fallback not implemented for: {cmd}"}
    except Exception as e:
        logger.warning(f"yfinance fallback failed for {cmd}/{sym}: {e}")
        return {"success": False, "error": f"Fallback failed: {e}"}


# ─── Public API ──────────────────────────────────────────────────────────────

def get_quote(symbol: str) -> Dict[str, Any]:
    """Live quote: price, change, volume, high, low, open, prev_close."""
    result = _run(["quote", symbol])
    # Fincept returns raw dict for single quote (no "success" wrapper)
    if isinstance(result, dict) and "symbol" in result and "price" in result:
        return result
    if result.get("success") and "error" not in result:
        return result.get("data", result)
    # Try fallback
    fb = _fallback_yfinance(["quote", symbol])
    if isinstance(fb, dict) and "symbol" in fb and fb.get("price"):
        return fb
    err = fb.get("error", "unknown") if isinstance(fb, dict) else str(fb)
    logger.warning(f"get_quote({symbol}): all sources failed — {err}")
    return fb if isinstance(fb, dict) else {"symbol": symbol.upper(), "price": 0, "error": err}


def get_batch_quotes(symbols: List[str]) -> List[Dict[str, Any]]:
    """Live quotes for multiple symbols in one call."""
    result = _run(["batch_quotes"] + symbols)
    # Fincept can return a raw list for batch_quotes — handle both cases
    if isinstance(result, list):
        valid = [q for q in result if isinstance(q, dict) and q.get("price")]
        logger.info(f"get_batch_quotes: {len(valid)}/{len(symbols)} returned valid quotes")
        return valid
    if result.get("success"):
        data = result.get("data", [])
        valid = [q for q in data if isinstance(q, dict) and q.get("price")]
        logger.info(f"get_batch_quotes: {len(valid)}/{len(symbols)} returned valid quotes")
        return valid
    # Fallback: single quotes
    logger.info(f"get_batch_quotes: falling back to individual quotes for {len(symbols)} symbols")
    quotes = [get_quote(s) for s in symbols]
    valid = [q for q in quotes if isinstance(q, dict) and q.get("price")]
    logger.info(f"get_batch_quotes fallback: {len(valid)}/{len(symbols)} returned valid quotes")
    return valid


def get_historical(
    symbol: str,
    period: str = "5d",
    interval: str = "5m"
) -> List[Dict[str, Any]]:
    """
    Historical OHLCV bars.
    interval: 1m, 5m, 15m, 1h, 1d, etc.
    period: 1d, 5d, 1mo, 3mo, etc.
    """
    result = _run(["historical_period", symbol, period, interval])
    if result.get("success"):
        return result.get("data", [])
    # Fallback
    fb = _fallback_yfinance(["historical_period", symbol, period, interval])
    return fb.get("data", [])


def get_info(symbol: str) -> Dict[str, Any]:
    """Company info: float, volume, market cap, sector."""
    result = _run(["info", symbol])
    if result.get("success"):
        return result.get("data", result)
    # Fallback
    fb = _fallback_yfinance(["info", symbol])
    return fb


def get_news(symbol: str, count: int = 20) -> List[Dict[str, Any]]:
    """News articles for a symbol."""
    result = _run(["news", symbol, str(count)])
    if result.get("success"):
        return result.get("data", [])
    return []


def get_batch_all(symbols: List[str]) -> Dict[str, Any]:
    """
    Everything in one call: quotes + sparklines + recent history.
    Used by Richard to build the premarket watchlist efficiently.
    """
    payload = json.dumps({"symbols": symbols, "quotes": True, "sparklines": True, "history_days": 2})
    result = _run(["batch_all", payload])
    return result if result else {"success": False}


# ─── Convenience: timestamp helpers ─────────────────────────────────────────

def unix_to_dt(ts: int) -> datetime:
    return datetime.fromtimestamp(ts)


def recent_bars(symbol: str, bars: int = 20, interval: str = "5m") -> List[Dict[str, Any]]:
    """Get the most recent N bars for a symbol."""
    history = get_historical(symbol, period="1d", interval=interval)
    return history[-bars:] if len(history) > bars else history
