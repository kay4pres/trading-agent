"""
Whisper transcription pipeline for Warrior Trading course videos.
Uses faster-whisper for speed on CPU.
"""
import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

import faster_whisper

# ── Config ──────────────────────────────────────────────────────────────────
KNOWLEDGE_DIR = Path(r"E:\Me\TradingAgent\knowledge")
RAW_DIR = KNOWLEDGE_DIR / "raw"
TRANSCRIPT_DIR = KNOWLEDGE_DIR / "transcripts"
MODEL_SIZE = "tiny"  # fastest, good for rule extraction
LANGUAGE = "en"

TRANSCRIPTS = {
    "ch3_part2": {
        "source": RAW_DIR / "Chapter 3 Stock Selection, Fundamental Analysis, & Building a Watch List" / "Part 2 How to Understand the News Catalyst.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 3" / "Part2_News_Catalyst.txt",
        "priority": 1,
        "description": "News catalyst — directly feeds Richard's P1-P4 scoring",
    },
    "ch3_part5": {
        "source": RAW_DIR / "Chapter 3 Stock Selection, Fundamental Analysis, & Building a Watch List" / "Part 5 Building a Daily Watch List.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 3" / "Part5_Building_Watchlist.txt",
        "priority": 2,
        "description": "Watchlist building — directly feeds Richard's premarket pipeline",
    },
    "ch3_part1": {
        "source": RAW_DIR / "Chapter 3 Stock Selection, Fundamental Analysis, & Building a Watch List" / "Part 1 Stock Selection.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 3" / "Part1_Stock_Selection.txt",
        "priority": 3,
        "description": "Stock selection fundamentals",
    },
    "ch4_part1": {
        "source": RAW_DIR / "Chapter 4 Daily Chart Patterns" / "Part 1 Daily Chart Patterns.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 4" / "Part1_Daily_Chart_Patterns.txt",
        "priority": 4,
        "description": "Daily chart patterns for setup confirmation",
    },
    "ch4_part2": {
        "source": RAW_DIR / "Chapter 4 Daily Chart Patterns" / "Part 2 Daily Stock Types.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 4" / "Part2_Daily_Stock_Types.txt",
        "priority": 5,
        "description": "Daily stock types — strong vs weak charts",
    },
    "ch3_part3": {
        "source": RAW_DIR / "Chapter 3 Stock Selection, Fundamental Analysis, & Building a Watch List" / "Part 3 Fundamental Analysis.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 3" / "Part3_Fundamental_Analysis.txt",
        "priority": 6,
        "description": "Fundamental analysis basics",
    },
    "ch3_part4": {
        "source": RAW_DIR / "Chapter 3 Stock Selection, Fundamental Analysis, & Building a Watch List" / "Part 4 Easy to Borrow vs. Hard to Borrow.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 3" / "Part4_Easy_vs_Hard_Borrow.txt",
        "priority": 7,
        "description": "Short selling mechanics — easy vs hard to borrow",
    },
    # ── Course 1: Chapters 12-15 (Basic Course) ──────────────────────────────
    "ch12_scanning": {
        "source": RAW_DIR / "1. Day Trading The Basics" / "Chapter12" / "Chapter 12 Scanning 101.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 12" / "Scanning_101.txt",
        "priority": 8,
        "description": "Scanner setup and operation — CRITICAL for Richard's pipeline",
    },
    "ch13_psychology": {
        "source": RAW_DIR / "1. Day Trading The Basics" / "Chapter13" / "Chapter 13 The Psychology of Trading.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 13" / "Psychology_of_Trading.txt",
        "priority": 9,
        "description": "Hot buttons, fear/greed, emotional management",
    },
    "ch14_preparing": {
        "source": RAW_DIR / "1. Day Trading The Basics" / "Chapter14" / "Chapter 14 Preparing to Start Trading.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 14" / "Preparing_to_Start_Trading.txt",
        "priority": 10,
        "description": "Broker setup, platform config, paper trading checklist",
    },
}


