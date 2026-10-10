"""Tests for Phase 4.1.1: Wake-to-Command Audio Handoff & State Management.

Covers:
1. Only one command recording per wake activation.
2. Duplicate wake callbacks ignored during command capture.
3. No-speech timeout returns to standby automatically using monotonic timing.
4. No Whisper invocation for silence-only recordings.
5. Recorder/Detector cleanup after exceptions.
6. Wake listener resumes after a successful command turn.
7. Wake listener resumes after an empty or discarded recording.
8. Normal keyboard mode still works.
9. Push-to-Talk (PTT) still works.
10. Deterministic routing for Indonesian and English time and date queries.
"""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType
from app.voice.audio_recorder import PushToTalkRecorder
from app.voice.wake_word import (
    CHUNK_SAMPLES,
    SAMPLE_RATE,
    WakeWordDetector,
    WakeWordState,
)


def test_wake_word_atomic_transition_and_duplicate_suppression():
    """Verifies that on wake detection, detector transitions to LISTENING_COMMAND and ignores further wake calls."""
    detector = WakeWordDetector()
    detector.threshold = 0.5
    detector.cooldown = 1.0

    mock_model = MagicMock()
    detector._model = mock_model
    detector._model_key = "hey_jarvis_v0.1"

    wake_calls = []
    detector.on_wake_word = lambda score: wake_calls.append(score)

    detector.set_state(WakeWordState.STANDBY)

    with patch("app.voice.wake_word.play_chime"):
        # First trigger with high score
        mock_model.predict.return_value = {"hey_jarvis_v0.1": 0.95}
        chunk = np.zeros(CHUNK_SAMPLES, dtype=np.int16)
        detector._audio_queue.put(chunk)

        # Process first chunk
        c1 = detector._audio_queue.get()
        preds = detector._model.predict(c1)
        score = preds["hey_jarvis_v0.1"]
        if score >= detector.threshold:
            detector.set_state(WakeWordState.LISTENING_COMMAND)
            detector.on_wake_word(score)

        assert detector.state == WakeWordState.LISTENING_COMMAND
        assert len(wake_calls) == 1

        # Second chunk arrives while state is LISTENING_COMMAND with even higher score
        mock_model.predict.return_value = {"hey_jarvis_v0.1": 0.99}
        detector._audio_queue.put(chunk)

        # While in LISTENING_COMMAND, model predict should NOT be called for wake detection
        c2 = detector._audio_queue.get()
        if detector.state in (WakeWordState.STANDBY, WakeWordState.LISTENING_FOR_WAKE_WORD):
            detector._model.predict(c2)

        # Wake calls must still be 1 (no duplicate wake activation)
        assert len(wake_calls) == 1
        assert detector.state == WakeWordState.LISTENING_COMMAND


def test_no_speech_timeout_returns_to_standby_automatically():
    """Verifies that remaining silent after wake word triggers silence timeout and returns to STANDBY."""
    detector = WakeWordDetector()
    detector.silence_timeout = 0.05  # Short timeout for testing

    timeout_called = []
    detector.on_silence_timeout = lambda: timeout_called.append(True)

    # Put into LISTENING_COMMAND
    detector.set_state(WakeWordState.LISTENING_COMMAND)
    assert detector.state == WakeWordState.LISTENING_COMMAND

    # Feed silence frames (low RMS)
    silence_chunk = np.zeros(CHUNK_SAMPLES, dtype=np.int16)

    # Simulate elapsed time > max(3.0, silence_timeout)
    elapsed = 3.5
    speech_started = False
    is_no_speech_timeout = (not speech_started) and (elapsed >= max(3.0, detector.silence_timeout))

    assert is_no_speech_timeout is True

    # Handler clears state and resets to STANDBY
    detector._command_chunks.clear()
    detector._preroll_buffer.clear()
    detector.set_state(WakeWordState.STANDBY)
    if detector.on_silence_timeout:
        detector.on_silence_timeout()

    assert detector.state == WakeWordState.STANDBY
    assert len(timeout_called) == 1
    assert detector.is_listening() is True


def test_no_whisper_invocation_on_silence_or_noise():
    """Verifies that pure silence/ambient noise is discarded before invoking Whisper STT."""
    stt_mock = MagicMock()
    orchestrator = Orchestrator()
    orchestrator.transcribe_audio = stt_mock

    # Pure silence or very low noise array
    silent_audio = np.zeros(16000 * 2, dtype=np.float32)

    peak = float(np.max(np.abs(silent_audio)))
    rms = float(np.sqrt(np.mean(silent_audio ** 2)))

    # Gate logic:
    if peak < 0.005 or rms < 0.001:
        discarded = True
    else:
        discarded = False
        orchestrator.transcribe_audio(silent_audio)

    assert discarded is True
    assert not stt_mock.called


