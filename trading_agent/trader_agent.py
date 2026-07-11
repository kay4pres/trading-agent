"""
Trader Agent — Position Monitoring Loop
Monitors open positions, executes deterministic exits, sends Telegram notifications.

Usage:
    python trader_agent.py          # start monitoring loop
    python trader_agent.py --open   # open a new position manually
    python trader_agent.py --status # print current positions
"""
import json, time, sys, os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd

# ── Alpaca Trading ──────────────────────────────────────────────────────────────
# Lazy import — alpaca-py may not be installed on all systems
_alpaca_trading = None

def _get_alpaca_trading():
    global _alpaca_trading
    if _alpaca_trading is None:
        try:
            from trading_agent.alpaca_connector import AlpacaTrading
            _alpaca_trading = AlpacaTrading
        except ImportError:
            print("[WARN] alpaca-py not installed — Alpaca execution disabled (simulated mode)")
            return None
    return _alpaca_trading

import traceback

# Config
POSITIONS_FILE = Path(r"E:\Me\TradingAgent\data\positions.json")
DATA_DIR = Path(r"E:\Me\TradingAgent\data")
TELEGRAM_MODULE = Path(r"E:\Me\TradingAgent\trading_agent\telegram_sender.py")
POLL_INTERVAL = 30  # seconds
MARKET_TZ = timezone(timedelta(hours=-5))  # ET (NY)
AMSTERDAM_TZ = timezone(timedelta(hours=2))
TELEGRAM_GROUP = "-5581171035"

def now_amsterdam():
    return datetime.now(AMSTERDAM_TZ)

def now_ny():
    return datetime.now(MARKET_TZ)

def is_market_hours():
    """Market open: 15:30 Amsterdam / 09:30 NY. Close: 22:00 Amsterdam / 16:00 NY."""
    ny = now_ny()
    if ny.weekday() >= 5:
        return False  # weekend
    ny_time = ny.time()
    from datetime import time as t
    return t(9, 30) <= ny_time <= t(16, 0)

def load_positions():
    if not POSITIONS_FILE.exists():
        return {"schema_version": "1.0", "updated_at": now_amsterdam().isoformat(), "positions": {}, "history": []}
    with open(POSITIONS_FILE) as f:
        return json.load(f)

