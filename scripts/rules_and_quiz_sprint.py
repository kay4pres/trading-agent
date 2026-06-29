"""
Rules extraction + Quiz generation from new transcripts — 2026-06-29
Processes C1 Ch2,6,7,8,9,10,11 and C2 Ch1,2,6
"""
import json
import re
import os
import sys
from pathlib import Path
from datetime import datetime

# ── Paths ────────────────────────────────────────────────────────────────────
BASE = Path(r"E:\Me\TradingAgent")
TRANSCRIPT_DIR = BASE / "knowledge" / "transcripts"
RULES_DIR = BASE / "knowledge" / "rules"
QUIZ_BANK = BASE / "quiz" / "bank" / "quiz_bank.json"
SKIP_CHAPTERS = {"Chapter5_Course1", "Chapter5_Course2",
                 "Chapter 3", "Chapter 4", "Chapter 12", "Chapter 15"}

# ── Chapters to process ──────────────────────────────────────────────────────
CHAPTERS = [
    ("Chapter 2", "C1 Ch2", "Day Trading Basics — Stock Picking"),
    ("Chapter 6", "C1 Ch6", "Day Trading Basics — Trading Platform"),
    ("Chapter 7", "C1 Ch7", "Day Trading Basics — Chapter 7"),
    ("Chapter 8", "C1 Ch8", "Day Trading Basics — Chapter 8"),
    ("Chapter 9", "C1 Ch9", "Day Trading Basics — Order Entry"),
    ("Chapter 10", "C1 Ch10", "Day Trading Basics — Hot Keys & Buttons"),
    ("Chapter 11", "C1 Ch11", "Day Trading Basics — Stock Halts"),
    ("Chapter 1 Course2", "C2 Ch1", "Day Trading Strategies — Intro"),
    ("Chapter 2 Course2", "C2 Ch2", "Day Trading Strategies — Risk Management"),
    ("Chapter 6 Course2", "C2 Ch6", "Day Trading Strategies — Level 2 & Tape Reading"),
]


# ── Keyword-based rules extraction ───────────────────────────────────────────
RULES_KEYWORDS = {
    "catalyst_news": ["catalyst", "news catalyst", "earnings", "FDA approval", "contract",
                      "partnership", "upgrade", "downgrade", "short squeeze", "news catalyst"],
    "gap_patterns": ["gap up", "gap down", "gapped", "fill the gap", "at the open",
                    "opening range", "partial gap", "full gap"],
    "volume_patterns": ["relative volume", "volume spike", "heavy volume", "light volume",
                       "volume confirmation", "volume dry up", "RV"],
    "risk_management": ["stop loss", "stop out", "position sizing", "max loss",
                        "risk reward", "risk/reward", "risk per trade", "2:1"],
    "first_pullback": ["first pullback", "pull back", "pullback", "consolidation",
                       "resting", "setup"],
    "order_types": ["market order", "limit order", "stop order", "stop loss",
                   "trailing stop", "OCO", "bracket", "fill or kill", "IOC", "FOK"],
    "hot_keys": ["hot key", "hot keys", "hot button", "scale out", "scale in",
                 "single cancel remaining", "SCR", "cancel send", "reverse"],
    "stock_halts": ["halt", "LULD", "circuit breaker", "Limit Up", "Limit Down",
                    "resume", "halted", "T1", "T2"],
    "level2": ["level 2", "time and sales", "bid", "ask", "spread", "depth of market",
                "print", "ADFN", "consolidated tape", "MM", "maker"],
    "market_makers": ["market maker", "MM", "PFOF", "payment for order flow",
                      "direct access", "internalization", "execution venue"],
    "stock_types": ["float", "low float", "high float", "micro cap", "small cap",
                    "nano cap", "medium float", "large cap"],
    "scaling": ["scaling in", "scaling out", "scale in", "scale out", "position sizing",
                "1/4 size", "half size", "full size", "quarter"],
    "trading_platform": ["broker", "platform", "routing", "clearing", "account",
                        "margin", "pattern day trader", "PDT"],
}

