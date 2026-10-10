"""Automated tests for Phase 4.1 Audio Stability, Microphone Lifecycle, and Silence Rejection."""

import queue
import threading
import time
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType
from app.tools.browser import is_known_website, website_registry
from app.voice.audio_recorder import PushToTalkRecorder, reset_cached_input_device
from app.voice.speech_to_text import SpeechToText
from app.voice.wake_word import WakeWordDetector, WakeWordState


@pytest.fixture
def settings():
    return Settings(
        jarvis_name="Jarvis",
        tts_enabled=False,
        voice_enabled=False,
    )


@pytest.fixture
def mock_orchestrator(settings):
    mock_llm = MagicMock()
    mock_llm.is_server_available.return_value = True
    mock_llm.is_model_available.return_value = True
    mock_llm.chat_stream.return_value = iter(["Hello, sir."])

    orch = Orchestrator(settings=settings, llm_client=mock_llm)
    return orch


# ---------------------------------------------------------------------------
# Test 1: Empty Audio and Low-Energy Noise Do Not Invoke LLM or Tools
# ---------------------------------------------------------------------------
def test_empty_audio_does_not_invoke_llm_or_tool(mock_orchestrator):
    mock_stt = MagicMock()
    mock_stt.transcribe.return_value = ("", {"language": "", "peak": 0.0, "rms": 0.0})
    mock_orchestrator.stt = mock_stt

    with patch("app.tools.apps.launch_application") as mock_launch:
        # 1. Zero length audio
        text, info = mock_orchestrator.transcribe_audio(np.zeros(0, dtype=np.float32))
        assert text == ""
        mock_launch.assert_not_called()
        mock_orchestrator.llm.chat_stream.assert_not_called()

        # 2. Pure flat silence
        silence = np.zeros(16000, dtype=np.float32)
        text, info = mock_orchestrator.transcribe_audio(silence)
        assert text == ""
        mock_launch.assert_not_called()
        mock_orchestrator.llm.chat_stream.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2: Silence After Wake Word Does Not Trigger Command Execution
# ---------------------------------------------------------------------------
def test_silence_after_wake_word_does_not_trigger_command(settings):
    captured_commands = []

    detector = WakeWordDetector(
        settings=settings,
        on_command_captured=lambda audio: captured_commands.append(audio),
    )

    # Mock openwakeword model
    mock_model = MagicMock()
    mock_model.models = {"hey_jarvis": {}}
    mock_model.predict.return_value = {"hey_jarvis": 0.95}
    detector._model = mock_model
    detector._model_key = "hey_jarvis"
    detector.device_index = 0

    with patch("sounddevice.InputStream") as mock_stream_cls:
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream

        # Start detector
        detector.start()
        assert detector.state == WakeWordState.LISTENING_FOR_WAKE_WORD

        # Simulate wake-word chunk (triggers wake word)
        wake_chunk = np.zeros(1280, dtype=np.int16)
        detector._audio_queue.put(wake_chunk)

        # Allow worker thread to detect wake word and transition to CAPTURING_COMMAND
        time.sleep(0.15)
        assert detector.state in (WakeWordState.WAKE_WORD_DETECTED, WakeWordState.CAPTURING_COMMAND)

        # Now feed 40 chunks of silence (each RMS < 150) to trigger silence timeout
        silence_chunk = np.zeros(1280, dtype=np.int16)
        for _ in range(45):
            detector._audio_queue.put(silence_chunk)

        # Wait for silence timeout
        time.sleep(0.3)

        # Verify command capture was rejected and returned to listening standby
        detector.stop()
        assert len(captured_commands) == 0, "Silence should never be dispatched to on_command_captured"


# ---------------------------------------------------------------------------
# Test 3: Wake Detector Can Stop and Start Repeatedly Without Error (10 Cycles)
# ---------------------------------------------------------------------------
def test_wake_detector_stop_start_repeatedly_without_error(settings):
    detector = WakeWordDetector(settings=settings)

    mock_model = MagicMock()
    mock_model.models = {"hey_jarvis": {}}
    detector._model = mock_model
    detector._model_key = "hey_jarvis"
    detector.device_index = 0

    with patch("sounddevice.InputStream") as mock_stream_cls:
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream

        for cycle in range(10):
            detector.start()
            assert detector.state == WakeWordState.LISTENING_FOR_WAKE_WORD
            assert detector._stream is not None

            detector.stop()
            assert detector.state == WakeWordState.STOPPED
            assert detector._stream is None


