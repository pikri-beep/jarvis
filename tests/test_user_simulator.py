"""Unit and Integration Tests for Simulated User Agent module."""

import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from tests.user_simulator.audio_injector import AudioStreamInjector
from tests.user_simulator.persona_engine import GroqUserPersonaEngine, PersonaConfig, TurnPlan
from tests.user_simulator.scenarios import get_all_scenarios, get_scenario
from tests.user_simulator.verifier import SystemStateVerifier, VerificationResult
from tests.user_simulator.voice_synth import EdgeTTSVoiceSynthesizer


class TestAudioStreamInjector(unittest.TestCase):
    def test_injector_slicing_and_queue(self):
        """Verify PCM array is sliced into 1280-sample chunks and queued."""
        mock_detector = MagicMock()
        mock_detector._audio_queue = MagicMock()

        injector = AudioStreamInjector(wake_detector=mock_detector)
        # Create 2560 samples (exactly 2 chunks of 1280)
        pcm = np.zeros(2560, dtype=np.int16)

        chunks_sent = []
        success = injector.inject_pcm(
            pcm,
            real_time=False,
            on_chunk_sent=lambda cur, tot: chunks_sent.append((cur, tot)),
        )

        self.assertTrue(success)
        self.assertEqual(len(chunks_sent), 2)
        self.assertEqual(mock_detector._audio_queue.put.call_count, 2)

    def test_hook_tts_capture(self):
        """Verify TTS capture hook properly records spoken sentences."""
        mock_tts = MagicMock()
        mock_tts.speak = MagicMock()
        mock_orchestrator = MagicMock()
        mock_orchestrator.get_tts.return_value = mock_tts

        injector = AudioStreamInjector()
        injector.hook_tts_capture(mock_orchestrator)

        # Trigger hooked speak
        mock_tts.speak("Opening Chrome, sir.")
        captured = injector.get_latest_jarvis_speech()

        self.assertEqual(captured, "Opening Chrome, sir.")
        # Subsequent call should return empty (cleared)
        self.assertEqual(injector.get_latest_jarvis_speech(), "")


class TestPersonaEngine(unittest.TestCase):
    def test_fallback_planner(self):
        """Verify smart fallback planner generates turn steps when no Groq client exists."""
        config = PersonaConfig(name="Tester", goal="Run tests", max_turns=3)
        engine = GroqUserPersonaEngine(api_key="", config=config)
        engine.client = None  # Force offline fallback test

        plan1 = engine.plan_next_turn(
            turn_number=1,
            dialogue_history=[],
            last_jarvis_speech="",
            scenario_fallback_steps=["Hey Jarvis, open Notepad", "Hey Jarvis, close Notepad"],
        )
        self.assertEqual(plan1.spoken_text, "Hey Jarvis, open Notepad")
        self.assertFalse(plan1.is_goal_achieved)

        plan2 = engine.plan_next_turn(
            turn_number=2,
            dialogue_history=[{"user": "Hey Jarvis, open Notepad", "jarvis": "Opening Notepad"}],
            last_jarvis_speech="Opening Notepad",
            scenario_fallback_steps=["Hey Jarvis, open Notepad", "Hey Jarvis, close Notepad"],
        )
        self.assertEqual(plan2.spoken_text, "Hey Jarvis, close Notepad")
        self.assertTrue(plan2.is_goal_achieved)

    def test_confirmation_handling(self):
        """Verify confirmation request from JARVIS automatically triggers 'Yes, please proceed'."""
        engine = GroqUserPersonaEngine(api_key="", config=PersonaConfig())
        engine.client = None  # Force offline fallback test
        plan = engine.plan_next_turn(
            turn_number=2,
            dialogue_history=[],
            last_jarvis_speech="That will delete the folder. Are you sure you want to continue?",
        )
        self.assertEqual(plan.intent_type, "confirmation")
        self.assertIn("proceed", plan.spoken_text.lower())


class TestSystemStateVerifier(unittest.TestCase):
    def setUp(self):
        self.verifier = SystemStateVerifier()

    def test_safety_confirmation_check(self):
        """Verify safety check detects warning / confirmation queries."""
        self.assertTrue(self.verifier.check_safety_confirmation_asked("Are you sure you want to proceed?"))
        self.assertTrue(self.verifier.check_safety_confirmation_asked("Apakah anda yakin ingin menghapus?"))
        self.assertFalse(self.verifier.check_safety_confirmation_asked("Opening Chrome now, sir."))

    def test_response_relevance_check(self):
        """Verify keyword matching in assistant replies."""
        reply = "Opening Google Chrome, sir."
        self.assertTrue(self.verifier.check_response_relevance(reply, ["chrome", "opening"]))
        self.assertFalse(self.verifier.check_response_relevance(reply, ["spotify", "music"]))

    @patch("psutil.process_iter")
    def test_process_running_check(self, mock_iter):
        """Verify process running lookup."""
        mock_proc = MagicMock()
        mock_proc.info = {"name": "chrome.exe"}
        mock_iter.return_value = [mock_proc]

        self.assertTrue(self.verifier.check_process_running("chrome"))
        self.assertFalse(self.verifier.check_process_running("notepad"))


class TestScenariosRegistry(unittest.TestCase):
    def test_all_scenarios_available(self):
        """Verify standard scenarios SC-01 through SC-06 exist."""
        scenarios = get_all_scenarios()
        self.assertGreaterEqual(len(scenarios), 6)

        sc01 = get_scenario("SC-01")
        self.assertIsNotNone(sc01)
        self.assertEqual(sc01.id, "SC-01")

        sc04 = get_scenario("SC-04")
        self.assertIsNotNone(sc04)
        self.assertEqual(sc04.persona.language, "id")


if __name__ == "__main__":
    unittest.main()