def get_audio_duration(video_path: Path) -> float:
    """Get audio duration using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def transcribe_video(video_path: Path, output_path: Path, model_size: str = MODEL_SIZE):
    """Transcribe a video file and save the transcript."""
    print(f"\n{'='*60}")
    print(f"Transcribing: {video_path.name}")
    print(f"Output: {output_path}")

    if not video_path.exists():
        print(f"ERROR: Source file not found: {video_path}")
        return False

    # Get duration
    duration = get_audio_duration(video_path)
    print(f"Duration: {duration/60:.1f} min")
    print(f"Model: {model_size} | Language: {LANGUAGE}")

    # Create output dir
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load model
    print("Loading Whisper model...")
    model = faster_whisper.WhisperModel(model_size, device="cpu", compute_type="int8")

    print("Transcribing...")
    start_time = datetime.now()

    segments_gen, info = model.transcribe(
        str(video_path),
        language=LANGUAGE,
        beam_size=5,
        vad_filter=True,  # voice activity detection
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    print(f"Detected language: {info.language} ({info.language_probability:.2%})")

    full_text = []
    for i, segment in enumerate(segments_gen):
        text = segment.text.strip()
        start_ts = format_timestamp(segment.start)
        full_text.append(f"[{start_ts}] {text}")
        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1} segments...")

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"Done in {elapsed:.0f}s ({duration/elapsed:.1f}x realtime)")

    # Save transcript
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {video_path.name}\n")
        f.write(f"# Transcribed: {datetime.now().isoformat()}\n")
        f.write(f"# Duration: {duration/60:.1f} minutes\n")
        f.write(f"# Model: faster-whisper {model_size}\n")
        f.write(f"# Language: {info.language}\n\n")
        f.write("\n".join(full_text))

    print(f"Saved: {output_path}")
    return True


def format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def extract_rules(transcript_path: Path) -> dict:
    """
    Extract Ross Cameron rules from a transcript using keyword matching.
    This is a quick extraction — full LLM-based rule extraction comes later.
    """
    if not transcript_path.exists():
        return {}

    with open(transcript_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Keywords for rule extraction
    keywords = {
        "catalyst_types": ["catalyst", "news catalyst", "earnings", "FDA", "FDA approval",
                           "contract", "partnership", "upgrade", "downgrade", "news"],
        "gap_patterns": ["gap up", "gap down", "gapped up", "gapped down", "fill the gap",
                         "gap fill", "at the open", "opening range"],
        "volume_patterns": ["relative volume", "volume spike", "heavy volume", "light volume",
                           "volume confirmation", "volume dry up"],
        "risk_rules": ["stop loss", "stop out", "risk management", "position sizing",
                       "max loss", "risk reward", "risk/reward"],
        "first_pullback": ["first pullback", "pull back", "pullback", "consolidation",
                           "resting", "setup"],
        "scalping": ["scalp", "scalping", "quick trade", "intraday", "same day"],
    }

    found_rules = {}
    for category, terms in keywords.items():
        matches = []
        for term in terms:
            if term.lower() in text.lower():
                matches.append(term)
        found_rules[category] = matches

    return found_rules


def main():
    if len(sys.argv) > 1:
        # Run specific transcript
        key = sys.argv[1]
        if key in TRANSCRIPTS:
            t = TRANSCRIPTS[key]
            success = transcribe_video(t["source"], t["output"])
            if success:
                print(f"\nExtracting rules from {t['output'].name}...")
                rules = extract_rules(t["output"])
                for category, keywords in rules.items():
                    if keywords:
                        print(f"  [{category}]: {keywords}")
        else:
            print(f"Unknown key: {key}")
            print(f"Available: {list(TRANSCRIPTS.keys())}")
        return

    # Run all, prioritized
    print(f"Warrior Trading Transcription Pipeline")
    print(f"Model: {MODEL_SIZE} | Output dir: {TRANSCRIPT_DIR}")
    print(f"Found {len(TRANSCRIPTS)} videos to process\n")

    results = {}
    for key in sorted(TRANSCRIPTS, key=lambda k: TRANSCRIPTS[k]["priority"]):
        t = TRANSCRIPTS[key]
        if t["source"].exists():
            print(f"\n[Priority {t['priority']}] {t['description']}")
            success = transcribe_video(t["source"], t["output"])
            results[key] = success
            if success:
                print(f"  Extracting rules...")
                rules = extract_rules(t["output"])
                for category, keywords in rules.items():
                    if keywords:
                        print(f"    [{category}]: {keywords}")
        else:
            print(f"[Priority {t['priority']}] SKIP — file not found: {t['source'].name}")
            results[key] = False

    print(f"\n{'='*60}")
    print("SUMMARY")
    for key, success in results.items():
        status = "✅" if success else "❌"
        t = TRANSCRIPTS[key]
        print(f"  {status} {t['source'].name}: {t['description']}")


if __name__ == "__main__":
    main()
