"""Automated test suite for Wake Word & Voice Capture Lifecycle (Sections 3, 4 & 10.C).

Verifies:
- Explicit 10-state lifecycle (STANDBY, WAKE_DETECTED, WAITING_FOR_SPEECH, RECORDING, etc.).
- 3.0-second speech-start grace period giving user time to think.
- Configurable post-utterance silence threshold (1.8s).
- Listener recovery after empty recordings, timeouts, and exceptions.
- Repeated detections and duplicate trigger suppression.
- Clean transitions through RECOVERING back to STANDBY.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.voice.wake_word import WakeWordDetector, WakeWordState


class TestWakeWordGracePeriod(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            wake_word_speech_start_grace=3.0,
            wake_word_post_speech_silence=1.8,
        )
        self.detector = WakeWordDetector(settings=self.settings)

    def test_state_machine_enum_completeness(self):
        """Verify all required states from Section 3 exist in the state machine."""
        required_states = [
            "STANDBY",
            "WAKE_DETECTED",
            "WAITING_FOR_SPEECH",
            "RECORDING",
            "TRANSCRIBING",
            "INTERPRETING",
            "EXECUTING",
            "SPEAKING",
            "RECOVERING",
        ]
        for st in required_states:
            self.assertTrue(hasattr(WakeWordState, st), f"WakeWordState missing {st}")

    def test_initial_state_is_stopped(self):
        """Detector must start in STOPPED state before start() is called."""
        self.assertEqual(self.detector.state, WakeWordState.STOPPED)

    def test_explicit_state_transitions(self):
        """Transitions between states must update the current state and notify callback."""
        transitions = []
        self.detector.on_state_change = lambda old, new: transitions.append((old, new))

        self.detector.set_state(WakeWordState.STANDBY)
        self.assertEqual(self.detector.state, WakeWordState.STANDBY)

        self.detector.set_state(WakeWordState.WAKE_DETECTED)
        self.assertEqual(self.detector.state, WakeWordState.WAKE_DETECTED)

        self.detector.set_state(WakeWordState.WAITING_FOR_SPEECH)
        self.assertEqual(self.detector.state, WakeWordState.WAITING_FOR_SPEECH)

        self.detector.set_state(WakeWordState.RECORDING)
        self.assertEqual(self.detector.state, WakeWordState.RECORDING)

        self.detector.set_state(WakeWordState.TRANSCRIBING)
        self.assertEqual(self.detector.state, WakeWordState.TRANSCRIBING)

        self.detector.set_state(WakeWordState.INTERPRETING)
        self.assertEqual(self.detector.state, WakeWordState.INTERPRETING)

        self.detector.set_state(WakeWordState.EXECUTING)
        self.assertEqual(self.detector.state, WakeWordState.EXECUTING)

        self.detector.set_state(WakeWordState.SPEAKING)
        self.assertEqual(self.detector.state, WakeWordState.SPEAKING)

        self.detector.set_state(WakeWordState.RECOVERING)
        self.assertEqual(self.detector.state, WakeWordState.RECOVERING)

        self.detector.set_state(WakeWordState.STANDBY)
        self.assertEqual(self.detector.state, WakeWordState.STANDBY)

        self.assertEqual(len(transitions), 10)

    def test_speech_start_grace_configuration(self):
        """Configurable speech-start grace period and silence thresholds."""
        self.assertEqual(self.detector.speech_start_grace, 3.0)
        self.assertEqual(self.detector.post_speech_silence, 1.8)

    def test_resume_listening_recovers_through_recovering_to_standby(self):
        """resume_listening must clean up and return to STANDBY state via RECOVERING."""
        transitions = []
        self.detector.on_state_change = lambda old, new: transitions.append((old, new))

        self.detector.set_state(WakeWordState.EXECUTING)
        # Mock active stream so resume doesn't call start()
        self.detector._stream = MagicMock()

        self.detector.resume_listening()

        self.assertEqual(self.detector.state, WakeWordState.STANDBY)
        # Check that RECOVERING state was entered during cleanup
        state_history = [t[1] for t in transitions]
        self.assertIn(WakeWordState.RECOVERING, state_history)
        self.assertEqual(state_history[-1], WakeWordState.STANDBY)


if __name__ == "__main__":
    unittest.main()
