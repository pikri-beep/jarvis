import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
from faster_whisper import WhisperModel
from app.voice.text_to_speech import TextToSpeech
from app.voice.audio_recorder import resample_audio

tts = TextToSpeech()
model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=6)

items = [
    ("Selamat pagi, apa kabar?", "id"),
    ("Tolong buka Chrome.", "id"),
    ("Sekarang buka Google Chrome.", "id"),
    ("Saya ingin mengetahui perbedaan RAM dan SSD.", "id"),
    ("Jelaskan jadwal saya hari ini.", "id"),
    ("Hello, Jarvis.", "en"),
    ("What time is it?", "en"),
    ("Explain the difference between RAM and SSD.", "en")
]

for text, true_lang in items:
    raw, sr = tts.synthesize(text, language=true_lang)
    audio = resample_audio(raw.astype(np.float32) / 32768.0, sr, 16000)
    
    _, info = model.transcribe(audio, beam_size=1)
    probs = dict(info.all_language_probs) if hasattr(info, "all_language_probs") and info.all_language_probs else {}
    id_score = probs.get("id", 0.0) + probs.get("ms", 0.0)
    en_score = probs.get("en", 0.0)
    selected = "id" if id_score >= en_score else "en"
    
    print(f"Target: '{text}' ({true_lang}) -> id_score={id_score:.4f}, en_score={en_score:.4f} => Selected: {selected} {'[CORRECT]' if selected == true_lang else '[WRONG]'}")
