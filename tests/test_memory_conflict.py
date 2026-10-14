"""Unit tests for Memory Conflict Detection & Confirmation Resolution."""

import pytest
from app.memory.database import Database
from app.memory.memory import MemoryManager
from app.memory.schemas import MemoryConflict, MemoryItem


@pytest.fixture
def temp_memory_manager(tmp_path):
    """Provides a fresh isolated MemoryManager instance using temporary SQLite."""
    db_file = tmp_path / "test_conflict.db"
    db = Database(db_path=db_file)
    mgr = MemoryManager(db=db)
    return mgr


def test_conflict_detection_on_different_value(temp_memory_manager):
    """Saving an existing key with a new distinct value must generate a conflict."""
    # Seed initial memory
    temp_memory_manager.db.set_memory("preferred_browser", "Brave", category="preference", description="Peramban web utama")

    # Learn conflicting update
    text = "peramban favoritku Firefox"
    res = temp_memory_manager.learn_from_text(text, auto_confirm=False, language="id")

    assert res.has_conflicts is True
    assert len(res.conflicts) == 1
    conflict = res.conflicts[0]
    assert conflict.item.key == "preferred_browser"
    assert conflict.item.value == "Firefox"
    assert conflict.existing_value == "Brave"
    assert "Sebelumnya" in conflict.prompt_question
    assert "Brave" in conflict.prompt_question


def test_conflict_resolution_approved(temp_memory_manager):
    """When conflict resolution is approved by user, new value is committed."""
    temp_memory_manager.db.set_memory("preferred_browser", "Brave", category="preference", description="Peramban web utama")

    item = MemoryItem(key="preferred_browser", value="Firefox", category="preference", description="Peramban web utama")
    conflict = MemoryConflict(item=item, existing_value="Brave", existing_description="Peramban web utama")

    success, msg = temp_memory_manager.apply_conflict_resolution(conflict, approved=True, language="id")
    assert success is True
    assert "diperbarui menjadi 'Firefox'" in msg
    assert temp_memory_manager.db.get_memory("preferred_browser") == "Firefox"


def test_conflict_resolution_rejected(temp_memory_manager):
    """When conflict resolution is rejected by user, old value is preserved."""
    temp_memory_manager.db.set_memory("preferred_browser", "Brave", category="preference", description="Peramban web utama")

    item = MemoryItem(key="preferred_browser", value="Firefox", category="preference", description="Peramban web utama")
    conflict = MemoryConflict(item=item, existing_value="Brave", existing_description="Peramban web utama")

    success, msg = temp_memory_manager.apply_conflict_resolution(conflict, approved=False, language="id")
    assert success is False
    assert "tetap menggunakan 'Brave'" in msg
    assert temp_memory_manager.db.get_memory("preferred_browser") == "Brave"


def test_no_conflict_on_same_value(temp_memory_manager):
    """If the value is identical (case-insensitive), no conflict should be generated."""
    temp_memory_manager.db.set_memory("user_name", "Alex", category="identity")
    text = "namaku Alex"
    res = temp_memory_manager.learn_from_text(text, auto_confirm=False)
    assert res.has_conflicts is False
    assert len(res.learned) >= 1
