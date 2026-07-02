"""
bull_bear_debate.py
===================
Richard's Bull/Bear debate — entry quality filter before Trader opens a position.

Flow:
  1. Richard finds signal (score ≥ threshold, e.g. 4.5)
  2. Bull argument: why this is a valid Ross Cameron First Pullback right now
  3. Bear argument: why this fails a rule or is too risky
  4. Research Manager: synthesize, score conviction (0-10), recommend APPROVE/SKIP
  5. Kay reviews — if conviction >= 7, Trader opens position

Token cost: ~4 LLM calls per debate (~0.01 USD)
Triggered only on high-confidence Richard signals (score ≥ 4.5)
"""

import json, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ── Config — UTA/Docker: TRADING_DATA_DIR env var; Local: E:\Me\TradingAgent\data
_DATA_ROOT = os.environ.get('TRADING_DATA_DIR', '').strip()
DATA_DIR   = Path(_DATA_ROOT) if _DATA_ROOT else Path(r'E:\Me\TradingAgent\data')
DATA_DIR.mkdir(parents=True, exist_ok=True)
POSITIONS_FILE = DATA_DIR / 'positions.json'
CONVICTION_THRESHOLD = 7.0   # Only open if conviction >= this
MIN_SCORE_TO_DEBATE = 4.5   # Only debate signals this strong or stronger

AMSTERDAM_TZ = timezone(timedelta(hours=2))


def load_llm():
    """Lazy-load the LLM caller."""
    sys.path.insert(0, str(Path(__file__).parent))
    from fincept_connector import get_batch_quotes
    return None  # placeholder — use mavis.llm_call skill when integrated


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

BULL_PROMPT = """You are Bull — a rigorous Ross Cameron day trading analyst.
Your job: argue WHY the following signal is a VALID First Pullback entry right now.
Be specific. Cite exact rules from Ross Cameron. If a rule is not met, say so honestly.

---
SIGNAL:
  Symbol:     {symbol}
  Price:      ${price}
  Gap:        +{gap_pct}% (from yesterday close ${yesterday_close})
  Float:      {float_m}M shares
  Rel Volume: {rel_vol}x average
  RSI:        {rsi} (5-min)
  News:       {news}
  Score:      {score}/5

FIVE PILLARS (Richard's scoring):
  P1 Gap/Catalyst: {p1}
  P2 Price/Float:  {p2}
  P3 Volume:       {p3}
  P4 Catalyst:     {p4}
  P5 Setup:        {p5}

---
YOUR TASK:
Evaluate each of these Ross Cameron rules for THIS specific trade:

1. GAP RULE: Stock must gap up {gap_min}%+ on catalyst. Partial gaps need confirmation.
   - What caused the gap? Is the catalyst real?

2. FLOAT RULE: Nano (<1M) or Micro (1-5M) float preferred. Larger = harder to move.
   - Is float small enough for this price range?

3. VOLUME RULE: Relative volume 2x+ average. Volume confirms the move.
   - Is volume strong enough to confirm the gap?

4. FIRST PULLBACK PATTERN: Gap → pullback → first candle making new highs = BUY.
   - Where is the pullback happening? Is this truly the FIRST pullback?
   - Has it already run? Is price extended?

5. CATALYST RULE: News, earnings, FDA, upgrade, contract — something real drove the gap.
   - Is there a verifiable catalyst?

6. 2-MINUTE RULE (pre-entry): If price doesn't make a new high within 2 minutes of entry, exit immediately.
   - Would this pass the 2-min discipline?

7. 2:1 REWARD/RISK: Target must be 2x the stop distance.
   - Target: +${target} | Stop: -${stop} | Ratio: {risk_reward}:1

Respond in this exact format:
BULL_CASE:
  [Your clearest, strongest argument for why THIS trade passes Ross's rules right now]
RULE_CHECK:
  - GAP: PASS/FAIL — [reason]
  - FLOAT: PASS/FAIL — [reason]
  - VOLUME: PASS/FAIL — [reason]
  - PULLBACK: PASS/FAIL — [reason]
  - CATALYST: PASS/FAIL — [reason]
  - 2MIN: PASS/FAIL — [reason]
  - RISK_REWARD: PASS/FAIL — [reason]
CONVICTION: [0-10 integer — how strongly you believe this is a valid entry right now]
"""


