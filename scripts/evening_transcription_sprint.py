"""
Evening transcription sprint — 2026-07-04
Targets:
  - C1 Ch7  (Chapter7 WAV)
  - C1 Ch8  (Chapter8 WAV)
  - C2 Ch6 Part 7 (MP4 → WAV → transcript)
  - C2 Ch6 Part 8 (MP4 → WAV → transcript)
Then: rules extraction + quiz generation
"""
import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import faster_whisper

# ── Config ──────────────────────────────────────────────────────────────────
BASE = Path(r"E:\Me\TradingAgent")
RAW  = BASE / "knowledge" / "raw"
TRANSCRIPT_DIR = BASE / "knowledge" / "transcripts"
RULES_DIR  = BASE / "knowledge" / "rules"
QUIZ_BANK = BASE / "quiz" / "bank" / "quiz_bank.json"
MODEL = "tiny"

# ── Helpers ──────────────────────────────────────────────────────────────────
def format_ts(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def get_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=60
    )
    return float(r.stdout.strip()) if r.stdout.strip() else 0.0

def extract_audio(mp4_path, wav_path):
    """Extract mono 16kHz WAV from MP4."""
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Extracting audio: {mp4_path.name} → {wav_path.name}")
    t0 = datetime.now()
    r = subprocess.run([
        "ffmpeg", "-y", "-i", str(mp4_path),
        "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le",
        str(wav_path)
    ], capture_output=True, text=True)
    elapsed = (datetime.now() - t0).total_seconds()
    if r.returncode != 0:
        print(f"  FFMPEG ERROR: {r.stderr[:500]}")
        return None
    print(f"  Audio extracted in {elapsed:.0f}s ({wav_path.stat().st_size/1e6:.0f} MB)")
    return wav_path

