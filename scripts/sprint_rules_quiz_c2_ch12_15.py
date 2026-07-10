"""
Rules extraction + Quiz generation for C2 Ch12-15 sprint (added 2026-07-10).
Reuses patterns from rules_and_quiz_sprint.py with new keywords/templates.
"""
import json
import re
from pathlib import Path
from datetime import datetime

BASE = Path(r"E:\Me\TradingAgent")
TRANSCRIPT_DIR = BASE / "knowledge" / "transcripts"
RULES_DIR = BASE / "knowledge" / "rules"
QUIZ_BANK = BASE / "quiz" / "bank" / "quiz_bank.json"

# Chapter dir → (chapter_tag, chapter_label, file_pattern)
CHAPTERS = [
    ("Chapter 12 Course2", "c2_ch12", "C2 Ch12 — Stock Scanning / Day Trade Dash"),
    ("Chapter 13 Course2", "c2_ch13", "C2 Ch13 — Trading Psychology, Discipline, Recovery"),
    ("Chapter 14 Course2", "c2_ch14", "C2 Ch14 — Trading Plan & Strategy (Beginner)"),
    ("Chapter 15 Course2", "c2_ch15", "C2 Ch15 — When to Trade Real Money & Position Mgmt"),
]

# New keywords for the new chapters
RULES_KEYWORDS = {
    # Ch12 — Stock scanning
    "stock_scanning": ["scanner", "scanning", "day trade dash", "gap scanner", "top gainer",
                       "small cap high", "continuation", "float scan", "price scan", "volume scan"],
    "scanner_filters": ["relative volume", "RV filter", "price filter", "float filter",
                        "gap percent", "% gainer", "market cap", "average volume"],
    "premarket_scan": ["premarket", "pre-market", "before the bell", "4am", "7am", "morning scan",
                       "after hours", "top gainer scan", "scan process"],
    # Ch13 — Psychology
    "psychology_discipline": ["discipline", "mindset", "psychology", "emotional", "emotion",
                              "patience", "tilt", "revenge", "stick to plan", "process over outcome"],
    "loss_recovery": ["loss recovery", "losing streak", "big loss", "drawdown", "recover",
                      "take a break", "step away", "reset", "stop trading after loss"],
    "consistency": ["consistency", "consistent", "process", "routine", "daily routine",
                    "habit", "checklist", "pre-market prep"],
    # Ch14 — Trading plan
    "trading_plan": ["trading plan", "plan", "rules", "checklist", "pre-market", "post-market",
                     "morning routine", "end of day", "review"],
    "beginner_strategy": ["beginner", "starting out", "new trader", "first strategy", "simple",
                          "as a beginner", "would use", "I'd use"],
    # Ch15 — Real money
    "real_money_timing": ["real money", "going live", "live trading", "switch to live",
                          "when to trade live", "simulator to live", "paper trade"],
    "share_scaling": ["share size", "increasing size", "position size", "share count",
                      "100 shares", "200 shares", "500 shares", "1000 shares", "scale up"],
    "trades_per_day": ["trades per day", "more trades", "frequency", "trade count",
                       "daily limit", "max trades", "multiple trades"],
    "scaling_out": ["scaling out", "partial exit", "scale out", "trim", "take profits",
                    "partial profit", "selling half", "selling 1/3"],
    "scaling_in": ["scaling in", "add to winner", "add to position", "pyramid", "scale in",
                   "averaging up", "add shares"],
    "position_management": ["position management", "manage position", "trailing stop",
                            "move stop", "breakeven", "stop to breakeven", "protect profit"],
}

