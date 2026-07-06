"""
Evening transcription sprint — 2026-07-06
Covers:
  1. C1 Ch2 Part2 (Long vs Short Selling) — re-transcribe from WAV (77MB, 42 min)
  2. C2 Ch6 all 8 parts — extract audio → whisper from WAV
"""
import subprocess, sys, shutil, os
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
KNOWLEDGE_DIR = Path(r"E:\Me\TradingAgent\knowledge")
RAW_DIR       = KNOWLEDGE_DIR / "raw"
TRANSCRIPT_DIR= KNOWLEDGE_DIR / "transcripts"
RULES_DIR     = KNOWLEDGE_DIR / "rules"
SEG_SIZE_MB   = 18
MODEL          = "tiny"
LANGUAGE       = "en"

C1 = RAW_DIR / "1. Day Trading The Basics"
C2 = RAW_DIR / "2. Day Trading Strategies & Scaling"
C2_CH6_DIR = C2 / "Chapter 6 Level 2, Tape Reading, and Hot KeysButtons"

def get_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=60
    )
    return float(r.stdout.strip()) if r.stdout.strip() else 0.0

def extract_audio(video_path: Path, wav_path: Path, max_size_mb: int = 500):
    """Extract mono 16kHz audio. If WAV already exists, skip."""
    if wav_path.exists():
        print(f"  Audio exists, skipping extract: {wav_path.name}")
        return wav_path
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    # Use -fs to cap output size (ffmpeg will truncate at ~500MB if needed, but we only need the audio)
    ret = subprocess.run([
        "ffmpeg", "-y", "-i", str(video_path),
        "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le",
        "-fs", f"{max_size_mb}M",
        str(wav_path)
    ], capture_output=True, text=True)
    if ret.returncode != 0:
        print(f"  FFmpeg ERROR: {ret.stderr[:500]}")
    return wav_path

def segment_audio(wav_path: Path, seg_dir: Path, max_size_mb: int = SEG_SIZE_MB) -> list[Path]:
    """Split WAV by file size (~18MB chunks)."""
    seg_dir.mkdir(parents=True, exist_ok=True)
    duration = get_duration(wav_path)
    max_sec  = int((max_size_mb / 11) * 60)
    segments = []
    seg_idx  = 0
    for start in range(0, int(duration), max_sec):
        seg_path = seg_dir / f"seg_{seg_idx:02d}.wav"
        r = subprocess.run([
            "ffmpeg", "-y", "-ss", str(start), "-i", str(wav_path),
            "-t", str(max_sec), "-ac", "1", "-ar", "16000",
            "-acodec", "pcm_s16le", "-fs", f"{max_size_mb}M",
            str(seg_path)
        ], capture_output=True, text=True)
        if seg_path.exists() and seg_path.stat().st_size > 50000:
            segments.append(seg_path)
            seg_idx += 1
    print(f"  Segmented into {len(segments)} parts")
    return segments

def run_whisper(segments: list[Path], output_path: Path, model_size: str = MODEL):
    """Run faster-whisper on segments and concatenate."""
    import faster_whisper
    output_path.parent.mkdir(parents=True, exist_ok=True)

    model = faster_whisper.WhisperModel(model_size, device="cpu", compute_type="int8")
    all_lines = []
    for seg in segments:
        print(f"  Whisper: {seg.name}")
        segs_gen, info = model.transcribe(
            str(seg), language=LANGUAGE, beam_size=5,
            vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500)
        )
        for s in segs_gen:
            ts = f"{int(s.start//3600):02d}:{int((s.start%3600)//60):02d}:{int(s.start%60):02d}"
            all_lines.append(f"[{ts}] {s.text.strip()}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Segments: {len(segments)}\n")
        f.write(f"# Transcribed: {datetime.now().isoformat()}\n\n")
        f.write("\n".join(all_lines))

    return output_path

