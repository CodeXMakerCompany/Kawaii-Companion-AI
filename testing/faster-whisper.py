from faster_whisper import WhisperModel

model = WhisperModel("small", compute_type="float32")  # Explicitly specify float32 or int8 to suppress CTranslate2 warnings
segments, info = model.transcribe("testing/test.mp3")

for segment in segments:
    print(segment.text)