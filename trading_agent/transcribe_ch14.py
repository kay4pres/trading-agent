# Background transcription for Chapter 14
# Run this separately: python transcribe_ch14.py

import whisper
from pathlib import Path

EXTRACTED_DIR = Path(r'E:\Me\TradingAgent\knowledge\extracted')
AUDIO_DIR = Path(r'E:\Me\TradingAgent\knowledge\audio')

print("Loading Whisper model...")
model = whisper.load_model('base')

print("Transcribing Chapter 14...")
result = model.transcribe(str(AUDIO_DIR / 'Chapter14_audio.wav'), verbose=False)

print(f"Saving transcript ({len(result['text'])} chars)...")
with open(EXTRACTED_DIR / 'Chapter14_extracted.txt', 'w', encoding='utf-8') as f:
    f.write("# Preparing to Start Trading\n")
    f.write("# Extracted: 2026-06-24\n\n")
    f.write(result['text'])

print("Done!")
