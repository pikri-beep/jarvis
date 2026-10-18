"""End-to-end integration tests for JARVIS Memory and Recollection System."""

import pytest
from unittest.mock import patch

from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.memory.database import Database
from app.memory.memory import MemoryManager


@pytest.fixture
def memory_test_env(tmp_path):
    """Sets up an isolated database and memory manager."""
    test_db_path = tmp_path / "test_memory_system.db"
    db = Database(db_path=test_db_path)
    mgr = MemoryManager(db=db)

    with patch("app.memory.memory.memory_manager", mgr):
        yield mgr


def test_memory_store_and_recall_flow(memory_test_env):
    """Tests storing facts, recalling, and listing via Orchestrator."""
    settings = Settings(llm_enabled=False, voice_enabled=False, tts_enabled=False)
    orch = Orchestrator(settings=settings)
    orch.memory = memory_test_env

    # 1. Store user name
    r1, g1 = orch.process_command("Ingat bahwa nama saya adalah Alex")
    out1 = "".join(list(g1))
    assert r1.action == "store_memory"
    assert "alex" in out1.lower()
    assert memory_test_env.recall_fact("nama") == "alex"

    # 2. Store food preference
    r2, g2 = orch.process_command("Ingat bahwa makanan kesukaan saya adalah soto ayam")
    out2 = "".join(list(g2))
    assert r2.action == "store_memory"
    assert "soto ayam" in out2.lower()

    # 3. Recall user name directly
    r3, g3 = orch.process_command("Siapa nama saya?")
    out3 = "".join(list(g3))
    assert r3.action == "recall_memories"
    assert "alex" in out3.lower()

    # 4. Show profile / list memories
    r4, g4 = orch.process_command("Apa yang kamu ingat tentang saya?")
    out4 = "".join(list(g4))
    assert r4.action == "show_profile"
    assert "alex" in out4.lower()
    assert "soto ayam" in out4.lower()

    # 5. Forget food preference with possessive phrasing
    r5, g5 = orch.process_command("Lupakan makanan kesukaan saya")
    out5 = "".join(list(g5))
    assert r5.action == "forget_memory"
    assert "dihapus" in out5.lower()
    assert memory_test_env.recall_fact("makanan kesukaan") is None

    # 6. Clear all memories
    r6, g6 = orch.process_command("Hapus semua ingatan")
    out6 = "".join(list(g6))
    assert r6.action == "forget_memory"
    assert "dibersihkan" in out6.lower()
    assert len(memory_test_env.recall_all()) == 0