def format_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def extract_rules_from_file(txt_path: Path) -> dict:
    """Keyword-based rule extraction."""
    if not txt_path.exists():
        return {}
    text = Path(txt_path).read_text(encoding="utf-8")
    keywords = {
        "catalyst_types":    ["catalyst","news catalyst","earnings","FDA","FDA approval","contract","partnership","upgrade","downgrade"],
        "gap_patterns":      ["gap up","gap down","gapped up","gapped down","fill the gap","gap fill","at the open","opening range"],
        "volume_patterns":   ["relative volume","volume spike","heavy volume","light volume","volume confirmation","volume dry up"],
        "risk_rules":        ["stop loss","stop out","risk management","position sizing","max loss","risk reward","risk/reward"],
        "first_pullback":    ["first pullback","pull back","pullback","consolidation","resting","setup"],
        "scalping":          ["scalp","scalping","quick trade","intraday","same day"],
        "level2":            ["level 2","time and sales","bid","ask","offer","market maker","limit order","market order","short locate","hard to borrow"],
        "order_types":       ["limit order","market order","stop loss","stop limit","IOC","FOK","day order","GTC"],
        "hot_keys":          ["hot key","hotkeys","hot button","keyboard shortcut","trade key"],
    }
    found = {}
    for cat, terms in keywords.items():
        matches = [t for t in terms if t.lower() in text.lower()]
        if matches:
            found[cat] = matches
    return found

def save_rules(rules: dict, chapter_tag: str):
    """Save extracted rules to knowledge/rules/."""
    RULES_DIR.mkdir(parents=True, exist_ok=True)
    out = RULES_DIR / f"{chapter_tag}_rules.md"
    lines = [f"# {chapter_tag} Rules (extracted {datetime.now().date()})\n"]
    for cat, terms in rules.items():
        lines.append(f"\n## {cat}\n" + "\n".join(f"- {t}" for t in terms))
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Rules saved → {out.name}")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — C1 Ch2 Part2 re-transcribe
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("STEP 1 — C1 Ch2 Part2: Long vs Short Selling (re-transcribe)")
print("="*60)

src = C1 / "Chapter2" / "Picking stocks P2-Long vs short selling_audio.wav"
out = TRANSCRIPT_DIR / "Chapter 2" / "Part2_Long_Short_Selling.txt"
seg_dir = KNOWLEDGE_DIR / "_ch1_c1_p2_segs"

# Backup already done. Now re-transcribe.
if not src.exists():
    print(f"ERROR: {src} not found")
else:
    dur = get_duration(src)
    src_mb = src.stat().st_size / 1_000_000
    print(f"Source: {src.name} | {dur/60:.1f} min | {src_mb:.0f}MB")
    if dur > 60:
        segs = segment_audio(src, seg_dir)
        run_whisper(segs, out)
    else:
        import faster_whisper
        model = faster_whisper.WhisperModel(MODEL, device="cpu", compute_type="int8")
        segs_gen, info = model.transcribe(str(src), language=LANGUAGE, beam_size=5,
                                          vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))
        lines = [f"[{format_ts(s.start)}] {s.text.strip()}" for s in segs_gen]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f"# {src.name}\n# Transcribed: {datetime.now().isoformat()}\n# Duration: {dur/60:.1f} min\n\n" + "\n".join(lines), encoding="utf-8")
    print(f"  Saved: {out}")

    rules = extract_rules_from_file(out)
    for cat, terms in rules.items():
        if terms:
            print(f"  [{cat}]: {terms}")
    save_rules(rules, "c1_ch2_part2_long_short")

print("\n" + "="*60)
print("STEP 2 — C2 Ch6: extract audio for all 8 MP4s")
print("="*60)