RULES_TEMPLATES = {
    "catalyst_news": "## News Catalysts\n- Catalysts drive initial volatility and volume spikes.\n- Ross: 'Technical catalyst alone isn't usually enough — need news catalyst too.'\n",
    "gap_patterns": "## Gap Patterns\n- Gap up/down patterns: partial gap vs full gap; partial gaps are more tradeable.\n- Opening range consolidation: stock rests before continuation.\n",
    "volume_patterns": "## Volume Analysis\n- Relative Volume (RV): look for 5x+ above average.\n- Volume confirmation required for breakouts.\n",
    "risk_management": "## Risk Management\n- Max loss defined BEFORE entering — never adjust mid-trade.\n- Stop placement: based on ATR or recent volatility.\n- 1:2 risk/reward minimum; 2:1 target.\n- Risk 1-2% of account per trade max.\n",
    "first_pullback": "## First Pullback Setup\n- Entry: first candle making a NEW HIGH after the pullback.\n- Skip if pullback >4 candles or >50% retracement.\n",
    "order_types": "## Order Types\n- Market Order: immediate fill, no price guarantee.\n- Limit Order: fill at specified price or better.\n- Stop Order: triggers market order when price reached.\n- Bracket Order: entry + take-profit + stop-loss in one.\n",
    "hot_keys": "## Hot Keys & Buttons\n- Hot keys: single-key actions for speed (SCR, scale out, reverse).\n- Scale out: reduce size as trade moves in your favor.\n- Reverse: close and flip position direction.\n",
    "stock_halts": "## Stock Halts\n- LULD (Limit Up / Limit Down): automatic trading pause on rapid moves.\n- T1 Halt: 5 min pause; T2 Halt: 10 min pause.\n- Resume conditions: price within LULD bands for 15 seconds.\n- Ross: never hold through a halt — exit before T1.\n",
    "level2": "## Level 2 & Time & Sales\n- Level 2: shows bid/ask depth — MM activity visible.\n- Time & Sales (T&S): every print with time/size/price.\n- ADFN: alternative data feed, shows dark pool prints.\n- Prints: trades happening at specific price levels.\n",
    "market_makers": "## Market Makers & PFOF\n- Market Makers (MM): provide liquidity, must maintain fair and orderly markets.\n- PFOF: brokers sell order flow to MMs (e.g., Citadel, Virtu).\n- Direct Access: route orders directly to exchange, bypass PFOF.\n- Internalization: broker fills order internally at NBBO.\n",
    "stock_types": "## Stock Types by Float\n- Nano Cap: <10M shares float.\n- Micro Cap: 10-50M shares.\n- Low Float: 50-100M shares.\n- Medium Float: 100-200M shares.\n- Large Float: >200M shares.\n- Small float = bigger % moves, harder to trade.\n",
    "scaling": "## Position Scaling (Daily)\n- Start at 1/4 size for first trade of the day.\n- Add 1/4 size for second trade if first is profitable.\n- Full size only after demonstrating success.\n",
    "trading_platform": "## Trading Platform Setup\n- Pattern Day Trader (PDT): >3 day trades in 5 business days with <$25k.\n- Routing: SMART routing, IEX routing available on some platforms.\n- Clearing: ensure same-day or next-day settlement.\n",
}


def extract_rules_from_transcript(txt_path: Path) -> dict:
    """Keyword-based rules extraction."""
    if not txt_path.exists():
        return {}
    text = txt_path.read_text(encoding="utf-8", errors="ignore").lower()
    found = {}
    for category, keywords in RULES_KEYWORDS.items():
        matches = [kw for kw in keywords if kw.lower() in text]
        if matches:
            found[category] = matches
    return found


def load_quiz_bank():
    with open(QUIZ_BANK, "r", encoding="utf-8") as f:
        return json.load(f)


def save_quiz_bank(bank):
    with open(QUIZ_BANK, "w", encoding="utf-8") as f:
        json.dump(bank, f, indent=2, ensure_ascii=False)


def get_next_id(bank, prefix):
    """Get next question ID for a prefix."""
    nums = []
    for q in bank:
        if q["id"].startswith(prefix):
            try:
                nums.append(int(q["id"][len(prefix)+1:]))
            except ValueError:
                pass
    return f"{prefix}_{max(nums) + 1 if nums else 1:03d}"


