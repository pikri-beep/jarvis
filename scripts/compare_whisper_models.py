"""Compare faster-whisper base vs small for Indonesian accuracy and latency."""
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
    prompt = "Halo JARVIS. Tolong buka Chrome, Google Chrome, WhatsApp, Notepad, Edge, Kalkulator, Pengaturan, Berkas. RAM, SSD, jadwal hari ini."

    texts = [
        "Selamat pagi, apa kabar?",
        "Tolong buka Chrome.",
        "Sekarang buka Google Chrome.",
        "Saya ingin mengetahui perbedaan RAM dan SSD.",
        "Jelaskan jadwal saya hari ini.",
        "Tolong buka WhatsApp.",
        "Buka kalkulator.",
        "Buka pengaturan.",
    ]

    # Pre-generate audio samples so TTS time isn't measured
    samples = []
    for t in texts:
        raw, sr = tts.synthesize(t, language="id")
        audio = resample_audio(raw.astype(np.float32) / 32768.0, sr, 16000)
        samples.append((t, audio))

    for m_name in ["base", "small"]:
        print(f"\n=== Testing faster-whisper: {m_name} ===")
        t_load = time.time()
        model = WhisperModel(m_name, device="cpu", compute_type="int8", cpu_threads=6)
        print(f"Model {m_name} loaded in {time.time() - t_load:.2f}s")
        
        total_lat = 0.0
        for orig, audio in samples:
            t0 = time.time()
            segs, info = model.transcribe(
                audio,
                beam_size=1,
                language="id",
                initial_prompt=prompt,
                condition_on_previous_text=False,
            )
            res = " ".join(s.text.strip() for s in segs)
            dt = time.time() - t0
            total_lat += dt
            print(f'"{orig}" -> "{res}" ({dt:.2f}s)')
        print(f"Avg latency ({m_name}): {total_lat / len(samples):.2f}s")

if __name__ == "__main__":
    main()
