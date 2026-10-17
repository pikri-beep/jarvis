"""Tests for Dynamic Execution, Anti-Hallucination Guard, and Universal Tool-Calling."""

import pytest
from unittest.mock import MagicMock
from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType, RouteResult
from app.core.todo_manager import TodoManager
from app.core.task_executor import AutonomousReActAgent, execute_registered_tool
from app.memory.database import Database
from app.ai.interpreter import ActionInterpreter, InterpreterPlan


def test_database_and_manager_clear_all_todos(tmp_path):
    db_file = tmp_path / "todos_test.db"
    db = Database(str(db_file))
    mgr = TodoManager(database=db)

    # Add 3 todos
    db.add_todo("Tugas 1")
    db.add_todo("Tugas 2")
    db.add_todo("Tugas 3")
    assert len(mgr.list_tasks(include_completed=True)) == 3

    # Clear all
    cleared = mgr.clear_all()
    assert cleared == 3
    assert len(mgr.list_tasks(include_completed=True)) == 0


def test_router_clear_all_todos():
    router = CommandRouter()
    queries = [
        "hapus semua todo",
        "hapus semua tugas",
        "kosongkan todo",
        "clear all todos",
        "delete all tasks",
    ]
    for q in queries:
        res = router.route(q)
        assert res.route_type == RouteType.FAST_COMMAND, f"Failed for '{q}'"
        assert res.action == "clear_all_todos", f"Action not clear_all_todos for '{q}'"


def test_fast_command_clear_all_todos_execution(tmp_path):
    from app.core.handlers.fast_command_handler import handle_fast_command
    db_file = tmp_path / "test_exec.db"
    db = Database(str(db_file))
    db.add_todo("Beli makan")
    db.add_todo("Bayar internet")

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
    route = RouteResult(route_type=RouteType.FAST_COMMAND, action="clear_all_todos")

    _, gen = handle_fast_command(orch, route, "hapus semua todo", "id", True)
    output = "".join(list(gen))
    assert "Semua 2 tugas dalam daftar todo Anda telah berhasil dihapus" in output
    assert len(db.get_todos()) == 0


def test_interpreter_plan_todo_clear_all():
    interp = ActionInterpreter()
    # Mock parse_and_validate_json
    raw_json = '{"type": "action", "intent": "todo", "action": "clear_all", "target": "all", "parameters": {}}'
    plan = interp.parse_and_validate_json(raw_json, "hapus semua todo", 10.0)
    assert plan.is_action is True
    assert plan.intent == "todo"
    assert plan.action == "clear_all"


def test_task_executor_clear_all_todos(tmp_path):
    from app.memory.database import Database
    # Test execute_registered_tool for clear_all_todos
    ok, msg = execute_registered_tool("clear_all_todos", language="id")
    assert ok is True
    assert "berhasil dihapus" in msg or "cleared" in msg
