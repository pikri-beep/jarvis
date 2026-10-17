"""Unit tests verifying user-reported fixes:
1. Esc / stop speech shortcut & stop command.
2. Song titles containing 'jangan' (e.g. 'play lagu jangan pergi') not being cancelled.
3. System info command ('Cek info sistem') routing deterministically and 'Iya' affirmation.
4. Todo natural time parsing ('jam 14.20 beli makanan') and proactive due reminder loop.
5. Search query prefix/suffix cleaning ('search band naif di google') and ordinal source follow-up ('sumber 2').
6. ReAct internal chain-of-thought sanitization.
"""

import pytest
from unittest.mock import MagicMock
from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType
from app.core.todo_manager import TodoManager
from app.core.task_executor import AutonomousReActAgent
from app.memory.database import Database
from app.core.proactive_agent import ProactiveAgent


def test_song_title_with_jangan_not_negated():
    router = CommandRouter()
    res = router.route("play lagu jangan pergi")
    assert res.route_type == RouteType.FAST_COMMAND
    assert res.action == "play_music"
    assert res.args.get("query") == "jangan pergi"


def test_system_info_deterministic_routing():
    router = CommandRouter()
    queries = [
        "Cek info sistem",
        "cek info sistem",
        "info sistem",
        "spesifikasi sistem",
        "cek spesifikasi",
        "cek spek",
        "spek laptop",
        "system info",
    ]
    for q in queries:
        res = router.route(q)
        assert res.route_type == RouteType.FAST_COMMAND, f"Failed on {q}"
        assert res.action == "system_info", f"Action mismatch on {q}"


def test_affirmative_iya_in_confirmation_handler():
    from app.core.handlers.confirmation_handler import _AFFIRMATIVES
    assert "iya" in _AFFIRMATIVES
    assert "ya" in _AFFIRMATIVES
    assert "betul" in _AFFIRMATIVES
    assert "yep" in _AFFIRMATIVES


def test_stop_speech_commands():
    router = CommandRouter()
    commands = [
        "stop bicara",
        "berhenti ngomong",
        "diam",
        "cukup",
        "stop talking",
    ]
    for cmd in commands:
        res = router.route(cmd)
        assert res.route_type == RouteType.FAST_COMMAND, f"Failed on {cmd}"
        assert res.action == "stop_speech", f"Action mismatch on {cmd}"


def test_search_query_cleaning():
    router = CommandRouter()
    # 1. Trailing google search
    res1 = router.route("search band naif di google")
    assert res1.route_type == RouteType.WEB_SEARCH
    assert res1.action == "search_web"
    assert res1.args.get("query") == "band naif"
    assert res1.args.get("open_browser") is True

    # 2. English prefix
    res2 = router.route("search band naif")
    assert res2.route_type == RouteType.WEB_SEARCH
    assert res2.args.get("query") == "band naif"


def test_search_source_ordinal_followup():
    router = CommandRouter()
    # "buka sumber 1"
    res1 = router.route("buka sumber 1")
    assert res1.route_type == RouteType.FAST_COMMAND
    assert res1.action == "open_search_source"
    assert res1.args.get("index") == 1

    # "sumber 2" without verb
    res2 = router.route("sumber 2")
    assert res2.route_type == RouteType.FAST_COMMAND
    assert res2.action == "open_search_source"
    assert res2.args.get("index") == 2

    # "nomor 3"
    res3 = router.route("nomor 3")
    assert res3.route_type == RouteType.FAST_COMMAND
    assert res3.action == "open_search_source"
    assert res3.args.get("index") == 3


def test_todo_time_parsing_and_title_cleaning(tmp_path):
    db_file = tmp_path / "test_todos.db"
    db = Database(db_path=db_file)
    mgr = TodoManager(database=db)

    # User scenario: 'Catat todo: jam 14.20 beli makanan'
    ok, msg, tid = mgr.add_task("Catat todo: jam 14.20 beli makanan")
    assert ok is True
    assert "beli makanan" in msg
    assert "14:20" in msg

    todos = db.get_todos(include_completed=False)
    assert len(todos) == 1
    assert todos[0]["title"] == "beli makanan"
    assert todos[0]["due_date"] == "14:20"


