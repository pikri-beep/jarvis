"""Unit tests for Deep Personalization, Dynamic Honorifics, Tool Routing & Prompt Grounding."""

import pytest
from unittest.mock import patch, MagicMock

from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType
from app.memory.database import Database
from app.memory.memory import memory_manager, MemoryManager
from app.ai.prompts import get_system_prompt


@pytest.fixture
def isolated_env(tmp_path):
    """Sets up an isolated temporary database for personalization testing."""
    test_db = tmp_path / "test_personalization.db"
    db = Database(db_path=test_db)
    mgr = MemoryManager(db=db)
    
    with patch("app.memory.memory.memory_manager", mgr):
        yield mgr


def test_dynamic_honorific_default_and_custom(isolated_env):
    """Default honorific is 'sir'; once learned as 'bos', it dynamically updates."""
    assert isolated_env.get_honorific() == "sir"

    isolated_env.db.set_memory("honorific", "bos", category="identity", description="Panggilan kesukaan pengguna")
    assert isolated_env.get_honorific() == "bos"


def test_preferred_tool_resolution_in_router(isolated_env):
    """Router dynamically resolves 'buka browser' to user's preferred_browser."""
    router = CommandRouter()

    # Before setting, 'buka browser' defaults to chrome
    res1 = router.route("buka browser")
    assert res1.route_type == RouteType.FAST_COMMAND
    assert res1.action == "open_application"
    assert res1.args.get("target") == "chrome"

    # Set preferred browser to Brave
    isolated_env.db.set_memory("preferred_browser", "Brave", category="preference")
    res2 = router.route("buka browser")
    assert res2.args.get("target") == "brave"

    # Set preferred editor to VS Code
    isolated_env.db.set_memory("preferred_code_editor", "code", category="preference")
    res3 = router.route("buka editor")
    assert res3.args.get("target") == "code"


def test_profile_card_formatting(isolated_env):
    """Profile card lists stored user items categorized cleanly."""
    isolated_env.db.set_memory("user_name", "Alex", category="identity", description="Nama pengguna")
    isolated_env.db.set_memory("honorific", "bos", category="identity", description="Panggilan kesukaan pengguna")
    isolated_env.db.set_memory("preferred_browser", "Brave", category="preference", description="Peramban web utama")

    card = isolated_env.format_profile_card(language="id")
    assert "PROFIL & KEBIASAAN PENGGUNA (BOS)" in card
    assert "Alex" in card
    assert "Brave" in card
    assert "Identitas" in card


def test_system_prompt_injects_user_profile(isolated_env):
    """Prompt grounding automatically injects [USER PROFILE, PREFERENCES & RULES]."""
    isolated_env.db.set_memory("user_name", "David", category="identity", description="Nama pengguna")
    isolated_env.db.set_memory("honorific", "bos", category="identity", description="Panggilan kesukaan pengguna")
    isolated_env.db.set_memory("code_language_priority", "Python", category="rule", description="Prioritas kode")

    prompt = get_system_prompt(language="id")
    assert "[USER PROFILE, PREFERENCES & RULES]:" in prompt
    assert "Preferred Honorific: 'bos'" in prompt
    assert "Python" in prompt


def test_orchestrator_learn_and_conflict_flow(isolated_env):
    """End-to-end test: /learn command triggers learning and handles conflicts via confirmation."""
    settings = Settings(llm_enabled=False, voice_enabled=False, tts_enabled=False)
    orch = Orchestrator(settings=settings)

    # 1. First learn command
    route1, gen1 = orch.process_input_stream("/learn namaku Alex, panggil aku bos, perambanku Brave")
    reply1 = "".join(list(gen1))
    assert route1.action == "learn_memory"
    assert "bos" in reply1.lower()
    assert "mempelajari" in reply1.lower()

    # Verify saved
    assert (isolated_env.db.get_memory("user_name") or "").lower() == "alex"
    assert isolated_env.get_honorific() == "bos"
    assert (isolated_env.db.get_memory("preferred_browser") or "").lower() == "brave"

    # 2. Conflicting learn command
    route2, gen2 = orch.process_input_stream("/learn perambanku Firefox")
    reply2 = "".join(list(gen2))
    assert "Sebelumnya" in reply2
    assert "Brave" in reply2
    assert orch.state.pending_action is not None
    assert orch.state.pending_action.action == "confirm_memory_conflict"

    # 3. Confirm with 'Ya'
    route3, gen3 = orch.process_input_stream("ya")
    reply3 = "".join(list(gen3))
    assert "diperbarui menjadi 'firefox'" in reply3.lower()
    assert (isolated_env.db.get_memory("preferred_browser") or "").lower() == "firefox"
    assert orch.state.pending_action is None
