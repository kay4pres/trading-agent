"""
Overnight transcription sprint runner — 2026-06-29
Transcribes C1: Ch2,6,7,8,9,10,11 and C2: Ch1,2,6
Uses faster-whisper tiny on CPU.
"""
import os
import sys
import json
import subprocess
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

import faster_whisper

# ── Config ──────────────────────────────────────────────────────────────────
BASE = Path(r"E:\Me\TradingAgent")
RAW = BASE / "knowledge" / "raw"
TRANSCRIPT_DIR = BASE / "knowledge" / "transcripts"
MODEL_SIZE = "tiny"
LANGUAGE = "en"
SEG_SIZE_MB = 18

C1_DIR = RAW / "1. Day Trading The Basics"
C2_DIR = RAW / "2. Day Trading Strategies & Scaling"


def get_duration(path: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def format_ts(seconds: float) -> str:
    h, m, s = int(seconds // 3600), int((seconds % 3600) // 60), int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def segment_file(path: Path, seg_dir: Path, max_mb: int = SEG_SIZE_MB) -> list[Path]:
    """Split audio/video into chunks using ffmpeg."""
    seg_dir.mkdir(parents=True, exist_ok=True)
    duration = get_duration(path)
    max_seconds = int((max_mb / 11) * 60)
    segments, idx = [], 0
    for start in range(0, int(duration), max_seconds):
        seg_path = seg_dir / f"seg_{idx:02d}.wav"
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(start), "-i", str(path),
            "-t", str(max_seconds), "-ac", "1", "-ar", "16000",
            "-acodec", "pcm_s16le", "-fs", f"{max_mb}M", str(seg_path)
        ], capture_output=True)
        if seg_path.exists() and seg_path.stat().st_size > 50000:
            segments.append(seg_path)
            idx += 1
    print(f"  Segmented into {len(segments)} parts")
    return segments


def transcribe_file(source: Path, output: Path, seg_dir: Path,
                    file_size_mb: float = None) -> bool:
    """Transcribe a single audio/video file."""
    if not source.exists():
        print(f"  ERROR: not found: {source}")
        return False

    output.parent.mkdir(parents=True, exist_ok=True)
    duration = get_duration(source)
    size_str = f"{file_size_mb:.0f}MB" if file_size_mb else ""
    print(f"  {source.name} | {duration/60:.1f} min | {size_str}")

    model = faster_whisper.WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

    # Segment if large
    if file_size_mb and file_size_mb > SEG_SIZE_MB and seg_dir:
        segments = segment_file(source, seg_dir)
        if not segments:
            return False
        all_lines = []
        for seg in segments:
            segs_gen, _ = model.transcribe(str(seg), language=LANGUAGE,
                                           beam_size=5, vad_filter=True,
                                           vad_parameters=dict(min_silence_duration_ms=500))
            for s in segs_gen:
                all_lines.append(f"[{format_ts(s.start)}] {s.text.strip()}")
        with open(output, "w", encoding="utf-8") as f:
            f.write(f"# Segments: {len(segments)}\n# Transcribed: {datetime.now().isoformat()}\n\n")
            f.write("\n".join(all_lines))
    else:
        print("  Loading model...")
        start = datetime.now()
        segs_gen, info = model.transcribe(str(source), language=LANGUAGE,
                                          beam_size=5, vad_filter=True,
                                          vad_parameters=dict(min_silence_duration_ms=500))
        elapsed = (datetime.now() - start).total_seconds()
        print(f"  Done in {elapsed:.0f}s ({duration/elapsed:.1f}x realtime)")
        lines = []
        for s in segs_gen:
            lines.append(f"[{format_ts(s.start)}] {s.text.strip()}")
        with open(output, "w", encoding="utf-8") as f:
            f.write(f"# {source.name}\n# Transcribed: {datetime.now().isoformat()}\n"
                    f"# Duration: {duration/60:.1f} minutes\n"
                    f"# Model: faster-whisper {MODEL_SIZE}\n\n")
            f.write("\n".join(lines))

    print(f"  Saved: {output.name}")
    return True


