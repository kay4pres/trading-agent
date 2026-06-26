"""
Interactive Quiz Runner for Ross Cameron Day Trading Knowledge.
Run: python run_quiz.py [--chapter CHAPTER] [--count N] [--session SESSION_ID]

Modes:
  python run_quiz.py                    → Full 50-question quiz (random from all chapters)
  python run_quiz.py --chapter Ch15     → Chapter-specific quiz
  python run_quiz.py --count 20         → Custom number of questions
  python run_quiz.py --review           → Review all questions (no scoring)
  python run_quiz.py --weak-areas       → Generate targeted practice from weak areas
"""
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

QUIZ_DIR = Path(r"E:\Me\TradingAgent\quiz")
BANK_PATH = QUIZ_DIR / "bank" / "quiz_bank.json"
PROGRESS_PATH = QUIZ_DIR / "progress.json"
SESSIONS_DIR = QUIZ_DIR / "sessions"


def load_bank():
    with open(BANK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_progress():
    if PROGRESS_PATH.exists():
        with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"topic_scores": {}, "chapter_scores": {}, "weak_areas": [],
            "total_questions_answered": 0, "total_correct": 0}


def save_progress(progress):
    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


def select_questions(bank, chapter=None, count=50, weak_areas_only=False):
    if chapter:
        pool = [q for q in bank if chapter.lower() in q["chapter"].lower()]
    elif weak_areas_only:
        progress = load_progress()
        weak = progress.get("weak_areas", [])
        if not weak:
            print("No weak areas yet. Run a full quiz first.")
            sys.exit(0)
        pool = [q for q in bank if any(w.lower() in q["topic"].lower() for w in weak)]
        if not pool:
            print(f"No questions found for weak areas: {weak}")
            sys.exit(0)
    else:
        pool = bank

    count = min(count, len(pool))
    return random.sample(pool, count)


def run_quiz(questions, session_id=None):
    progress = load_progress()
    session = {
        "session_id": session_id or datetime.now().strftime("%Y%m%d_%H%M%S"),
        "date": datetime.now().isoformat(),
        "questions": [],
        "score": 0,
        "total": len(questions),
        "topic_results": {},
        "chapter_results": {}
    }

    print("\n" + "=" * 70)
    print("  ROSS CAMERON DAY TRADING — KNOWLEDGE QUIZ")
    print("  Answer each question. Type A, B, C, or D.")
    print("  Type 'skip' to skip, 'quit' to exit early.")
    print("=" * 70 + "\n")

    for i, q in enumerate(questions, 1):
        print(f"Q{i}/{len(questions)} [{q['difficulty'].upper()}] {q['chapter']} — {q['topic']}")
        print(f"  {q['question']}")
        for opt in q["options"]:
            print(f"  {opt}")
        print()

        while True:
            raw = input("Your answer: ").strip().upper()
            if raw in ("A", "B", "C", "D"):
                answer = raw
                break
            elif raw in ("SKIP", "S"):
                answer = None
                break
            elif raw in ("QUIT", "Q"):
                print("\nQuiz ended early.")
                print_results(i - 1, session, progress)
                return
            else:
                print("  Please enter A, B, C, or D (or 'skip' / 'quit')")

        result = {
            "id": q["id"],
            "question": q["question"],
            "user_answer": answer,
            "correct_answer": q["correct"],
            "correct": answer == q["correct"],
            "explanation": q["explanation"]
        }

        if answer is None:
            result["correct"] = False
        elif answer == q["correct"]:
            session["score"] += 1

        # Track per-topic and per-chapter
        topic = q["topic"]
        chapter = q["chapter"]
        if topic not in session["topic_results"]:
            session["topic_results"][topic] = {"correct": 0, "total": 0}
        if chapter not in session["chapter_results"]:
            session["chapter_results"][chapter] = {"correct": 0, "total": 0}

        session["topic_results"][topic]["total"] += 1
        session["chapter_results"][chapter]["total"] += 1
        if answer == q["correct"]:
            session["topic_results"][topic]["correct"] += 1
            session["chapter_results"][chapter]["correct"] += 1

        # Show result
        if answer is None:
            print(f"  ⏭ SKIPPED")
        elif answer == q["correct"]:
            print(f"  ✅ CORRECT!")
        else:
            print(f"  ❌ WRONG — Correct: {q['correct']}")

        print(f"  → {q['explanation']}\n")

        # Progress update every 10 questions
        if i % 10 == 0:
            pct = session["score"] / i * 100
            print(f"  📊 Progress: {session['score']}/{i} correct ({pct:.0f}%)\n")

    print_results(len(questions), session, progress)