# C2 Ch6 parts: (key, mp4_name, wav_name, transcript_path, seg_dir)
C2_CH6_PARTS = [
    ("p1", "Part 1 Level 2 and Time and Sales.mp4",
     "Part1_audio.wav", TRANSCRIPT_DIR/"Chapter 6 Course2"/"Part1_Level2_Time_Sales.txt",
     KNOWLEDGE_DIR/"_ch2_c6_p1_segs"),
    ("p2", "Part 2 ADFN Prints .mp4",
     "Part2_audio.wav", TRANSCRIPT_DIR/"Chapter 6 Course2"/"Part2_ADFN_Prints.txt",
     KNOWLEDGE_DIR/"_ch2_c6_p2_segs"),
    ("p3", "Part 3 Circuit Breaker Halts.mp4",
     "Part3_audio.wav", TRANSCRIPT_DIR/"Chapter 6 Course2"/"Part3_Circuit_Breaker_Halts.txt",
     KNOWLEDGE_DIR/"_ch2_c6_p3_segs"),
    ("p4", "Part 4 Market Makers.mp4",
     "Part4_audio.wav", TRANSCRIPT_DIR/"Chapter 6 Course2"/"Part4_Market_Makers.txt",
     KNOWLEDGE_DIR/"_ch2_c6_p4_segs"),
    ("p5", "Part 5 PFOF vs Direct Access.mp4",
     "Part5_audio.wav", TRANSCRIPT_DIR/"Chapter 6 Course2"/"Part5_PFOF_Direct_Access.txt",
     KNOWLEDGE_DIR/"_ch2_c6_p5_segs"),
    ("p6", "Part 6 Order Routing, Order Types, and Adding Liquidity.mp4",
     "Part6_audio.wav", TRANSCRIPT_DIR/"Chapter 6 Course2"/"Part6_Order_Routing.txt",
     KNOWLEDGE_DIR/"_ch2_c6_p6_segs"),
    ("p7", "Part 7 Advanced Hot Keys and Hot Buttons.mp4",
     "Part7_audio.wav", TRANSCRIPT_DIR/"Chapter 6 Course2"/"Part7_Advanced_Hot_Keys.txt",
     KNOWLEDGE_DIR/"_ch2_c6_p7_segs"),
    ("p8", "Part 8 Multi-Account Syncing.mp4",
     "Part8_audio.wav", TRANSCRIPT_DIR/"Chapter 6 Course2"/"Part8_Multi_Account_Syncing.txt",
     KNOWLEDGE_DIR/"_ch2_c6_p8_segs"),
]

TEMP_AUDIO_DIR = KNOWLEDGE_DIR / "_c2_ch6_audio_temp"
TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

results = []
for idx, (key, mp4_name, wav_name, transcript_path, seg_dir) in enumerate(C2_CH6_PARTS, 1):
    mp4_path = C2_CH6_DIR / mp4_name
    wav_path = TEMP_AUDIO_DIR / wav_name

    print(f"\n[{idx}/8] C2 Ch6 {key}: {mp4_name}")
    if not mp4_path.exists():
        print(f"  SKIP — MP4 not found: {mp4_path.name}")
        results.append((key, False))
        continue

    mp4_size_gb = mp4_path.stat().st_size / 1e9
    print(f"  MP4 size: {mp4_size_gb:.1f} GB")

    # Step A: extract audio
    print(f"  Extracting audio → {wav_path.name}...")
    wav_path = extract_audio(mp4_path, wav_path)
    wav_size_gb = wav_path.stat().st_size / 1e9 if wav_path.exists() else 0
    print(f"  WAV size: {wav_size_gb:.1f} GB")

    if not wav_path.exists() or wav_path.stat().st_size < 100000:
        print(f"  ERROR: audio extraction failed for {mp4_name}")
        results.append((key, False))
        continue

    # Step B: segment
    dur = get_duration(wav_path)
    print(f"  Duration: {dur/60:.1f} min | WAV size: {wav_size_gb:.1f} GB")
    print(f"  Segmenting (18MB chunks)...")
    segs = segment_audio(wav_path, seg_dir)

    # Step C: whisper
    print(f"  Transcribing {len(segs)} segments...")
    run_whisper(segs, transcript_path)
    print(f"  Saved: {transcript_path.name}")

    # Step D: rules
    rules = extract_rules_from_file(transcript_path)
    for cat, terms in rules.items():
        if terms:
            print(f"  [{cat}]: {terms}")
    save_rules(rules, f"c2_ch6_{key}")

    # Step E: cleanup WAV (keep only segment dirs)
    try:
        wav_path.unlink()
        print(f"  Cleaned up temp WAV")
    except Exception as e:
        print(f"  Could not delete temp WAV: {e}")

    results.append((key, True))

# Cleanup temp dir
try:
    TEMP_AUDIO_DIR.rmdir()
except:
    pass

print("\n" + "="*60)
print("SPRINT COMPLETE — SUMMARY")
print("="*60)
for key, ok in results:
    status = "✅" if ok else "❌"
    print(f"  {status} C2 Ch6 {key}")
print(f"\nAll transcripts → {TRANSCRIPT_DIR}")
print(f"All rules       → {RULES_DIR}")
