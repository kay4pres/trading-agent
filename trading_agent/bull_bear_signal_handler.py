"""
bull_bear_signal_handler.py
===========================
Called by scan-market cron AFTER scanner runs.
Reads latest signals JSON, filters high-conviction signals, runs Bull/Bear debate,
auto-opens positions or notifies Kay via Telegram.

Token cost: ~$0.01-0.02 per signal debated.

Usage:
    python bull_bear_signal_handler.py
    python bull_bear_signal_handler.py --symbols MIMI,AIIO  # specific symbols
"""

import json, sys, subprocess
from pathlib import Path
from datetime import datetime, date, timezone, timedelta
from typing import Optional

# Config
DATA_DIR = Path(r'E:\Me\TradingAgent\data')
POSITIONS_FILE = DATA_DIR / 'positions.json'
BULL_BEAR_THRESHOLD = 4.5   # Only debate signals this strong
CONVICTION_THRESHOLD = 7.0  # Auto-open only if conviction >= this
TELEGRAM_SCRIPT = Path(r'E:\Me\TradingAgent\trading_agent\telegram_sender.py')
AMSTERDAM_TZ = timezone(timedelta(hours=2))

sys.path.insert(0, str(Path(__file__).parent.parent / 'trading_agent'))
from fincept_connector import get_info, get_historical

# ── Prompt Templates ─────────────────────────────────────────────────────────────

BULL_PROMPT = """You are Bull — a rigorous Ross Cameron day trading analyst.
Argue WHY this is a VALID First Pullback entry RIGHT NOW. Be specific, cite Ross Cameron rules.

SIGNAL:
  Symbol: {symbol}
  Price: ${price} (today: ${today_close}, yesterday: ${yesterday_close})
  Gap: +{gap_pct}% | Float: {float_m}M | RelVol: {rel_vol}x
  RSI: {rsi} | News: {news}

Evaluate:
1. GAP: Stock gaps up on catalyst? Gap % sustainable?
2. FLOAT: Nano (<1M) or Micro (1-5M) preferred?
3. VOLUME: RelVol 2x+ confirms the move?
4. PULLBACK: Gap → pullback → first candle new highs = BUY. Is this the FIRST pullback?
5. CATALYST: Real catalyst (earnings, FDA, upgrade)?
6. 2-MIN RULE: Price discipline for 2 minutes after entry?
7. RISK/REWARD: Target +$0.20, stop $0.10-0.15 = 2:1 minimum?

Respond:
BULL_CASE: [strongest argument for this trade]
RULE_CHECK:
  - GAP: PASS/FAIL — reason
  - FLOAT: PASS/FAIL — reason
  - VOLUME: PASS/FAIL — reason
  - PULLBACK: PASS/FAIL — reason
  - CATALYST: PASS/FAIL — reason
  - 2MIN: PASS/FAIL — reason
  - RISK_REWARD: PASS/FAIL — reason
CONVICTION: [0-10 integer]"""

BEAR_PROMPT = """You are Bear — a skeptical Ross Cameron risk manager.
Find every reason this trade should be SKIPPED. Be brutal.

SIGNAL:
  Symbol: {symbol}
  Price: ${price} (today: ${today_close}, yesterday: ${yesterday_close})
  Gap: +{gap_pct}% | Float: {float_m}M | RelVol: {rel_vol}x
  RSI: {rsi} | News: {news}

Find red flags:
1. GAP: Gap too large (>50%)? Already filled? No catalyst?
2. FLOAT: Large float (20M+) = hard to move. Nano float = one-way ticket?
3. VOLUME: Volume weaker than average = no conviction?
4. PULLBACK: Second pullback? Already extended? Too deep?
5. CATALYST: No catalyst? Fake news? Already priced in?
6. RISK/REWARD: Can target actually be hit from here?
7. MARKET: Broader market working against this?

Respond:
BEAR_CASE: [strongest arguments to skip]
RULE_CHECK:
  - GAP: RED FLAG/NO FLAG — reason
  - FLOAT: RED FLAG/NO FLAG — reason
  - VOLUME: RED FLAG/NO FLAG — reason
  - PULLBACK: RED FLAG/NO FLAG — reason
  - CATALYST: RED FLAG/NO FLAG — reason
  - RISK_REWARD: RED FLAG/NO FLAG — reason
  - MARKET: RED FLAG/NO FLAG — reason
CONVICTION_HOLD: [0-10 integer — how strongly this should be SKIPPED]"""

