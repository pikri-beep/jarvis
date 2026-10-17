"""Unit tests for Modern Hacker Terminal HUD tabs and widgets."""

import pytest
from PyQt6.QtWidgets import QApplication

from app.core.orchestrator import Orchestrator
from app.ui.main_window import JarvisMainWindow
from app.ui.tabs.terminal_console_tab import TerminalConsoleTab
from app.ui.tabs.terminal_janitor_tab import TerminalJanitorTab
from app.ui.tabs.terminal_proactive_tab import TerminalProactiveTab
from app.ui.tabs.terminal_todo_tab import TerminalTodoTab


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_terminal_console_tab(qapp):
    tab = TerminalConsoleTab()
    assert tab.input_edit is not None
    assert tab.btn_mic is not None

    submitted = []
    tab.command_submitted.connect(lambda cmd: submitted.append(cmd))

    tab.input_edit.setText("test command")
    tab.btn_send.click()
    assert submitted == ["test command"]
    assert tab.input_edit.text() == ""

    # Streaming token
    tab.start_assistant_message()
    tab.append_assistant_token("Hello ")
    tab.append_assistant_token("World!")
    tab.end_assistant_message()
    assert "Hello World!" in tab.log_area.toPlainText()


def test_terminal_todo_tab(qapp):
    tab = TerminalTodoTab()
    assert tab.input_todo is not None

    tab.input_todo.setText("Tugas otomatis testing")
    tab._on_add_todo()
    assert "Tugas otomatis testing" in tab.list_widget.item(0).text() or tab.list_widget.count() > 0


def test_terminal_janitor_tab(qapp):
    tab = TerminalJanitorTab()
    assert tab.combo_target.count() >= 2
    assert tab.btn_scan is not None
    assert tab.btn_clean is not None


def test_terminal_proactive_tab(qapp):
    tab = TerminalProactiveTab()
    assert tab.lbl_focus_time is not None
    tab.log_event("HEALTH", "Test health event")
    assert "Test health event" in tab.event_browser.toPlainText()


def test_main_window_terminal_hud_integration(qapp):
    orch = Orchestrator()
    orch.state.is_muted = True
    window = JarvisMainWindow(orchestrator=orch)

    # 4 tabs present
    assert window.tab_widget.count() == 4
    assert window.tab_widget.tabText(0) == ">_ CONSOLE"
    assert window.tab_widget.tabText(1) == "📝 TODO & NOTES"
    assert window.tab_widget.tabText(2) == "🧹 JANITOR"
    assert window.tab_widget.tabText(3) == "⚡ PROACTIVE STREAM"

    # Engine toggle
    initial_provider = window.current_engine_provider
    window._toggle_engine()
    new_provider = window.current_engine_provider
    assert initial_provider != new_provider
    window._toggle_engine()
    assert window.current_engine_provider == initial_provider

    window.close()
