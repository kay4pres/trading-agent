# Continue Chapter 15 Part 1 transcription
import whisper
from pathlib import Path

AUDIO_DIR = Path(r'E:\Me\TradingAgent\knowledge\audio')
EXTRACTED_DIR = Path(r'E:\Me\TradingAgent\knowledge\extracted')

audio_path = AUDIO_DIR / 'Chapter15_Part1_audio.wav'
transcript_path = EXTRACTED_DIR / 'Chapter15_Part1_extracted.txt'

print('Loading model...')
model = whisper.load_model('base')

print('Transcribing...')
result = model.transcribe(str(audio_path), verbose=True, fp16=False)

with open(transcript_path, 'w', encoding='utf-8') as f:
    f.write(f'# Chapter 15 Part 1: Trading Plan & Day Trading Strategy\n\n')
    f.write(result['text'])

print(f'\nDone! {len(result["text"])} chars saved to {transcript_path}')