def test_proactive_due_todo_reminder(tmp_path):
    import datetime
    db_file = tmp_path / "test_proactive_todos.db"
    db = Database(db_path=db_file)
    mgr = TodoManager(database=db)

    # Current time
    now = datetime.datetime.now()
    cur_time_str = f"{now.hour:02d}:{now.minute:02d}"

    # Add task due right now
    ok, _, tid = mgr.add_task(f"beli makan siang jam {cur_time_str}")
    assert ok is True

    # Check proactive agent detects it
    settings = Settings(proactive_enabled=True)
    agent = ProactiveAgent(settings=settings)
    # Mock orchestrator memory db
    class MockOrchestrator:
        class MockMemory:
            pass
        class MockState:
            is_processing = False
            pending_action = None
            conversation_language = "id"
        memory = MockMemory()
        memory.db = db
        state = MockState()
        wake_word = None
        tts = None
    agent.orchestrator = MockOrchestrator()

    event = agent.check_context()
    assert event is not None
    assert event.category == "todo_reminder"
    assert "beli makan siang" in event.display_message
    assert "beli makan siang" in event.spoken_message

    # Verify task was marked as reminded so it doesn't trigger again
    event2 = agent.check_context()
    assert event2 is None or event2.category != "todo_reminder"


def test_react_output_parser_sanitizes_thoughts():
    agent = AutonomousReActAgent()
    # Scenario: LLM outputs numbered thoughts and fails to output JSON
    raw_llm = (
        "Thought 3: The user wants to check the system information. I need to find a way to get the system information without encountering a syntax error.\n"
        "Action 3: execute_powershell({\"command\": \"Get-ComputerInfo\"})"
    )
    thought, action, action_input, final_answer = agent.parse_react_output(raw_llm)
    assert action == "execute_powershell"
    assert "Thought 3" not in (final_answer or "")


def test_audio_queue_immediate_stop():
    from app.voice.text_to_speech import AudioPlaybackQueue
    import numpy as np

    q = AudioPlaybackQueue()
    q._queue.put((np.zeros(100, dtype=np.int16), 16000))
    q._queue.put((np.zeros(100, dtype=np.int16), 16000))

    q.stop()
    assert q._stop_event.is_set()
    assert q._queue.empty()
    assert q.is_playing() is False


def test_clean_text_for_speech_strips_sumber_terkait():
    from app.voice.text_to_speech import clean_text_for_speech

    raw_text = (
        "Membuka pencarian Google untuk 'band naif' di browser, sir.\n\n"
        "Sumber Terkait:\n"
        "1. [The Lantis Rayakan Nostalgia](https://news.google.com/1) (eventguide.id)\n"
        "2. [The Lantis Hadirkan Versi Baru](https://news.google.com/2) (medcom.id)"
    )

    cleaned = clean_text_for_speech(raw_text, language="id")
    assert "Membuka pencarian" in cleaned
    assert "Sumber Terkait" not in cleaned
    assert "The Lantis" not in cleaned
    assert "eventguide.id" not in cleaned


def test_navigation_source_routing():
    router = CommandRouter()

    res1 = router.route("tolong ke sumber pertama")
    assert res1.route_type == RouteType.FAST_COMMAND
    assert res1.action == "open_search_source"
    assert res1.args.get("index") == 1

    res2 = router.route("ke sumber 1")
    assert res2.route_type == RouteType.FAST_COMMAND
    assert res2.action == "open_search_source"
    assert res2.args.get("index") == 1

    res3 = router.route("menuju sumber kedua")
    assert res3.route_type == RouteType.FAST_COMMAND
    assert res3.action == "open_search_source"
    assert res3.args.get("index") == 2

    res4 = router.route("sumber 3")
    assert res4.route_type == RouteType.FAST_COMMAND
    assert res4.action == "open_search_source"
    assert res4.args.get("index") == 3


def test_is_meta_reasoning_filter():
    from app.core.handlers.ai_handler import is_meta_reasoning

    assert is_meta_reasoning("The user is looking for the first result of 'sumber 3'") is True
    assert is_meta_reasoning("The user wants to open chrome") is True
    assert is_meta_reasoning("User is looking for something") is True
    assert is_meta_reasoning("Tentu sir, saya akan membantu Anda.") is False
    assert is_meta_reasoning("Membuka sumber pertama di browser, sir.") is False


