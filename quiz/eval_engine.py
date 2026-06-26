"""
Self-Evaluation Engine for Ross Cameron Trading Quiz.
Tracks progress, identifies weak areas, evolves the question bank.

Usage:
  python eval_engine.py                          → Full score report
  python eval_engine.py --sessions               → List all sessions
  python eval_engine.py --session SESSION_ID     → Detail one session
  python eval_engine.py --evolve                 → Add new questions from transcripts
  python eval_engine.py --report                 → Generate performance report
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

QUIZ_DIR = Path(r"E:\Me\TradingAgent\quiz")
PROGRESS_PATH = QUIZ_DIR / "progress.json"
BANK_PATH = QUIZ_DIR / "bank" / "quiz_bank.json"
SESSIONS_DIR = QUIZ_DIR / "sessions"


def load_progress():
    if PROGRESS_PATH.exists():
        with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_bank():
    with open(BANK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_bank(bank):
    with open(BANK_PATH, "w", encoding="utf-8") as f:
        json.dump(bank, f, indent=2, ensure_ascii=False)


def load_sessions():
    sessions = []
    if SESSIONS_DIR.exists():
        for f in sorted(SESSIONS_DIR.glob("session_*.json")):
            with open(f, "r", encoding="utf-8") as fp:
                sessions.append(json.load(fp))
    return sessions


def compute_stats(sessions, progress):
    """Compute comprehensive statistics from all sessions."""
    total_q = sum(s["total"] for s in sessions)
    total_c = sum(s["score"] for s in sessions)
    pct = total_c / total_q * 100 if total_q > 0 else 0

    # Chapter scores
    chapter_totals = {}
    for s in sessions:
        for ch, res in s.get("chapter_results", {}).items():
            if ch not in chapter_totals:
                chapter_totals[ch] = {"correct": 0, "total": 0}
            chapter_totals[ch]["correct"] += res["correct"]
            chapter_totals[ch]["total"] += res["total"]

    # Topic scores
    topic_totals = {}
    for s in sessions:
        for t, res in s.get("topic_results", {}).items():
            if t not in topic_totals:
                topic_totals[t] = {"correct": 0, "total": 0}
            topic_totals[t]["correct"] += res["correct"]
            topic_totals[t]["total"] += res["total"]

    # Weak areas
    weak = [t for t, r in topic_totals.items()
            if r["total"] >= 3 and r["correct"] / r["total"] < 0.7]
    strong = [t for t, r in topic_totals.items()
              if r["total"] >= 3 and r["correct"] / r["total"] >= 0.9]

    return {
        "total_questions": total_q,
        "total_correct": total_c,
        "overall_pct": pct,
        "grade": "A" if pct >= 90 else "B" if pct >= 80 else "C" if pct >= 70 else "D" if pct >= 60 else "F",
        "num_sessions": len(sessions),
        "chapter_scores": chapter_totals,
        "topic_scores": topic_totals,
        "weak_areas": weak,
        "strong_areas": strong
    }


def print_full_report():
    progress = load_progress()
    sessions = load_sessions()
    stats = compute_stats(sessions, progress)

    print("\n" + "=" * 70)
    print("  ROSS CAMERON TRADING QUIZ — PERFORMANCE REPORT")
    print("=" * 70)
    print(f"\n  Overall: {stats['total_correct']}/{stats['total_questions']} "
          f"({stats['overall_pct']:.1f}%) — Grade: {stats['grade']}")
    print(f"  Sessions completed: {stats['num_sessions']}")

    # Chapter performance
    print("\n  BY CHAPTER:")
    sorted_chapters = sorted(stats["chapter_scores"].items(),
                             key=lambda x: x[1]["correct"] / max(x[1]["total"], 1),
                             reverse=True)
    for ch, res in sorted_chapters:
        pct = res["correct"] / res["total"] * 100
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct // 10))
        status = "✅" if pct >= 70 else "⚠️"
        print(f"  {status} {bar} {pct:5.1f}% {res['correct']:2d}/{res['total']:2d}  {ch}")

    # Topic performance
    print("\n  BY TOPIC:")
    sorted_topics = sorted(stats["topic_scores"].items(),
                           key=lambda x: x[1]["correct"] / max(x[1]["total"], 1),
                           reverse=True)
    for t, res in sorted_topics:
        pct = res["correct"] / res["total"] * 100
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct // 10))
        status = "✅" if pct >= 70 else "⚠️"
        print(f"  {status} {bar} {pct:5.1f}% {res['correct']:2d}/{res['total']:2d}  {t}")

    # Weak/strong
    if stats["weak_areas"]:
        print(f"\n  🔴 WEAK AREAS (focus study here):")
        for t in stats["weak_areas"]:
            print(f"     - {t}")
    if stats["strong_areas"]:
        print(f"\n  🟢 STRONG AREAS:")
        for t in stats["strong_areas"]:
            print(f"     - {t}")

    # Recommendation
    print("\n  RECOMMENDATIONS:")
    if stats["weak_areas"]:
        print(f"  1. Run targeted practice: python run_quiz.py --weak-areas")
    print(f"  2. Review rules files for weak areas before re-testing")
    print(f"  3. Re-test after reviewing — aim for 80%+ per chapter")
    print(f"  4. Once all chapters ≥80%: ready for live paper trading")

    print("\n" + "=" * 70 + "\n")


def list_sessions():
    sessions = load_sessions()
    print(f"\n  Found {len(sessions)} quiz sessions:\n")
    for s in sessions:
        pct = s["score"] / s["total"] * 100 if s["total"] > 0 else 0
        print(f"  {s['session_id']}  {s['date'][:10]}  "
              f"{s['score']}/{s['total']} ({pct:.0f}%)")
    print()


def session_detail(session_id):
    sessions = load_sessions()
    for s in sessions:
        if s["session_id"] == session_id:
            pct = s["score"] / s["total"] * 100
            print(f"\n  Session: {s['session_id']}")
            print(f"  Date: {s['date']}")
            print(f"  Score: {s['score']}/{s['total']} ({pct:.0f}%)")
            print(f"\n  Chapter breakdown:")
            for ch, res in s["chapter_results"].items():
                cp = res["correct"] / res["total"] * 100
                print(f"    {ch}: {res['correct']}/{res['total']} ({cp:.0f}%)")
            print(f"\n  Topic breakdown:")
            for t, res in s["topic_results"].items():
                tp = res["correct"] / res["total"] * 100
                status = "✅" if tp >= 70 else "❌"
                print(f"    {status} {t}: {res['correct']}/{res['total']} ({tp:.0f}%)")
            print()
            return
    print(f"Session '{session_id}' not found.")


def print_bank_stats():
    bank = load_bank()
    by_chapter = {}
    by_topic = {}
    by_difficulty = {"easy": 0, "medium": 0, "hard": 0}
    for q in bank:
        ch = q["chapter"]
        t = q["topic"]
        d = q["difficulty"]
        by_chapter[ch] = by_chapter.get(ch, 0) + 1
        by_topic[t] = by_topic.get(t, 0) + 1
        by_difficulty[d] = by_difficulty.get(d, 0) + 1

    print(f"\n  Quiz Bank: {len(bank)} questions")
    print(f"\n  By chapter:")
    for ch, cnt in sorted(by_chapter.items()):
        print(f"    {ch}: {cnt} questions")
    print(f"\n  By difficulty:")
    for d, cnt in by_difficulty.items():
        print(f"    {d}: {cnt}")
    print()


def main():
    args = sys.argv[1:]

    if "--sessions" in args:
        list_sessions()
    elif "--session" in args:
        idx = args.index("--session")
        session_detail(args[idx + 1])
    elif "--bank" in args:
        print_bank_stats()
    elif "--report" in args:
        print_full_report()
    else:
        print_full_report()
        print("  Usage:")
        print("    python eval_engine.py --report          → Full performance report")
        print("    python eval_engine.py --sessions         → List all sessions")
        print("    python eval_engine.py --session ID      → Detail one session")
        print("    python eval_engine.py --bank            → Quiz bank statistics")


if __name__ == "__main__":
    main()
