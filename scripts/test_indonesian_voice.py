"""Validation script for Indonesian voice quality, pronunciation, and latency."""

import os
import sys
import time
import wave
from pathlib import Path
import numpy as np

# Ensure project root is in sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.core.config import get_settings
from app.voice.text_to_speech import TextToSpeech, clean_text_for_speech


def validate_indonesian_voice():
    print("=" * 72)
    print("   PHASE 3.5: INDONESIAN VOICE QUALITY & LATENCY VALIDATION")
    print("=" * 72)

    settings = get_settings()
    tts = TextToSpeech(settings=settings)

    test_cases = [
        ("Kabar", "Selamat pagi, apa kabar?", "Selamat pagi. Saya siap membantu Anda dengan apa pun yang dibutuhkan."),
        ("Chrome", "Baik, sekarang buka Chrome.", "Membuka Chrome, sir."),
        ("RAM_SSD", "Saya ingin mengetahui perbedaan RAM dan SSD.", "RAM adalah memori sementara untuk proses aktif, sedangkan SSD adalah penyimpanan permanen untuk data dan sistem operasi."),
        ("Jadwal", "JARVIS, tolong jelaskan jadwal saya hari ini.", "Maaf sir, saya belum memiliki akses ke kalender atau jadwal Anda hari ini."),
    ]

    print("\n--- Testing Indonesian Piper Model (id_ID-news_tts-medium) ---")
    tts.load_model("id")

    results = []

    for key, prompt, response in test_cases:
        clean_text = clean_text_for_speech(response)
        t0 = time.time()
        audio, sr = tts.synthesize(clean_text, language="id")
        synth_time = time.time() - t0

        assert audio is not None and len(audio) > 0, f"Synthesis failed for {key}"
        dur = len(audio) / sr
        rtf = synth_time / dur

        # Audio quality checks
        peak = np.max(np.abs(audio)) / 32768.0
        rms = np.sqrt(np.mean((audio.astype(np.float32) / 32768.0) ** 2))
        is_clipped = bool(np.max(np.abs(audio)) >= 32767)

        # Save WAV file
        out_wav = os.path.join(_PROJECT_ROOT, "data", f"id_test_{key.lower()}.wav")
        with wave.open(out_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(audio.tobytes())

        print(f"\n[Prompt]:   \"{prompt}\"")
        print(f"[Response]: \"{response}\"")
        print(f"[Metrics]:  Duration: {dur:.2f}s | Synth: {synth_time:.3f}s | RTF: {rtf:.2f}x")
        print(f"[Quality]:  Peak: {peak:.3f} | RMS: {rms:.4f} | Clipped: {is_clipped} | Saved: {out_wav}")

        results.append({
            "key": key,
            "prompt": prompt,
            "response": response,
            "duration": dur,
            "synth_time": synth_time,
            "rtf": rtf,
            "peak": peak,
            "rms": rms,
            "clipped": is_clipped,
            "wav": out_wav,
        })

    print("\n" + "=" * 72)
    print("INDONESIAN VOICE VALIDATION COMPLETE")
    print("=" * 72)
    return results


if __name__ == "__main__":
    validate_indonesian_voice()
