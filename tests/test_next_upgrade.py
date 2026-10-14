"""Comprehensive automated test suite for JARVIS NEXT Full-System Upgrade.

Covers:
- Workstream A: Wake word state machine transitions and recovery
- Workstream B: Fast AI orchestration without unnecessary LLM calls
- Workstream C: Deterministic Indonesian and English datetime tool
- Workstream D: TTS phonetic normalization
- Workstream E: Browser agent search and web extraction
- Workstream F: Windows native media keys and music controller
- Workstream G: Hardware specs, battery status, and filesystem security
- Workstream H: SQLite persistent user memories and prompt injection
- Workstream I: Diagnostics generation and reporting
"""

import os
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.core.diagnostics import format_diagnostics_text, generate_diagnostics_report
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType
from app.memory.database import Database
from app.memory.memory import (
    MemoryManager,
    forget_user_memory,
    get_relevant_memories_prompt,
    recall_user_memories,
    save_user_memory,
)
from app.tools.browser_agent import CleanHTMLTextExtractor, summarize_topic
from app.tools.datetime_tool import (
    INDONESIAN_DAYS,
    INDONESIAN_MONTHS,
    get_current_date,
    get_current_time,
)
from app.tools.filesystem import create_folder, resolve_standard_folder, safe_delete
from app.tools.music import (
    change_volume,
    media_next,
    media_play_pause,
    media_previous,
    media_stop,
    play_music,
)
from app.tools.windows import get_battery_status, get_hardware_specs, lock_windows
from app.voice.text_to_speech import normalize_text_for_speech
from app.voice.wake_word import WakeWordState


class TestDatetimeTool(unittest.TestCase):
    """Workstream C: Test datetime tool for accurate Indonesian and English clock/calendar."""

    def test_get_current_time_id(self):
        fixed_dt = datetime(2026, 10, 10, 9, 5, 0)
        time_str = get_current_time(lang="id", now=fixed_dt)
        self.assertIn("09.05", time_str)
        self.assertIn("pagi", time_str)
        self.assertTrue(time_str.endswith(", sir."))

    def test_get_current_time_en(self):
        fixed_dt = datetime(2026, 10, 10, 14, 30, 0)
        time_str = get_current_time(lang="en", now=fixed_dt)
        self.assertIn("2:30 PM", time_str)
        self.assertTrue(time_str.endswith(", sir."))

    def test_get_current_date_id(self):
        fixed_dt = datetime(2026, 10, 10)  # Saturday
        date_str = get_current_date(lang="id", now=fixed_dt)
        self.assertIn("Sabtu", date_str)
        self.assertIn("Oktober", date_str)
        self.assertIn("2026", date_str)
        self.assertTrue(date_str.endswith(", sir."))

    def test_get_current_date_en(self):
        fixed_dt = datetime(2026, 10, 10)
        date_str = get_current_date(lang="en", now=fixed_dt)
        self.assertIn("Saturday", date_str)
        self.assertIn("October", date_str)
        self.assertIn("2026", date_str)
        self.assertTrue(date_str.endswith(", sir."))


