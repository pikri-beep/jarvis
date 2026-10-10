import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

import time
import numpy as np
from faster_whisper import WhisperModel
from app.voice.text_to_speech import TextToSpeech
from app.voice.audio_recorder import resample_audio

def main():
    tts = TextToSpeech()
    tts.load_model("id")
    tts.load_model("en")

    utterances = [
        ("Selamat pagi, apa kabar?", "id"),
        ("Tolong buka Chrome.", "id"),
        ("Sekarang buka Google Chrome.", "id"),
        ("Saya ingin mengetahui perbedaan RAM dan SSD.", "id"),
        ("Jelaskan jadwal saya hari ini.", "id"),
        ("Hello, Jarvis.", "en"),
        ("What time is it?", "en")
    ]

    for model_name in ["base", "small"]:
        print(f"\n{'='*20} Testing Whisper Model: {model_name} {'='*20}")
        model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=6)
        
        for text, lang in utterances:
            audio_int16, sr = tts.synthesize(text, language=lang)
            audio_16k = resample_audio(audio_int16.astype(np.float32) / 32768.0, sr, 16000)
            
            # 1. No prompt (Auto detect)
            t0 = time.time()
            segs, info = model.transcribe(audio_16k, beam_size=1, condition_on_previous_text=False)
            txt = " ".join(s.text.strip() for s in segs)
            dt = time.time() - t0
            
            # 2. With bilingual initial prompt biasing
            prompt = "Halo JARVIS. Tolong buka Chrome, Google Chrome, Notepad. RAM, SSD, jadwal."
            t0_p = time.time()
            segs_p, info_p = model.transcribe(audio_16k, beam_size=1, condition_on_previous_text=False, initial_prompt=prompt)
            txt_p = " ".join(s.text.strip() for s in segs_p)
            dt_p = time.time() - t0_p
            
            print(f"Target: \"{text}\" ({lang.upper()})")
            print(f"  [No Prompt]   -> \"{txt}\" | Lang: {info.language} ({info.language_probability:.2f}) | {dt:.2f}s")
            print(f"  [With Prompt] -> \"{txt_p}\" | Lang: {info_p.language} ({info_p.language_probability:.2f}) | {dt_p:.2f}s")

if __name__ == "__main__":
    main()