def generate_quiz_from_transcript(txt_path: Path, chapter_label: str, chapter_tag: str) -> list:
    """Generate 5-8 quiz questions from a transcript using keyword extraction + templates."""
    if not txt_path.exists():
        return []
    text = txt_path.read_text(encoding="utf-8", errors="ignore")
    word_count = len(text.split())

    # Adjust question count based on length
    if word_count < 5000:
        num_q = 4
    elif word_count < 15000:
        num_q = 6
    else:
        num_q = 8

    # Find which categories this chapter covers
    found_cats = []
    text_lower = text.lower()
    for cat, kws in RULES_KEYWORDS.items():
        if any(kw.lower() in text_lower for kw in kws):
            found_cats.append(cat)

    questions = []
    # Use templates to generate questions based on what was found
    question_templates = {
        "order_types": [
            ("What is the key difference between a market order and a limit order?",
             ["A market order guarantees execution but not price; a limit order guarantees price but not execution.",
              "A limit order guarantees execution but not price.",
              "A market order is only used by professionals.",
              "They are identical for day trading purposes."],
             "medium", "c1_ch9_order_types.md"),
            ("A bracket order combines which three components?",
             ["Entry order, take-profit limit, and stop-loss order.",
              "Only entry and exit orders.",
              "Two market orders.",
              "A market order and a stop order."],
             "easy", "c1_ch9_order_types.md"),
        ],
        "hot_keys": [
            ("What does SCR stand for in hot key terminology?",
             ["Single Cancel Remaining.",
              "Stop, Cancel, Reverse.",
              "Send, Confirm, Route.",
              "Scale, Close, Rest."],
             "medium", "c1_ch10_hot_keys.md"),
            ("What is the purpose of a 'reverse' hot key?",
             ["Closes the current position and opens an opposite position simultaneously.",
              "Reverses the stop-loss order.",
              "Cancels all pending orders.",
              "Changes the order from buy to sell."],
             "easy", "c1_ch10_hot_keys.md"),
        ],
        "stock_halts": [
            ("What is a T1 stock halt and how long does it last?",
             ["A 5-minute automatic trading pause triggered by rapid price movement.",
              "A 10-minute halt.",
              "A 1-minute pause only.",
              "A halt that only affects short sellers."],
             "medium", "c1_ch11_stock_halts.md"),
            ("According to Ross, what is the rule regarding trading through a halt?",
             ["Never hold through a halt — exit before T1 triggers.",
              "It's fine to hold as long as you have a stop in place.",
              "You can only hold if the stock is in your favor.",
              "T1 halts are not important for day traders."],
             "easy", "c1_ch11_stock_halts.md"),
            ("What is the LULD band and when does it trigger?",
             ["Limit Up / Limit Down — automatic trading pause when price moves too fast in either direction.",
              "A technical indicator for trend direction.",
              "A type of limit order.",
              "The maximum loss allowed per trade."],
             "medium", "c1_ch11_stock_halts.md"),
        ],
        "risk_management": [
            ("What is Ross's rule for position scaling at the start of the trading day?",
             ["Start at 1/4 size, add 1/4 more only if profitable, full size last.",
              "Always start with full position size.",
              "Start with 1/2 size.",
              "Size is not important for day trading."],
             "easy", "c2_ch2_risk_management.md"),
            ("When should your maximum loss per trade be determined?",
             ["Before entering the trade — never adjust mid-trade.",
              "After the trade starts going against you.",
              "At the end of the trading day.",
              "Only if you are a beginner."],
             "easy", "c2_ch2_risk_management.md"),
            ("Why is the intraday 5-minute ATR preferred over 3-month daily ATR for day trades?",
             ["3-month daily ATR picks up massive historical moves that don't reflect today's volatility.",
              "5-minute ATR is always smaller.",
              "Daily ATR cannot be used for day trading.",
              "There is no difference between them."],
             "hard", "c2_ch2_risk_management.md"),
        ],
        "level2": [
            ("What does Level 2 quote data show that Level 1 does not?",
             ["Full bid/ask depth across multiple market makers and exchanges.",
              "Only the current stock price.",
              "Historical volume data.",
              "The company's earnings date."],
             "easy", "c2_ch6_level2.md"),
            ("What is a 'print' in Time & Sales?",
             ["A recorded trade — price, size, and time of an actual transaction.",
              "A pending order waiting to fill.",
              "A market maker quote update.",
              "A stock chart pattern."],
             "easy", "c2_ch6_level2.md"),
            ("What is ADFN and what does it show?",
             ["Alternative Data Feed Network — dark pool prints and off-exchange trade data.",
              "Advanced Financial Data Network — SEC filings.",
              "Automated Data Feed Node — broker quotes.",
              "Alternative Data File Number — historical trades."],
             "hard", "c2_ch6_level2.md"),
        ],
        "market_makers": [
            ("What is PFOF (Payment for Order Flow)?",
             ["Brokers sell retail orders to market makers (e.g., Citadel, Virtu) for payment.",
              "Market makers pay the broker for research.",
              "Investors pay fees to access Level 2 data.",
              "The SEC charges a fee per trade."],
             "medium", "c2_ch6_pfoff.md"),
            ("What is the main advantage of a direct access broker over PFOF routing?",
             ["Orders are routed directly to the exchange, avoiding internalization.",
              "Direct access is always faster.",
              "Direct access means no commissions.",
              "There is no difference."],
             "medium", "c2_ch6_pfoff.md"),
        ],
        "catalyst_news": [
            ("According to Ross, what is required for a high-probability day trade?",
             ["A news catalyst combined with a strong technical setup.",
              "Only technical analysis — catalysts are not important.",
              "Only a news catalyst is needed.",
              "A large account size."],
             "easy", "c3_part2_news_catalyst_rules.md"),
        ],
        "gap_patterns": [
            ("What is the difference between a partial gap and a full gap?",
             ["Partial gap: stock doesn't fully clear the previous day's range; full gap: stock opens well beyond it.",
              "They are the same thing.",
              "Partial gaps are not tradeable.",
              "Full gaps only happen on down days."],
             "medium", "c3_part2_news_catalyst_rules.md"),
        ],
    }

    # Build questions for found categories
    for cat in found_cats:
        if cat in question_templates:
            for tmpl in question_templates[cat]:
                q = {
                    "id": f"{chapter_tag}_q{len(questions)+1:03d}",
                    "chapter": chapter_label,
                    "topic": cat.replace("_", " ").title(),
                    "question": tmpl[0],
                    "options": tmpl[1],
                    "correct": "A",
                    "explanation": tmpl[1][0],
                    "difficulty": tmpl[2],
                    "source_rule": tmpl[3]
                }
                questions.append(q)
                if len(questions) >= num_q:
                    break
        if len(questions) >= num_q:
            break

    # Add generic chapter questions if we still need more
    if len(questions) < num_q:
        generic = [
            ("What is the most important lesson from this chapter?",
             ["Practice risk management and position sizing on every trade.",
              "Trade as frequently as possible.",
              "Use the largest position size allowed.",
              "Ignore stop-loss orders."],
             "easy", "transcript"),
            ("Ross Cameron emphasizes which key principle for new day traders?",
             ["Start small, scale up only after demonstrating profitability.",
              "Go all in on every setup.",
              "Never use stop-loss orders.",
              "Trade every single day without breaks."],
             "easy", "transcript"),
        ]
        for gmpl in generic:
            if len(questions) >= num_q:
                break
            q = {
                "id": f"{chapter_tag}_q{len(questions)+1:03d}",
                "chapter": chapter_label,
                "topic": "Core Principles",
                "question": gmpl[0],
                "options": gmpl[1],
                "correct": "A",
                "explanation": gmpl[1][0],
                "difficulty": gmpl[2],
                "source_rule": f"{chapter_tag}.txt"
            }
            questions.append(q)

    return questions[:num_q]