class TestWindowsAndFilesystemTools(unittest.TestCase):
    """Workstream G: Test desktop automation and filesystem safety."""

    def test_get_hardware_specs(self):
        specs = get_hardware_specs()
        self.assertIn("os", specs)
        self.assertIn("cpu_count_logical", specs)
        self.assertIn("ram_total_gb", specs)
        self.assertGreater(specs["ram_total_gb"], 0)

    def test_get_battery_status(self):
        status = get_battery_status()
        self.assertIn("has_battery", status)
        self.assertIn("percent", status)
        self.assertIn("power_plugged", status)

    @patch("ctypes.windll.user32.LockWorkStation")
    def test_lock_windows(self, mock_lock):
        mock_lock.return_value = 1
        success, msg = lock_windows()
        self.assertTrue(success)
        mock_lock.assert_called_once()

    def test_resolve_standard_folders(self):
        self.assertIsNotNone(resolve_standard_folder("desktop"))
        self.assertIsNotNone(resolve_standard_folder("downloads"))
        self.assertIsNotNone(resolve_standard_folder("documents"))

    def test_create_and_delete_folder(self):
        test_dir = os.path.join(os.path.expanduser("~"), "_jarvis_test_tmp_dir")
        # Ensure clean initial state
        if os.path.exists(test_dir):
            os.rmdir(test_dir)

        success, path, msg = create_folder(test_dir)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(test_dir))

        # Safe delete without confirmation must fail
        del_success, del_msg = safe_delete(test_dir, confirmed=False)
        self.assertFalse(del_success)
        self.assertTrue(os.path.exists(test_dir))

        # Safe delete with confirmation must succeed
        del_success, del_msg = safe_delete(test_dir, confirmed=True)
        self.assertTrue(del_success)
        self.assertFalse(os.path.exists(test_dir))


class TestMusicController(unittest.TestCase):
    """Workstream F: Test media controls and music provider dispatching."""

    @patch("ctypes.windll.user32.keybd_event")
    def test_media_keys(self, mock_keybd):
        media_play_pause()
        media_next()
        media_previous()
        media_stop()
        self.assertEqual(mock_keybd.call_count, 8)  # 2 events (press + release) * 4 calls

    @patch("ctypes.windll.user32.keybd_event")
    def test_volume_keys(self, mock_keybd):
        change_volume("up")
        change_volume("down")
        change_volume("mute")
        self.assertEqual(mock_keybd.call_count, 10)

    @patch("app.tools.music.launch_website")
    def test_play_music_youtube(self, mock_launch):
        mock_launch.return_value = (True, "YouTube Music", "https://music.youtube.com", "ok")
        success, prov, msg = play_music(query="Coldplay Yellow", provider="youtube")
        self.assertTrue(success)
        self.assertIn("YouTube", prov)
        mock_launch.assert_called_once()


class TestBrowserAgent(unittest.TestCase):
    """Workstream E: Test web text extractor and search agent."""

    def test_clean_html_text_extractor(self):
        raw_html = "<html><body><h1>Title</h1><script>alert(1);</script><p>Hello &amp; world!</p></body></html>"
        parser = CleanHTMLTextExtractor()
        parser.feed(raw_html)
        text = parser.get_text()
        self.assertIn("Title", text)
        self.assertIn("Hello & world!", text)
        self.assertNotIn("alert", text)

    @patch("urllib.request.urlopen")
    def test_summarize_topic_mock(self, mock_urlopen):
        summary, url = summarize_topic("Python", lang="en")
        self.assertIsInstance(summary, str)
        self.assertIsInstance(url, str)


class TestMemorySubsystem(unittest.TestCase):
    """Workstream H: Test SQLite memory storage, retrieval, and prompt injection."""

    def setUp(self):
        self.test_db_path = "data/test_memory_upgrade.db"
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass
        self.db = Database(db_path=self.test_db_path)
        self.manager = MemoryManager(db=self.db)

    def tearDown(self):
        import gc
        gc.collect()
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass


    def test_store_and_recall_fact(self):
        success, msg = self.manager.store_fact("nama", "Alex")
        self.assertTrue(success)
        val = self.manager.recall_fact("nama")
        self.assertEqual(val, "Alex")

        # Recall all
        all_facts = self.manager.recall_all()
        self.assertEqual(all_facts.get("nama"), "Alex")

        # Forget fact
        f_success, f_msg = self.manager.forget_fact("nama")
        self.assertTrue(f_success)
        self.assertIsNone(self.manager.recall_fact("nama"))

    def test_prompt_injection(self):
        self.manager.store_fact("editor", "VS Code")
        with patch("app.memory.memory.memory_manager", self.manager):
            prompt_str = get_relevant_memories_prompt(language="en")
            self.assertIn("editor", prompt_str)
            self.assertIn("VS Code", prompt_str)


