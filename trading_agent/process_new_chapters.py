# Warrior Trading Course Processing Pipeline
# Processes new chapters: Extract audio → Transcribe → Extract frames → Analyze → Store rules

import subprocess
import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime

# Paths
RAW_DIR = Path(r"E:\Me\TradingAgent\knowledge\raw")
EXTRACTED_DIR = Path(r"E:\Me\TradingAgent\knowledge\extracted")
FRAMES_DIR = Path(r"E:\Me\TradingAgent\knowledge\frames")
AUDIO_DIR = Path(r"E:\Me\TradingAgent\knowledge\audio")

# Ensure directories exist
EXTRACTED_DIR.mkdir(exist_ok=True)
FRAMES_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)

def extract_audio(mp4_path, output_wav):
    """Extract audio from MP4 using ffmpeg"""
    print(f"  Extracting audio from {mp4_path.name}...")
    cmd = [
        "ffmpeg", "-y", "-i", str(mp4_path),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(output_wav)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr}")
        return False
    return True

def transcribe_audio(wav_path):
    """Transcribe audio using Whisper"""
    print(f"  Transcribing {wav_path.name}...")
    import whisper
    
    # Load model (use base for speed)
    model = whisper.load_model("base")
    
    # Transcribe
    result = model.transcribe(str(wav_path), verbose=False)
    
    return result["text"]

def extract_frames(mp4_path, output_dir, interval_sec=60):
    """Extract frames from video at regular intervals"""
    print(f"  Extracting frames from {mp4_path.name}...")
    
    # Get video duration
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
           "-of", "default=noprint_wrappers=1:nokey=1", str(mp4_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    duration = float(result.stdout.strip())
    
    # Extract frames every N seconds
    frame_times = list(range(0, int(duration), interval_sec))
    
    frames = []
    for i, t in enumerate(frame_times):
        output_path = output_dir / f"frame_{i:04d}.jpg"
        cmd = [
            "ffmpeg", "-y", "-ss", str(t), "-i", str(mp4_path),
            "-vframes", "1", "-q:v", "2", str(output_path)
        ]
        subprocess.run(cmd, capture_output=True)
        frames.append({
            "timestamp": t,
            "path": str(output_path),
            "duration": duration
        })
    
    return frames

def save_transcript(chapter_name, text, output_path):
    """Save transcript to file"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {chapter_name}\n")
        f.write(f"# Extracted: {datetime.now().isoformat()}\n\n")
        f.write(text)
    print(f"  Saved transcript: {output_path}")

def process_chapter(chapter_dir, chapter_num, chapter_name):
    """Process a single chapter"""
    print(f"\n{'='*60}")
    print(f"Processing Chapter {chapter_num}: {chapter_name}")
    print('='*60)
    
    # Find MP4 file
    mp4_files = list(chapter_dir.glob("*.mp4"))
    if not mp4_files:
        print(f"  No MP4 found in {chapter_dir}")
        return False
    
    mp4_path = mp4_files[0]
    
    # Paths
    audio_path = AUDIO_DIR / f"Chapter{chapter_num}_audio.wav"
    transcript_path = EXTRACTED_DIR / f"Chapter{chapter_num}_extracted.txt"
    frames_dir = FRAMES_DIR / f"Chapter{chapter_num}_frames"
    frames_dir.mkdir(exist_ok=True)
    
    # Step 1: Extract audio
    if not extract_audio(mp4_path, audio_path):
        return False
    
    # Step 2: Transcribe
    transcript = transcribe_audio(audio_path)
    save_transcript(chapter_name, transcript, transcript_path)
    
    # Step 3: Extract frames
    frames = extract_frames(mp4_path, frames_dir, interval_sec=60)
    print(f"  Extracted {len(frames)} frames")
    
    # Step 4: Save frame info
    batch_info = {
        "chapter": chapter_num,
        "chapter_name": chapter_name,
        "processed": datetime.now().isoformat(),
        "frames": frames,
        "transcript_path": str(transcript_path)
    }
    batch_path = FRAMES_DIR / f"batch_{chapter_num:04d}.json"
    with open(batch_path, "w") as f:
        json.dump(batch_info, f, indent=2)
    
    print(f"  ✓ Chapter {chapter_num} processed successfully")
    return True

def main():
    """Process new chapters (12 and 13)"""
    chapters = [
        (12, "Scanning 101"),
        (13, "The Psychology of Trading"),
    ]
    
    for chapter_num, chapter_name in chapters:
        chapter_dir = RAW_DIR / f"Chapter{chapter_num}"
        if chapter_dir.exists():
            process_chapter(chapter_dir, chapter_num, chapter_name)
        else:
            print(f"Chapter {chapter_num} directory not found: {chapter_dir}")
    
    print("\n" + "="*60)
    print("Processing complete!")
    print("="*60)

if __name__ == "__main__":
    main()
