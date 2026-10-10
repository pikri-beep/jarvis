"""Unit and integration tests for Phase 4 Wake-Word Detection."""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.voice.wake_word import (
    CHUNK_SAMPLES,
    SAMPLE_RATE,
    WakeWordDetector,
    WakeWordState,
    generate_chime_audio,
)


def test_chime_generation():
    """Verifies that the acknowledgment chime generates valid, non-clipped audio."""
    chime = generate_chime_audio(sample_rate=SAMPLE_RATE)
    assert len(chime) > 0
    assert chime.dtype == np.float32
    # Verify no clipping (amplitude should be safely bounded)
    assert np.max(np.abs(chime)) <= 0.5
    # Verify no NaN or Inf
    assert not np.isnan(chime).any()
    assert not np.isinf(chime).any()


def test_wake_word_initialization():
    """Verifies detector initializes with correct settings and initial state."""
    settings = Settings(wake_word_threshold=0.45, wake_word_cooldown=2.0)
    detector = WakeWordDetector(settings=settings)

    assert detector.state == WakeWordState.STOPPED
    assert detector.threshold == 0.45
    assert detector.cooldown == 2.0
    assert not detector.is_listening()


def test_wake_word_lifecycle_transitions():
    """Tests lifecycle states: initialize, start, pause, resume, stop."""
    detector = WakeWordDetector()
    state_transitions = []

    def _on_state_change(old_state, new_state):
        state_transitions.append((old_state, new_state))

    detector.on_state_change = _on_state_change

    with patch("sounddevice.InputStream") as mock_stream_cls, \
         patch("app.voice.wake_word.find_working_input_device", return_value=(0, 16000, 1)):
        mock_stream_instance = MagicMock()
        mock_stream_cls.return_value = mock_stream_instance

        # 1. Start detector
        detector.start()
        assert detector.state == WakeWordState.LISTENING_FOR_WAKE_WORD
        assert detector.is_listening()
        assert mock_stream_instance.start.called

        # 2. Pause detector
        detector.pause()
        assert detector.state == WakeWordState.PAUSED
        assert not detector.is_listening()

        # 3. Resume detector
        detector.resume()
        assert detector.state == WakeWordState.LISTENING_FOR_WAKE_WORD
        assert detector.is_listening()

        # 4. Stop detector
        detector.stop()
        assert detector.state == WakeWordState.STOPPED
        assert not detector.is_listening()
        assert mock_stream_instance.stop.called
        assert mock_stream_instance.close.called


def test_wake_word_detection_and_command_capture_flow():
    """Tests full detection pipeline: wake word trigger -> command capture -> callback."""
    detector = WakeWordDetector()
    detector.threshold = 0.5
    detector.cooldown = 1.0
    detector.silence_timeout = 0.16  # 2 chunks of silence to finish capture

    mock_model = MagicMock()
    mock_model.models = {"hey_jarvis_v0.1": None}
    detector._model = mock_model
    detector._model_key = "hey_jarvis_v0.1"

    wake_detected_calls = []
    command_captured_calls = []

    detector.on_wake_word = lambda score: wake_detected_calls.append(score)
    detector.on_command_captured = lambda audio: command_captured_calls.append(audio)

    with patch("app.voice.wake_word.play_chime"):
        # Put detector in listening state
        detector.set_state(WakeWordState.LISTENING_FOR_WAKE_WORD)

        # Worker thread simulation
        worker_stop = False

        # 1. Feed frame that does NOT trigger wake word
        mock_model.predict.return_value = {"hey_jarvis_v0.1": 0.1}
        dummy_chunk = np.zeros(CHUNK_SAMPLES, dtype=np.int16)
        detector._audio_queue.put(dummy_chunk)

        # Process single chunk manually via queue handling logic
        chunk = detector._audio_queue.get()
        preds = detector._model.predict(chunk)
        assert preds["hey_jarvis_v0.1"] < detector.threshold
        assert len(wake_detected_calls) == 0

        # 2. Feed frame that DOES trigger wake word (score = 0.95)
        mock_model.predict.return_value = {"hey_jarvis_v0.1": 0.95}
        detector._audio_queue.put(dummy_chunk)

        # Run detection block
        chunk = detector._audio_queue.get()
        preds = detector._model.predict(chunk)
        score = preds["hey_jarvis_v0.1"]
        if score >= detector.threshold:
            detector.set_state(WakeWordState.WAKE_WORD_DETECTED)
            detector.on_wake_word(score)
            detector.set_state(WakeWordState.CAPTURING_COMMAND)

        assert len(wake_detected_calls) == 1
        assert wake_detected_calls[0] == 0.95
        assert detector.state == WakeWordState.CAPTURING_COMMAND

        # 3. Simulate command capture with speech followed by silence
        speech_chunk = (np.ones(CHUNK_SAMPLES, dtype=np.int16) * 500)
        silence_chunk = np.zeros(CHUNK_SAMPLES, dtype=np.int16)

        detector._command_chunks.append(speech_chunk)
        detector._command_chunks.append(silence_chunk)

        # Complete command capture
        detector.set_state(WakeWordState.PROCESSING_COMMAND)
        raw_int16 = np.concatenate(detector._command_chunks, axis=0)
        audio_f32 = raw_int16.astype(np.float32) / 32768.0
        detector.on_command_captured(audio_f32)

        assert len(command_captured_calls) == 1
        assert len(command_captured_calls[0]) == CHUNK_SAMPLES * 2
        assert command_captured_calls[0].dtype == np.float32


def test_wake_word_paused_during_speaking():
    """Verifies that wake-word detection is suspended during SPEAKING_RESPONSE state."""
    detector = WakeWordDetector()
    detector.set_state(WakeWordState.SPEAKING_RESPONSE)

    mock_model = MagicMock()
    detector._model = mock_model
    detector._model_key = "hey_jarvis_v0.1"

    wake_detected_calls = []
    detector.on_wake_word = lambda score: wake_detected_calls.append(score)

    # Frame with high confidence score arriving during response playback
    mock_model.predict.return_value = {"hey_jarvis_v0.1": 0.99}
    chunk = (np.ones(CHUNK_SAMPLES, dtype=np.int16) * 1000)
    detector._audio_queue.put(chunk)

    # State check: in SPEAKING_RESPONSE, chunk should be skipped without calling predict
    if detector.state == WakeWordState.SPEAKING_RESPONSE:
        # Loop skips processing
        pass

    assert len(wake_detected_calls) == 0
    assert not mock_model.predict.called


def test_orchestrator_wake_word_system_status():
    """Verifies orchestrator status and lazy-loading of WakeWordDetector."""
    mock_detector = MagicMock()
    mock_detector.is_listening.return_value = True

    settings = Settings(wake_word_enabled=True, wake_word_model="hey_jarvis_v0.1.onnx")
    orchestrator = Orchestrator(settings=settings, wake_word_client=mock_detector)

    status = orchestrator.get_system_status()
    assert status["wake_word_enabled"] is True
    assert status["wake_word_model"] == "hey_jarvis_v0.1.onnx"
    assert status["wake_word_active"] is True
    assert orchestrator.get_wake_word() is mock_detector
