# Process Course 2: Day Trading Strategies & Scaling
# Ingestion pipeline for Warrior Trading Course 2
import whisper
import subprocess
from pathlib import Path
import json
from datetime import datetime

RAW_DIR = Path(r'E:\Me\TradingAgent\knowledge\raw\2. Day Trading Strategies & Scaling')
EXTRACTED_DIR = Path(r'E:\Me\TradingAgent\knowledge\extracted')
AUDIO_DIR = Path(r'E:\Me\TradingAgent\knowledge\audio')
FRAMES_DIR = Path(r'E:\Me\TradingAgent\knowledge\frames')

AUDIO_DIR.mkdir(exist_ok=True)
FRAMES_DIR.mkdir(exist_ok=True)

# Course 2 — 12 Chapters (from user profile)
# Currently available: Ch 1, Ch 2
# Pending download: Ch 3–12

CHAPTERS = [
    # (chapter_num, part_num_or_None, subfolder_name, display_name)
    # === CURRENTLY AVAILABLE ===
    (1, None, 'Chapter 1 Intro to Day Trading', 'Intro to My Day Trading Strategies', 1),
    (2, None, 'Chapter 2 Risk Management', 'Learning to Manage Your Risk', 1),
    # === PENDING DOWNLOAD (Ch 3–12 from Warrior Trading platform) ===
    # (3, None, 'Chapter 3 Momentum Scaling', 'Momentum Scaling Strategies', 1),
    # (4, None, 'Chapter 4 News Catalysts', 'Trading News Catalysts', 1),
    # (5, None, 'Chapter 5 Short Selling', 'Short Selling Strategies', 1),
    # (6, None, 'Chapter 6 Scaling In', 'Scaling In & Out of Positions', 1),
    # (7, None, 'Chapter 7 Morning Panic', 'Trading the Morning Panic', 1),
    # (8, None, 'Chapter 8 Sector Rotation', 'Sector Rotation Strategies', 1),
    # (9, None, 'Chapter 9 Gap Fade', 'Gap Fade Strategy', 1),
    # (10, None, 'Chapter 10 VWAP Trading', 'VWAP Strategy', 1),
    # (11, None, 'Chapter 11 Live Trading', 'Going Live with Real Money', 1),
    # (12, None, 'Chapter 12 Review', 'Course Review & Next Steps', 1),
]

def extract_audio(mp4_path, audio_path):
    """Extract audio from MP4 using ffmpeg."""
    cmd = ['ffmpeg', '-y', '-i', str(mp4_path), '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', str(audio_path)]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0

def transcribe(audio_path):
    """Transcribe audio using Whisper (local, no API cost)."""
    model = whisper.load_model('base')
    result = model.transcribe(str(audio_path), verbose=False)
    return result['text']

def extract_frames(mp4_path, frames_dir):
    """Extract frames from MP4 for visual study."""
    frames_dir.mkdir(exist_ok=True, parents=True)
    cmd = ['ffmpeg', '-i', str(mp4_path), '-vf', 'fps=1', str(frames_dir / 'frame_%04d.png')]
    subprocess.run(cmd, capture_output=True)

def save_transcript(chapter, part, name, text):
    """Save transcript to extracted directory."""
    if part:
        path = EXTRACTED_DIR / f'Chapter{chapter}_Part{part}_{name.replace(" ","_")}_extracted.txt'
    else:
        path = EXTRACTED_DIR / f'Chapter{chapter}_{name.replace(" ","_")}_extracted.txt'
    path.parent.mkdir(exist_ok=True, parents=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'# Chapter {chapter}: {name}\n')
        f.write(f'# Course: Day Trading Strategies & Scaling\n')
        f.write(f'# Extracted: {datetime.now().isoformat()}\n\n')
        f.write(text)
    return path

def process_chapter(ch_num, part, subfolder, name, num_parts):
    """Process a single chapter."""
    print(f'\n📚 Processing Chapter {ch_num}: {name}')

    for p in range(1, num_parts + 1):
        mp4_name = f'Part {p} {name}.mp4' if num_parts > 1 else f'{name}.mp4'
        mp4_path = RAW_DIR / subfolder / mp4_name

        if not mp4_path.exists():
            print(f'  ⚠️  MP4 not found: {mp4_path}')
            continue

        # Audio extraction
        audio_name = f'Chapter{ch_num}_Part{p}_audio.wav' if num_parts > 1 else f'Chapter{ch_num}_audio.wav'
        audio_path = AUDIO_DIR / audio_name
        print(f'  🎧 Extracting audio ({p}/{num_parts})...')
        extract_audio(mp4_path, audio_path)

        # Transcription
        print(f'  🎤 Transcribing...')
        text = transcribe(audio_path)
        print(f'  ✅ {len(text):,} chars transcribed')

        # Save
        transcript_path = save_transcript(ch_num, p if num_parts > 1 else None, name, text)
        print(f'  💾 Saved: {transcript_path.name}')

        # Extract frames for visual study
        frames_dir = FRAMES_DIR / f'Chapter{ch_num}_Chapter{p}_{name.replace(" ","_")}_frames'
        print(f'  🖼️  Extracting frames...')
        extract_frames(mp4_path, frames_dir)

if __name__ == '__main__':
    print('=' * 60)
    print('Course 2: Day Trading Strategies & Scaling — Ingestion Pipeline')
    print(f'Started: {datetime.now().isoformat()}')
    print('=' * 60)

    for args in CHAPTERS:
        try:
            process_chapter(*args)
        except Exception as e:
            print(f'  ❌ Error processing chapter: {e}')

    print('\n' + '=' * 60)
    print('Pipeline complete!')
    print('=' * 60)