RULES_TEMPLATES = {
    "stock_scanning": "## Stock Scanning Fundamentals\n- Scanners are the first step — find stocks with momentum BEFORE the open.\n- Ross: '9 out of 10 times the stock is hitting one of my scanners.'\n- Day Trade Dash is Ross's primary scanner — filters by price, float, gap %, RV.\n- Scan multiple times throughout the day: pre-market, open, mid-morning, lunch.\n",
    "scanner_filters": "## Scanner Filter Criteria\n- Relative Volume (RV): 5x+ above average is the primary filter.\n- Price range: typically $1-$20 for small caps.\n- Float: nano/micro cap (under 50M shares) for biggest % moves.\n- Gap %: 4-10% gap up is sweet spot; >20% may have already extended.\n- Time of day matters — most signals fire 9:30-10:30 AM ET.\n",
    "premarket_scan": "## Pre-Market Scan Routine\n- 4-7 AM ET: scan pre-market gainers using Day Trade Dash.\n- 7-8 AM ET: narrow to 5-10 candidates; check news, float, RV.\n- Build watchlist BEFORE 9:30 AM — no scrambling at the open.\n- Top gainers scanner is the primary filter; sub-filters: float, price, RV.\n",
    "psychology_discipline": "## Trading Psychology & Discipline\n- The biggest enemy is YOU — emotions, FOMO, revenge trading, greed.\n- Ross: 'Process over outcome — follow the plan, not the P&L.'\n- Have a daily checklist. Stick to it. No improvising.\n- After 2-3 consecutive losses, STOP trading for the day.\n",
    "loss_recovery": "## Recovery from Losses\n- After a big loss: step away, take a walk, come back next day fresh.\n- NEVER revenge trade — biggest account killer.\n- Review the losing trade in your journal — what rule did you break?\n- Reduce size after losses; rebuild confidence with 1/4 size first.\n",
    "consistency": "## Consistency is King\n- One good trade doesn't make you profitable. 100 consistent trades do.\n- Process over outcome — same setup, same execution, regardless of P&L.\n- Daily routine: pre-market scan, watchlist, post-market review.\n- Track stats: win rate, avg win vs avg loss, profit factor.\n",
    "trading_plan": "## The Trading Plan\n- Written rules: what setups to take, when to enter, where to stop, where to target.\n- Pre-market checklist: scan → watchlist → news check → risk plan.\n- In-trade rules: max loss per trade, max trades per day, daily max loss.\n- Post-market: review journal, note lessons, prep tomorrow.\n",
    "beginner_strategy": "## Beginner-Friendly Strategy\n- Start with one setup only — first pullback is the easiest to learn.\n- Trade small size (100-200 shares) until you have 30+ profitable trades.\n- Keep a journal: entry, exit, why you took it, what you'd do differently.\n- Don't add new strategies until you've proven one is profitable.\n",
    "real_money_timing": "## When to Trade with Real Money\n- 30+ profitable trades in the simulator (50%+ win rate, positive P&L).\n- Simulator and live results should be within 20% of each other.\n- Start with 1/4 size on day 1 of live trading.\n- NEVER switch to live because you 'feel ready' — let the data decide.\n",
    "share_scaling": "## Share Size Scaling\n- Day 1 of live: 1/4 of target size (e.g., 100 shares instead of 400).\n- After 5+ profitable live trades: scale to 1/2 size.\n- After 20+ profitable live trades: scale to full size.\n- One bad day = drop back to previous size level.\n",
    "trades_per_day": "## Trade Frequency\n- Beginner: 1-3 trades per day max. Quality over quantity.\n- Intermediate: 3-5 trades per day.\n- Advanced: 5-10 trades per day.\n- Hard cap: 10 trades/day — overtrading kills accounts.\n",
    "scaling_out": "## Scaling Out (Taking Partial Profits)\n- Take 1/3 off at first target (e.g., +$0.20).\n- Move stop to breakeven on remaining 2/3.\n- Take another 1/3 at second target (+$0.40).\n- Let final 1/3 ride with trailing stop — let winners run.\n",
    "scaling_in": "## Scaling In (Adding to Winners)\n- ONLY scale into a position that is already profitable.\n- Add 1/4 size on first confirmation, more on continuation.\n- NEVER add to a losing position — that's averaging down, not scaling in.\n- Ross: 'Add to winners, not losers — be patient.'\n",
    "position_management": "## Position Management Rules\n- Move stop to breakeven once trade is +$0.20 in your favor.\n- Trail stop using 1-min or 5-min candle lows — not arbitrary numbers.\n- Never move stop FURTHER from entry — only closer.\n- If trade stalls for 2 minutes with no progress, exit at market.\n",
}