BEAR_PROMPT = """You are Bear — a skeptical Ross Cameron risk manager.
Your job: find every reason this signal should be SKIPPED.
Be brutal. Ross Cameron traders lose money when they ignore red flags. Find them.

---
SIGNAL:
  Symbol:     {symbol}
  Price:      ${price}
  Gap:        +{gap_pct}% (from yesterday close ${yesterday_close})
  Float:      {float_m}M shares
  Rel Volume: {rel_vol}x average
  RSI:        {rsi} (5-min)
  News:       {news}
  Score:      {score}/5

FIVE PILLARS:
  P1 Gap/Catalyst: {p1}
  P2 Price/Float:  {p2}
  P3 Volume:       {p3}
  P4 Catalyst:     {p4}
  P5 Setup:        {p5}

---
YOUR TASK — find every reason to skip this trade:

1. GAP RED FLAGS: Gap too large (>50%) = unsustainable. Gap on no volume = fake.
   Gap already filled? Price already fading?

2. FLOAT RED FLAGS: Large float (20M+) = hard to move, institutions will fade you.
   Low float = explosive but one-way tickets.

3. VOLUME RED FLAGS: Volume weaker than average = no conviction behind the move.
   Volume too light for the price range?

4. PULLBACK RED FLAGS: Second pullback? Already made the run? Extended too far?
   Was the first pullback too deep (超过 50%)?

5. CATALYST RED FLAGS: No catalyst = random float. Fake news? Rumor?
   Catalyst already priced in?

6. RISK/REWARD RED FLAGS: Can you actually hit the target from here?
   Is the reward realistic given current price action?

7. MARKET CONDITIONS: Is this during a bull market continuation or a reversal day?
   Is the broader market working against this trade?

Respond in this exact format:
BEAR_CASE:
  [Your strongest arguments for why this trade should be SKIPPED]
RULE_CHECK:
  - GAP: RED FLAG/NO FLAG — [specific problem or "clean"]
  - FLOAT: RED FLAG/NO FLAG — [specific problem or "clean"]
  - VOLUME: RED FLAG/NO FLAG — [specific problem or "clean"]
  - PULLBACK: RED FLAG/NO FLAG — [specific problem or "clean"]
  - CATALYST: RED FLAG/NO FLAG — [specific problem or "clean"]
  - RISK_REWARD: RED FLAG/NO FLAG — [specific problem or "clean"]
  - MARKET: RED FLAG/NO FLAG — [specific problem or "clean"]
CONVICTION_HOLD: [0-10 integer — how strongly you believe this should be SKIPPED]
"""


RESEARCH_MANAGER_PROMPT = """You are the Research Manager — objective synthesizer.
Bull argued this is a valid trade. Bear argued it should be skipped.
Your job: weigh both sides and give a clear, disciplined verdict.

---
BULL ARGUMENT:
{bull_response}

---
BEAR ARGUMENT:
{bear_response}

---
ORIGINAL SIGNAL:
  Symbol: {symbol} @ ${price} | Score: {score}/5
  Gap: +{gap_pct}% | Float: {float_m}M | RelVol: {rel_vol}x

---
SYNTHESIS:
  [Weigh Bull's strongest points against Bear's strongest points.
   Which rules are actually violated? Which are borderline?
   What would Ross Cameron do here?]

BULL_STRONGEST: [1-2 sentences — Bull's best argument]
BEAR_STRONGEST: [1-2 sentences — Bear's best counter]
DECISION_FACTOR: [The single most important factor in this decision]
CONVICTION_SCORE: [0-10 — your confidence this is a good trade RIGHT NOW]
FINAL_VERDICT: APPROVE or SKIP
REASONING: [2-4 sentences — why APPROVE or why SKIP]
IF_APPROVE:
  Entry: ${entry} | Target: ${target} | Stop: ${stop} | Qty: 100 shares
  Max risk: ${max_risk} | Max reward: ${max_reward} | R:R = {risk_reward}:1
IF_SKIP:
  Next action: [what would need to change for this to be a valid trade]
"""


