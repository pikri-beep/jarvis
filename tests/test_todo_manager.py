"""Unit tests for TodoManager and User Todos subsystem."""

import pytest
from pathlib import Path
from app.memory.database import Database
from app.core.todo_manager import TodoManager


@pytest.fixture
def temp_db(tmp_path: Path):
    db_file = tmp_path / "test_todos.db"
    return Database(db_path=db_file)


def test_todo_crud_operations(temp_db):
    """Verifies adding, retrieving, toggling, and deleting tasks."""
    mgr = TodoManager(database=temp_db)

    # 1. Add Task
    ok, msg, todo_id = mgr.add_task("Kirim email revisi jam 3 sore")
    assert ok is True
    assert todo_id > 0
    assert "revisi" in msg

    # 2. List Tasks
    tasks = mgr.list_tasks(include_completed=True)
    assert len(tasks) == 1
    assert tasks[0]["id"] == todo_id
    assert tasks[0]["is_completed"] == 0
    assert "jam 3 sore" in tasks[0]["due_date"].lower()

    # 3. Toggle Complete
    toggled = mgr.toggle_task(todo_id)
    assert toggled is True
    tasks_after = mgr.list_tasks(include_completed=True)
    assert tasks_after[0]["is_completed"] == 1

    # 4. Clear Completed
    cleared = mgr.clear_completed()
    assert cleared == 1
    assert len(mgr.list_tasks(include_completed=True)) == 0


def test_natural_language_prefixes(temp_db):
    """Verifies parsing removes 'catat todo:', 'ingatkan saya untuk', etc."""
    mgr = TodoManager(database=temp_db)

    ok1, _, id1 = mgr.add_task("tolong catat: beli kopi dan susu")
    assert ok1 is True
    tasks = mgr.list_tasks()
    assert tasks[0]["title"] == "beli kopi dan susu"

    ok2, _, id2 = mgr.add_task("ingatkan saya untuk olahraga besok pagi")
    assert ok2 is True
    tasks2 = mgr.list_tasks()
    # Most recent first
    latest = [t for t in tasks2 if t["id"] == id2][0]
    assert "olahraga" in latest["title"]
    assert "besok" in latest["due_date"]


def test_orchestrator_todo_routing():
    """Verifies that Orchestrator parses and handles 'catat todo: ...' commands end-to-end."""
    from app.core.orchestrator import Orchestrator
    orch = Orchestrator()
    route, stream = orch.process_input_stream("catat todo: bayar internet")
    assert route.action == "add_todo"
    reply = "".join(list(stream))
    assert "telah dicatat" in reply or "Noted" in reply

