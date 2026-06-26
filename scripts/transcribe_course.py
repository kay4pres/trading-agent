"""
Whisper transcription pipeline for Warrior Trading course videos.
Uses faster-whisper for speed on CPU.
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
KNOWLEDGE_DIR = Path(r"E:\Me\TradingAgent\knowledge")
RAW_DIR = KNOWLEDGE_DIR / "raw"
TRANSCRIPT_DIR = KNOWLEDGE_DIR / "transcripts"
MODEL_SIZE = "tiny"  # fastest, good for rule extraction
LANGUAGE = "en"
SEG_SIZE_MB = 18  # ~18 min per segment for faster-whisper CPU
SEG_DIR = KNOWLEDGE_DIR / "_ch5_course1_segs"


def segment_audio(video_path: Path, output_dir: Path, max_size_mb: int = SEG_SIZE_MB) -> list[Path]:
    """
    Split audio/video into chunks using ffmpeg.
    Chunks by file size (MB) rather than duration to keep memory manageable.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get duration
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True, timeout=30
    )
    duration = float(result.stdout.strip())
    max_seconds = int((max_size_mb / 11) * 60)  # ~11MB/min estimate for 16kHz mono

    segments = []
    seg_idx = 0
    for start in range(0, int(duration), max_seconds):
        seg_path = output_dir / f"seg_{seg_idx:02d}.wav"
        ret = subprocess.run([
            "ffmpeg", "-y", "-ss", str(start), "-i", str(video_path),
            "-t", str(max_seconds), "-ac", "1", "-ar", "16000",
            "-acodec", "pcm_s16le", "-fs", f"{max_size_mb}M",
            str(seg_path)
        ], capture_output=True, text=True)
        if seg_path.exists() and seg_path.stat().st_size > 50000:
            segments.append(seg_path)
            seg_idx += 1

    print(f"  Segmented into {len(segments)} parts")
    return segments


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


