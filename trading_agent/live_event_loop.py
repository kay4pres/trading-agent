r"""
live_event_loop.py
==================
Event-driven trading loop — the core wiring piece.

Architecture:
    Alpaca WebSocket (price_event_handler)
        ↓
    Pullback detected → write to signals_live.json
        ↓
    Mavis scan-market cron → picks up signal → runs Bull/Bear LLM debate
        ↓
    Results written to bull_bear_results.json
        ↓
    live_event_loop polls results → auto-opens if conviction >= 7
        ↓
    Position monitor (target/stop/2-min) → on exit → memory_logger

LLM key lives in Mavis daemon session — Bull/Bear runs inside Mavis cron,
not in a subprocess. This is the same pattern that fixed the 401 error.

Usage:
    py -3 trading_agent\live_event_loop.py --watchlist AAPL,TSLA --secret
    py -3 trading_agent\live_event_loop.py --help
"""

import json
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
DATA_DIR      = Path(r"E:\Me\TradingAgent\data")
DEBATE_IN     = DATA_DIR / "bull_bear_results.json"   # written by Mavis cron
SIGNAL_QUEUE  = DATA_DIR / "signals_live.json"         # written by live_event_loop
POSITIONS_FILE = DATA_DIR / "positions.json"
AMSTERDAM_TZ  = timezone(timedelta(hours=2))
CONVICTION_THRESHOLD = 7.0
POLL_INTERVAL = 15   # seconds between result checks and exit checks


# ── Exit Handler ────────────────────────────────────────────────────────────────

def on_exit(symbol: str, reason: str, exit_price: float, pos: dict):
    """Called when a position exits. Logs to journal."""
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from memory_logger import log_trade

        trade_record = {
            "symbol": symbol,
            "action": pos.get("direction", "LONG").upper(),
            "entry_price": pos["entry_price"],
            "exit_price": round(exit_price, 4),
            "exit_reason": reason,
            "pnl": round((exit_price - pos["entry_price"]) * pos["quantity"], 2),
            "pnl_pct": round(
                (exit_price - pos["entry_price"]) / pos["entry_price"] * 100, 2
            ),
            "closed_at": datetime.now(AMSTERDAM_TZ).isoformat(),
            "notes": (
                f"Signal: {pos.get('entry_signal','?')} | "
                f"Score: {pos.get('signal_score','?')}/5 | "
                f"ATR: {pos.get('atr','?')}"
            ),
        }
        msg = log_trade(trade_record)
        print(f"[Memory] {msg}")
    except Exception as e:
        print(f"[Memory] Failed to log trade: {e}")


# ── Position Monitor (exit checks + debate polling) ─────────────────────────────

def monitor_positions():
    """
    Background thread — polls every POLL_INTERVAL seconds:
    1. Check open positions for target/stop/2-min rule exits
    2. Poll bull_bear_results.json for new debate verdicts
    """
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    from trader_agent import (
        load_positions, get_live_price,
        check_exit, check_two_min_rule, execute_exit,
        is_market_hours,
    )

    while True:
        try:
            if not is_market_hours():
                time.sleep(60)
                continue

            # 1. Exit checks on open positions
            state = load_positions()
            if state.get("positions"):
                for symbol, pos in list(state["positions"].items()):
                    if pos.get("status") != "OPEN":
                        continue
                    live_price = get_live_price(symbol)
                    if live_price is None:
                        continue
                    print(f"[Monitor] {symbol}: ${live_price:.2f} | "
                          f"T:{pos['target']:.2f} S:{pos['stop']:.2f}")
                    should_exit_2min, reason_2min = check_two_min_rule(
                        state, symbol, pos, live_price
                    )
                    if should_exit_2min:
                        execute_exit(state, symbol, pos, reason_2min, live_price)
                        continue
                    should_exit, reason = check_exit(state, symbol, pos, live_price)
                    if should_exit:
                        execute_exit(state, symbol, pos, reason, live_price)
                        continue

            # 2. Poll for new debate results
            results = process_debate_results()
            for result in results:
                handle_debate_result(result)

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("[Monitor] Interrupted — exiting.")
            break
        except Exception as e:
            print(f"[Monitor] Error: {e}")
            time.sleep(POLL_INTERVAL)


# ── Pullback Signal Handler ──────────────────────────────────────────────────────