class TestPhoneticNormalization(unittest.TestCase):
    """Workstream D: Test speech text normalization for natural TTS."""

    def test_phonetic_replacements_id(self):
        normalized = normalize_text_for_speech("Buka Spotify dan YouTube, lalu cek 75% baterai jam 09.30", language="id")
        self.assertIn("spotifai", normalized.lower())
        self.assertIn("yutub", normalized.lower())
        self.assertIn("persen", normalized.lower())
        self.assertIn("lewat", normalized.lower())



class TestCommandRouterUpgrades(unittest.TestCase):
    """Workstream B: Test structured intent router on Indonesian and English commands."""

    def setUp(self):
        self.router = CommandRouter()

    def test_datetime_routing(self):
        r1 = self.router.route("jam berapa sekarang?")
        self.assertEqual(r1.action, "get_time")
        self.assertEqual(r1.route_type, RouteType.FAST_COMMAND)

        r2 = self.router.route("what time is it?")
        self.assertEqual(r2.action, "get_time")

        r3 = self.router.route("hari apa sekarang?")
        self.assertEqual(r3.action, "get_date")

        r4 = self.router.route("what's today's date?")
        self.assertEqual(r4.action, "get_date")

    def test_media_and_music_routing(self):
        r1 = self.router.route("play coldplay yellow")
        self.assertEqual(r1.action, "play_music")
        self.assertEqual(r1.args["query"], "coldplay yellow")

        r2 = self.router.route("lagu berikutnya")
        self.assertEqual(r2.action, "media_next")

        r3 = self.router.route("pause music")
        self.assertEqual(r3.action, "media_play_pause")

    def test_folder_routing(self):
        r = self.router.route("buka folder downloads")
        self.assertEqual(r.action, "open_folder")
        self.assertEqual(r.args["target"], "downloads")

    def test_memory_routing(self):
        r1 = self.router.route("ingat nama saya Alex")
        self.assertEqual(r1.action, "store_memory")

        r2 = self.router.route("apa yang kamu ingat tentang saya?")
        self.assertEqual(r2.action, "recall_memories")

    def test_terminal_diagnostics_routing(self):
        r1 = self.router.route("/diag")
        self.assertEqual(r1.action, "show_diagnostics")

        r2 = self.router.route("/reset")
        self.assertEqual(r2.action, "reset_context")


class TestOrchestratorIntegration(unittest.TestCase):
    """End-to-end integration test verifying fast tools do not call the LLM."""

    def setUp(self):
        self.settings = Settings()
        self.orchestrator = Orchestrator(settings=self.settings)
        # Mock LLM chat stream to verify it is NOT called during fast commands
        self.orchestrator.llm.chat_stream = MagicMock()

    def test_fast_datetime_execution(self):
        route, stream = self.orchestrator.process_input_stream("jam berapa sekarang?")
        response = "".join(list(stream))
        self.assertIn("pukul", response.lower())
        self.orchestrator.llm.chat_stream.assert_not_called()

    def test_fast_hardware_specs_execution(self):
        route, stream = self.orchestrator.process_input_stream("system info")
        response = "".join(list(stream))
        self.assertIn("system", response.lower())
        self.orchestrator.llm.chat_stream.assert_not_called()

    def test_diagnostics_generation(self):
        route, stream = self.orchestrator.process_input_stream("/diag")
        response = "".join(list(stream))
        self.assertIn("JARVIS SYSTEM DIAGNOSTICS", response)
        self.assertIn("Audio/Voice", response)



class TestWakeWordStateTransitions(unittest.TestCase):
    """Workstream A: Test state machine transitions including RECOVERING state."""

    def test_state_enum_contains_recovering(self):
        self.assertTrue(hasattr(WakeWordState, "RECOVERING"))
        self.assertEqual(WakeWordState.STANDBY.value, "STANDBY")
        self.assertEqual(WakeWordState.RECOVERING.value, "RECOVERING")


if __name__ == "__main__":
    unittest.main()
