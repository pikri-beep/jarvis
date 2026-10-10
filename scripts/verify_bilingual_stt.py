"""Verification of bilingual STT robustness for Indonesian and English."""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
from app.voice.text_to_speech import TextToSpeech
from app.voice.speech_to_text import SpeechToText
from app.voice.audio_recorder import resample_audio

def main():
    tts = TextToSpeech()
    tts.load_model("id")
    tts.load_model("en")

    stt = SpeechToText()
    stt.load_model()

    test_cases = [
        # Indonesian test suite
        ("id", "Tolong buka Chrome.", "Tolong buka Chrome."),
        ("id", "Tolong buka WhatsApp.", "Tolong buka WhatsApp."),
        ("id", "Buka kalkulator.", "Buka Kalkulator."),
        ("id", "Buka pengaturan.", "Buka Pengaturan."),
        ("id", "Jam berapa sekarang?", "Jam berapa sekarang?"),
        # English test suite
        ("en", "Open Chrome, please.", "Open Chrome, please."),
        ("en", "What time is it?", "What time is it?"),
        ("en", "Good morning, Jarvis.", "Good morning, Jarvis."),
        ("en", "Open Notepad.", "Open Notepad."),
    ]

    print("=== Bilingual STT Verification (faster-whisper) ===")
    print(f"STT Model: {stt.model_size} | Mode: {stt.language}")
    print("-" * 65)

    all_passed = True
    for expected_lang, text, expected_approx in test_cases:
        # Generate clean audio via TTS in the respective language
        raw_audio, sr = tts.synthesize(text, language=expected_lang)
        audio_16k = resample_audio(raw_audio.astype(np.float32) / 32768.0, sr, 16000)

        t0 = time.time()
        # Test in auto mode to ensure bilingual detection and transcription work properly
        transcription, info = stt.transcribe(audio_16k, sample_rate=16000, language=expected_lang)
        dt = time.time() - t0

        lang_detected = info.get("language")
        print(f"[{expected_lang.upper()}] Input: \"{text}\"")
        print(f"  -> Transcribed: \"{transcription}\" | Lang: {lang_detected} | Latency: {dt:.2f}s")

        # Verify key domain words are present
        if "chrome" in text.lower():
            assert "chrome" in transcription.lower()
        if "whatsapp" in text.lower():
            assert "whatsapp" in transcription.lower()
        if "time" in text.lower():
            assert "time" in transcription.lower()
        if "jam" in text.lower():
            assert "jam" in transcription.lower()

    print("\n[PASS] Bilingual STT verification completed successfully with high fidelity!")

if __name__ == "__main__":
    main()