def on_pullback(event: dict):
    """
    Called by PriceEventHandler when a valid first pullback is detected.
    Writes the signal to signals_live.json — the Mavis cron picks it up,
    runs the Bull/Bear debate using its own LLM key, writes results to
    bull_bear_results.json. We then poll that file and act on the verdict.
    """
    symbol = event["symbol"]
    print(f"[Pullback] {symbol} detected at ${event['price']:.2f}")

    # Guard: skip if already in a position
    if POSITIONS_FILE.exists():
        try:
            with open(POSITIONS_FILE, encoding="utf-8") as f:
                state = json.load(f)
            if symbol.upper() in (s.upper() for s in state.get("positions", {}).keys()):
                print(f"[Pullback] {symbol} already in position — skipping")
                return
        except Exception:
            pass

    # Guard: skip if already queued for debate
    if SIGNAL_QUEUE.exists():
        try:
            with open(SIGNAL_QUEUE, encoding="utf-8") as f:
                queue = json.load(f)
            if not isinstance(queue, list):
                queue = [queue]
            pending = [s for s in queue if s.get("debated", False) is False]
            already_queued = any(s.get("symbol", "").upper() == symbol.upper() for s in pending)
            if already_queued:
                print(f"[Pullback] {symbol} already queued for debate")
                return
        except Exception:
            queue = []

    # Build the signal record
    from price_event_handler import build_signal_from_event
    sig = build_signal_from_event(event)
    sig["debated"] = False
    sig["queued_at"] = datetime.now(AMSTERDAM_TZ).isoformat()

    # Append to signal queue
    SIGNAL_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    queue = []
    if SIGNAL_QUEUE.exists():
        try:
            with open(SIGNAL_QUEUE, encoding="utf-8") as f:
                queue = json.load(f)
            if not isinstance(queue, list):
                queue = [queue]
        except Exception:
            queue = []

    # Deduplicate by symbol (keep only latest)
    queue = [s for s in queue if s.get("symbol", "").upper() != symbol.upper()]
    queue.append(sig)

    with open(SIGNAL_QUEUE, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, default=str)

    print(f"[Pullback] {symbol} queued for Bull/Bear debate → {SIGNAL_QUEUE}")
    print(f"[Pullback] Signal: gap={sig.get('gap_pct',0)}% price=${sig['price']} "
          f"atr={sig.get('atr',0):.3f} pullback=${sig.get('pullback_dollar',0):.2f}")


# ── Debate Result Processor ──────────────────────────────────────────────────────

def process_debate_results():
    """
    Poll bull_bear_results.json for new debate results.
    Called every POLL_INTERVAL seconds alongside position monitoring.
    """
    if not DEBATE_IN.exists():
        return []

    try:
        with open(DEBATE_IN, encoding="utf-8") as f:
            data = json.load(f)
        debates = data.get("debates", [])
        if not debates:
            return []
    except Exception:
        return []

    # Mark as processed to avoid re-processing
    with open(DEBATE_IN, "w", encoding="utf-8") as f:
        json.dump({"debates": []}, f, default=str)

    return debates