RESEARCH_MANAGER_PROMPT = """You are the Research Manager — objective synthesizer.
Bull argues this is valid. Bear argues it should be skipped. Give a clear verdict.

BULL: {bull}
BEAR: {bear}

ORIGINAL SIGNAL:
  {symbol} @ ${price} | Score: {score}/5
  Gap: +{gap_pct}% | Float: {float_m}M | RelVol: {rel_vol}x

SYNTHESIS: [weigh both sides — which rules are actually violated?]
BULL_STRONGEST: [1-2 sentences]
BEAR_STRONGEST: [1-2 sentences]
DECISION_FACTOR: [single most important factor]
CONVICTION_SCORE: [0-10]
FINAL_VERDICT: APPROVE or SKIP
REASONING: [2-4 sentences]
IF_APPROVE:
  Entry: ${price} | Target: ${target} | Stop: ${stop} | Qty: 100 shares
  Max risk: ${max_risk} | Max reward: ${max_reward} | R:R = {risk_reward}:1
IF_SKIP:
  Next action: [what would need to change]"""

# ── LLM Caller ──────────────────────────────────────────────────────────────────

LLM_SCRIPT = r'C:\Users\Kay\.mavis\.builtin-skills\llm-call\scripts\llm_call.py'


def llm_call(prompt: str, model: str = 'minimax/MiniMax-M2.7') -> str:
    """
    Call the configured LLM via llm_call.py.
    Uses the model configured in the daemon (MiniMax M2.7).
    """
    result = subprocess.run(
        ['py', '-3', LLM_SCRIPT, '--model', model, '--prompt', prompt],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        raise RuntimeError(f"LLM call failed: {result.stderr}")
    return result.stdout.strip()

# ── Enrichment ─────────────────────────────────────────────────────────────────

def enrich_signal(sig: dict) -> dict:
    """Add yesterday close, float, news to a signal."""
    sym = sig['ticker']
    enriched = {
        'symbol': sym,
        'price': sig.get('price', 0),
        'today_close': sig.get('price', 0),
        'yesterday_close': sig.get('yesterday_close', sig.get('price', 0)),
        'gap_pct': sig.get('gap_pct', 0),
        'float_m': sig.get('float_m', sig.get('float', '?')),
        'rel_vol': sig.get('volume_ratio', 0),
        'rsi': sig.get('rsi', 0),
        'score': sig.get('score', 0),
        'news': sig.get('news', 'No major news'),
        'target': round(sig.get('price', 0) + 0.20, 2),
        'stop': round(sig.get('price', 0) - 0.10, 2),
        'qty': 100,
    }

    # Try to get yesterday's close
    try:
        info = get_info(sym)
        if info:
            enriched['yesterday_close'] = info.get('previous_close', enriched['yesterday_close'])
    except Exception:
        pass

    enriched['target_amount'] = round(enriched['target'] - enriched['price'], 2)
    enriched['stop_amount'] = round(enriched['price'] - enriched['stop'], 2)
    rr = enriched['target_amount'] / enriched['stop_amount'] if enriched['stop_amount'] > 0 else 0
    enriched['risk_reward'] = round(rr, 1)
    enriched['max_risk'] = round(enriched['stop_amount'] * enriched['qty'], 2)
    enriched['max_reward'] = round(enriched['target_amount'] * enriched['qty'], 2)

    return enriched


# ── Debate ─────────────────────────────────────────────────────────────────────

def run_bull_bear(sig: dict) -> dict:
    """Run full Bull/Bear/Research Manager debate on a signal."""
    sym = sig['symbol']
    print(f"[Bull/Bear] Debating {sym} @ ${sig['price']} (score {sig['score']:.1f})...")

    vars_ = {
        **sig,
        'bull_prompt': BULL_PROMPT.format(**sig),
        'bear_prompt': BEAR_PROMPT.format(**sig),
    }

    # Step 1: Bull
    bull_resp = llm_call(BULL_PROMPT.format(**sig))
    print(f"[Bull] {sym}: {bull_resp[:200]}...")

    # Step 2: Bear
    bear_resp = llm_call(BEAR_PROMPT.format(**sig))
    print(f"[Bear] {sym}: {bear_resp[:200]}...")

    # Step 3: Research Manager
    rm_prompt = RESEARCH_MANAGER_PROMPT.format(
        bull=bull_resp, bear=bear_resp, **sig
    )
    rm_resp = llm_call(rm_prompt)
    print(f"[RM] {sym}: {rm_resp[:300]}...")

    # Parse conviction and verdict
    conviction = _extract_score(rm_resp, 'CONVICTION_SCORE')
    verdict = _extract_word(rm_resp, 'FINAL_VERDICT')

    return {
        'symbol': sym,
        'debate_time': datetime.now(AMSTERDAM_TZ).isoformat(),
        'bull': bull_resp,
        'bear': bear_resp,
        'research_manager': rm_resp,
        'conviction': conviction,
        'verdict': verdict,
        'signal': sig,
    }


def _extract_score(text: str, key: str) -> float:
    for line in text.split('\n'):
        if key in line:
            parts = line.split(':')
            if len(parts) > 1:
                try:
                    return float(parts[1].strip())
                except ValueError:
                    pass
    return 5.0


def _extract_word(text: str, key: str) -> str:
    for line in text.split('\n'):
        if key in line.upper():
            for word in line.split():
                if word in ('APPROVE', 'SKIP'):
                    return word
    return 'SKIP'


# ── Actions ────────────────────────────────────────────────────────────────────

def auto_open(result: dict):
    """Open position via trader_agent.open_position."""
    from trading_agent.trader_agent import open_position
    sig = result['signal']
    opened = open_position(
        symbol=sig['symbol'],
        direction='long',
        entry_price=sig['price'],
        quantity=sig['qty'],
        target=sig['target'],
        stop=sig['stop'],
        signal_score=sig['score'],
        rules_applied=['P1', 'P2', 'P3', 'P4', 'P5'],
        signal_type='First Pullback + Bull/Bear'
    )
    if opened:
        send_telegram(
            f"🚀 AUTO-OPENED via Bull/Bear:\n"
            f"{sig['symbol']} LONG {sig['qty']} @ ${sig['price']}\n"
            f"Target: ${sig['target']} (+${sig['target_amount']}) | "
            f"Stop: ${sig['stop']} (-${sig['stop_amount']})\n"
            f"Conviction: {result['conviction']}/10 | R:R = {sig['risk_reward']}:1"
        )


def notify_kay(result: dict):
    """Notify Kay via Telegram for manual decision."""
    sig = result['signal']
    send_telegram(
        f"📊 Bull/Bear Alert — {sig['symbol']}\n"
        f"Score: {sig['score']:.1f}/5 | Conviction: {result['conviction']}/10\n"
        f"Verdict: {result['verdict']}\n"
        f"{sig['symbol']} @ ${sig['price']} | Gap: +{sig['gap_pct']}%\n"
        f"Target: ${sig['target']} | Stop: ${sig['stop']}\n"
        f"R:R = {sig['risk_reward']}:1\n"
        f"Summarize the debate for me — should I open?"
    )


def send_telegram(message: str):
    """Send via telegram_sender."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / 'trading_agent'))
        from telegram_sender import send_message as tg_send
        tg_send(message)
    except Exception as e:
        print(f"[Telegram error] {e}")


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


# ── Latest Signals ──────────────────────────────────────────────────────────────

def get_latest_signals() -> list:
    """Find and read the most recent signals JSON."""
    candidates = sorted(DATA_DIR.glob('signals_*.json'), reverse=True)
    if not candidates:
        return []
    latest = candidates[0]
    with open(latest) as f:
        data = json.load(f)
    return data.get('ranked_signals', [])


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    print(f"[Bull/Bear Handler] Starting — {datetime.now(AMSTERDAM_TZ).strftime('%H:%M:%S')}")

    # Load positions
    held = get_open_symbols()
    if held:
        print(f"[Bull/Bear] Already in position: {held} — skipping debate")
        return

    # Load latest signals
    signals = get_latest_signals()
    if not signals:
        print("[Bull/Bear] No signals found")
        return

    # Filter by threshold and held symbols
    candidates = [s for s in signals if s.get('score', 0) >= BULL_BEAR_THRESHOLD and s['ticker'] not in held]
    if not candidates:
        print(f"[Bull/Bear] No signals >= {BULL_BEAR_THRESHOLD} score — skipping")
        return

    print(f"[Bull/Bear] {len(candidates)} candidate(s): {[s['ticker'] for s in candidates]}")

    for sig_raw in candidates:
        sig = enrich_signal(sig_raw)
        try:
            result = run_bull_bear(sig)
        except Exception as e:
            print(f"[Bull/Bear] Debate failed for {sig['symbol']}: {e}")
            continue

        if result['verdict'] == 'APPROVE' and result['conviction'] >= CONVICTION_THRESHOLD:
            auto_open(result)
        elif result['verdict'] == 'APPROVE':
            notify_kay(result)
        else:
            print(f"[Bull/Bear] {sig['symbol']}: SKIPPED (conviction {result['conviction']}/10)")

    print(f"[Bull/Bear] Done — {datetime.now(AMSTERDAM_TZ).strftime('%H:%M:%S')}")


if __name__ == '__main__':
    main()
