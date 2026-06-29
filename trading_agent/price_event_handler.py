"""
price_event_handler.py
======================
Event-driven price handler — replaces cron-based intraday scanning.

Architecture:
    Alpaca WebSocket live quotes (1-min updates)
        ↓
    PriceEventHandler
        ↓
    Tracks: intraday_high, pullback_depth, ATR per symbol
        ↓
    On pullback trigger (1.5×–3× ATR from high):
        → Fires scanner signal
        → Triggers Bull/Bear debate
        → Auto-opens position
        ↓
    On target / stop / 2-min rule hit:
        → Closes position
        → Writes to positions.json
        → Telegram notification

Usage:
    from price_event_handler import PriceEventHandler
    handler = PriceEventHandler(watchlist=['AAPL', 'TSLA', 'SOFI'], secret=secret)
    handler.start()   # starts WebSocket, blocks
    handler.stop()
"""

import json
import sys
import time
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional

DATA_DIR     = Path(r"E:\Me\TradingAgent\data")
POS_FILE     = DATA_DIR / "positions.json"
RESULTS_FILE = DATA_DIR / "bull_bear_results.json"
SIGNALS_FILE = DATA_DIR / "signals_live.json"

AMSTERDAM_TZ = timezone(timedelta(hours=2))

# ── ATR pullback filter (from intraday_scanner.py logic) ────────────────────

MAX_PULLBACK_ATR = 3.0   # 3× ATR = too deep, skip
MIN_PULLBACK_ATR = 1.5   # 1.5× ATR = not enough discount
MAX_INTRADAY_PULLBACK_PCT = 0.30  # 30% of intraday range max


class SymbolTracker:
    """
    Tracks a single symbol's intraday state.
    Computes ATR from rolling 14-bar history.
    Fires when price is in the valid pullback zone (1.5×–3× ATR from high).
    """

    def __init__(self, symbol: str, atr_bars: int = 14):
        self.symbol    = symbol
        self.atr_bars  = atr_bars
        self.high      = 0.0      # intraday high
        self.low       = float('inf')
        self.close_prices = []   # rolling close prices for ATR
        self.last_quote = None
        self.pullback_fired = False  # prevent re-fire on same pullback

    def update(self, bid: float, ask: float, ts: datetime):
        """Called on every WebSocket quote update."""
        price = (bid + ask) / 2
        self.last_quote = price

        # Update intraday high/low
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price

        # Rolling close history for ATR
        self.close_prices.append(price)
        if len(self.close_prices) > self.atr_bars + 1:
            self.close_prices.pop(0)

    def get_atr(self) -> float:
        """Compute ATR from rolling bar closes (simplified)."""
        if len(self.close_prices) < self.atr_bars + 1:
            return 0.0

        trs = []
        closes = self.close_prices
        for i in range(1, len(closes)):
            high  = max(closes[i], closes[i-1])
            low   = min(closes[i], closes[i-1])
            tr    = high - low
            trs.append(tr)

        if len(trs) < self.atr_bars:
            return 0.0
        return sum(trs[-self.atr_bars:]) / self.atr_bars

    def check_pullback(self, price: float) -> tuple[bool, str]:
        """
        Returns (should_fire, reason).
        Fires once per pullback event (not on every tick).
        """
        if self.high == 0:
            return False, "no high yet"

        atr = self.get_atr()
        if atr <= 0:
            return False, "ATR not ready"

        pullback_dollar = self.high - price
        pullback_pct    = pullback_dollar / self.high if self.high > 0 else 0
        pullback_atr    = pullback_dollar / atr

        # Already fired on this pullback — wait for new high first
        if self.pullback_fired:
            if price >= self.high * 0.995:  # reset when recovering to near high
                self.pullback_fired = False
            else:
                return False, "pullback already fired, waiting for recovery"

        # Valid first pullback zone?
        if pullback_atr < MIN_PULLBACK_ATR:
            return False, f"pullback {pullback_atr:.1f}× ATR < 1.5× (too shallow)"

        if pullback_atr > MAX_PULLBACK_ATR:
            return False, f"pullback {pullback_atr:.1f}× ATR > 3× (too deep)"

        if pullback_pct > MAX_INTRADAY_PULLBACK_PCT:
            return False, f"pullback {pullback_pct:.1%} > 30% of intraday range"

        # Price recovering? (above EMA_9 — approximated by: price > mid-range of intraday)
        mid = (self.high + self.low) / 2
        if price < mid:
            return False, "price below intraday mid-range (still falling)"

        self.pullback_fired = True
        return True, (
            f"FIRST PULLBACK: {pullback_atr:.1f}× ATR pullback from ${self.high:.2f} high. "
            f"Entry: ${price:.2f}. ATR=${atr:.3f}"
        )


