"""
Segmentation + Transcription for Chapter 12 — Scanning 101
openai-whisper tiny — ONE segment at a time, model loads fresh per segment.
Checkpoints after each segment to survive daemon restarts.
Output: knowledge/transcripts/Chapter 12/Scanning_101.txt
"""
import subprocess, whisper, json, os
from pathlib import Path
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────────────────
VIDEO_PATH   = Path(r"E:\Me\TradingAgent\knowledge\raw\1. Day Trading The Basics\Chapter12\Chapter 12 Scanning 101.mp4")
OUTPUT_DIR   = Path(r"E:\Me\TradingAgent\knowledge\transcripts\Chapter 12")
SEG_DIR      = Path(r"E:\Me\TradingAgent\knowledge\raw\_ch12_segs")
OUTPUT_FILE  = OUTPUT_DIR / "Scanning_101.txt"
CKPT_FILE    = OUTPUT_DIR / "checkpoint.json"
MODEL_NAME   = "tiny"
SEG_DURATION = 600  # 10 min per segment


def get_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=30)
    return float(r.stdout.strip()) if r.returncode == 0 else 0.0


def extract_seg(vid, start, end, out):
    dur = end - start
    r = subprocess.run(
        ["ffmpeg", "-y", "-ss", str(start), "-t", str(dur), "-i", str(vid),
         "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(out)],
        capture_output=True, text=True, timeout=300)
    return r.returncode == 0


def transcribe_one(wav_path):
    """Load model, transcribe single file, return text + elapsed."""
    model = whisper.load_model(MODEL_NAME, device="cpu")
    t0 = datetime.now()
    result = model.transcribe(str(wav_path), language="en", beam_size=5)
    elapsed = (datetime.now() - t0).total_seconds()
    lines = []
    for seg in result.get("segments", []):
        ts = f"{int(seg['start']//3600):02d}:{int((seg['start']%3600)//60):02d}:{int(seg['start']%60):02d}"
        lines.append(f"[{ts}] {seg['text'].strip()}")
    return lines, elapsed


def save_ckpt(lines, done_segs, elapsed_total):
    ckpt = {"lines": lines, "done_segments": done_segs, "elapsed": elapsed_total}
    with open(CKPT_FILE, "w", encoding="utf-8") as f:
        json.dump(ckpt, f)
    print(f"  [CKPT] saved after segment {done_segs[-1]}")


def fmt_ts(s):
    return f"{int(s//3600):02d}:{int((s%3600)//60):02d}:{int(s%60):02d}"


# ── Main ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SEG_DIR.mkdir(parents=True, exist_ok=True)

duration = get_duration(VIDEO_PATH)
num_segs = int(duration / SEG_DURATION) + 1
print(f"Duration: {duration/60:.1f} min | Segments: {num_segs}")

# Resume from checkpoint if available
lines = []
done = []
elapsed_total = 0.0
if CKPT_FILE.exists():
    ckpt = json.loads(CKPT_FILE.read_text(encoding="utf-8"))
    lines = ckpt["lines"]
    done  = ckpt["done_segments"]
    elapsed_total = ckpt["elapsed"]
    print(f"Resuming from segment {len(done)}/{num_segs} ({len(lines)} lines saved)")

start_seg = len(done)
overall_start = datetime.now()

for i in range(start_seg, num_segs):
    start = i * SEG_DURATION
    end   = min((i + 1) * SEG_DURATION, duration)
    wav   = SEG_DIR / f"seg_{i:02d}.wav"

    print(f"\n[{i+1}/{num_segs}] {fmt_ts(start)}-{fmt_ts(end)}  →  {wav.name}")

    if not wav.exists():
        print("  Extracting audio...")
        ok = extract_seg(VIDEO_PATH, start, end, wav)
        if not ok:
            print("  FFmpeg failed — skipping")
            continue
        print(f"  Extracted: {wav.stat().st_size/1e6:.1f} MB")
    else:
        print("  Using cached WAV")

    print("  Transcribing (model loads fresh)...")
    seg_lines, seg_elapsed = transcribe_one(wav)
    elapsed_total += seg_elapsed
    lines.extend(seg_lines)
    done.append(i)
    print(f"  {len(seg_lines)} segments in {seg_elapsed:.0f}s | total lines: {len(lines)}")

    # Checkpoint after every segment
    save_ckpt(lines, done, elapsed_total)

# All done — write final transcript
overall_elapsed = (datetime.now() - overall_start).total_seconds()
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(f"# Chapter 12 — Scanning 101\n")
    f.write(f"# Source: {VIDEO_PATH.name}\n")
    f.write(f"# Transcribed: {datetime.now().isoformat()}\n")
    f.write(f"# Duration: {duration/60:.1f} min\n")
    f.write(f"# Segments: {num_segs}\n")
    f.write(f"# Model: openai-whisper {MODEL_NAME}\n")
    f.write(f"# Wall time: {overall_elapsed:.0f}s ({duration/overall_elapsed:.1f}x realtime)\n\n")
    f.write("\n".join(lines))

CKPT_FILE.unlink(missing_ok=True)
print(f"\n{'='*60}")
print(f"DONE — {len(lines)} lines in {overall_elapsed:.0f}s")
print(f"Saved: {OUTPUT_FILE}")