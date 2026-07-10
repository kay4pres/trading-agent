"""
Sprint driver: transcribe C2 Ch12-15 new MP4s added 2026-07-10.
Pattern (from memory, proven in C2 Ch7 sprint):
  1) extract full WAV from MP4 (1-2s, much faster than per-chunk re-decode)
  2) segment WAV into ~18MB chunks
  3) faster-whisper tiny + VAD
  4) cleanup WAV + segments after each file
"""
import os, sys, subprocess, shutil
from pathlib import Path
from datetime import datetime
import faster_whisper

# Config
MODEL_SIZE = "tiny"
LANGUAGE = "en"
SEG_SIZE_MB = 18
KNOWLEDGE = Path(r"E:\Me\TradingAgent\knowledge")
RAW = KNOWLEDGE / "raw" / "2. Day Trading Strategies & Scaling"
TRANSCRIPT = KNOWLEDGE / "transcripts"
WORK = Path(r"E:\_sprint_c2_ch12_15")

# (source, output_dir, output_basename, description, work_seg_dir_name)
C2 = RAW
TARGETS = [
    # Ch12 — Stock Scanning
    (C2 / "Chapter 12 Stock Scanning (featuring Day Trade Dash Scanner)" / "Stock Scanning (featuring Day Trade Dash Scanner).mp4",
     TRANSCRIPT / "Chapter 12 Course2", "Part1_Stock_Scanning_DayTradeDash.txt",
     "Ch12 Stock Scanning / Day Trade Dash", "ch12"),
    # Ch13 — Trading Psychology
    (C2 / "Chapter 13 Trading Psychology, Building Discipline, and Recovering from Loss" / "Trading Psychology, Building Discipline, and Recovering from Loss.mp4",
     TRANSCRIPT / "Chapter 13 Course2", "Part1_Trading_Psychology.txt",
     "Ch13 Trading Psychology", "ch13"),
    # Ch14 — Trading Plan
    (C2 / "Chapter 14 Creating a Trading Plan" / "Part 1 The Trading Plan I Would Use as a Beginner.mp4",
     TRANSCRIPT / "Chapter 14 Course2", "Part1_Trading_Plan_Beginner.txt",
     "Ch14 P1 Trading Plan Beginner", "ch14p1"),
    (C2 / "Chapter 14 Creating a Trading Plan" / "Part 2 The Strategy I Would Use as a Beginner.mp4",
     TRANSCRIPT / "Chapter 14 Course2", "Part2_Strategy_Beginner.txt",
     "Ch14 P2 Strategy Beginner", "ch14p2"),
    # Ch15 — Real Money
    (C2 / "Chapter 15 When to Trade with Real Money & Position Management" / "Part 1 When to Trade with Real Money.mp4",
     TRANSCRIPT / "Chapter 15 Course2", "Part1_When_Real_Money.txt",
     "Ch15 P1 When to Trade Real Money", "ch15p1"),
    (C2 / "Chapter 15 When to Trade with Real Money & Position Management" / "Part 2 Increasing Share Size.mp4",
     TRANSCRIPT / "Chapter 15 Course2", "Part2_Increasing_Share_Size.txt",
     "Ch15 P2 Increasing Share Size", "ch15p2"),
    (C2 / "Chapter 15 When to Trade with Real Money & Position Management" / "Part 3 Increasing the Number of Trades Per Day.mp4",
     TRANSCRIPT / "Chapter 15 Course2", "Part3_Increasing_Trades_Per_Day.txt",
     "Ch15 P3 Increasing Trades Per Day", "ch15p3"),
    (C2 / "Chapter 15 When to Trade with Real Money & Position Management" / "Part 4 Scaling Out of Trades.mp4",
     TRANSCRIPT / "Chapter 15 Course2", "Part4_Scaling_Out.txt",
     "Ch15 P4 Scaling Out", "ch15p4"),
    (C2 / "Chapter 15 When to Trade with Real Money & Position Management" / "Part 5 Scaling Into Trades and Out of Trades.mp4",
     TRANSCRIPT / "Chapter 15 Course2", "Part5_Scaling_In_Out.txt",
     "Ch15 P5 Scaling In and Out", "ch15p5"),
]


