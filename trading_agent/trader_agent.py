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
    """Close position, write to history, send notification."""
    exit_price = live_price
    qty = pos["quantity"]

    if pos["direction"] == "long":
        pnl = (exit_price - pos["entry_price"]) * qty
    else:
        pnl = (pos["entry_price"] - exit_price) * qty

    pos["status"] = "CLOSED"
    pos["exited_at"] = now_amsterdam().isoformat()
    pos["exit_reason"] = reason
    pos["exit_price"] = round(exit_price, 4)
    pos["pnl"] = round(pnl, 4)
    pos["pnl_percent"] = round(pnl / (pos["entry_price"] * qty) * 100, 2)

    # Move to history
    state["history"].append(pos)
    del state["positions"][symbol]

    # Save
    save_positions(state)

    # Notify
    emoji = "✅" if pnl > 0 else "❌"
    direction = pos["direction"].upper()
    msg = (
        f"{emoji} EXIT: {symbol}\n"
        f"{direction} {qty} shares @ ${exit_price:.2f}\n"
        f"Reason: {reason}\n"
        f"P&L: ${pnl:.2f} ({pos['pnl_percent']:.1f}%)\n"
        f"Target was ${pos['target']:.2f} | Stop was ${pos['stop']:.2f}"
    )
    send_telegram(msg)

    print(f"[EXIT] {symbol} {reason} @ ${exit_price:.2f} | P&L: ${pnl:.2f}")
    return True

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

def open_position(symbol, direction, entry_price, quantity, target, stop,
                 signal_score, rules_applied, signal_type):
    """Open a new position. Called by Richard or manual entry."""
    state = load_positions()

    if symbol in state["positions"]:
        print(f"[WARN] {symbol} already in position — skipping open")
        return False

    now = now_amsterdam()
    two_min_exit = (now + timedelta(minutes=2)).isoformat()

    state["positions"][symbol] = {
        "symbol": symbol,
        "direction": direction,
        "entry_price": round(entry_price, 4),
        "quantity": quantity,
        "target": round(target, 4),
        "stop": round(stop, 4),
        "target_amount": round(target - entry_price, 4),
        "stop_amount": round(entry_price - stop, 4),
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

    save_positions(state)

    msg = (
        f"🚀 ENTRY: {symbol}\n"
        f"{direction.upper()} {quantity} shares @ ${entry_price:.2f}\n"
        f"Target: ${target:.2f} (+${target-entry_price:.2f})\n"
        f"Stop: ${stop:.2f} (-${entry_price-stop:.2f})\n"
        f"Score: {signal_score:.1f}/5 | Signal: {signal_type}"
    )
    send_telegram(msg)
    print(f"[ENTRY] {symbol} {direction.upper()} @ ${entry_price:.2f}")
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