def handle_debate_result(result: dict):
    """Act on a completed Bull/Bear debate result."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    from trader_agent import open_position, send_telegram

    sig = result.get("signal", result)
    symbol = sig.get("symbol", "UNKNOWN")
    verdict = result.get("verdict", "SKIP")
    conviction = result.get("conviction", 5.0)

    if verdict == "APPROVE" and conviction >= CONVICTION_THRESHOLD:
        print(f"[Entry] AUTO-OPEN {symbol} (conviction {conviction}/10)")
        try:
            opened = open_position(
                symbol=symbol,
                direction="long",
                entry_price=sig["price"],
                quantity=sig.get("qty", 100),
                target=sig.get("target"),
                stop=sig.get("stop"),
                signal_score=sig.get("score", 5.0),
                rules_applied=["P1", "P2", "P3", "P4", "P5"],
                signal_type=f"First Pullback + Bull/Bear (conviction {conviction}/10)",
            )
            if opened:
                send_telegram(
                    f"🚀 AUTO-OPENED\n"
                    f"{symbol} LONG 100 @ ${sig['price']}\n"
                    f"Target: ${sig.get('target','?')} | Stop: ${sig.get('stop','?')}\n"
                    f"Conviction: {conviction}/10"
                )
        except Exception as e:
            print(f"[Entry] Failed to open {symbol}: {e}")

    elif verdict == "APPROVE":
        print(f"[Entry] Notify Kay — conviction {conviction}/10 < {CONVICTION_THRESHOLD}")
        try:
            send_telegram(
                f"📊 Bull/Bear Alert — {symbol}\n"
                f"Conviction: {conviction}/10 | Verdict: APPROVE\n"
                f"Price: ${sig['price']} | Manual approval needed."
            )
        except Exception:
            pass
    else:
        print(f"[Entry] SKIPPED {symbol} — verdict={verdict}, conviction={conviction}/10")


# ── Main ────────────────────────────────────────────────────────────────────────

def start_live_loop(watchlist: list[str], secret: str):
    """
    Start the live event loop:
    1. PriceEventHandler (Alpaca WebSocket) in background thread
    2. Position monitor thread (exit checks)
    Blocks until KeyboardInterrupt.
    """
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    from price_event_handler import PriceEventHandler

    print(f"[LiveLoop] Starting with watchlist: {watchlist}")

    # Start position monitor thread
    monitor_thread = threading.Thread(target=monitor_positions, daemon=True)
    monitor_thread.start()
    print("[LiveLoop] Position monitor started")

    # Start WebSocket handler
    handler = PriceEventHandler(
        watchlist=watchlist,
        secret=secret,
        on_signal=on_pullback,
    )
    handler.start()

    print("[LiveLoop] Running — Ctrl+C to stop")
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        print("[LiveLoop] Stopping...")
        handler.stop()


def load_watchlist_symbols(csv_path: Path = None) -> list[str]:
    """
    Read symbols from Richard's premarket watchlist CSV.
    Falls back to today's dated watchlist, then to watchlist_latest.csv.
    Returns list of ticker symbols sorted by score (highest first).
    """
    if csv_path is None:
        csv_path = DATA_DIR / "watchlists" / "watchlist_latest.csv"

    if not csv_path.exists():
        # Try today's dated file
        today_str = datetime.now(AMSTERDAM_TZ).strftime("%Y%m%d")
        csv_path = DATA_DIR / "watchlists" / f"watchlist_{today_str}.csv"

    if not csv_path.exists():
        return []

    try:
        import csv
        symbols = []
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = row.get('symbol', '').strip().upper()
                if sym:
                    symbols.append(sym)
        return symbols
    except Exception as e:
        print(f"[Watchlist] Failed to read {csv_path}: {e}")
        return []


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Live event-driven trading loop")
    parser.add_argument("--watchlist", default=None,
                        help="Comma-separated symbols (overrides watchlist_latest.csv)")
    parser.add_argument("--secret", action="store_true",
                        help="Prompt for Alpaca secret key")
    parser.add_argument("--from-csv", type=Path,
                        default=DATA_DIR / "watchlists" / "watchlist_latest.csv",
                        help="Path to watchlist CSV (default: watchlist_latest.csv)")
    args = parser.parse_args()

    # Resolve symbols: CLI arg > CSV > nothing
    if args.watchlist:
        symbols = [s.strip().upper() for s in args.watchlist.split(",") if s.strip()]
        print(f"[LiveLoop] Using CLI symbols: {symbols}")
    else:
        symbols = load_watchlist_symbols(args.from_csv)
        if symbols:
            print(f"[LiveLoop] Loaded {len(symbols)} symbols from {args.from_csv.name}: {symbols}")
        else:
            print("[LiveLoop] No watchlist found — use --watchlist or ensure Richard's premarket ran today")
            symbols = []

    if not symbols:
        parser.print_help()
        print("\nNo symbols available. Options:")
        print("  1. Run Richard's premarket screener first:")
        print("     py -3 trading_agent\\premarket_screener.py --save")
        print("  2. Or pass symbols manually:")
        print("     py -3 trading_agent\\live_event_loop.py --watchlist AAPL,TSLA --secret")
    elif args.secret:
        from alpaca_connector import get_secret_from_kay
        lock_file = DATA_DIR / ".live_loop.lock"
        import os
        # Guard: refuse to double-start
        if lock_file.exists():
            try:
                pid = int(lock_file.read_text().strip())
                os.kill(pid, 0)  # check if still alive
                print(f"[LiveLoop] Already running (PID {pid}) — refusing to start again.")
                print(f"           Stop it first, then restart.")
                return
            except (ValueError, OSError, ProcessLookupError):
                pass  # stale lock, proceed normally
        # Write PID so crash detection works next time
        lock_file.write_text(str(os.getpid()))
        try:
            secret = get_secret_from_kay()
            start_live_loop(symbols, secret)
        finally:
            lock_file.unlink(missing_ok=True)  # always clean up on exit
    else:
        parser.print_help()