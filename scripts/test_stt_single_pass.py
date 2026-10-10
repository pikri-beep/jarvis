"""Tests single-pass faster-whisper with initial_prompt for Indonesian speech."""

import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
from faster_whisper import WhisperModel
from app.voice.text_to_speech import TextToSpeech
from app.voice.audio_recorder import resample_audio

def main():
    tts = TextToSpeech()
    tts.load_model("id")
    model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=6)
    prompt = "Halo JARVIS. Tolong buka Chrome, WhatsApp, Notepad. RAM, SSD, jadwal hari ini."

    utterances = [
        "Selamat pagi, apa kabar?",
        "Tolong buka Chrome.",
        "Sekarang buka Google Chrome.",
        "Saya ingin mengetahui perbedaan RAM dan SSD.",
        "Jelaskan jadwal saya hari ini.",
        "Tolong buka WhatsApp.",
    ]

    print("=== Testing Single-Pass STT (language='id') ===")
    for text in utterances:
        raw, sr = tts.synthesize(text, language="id")
        audio = resample_audio(raw.astype(np.float32) / 32768.0, sr, 16000)

        t0 = time.time()
        segs, info = model.transcribe(
            audio,
            beam_size=1,
            language="id",
            initial_prompt=prompt,
            condition_on_previous_text=False,
        )
        result_text = " ".join(s.text.strip() for s in segs)
        dt = time.time() - t0
        print(f"Target: \"{text}\"")
        print(f"  -> Transcribed: \"{result_text}\" | Lang: {info.language} ({info.language_probability:.2f}) | Latency: {dt:.2f}s")
        print("-" * 50)

if __name__ == "__main__":
    main()
