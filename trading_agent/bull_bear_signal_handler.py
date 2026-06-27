"""
bull_bear_signal_handler.py
===========================
Handles post-debate actions: auto-open, notify Kay, update positions.

LLM calls live in the Mavis scan-market cron session (has real API key).
This script reads debate results from the shared JSON file written by that session.

Usage:
    python bull_bear_signal_handler.py
"""

import json, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

# Config
DATA_DIR = Path(r'E:\Me\TradingAgent\data')
POSITIONS_FILE = DATA_DIR / 'positions.json'
DEBATE_RESULTS_FILE = DATA_DIR / 'bull_bear_results.json'
CONVICTION_THRESHOLD = 7.0  # Auto-open only if conviction >= this
AMSTERDAM_TZ = timezone(timedelta(hours=2))

sys.path.insert(0, str(Path(__file__).parent))
from bull_bear_prompts import BullBearSignal, extract_score, extract_verdict


# ── Debate Results Reader ──────────────────────────────────────────────────────

def get_latest_debate_results() -> list[dict]:
    """Read debate results written by the Mavis scan-market cron session."""
    if not DEBATE_RESULTS_FILE.exists():
        return []
    try:
        with open(DEBATE_RESULTS_FILE, encoding='utf-8') as f:
            data = json.load(f)
        return data.get('debates', [])
    except Exception:
        return []


# ── Positions Guard ─────────────────────────────────────────────────────────────

def get_open_symbols() -> set:
    if not POSITIONS_FILE.exists():
        return set()
    try:
        with open(POSITIONS_FILE) as f:
            state = json.load(f)
        return {
            sym for sym, pos in state.get('positions', {}).items()
            if pos.get('status') == 'OPEN'
        }
    except Exception:
        return set()


# ── Actions ────────────────────────────────────────────────────────────────────

def auto_open(result: dict):
    """Open position via trader_agent.open_position."""
    from trading_agent.trader_agent import open_position
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
        signal_type='First Pullback + Bull/Bear'
    )
    if opened:
        send_telegram(
            f"🚀 AUTO-OPENED via Bull/Bear:\n"
            f"{sig['symbol']} LONG {sig.get('qty', 100)} @ ${sig['price']}\n"
            f"Target: ${sig['target']} (+${sig.get('target_amount', 0.20)}) | "
            f"Stop: ${sig['stop']} (-${sig.get('stop_amount', 0.10)})\n"
            f"Conviction: {result.get('conviction', 7)}/10 | R:R = {sig.get('risk_reward', 2.0)}:1"
        )


def notify_kay(result: dict):
    """Notify Kay via Telegram for manual decision."""
    sig = result.get('signal', result)
    bull = result.get('bull', '')
    bear = result.get('bear', '')
    rm = result.get('research_manager', '')

    # Summarize the debate for Kay
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


def send_telegram(message: str):
    """Send via telegram_sender."""
    try:
        from telegram_sender import send_message as tg_send
        tg_send(message)
    except Exception as e:
        print(f"[Telegram error] {e}")


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    print(f"[Bull/Bear Handler] Starting — {datetime.now(AMSTERDAM_TZ).strftime('%H:%M:%S')}")

    # Check for open positions
    held = get_open_symbols()
    if held:
        print(f"[Bull/Bear] Already in position: {held} — skipping")
        return

    # Read debate results written by Mavis cron session
    debates = get_latest_debate_results()
    if not debates:
        print("[Bull/Bear] No debate results found — session may still be running")
        return

    print(f"[Bull/Bear] Processing {len(debates)} debate result(s)...")

    for result in debates:
        sym = result.get('symbol', 'UNKNOWN')
        verdict = result.get('verdict', 'SKIP')
        conviction = result.get('conviction', 5.0)

        if verdict == 'APPROVE' and conviction >= CONVICTION_THRESHOLD:
            print(f"[Bull/Bear] {sym}: AUTO-OPEN (conviction {conviction}/10)")
            auto_open(result)
        elif verdict == 'APPROVE':
            print(f"[Bull/Bear] {sym}: Notify Kay (conviction {conviction}/10)")
            notify_kay(result)
        else:
            print(f"[Bull/Bear] {sym}: SKIPPED (conviction {conviction}/10)")

    print(f"[Bull/Bear] Done — {datetime.now(AMSTERDAM_TZ).strftime('%H:%M:%S')}")


if __name__ == '__main__':
    main()
