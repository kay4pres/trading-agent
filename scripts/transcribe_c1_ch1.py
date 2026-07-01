"""
C1 Chapter 1 Transcription — 2026-07-01 Evening Sprint
Source: Chapter1. Becoming a Day Trader_audio.wav (108.8 MB)
Segments into 18MB chunks for faster-whisper CPU processing.
"""
import subprocess
import faster_whisper
import os
from pathlib import Path
from datetime import datetime

# Paths
RAW_DIR = Path(r"E:\Me\TradingAgent\knowledge\raw\1. Day Trading The Basics\Chapter1-Becoming a Day Trader\chapter1")
WAV_FILE = list(RAW_DIR.glob("*.wav"))[0]
SEG_DIR = Path(r"E:\Me\TradingAgent\_ch1_segs")
TRANSCRIPT_DIR = Path(r"E:\Me\TradingAgent\knowledge\transcripts\Chapter 1")
OUTPUT_FILE = TRANSCRIPT_DIR / "Becoming_a_Day_Trader.txt"

SEG_SIZE_MB = 18

print(f"Source: {WAV_FILE.name}")
print(f"Size: {WAV_FILE.stat().st_size / 1e6:.1f} MB")

# Step 1: Segment
SEG_DIR.mkdir(parents=True, exist_ok=True)
result = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "default=noprint_wrappers=1:nokey=1", str(WAV_FILE)],
    capture_output=True, text=True
)
duration = float(result.stdout.strip())
print(f"Duration: {duration / 60:.1f} min")
max_seconds = int((SEG_SIZE_MB / 11) * 60)

segments = []
seg_idx = 0
for start in range(0, int(duration), max_seconds):
    seg_path = SEG_DIR / f"seg_{seg_idx:02d}.wav"
    ret = subprocess.run([
        "ffmpeg", "-y", "-ss", str(start), "-i", str(WAV_FILE),
        "-t", str(max_seconds), "-ac", "1", "-ar", "16000",
        "-acodec", "pcm_s16le", "-fs", f"{SEG_SIZE_MB}M",
        str(seg_path)
    ], capture_output=True, text=True)
    if seg_path.exists() and seg_path.stat().st_size > 50000:
        segments.append(seg_path)
        seg_idx += 1

print(f"Segmented into {len(segments)} parts")

# Step 2: Transcribe
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
print("Loading Whisper model...")
model = faster_whisper.WhisperModel("tiny", device="cpu", compute_type="int8")

def fmt(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

all_lines = []
total_start = datetime.now()
for seg in segments:
    seg_start = datetime.now()
    print(f"  Transcribing {seg.name}...")
    segs_gen, info = model.transcribe(
        str(seg), language="en", beam_size=5,
        vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500)
    )
    for seg_obj in segs_gen:
        text = seg_obj.text.strip()
        ts = fmt(seg_obj.start)
        all_lines.append(f"[{ts}] {text}")
    elapsed = (datetime.now() - seg_start).total_seconds()
    print(f"    Done in {elapsed:.0f}s")

# Save transcript
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(f"# {WAV_FILE.name}\n")
    f.write(f"# Transcribed: {datetime.now().isoformat()}\n")
    f.write(f"# Duration: {duration / 60:.1f} minutes\n")
    f.write(f"# Model: faster-whisper tiny\n")
    f.write(f"# Segments: {len(segments)}\n\n")
    f.write("\n".join(all_lines))

total_elapsed = (datetime.now() - total_start).total_seconds()
print(f"\nSaved: {OUTPUT_FILE}")
print(f"Total lines: {len(all_lines)}")
print(f"Total time: {total_elapsed:.0f}s ({duration / total_elapsed:.1f}x realtime)")