# ═══════════════════════════════════════════════════════════════════════════════
# DEBATE RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_debate(signal: dict, llm_call_fn) -> dict:
    """
    Run the full Bull/Bear/Research Manager debate on a Richard signal.
    Returns dict with verdict, conviction, bull/bear arguments.

    signal = {
        'symbol', 'price', 'yesterday_close', 'gap_pct',
        'float_m', 'rel_vol', 'rsi', 'news', 'score',
        'p1', 'p2', 'p3', 'p4', 'p5',
        'target', 'stop', 'qty'
    }
    """
    symbol = signal['symbol']
    stop_dist = round(signal['price'] - signal['stop'], 4)
    target_dist = round(signal['target'] - signal['price'], 4)
    rr = round(target_dist / stop_dist, 1) if stop_dist > 0 else 0

    # Fill template vars
    vars_ = {
        **signal,
        'stop': signal['stop'],
        'target': signal['target'],
        'risk_reward': rr,
        'max_risk': round(stop_dist * signal['qty'], 2),
        'max_reward': round(target_dist * signal['qty'], 2),
        'entry': signal['price'],
    }

    # Step 1: Bull
    print(f"[Bull/Bear] Running debate for {symbol}...")
    bull_resp = llm_call_fn(BULL_PROMPT.format(**vars_))

    # Step 2: Bear
    bear_resp = llm_call_fn(BEAR_PROMPT.format(**vars_))

    # Step 3: Research Manager
    rm_vars = {**vars_, 'bull_response': bull_resp, 'bear_response': bear_resp}
    rm_resp = llm_call_fn(RESEARCH_MANAGER_PROMPT.format(**rm_vars))

    # Parse conviction from RM response
    conviction = _extract_score(rm_resp, 'CONVICTION_SCORE')
    verdict = _extract_word(rm_resp, 'FINAL_VERDICT')

    result = {
        'symbol': symbol,
        'debate_time': datetime.now(AMSTERDAM_TZ).isoformat(),
        'bull': bull_resp,
        'bear': bear_resp,
        'research_manager': rm_resp,
        'conviction': conviction,
        'verdict': verdict,
        'signal': signal,
    }

    # Auto-open if conviction is high (alpha mode — no human approval needed)
    if conviction >= CONVICTION_THRESHOLD and verdict == 'APPROVE':
        _auto_open(result)
    else:
        print(f"[Bull/Bear] {symbol}: {verdict} (conviction {conviction}/10) — no auto-open")

    return result


def _extract_score(text: str, key: str) -> float:
    """Extract a numeric score from LLM response."""
    for line in text.split('\n'):
        if key in line:
            parts = line.split(':')
            if len(parts) > 1:
                try:
                    return float(parts[1].strip())
                except ValueError:
                    pass
    return 5.0  # default


def _extract_word(text: str, key: str) -> str:
    """Extract a word (APPROVE/SKIP) from LLM response."""
    for line in text.split('\n'):
        if key in line.upper():
            for word in line.split():
                if word in ('APPROVE', 'SKIP'):
                    return word
    return 'SKIP'


def _auto_open(debate_result: dict):
    """Auto-open position if conviction is high enough. Alpha mode only."""
    from trader_agent import open_position

    sig = debate_result['signal']
    result = open_position(
        symbol=sig['symbol'],
        direction='long',
        entry_price=sig['price'],
        quantity=sig.get('qty', 100),
        target=sig['target'],
        stop=sig['stop'],
        signal_score=sig['score'],
        rules_applied=[f"P{i}" for i in range(1, 6) if sig.get(f"p{i}")],
        signal_type='First Pullback + Bull/Bear Debate'
    )
    if result:
        print(f"[Bull/Bear] AUTO-OPENED {sig['symbol']} @ ${sig['price']} — conviction {debate_result['conviction']}/10")


def format_debate_report(debate_result: dict) -> str:
    """Format debate result as a readable Telegram/IM report."""
    sig = debate_result['signal']
    verdict = debate_result['verdict']
    conviction = debate_result['conviction']
    emoji = "✅ APPROVE" if verdict == "APPROVE" else "❌ SKIP"

    lines = [
        f"━━━ BULL/BEAR DEBATE: {sig['symbol']} ━━━",
        f"Score: {sig['score']}/5 | Conviction: {conviction}/10",
        f"Verdict: {emoji}",
        "",
        f"📊 Entry: ${sig['price']} | Target: ${sig['target']} | Stop: ${sig['stop']}",
        f"   Gap: +{sig['gap_pct']}% | Float: {sig['float_m']}M | RelVol: {sig['rel_vol']}x",
        "",
        f"🐂 BULL: {debate_result['bull'][:300]}...",
        "",
        f"🐻 BEAR: {debate_result['bear'][:300]}...",
        "",
        f"📋 RM: {debate_result['research_manager'][:400]}...",
    ]
    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Example signal — replace with actual Richard output
    test_signal = {
        'symbol': 'MULN',
        'price': 4.20,
        'yesterday_close': 3.85,
        'gap_pct': 9.1,
        'float_m': 3.2,
        'rel_vol': 4.1,
        'rsi': 62,
        'news': 'FDA approval announced pre-market',
        'score': 4.5,
        'p1': 'PASS — gap 9.1% on FDA catalyst',
        'p2': 'PASS — micro float 3.2M',
        'p3': 'PASS — rel vol 4.1x',
        'p4': 'PASS — FDA catalyst',
        'p5': 'PASS — first pullback forming',
        'target': 4.40,
        'stop': 4.10,
        'qty': 100,
    }
    print("Bull/Bear debate module loaded. Use run_debate(signal, llm_fn) to run.")
    print(f"Test signal: {test_signal['symbol']} @ ${test_signal['price']}")