def transcribe_segments(segments: list[Path], output_path: Path, model_size: str = MODEL_SIZE):
    """Transcribe pre-split segments and concatenate."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    model = faster_whisper.WhisperModel(model_size, device="cpu", compute_type="int8")

    all_lines = []
    for seg in segments:
        print(f"  Transcribing {seg.name}...")
        segs_gen, info = model.transcribe(
            str(seg), language=LANGUAGE, beam_size=5,
            vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500)
        )
        for seg_obj in segs_gen:
            text = seg_obj.text.strip()
            ts = format_timestamp(seg_obj.start)
            all_lines.append(f"[{ts}] {text}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Segments: {len(segments)}\n")
        f.write(f"# Transcribed: {datetime.now().isoformat()}\n\n")
        f.write("\n".join(all_lines))

    return output_path


def transcribe_video(video_path: Path, output_path: Path, model_size: str = MODEL_SIZE,
                     file_size_mb: float = None, seg_dir: Path = None):
    """
    Transcribe a video/audio file. Auto-segments if > SEG_SIZE_MB.
    """
    print(f"\n{'='*60}")
    print(f"Transcribing: {video_path.name}")
    print(f"Output: {output_path}")

    if not video_path.exists():
        print(f"ERROR: Source file not found: {video_path}")
        return False

    duration = get_audio_duration(video_path)
    print(f"Duration: {duration/60:.1f} min | Size: {file_size_mb:.0f}MB" if file_size_mb else f"Duration: {duration/60:.1f} min")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if file_size_mb and file_size_mb > SEG_SIZE_MB and seg_dir:
        # Segment and transcribe in pieces
        segments = segment_audio(video_path, seg_dir)
        if segments:
            transcribe_segments(segments, output_path, model_size)
            print(f"Saved (segmented): {output_path}")
        return True

    # Direct transcription for smaller files
    print("Loading Whisper model...")
    model = faster_whisper.WhisperModel(model_size, device="cpu", compute_type="int8")

    print("Transcribing...")
    start_time = datetime.now()

    segments_gen, info = model.transcribe(
        str(video_path),
        language=LANGUAGE,
        beam_size=5,
        vad_filter=True,
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
    """Extract Ross Cameron rules from a transcript using keyword matching."""
    if not transcript_path.exists():
        return {}

    with open(transcript_path, "r", encoding="utf-8") as f:
        text = f.read()

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
        "chart_patterns": ["double top", "double bottom", "head and shoulders", "cup and handle",
                           "bull flag", "bear flag", "ABCD", "pivot", "support", "resistance",
                           "breakout", "breakdown", "VWAP", "moving average"],
        "timeframes": ["5-minute", "1-minute", "15-minute", "daily chart", "intraday"],
    }

    found_rules = {}
    for category, terms in keywords.items():
        matches = [t for t in terms if t.lower() in text.lower()]
        if matches:
            found_rules[category] = matches

    return found_rules


# ── Ch5 Transcription Targets ──────────────────────────────────────────────
C1 = RAW_DIR / "1. Day Trading The Basics"
C2 = RAW_DIR / "2. Day Trading Strategies & Scaling"
C5 = C2 / "Chapter 5 Intraday Chart Patterns"

CH5_COURSE1 = {
    "c1_ch5_p1": {
        "source": C1 / "Chapter5" / "Ch5-Part1-Chart Types and Time Frames_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter5_Course1" / "Part1_Chart_Types_Time_Frames.txt",
        "size_mb": 50, "seg": KNOWLEDGE_DIR / "_ch5_c1_p1_segs",
        "description": "Chart Types and Time Frames",
    },
    "c1_ch5_p2": {
        "source": C1 / "Chapter5" / "Ch5-Part2-Candlesticks_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter5_Course1" / "Part2_Candlesticks.txt",
        "size_mb": 84, "seg": KNOWLEDGE_DIR / "_ch5_c1_p2_segs",
        "description": "Candlestick Basics",
    },
    "c1_ch5_p3": {
        "source": C1 / "Chapter5" / "Ch5-part3-Multi-Candlestick Chart Patterns_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter5_Course1" / "Part3_Multi_Candlestick_Patterns.txt",
        "size_mb": 93, "seg": KNOWLEDGE_DIR / "_ch5_c1_p3_segs",
        "description": "Multi-Candlestick Chart Patterns",
    },
    "c1_ch5_p4": {
        "source": C1 / "Chapter5" / "Ch5-part4-Support-and-resistance_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter5_Course1" / "Part4_Support_Resistance.txt",
        "size_mb": 78, "seg": KNOWLEDGE_DIR / "_ch5_c1_p4_segs",
        "description": "Support and Resistance",
    },
    "c1_ch5_p5": {
        "source": C1 / "Chapter5" / "Ch5-part5-Gaps-and-Windows-on-Daily-Charts_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter5_Course1" / "Part5_Gaps_Windows.txt",
        "size_mb": 66, "seg": KNOWLEDGE_DIR / "_ch5_c1_p5_segs",
        "description": "Gaps and Windows on Daily Charts",
    },
    "c1_ch5_p6": {
        "source": C1 / "Chapter5" / "Ch5-part6-Multi-Time-Frame-Alignment_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter5_Course1" / "Part6_Multi_Timeframe_Alignment.txt",
        "size_mb": 28, "seg": KNOWLEDGE_DIR / "_ch5_c1_p6_segs",
        "description": "Multi-Time-Frame Alignment",
    },
    "c1_ch5_p7": {
        "source": C1 / "Chapter5" / "Ch5-part7-Popular-Technical-Indicators_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter5_Course1" / "Part7_Technical_Indicators.txt",
        "size_mb": 66, "seg": KNOWLEDGE_DIR / "_ch5_c1_p7_segs",
        "description": "Popular Technical Indicators",
    },
    "c1_ch5_p8": {
        "source": C1 / "Chapter5" / "Ch5-part8-Understanding-what-makes-a-strong-or-weak-Daily-Chart_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter5_Course1" / "Part8_Strong_Weak_Charts.txt",
        "size_mb": 33, "seg": KNOWLEDGE_DIR / "_ch5_c1_p8_segs",
        "description": "Strong vs Weak Daily Charts",
    },
    "c1_ch5_p9": {
        "source": C1 / "Chapter5" / "Ch5-part9-Setting-up-your-Charts_audio.wav",
        "output": TRANSCRIPT_DIR / "Chapter5_Course1" / "Part9_Chart_Setup.txt",
        "size_mb": 22, "seg": KNOWLEDGE_DIR / "_ch5_c1_p9_segs",
        "description": "Setting Up Your Charts",
    },
}

CH5_COURSE2 = {
    "c2_ch5_intro": {
        "source": C5 / "Intro to Intraday Chart Patterns.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "Intro_Intraday_Patterns.txt",
        "size_mb": 14, "seg": KNOWLEDGE_DIR / "_ch5_c2_intro_segs",
        "description": "Intro to Intraday Chart Patterns",
    },
    "c2_ch5_abcd": {
        "source": C5 / "ABCD Pattern.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "ABCD_Pattern.txt",
        "size_mb": 19, "seg": KNOWLEDGE_DIR / "_ch5_c2_abcd_segs",
        "description": "ABCD Pattern",
    },
    "c2_ch5_algo": {
        "source": C5 / "Algo Spikes.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "Algo_Spikes.txt",
        "size_mb": 21, "seg": KNOWLEDGE_DIR / "_ch5_c2_algo_segs",
        "description": "Algo Spikes",
    },
    "c2_ch5_vwap": {
        "source": C5 / "Break of VWAP  Sub VWAP Trap  Fade Off VWAP Patterns.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "VWAP_Patterns.txt",
        "size_mb": 36, "seg": KNOWLEDGE_DIR / "_ch5_c2_vwap_segs",
        "description": "VWAP Patterns",
    },
    "c2_ch5_flags": {
        "source": C5 / "Bull Flags & Bear Flags.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "Bull_Bear_Flags.txt",
        "size_mb": 30, "seg": KNOWLEDGE_DIR / "_ch5_c2_flags_segs",
        "description": "Bull Flags & Bear Flags",
    },
    "c2_ch5_traps": {
        "source": C5 / "Bull Traps, Bear Traps, Liquidity Traps, Jackknife Candles.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "Trap_Patterns.txt",
        "size_mb": 27, "seg": KNOWLEDGE_DIR / "_ch5_c2_traps_segs",
        "description": "Bull/Bear/Liquidity Traps, Jackknife Candles",
    },
    "c2_ch5_cup": {
        "source": C5 / "Cup and Handle Pattern.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "Cup_Handle.txt",
        "size_mb": 18, "seg": KNOWLEDGE_DIR / "_ch5_c2_cup_segs",
        "description": "Cup and Handle Pattern",
    },
    "c2_ch5_curling": {
        "source": C5 / "Curling Pattern.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "Curling_Pattern.txt",
        "size_mb": 16, "seg": KNOWLEDGE_DIR / "_ch5_c2_curling_segs",
        "description": "Curling Pattern",
    },
    "c2_ch5_double": {
        "source": C5 / "Double Top and Double Bottom Pattern.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "Double_Top_Bottom.txt",
        "size_mb": 19, "seg": KNOWLEDGE_DIR / "_ch5_c2_double_segs",
        "description": "Double Top and Double Bottom",
    },
    "c2_ch5_frontback": {
        "source": C5 / "Frontside vs. Backside of Momentum.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "Frontside_Backside_Momentum.txt",
        "size_mb": 20, "seg": KNOWLEDGE_DIR / "_ch5_c2_frontback_segs",
        "description": "Frontside vs Backside of Momentum",
    },
    "c2_ch5_hns": {
        "source": C5 / "Head and Shoulders Pattern & Inverted Head and Shoulders Pattern.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "Head_Shoulders.txt",
        "size_mb": 23, "seg": KNOWLEDGE_DIR / "_ch5_c2_hns_segs",
        "description": "Head and Shoulders & Inverted",
    },
    "c2_ch5_hod": {
        "source": C5 / "High of Day Breakouts & Low of Day Breakdowns Including Flat Top Breakout & Flat Bottom Breakdown Patterns.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "HOD_LOD_Breakouts.txt",
        "size_mb": 30, "seg": KNOWLEDGE_DIR / "_ch5_c2_hod_segs",
        "description": "HOD/LOD Breakouts",
    },
    "c2_ch5_srr": {
        "source": C5 / "Horizontal and Ascending  Descending Support  Resistance Lines.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "SR_Lines.txt",
        "size_mb": 25, "seg": KNOWLEDGE_DIR / "_ch5_c2_srr_segs",
        "description": "Support/Resistance Lines",
    },
    "c2_ch5_vwappull": {
        "source": C5 / "Moving Average  VWAP Pullbacks.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "MA_VWAP_Pullbacks.txt",
        "size_mb": 25, "seg": KNOWLEDGE_DIR / "_ch5_c2_vwappull_segs",
        "description": "MA/VWAP Pullbacks",
    },
    "c2_ch5_pivots": {
        "source": C5 / "Pivots.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "Pivots.txt",
        "size_mb": 22, "seg": KNOWLEDGE_DIR / "_ch5_c2_pivots_segs",
        "description": "Pivots",
    },
    "c2_ch5_pulling": {
        "source": C5 / "Pulling Away Pattern.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "Pulling_Away.txt",
        "size_mb": 20, "seg": KNOWLEDGE_DIR / "_ch5_c2_pulling_segs",
        "description": "Pulling Away Pattern",
    },
    "c2_ch5_roundtrips": {
        "source": C5 / "Round Trips.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "Round_Trips.txt",
        "size_mb": 17, "seg": KNOWLEDGE_DIR / "_ch5_c2_roundtrips_segs",
        "description": "Round Trips",
    },
    "c2_ch5_sysshort": {
        "source": C5 / "System Short Sellers.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "System_Short_Sellers.txt",
        "size_mb": 25, "seg": KNOWLEDGE_DIR / "_ch5_c2_sysshort_segs",
        "description": "System Short Sellers",
    },
    "c2_ch5_reversal": {
        "source": C5 / "Top and Bottom Reversal.mp4",
        "output": TRANSCRIPT_DIR / "Chapter5_Course2" / "Top_Bottom_Reversal.txt",
        "size_mb": 20, "seg": KNOWLEDGE_DIR / "_ch5_c2_reversal_segs",
        "description": "Top and Bottom Reversal",
    },
}

TRANSCRIPTS = {**CH5_COURSE1, **CH5_COURSE2}


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
    if len(sys.argv) == 1:
        # No args: run all CH5_COURSE1 (default)
        target_dict = CH5_COURSE1
    elif sys.argv[1] == "c1":
        target_dict = CH5_COURSE1
    elif sys.argv[1] == "c2":
        target_dict = CH5_COURSE2
    elif sys.argv[1] in TRANSCRIPTS:
        # Single key
        t = TRANSCRIPTS[sys.argv[1]]
        success = transcribe_video(
            t["source"], t["output"],
            file_size_mb=t.get("size_mb"), seg_dir=t.get("seg")
        )
        if success:
            rules = extract_rules(t["output"])
            for category, keywords in rules.items():
                if keywords:
                    print(f"  [{category}]: {keywords}")
        return
    else:
        print(f"Unknown arg: {sys.argv[1]}")
        print(f"Usage: python transcribe_course.py [c1|c2|<key>]")
        return

    print(f"Warrior Trading Transcription Pipeline")
    print(f"Model: {MODEL_SIZE} | Output dir: {TRANSCRIPT_DIR}")
    print(f"Processing {len(target_dict)} files\n")

    results = {}
    for idx, (key, t) in enumerate(target_dict.items(), 1):
        if not t["source"].exists():
            print(f"[{idx}/{len(target_dict)}] SKIP — not found: {t['source'].name}")
            results[key] = False
            continue

        print(f"[{idx}/{len(target_dict)}] {t['description']}")
        success = transcribe_video(
            t["source"], t["output"],
            file_size_mb=t.get("size_mb"), seg_dir=t.get("seg")
        )
        results[key] = success
        if success:
            rules = extract_rules(t["output"])
            for category, keywords in rules.items():
                if keywords:
                    print(f"  [{category}]: {keywords}")

    print(f"\n{'='*60}")
    print("SUMMARY")
    for key, success in results.items():
        status = "✅" if success else "❌"
        t = target_dict[key]
        print(f"  {status} {t['source'].name}")


if __name__ == "__main__":
    main()