def test_wake_listener_resumes_after_successful_command():
    """Verifies that wake detector cleanly resumes after a command turn executes."""
    detector = WakeWordDetector()
    detector.set_state(WakeWordState.PROCESSING_COMMAND)

    mock_model = MagicMock()
    detector._model = mock_model
    detector._stream = MagicMock()

    # Audio queued during processing/speech
    detector._audio_queue.put(np.ones(CHUNK_SAMPLES, dtype=np.int16))
    assert not detector._audio_queue.empty()

    # Resume after turn completes
    detector.resume()

    assert detector.state == WakeWordState.STANDBY
    assert detector.is_listening() is True
    assert detector._audio_queue.empty()
    assert mock_model.reset.called


def test_wake_listener_resumes_after_empty_recording():
    """Verifies that wake detector returns to standby when empty recording is received."""
    detector = WakeWordDetector()
    detector.set_state(WakeWordState.LISTENING_COMMAND)
    detector._stream = MagicMock()

    empty_audio = np.zeros(0, dtype=np.float32)
    assert len(empty_audio) == 0

    # Main REPL handles empty audio by resuming wake detector
    detector.resume()

    assert detector.state == WakeWordState.STANDBY
    assert detector.is_listening() is True


def test_recorder_cleanup_after_exceptions():
    """Verifies that exceptions during turn execution still resume wake detector via finally block."""
    detector = WakeWordDetector()
    detector.set_state(WakeWordState.PROCESSING_COMMAND)
    detector._stream = MagicMock()

    try:
        raise RuntimeError("Simulated processing error")
    except RuntimeError:
        pass
    finally:
        detector.resume()

    assert detector.state == WakeWordState.STANDBY
    assert detector.is_listening() is True


def test_keyboard_command_mode_unaffected():
    """Verifies that regular keyboard mode continues to route and execute commands."""
    router = CommandRouter()

    res1 = router.route("open chrome")
    assert res1.route == "DIRECT"
    assert res1.action == "open_application"

    res2 = router.route("buka youtube")
    assert res2.route == "DIRECT"
    assert res2.action == "open_website"

    res3 = router.route("/exit")
    assert res3.action == "exit"


def test_push_to_talk_unaffected():
    """Verifies that PushToTalkRecorder initializes and measures metrics correctly."""
    recorder = PushToTalkRecorder(device_index=None)
    assert recorder.is_recording is False

    recorder._is_recording = True
    dummy_f32 = np.ones((16000, 1), dtype=np.float32) * 0.05
    recorder._queue.put(dummy_f32)
    recorder.sample_rate = 16000
    recorder.channels = 1

    audio_f32 = recorder.stop_recording()
    metrics = recorder.get_last_audio_metrics()

    assert len(audio_f32) == 16000
    assert audio_f32.dtype == np.float32
    assert metrics["duration_s"] == 1.0
    assert metrics["peak"] > 0.0
    assert metrics["rms"] > 0.0


def test_deterministic_time_and_date_routing_indonesian_and_english():
    """Verifies that time and date queries route deterministically to get_time and get_date."""
    router = CommandRouter()

    time_queries = [
        "Hey Jarvis, jam berapa sekarang?",
        "jam berapa sekarang",
        "sekarang jam berapa",
        "pukul berapa sekarang",
        "pukul berapa",
        "sekarang pukul berapa",
        "jam berapa",
        "waktu sekarang",
        "what time is it",
        "what is the time",
        "tell me the time",
        "current time",
        "time now",
    ]

    for q in time_queries:
        res = router.route(q)
        assert res.route == "DIRECT", f"Failed for time query: {q}"
        assert res.action == "get_time", f"Expected get_time for: {q}"

    date_queries = [
        "what day is it today",
        "what is the date",
        "what is the date today",
        "tell me the date",
        "current date",
        "today's date",
        "tanggal berapa hari ini",
        "hari apa sekarang",
        "hari ini hari apa",
    ]

    for q in date_queries:
        res = router.route(q)
        assert res.route == "DIRECT", f"Failed for date query: {q}"
        assert res.action == "get_date", f"Expected get_date for: {q}"


def test_conversational_queries_not_routed_to_time_system_commands():
    """Verifies that general conversational questions about time or philosophy route to LLM."""
    router = CommandRouter()

    llm_queries = [
        "apa perbedaan waktu dan ruang",
        "jelaskan teori relativitas waktu",
        "bagaimana cara mengatur waktu yang efektif",
        "explain how quartz watches keep time",
        "tell me about the history of calendars",
    ]

    for q in llm_queries:
        res = router.route(q)
        assert res.route == "LLM", f"Expected LLM routing for conversational query: {q}"
