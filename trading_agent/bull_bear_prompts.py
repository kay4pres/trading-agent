"""
bull_bear_prompts.py
====================
Shared prompt templates for the Bull/Bear/Research Manager debate.
Used by:
  - bull_bear_signal_handler.py (for enrichment/parsing helpers)
  - scan-market cron (for inline Mavis session LLM calls)

The actual LLM calls live in the Mavis session (scan-market cron),
not in a subprocess — this avoids the config.yaml / 401 issue.
"""

from dataclasses import dataclass


@dataclass
class BullBearSignal:
    symbol: str
    price: float
    today_close: float
    yesterday_close: float
    gap_pct: float
    float_m: float
    rel_vol: float
    rsi: float
    news: str
    score: float
    target: float
    stop: float
    qty: int = 100
    # Computed
    target_amount: float = 0.0
    stop_amount: float = 0.0
    risk_reward: float = 0.0
    max_risk: float = 0.0
    max_reward: float = 0.0

    def compute_rr(self):
        self.target_amount = round(self.target - self.price, 2)
        self.stop_amount = round(self.price - self.stop, 2)
        self.risk_reward = round(
            self.target_amount / self.stop_amount, 1
        ) if self.stop_amount > 0 else 0.0
        self.max_risk = round(self.stop_amount * self.qty, 2)
        self.max_reward = round(self.target_amount * self.qty, 2)
        return self


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

Respond with this EXACT format:
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

Respond with this EXACT format:
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

Respond with this EXACT format:
SYNTHESIS: [weigh both sides — which rules are actually violated?]
BULL_STRONGEST: [1-2 sentences]
BEAR_STRONGEST: [1-2 sentences]
DECISION_FACTOR: [single most important factor]
CONVICTION_SCORE: [0-10]
FINAL_VERDICT: APPROVE or SKIP
REASONING: [2-4 sentences]
IF_APPROVE:
  Entry: ${entry} | Target: ${target} | Stop: ${stop} | Qty: 100 shares
  Max risk: ${max_risk} | Max reward: ${max_reward} | R:R = {risk_reward}:1
IF_SKIP:
  Next action: [what would need to change for this to become a valid trade]"""


def build_bull_prompt(s: BullBearSignal) -> str:
    return BULL_PROMPT.format(
        symbol=s.symbol,
        price=s.price,
        today_close=s.today_close,
        yesterday_close=s.yesterday_close,
        gap_pct=s.gap_pct,
        float_m=s.float_m,
        rel_vol=s.rel_vol,
        rsi=s.rsi,
        news=s.news,
    )


def build_bear_prompt(s: BullBearSignal) -> str:
    return BEAR_PROMPT.format(
        symbol=s.symbol,
        price=s.price,
        today_close=s.today_close,
        yesterday_close=s.yesterday_close,
        gap_pct=s.gap_pct,
        float_m=s.float_m,
        rel_vol=s.rel_vol,
        rsi=s.rsi,
        news=s.news,
    )


def build_rm_prompt(s: BullBearSignal, bull: str, bear: str) -> str:
    return RESEARCH_MANAGER_PROMPT.format(
        bull=bull,
        bear=bear,
        symbol=s.symbol,
        price=s.price,
        score=s.score,
        gap_pct=s.gap_pct,
        float_m=s.float_m,
        rel_vol=s.rel_vol,
        entry=s.price,
        target=s.target,
        stop=s.stop,
        max_risk=s.max_risk,
        max_reward=s.max_reward,
        risk_reward=s.risk_reward,
    )


def extract_score(text: str, key: str) -> float:
    for line in text.split("\n"):
        if key in line:
            parts = line.split(":")
            if len(parts) > 1:
                try:
                    return float(parts[1].strip())
                except ValueError:
                    pass
    return 5.0


def extract_verdict(text: str) -> str:
    for line in text.split("\n"):
        if "FINAL_VERDICT" in line.upper():
            for word in line.split():
                if word in ("APPROVE", "SKIP"):
                    return word
    return "SKIP"
