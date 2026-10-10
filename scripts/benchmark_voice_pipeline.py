"""JARVIS Voice Pipeline Latency Benchmark Script.

Measures individual pipeline stages:
1. Audio Sample Duration & Ingestion
2. Speech-to-Text Transcription Latency (faster-whisper)
3. Command Router Intent Classification Latency
4. Local LLM Time-to-First-Token (TTFT)
5. Local LLM Generation Time & Output Token Speed
6. Total End-to-End Latency
"""

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
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType
from app.voice.speech_to_text import SpeechToText


def load_sample_audio(wav_path: str) -> np.ndarray:
    """Loads a mono 16kHz WAV file into float32 numpy array."""
    with wave.open(wav_path, "rb") as wf:
        data = wf.readframes(wf.getnframes())
        return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0


def run_benchmark():
    settings = get_settings()
    orchestrator = Orchestrator(settings=settings)
    stt = orchestrator.get_stt()

    print("=" * 72)
    print("      JARVIS VOICE-TO-TEXT PIPELINE BENCHMARK")
    print("=" * 72)
    print(f"Hardware:    Intel Core i5-1335U (10 cores/12 threads) | 16 GB RAM")
    print(f"Platform:    Windows 11 Pro 64-bit")
    print(f"Model:       {settings.model} (Ollama, think=False, temp={settings.temperature})")
    print(f"STT:         faster-whisper '{settings.stt_model}' ({settings.stt_device}, {settings.stt_compute_type}, lang={settings.stt_language})")
    print("=" * 72)

    # 1. Warm-up STT and LLM
    print("\n[Warmup] Pre-warming Whisper and Ollama Qwen3:8B...")
    stt.load_model()
    # Ensure model is warm in Ollama memory
    orchestrator.llm.chat([{"role": "user", "content": "ping"}])
    print("[Warmup] Completed. Pipeline warm.")

    # 2. Benchmark STT on audio sample
    wav_sample_path = os.path.join(_PROJECT_ROOT, "data", "mic_test_sample.wav")
    audio = load_sample_audio(wav_sample_path)
    audio_dur = len(audio) / 16000.0

    print(f"\n--- Stage 1: STT Transcription ({audio_dur:.2f}s sample) ---")
    stt_times = []
    transcriptions = []
    for i in range(3):
        t0 = time.time()
        text, info = stt.transcribe(audio)
        dt = time.time() - t0
        stt_times.append(dt)
        transcriptions.append(text)
        print(f"  Run {i+1}: {dt:.3f}s (audio: {info.get('duration', audio_dur):.2f}s, text: {text!r})")

    avg_stt = sum(stt_times) / len(stt_times)
    print(f"  Average STT Latency: {avg_stt:.3f}s (RTF: {avg_stt / audio_dur:.2f}x)")

    # 3. Benchmark TTS synthesis latency directly
    tts = orchestrator.get_tts()
    tts.load_model("en")
    print("\n--- Stage 2: TTS Synthesis Latency ---")
    en_sample = "Good evening, sir. All systems are operational."
    t0 = time.time()
    audio_en, sr_en = tts.synthesize(en_sample, language="en")
    synth_time_en = time.time() - t0
    audio_dur_en = len(audio_en) / sr_en if audio_en is not None else 0.0
    print(f"  English:    {audio_dur_en:.2f}s audio in {synth_time_en:.3f}s (RTF: {synth_time_en/audio_dur_en:.2f}x)")

    tts.load_model("id")
    id_sample = "Selamat malam, sir. Sistem JARVIS siap membantu Anda."
    t0 = time.time()
    audio_id, sr_id = tts.synthesize(id_sample, language="id")
    synth_time_id = time.time() - t0
    audio_dur_id = len(audio_id) / sr_id if audio_id is not None else 0.0
    print(f"  Indonesian: {audio_dur_id:.2f}s audio in {synth_time_id:.3f}s (RTF: {synth_time_id/audio_dur_id:.2f}x)")

    # 4. Test Cases (mix of Fast Deterministic Commands & Conversational AI queries)
    test_cases = [
        ("Fast Command: App Launch", "Jarvis, open Chrome"),
        ("Fast Command: Time Query", "What time is it?"),
        ("Fast Command: Date Query", "Jarvis, what is today's date?"),
        ("Conversational: Identity", "Who are you?"),
        ("Conversational: Creative", "Tell me a very short joke."),
        ("Reasoning: Knowledge Query", "What is the difference between RAM and SSD?"),
    ]

    print("\n" + "=" * 80)
    print("--- Stage 3: End-to-End Pipeline Evaluation (STT + LLM + Streaming TTS) ---")
    print("=" * 80)

    results = []

    for category, prompt in test_cases:
        print(f"\n>> [{category}] Prompt: \"{prompt}\"")
        
        # 1. Router timing
        t_router_0 = time.perf_counter()
        route = orchestrator.router.route(prompt)
        t_router = (time.perf_counter() - t_router_0) * 1000.0  # in ms

        # 2. Execution & Streaming TTS timing
        route_obj, stream_gen = orchestrator.process_input_stream(prompt)
        t_start = time.perf_counter()
        ttft = None
        chunks = []

        def _track_token(tok: str) -> None:
            nonlocal ttft
            if ttft is None:
                ttft = time.perf_counter() - t_start
            chunks.append(tok)

        tts_stats = tts.speak_stream(
            stream_gen,
            language="en",
            on_token=_track_token,
        )

        t_end = time.perf_counter()
        total_resp_time = t_end - t_start
        gen_time = max(0.0, total_resp_time - (ttft or 0.0))
        full_text = "".join(chunks).strip()
        word_count = len(full_text.split())
        ttfa = tts_stats.get("ttfa", 0.0)
        speech_dur = tts_stats.get("total_speech_s", 0.0)

        # Stop active audio playback between benchmark iterations
        tts.stop()

        e2e_first_audio = avg_stt + ttfa
        e2e_total = avg_stt + total_resp_time

        print(f"   Route:        {route_obj.route_type.name} ({route_obj.action}) in {t_router:.2f} ms")
        print(f"   Response:     \"{full_text}\"")
        print(f"   Words:        {word_count} words | Speech: {speech_dur:.2f}s")
        print(f"   TTFT (text):  {(ttft or 0):.3f}s")
        print(f"   TTFA (audio): {ttfa:.3f}s")
        print(f"   Gen Time:     {gen_time:.3f}s | Total LLM: {total_resp_time:.3f}s")
        print(f"   E2E Audio:    STT ({avg_stt:.2f}s) + TTFA ({ttfa:.2f}s) = {e2e_first_audio:.3f}s to first spoken word")

        results.append({
            "category": category,
            "prompt": prompt,
            "route_type": route_obj.route_type.name,
            "action": route_obj.action,
            "router_ms": t_router,
            "ttft_s": ttft or 0.0,
            "ttfa_s": ttfa,
            "gen_s": gen_time,
            "total_s": total_resp_time,
            "speech_s": speech_dur,
            "e2e_audio_s": e2e_first_audio,
            "words": word_count,
            "response": full_text,
        })

    print("\n" + "=" * 80)
    print("                PHASE 3 BENCHMARK SUMMARY TABLE")
    print("=" * 80)
    print(f"{'Test Case':<28} | {'Route':<14} | {'TTFT':<6} | {'TTFA':<6} | {'Gen':<6} | {'Audio':<6} | {'Words'}")
    print("-" * 80)
    for r in results:
        print(f"{r['category'][:28]:<28} | {r['route_type']:<14} | {r['ttft_s']:>4.2f}s | {r['ttfa_s']:>4.2f}s | {r['gen_s']:>4.2f}s | {r['speech_s']:>4.1f}s | {r['words']:>3d}")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark()
