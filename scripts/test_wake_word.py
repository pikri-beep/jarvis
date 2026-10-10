"""Standalone validation and benchmark script for JARVIS Phase 4 Wake-Word Detection.

Features:
1. Automated synthetic benchmark: Tests positive wake-word utterances and negative control
   phrases generated via Piper TTS to measure accuracy, false rejection, false alarms, and latency.
2. Resource utilization profiling: Measures idle CPU and RAM footprint.
3. Interactive live mode: Allows real-time testing with user microphone.
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

import numpy as np
import psutil

from app.core.config import get_settings
from app.core.logger import setup_logger
from app.voice.audio_recorder import resample_audio
from app.voice.text_to_speech import TextToSpeech
from app.voice.wake_word import CHUNK_SAMPLES, SAMPLE_RATE, WakeWordDetector, WakeWordState, play_chime

logger = setup_logger("jarvis.scripts.test_wake_word")


def synthesize_phrase_audio(tts: TextToSpeech, phrase: str, language: str) -> np.ndarray:
    """Synthesizes phrase using Piper TTS and resamples to 16kHz mono float32."""
    raw_audio, sr = tts.synthesize(phrase, language=language)
    if raw_audio is None or len(raw_audio) == 0:
        return np.zeros(0, dtype=np.float32)
    # raw_audio is int16, normalize to float32
    audio_f32 = raw_audio.astype(np.float32) / 32768.0
    return resample_audio(audio_f32, orig_sr=sr, target_sr=SAMPLE_RATE)


def test_synthetic_benchmark(detector: WakeWordDetector) -> dict:
    """Runs repeatable benchmark with positive wake-word attempts and negative controls."""
    print("=" * 68)
    print("      JARVIS PHASE 4 - WAKE-WORD ACCURACY & LATENCY BENCHMARK")
    print("=" * 68)

    settings = get_settings()
    tts = TextToSpeech(settings)
    tts.load_model()

    positive_phrases = [
        # 10 English variations of "Hey Jarvis"
        ("Hey Jarvis", "en"),
        ("Hey Jarvis, open Chrome", "en"),
        ("Hey Jarvis, what time is it?", "en"),
        ("Hey Jarvis, take a screenshot", "en"),
        ("Hey Jarvis, good morning", "en"),
        ("Hey Jarvis, tell me a joke", "en"),
        ("Hey Jarvis, how are you today?", "en"),
        ("Hey Jarvis, lock the computer", "en"),
        ("Hey Jarvis, increase the volume", "en"),
        ("Hey Jarvis, what is quantum computing?", "en"),
        # 10 Indonesian-accented / bilingual mixed variations
        ("Hey Jarvis, tolong buka Chrome", "id"),
        ("Hey Jarvis, apa kabar hari ini?", "id"),
        ("Hey Jarvis, jam berapa sekarang?", "id"),
        ("Hey Jarvis, tolong ambil screenshot", "id"),
        ("Hey Jarvis, buka Youtube", "id"),
        ("Hey Jarvis, matikan suara", "id"),
        ("Hey Jarvis, tolong jelaskan perbedaan RAM dan SSD", "id"),
        ("Hey Jarvis, besarkan volume", "id"),
        ("Hey Jarvis, selamat pagi", "id"),
        ("Hey Jarvis, tolong catat ini", "id"),
    ]

    negative_phrases = [
        ("Selamat pagi apa kabar semuanya?", "id"),
        ("Tolong buka browser Chrome sekarang", "id"),
        ("Saya ingin mengetahui perbedaan RAM dan SSD", "id"),
        ("Bagaimana cuaca besok pagi di Jakarta?", "id"),
        ("Kunci komputer sekarang juga", "id"),
        ("Buka Youtube dan cari video musik", "id"),
        ("Hari ini adalah hari yang cerah", "id"),
        ("Berapa harga saham hari ini?", "id"),
        ("Bisa bantu saya menulis email penting?", "id"),
        ("Terima kasih banyak atas bantuannya", "id"),
        ("Good morning everyone, how are you?", "en"),
        ("Can you please open the Chrome browser?", "en"),
        ("What is the current time in London?", "en"),
        ("I would like to summarize this document", "en"),
        ("Please increase the system volume", "en"),
        ("Explain the difference between CPU and GPU", "en"),
        ("Lock the Windows workstation right now", "en"),
        ("Take a full screen screenshot please", "en"),
        ("Today is a wonderful day to code", "en"),
        ("Thank you very much for your kind help", "en"),
    ]

    # Warm-up model
    detector.initialize()
    oww_model = detector._model
    model_key = detector._model_key

    # Benchmark inference speed per 80ms chunk
    dummy_chunk = np.zeros(CHUNK_SAMPLES, dtype=np.int16)
    warmup_times = []
    for _ in range(50):
        t0 = time.perf_counter()
        oww_model.predict(dummy_chunk)
        warmup_times.append(time.perf_counter() - t0)
    avg_chunk_latency_ms = (sum(warmup_times) / len(warmup_times)) * 1000.0

    print(f"\n[1] Chunk Inference Latency (80ms frame): {avg_chunk_latency_ms:.2f} ms")
    print(f"    Real-time speedup factor: {80.0 / avg_chunk_latency_ms:.1f}x real-time")

    print("\n[2] Testing 20 Positive Wake-Word Utterances ('Hey Jarvis'):")
    pos_detected = 0
    pos_scores = []
    for idx, (phrase, lang) in enumerate(positive_phrases, 1):
        audio = synthesize_phrase_audio(tts, phrase, lang)
        oww_model.reset()
        audio_int16 = (audio * 32767.0).clip(-32768, 32767).astype(np.int16)

        max_score = 0.0
        # Stream chunks into openWakeWord model
        for i in range(0, len(audio_int16) - CHUNK_SAMPLES, CHUNK_SAMPLES):
            chunk = audio_int16[i : i + CHUNK_SAMPLES]
            preds = oww_model.predict(chunk)
            score = preds.get(model_key, 0.0)
            if score > max_score:
                max_score = score

        is_hit = max_score >= detector.threshold
        if is_hit:
            pos_detected += 1
        pos_scores.append(max_score)
        mark = "[PASS]" if is_hit else "[FAIL]"
        print(f"  [{idx:02d}/20] {mark} | Score: {max_score:.3f} | [{lang.upper()}] \"{phrase}\"")

    print("\n[3] Testing 20 Negative Control Phrases (Conversational Speech):")
    false_positives = 0
    neg_scores = []
    for idx, (phrase, lang) in enumerate(negative_phrases, 1):
        audio = synthesize_phrase_audio(tts, phrase, lang)
        oww_model.reset()
        audio_int16 = (audio * 32767.0).clip(-32768, 32767).astype(np.int16)

        max_score = 0.0
        for i in range(0, len(audio_int16) - CHUNK_SAMPLES, CHUNK_SAMPLES):
            chunk = audio_int16[i : i + CHUNK_SAMPLES]
            preds = oww_model.predict(chunk)
            score = preds.get(model_key, 0.0)
            if score > max_score:
                max_score = score

        is_fp = max_score >= detector.threshold
        if is_fp:
            false_positives += 1
        neg_scores.append(max_score)
        mark = "[FALSE ACTIVATION]" if is_fp else "[CLEAN]"
        print(f"  [{idx:02d}/20] {mark} | Score: {max_score:.3f} | [{lang.upper()}] \"{phrase}\"")

    # Measure CPU and RAM utilization
    process = psutil.Process(os.getpid())
    ram_mb = process.memory_info().rss / (1024 * 1024)
    cpu_percent = process.cpu_percent(interval=0.5)

    print("\n" + "=" * 68)
    print("                      BENCHMARK SUMMARY")
    print("=" * 68)
    print(f" Model Name:                 {detector.settings.wake_word_model}")
    print(f" Detection Threshold:        {detector.threshold}")
    print(f" Frame Size:                 {CHUNK_SAMPLES} samples (80 ms @ 16kHz)")
    print(f" Inference Latency:          {avg_chunk_latency_ms:.2f} ms per 80ms chunk")
    print(f" True Positive Rate (Recall): {pos_detected}/20 ({pos_detected / 20 * 100:.1f}%)")
    print(f" False Positive Rate:        {false_positives}/20 ({false_positives / 20 * 100:.1f}%)")
    print(f" Average Positive Score:     {np.mean(pos_scores):.3f}")
    print(f" Average Negative Score:     {np.mean(neg_scores):.3f}")
    print(f" Process Memory (RAM):       {ram_mb:.1f} MB")
    print(f" CPU Utilization:            {cpu_percent:.1f}%")
    print("=" * 68)

    return {
        "model": detector.settings.wake_word_model,
        "chunk_latency_ms": avg_chunk_latency_ms,
        "positive_detected": pos_detected,
        "positive_total": 20,
        "false_positives": false_positives,
        "negative_total": 20,
        "avg_positive_score": float(np.mean(pos_scores)),
        "avg_negative_score": float(np.mean(neg_scores)),
        "ram_mb": ram_mb,
        "cpu_percent": cpu_percent,
    }


def run_live_microphone_test(detector: WakeWordDetector) -> None:
    """Runs interactive live microphone test."""
    print("=" * 68)
    print("         JARVIS - LIVE MICROPHONE WAKE-WORD TEST")
    print("=" * 68)
    print(f" Trigger phrase: 'Hey Jarvis'")
    print(f" Threshold:      {detector.threshold}")
    print(f" Cooldown:       {detector.cooldown}s")
    print(" Speak into the microphone. Say 'Hey Jarvis' to trigger activation.")
    print(" Press Ctrl+C to stop.\n")

    activations = 0

    def on_detected(score: float):
        nonlocal activations
        activations += 1
        print(f"\n[🔔 WAKE WORD DETECTED #{activations}] Score: {score:.3f} | State -> {WakeWordState.WAKE_WORD_DETECTED.value}")

    def on_state(old: WakeWordState, new: WakeWordState):
        print(f"  [State Transition] {old.value} -> {new.value}")

    def on_command(audio: np.ndarray):
        duration_s = len(audio) / SAMPLE_RATE
        peak = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0
        print(f"  [Command Captured] {duration_s:.2f}s audio (Peak: {peak:.4f})")
        print("  [Simulating TTS Response...] Speaking acknowledgment...")
        detector.set_state(WakeWordState.SPEAKING_RESPONSE)
        time.sleep(1.0)
        print("  [Response Finished] Resuming wake-word detection...")
        detector.resume()

    detector.on_wake_word = on_detected
    detector.on_state_change = on_state
    detector.on_command_captured = on_command

    detector.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping live detector...")
    finally:
        detector.stop()
        detector.cleanup()
        print("Live test stopped safely.")


def main():
    parser = argparse.ArgumentParser(description="Test JARVIS Wake-Word Detection")
    parser.add_argument("--live", action="store_true", help="Run interactive live microphone test")
    args = parser.parse_args()

    detector = WakeWordDetector()
    if args.live:
        run_live_microphone_test(detector)
    else:
        test_synthetic_benchmark(detector)


if __name__ == "__main__":
    main()
