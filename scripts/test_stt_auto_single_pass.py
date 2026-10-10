import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from faster_whisper import WhisperModel
from app.voice.text_to_speech import TextToSpeech
from app.voice.audio_recorder import resample_audio
import numpy as np

tts = TextToSpeech()
tts.load_model("id")
tts.load_model("en")
model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=6)
prompt = "Halo JARVIS. Tolong buka Chrome, WhatsApp, Notepad. Open Chrome, what is the weather."

tests = [
    ("Tolong buka Chrome.", "id"),
    ("Open Chrome, please.", "en"),
    ("Buka WhatsApp.", "id"),
    ("What time is it?", "en"),
]

print("=== Testing Single-Pass Whisper (language=None / auto) ===")
for t, lang in tests:
    raw, sr = tts.synthesize(t, language=lang)
    audio = resample_audio(raw.astype(np.float32) / 32768.0, sr, 16000)
    segs, info = model.transcribe(
        audio,
        beam_size=1,
        language=None,
        initial_prompt=prompt,
        condition_on_previous_text=False,
    )
    res = " ".join(s.text.strip() for s in segs)
    print(f'"{t}" ({lang}) -> "{res}" (detected: {info.language}, prob: {info.language_probability:.2f})')
