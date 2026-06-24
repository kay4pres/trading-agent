# Process Chapter 15 - FINAL Chapter of Day Trading Basics
import whisper
import subprocess
from pathlib import Path

RAW_DIR = Path(r'E:\Me\TradingAgent\knowledge\raw\1. Day Trading The Basics')
EXTRACTED_DIR = Path(r'E:\Me\TradingAgent\knowledge\extracted')
AUDIO_DIR = Path(r'E:\Me\TradingAgent\knowledge\audio')

# Chapter 15 has 2 parts
chapters = [
    (15, 1, 'Trading Plan & Day Trading Strategy'),
    (15, 2, 'The Warrior Learning Path'),
]

for ch_num, part_num, name in chapters:
    mp4_path = RAW_DIR / f'Chapter{ch_num}' / f'Part {part_num} {name}.mp4'
    audio_path = AUDIO_DIR / f'Chapter{ch_num}_Part{part_num}_audio.wav'
    transcript_path = EXTRACTED_DIR / f'Chapter{ch_num}_Part{part_num}_extracted.txt'
    
    print(f'Processing Chapter {ch_num} Part {part_num}: {name}')
    
    # Extract audio
    print('  Extracting audio...')
    cmd = ['ffmpeg', '-y', '-i', str(mp4_path), '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', str(audio_path)]
    subprocess.run(cmd, capture_output=True)
    
    # Transcribe
    print('  Transcribing...')
    model = whisper.load_model('base')
    result = model.transcribe(str(audio_path), verbose=False)
    
    # Save
    with open(transcript_path, 'w', encoding='utf-8') as f:
        f.write(f'# Chapter {ch_num} Part {part_num}: {name}\n')
        f.write(result['text'])
    
    print(f'  Done! {len(result["text"])} chars')

print('\nChapter 15 COMPLETE!')