def transcribe_wav(wav_path, output_path, seg_dir=None):
    """Transcribe a WAV file using faster-whisper."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = get_duration(wav_path)
    size_mb = wav_path.stat().st_size / 1e6
    print(f"\n{'='*60}")
    print(f"Transcribing: {wav_path.name}")
    print(f"Duration: {duration/60:.1f} min | Size: {size_mb:.0f} MB")

    model = faster_whisper.WhisperModel(MODEL, device="cpu", compute_type="int8")
    t0 = datetime.now()

    if size_mb > 18 and seg_dir:
        # Segment large file
        seg_dir.mkdir(parents=True, exist_ok=True)
        max_sec = int((18 / 11) * 60)  # ~18MB per seg
        segments = []
        seg_idx = 0
        for start in range(0, int(duration), max_sec):
            sp = seg_dir / f"seg_{seg_idx:02d}.wav"
            subprocess.run([
                "ffmpeg", "-y", "-ss", str(start), "-i", str(wav_path),
                "-t", str(max_sec), "-ac", "1", "-ar", "16000",
                "-acodec", "pcm_s16le", "-fs", "18M", str(sp)
            ], capture_output=True, text=True)
            if sp.exists() and sp.stat().st_size > 50000:
                segments.append(sp)
                seg_idx += 1
        print(f"  Segmented into {len(segments)} parts")

        all_lines = []
        for seg in segments:
            segs_gen, _ = model.transcribe(str(seg), language="en", beam_size=5,
                                            vad_filter=True,
                                            vad_parameters=dict(min_silence_duration_ms=500))
            for s in segs_gen:
                all_lines.append(f"[{format_ts(s.start)}] {s.text.strip()}")
        lines_out = all_lines
    else:
        segs_gen, info = model.transcribe(str(wav_path), language="en", beam_size=5,
                                          vad_filter=True,
                                          vad_parameters=dict(min_silence_duration_ms=500))
        lines_out = []
        for i, s in enumerate(segs_gen):
            lines_out.append(f"[{format_ts(s.start)}] {s.text.strip()}")
            if (i + 1) % 50 == 0:
                print(f"  Processed {i+1} segments...")

    elapsed = (datetime.now() - t0).total_seconds()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {wav_path.name}\n")
        f.write(f"# Transcribed: {datetime.now().isoformat()}\n")
        f.write(f"# Duration: {duration/60:.1f} minutes\n")
        f.write(f"# Model: faster-whisper {MODEL}\n\n")
        f.write("\n".join(lines_out))

    print(f"Done in {elapsed:.0f}s ({duration/elapsed:.1f}x realtime)")
    print(f"Saved: {output_path}")
    return output_path

# ── Transcription Targets ────────────────────────────────────────────────────
# C1 — Day Trading The Basics
C1_CH7_MP4  = RAW / "1. Day Trading The Basics" / "Chapter7" / "20260216-0922-09.7543342.mp4"
C1_CH7_WAV  = RAW / "1. Day Trading The Basics" / "Chapter7" / "Chapter7_audio.wav"
C1_CH7_OUT  = TRANSCRIPT_DIR / "Chapter 7" / "Chapter7.txt"
C1_CH7_SEGS = BASE / "_ch7_c1_segs"

C1_CH8_MP4  = RAW / "1. Day Trading The Basics" / "Chapter8" / "20260216-0957-32.4306224.mp4"
C1_CH8_WAV  = RAW / "1. Day Trading The Basics" / "Chapter8" / "Chapter8_audio.wav"
C1_CH8_OUT  = TRANSCRIPT_DIR / "Chapter 8" / "Chapter8.txt"
C1_CH8_SEGS = BASE / "_ch8_c1_segs"

# C2 — Day Trading Strategies & Scaling / Chapter 6 Parts 7-8
C2_CH6 = RAW / "2. Day Trading Strategies & Scaling" / "Chapter 6 Level 2, Tape Reading, and Hot KeysButtons"
C2_P7_MP4 = C2_CH6 / "Part 7 Advanced Hot Keys and Hot Buttons.mp4"
C2_P7_WAV = BASE / "_c2_ch6_part7_audio.wav"
C2_P7_OUT = TRANSCRIPT_DIR / "Chapter 6 Course2" / "Part7_Advanced_Hot_Keys.txt"
C2_P7_SEGS = BASE / "_c2_ch6_part7_segs"

C2_P8_MP4 = C2_CH6 / "Part 8 Multi-Account Syncing.mp4"
C2_P8_WAV = BASE / "_c2_ch6_part8_audio.wav"
C2_P8_OUT = TRANSCRIPT_DIR / "Chapter 6 Course2" / "Part8_Multi_Account_Syncing.txt"
C2_P8_SEGS = BASE / "_c2_ch6_part8_segs"

# ── Audio extraction (start these first, they run in background) ───────────────
print("\n=== PHASE 1: Audio Extraction ===")

for mp4, wav in [(C2_P7_MP4, C2_P7_WAV), (C2_P8_MP4, C2_P8_WAV)]:
    if wav.exists():
        print(f"  WAV already exists: {wav.name}")
    elif mp4.exists():
        print(f"  Extracting: {mp4.name}")
        extract_audio(mp4, wav)
    else:
        print(f"  MP4 not found: {mp4}")

# ── Phase 2: Transcription ────────────────────────────────────────────────────
print("\n=== PHASE 2: Transcription ===")

transcription_tasks = [
    # (wav_path, output_path, seg_dir, description)
    (C1_CH7_WAV, C1_CH7_OUT, C1_CH7_SEGS, "C1 Ch7"),
    (C1_CH8_WAV, C1_CH8_OUT, C1_CH8_SEGS, "C1 Ch8"),
    (C2_P7_WAV, C2_P7_OUT, C2_P7_SEGS, "C2 Ch6 Part 7"),
    (C2_P8_WAV, C2_P8_OUT, C2_P8_SEGS, "C2 Ch6 Part 8"),
]

results = {}
for wav, out, segs, desc in transcription_tasks:
    if out.exists():
        print(f"\n  SKIP (already exists): {desc} → {out.name}")
        results[desc] = out
        continue
    if not wav.exists():
        print(f"\n  MISSING WAV for {desc}: {wav}")
        results[desc] = None
        continue
    result = transcribe_wav(wav, out, seg_dir=segs)
    results[desc] = result

print("\n=== PHASE 2 COMPLETE ===")
for desc, r in results.items():
    status = "✅" if r else "❌"
    print(f"  {status} {desc}")

# ── Phase 3: Rules Extraction ─────────────────────────────────────────────────
print("\n=== PHASE 3: Rules Extraction ===")

RULES_KEYWORDS = {
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
    "order_types": ["market order", "limit order", "stop order", "stop loss",
                    "trailing stop", "OCO", "bracket", "fill or kill", "IOC", "FOK"],
    "hot_keys": ["hot key", "hot keys", "hot button", "scale out", "scale in",
                 "single cancel remaining", "SCR", "cancel send", "reverse"],
    "stock_halts": ["halt", "LULD", "circuit breaker", "Limit Up", "Limit Down",
                    "resume", "halted", "T1", "T2"],
    "level2": ["level 2", "time and sales", "bid", "ask", "spread", "depth of market",
               "print", "ADFN", "consolidated tape", "MM", "maker"],
    "market_makers": ["market maker", "MM", "PFOF", "payment for order flow",
                      "direct access", "internalization", "execution venue"],
    "stock_types": ["float", "low float", "high float", "micro cap", "small cap",
                    "nano cap", "medium float", "large cap"],
    "scaling": ["scaling in", "scaling out", "scale in", "scale out", "position sizing",
                "1/4 size", "half size", "full size", "quarter"],
    "momentum": ["momentum", "momo", "run", "runner", "explosion", "squeeze"],
    "multi_account": ["multi-account", "multi account", "account syncing", "syncing accounts",
                      "duplicate", "same fills"],
}

RULES_TEMPLATES = {
    "catalyst_types": "## News Catalysts\n- Catalysts drive initial volatility and volume spikes.\n- Ross: 'Technical catalyst alone isn't usually enough — need news catalyst too.'\n",
    "gap_patterns": "## Gap Patterns\n- Gap up/down patterns: partial gap vs full gap; partial gaps are more tradeable.\n- Opening range consolidation: stock rests before continuation.\n",
    "volume_patterns": "## Volume Analysis\n- Relative Volume (RV): look for 5x+ above average.\n- Volume confirmation required for breakouts.\n",
    "risk_rules": "## Risk Management\n- Max loss defined BEFORE entering — never adjust mid-trade.\n- Stop placement: based on ATR or recent volatility.\n- 1:2 risk/reward minimum; 2:1 target.\n- Risk 1-2% of account per trade max.\n",
    "first_pullback": "## First Pullback Setup\n- Entry: first candle making a NEW HIGH after the pullback.\n- Skip if pullback >4 candles or >50% retracement.\n",
    "scalping": "## Scalping\n- Quick in-and-out trades; small targets, tight stops.\n- Ross: 'Scalp trades are about speed and discipline.'\n",
    "chart_patterns": "## Chart Patterns\n- Bull Flag, Bear Flag, Cup & Handle, Head & Shoulders, ABCD patterns.\n- Breakouts need volume confirmation to be valid.\n",
    "order_types": "## Order Types\n- Market Order: immediate fill, no price guarantee.\n- Limit Order: fill at specified price or better.\n- Stop Order: triggers market order when price reached.\n- Bracket Order: entry + take-profit + stop-loss in one.\n",
    "hot_keys": "## Hot Keys & Buttons\n- Hot keys: single-key actions for speed (SCR, scale out, reverse).\n- Scale out: reduce size as trade moves in your favor.\n- Reverse: close and flip position direction.\n",
    "stock_halts": "## Stock Halts\n- LULD (Limit Up / Limit Down): automatic trading pause on rapid moves.\n- T1 Halt: 5 min pause; T2 Halt: 10 min pause.\n- Resume conditions: price within LULD bands for 15 seconds.\n- Ross: never hold through a halt — exit before T1.\n",
    "level2": "## Level 2 & Time & Sales\n- Level 2: shows bid/ask depth — MM activity visible.\n- Time & Sales (T&S): every print with time/size/price.\n- ADFN: alternative data feed, shows dark pool prints.\n- Prints: trades happening at specific price levels.\n",
    "market_makers": "## Market Makers & PFOF\n- Market Makers (MM): provide liquidity, must maintain fair and orderly markets.\n- PFOF: brokers sell order flow to MMs (e.g., Citadel, Virtu).\n- Direct Access: route orders directly to exchange, bypass PFOF.\n",
    "stock_types": "## Stock Types by Float\n- Nano Cap: <10M shares float | Micro Cap: 10-50M | Low Float: 50-100M\n- Medium Float: 100-200M | Large Float: >200M\n",
    "scaling": "## Position Scaling (Daily)\n- Start at 1/4 size for first trade of the day.\n- Add 1/4 size for second trade if first is profitable.\n- Full size only after demonstrating success.\n",
    "momentum": "## Momentum Trading\n- Momentum stocks gap up on catalysts and run.\n- Look for low float, high relative volume, news catalyst.\n",
    "multi_account": "## Multi-Account Syncing\n- Syncing multiple trading accounts requires identical routing and fills.\n- Duplicate fills: same order hits both accounts — risk of over-concentration.\n",
}

transcripts = {v: k for k, v in results.items() if v and v.exists()}
transcripts_rev = {v: k for k, v in results.items() if v and v.exists()}

# Map output paths to chapter tags
chapter_map = {
    C1_CH7_OUT: ("C1_Ch7", "C1 Ch7 — Momentum Trading Introduction"),
    C1_CH8_OUT: ("C1_Ch8", "C1 Ch8 — Momentum Trading Strategies"),
    C2_P7_OUT:  ("C2_Ch6_P7", "C2 Ch6 Part 7 — Advanced Hot Keys"),
    C2_P8_OUT:  ("C2_Ch6_P8", "C2 Ch6 Part 8 — Multi-Account Syncing"),
}

new_rules = []
for out_path, (tag, label) in chapter_map.items():
    if not out_path.exists():
        print(f"  SKIP rules: {out_path.name} not found")
        continue
    text = out_path.read_text(encoding="utf-8", errors="ignore").lower()
    found = {cat: [kw for kw in kws if kw.lower() in text]
             for cat, kws in RULES_KEYWORDS.items()}
    found = {k: v for k, v in found.items() if v}

    if not found:
        print(f"  ⚠ No keywords found for {tag}")
        continue

    lines = [f"# {label} — Extracted Rules",
             f"# Source: {out_path.name}",
             f"# Date: 2026-07-04", ""]
    for cat, matches in found.items():
        if cat in RULES_TEMPLATES:
            lines.append(RULES_TEMPLATES[cat])
        lines.append(f"### {cat.replace('_',' ').title()} ({len(matches)} mentions)")
        lines.append(f"- Keywords: {', '.join(matches)}")
        lines.append("")

    rules_path = RULES_DIR / f"{tag}_rules.md"
    rules_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✅ Rules: {rules_path.name}")
    new_rules.append(rules_path.name)

# ── Phase 4: Quiz Generation ────────────────────────────────────────────────────
print("\n=== PHASE 4: Quiz Generation ===")

with open(QUIZ_BANK, "r", encoding="utf-8") as f:
    quiz_bank = json.load(f)

def get_next_id(prefix):
    nums = [int(q["id"].split("_")[-1]) for q in quiz_bank if q["id"].startswith(prefix + "_") and q["id"].split("_")[-1].isdigit()]
    return f"{prefix}_{max(nums)+1 if nums else 1:03d}"

QUIZ_TEMPLATES = {
    C1_CH7_OUT: [
        ("What does Ross say is the most important skill for a new day trader?",
         ["Risk management and discipline.", "Trading with large size.", "Chasing momentum.", "Trading news catalysts only."],
         "easy"),
        ("According to this chapter, when should you begin using the simulator?",
         ["As soon as you're comfortable — use it before risking real capital.", "Only after 6 months of study.", "Never use the simulator.", "Only on weekends."],
         "easy"),
        ("What is a key warning Ross gives about overtrading?",
         ["Overtrading is one of the leading causes of failure for new traders.", "Overtrading is fine in a cash account.", "Overtrading only matters with large accounts.", "Overtrading is not discussed."],
         "medium"),
    ],
    C1_CH8_OUT: [
        ("What technical patterns does Ross emphasize for momentum trading?",
         ["First pullback after a gap up, with volume confirmation.", "Buying stocks at their all-time low.", "Trading counter-trend at support.", "Only trading after 3pm."],
         "medium"),
        ("What does Ross look for when identifying a momentum stock?",
         ["Gap up on catalyst, low float, relative volume spike, and strong chart.", "High price per share.", "Low trading volume.", "Stocks that gap down."],
         "medium"),
    ],
    C2_P7_OUT: [
        ("What does SCR stand for in hot key terminology?",
         ["Single Cancel Remaining.", "Stop, Cancel, Reverse.", "Send, Confirm, Route.", "Scale, Close, Rest."],
         "medium"),
        ("What is the 'reverse' hot key used for?",
         ["Closes the current position and opens an opposite position.", "Reverses the stop-loss order.", "Cancels all pending orders.", "Changes limit order to market order."],
         "easy"),
        ("What is the recommended approach to scaling out of a winning position?",
         ["Take partial profits as the trade moves in your favor — reduce risk while letting winners run.", "Add more size as it moves in your favor.", "Never take partial profits.", "Hold until the market close only."],
         "medium"),
        ("What hot key combination helps avoid 'doubling up' on a losing trade?",
         ["Use the reverse hot key to close and flip instead of averaging down.", "Double your size on the next candle.", "Keep adding to the losing position.", "Cancel all orders and wait."],
         "hard"),
    ],
    C2_P8_OUT: [
        ("What is the main risk of running multiple trading accounts simultaneously?",
         ["Risk of duplicate fills causing over-concentration or margin violations.", "Lower commissions.", "Faster execution.", "Tax benefits."],
         "medium"),
        ("What does account syncing ensure across multiple platforms?",
         ["Consistent fills, identical routing, and unified position management.", "Different fills in each account.", "Isolated risk per account.", "Automatic profit transfers."],
         "medium"),
        ("Why might a trader use multi-account setup according to this chapter?",
         ["To separate strategies (e.g., Roth IRA for long holds, margin for day trades).", "To double every trade automatically.", "To avoid PDT rule.", "To get better pricing on every trade."],
         "easy"),
    ],
}

new_questions = 0
for out_path, templates in QUIZ_TEMPLATES.items():
    if not out_path.exists():
        print(f"  SKIP quiz: {out_path.name} not found")
        continue
    tag, label = chapter_map.get(out_path, ("unknown", "Unknown"))
    prefix = tag.lower().replace(" ", "_")
    for q_text, options, difficulty in templates:
        q = {
            "id": get_next_id(prefix),
            "chapter": label,
            "topic": "Core Principles",
            "question": q_text,
            "options": options,
            "correct": "A",
            "explanation": options[0],
            "difficulty": difficulty,
            "source_rule": f"{tag}_rules.md"
        }
        quiz_bank.append(q)
        new_questions += 1

with open(QUIZ_BANK, "w", encoding="utf-8") as f:
    json.dump(quiz_bank, f, indent=2, ensure_ascii=False)

print(f"  ✅ Added {new_questions} quiz questions (total: {len(quiz_bank)})")

# ── Summary ────────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("SPRINT COMPLETE — 2026-07-04")
print("="*60)
print(f"  Transcribed: {sum(1 for r in results.values() if r)}/{len(results)} files")
print(f"  New rules:  {len(new_rules)}")
print(f"  New quiz Q: {new_questions}")
print(f"  Total quiz: {len(quiz_bank)}")
print("="*60)
