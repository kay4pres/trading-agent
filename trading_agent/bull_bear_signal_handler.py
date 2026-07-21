"""
bull_bear_signal_handler.py
===========================
Utility module for Bull/Bear debate actions.
Imported by live_event_loop.py and bull_bear_runner.py.

Functions:
    get_open_symbols()     — symbols currently in open positions
    get_latest_debate_results() — read bull_bear_results.json
    auto_open(result)     — open a position from a debate result
    notify_kay(result)    — send debate summary to Kay via Telegram
    send_telegram(msg)    — raw Telegram send

The canonical entry point for the Bull/Bear → position pipeline is:
    live_event_loop.py  (event-driven, uses PriceEventHandler + monitor thread)
"""

import json
import os
import sys
from pathlib import Path

# Config — UTA/Docker: TRADING_DATA_DIR env var; Local: ~/TradingAgent/data
_DATA_ROOT = os.environ.get('TRADING_DATA_DIR', '').strip()
DATA_DIR = Path(_DATA_ROOT) if _DATA_ROOT else Path.home() / 'TradingAgent' / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)
POSITIONS_FILE = DATA_DIR / 'positions.json'
DEBATE_RESULTS_FILE = DATA_DIR / 'bull_bear_results.json'
CONVICTION_THRESHOLD = 7.0  # Auto-open only if conviction >= this

sys.path.insert(0, str(Path(__file__).parent))


# ── Positions Guard ─────────────────────────────────────────────────────────────

def get_open_symbols() -> set:
    """Return symbols of all currently open positions."""
    if not POSITIONS_FILE.exists():
        return set()
    try:
        with open(POSITIONS_FILE, encoding='utf-8') as f:
            state = json.load(f)
        return {
            sym for sym, pos in state.get('positions', {}).items()
            if pos.get('status') == 'OPEN'
        }
    except Exception:
        return set()


# ── Debate Results Reader ──────────────────────────────────────────────────────

def get_latest_debate_results() -> list[dict]:
    """Read pending debate results from bull_bear_results.json."""
    if not DEBATE_RESULTS_FILE.exists():
        return []
    try:
        with open(DEBATE_RESULTS_FILE, encoding='utf-8') as f:
            data = json.load(f)
        return data.get('debates', [])
    except Exception:
        return []


# ── Actions ────────────────────────────────────────────────────────────────────

def send_telegram(message: str):
    """Send a message to Kay's Trading Team via telegram_sender."""
    try:
        from telegram_sender import send_message as tg_send
        tg_send(message)
    except Exception as e:
        print(f"[Telegram error] {e}")


def auto_open(result: dict):
    """Open a position from a debate result. Sends Telegram notification on success."""
    from trader_agent import open_position
    sig = result.get('signal', result)
    opened = open_position(
        symbol=sig['symbol'],
        direction='long',
        entry_price=sig['price'],
        quantity=sig.get('qty', 100),
        target=sig['target'],
        stop=sig['stop'],
        signal_score=sig.get('score', 5.0),
        rules_applied=['P1', 'P2', 'P3', 'P4', 'P5'],
        signal_type=f"First Pullback + Bull/Bear (conviction {result.get('conviction', '?')}/10)"
    )
    if opened:
        send_telegram(
            f"🚀 AUTO-OPENED\n"
            f"{sig['symbol']} LONG {sig.get('qty', 100)} @ ${sig['price']}\n"
            f"Target: ${sig['target']} | Stop: ${sig['stop']}\n"
            f"Conviction: {result.get('conviction', 7)}/10 | R:R = {sig.get('risk_reward', 2.0)}:1"
        )


def notify_kay(result: dict):
    """Send a debate summary to Kay for manual decision."""
    sig = result.get('signal', result)
    bull = result.get('bull', '')
    bear = result.get('bear', '')
    rm = result.get('research_manager', '')

    bull_summary = bull[:200] if bull else 'N/A'
    bear_summary = bear[:200] if bear else 'N/A'
    rm_summary = rm[:300] if rm else 'N/A'

    send_telegram(
        f"📊 Bull/Bear Alert — {sig['symbol']}\n"
        f"Score: {sig.get('score', '?')}/5 | Conviction: {result.get('conviction', '?')}/10\n"
        f"Verdict: {result.get('verdict', '?')}\n"
        f"{sig['symbol']} @ ${sig['price']} | Gap: +{sig.get('gap_pct', 0)}%\n"
        f"Target: ${sig['target']} | Stop: ${sig['stop']} | R:R = {sig.get('risk_reward', '?')}:1\n"
        f"─── Bull Case ───\n{bull_summary}\n"
        f"─── Bear Case ───\n{bear_summary}\n"
        f"─── Research Manager ───\n{rm_summary}"
    )