class PriceEventHandler:
    """
    Manages WebSocket stream and per-symbol trackers.
    Fires Bull/Bear debate when a valid first pullback is detected.
    """

    def __init__(self, watchlist: list[str],
                 secret: str,
                 on_signal: Optional[Callable] = None,
                 on_exit: Optional[Callable] = None):
        self.watchlist   = watchlist
        self.secret     = secret
        self.on_signal  = on_signal   # called with (symbol, price, atr, pullback_dollar, reason)
        self.on_exit    = on_exit     # called with (symbol, reason)
        self.trackers   = {sym: SymbolTracker(sym) for sym in watchlist}
        self._running   = False
        self._thread     = None

    def _on_quote(self, symbol: str, bid: float, ask: float, ts):
        """Called on every Alpaca WebSocket quote."""
        if symbol not in self.trackers:
            return

        tracker = self.trackers[symbol]
        tracker.update(bid, ask, ts)
        price = (bid + ask) / 2

        should_fire, reason = tracker.check_pullback(price)
        if should_fire:
            atr = tracker.get_atr()
            pullback_dollar = tracker.high - price
            print(f"[PriceEvent] {symbol}: {reason}")
            if self.on_signal:
                self.on_signal(
                    symbol=symbol,
                    price=price,
                    atr=atr,
                    intraday_high=tracker.high,
                    pullback_dollar=pullback_dollar,
                    reason=reason,
                    timestamp=ts,
                )

    def _stream_loop(self):
        """
        Runs in background thread — starts alpaca_ws_subprocess.py,
        reads JSON quotes from stdout, dispatches to trackers.
        Completely isolated event loop — no asyncio conflicts.
        """
        import subprocess, json, queue, threading

        from alpaca_connector import get_secret_from_kay, _read_api_key_from_vault

        # Get credentials
        sys.path.insert(0, str(Path(__file__).parent))
        api_key = _read_api_key_from_vault()
        secret = self.secret or get_secret_from_kay()

        symbols_arg = ",".join(self.watchlist)
        script = Path(__file__).parent / "alpaca_ws_subprocess.py"

        proc = subprocess.Popen(
            [sys.executable, str(script),
             "--api-key", api_key,
             "--secret", secret,
             "--symbols", symbols_arg],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # line buffered
        )

        print(f"[PriceEvent] Subprocess started (PID {proc.pid}), reading quotes...")

        # Read lines from stdout in this thread
        for raw_line in iter(proc.stdout.readline, ""):
            if not raw_line:
                break
            line = raw_line.strip()
            if not line or line.startswith("[WS]"):
                continue  # skip status lines
            try:
                quote = json.loads(line)
                self._on_quote(
                    quote["symbol"],
                    quote["bid"],
                    quote["ask"],
                    datetime.fromisoformat(quote["timestamp"]),
                )
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"[PriceEvent] Bad quote line: {e} — {line[:80]}")

        proc.wait()
        stderr = proc.stderr.read()
        if proc.returncode != 0 and stderr:
            print(f"[PriceEvent] Subprocess error: {stderr[:200]}")

    def start(self):
        """Start the WebSocket subprocess in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        print(f"[PriceEvent] Started tracking: {self.watchlist}")

    def stop(self):
        """Stop the handler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[PriceEvent] Stopped")


# ── Bull/Bear trigger integration ────────────────────────────────────────────

def build_signal_from_event(event: dict) -> dict:
    """Convert a price event into a scanner-style signal dict."""
    return {
        'symbol':           event['symbol'],
        'price':            event['price'],
        'today_close':      event['price'],
        'yesterday_close':   event['price'],  # not available from live feed
        'gap_pct':          0.0,              # not available from live feed
        'float_m':          0.0,
        'volume_ratio':     0.0,
        'rsi':              0.0,
        'score':            4.5,              # threshold for Bull/Bear
        'target':           round(event['price'] + 0.20, 2),
        'stop':             round(event['price'] - 0.10, 2),
        'atr':              event['atr'],
        'intraday_high':    event['intraday_high'],
        'pullback_dollar':  event['pullback_dollar'],
        'pullback_atr_ratio': round(event['pullback_dollar'] / event['atr'], 1) if event['atr'] > 0 else 0,
        'intraday_low':     0.0,
        'news':             'Live pullback event',
        'pattern':          'FIRST_PULLBACK',
        'source':           'price_event_handler',
        'timestamp':        event['timestamp'].isoformat() if isinstance(event['timestamp'], datetime) else event['timestamp'],
    }


def save_live_signal(event: dict):
    """Append live signal to signals_live.json for handler to pick up."""
    sig = build_signal_from_event(event)
    sigs = []
    if SIGNALS_FILE.exists():
        try:
            with open(SIGNALS_FILE, encoding='utf-8') as f:
                sigs = json.load(f)
            if not isinstance(sigs, list):
                sigs = [sigs]
        except Exception:
            sigs = []

    sigs.append(sig)
    with open(SIGNALS_FILE, 'w', encoding='utf-8') as f:
        json.dump(sigs, f, indent=2, default=str)

    print(f"[PriceEvent] Signal saved to {SIGNALS_FILE}: {sig['symbol']} @ ${sig['price']}")
    return sig


# ── Main entry ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Event-driven price handler")
    parser.add_argument("--watchlist", default="AAPL,TSLA,SOFI,AMD,NVDA",
                        help="Comma-separated watchlist symbols")
    parser.add_argument("--secret", action="store_true",
                        help="Prompt for Alpaca secret key")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.watchlist.split(",")]

    if args.secret:
        from alpaca_connector import get_secret_from_kay, AlpacaData
        secret = get_secret_from_kay()
        print(f"[PriceEvent] Starting with watchlist: {symbols}")

        handler = PriceEventHandler(
            watchlist=symbols,
            secret=secret,
            on_signal=save_live_signal,
        )
        handler.start()

        print("[PriceEvent] Running — Ctrl+C to stop")
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            handler.stop()
    else:
        parser.print_help()