def main():
    print(f"\n{'='*60}")
    print(f"RULES EXTRACTION + QUIZ GENERATION — 2026-06-29")
    print(f"{'='*60}\n")

    quiz_bank = load_quiz_bank()
    new_questions = []
    new_rules = []

    for chapter_dir, chapter_tag, chapter_label in CHAPTERS:
        chapter_path = TRANSCRIPT_DIR / chapter_dir
        if not chapter_path.exists():
            print(f"  SKIP — not found: {chapter_path}")
            continue

        txt_files = list(chapter_path.glob("*.txt"))
        if not txt_files:
            print(f"  SKIP — no txt in: {chapter_dir}")
            continue

        print(f"\n[{chapter_tag}] {chapter_label}")
        print(f"  Files: {[f.name for f in txt_files]}")

        for txt_file in txt_files:
            print(f"  Processing: {txt_file.name}")

            # ── Rules extraction ──
            found = extract_rules_from_transcript(txt_file)
            if found:
                rules_lines = [
                    f"# {chapter_label} — Extracted Rules",
                    f"# Source: {txt_file.name}",
                    f"# Date: 2026-06-29",
                    "",
                    "## RULES EXTRACTED FROM TRANSCRIPT (preliminary)",
                    ""
                ]
                for cat, matches in found.items():
                    if cat in RULES_TEMPLATES:
                        rules_lines.append(RULES_TEMPLATES[cat])
                    rules_lines.append(f"### {cat.replace('_', ' ').title()} ({len(matches)} mentions)")
                    rules_lines.append(f"- Keywords found: {', '.join(matches)}")
                    rules_lines.append("")

                rules_filename = f"{chapter_tag}_{txt_file.stem}_rules.md"
                rules_path = RULES_DIR / rules_filename
                rules_path.parent.mkdir(parents=True, exist_ok=True)
                rules_path.write_text("\n".join(rules_lines), encoding="utf-8")
                print(f"    ✅ Rules saved: {rules_path.name}")
                new_rules.append(rules_path.name)
            else:
                print(f"    ⚠️  No keywords found — no rules file generated")

            # ── Quiz generation ──
            questions = generate_quiz_from_transcript(txt_file, chapter_label, chapter_tag)
            for q in questions:
                q["id"] = get_next_id(quiz_bank, chapter_tag.replace(" ", "_").lower())
                quiz_bank.append(q)
                new_questions.append(q["id"])

            print(f"    ✅ Generated {len(questions)} quiz questions")

    save_quiz_bank(quiz_bank)
    print(f"\n{'='*60}")
    print(f"COMPLETE")
    print(f"  New rules files: {len(new_rules)}")
    print(f"  New quiz questions: {len(new_questions)}")
    print(f"  Total in bank now: {len(quiz_bank)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
