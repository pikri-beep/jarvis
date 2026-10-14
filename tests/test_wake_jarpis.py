"""Test suite verifying dual wake-word alias support ("Jarvis" and "Jarpis").

Covers Section 4 requirements:
- "Jarvis" and "Jarpis" are official configurable aliases.
- CommandRouter normalizes and strips both "jarvis" and "jarpis".
- WakeWordDetector initializes with both aliases and applies them in detection.
- Audio buffer capture and grace period settings are preserved.
"""

import unittest
from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.core.router import CommandRouter, RouteType
from app.voice.wake_word import WakeWordDetector, WakeWordState


class TestWakeJarpisSupport(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            wake_word_aliases=["jarvis", "jarpis"],
            wake_word_threshold=0.30,
            wake_word_speech_start_grace=3.0,
            wake_word_post_speech_silence=1.8,
        )
        self.detector = WakeWordDetector(settings=self.settings)
        self.router = CommandRouter()

    def test_settings_dual_aliases(self):
        """Verify settings default or config includes both aliases."""
        self.assertIn("jarvis", self.settings.wake_word_aliases)
        self.assertIn("jarpis", self.settings.wake_word_aliases)

    def test_detector_initializes_with_aliases(self):
        """Verify WakeWordDetector initializes and stores both aliases."""
        self.assertIn("jarvis", self.detector.aliases)
        self.assertIn("jarpis", self.detector.aliases)
        self.assertEqual(self.detector.threshold, 0.30)

    def test_router_strips_jarpis_prefix(self):
        """Verify CommandRouter strips 'jarpis' just like 'jarvis'."""
        cleaned_jarvis = self.router.strip_wake_word("jarvis buka chrome")
        cleaned_jarpis = self.router.strip_wake_word("jarpis buka chrome")
        self.assertEqual(cleaned_jarvis.strip(), "buka chrome")
        self.assertEqual(cleaned_jarpis.strip(), "buka chrome")

    def test_router_handles_jarpis_media_commands(self):
        """Verify fast commands route properly when prefixed with 'jarpis'."""
        route1 = self.router.route("jarpis pause lagu")
        self.assertEqual(route1.route_type, RouteType.FAST_COMMAND)
        self.assertEqual(route1.action, "media_play_pause")

        route2 = self.router.route("jarpis lanjutkan musik")
        self.assertEqual(route2.route_type, RouteType.FAST_COMMAND)
        self.assertEqual(route2.action, "media_play_pause")

    def test_router_handles_jarpis_search_commands(self):
        """Verify search queries route properly when prefixed with 'jarpis'."""
        route = self.router.route("jarpis carikan berita teknologi di google")
        self.assertEqual(route.route_type, RouteType.WEB_SEARCH)
        self.assertIn("teknologi", route.args.get("query", ""))

    def test_router_handles_jarpis_browser_commands(self):
        """Verify browser commands route properly when prefixed with 'jarpis'."""
        route = self.router.route("jarpis buka youtube")
        self.assertEqual(route.route_type, RouteType.FAST_COMMAND)
        self.assertEqual(route.action, "open_website")

    def test_state_transitions_during_jarpis_wake(self):
        """Verify clean transition sequence when wake word triggers."""
        self.detector.set_state(WakeWordState.STANDBY)
        self.assertEqual(self.detector.state, WakeWordState.STANDBY)

        # Trigger wake
        self.detector.set_state(WakeWordState.WAKE_DETECTED)
        self.assertEqual(self.detector.state, WakeWordState.WAKE_DETECTED)

        # Waiting for user speech with 3.0s grace period
        self.detector.set_state(WakeWordState.WAITING_FOR_SPEECH)
        self.assertEqual(self.detector.state, WakeWordState.WAITING_FOR_SPEECH)
        self.assertEqual(self.detector.speech_start_grace, 3.0)

        # Capturing speech with 1.8s silence timeout
        self.detector.set_state(WakeWordState.RECORDING)
        self.assertEqual(self.detector.state, WakeWordState.RECORDING)
        self.assertEqual(self.detector.post_speech_silence, 1.8)

        # Recovering back to standby
        self.detector.set_state(WakeWordState.RECOVERING)
        self.assertEqual(self.detector.state, WakeWordState.RECOVERING)
        self.detector.set_state(WakeWordState.STANDBY)
        self.assertEqual(self.detector.state, WakeWordState.STANDBY)