def test_cheatsheet_routing_and_content():
    from app.core.handlers.terminal_handler import handle_terminal_command
    router = CommandRouter()

    res1 = router.route("/cheat")
    assert res1.route_type == RouteType.TERMINAL_COMMAND
    assert res1.action == "cheatsheet"

    res2 = router.route("cheatsheet")
    assert res2.route_type == RouteType.TERMINAL_COMMAND
    assert res2.action == "cheatsheet"

    class MockOrchestrator:
        state = MagicMock()
    
    _, gen = handle_terminal_command(MockOrchestrator(), res1, "/cheat", "id", True)
    output = "".join(list(gen))
    assert "JARVIS // QUICK CHEATSHEET" in output
    assert "WEB & BROWSING" in output
    assert "MULTIMEDIA & AUDIO" in output
    assert "TODO & PROACTIVE REMINDERS" in output
    assert "KONTROL APLIKASI & WINDOWS" in output
    assert "EMERGENCY STOP" in output


def test_cheatsheet_silent_tts():
    from app.core.handlers.terminal_handler import _get_jarvis_cheatsheet
    from app.voice.text_to_speech import clean_text_for_speech

    cheatsheet_text = _get_jarvis_cheatsheet()
    cleaned = clean_text_for_speech(cheatsheet_text, language="id")
    # Must be completely empty string so TTS never produces audio
    assert cleaned == ""


def test_list_todos_routing():
    router = CommandRouter()
    queries = [
        "daftar tugas",
        "daftar todo",
        "lihat tugas",
        "cek todo",
        "ada tugas apa",
        "apa saja tugas saya",
        "show todos",
        "task list",
        "/todo",
        "todo",
    ]
    for q in queries:
        res = router.route(q)
        assert res.route_type == RouteType.FAST_COMMAND, f"Failed for '{q}'"
        assert res.action == "list_todos", f"Action not list_todos for '{q}'"


def test_complete_and_clear_todos_routing():
    router = CommandRouter()
    res1 = router.route("selesaikan tugas 1")
    assert res1.route_type == RouteType.FAST_COMMAND
    assert res1.action == "complete_todo"
    assert res1.args.get("task_number") == 1

    res2 = router.route("hapus todo selesai")
    assert res2.route_type == RouteType.FAST_COMMAND
    assert res2.action == "clear_completed_todos"


def test_list_todos_execution_empty_and_populated(tmp_path):
    from app.core.handlers.fast_command_handler import handle_fast_command
    from app.core.router import RouteResult
    from app.memory.database import Database

    db_file = tmp_path / "test_todos.db"
    db = Database(str(db_file))

    class MockState:
        def __init__(self):
            self.history = []
        def add_turn(self, u, a):
            self.history.append((u, a))

    class MockMemory:
        def __init__(self, db):
            self.db = db

    class MockOrchestrator:
        def __init__(self, db):
            self.state = MockState()
            self.memory = MockMemory(db)

    orch = MockOrchestrator(db)
    route = RouteResult(route_type=RouteType.FAST_COMMAND, action="list_todos")

    # 1. Empty state
    _, gen_empty = handle_fast_command(orch, route, "daftar tugas", "id", True)
    out_empty = "".join(list(gen_empty))
    assert "Belum ada tugas aktif" in out_empty

    # 2. Add item and check populated state
    db.add_todo(title="Beli makanan", due_date="14:20")
    _, gen_pop = handle_fast_command(orch, route, "daftar tugas", "id", True)
    out_pop = "".join(list(gen_pop))
    assert "📋 **Daftar Tugas Aktif:**" in out_pop
    assert "1. [ ] Beli makanan *(Waktu: 14:20)*" in out_pop


def test_react_agent_loop_detection():
    from app.core.task_executor import AutonomousReActAgent
    from unittest.mock import MagicMock

    mock_llm = MagicMock()
    # LLM keeps returning the same Action for open_website
    mock_llm.chat.return_value = (
        'Thought: Buka instagram lagi\nAction: open_website\nAction Input: {"url": "https://instagram.com"}'
    )

    agent = AutonomousReActAgent(llm=mock_llm, max_iterations=4)
    # Mock execute_registered_tool to track calls
    with MagicMock() as mock_exec:
        import app.core.task_executor as te
        orig_exec = te.execute_registered_tool
        call_count = [0]
        def fake_exec(*args, **kwargs):
            call_count[0] += 1
            return True, "Opened instagram"
        te.execute_registered_tool = fake_exec
        try:
            res = agent.run("daftar tugas", language="id")
            # Loop detection must break early and NOT call the tool 4 times!
            assert call_count[0] == 1  # Executed once, second duplicate blocked, then broken out!
            assert res.success is True
        finally:
            te.execute_registered_tool = orig_exec