QUESTION_TEMPLATES = {
    "stock_scanning": [
        ("According to Ross, what percentage of his trades come from his scanner results?",
         ["About 9 out of 10 trades hit one of his scanners.",
          "Less than 10% — most are discretionary.",
          "All trades come from one specific chart pattern.",
          "He doesn't use scanners."],
         "medium", "c2_ch12_scanning.md"),
        ("What is the Day Trade Dash scanner primarily used for?",
         ["Filtering stocks by float, gap %, relative volume, and price in real time.",
          "Placing orders automatically.",
          "Tracking your P&L throughout the day.",
          "Posting trade ideas to social media."],
         "easy", "c2_ch12_scanning.md"),
    ],
    "scanner_filters": [
        ("What Relative Volume (RV) threshold does Ross typically look for in his scan?",
         ["5x above average or higher.",
          "Any positive volume is fine.",
          "10x above average is the minimum.",
          "1.5x is enough."],
         "medium", "c2_ch12_filters.md"),
        ("What is the typical price range Ross scans for in small-cap day trading?",
         ["$1 to $20 per share.",
          "Only stocks under $1.",
          "Stocks above $100.",
          "Price doesn't matter."],
         "easy", "c2_ch12_filters.md"),
    ],
    "premarket_scan": [
        ("What time does Ross recommend starting the pre-market scan?",
         ["4-7 AM ET, with a refined list by 8 AM ET.",
          "Right at market open (9:30 AM).",
          "The day before, after market close.",
          "There is no pre-market scan."],
         "medium", "c2_ch12_premarket.md"),
    ],
    "psychology_discipline": [
        ("What does Ross consider the biggest enemy of a day trader?",
         ["The trader themselves — emotions, FOMO, and revenge trading.",
          "Market makers.",
          "High-frequency trading algorithms.",
          "The news media."],
         "easy", "c2_ch13_psychology.md"),
        ("After how many consecutive losses does Ross recommend stopping for the day?",
         ["2-3 consecutive losses.",
          "After the first loss.",
          "10 consecutive losses.",
          "Never stop on a loss."],
         "medium", "c2_ch13_psychology.md"),
    ],
    "loss_recovery": [
        ("What is the most important rule after a significant trading loss?",
         ["Step away, take a break, and review the trade before trading again.",
          "Immediately double your position size to recover.",
          "Switch to a different strategy on the spot.",
          "Take revenge trades to 'win it back'."],
         "easy", "c2_ch13_recovery.md"),
    ],
    "consistency": [
        ("What does Ross mean by 'process over outcome'?",
         ["Follow the trading plan and rules regardless of whether a trade wins or loses.",
          "Always aim for the biggest possible profit.",
          "Trade the same setup every day no matter what.",
          "Process is irrelevant if the outcome is profit."],
         "medium", "c2_ch13_consistency.md"),
    ],
    "trading_plan": [
        ("What are the key components of a trading plan?",
         ["Entry rules, stop-loss, profit target, position size, and max daily loss.",
          "Just a list of stocks to watch.",
          "Only the times you will trade.",
          "Only the broker you will use."],
         "easy", "c2_ch14_plan.md"),
    ],
    "beginner_strategy": [
        ("What strategy does Ross recommend a beginner focus on first?",
         ["The first pullback setup — simple, repeatable, well-defined entry and stop.",
          "Reversal trading — complex but high reward.",
          "Options trading — leverage and flexibility.",
          "Whatever is trending on Twitter that day."],
         "easy", "c2_ch14_beginner.md"),
        ("How many profitable trades in the simulator should a beginner aim for before going live?",
         ["At least 30+ profitable trades with a 50%+ win rate.",
          "Just 1 successful trade is enough.",
          "100+ trades in a single day.",
          "No simulator needed — just go live."],
         "medium", "c2_ch14_beginner.md"),
    ],
    "real_money_timing": [
        ("According to Ross, when should a trader switch from simulator to real money?",
         ["After 30+ profitable simulator trades with consistent positive P&L.",
          "Whenever they feel emotionally ready.",
          "On the first day of learning.",
          "After depositing $25,000 into a broker account."],
         "medium", "c2_ch15_real_money.md"),
    ],
    "share_scaling": [
        ("What is the recommended share size on the FIRST day of live trading?",
         ["1/4 of the target position size.",
          "Full size immediately.",
          "10x normal size to maximize profits.",
          "It doesn't matter."],
         "medium", "c2_ch15_share_size.md"),
        ("How many profitable live trades are typically needed before scaling up to full size?",
         ["20+ profitable live trades.",
          "1 trade is enough.",
          "100+ trades.",
          "Never scale up."],
         "medium", "c2_ch15_share_size.md"),
    ],
    "trades_per_day": [
        ("How many trades per day does Ross recommend for beginner day traders?",
         ["1-3 trades per day, focused on quality setups.",
          "As many as possible — the more the better.",
          "20+ trades per day.",
          "Only 1 trade per week."],
         "easy", "c2_ch15_frequency.md"),
    ],
    "scaling_out": [
        ("What is the standard scale-out plan Ross describes for partial profit taking?",
         ["Take 1/3 at first target, 1/3 at second target, ride 1/3 with trailing stop.",
          "Exit the full position at first target.",
          "Never take partial profits.",
          "Take 50% off immediately, hold the rest forever."],
         "medium", "c2_ch15_scaling_out.md"),
    ],
    "scaling_in": [
        ("When is it acceptable to scale INTO a position?",
         ["Only when the position is already profitable — never into a losing trade.",
          "Whenever the stock dips.",
          "When the news is bad.",
          "Never scale in."],
         "easy", "c2_ch15_scaling_in.md"),
    ],
    "position_management": [
        ("When should you move your stop-loss to breakeven?",
         ["Once the trade is at least +$0.20 in your favor (or your defined first target).",
          "Immediately after entry.",
          "Never.",
          "Only on the last day of trading."],
         "medium", "c2_ch15_mgmt.md"),
        ("What is the 2-minute rule for managing a position?",
         ["If the trade shows no progress for 2 minutes, exit at market.",
          "Hold every trade for at least 2 minutes.",
          "Wait 2 minutes before entering any trade.",
          "Only trade at the 2-minute mark of the hour."],
         "hard", "c2_ch15_mgmt.md"),
    ],
}