# ── Target definitions ───────────────────────────────────────────────────────
# Each entry: (source_path, output_path, seg_dir, description)
TARGETS = [
    # ── C1 Chapter 2: Picking Stocks (3 parts) ──────────────────────────────
    {
        "source": C1_DIR / "Chapter2" / "Picking stocks P1_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter 2" / "Part1_Picking_Stocks.txt",
        "seg": BASE / "_c1_ch2_p1_segs",
        "desc": "C1 Ch2 P1 — Picking Stocks",
        "size_mb": None,
    },
    {
        "source": C1_DIR / "Chapter2" / "Picking stocks P2-Long vs short selling_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter 2" / "Part2_Long_Short_Selling.txt",
        "seg": BASE / "_c1_ch2_p2_segs",
        "desc": "C1 Ch2 P2 — Long vs Short Selling",
        "size_mb": None,
    },
    {
        "source": C1_DIR / "Chapter2" / "Picking stocks P3-What makes a strong stock_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter 2" / "Part3_Strong_Stock.txt",
        "seg": BASE / "_c1_ch2_p3_segs",
        "desc": "C1 Ch2 P3 — What Makes a Strong Stock",
        "size_mb": None,
    },
    # ── C1 Chapter 6: Trading Platform ─────────────────────────────────────
    {
        "source": C1_DIR / "Chapter6" / "Ch6-Trading-Platform-Walk-Through_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter 6" / "Trading_Platform_Walkthrough.txt",
        "seg": BASE / "_c1_ch6_segs",
        "desc": "C1 Ch6 — Trading Platform Walk-Through",
        "size_mb": None,
    },
    # ── C1 Chapter 7 ───────────────────────────────────────────────────────
    {
        "source": C1_DIR / "Chapter7" / "20260216-0922-09.7543342_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter 7" / "Chapter7.txt",
        "seg": BASE / "_c1_ch7_segs",
        "desc": "C1 Ch7",
        "size_mb": None,
    },
    # ── C1 Chapter 8 ───────────────────────────────────────────────────────
    {
        "source": C1_DIR / "Chapter8" / "20260216-0957-32.4306224_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter 8" / "Chapter8.txt",
        "seg": BASE / "_c1_ch8_segs",
        "desc": "C1 Ch8",
        "size_mb": None,
    },
    # ── C1 Chapter 9: Order Entry ──────────────────────────────────────────
    {
        "source": C1_DIR / "Chapter9" / "Chapter 9 Order Entry Window and Popular Order Types_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter 9" / "Order_Entry_Types.txt",
        "seg": BASE / "_c1_ch9_segs",
        "desc": "C1 Ch9 — Order Entry & Order Types",
        "size_mb": None,
    },
    # ── C1 Chapter 10: Hot Keys (2 parts) ──────────────────────────────────
    {
        "source": C1_DIR / "Chapter10" / "Chapter10-Part 1 Hot Keys_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter 10" / "Part1_Hot_Keys.txt",
        "seg": BASE / "_c1_ch10_p1_segs",
        "desc": "C1 Ch10 P1 — Hot Keys",
        "size_mb": None,
    },
    {
        "source": C1_DIR / "Chapter10" / "Chapter10-Part 2 Hot Buttons_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter 10" / "Part2_Hot_Buttons.txt",
        "seg": BASE / "_c1_ch10_p2_segs",
        "desc": "C1 Ch10 P2 — Hot Buttons",
        "size_mb": None,
    },
    # ── C1 Chapter 11: Stock Halts ──────────────────────────────────────────
    {
        "source": C1_DIR / "Chapter11" / "Chapter 11 Stock Halts_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter 11" / "Stock_Halts.txt",
        "seg": BASE / "_c1_ch11_segs",
        "desc": "C1 Ch11 — Stock Halts",
        "size_mb": None,
    },
    # ── C2 Chapter 1: Intro to Day Trading ─────────────────────────────────
    {
        "source": C2_DIR / "Chapter 1 Intro to Day Trading" / "Intro to My Day Trading Strategies.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 1 Course2" / "Intro_Day_Trading.txt",
        "seg": BASE / "_c2_ch1_segs",
        "desc": "C2 Ch1 — Intro to Day Trading Strategies",
        "size_mb": None,
    },
    # ── C2 Chapter 2: Risk Management ──────────────────────────────────────
    {
        "source": C2_DIR / "Chapter 2 Risk Management" / "Learning to Manage Your Risk.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 2 Course2" / "Learning_Risk_Management.txt",
        "seg": BASE / "_c2_ch2_segs",
        "desc": "C2 Ch2 — Learning to Manage Your Risk",
        "size_mb": None,
    },
    # ── C2 Chapter 6: Level 2, Tape Reading, Hot Keys (8 MP4s) ─────────────
    {
        "source": C2_DIR / "Chapter 6 Level 2, Tape Reading, and Hot KeysButtons" / "Part 1 Level 2 and Time and Sales.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 6 Course2" / "Part1_Level2_Time_Sales.txt",
        "seg": BASE / "_c2_ch6_p1_segs",
        "desc": "C2 Ch6 P1 — Level 2 & Time & Sales",
        "size_mb": None,
    },
    {
        "source": C2_DIR / "Chapter 6 Level 2, Tape Reading, and Hot KeysButtons" / "Part 2 ADFN Prints .mp4",
        "output": TRANSCRIPT_DIR / "Chapter 6 Course2" / "Part2_ADFN_Prints.txt",
        "seg": BASE / "_c2_ch6_p2_segs",
        "desc": "C2 Ch6 P2 — ADFN Prints",
        "size_mb": None,
    },
    {
        "source": C2_DIR / "Chapter 6 Level 2, Tape Reading, and Hot KeysButtons" / "Part 3 Circuit Breaker Halts.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 6 Course2" / "Part3_Circuit_Breaker_Halts.txt",
        "seg": BASE / "_c2_ch6_p3_segs",
        "desc": "C2 Ch6 P3 — Circuit Breaker Halts",
        "size_mb": None,
    },
    {
        "source": C2_DIR / "Chapter 6 Level 2, Tape Reading, and Hot KeysButtons" / "Part 4 Market Makers.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 6 Course2" / "Part4_Market_Makers.txt",
        "seg": BASE / "_c2_ch6_p4_segs",
        "desc": "C2 Ch6 P4 — Market Makers",
        "size_mb": None,
    },
    {
        "source": C2_DIR / "Chapter 6 Level 2, Tape Reading, and Hot KeysButtons" / "Part 5 PFOF vs Direct Access.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 6 Course2" / "Part5_PFOF_Direct_Access.txt",
        "seg": BASE / "_c2_ch6_p5_segs",
        "desc": "C2 Ch6 P5 — PFOF vs Direct Access",
        "size_mb": None,
    },
    {
        "source": C2_DIR / "Chapter 6 Level 2, Tape Reading, and Hot KeysButtons" / "Part 6 Order Routing, Order Types, and Adding Liquidity.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 6 Course2" / "Part6_Order_Routing.txt",
        "seg": BASE / "_c2_ch6_p6_segs",
        "desc": "C2 Ch6 P6 — Order Routing & Liquidity",
        "size_mb": None,
    },
    {
        "source": C2_DIR / "Chapter 6 Level 2, Tape Reading, and Hot KeysButtons" / "Part 7 Advanced Hot Keys and Hot Buttons.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 6 Course2" / "Part7_Advanced_Hot_Keys.txt",
        "seg": BASE / "_c2_ch6_p7_segs",
        "desc": "C2 Ch6 P7 — Advanced Hot Keys & Buttons",
        "size_mb": None,
    },
    {
        "source": C2_DIR / "Chapter 6 Level 2, Tape Reading, and Hot KeysButtons" / "Part 8 Multi-Account Syncing.mp4",
        "output": TRANSCRIPT_DIR / "Chapter 6 Course2" / "Part8_Multi_Account_Syncing.txt",
        "seg": BASE / "_c2_ch6_p8_segs",
        "desc": "C2 Ch6 P8 — Multi-Account Syncing",
        "size_mb": None,
    },
]


def main():
    total = len(TARGETS)
    results = {}
    print(f"\n{'='*60}")
    print(f"OVERNIGHT TRANSCRIPTION SPRINT — 2026-06-29")
    print(f"Total targets: {total}")
    print(f"Model: {MODEL_SIZE} | CPU | faster-whisper")
    print(f"{'='*60}\n")

    for i, t in enumerate(TARGETS, 1):
        print(f"[{i}/{total}] {t['desc']}")
        try:
            success = transcribe_file(
                t["source"], t["output"], t["seg"], t.get("size_mb")
            )
            results[t["desc"]] = success
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            results[t["desc"]] = False

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    print(f"  Passed: {passed}/{total}")
    print(f"  Failed: {failed}/{total}")
    for desc, ok in results.items():
        status = "✅" if ok else "❌"
        print(f"  {status} {desc}")

    # Save results
    report = BASE / "_transcription_results.json"
    with open(report, "w", encoding="utf-8") as f:
        json.dump({"total": total, "passed": passed, "failed": failed,
                   "results": results, "timestamp": datetime.now().isoformat()}, f,
                  indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {report}")


if __name__ == "__main__":
    main()
