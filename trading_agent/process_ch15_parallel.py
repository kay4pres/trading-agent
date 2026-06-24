# Process Chapter 15 BOTH PARTS in parallel
import whisper
import subprocess
import concurrent.futures
from pathlib import Path

RAW_DIR = Path(r'E:\Me\TradingAgent\knowledge\raw\1. Day Trading The Basics')
EXTRACTED_DIR = Path(r'E:\Me\TradingAgent\knowledge\extracted')
AUDIO_DIR = Path(r'E:\Me\TradingAgent\knowledge\audio')

chapters = [
    (15, 1, 'Trading Plan & Day Trading Strategy'),
    (15, 2, 'The Warrior Learning Path'),
]

def process_one(ch_num, part_num, name):
    mp4_path = RAW_DIR / f'Chapter{ch_num}' / f'Part {part_num} {name}.mp4'
    audio_path = AUDIO_DIR / f'Chapter{ch_num}_Part{part_num}_audio.wav'
    transcript_path = EXTRACTED_DIR / f'Chapter{ch_num}_Part{part_num}_extracted.txt'
    
    print(f'[Chapter {ch_num} Part {part_num}] Starting: {name}')
    
    # Extract audio
    subprocess.run(['ffmpeg', '-y', '-i', str(mp4_path), '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', str(audio_path)], capture_output=True)
    print(f'[Chapter {ch_num} Part {part_num}] Audio extracted')
    
    # Transcribe
    model = whisper.load_model('base')
    result = model.transcribe(str(audio_path), verbose=False, fp16=False)
    
    # Save
    with open(transcript_path, 'w', encoding='utf-8') as f:
        f.write(f'# Chapter {ch_num} Part {part_num}: {name}\n\n')
        f.write(result['text'])
    
    chars = len(result['text'])
    print(f'[Chapter {ch_num} Part {part_num}] Done! {chars} chars')
    return ch_num, part_num, chars

# Run both in parallel
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    futures = [executor.submit(process_one, c, p, n) for c, p, n in chapters]
    results = [f.result() for f in concurrent.futures.as_completed(futures)]

print('\n=== Chapter 15 COMPLETE ===')
for ch, part, chars in sorted(results):
    print(f'  Part {part}: {chars} chars')