def save_positions(state):
    state["updated_at"] = now_amsterdam().isoformat()
    with open(POSITIONS_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_live_price(symbol):
    """Get live price via yfinance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        price = ticker.fast_info.last_price
        return price
    except Exception as e:
        print(f"[WARN] Could not fetch price for {symbol}: {e}")
        return None


def get_historical(symbol, period='5d', interval='5m'):
    """Fetch 5-min bars via yfinance. Returns list of dicts with timestamp/high/low/close."""
    import yfinance as yf
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    if df.empty:
        return []
    bars = []
    for ts, row in df.iterrows():
        bars.append({
            'timestamp': ts.timestamp(),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
        })
    return bars

def get_atr(symbol):
    """
    Calculate ATR from INTRADAY 5-min bars (today's volatility).
    Uses median True Range over last 14 bars — robust to spikes on volatile days.
    This captures the stock's actual day-range, which is what Ross traders watch.
    """
    try:
        bars = get_historical(symbol, period='5d', interval='5m')
    except Exception:
        return None

    if not bars or len(bars) < 20:
        return None

    # Use today's bars only (last ~78 5-min bars = full trading day)
    today = datetime.now().strftime('%Y-%m-%d')
    today_bars = [b for b in bars if datetime.fromtimestamp(b['timestamp']).strftime('%Y-%m-%d') == today]

    use_bars = today_bars if len(today_bars) >= 10 else bars[-60:]

    tr_values = []
    for i in range(1, len(use_bars)):
        high = use_bars[i]['high']
        low = use_bars[i]['low']
        prev_close = use_bars[i-1]['close']
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)

    if len(tr_values) < 5:
        return None

    # Median is robust to single-bar spikes on volatile days
    import statistics
    atr = statistics.median(tr_values[-14:]) if len(tr_values) >= 14 else statistics.mean(tr_values[-5:])
    return round(atr, 4)


def calc_stop_target(symbol, entry_price, pullback_low=None):
    """
    Ross Cameron-style stop/target calculation.

    Rules:
    - Target: entry + $0.20 (minimum, Ross standard)
    - ATR-stop: entry - 2×ATR  (adapts to volatility)
    - Pullback-stop: pullback_low (if provided)
    - Final stop: max(ATR-stop, pullback_low)  OR entry - $0.20, whichever is tighter
    - MINIMUM 2:1 ratio: skip trade if stop would be more than $0.20 below entry
      (i.e., $0.20 must always be our minimum stop distance)
    - Wider stops only if pullback_low naturally provides it

    Returns (stop, target, skip_reason) where skip_reason is None if tradeable.
    """
    atr = get_atr(symbol)
    atr_stop = round(entry_price - 2 * atr, 2) if atr else None

    # Ross minimum: $0.20 stop distance
    ross_min_stop = round(entry_price - 0.20, 2)

    if pullback_low is not None:
        # Use pullback low as primary stop, but must be within $0.20 of entry
        if entry_price - pullback_low > 0.20:
            # Stop too wide — Ross would skip this trade
            return None, None, f"STOP_WIDE: pullback ${pullback_low:.2f} is ${entry_price - pullback_low:.2f} below entry (max $0.20)"
        stop = pullback_low
    elif atr_stop is not None:
        # Use ATR-based stop, respect Ross minimum
        if entry_price - atr_stop > 0.20:
            # ATR gives wider than $0.20 — use the tighter stop to maintain 2:1
            # This is the ATR giving us a wider stop for volatile stocks
            # But we still need 2:1: target = entry + 0.20, stop = ross_min_stop
            stop = ross_min_stop
            print(f"[WARN] {symbol}: ATR-stop ${atr_stop:.2f} wider than $0.20 minimum — using ${stop:.2f}")
        else:
            stop = atr_stop
    else:
        # No ATR data — fall back to Ross minimum
        stop = ross_min_stop

    target = round(entry_price + 0.20, 2)

    # Final 2:1 check
    stop_distance = entry_price - stop
    target_distance = target - entry_price
    if stop_distance < 0.10:
        return None, None, f"STOP_TIGHT: stop distance ${stop_distance:.2f} < $0.10 minimum"
    if target_distance / stop_distance < 2.0:
        return None, None, f"SKIP: R:R would be {target_distance/stop_distance:.1f}:1 < 2:1 required"

    return round(stop, 4), target, None

def send_telegram(message):
    """Send message to Kay's Trading Team via telegram_sender module."""
    try:
        sys.path.insert(0, str(TELEGRAM_MODULE.parent))
        from telegram_sender import send_message as tg_send
        tg_send(message)
        print(f"[Telegram] Sent: {message[:80]}")
    except Exception as e:
        print(f"[ERROR] Telegram error: {e}")

def check_exit(state, symbol, pos, live_price):
    """Check target and stop exit conditions. Returns (should_exit, reason)."""
    if live_price is None:
        return False, None

    if pos["direction"] == "long":
        if live_price >= pos["target"]:
            return True, "TARGET_HIT"
        if live_price <= pos["stop"]:
            return True, "STOP_HIT"

    return False, None

def execute_exit(state, symbol, pos, reason, live_price):
    """Close position, write to history, send notification, log to journal."""
    exit_price = live_price
    qty = pos["quantity"]

    if pos["direction"] == "long":
        pnl = (exit_price - pos["entry_price"]) * qty
    else:
        pnl = (pos["entry_price"] - exit_price) * qty

    pnl_percent = round(pnl / (pos["entry_price"] * qty) * 100, 2)
    pos["status"] = "CLOSED"
    pos["exited_at"] = now_amsterdam().isoformat()
    pos["exit_reason"] = reason
    pos["exit_price"] = round(exit_price, 4)
    pos["pnl"] = round(pnl, 4)
    pos["pnl_percent"] = pnl_percent

    # Move to history
    state["history"].append(pos)
    del state["positions"][symbol]

    # Save
    save_positions(state)

    # Log to trade journal
    _log_to_journal(symbol, pos, exit_price, reason, pnl, pnl_percent)

    # Notify
    emoji = "✅" if pnl > 0 else "❌"
    direction = pos["direction"].upper()
    msg = (
        f"{emoji} EXIT: {symbol}\n"
        f"{direction} {qty} shares @ ${exit_price:.2f}\n"
        f"Reason: {reason}\n"
        f"P&L: ${pnl:.2f} ({pnl_percent:.1f}%)\n"
        f"Target was ${pos['target']:.2f} | Stop was ${pos['stop']:.2f}"
    )
    send_telegram(msg)

    print(f"[EXIT] {symbol} {reason} @ ${exit_price:.2f} | P&L: ${pnl:.2f}")
    return True


def _log_to_journal(symbol, pos, exit_price, reason, pnl, pnl_percent):
    """Append closed trade to the trade journal."""
    try:
        from memory_logger import log_trade
        log_trade({
            "symbol": symbol,
            "action": pos.get("direction", "LONG").upper(),
            "entry_price": pos["entry_price"],
            "exit_price": round(exit_price, 4),
            "exit_reason": reason,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_percent, 2),
            "closed_at": now_amsterdam().isoformat(),
            "notes": (
                f"Signal: {pos.get('entry_signal','?')} | "
                f"Score: {pos.get('signal_score','?')}/5 | "
                f"ATR: {pos.get('atr','?')}"
            ),
        })
    except Exception as e:
        print(f"[Memory] Failed to log trade: {e}")

def check_two_min_rule(state, symbol, pos, live_price):
    """
    Check 2-minute breakout rule.
    Fires once: if price hasn't made a new high within 2 min of entry, exit at current price.
    If price IS above entry at the 2-min mark, rule passes and we clear the flag so it doesn't fire again.
    """
    TWO_MIN = timedelta(minutes=2)

    # If rule already passed (flag cleared) or not yet a long, skip
    if not pos.get("two_min_exit_time") or pos["direction"] != "long":
        return False, None

    deadline = datetime.fromisoformat(pos["two_min_exit_time"])
    if now_amsterdam() < deadline:
        return False, None  # not yet time

    # 2 minutes have passed — check if we made a new high
    if live_price > pos["entry_price"]:
        # Rule passed — price moved up, clear the flag so this only fires once
        pos["two_min_exit_time"] = None
        save_positions(state)
        print(f"[2MIN] {symbol} rule PASSED — price above entry at 2-min mark")
        return False, None
    else:
        # Rule failed — price didn't make new high, exit now
        return True, "2MIN_RULE"

def open_position(symbol, direction, entry_price, quantity, target=None, stop=None,
                 signal_score=0, rules_applied=None, signal_type="First Pullback",
                 pullback_low=None, skip_if_bad_rr=True):
    """
    Open a new position. Uses ATR-based stops automatically.

    Args:
        symbol, direction, entry_price, quantity — required
        target: if None, calculated as entry + $0.20
        stop: if None, uses ATR-based calculation
        pullback_low: if provided, used as primary stop (Ross's rule)
        skip_if_bad_rr: if True (default), skips trade when 2:1 can't be maintained
    """
    if rules_applied is None:
        rules_applied = []

    state = load_positions()
    if symbol in state["positions"]:
        print(f"[WARN] {symbol} already in position — skipping open")
        return False

    # Calculate ATR-based stop/target
    calc_stop, calc_target, skip_reason = calc_stop_target(
        symbol, entry_price, pullback_low=pullback_low
    )

    if skip_reason and skip_if_bad_rr:
        print(f"[SKIP] {symbol} @ ${entry_price:.2f} — {skip_reason}")
        send_telegram(f"⏭️ SKIPPED: {symbol} @ ${entry_price:.2f}\n{skip_reason}")
        return False

    stop = round(stop, 4) if stop is not None else calc_stop
    target = round(target, 4) if target is not None else calc_target

    if stop is None or target is None:
        print(f"[ERROR] {symbol}: could not calculate stop/target")
        return False

    atr = get_atr(symbol)
    now = now_amsterdam()
    two_min_exit = (now + timedelta(minutes=2)).isoformat()

    pos = {
        "symbol": symbol,
        "direction": direction,
        "entry_price": round(entry_price, 4),
        "quantity": quantity,
        "target": target,
        "stop": stop,
        "target_amount": round(target - entry_price, 4),
        "stop_amount": round(entry_price - stop, 4),
        "atr": atr,
        "atr_stop_distance": round(2 * atr, 4) if atr else None,
        "status": "OPEN",
        "opened_at": now.isoformat(),
        "exited_at": None,
        "exit_price": None,
        "pnl": None,
        "exit_reason": None,
        "entry_signal": signal_type,
        "signal_score": signal_score,
        "rules_applied": rules_applied,
        "premarket_watchlist": now.strftime("%Y-%m-%d"),
        "two_min_exit_time": two_min_exit,
        "entry_candle_time": None
    }

    state["positions"][symbol] = pos
    save_positions(state)

    rr = (target - entry_price) / (entry_price - stop) if entry_price != stop else 0
    msg = (
        f"🚀 ENTRY: {symbol}\n"
        f"{direction.upper()} {quantity} shares @ ${entry_price:.2f}\n"
        f"Target: ${target:.2f} (+${target-entry_price:.2f})\n"
        f"Stop: ${stop:.2f} (-${entry_price-stop:.2f}) | ATR: ${atr:.4f if atr else '?'}\n"
        f"R:R = {rr:.1f}:1 | Score: {signal_score:.1f}/5\n"
        f"{signal_type}"
    )
    send_telegram(msg)
    print(f"[ENTRY] {symbol} {direction.upper()} @ ${entry_price:.2f} | T:{target} S:{stop} | ATR:{atr} | R:R:{rr:.1f}:1")

    # ── Submit real order to Alpaca paper trading ───────────────────────────
    try:
        Alpaca = _get_alpaca_trading()
        if Alpaca is not None:
            # Map direction to order side: "long" → buy, "short" → sell
            side = "buy" if direction.lower() == "long" else "sell"
            result = Alpaca.submit_market_order(
                symbol=symbol.upper(),
                qty=quantity,
                side=side,
                dry_run=False,
            )
            print(f"[Alpaca] Order submitted: {result['order_id']} | {side.upper()} {quantity} {symbol}")
            # Attach order_id to the position for audit trail
            pos["broker_order_id"] = result["order_id"]
            save_positions(state)
        else:
            print(f"[Alpaca] SIMULATED (alpaca-py unavailable) — no broker order sent")
    except Exception as e:
        # Best-effort: log the error but don't fail the position tracking
        print(f"[Alpaca] Order submission failed: {e}")
        print(f"[Alpaca] Position IS TRACKED locally — broker order needs manual check")

    return True

def monitor_loop():
    """Main monitoring loop — polls every POLL_INTERVAL seconds during market hours."""
    print(f"[Trader] Starting monitor loop. Poll every {POLL_INTERVAL}s.")
    print(f"[Trader] Market hours check: {'ACTIVE' if is_market_hours() else 'CLOSED'}")
    print(f"[Trader] Started at {now_amsterdam().strftime('%H:%M:%S')}")

    while True:
        try:
            if not is_market_hours():
                # Outside market hours — sleep longer
                time.sleep(60)
                continue

            state = load_positions()
            if not state["positions"]:
                time.sleep(POLL_INTERVAL)
                continue

            for symbol, pos in list(state["positions"].items()):
                if pos["status"] != "OPEN":
                    continue

                live_price = get_live_price(symbol)
                if live_price is None:
                    time.sleep(POLL_INTERVAL)
                    continue

                print(f"[Monitor] {symbol}: ${live_price:.2f} | Target: ${pos['target']:.2f} | Stop: ${pos['stop']:.2f}")

                # Check 2-min rule first
                should_exit_2min, reason_2min = check_two_min_rule(state, symbol, pos, live_price)
                if should_exit_2min:
                    execute_exit(state, symbol, pos, reason_2min, live_price)
                    continue

                # Check target / stop
                should_exit, reason = check_exit(state, symbol, pos, live_price)
                if should_exit:
                    execute_exit(state, symbol, pos, reason, live_price)
                    continue

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("[Trader] Interrupted — saving state and exiting.")
            break
        except Exception as e:
            print(f"[ERROR] Monitor loop error: {e}")
            time.sleep(POLL_INTERVAL)


def poll_once():
    """Single poll cycle — one check on all positions, then exit. For cron use."""
    if not is_market_hours():
        print(f"[Trader] Outside market hours — skipping poll.")
        return

    state = load_positions()
    if not state["positions"]:
        print(f"[Trader] No open positions.")
        return

    for symbol, pos in list(state["positions"].items()):
        if pos["status"] != "OPEN":
            continue
        live_price = get_live_price(symbol)
        if live_price is None:
            continue
        print(f"[Poll] {symbol}: ${live_price:.2f} | Target: ${pos['target']:.2f} | Stop: ${pos['stop']:.2f}")
        should_exit_2min, reason_2min = check_two_min_rule(state, symbol, pos, live_price)
        if should_exit_2min:
            execute_exit(state, symbol, pos, reason_2min, live_price)
            continue
        should_exit, reason = check_exit(state, symbol, pos, live_price)
        if should_exit:
            execute_exit(state, symbol, pos, reason, live_price)
            continue

def print_status():
    """Print current positions and exit. Call with: python trader_agent.py --status"""
    state = load_positions()
    print(f"\n=== Trader Status ({now_amsterdam().strftime('%H:%M:%S')}) ===")
    print(f"Schema: {state['schema_version']}")
    print(f"Updated: {state['updated_at']}")
    print(f"Open positions: {len(state['positions'])}")
    print(f"Closed this session: {len(state['history'])}")
    for symbol, pos in state["positions"].items():
        print(f"\n  {symbol} | {pos['direction']} | {pos['quantity']} shares")
        print(f"    Entry: ${pos['entry_price']} @ {pos['opened_at']}")
        print(f"    Target: ${pos['target']} | Stop: ${pos['stop']}")
        print(f"    Status: {pos['status']} | Score: {pos['signal_score']}")
    if state["history"]:
        print(f"\n  Closed positions:")
        for h in state["history"][-5:]:
            print(f"    {h['symbol']} | {h['direction']} | ${h.get('exit_price','?')} | {h['exit_reason']} | P&L: ${h.get('pnl','?')}")
    print()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print_status()
    elif len(sys.argv) > 1 and sys.argv[1] == "--poll-once":
        poll_once()
    else:
        monitor_loop()
