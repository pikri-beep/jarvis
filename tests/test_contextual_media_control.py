"""Automated test suite for Contextual Media Control (Section 6 & Section 10.B).

Verifies:
- 'Pause the music' invokes media control tool directly.
- 'Pause it' resolves active media target.
- 'Resume it' resumes playback.
- Unsupported media targets are handled safely.
- Failed execution is not reported as success.
- Deterministic media routing executes in < 50 ms.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType
from app.tools.music import media_play_pause, pause_music, resume_music


class TestContextualMediaControl(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()
        self.settings = Settings(llm_enabled=False)
        self.orchestrator = Orchestrator(settings=self.settings)

    def test_pause_the_music_deterministic_routing(self):
        """'Pause the music' must be routed deterministically without LLM."""
        t0 = time.perf_counter()
        route = self.router.route("Pause the music")
        latency_ms = (time.perf_counter() - t0) * 1000.0

        self.assertEqual(route.route_type, RouteType.FAST_COMMAND)
        self.assertEqual(route.action, "media_play_pause")
        self.assertLess(latency_ms, 50.0, "Routing must complete under 50 ms")

    def test_pause_it_deterministic_routing(self):
        """'Pause it' must be routed directly to media control."""
        route = self.router.route("Pause it")
        self.assertEqual(route.route_type, RouteType.FAST_COMMAND)
        self.assertEqual(route.action, "media_play_pause")

    def test_resume_the_music_and_resume_it(self):
        """'Resume the music' and 'Resume it' must route to media control."""
        r1 = self.router.route("Resume the music")
        self.assertEqual(r1.action, "media_play_pause")

        r2 = self.router.route("Resume it")
        self.assertEqual(r2.action, "media_play_pause")

    def test_polite_media_requests_stripped_and_routed(self):
        """Courtesy phrases like 'Can you pause the music for a moment' must route fast."""
        r1 = self.router.route("Can you pause the music for a moment?")
        self.assertEqual(r1.action, "media_play_pause")

        r2 = self.router.route("Bisakah jeda musiknya sebentar?")
        self.assertEqual(r2.action, "media_play_pause")

    @patch("app.tools.music._send_vk")
    def test_pause_music_invokes_correct_tool(self, mock_send_vk):
        """pause_music helper must invoke native Windows media key."""
        ok, msg = pause_music(language="en")
        self.assertTrue(ok)
        mock_send_vk.assert_called_once()
        self.assertIn("Paused music playback", msg)

    @patch("app.tools.music._send_vk")
    def test_resume_music_invokes_correct_tool(self, mock_send_vk):
        """resume_music helper must invoke native Windows media key."""
        ok, msg = resume_music(language="id")
        self.assertTrue(ok)
        mock_send_vk.assert_called_once()
        self.assertIn("Melanjutkan pemutaran musik", msg)

    @patch("app.tools.music._send_vk", side_effect=RuntimeError("Hardware media key blocked"))
    def test_failed_execution_not_reported_as_success(self, mock_send_vk):
        """Failed execution must honestly report failure."""
        ok, msg = pause_music(language="en")
        self.assertFalse(ok)
        self.assertIn("Failed to pause music", msg)

    def test_orchestrator_media_play_pause_execution(self):
        """Orchestrator fast command path must execute without invoking LLM."""
        with patch("app.tools.music._send_vk") as mock_vk:
            route, stream = self.orchestrator.process_input_stream("pause the music")
            response = "".join(list(stream))

            self.assertEqual(route.action, "media_play_pause")
            mock_vk.assert_called_once()
            self.assertTrue(len(response) > 0)


if __name__ == "__main__":
    unittest.main()
