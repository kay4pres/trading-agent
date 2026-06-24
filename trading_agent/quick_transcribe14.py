import whisper

print('Loading model...')
model = whisper.load_model('base')

print('Transcribing Chapter 14...')
result = model.transcribe(r'E:\Me\TradingAgent\knowledge\audio\Chapter14_audio.wav', verbose=False)

print('Saving...')
with open(r'E:\Me\TradingAgent\knowledge\extracted\Chapter14_extracted.txt', 'w', encoding='utf-8') as f:
    f.write('# Preparing to Start Trading\n')
    f.write(result['text'])

print('Done! ' + str(len(result['text'])) + ' chars')