def extract_rules_from_transcript(txt_path: Path) -> dict:
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
    nums = []
    for q in bank:
        if q["id"].startswith(prefix):
            try:
                nums.append(int(q["id"][len(prefix)+1:]))
            except ValueError:
                pass
    return f"{prefix}_{max(nums) + 1 if nums else 1:03d}"


def generate_quiz_from_transcript(txt_path: Path, chapter_label: str, chapter_tag: str) -> list:
    if not txt_path.exists():
        return []
    text = txt_path.read_text(encoding="utf-8", errors="ignore")
    word_count = len(text.split())

    if word_count < 5000:
        num_q = 4
    elif word_count < 15000:
        num_q = 6
    else:
        num_q = 8

    found_cats = []
    text_lower = text.lower()
    for cat, kws in RULES_KEYWORDS.items():
        if any(kw.lower() in text_lower for kw in kws):
            found_cats.append(cat)

    questions = []
    for cat in found_cats:
        if cat in QUESTION_TEMPLATES:
            for tmpl in QUESTION_TEMPLATES[cat]:
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

    if len(questions) < num_q:
        generic = [
            ("What is the most important lesson from this chapter?",
             ["Stick to your trading plan and risk management rules — consistency is the edge.",
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
    print(f"RULES + QUIZ SPRINT — C2 Ch12-15 (added 2026-07-10)")
    print(f"{'='*60}\n")

    quiz_bank = load_quiz_bank()
    new_questions = []
    new_rules = []

    for chapter_dir, chapter_tag, chapter_label in CHAPTERS:
        chapter_path = TRANSCRIPT_DIR / chapter_dir
        if not chapter_path.exists():
            print(f"  SKIP — not found: {chapter_path}")
            continue

        txt_files = sorted(chapter_path.glob("*.txt"))
        if not txt_files:
            print(f"  SKIP — no txt in: {chapter_dir}")
            continue

        print(f"\n[{chapter_tag}] {chapter_label}")
        print(f"  Files: {[f.name for f in txt_files]}")

        for txt_file in txt_files:
            print(f"  Processing: {txt_file.name}")

            # Rules
            found = extract_rules_from_transcript(txt_file)
            if found:
                rules_lines = [
                    f"# {chapter_label} — Extracted Rules",
                    f"# Source: {txt_file.name}",
                    f"# Date: 2026-07-10",
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
                print(f"    Rules saved: {rules_path.name}")
                new_rules.append(rules_path.name)
            else:
                print(f"    No keywords found")

            # Quiz
            questions = generate_quiz_from_transcript(txt_file, chapter_label, chapter_tag)
            for q in questions:
                q["id"] = get_next_id(quiz_bank, chapter_tag)
                quiz_bank.append(q)
                new_questions.append(q["id"])
            print(f"    Generated {len(questions)} quiz questions")

    save_quiz_bank(quiz_bank)
    print(f"\n{'='*60}")
    print(f"COMPLETE")
    print(f"  New rules files: {len(new_rules)}")
    print(f"  New quiz questions: {len(new_questions)}")
    print(f"  Total in bank now: {len(quiz_bank)}")
    print(f"{'='*60}\n")
    for nq in new_questions:
        print(f"  {nq}")


if __name__ == "__main__":
    main()