def fmt_ts(s):
    h = int(s // 3600); m = int((s % 3600) // 60); sec = int(s % 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def extract_full_wav(mp4: Path, wav_path: Path) -> bool:
    """Step 1: full audio extraction. ~1-2s for full file."""
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    if wav_path.exists() and wav_path.stat().st_size > 100_000:
        print(f"  [skip] WAV exists: {wav_path.name} ({wav_path.stat().st_size/1048576:.0f}MB)")
        return True
    r = subprocess.run([
        "ffmpeg", "-y", "-i", str(mp4),
        "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le",
        str(wav_path)
    ], capture_output=True, text=True)
    if not wav_path.exists() or wav_path.stat().st_size < 100_000:
        print(f"  [FAIL] WAV extraction failed for {mp4.name}")
        print(r.stderr[-500:])
        return False
    print(f"  [ok] WAV extracted: {wav_path.name} ({wav_path.stat().st_size/1048576:.0f}MB)")
    return True


def segment_wav(wav: Path, seg_dir: Path) -> list:
    """Step 2: split WAV into ~18MB chunks via ffmpeg."""
    seg_dir.mkdir(parents=True, exist_ok=True)
    # clean old segs
    for old in seg_dir.glob("seg_*.wav"):
        old.unlink()
    r = subprocess.run([
        "ffmpeg", "-y", "-i", str(wav),
        "-f", "segment", "-segment_time", "600",  # 10-min chunks
        "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le",
        "-fs", f"{SEG_SIZE_MB}M",
        str(seg_dir / "seg_%02d.wav")
    ], capture_output=True, text=True)
    segs = sorted(seg_dir.glob("seg_*.wav"))
    print(f"  [ok] Segmented into {len(segs)} chunks")
    return segs


def transcribe_segs(seg_dir: Path, model, out_path: Path, src_name: str):
    """Step 3: whisper each segment, concatenate with timestamps."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    segs = sorted(seg_dir.glob("seg_*.wav"))
    all_lines = []
    for seg in segs:
        print(f"    transcribing {seg.name}...")
        t0 = datetime.now()
        segs_gen, info = model.transcribe(
            str(seg), language=LANGUAGE, beam_size=5,
            vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500),
        )
        for s in segs_gen:
            t = s.text.strip()
            if t:
                all_lines.append(f"[{fmt_ts(s.start)}] {t}")
        print(f"      ({ (datetime.now()-t0).total_seconds():.0f}s)")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# {src_name}\n")
        f.write(f"# Transcribed: {datetime.now().isoformat()}\n")
        f.write(f"# Model: faster-whisper {MODEL_SIZE}\n")
        f.write(f"# Language: {LANGUAGE}\n")
        f.write(f"# Segments: {len(segs)}\n")
        f.write(f"# Lines: {len(all_lines)}\n\n")
        f.write("\n".join(all_lines))
    print(f"  [ok] Saved: {out_path} ({out_path.stat().st_size/1024:.0f}KB, {len(all_lines)} lines)")


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    print(f"Loading Whisper {MODEL_SIZE} model...")
    model = faster_whisper.WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    print(f"Model loaded.\n")

    results = []
    for idx, (src, out_dir, out_name, desc, seg_name) in enumerate(TARGETS, 1):
        print(f"\n{'='*70}")
        print(f"[{idx}/{len(TARGETS)}] {desc}")
        print(f"  source: {src.name}")
        if not src.exists():
            print(f"  [SKIP] not found")
            results.append((desc, False, "missing"))
            continue
        print(f"  size: {src.stat().st_size/1048576:.0f}MB")

        wav_path = WORK / f"{seg_name}_full.wav"
        seg_dir = WORK / f"{seg_name}_segs"
        out_path = out_dir / out_name

        if out_path.exists() and out_path.stat().st_size > 1000:
            print(f"  [SKIP] already transcribed: {out_path.name}")
            results.append((desc, True, "exists"))
            continue

        t_start = datetime.now()
        if not extract_full_wav(src, wav_path):
            results.append((desc, False, "extract_fail"))
            continue
        segs = segment_wav(wav_path, seg_dir)
        if not segs:
            results.append((desc, False, "segment_fail"))
            continue
        transcribe_segs(seg_dir, model, out_path, src.name)
        elapsed = (datetime.now() - t_start).total_seconds()
        print(f"  TOTAL: {elapsed/60:.1f} min")
        results.append((desc, True, f"{elapsed/60:.1f}min"))

        # cleanup WAV and segs to save disk
        try:
            wav_path.unlink()
            shutil.rmtree(seg_dir, ignore_errors=True)
            print(f"  [cleanup] WAV and segs removed")
        except Exception as e:
            print(f"  [cleanup warn] {e}")

    print(f"\n{'='*70}\nSUMMARY")
    for desc, ok, info in results:
        mark = "[OK]" if ok else "[FAIL]"
        print(f"  {mark} {desc} — {info}")


if __name__ == "__main__":
    main()
