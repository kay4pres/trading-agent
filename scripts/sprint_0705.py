"""
Overnight transcription sprint - 2026-07-05
Transcribes: C1 Ch1, C2 Ch1, C2 Ch2
"""
import sys, subprocess, faster_whisper
from pathlib import Path
from datetime import datetime

MODEL_SIZE = "tiny"
LANGUAGE = "en"
SEG_SIZE_MB = 18

def format_ts(s):
    h, m, s = int(s//3600), int((s%3600)//60), int(s%60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def get_duration(path):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)], capture_output=True, text=True, timeout=30)
    return float(r.stdout.strip())

def segment_audio(video_path, output_dir, max_size_mb=SEG_SIZE_MB):
    output_dir.mkdir(parents=True, exist_ok=True)
    duration = get_duration(video_path)
    max_seconds = int((max_size_mb / 11) * 60)
    segments = []
    seg_idx = 0
    for start in range(0, int(duration), max_seconds):
        seg_path = output_dir / f"seg_{seg_idx:02d}.wav"
        subprocess.run(["ffmpeg","-y","-ss",str(start),"-i",str(video_path),"-t",str(max_seconds),"-ac","1","-ar","16000","-acodec","pcm_s16le","-fs",f"{max_size_mb}M",str(seg_path)], capture_output=True, text=True)
        if seg_path.exists() and seg_path.stat().st_size > 50000:
            segments.append(seg_path)
            seg_idx += 1
    print(f"  Segmented into {len(segments)} parts")
    return segments

def transcribe(source, output, seg_dir, force=False):
    """Transcribe a video/audio file."""
    if not force and output.exists() and output.stat().st_size > 500000:
        print(f"SKIP (exists, {output.stat().st_size//1024} KB): {output.name}")
        return True
    
    if not source.exists():
        print(f"ERROR: Source not found: {source}")
        return False
    
    duration = get_duration(source)
    print(f"\nTranscribing: {source.name}")
    print(f"Duration: {duration/60:.1f} min | Size: {source.stat().st_size/1e6:.0f} MB")
    
    all_lines = []
    if duration > 90:
        segs = segment_audio(source, seg_dir)
        model = faster_whisper.WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        for seg in segs:
            print(f"  Transcribing {seg.name}...")
            gen, _ = model.transcribe(str(seg), language=LANGUAGE, beam_size=5, 
                                       vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))
            for s in gen:
                all_lines.append(f"[{format_ts(s.start)}] {s.text.strip()}")
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output,"w",encoding="utf-8") as f:
            f.write(f"# Segments: {len(segs)}\n")
            f.write(f"# Transcribed: {datetime.now().isoformat()}\n\n")
            f.write("\n".join(all_lines))
    else:
        model = faster_whisper.WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        print("Transcribing...")
        gen, info = model.transcribe(str(source), language=LANGUAGE, beam_size=5, 
                                     vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))
        for s in gen:
            all_lines.append(f"[{format_ts(s.start)}] {s.text.strip()}")
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output,"w",encoding="utf-8") as f:
            f.write(f"# {source.name}\n# Transcribed: {datetime.now().isoformat()}\n# Duration: {duration/60:.1f} min\n\n")
            f.write("\n".join(all_lines))
    
    print(f"Saved: {output} ({len(all_lines)} lines)")
    return True

# ── Targets ────────────────────────────────────────────────────────────────
BASE = Path(r"E:\Me\TradingAgent")
RAW = BASE / "knowledge" / "raw"
TRANS = BASE / "knowledge" / "transcripts"

C1 = RAW / "1. Day Trading The Basics"
C2 = RAW / "2. Day Trading Strategies & Scaling"

targets = [
    # C1 Ch1 — WAV in chapter1/ subdirectory
    {
        "name": "C1 Ch1 - Becoming a Day Trader",
        "source": C1 / "Chapter1-Becoming a Day Trader" / "chapter1" / "Chapter1. Becoming a Day Trader_audio.wav",
        "output": TRANS / "Chapter 1" / "Becoming_a_Day_Trader.txt",
        "seg_dir": BASE / "_c1_ch1_segs",
    },
    # C2 Ch1 — WAV already extracted to E:
    {
        "name": "C2 Ch1 - Intro to Day Trading",
        "source": Path(r"E:\Me\_c2_ch1_audio.wav"),
        "output": TRANS / "Chapter 1 Course2" / "Intro_Day_Trading.txt",
        "seg_dir": BASE / "_c2_ch1_segs",
    },
    # C2 Ch2 — MP4 (will extract audio first inline)
    {
        "name": "C2 Ch2 - Risk Management",
        "source": C2 / "Chapter 2 Risk Management" / "Learning to Manage Your Risk.mp4",
        "output": TRANS / "Chapter 2 Course2" / "Learning_Risk_Management.txt",
        "seg_dir": BASE / "_c2_ch2_segs",
        "extract_wav": str(BASE / "_c2_ch2_audio.wav"),
    },
]

if __name__ == "__main__":
    print(f"Warrior Trading Sprint — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Model: {MODEL_SIZE} | CPU | {' '.join([t['name'] for t in targets])}")
    
    results = {}
    for t in targets:
        # Extract WAV if needed
        wav_src = t["source"]
        if t.get("extract_wav"):
            wav_path = Path(t["extract_wav"])
            if not wav_path.exists():
                print(f"\nExtracting audio from {t['name']}...")
                subprocess.run(["ffmpeg","-y","-i",str(t["source"]),"-ac","1","-ar","16000",str(wav_path)], capture_output=True)
                print(f"  Audio extracted: {wav_path.stat().st_size/1e6:.0f} MB")
            wav_src = wav_path
        
        success = transcribe(wav_src, t["output"], t["seg_dir"])
        results[t["name"]] = success
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    for name, ok in results.items():
        print(f"  {'✅' if ok else '❌'} {name}")