def print_results(total, session, progress):
    score = session["score"]
    pct = score / total * 100
    grade = "A" if pct >= 90 else "B" if pct >= 80 else "C" if pct >= 70 else "D" if pct >= 60 else "F"

    print("\n" + "=" * 70)
    print(f"  QUIZ COMPLETE — {score}/{total} correct ({pct:.0f}%) — Grade: {grade}")
    print("=" * 70)

    # Chapter breakdown
    print("\n  BY CHAPTER:")
    for chapter, res in session["chapter_results"].items():
        cp = res["correct"] / res["total"] * 100
        bar = "█" * int(cp / 10) + "░" * (10 - int(cp / 10))
        flag = " ⚠️ WEAK" if cp < 70 else " ✅"
        print(f"  {bar} {cp:4.0f}% {chapter}{flag}")

    # Topic breakdown
    print("\n  TOPIC BREAKDOWN:")
    for topic, res in session["topic_results"].items():
        tp = res["correct"] / res["total"] * 100
        bar = "█" * int(tp / 10) + "░" * (10 - int(tp / 10))
        flag = " ⚠️" if tp < 70 else " ✅"
        print(f"  {bar} {tp:4.0f}% {topic}{flag}")

    # Update progress
    progress["total_questions_answered"] += total
    progress["total_correct"] += score
    overall = progress["total_correct"] / progress["total_questions_answered"] * 100
    print(f"\n  ALL-TIME: {progress['total_correct']}/{progress['total_questions_answered']} ({overall:.0f}%)")

    # Identify new weak areas (< 70% in this session)
    new_weak = [t for t, r in session["topic_results"].items()
                if r["correct"] / r["total"] < 0.7
                and t not in progress.get("weak_areas", [])]
    if new_weak:
        print(f"\n  🔴 New weak areas identified: {new_weak}")
        progress.setdefault("weak_areas", [])
        progress["weak_areas"].extend(new_weak)

    # Save session
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_path = SESSIONS_DIR / f"session_{session['session_id']}.json"
    with open(session_path, "w", encoding="utf-8") as f:
        json.dump(session, f, indent=2)

    save_progress(progress)
    print(f"\n  Session saved: {session_path.name}")
    print(f"  Run 'python run_quiz.py --weak-areas' to practice weak topics.\n")


def generate_markdown_quiz(questions, output_path):
    """Generate a human-readable markdown quiz."""
    lines = ["# Ross Cameron Day Trading — Knowledge Quiz\n",
             f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | {len(questions)} questions*\n",
             "---\n"]
    for i, q in enumerate(questions, 1):
        lines.append(f"## Q{i}. [{q['difficulty'].upper()}] {q['chapter']} — {q['topic']}\n")
        lines.append(f"{q['question']}\n")
        for opt in q["options"]:
            lines.append(f"- {opt}\n")
        lines.append(f"\n*Answer: {q['correct']}*\n")
        lines.append(f"**Explanation:** {q['explanation']}\n")
        lines.append(f"*Source: {q['source_rule']}*\n")
        lines.append("---\n")

    lines.append("\n## Answer Key\n")
    for i, q in enumerate(questions, 1):
        lines.append(f"Q{i}: {q['correct']} — {q['question'][:60]}...\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"Markdown quiz written: {output_path}")


def main():
    args = sys.argv[1:]
    chapter = None
    count = 50
    mode = "quiz"

    i = 0
    while i < len(args):
        if args[i] == "--chapter" and i + 1 < len(args):
            chapter = args[i + 1]
            i += 2
        elif args[i] == "--count" and i + 1 < len(args):
            count = int(args[i + 1])
            i += 2
        elif args[i] == "--session" and i + 1 < len(args):
            session_id = args[i + 1]
            i += 2
        elif args[i] == "--review":
            mode = "review"
            i += 1
        elif args[i] == "--weak-areas":
            mode = "weak"
            i += 1
        elif args[i] == "--md":
            mode = "md"
            i += 1
        else:
            i += 1

    bank = load_bank()
    print(f"\nLoaded {len(bank)} questions from quiz bank.")

    if mode == "review":
        count = len(bank)
        questions = random.sample(bank, count)
        print(f"Review mode: all {count} questions (answers shown)\n")
        run_quiz(questions)

    elif mode == "weak":
        questions = select_questions(bank, weak_areas_only=True, count=count)
        print(f"Targeted practice: {len(questions)} questions from weak areas\n")
        run_quiz(questions)

    elif mode == "md":
        questions = select_questions(bank, chapter=chapter, count=count)
        out = QUIZ_DIR / "course1_full_quiz.md"
        generate_markdown_quiz(questions, out)

    elif mode == "bank":
        bank = load_bank()
        by_ch = {}
        by_d = {"easy": 0, "medium": 0, "hard": 0}
        for q in bank:
            by_ch[q["chapter"]] = by_ch.get(q["chapter"], 0) + 1
            by_d[q["difficulty"]] = by_d.get(q["difficulty"], 0) + 1
        print(f"\n  Quiz Bank: {len(bank)} questions")
        print(f"\n  By chapter:")
        for ch, cnt in sorted(by_ch.items()):
            print(f"    {ch}: {cnt}")
        print(f"\n  By difficulty: easy={by_d['easy']}, medium={by_d['medium']}, hard={by_d['hard']}")
        print()

    else:
        questions = select_questions(bank, chapter=chapter, count=count)
        print(f"Quiz mode: {len(questions)} questions")
        if chapter:
            print(f"Chapter filter: {chapter}\n")
        run_quiz(questions)


if __name__ == "__main__":
    main()
