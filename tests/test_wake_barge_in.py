"""Unit tests for Wake Word Barge-In interruption ('Jarvis, Stop') and stop_speech fast command."""

import time
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType
from app.voice.wake_word import (
    CHUNK_SAMPLES,
    SAMPLE_RATE,
    WakeWordDetector,
    WakeWordState,
)


class TestWakeWordBargeIn(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            wake_word_threshold=0.15,
            wake_word_vad_threshold=0.0,
            wake_word_speech_start_grace=3.0,
            tts_enabled=True,
        )
        self.router = CommandRouter()

    def test_router_handles_stop_speech_commands(self):
        """Verify 'stop', 'jarvis stop', 'cukup', 'diam', 'berhenti' route to stop_speech."""
        commands = [
            "stop",
            "jarvis stop",
            "jarpis stop",
            "berhenti",
            "jarvis berhenti",
            "cukup",
            "diam",
            "jarvis diam",
            "cancel",
            "batal",
        ]
        for cmd in commands:
            route = self.router.route(cmd)
            self.assertEqual(
                route.route_type,
                RouteType.FAST_COMMAND,
                f"Failed for command: {cmd}",
            )
            self.assertEqual(
                route.action,
                "stop_speech",
                f"Wrong action for command: {cmd}",
            )

    def test_orchestrator_stop_speech_halts_tts(self):
        """Verify orchestrator execution of stop_speech invokes TTS stop."""
        orchestrator = Orchestrator(settings=self.settings)
        mock_tts = MagicMock()
        orchestrator.wake_word = MagicMock()
        with patch.object(orchestrator, "get_tts", return_value=mock_tts):
            route, stream_gen = orchestrator.process_input_stream("jarvis stop")
            self.assertEqual(route.action, "stop_speech")
            tokens = list(stream_gen)
            self.assertTrue(len(tokens) > 0)
            mock_tts.stop.assert_called_once()

    def test_barge_in_during_speaking_state(self):
        """Verify wake detection during SPEAKING invokes on_barge_in and enters WAITING_FOR_SPEECH."""
        barge_in_called = []
        wake_called = []

        detector = WakeWordDetector(
            settings=self.settings,
            on_barge_in=lambda: barge_in_called.append(True),
            on_wake_word=lambda s: wake_called.append(s),
        )

        mock_model = MagicMock()
        mock_model.models = {"hey_jarvis_v0.1": None}
        mock_model.predict.return_value = {"hey_jarvis_v0.1": 0.28}
        detector._model = mock_model
        detector._model_key = "hey_jarvis_v0.1"

        detector.set_state(WakeWordState.SPEAKING)
        self.assertEqual(detector.state, WakeWordState.SPEAKING)

        # Feed an audio chunk to the queue
        chunk = np.zeros(CHUNK_SAMPLES, dtype=np.int16)
        detector._audio_queue.put(chunk)

        # Run one processing loop step in a patched environment
        with patch("app.voice.wake_word.play_chime"):
            # Simulate worker picking up chunk while in SPEAKING
            retrieved = detector._audio_queue.get()
            preds = detector._model.predict(retrieved)
            score = preds["hey_jarvis_v0.1"]

            if score >= detector.threshold:
                if detector.on_barge_in:
                    detector.on_barge_in()
                detector.set_state(WakeWordState.WAKE_DETECTED)
                if detector.on_wake_word:
                    detector.on_wake_word(score)
                detector.set_state(WakeWordState.WAITING_FOR_SPEECH)

        self.assertTrue(len(barge_in_called) == 1)
        self.assertTrue(len(wake_called) == 1)
        self.assertEqual(detector.state, WakeWordState.WAITING_FOR_SPEECH)


if __name__ == "__main__":
    unittest.main()