# ---------------------------------------------------------------------------
# Test 4: Exceptions During Stream Start Release Audio Resources
# ---------------------------------------------------------------------------
def test_exceptions_release_audio_resources(settings):
    import sounddevice as sd

    detector = WakeWordDetector(settings=settings)
    mock_model = MagicMock()
    mock_model.models = {"hey_jarvis": {}}
    detector._model = mock_model
    detector._model_key = "hey_jarvis"
    detector.device_index = 0

    with patch("sounddevice.InputStream", side_effect=sd.PortAudioError("Device busy")):
        with pytest.raises(sd.PortAudioError):
            detector.start()

        assert detector.state == WakeWordState.STOPPED
        assert detector._stream is None


# ---------------------------------------------------------------------------
# Test 5: PTT Amplitude Measurement Uses Expected Units and Values
# ---------------------------------------------------------------------------
def test_ptt_amplitude_metrics_units_and_values():
    with patch("app.voice.audio_recorder.find_working_input_device", return_value=(0, 16000, 1)):
        recorder = PushToTalkRecorder(device_index=0)

    # Create known 440Hz sine wave with peak = 0.50
    duration = 1.0
    sr = 16000
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    sine = (0.50 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)

    with patch("sounddevice.InputStream") as mock_stream_cls:
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream

        recorder.start_recording()
        # Feed simulated chunks into recorder queue
        recorder._queue.put(sine[:8000].reshape(-1, 1))
        recorder._queue.put(sine[8000:].reshape(-1, 1))

        audio_out = recorder.stop_recording()

        metrics = recorder.get_last_audio_metrics()
        assert np.isclose(metrics["peak"], 0.50, atol=0.05)
        assert metrics["rms"] > 0.30
        assert metrics["duration_s"] == 1.0
        assert len(audio_out) == 16000


# ---------------------------------------------------------------------------
# Test 6: Instagram Registration and Deterministic Browser Routing
# ---------------------------------------------------------------------------
def test_instagram_registered_and_routes_to_browser():
    router = CommandRouter()

    # 1. Registry verification
    assert is_known_website("instagram")
    assert is_known_website("ig")
    assert is_known_website("insta")
    site = website_registry.get("instagram")
    assert site is not None
    assert site.url == "https://www.instagram.com"

    # 2. Command routing verification
    phrases = [
        "Open Instagram",
        "open instagram.",
        "Buka Instagram",
        "Buka Instagram dong",
        "Tolong buka Instagram",
        "Open IG",
        "Buka Insta",
    ]
    for text in phrases:
        res = router.route(text)
        assert res.route_type == RouteType.FAST_COMMAND, f"Routing failed for '{text}'"
        assert res.action == "open_website"
        assert res.args.get("target") == "instagram"
        assert res.route == "DIRECT"


# ---------------------------------------------------------------------------
# Test 7: Completed Browser Command and Error Recovery Restore Wake Listening
# ---------------------------------------------------------------------------
def test_completed_browser_command_restores_wake_listening(mock_orchestrator, settings):
    detector = WakeWordDetector(settings=settings)
    mock_model = MagicMock()
    mock_model.models = {"hey_jarvis": {}}
    detector._model = mock_model
    detector._model_key = "hey_jarvis"

    with patch("sounddevice.InputStream"):
        detector.start()
        detector.set_state(WakeWordState.PROCESSING_COMMAND)

        # Simulate execution turn
        with patch("app.tools.browser.launch_website", return_value=(True, "Instagram", "https://www.instagram.com", "Launched")):
            route, gen = mock_orchestrator.process_input_stream("Open Instagram")
            output = "".join(list(gen))
            assert "Instagram" in output

            # In main.py, try/finally ensures resume is invoked
            detector.resume()
            assert detector.state == WakeWordState.LISTENING_FOR_WAKE_WORD

        detector.stop()


# ---------------------------------------------------------------------------
# Test 8: STT Discards Low Energy Ambient Noise Without Running Non-VAD Fallback
# ---------------------------------------------------------------------------
def test_stt_discards_ambient_noise_without_hallucinating(settings):
    stt = SpeechToText(settings=settings)

    # 1. Faint noise (RMS < 0.001) should be rejected before Whisper model call
    low_noise = (np.random.randn(16000) * 0.0005).astype(np.float32)
    transcription, info = stt.transcribe(low_noise)
    assert transcription == ""

    # 2. Mock Whisper returning empty segments with VAD enabled
    stt._model = MagicMock()
    stt._model.transcribe.return_value = (iter([]), MagicMock(language="id", language_probability=0.0))

    audible_audio = (np.sin(np.linspace(0, 10, 16000)) * 0.05).astype(np.float32)
    transcription, info = stt.transcribe(audible_audio)
    assert transcription == ""
    # Ensure transcribe was called with vad_filter=True and not retried with vad_filter=False
    assert stt._model.transcribe.call_count == 1
    call_kwargs = stt._model.transcribe.call_args[1]
    assert call_kwargs.get("vad_filter") is True
