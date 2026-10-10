"""JARVIS Phase 3.6 — Diagnostic and Validation Script.

Meets all Phase 3.6 requirements:
1. Lists active input device and audio format.
2. Measures STT on target utterances:
   - "Selamat pagi, apa kabar?"
   - "Tolong buka Chrome."
   - "Sekarang buka Google Chrome."
   - "Saya ingin mengetahui perbedaan RAM dan SSD."
   - "Jelaskan jadwal saya hari ini."
   - "Hello, Jarvis."
   - "What time is it?"
3. Reports detected language, transcription, duration, peak, RMS, and STT latency.
4. Reports which Piper model was selected for the resulting response.
5. Verifies CommandRouter without launching actual apps (using mock).
"""

import sys
import time
from pathlib import Path
from unittest.mock import patch
import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Ensure UTF-8 console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

import sounddevice as sd
from app.core.config import get_settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType
from app.voice.audio_recorder import PushToTalkRecorder, resample_audio
from app.voice.speech_to_text import SpeechToText
from app.voice.text_to_speech import TextToSpeech, detect_language


def report_active_audio_device(settings) -> None:
    """Queries and displays active audio input device and recording format."""
    print("=" * 70)
    print(" 1. ACTIVE INPUT DEVICE & AUDIO FORMAT")
    print("=" * 70)

    devices = sd.query_devices()
    configured_idx = settings.audio_device

    print(f"Total Audio Devices Detected: {len(devices)}")
    print(f"Configured Input Device Index: {configured_idx}")

    recorder = PushToTalkRecorder(device_index=configured_idx)
    selected_idx = recorder.device_index
    if selected_idx is not None and 0 <= selected_idx < len(devices):
        dev_info = devices[selected_idx]
        hostapi = sd.query_hostapis(dev_info["hostapi"])["name"]
        print(f"Active Device Name:        {dev_info['name']}")
        print(f"Host API:                  {hostapi}")
        print(f"Device Max Input Channels: {dev_info['max_input_channels']}")
        print(f"Hardware Sample Rate:      {recorder.sample_rate} Hz")
        print(f"Hardware Channels:         {recorder.channels}")
        print(f"Target Processed Format:   16,000 Hz float32 mono")
    else:
        print("Using System Default Input Device (16,000 Hz float32 mono)")


def run_target_utterances_benchmark(orchestrator: Orchestrator) -> list[dict]:
    """Runs the 7 Phase 3.6 test utterances through STT and reports all metrics."""
    print("\n" + "=" * 70)
    print(" 2. TARGET UTTERANCES SPEECH-TO-TEXT & PIPER MODEL SELECTION")
    print("=" * 70)

    stt = orchestrator.get_stt()
    tts = orchestrator.get_tts()
    stt.load_model()
    tts.load_model("id")
    tts.load_model("en")

    test_utterances = [
        ("Selamat pagi, apa kabar?", "id"),
        ("Tolong buka Chrome.", "id"),
        ("Sekarang buka Google Chrome.", "id"),
        ("Saya ingin mengetahui perbedaan RAM dan SSD.", "id"),
        ("Jelaskan jadwal saya hari ini.", "id"),
        ("Hello, Jarvis.", "en"),
        ("What time is it?", "en"),
    ]

    results = []

    for idx, (target_text, true_lang) in enumerate(test_utterances, 1):
        print(f"\n[Test #{idx}] Target: \"{target_text}\" (Expected: {true_lang.upper()})")

        # 1. Synthesize clean reference acoustic signal using Piper
        raw_audio_int16, sr = tts.synthesize(target_text, language=true_lang)
        assert raw_audio_int16 is not None, f"Synthesis failed for '{target_text}'"

        float_audio = raw_audio_int16.astype(np.float32) / 32768.0
        audio_16k = resample_audio(float_audio, sr, 16000)

        duration = len(audio_16k) / 16000.0
        peak = float(np.max(np.abs(audio_16k)))
        rms = float(np.sqrt(np.mean(audio_16k**2)))

        # 2. Transcribe via faster-whisper with bilingual resolution and initial prompt
        t0 = time.time()
        transcription, stt_info = stt.transcribe(audio_16k, sample_rate=16000, language="auto")
        stt_latency = time.time() - t0

        detected_lang = stt_info.get("language", "id")

        # 3. Simulate routing & Piper model selection without launching actual apps
        with patch("app.tools.apps.launch_application") as mock_launch:
            mock_launch.return_value = (True, "Chrome", "Berhasil")
            route, stream_gen = orchestrator.process_input_stream(transcription)
            response_tokens = list(stream_gen)
            response_text = "".join(response_tokens).strip()

        # Model selection: orchestrator state language -> piper model
        selected_piper_model = (
            orchestrator.settings.tts_model_id
            if orchestrator.state.conversation_language.startswith("id")
            else orchestrator.settings.tts_model_en
        )

        print(f"  * Audio Duration:     {duration:.2f} s")
        print(f"  * Peak Amplitude:     {peak:.4f} (RMS: {rms:.4f})")
        print(f"  * STT Latency:        {stt_latency:.2f} s")
        print(f"  * Detected Language:  {detected_lang.upper()} (Expected: {true_lang.upper()})")
        print(f"  * Transcription:      \"{transcription}\"")
        print(f"  * Route Type:         {route.route_type.name} (action: {route.action})")
        print(f"  * Assistant Reply:    \"{response_text}\"")
        print(f"  * Piper Model Used:   {selected_piper_model}")

        results.append({
            "target": target_text,
            "true_lang": true_lang,
            "detected_lang": detected_lang,
            "transcription": transcription,
            "duration": duration,
            "peak": peak,
            "rms": rms,
            "stt_latency": stt_latency,
            "route": route.route_type.name,
            "action": route.action,
            "piper_model": selected_piper_model,
        })

    return results


def verify_router_and_normalization():
    """Tests the CommandRouter with app name variants and misrecognitions without launching apps."""
    print("\n" + "=" * 70)
    print(" 3. COMMAND ROUTER & CHROME ALIAS NORMALIZATION VERIFICATION")
    print("=" * 70)

    router = CommandRouter()

    test_cases = [
        ("Tolong buka Chrome.", "open_application", "chrome"),
        ("Sekarang buka Google Chrome.", "open_application", "chrome"),
        ("Tolong buka kromya", "open_application", "chrome"),
        ("Buka krom", "open_application", "chrome"),
        ("buka notepad", "open_application", "notepad"),
        ("tolong buka catatan", "open_application", "notepad"),
        ("buka kalkulator", "open_application", "calculator"),
        ("tutup chrome", "close_application", "chrome"),
        ("What time is it?", "get_time", ""),
    ]

    all_passed = True
    for cmd, expected_action, expected_target in test_cases:
        res = router.route(cmd)
        target = res.args.get("target", "")
        passed = (res.action == expected_action) and (target == expected_target)
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} \"{cmd}\" -> action: '{res.action}', target: '{target}'")
        if not passed:
            all_passed = False

    assert all_passed, "Command router verification failed!"
    print("  All router and normalization cases PASSED.")


def main():
    orchestrator = Orchestrator()
    settings = get_settings()

    report_active_audio_device(settings)
    results = run_target_utterances_benchmark(orchestrator)
    verify_router_and_normalization()

    print("\n" + "=" * 70)
    print(" ALL DIAGNOSTIC TESTS COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    main()
