"""Unit tests for JARVIS Claude-Style Minimalist Desktop GUI."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from app.core.orchestrator import Orchestrator
from app.ui.chat_canvas import ChatCanvas, MessageBubble
from app.ui.dialogs import ConfirmationDialog, ProfileDialog
from app.ui.input_pill import InputPill
from app.ui.main_window import JarvisMainWindow
from scripts.create_desktop_shortcut import create_desktop_shortcut


@pytest.fixture(scope="session")
def qapp():
    """Provides a single QApplication instance for the test suite."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_confirmation_dialog_creation(qapp):
    """Verifies ConfirmationDialog instantiates and exposes expected buttons."""
    dialog = ConfirmationDialog(
        title="Test Dangerous Action",
        message="Are you sure you want to test this action?",
        details="Operation: rm -rf /test",
    )
    assert dialog.windowTitle() == "Test Dangerous Action"
    assert dialog.btn_cancel is not None
    assert dialog.btn_confirm is not None


def test_profile_dialog(qapp):
    """Verifies ProfileDialog displays user facts and preferences properly."""
    memories = {
        "user_name": "Alex",
        "honorific": "bos",
        "preferred_browser": "chrome",
    }
    dlg = ProfileDialog(memories=memories)
    assert dlg.windowTitle() == "Profil & Memori Pengguna"


def test_message_bubble_and_streaming(qapp):
    """Verifies MessageBubble supports creation and token appending."""
    bubble = MessageBubble("JARVIS", "Halo ", is_user=False)
    assert bubble.lbl_text.text() == "Halo "
    bubble.append_text("bos!")
    assert bubble.lbl_text.text() == "Halo bos!"

    user_bubble = MessageBubble("Anda", "Buka Chrome", is_user=True)
    assert user_bubble.lbl_text.text() == "Buka Chrome"


def test_chat_canvas(qapp):
    """Verifies ChatCanvas handles user and assistant messages, suggestions, and clear."""
    canvas = ChatCanvas()
    assert canvas.welcome_container is not None

    clicked = []
    canvas.suggestion_clicked.connect(lambda txt: clicked.append(txt))

    user_bubble = canvas.add_user_message("Halo Jarvis")
    assert user_bubble.lbl_text.text() == "Halo Jarvis"
    assert canvas.welcome_container is None

    asst_bubble = canvas.add_assistant_message("Halo bos")
    assert asst_bubble.lbl_text.text() == "Halo bos"

    canvas.clear_chat()
    assert canvas.welcome_container is not None


def test_input_pill(qapp):
    """Verifies InputPill text submission, mic state toggling, and audio level."""
    pill = InputPill()
    submitted = []
    pill.text_submitted.connect(lambda txt: submitted.append(txt))

    pill.set_text("Jalankan notepad")
    assert pill.btn_send.isEnabled() is True

    pill.btn_send.click()
    assert submitted == ["Jalankan notepad"]
    assert pill.text_edit.toPlainText() == ""

    # Test mic state
    pill.set_recording(True)
    assert pill._is_recording is True
    assert pill.btn_mic.text() == "🔴"

    pill.set_audio_level(0.75)
    assert pill.audio_bar.value() == 75

    pill.set_recording(False)
    assert pill._is_recording is False
    assert pill.btn_mic.text() == "🎙️"


def test_minimal_main_window_initialization(qapp):
    """Verifies JarvisMainWindow creates minimalist interface without multi-tabs."""
    orch = Orchestrator()
    window = JarvisMainWindow(orchestrator=orch)

    # Window title and essential minimalist widgets
    assert "JARVIS" in window.windowTitle()
    assert hasattr(window, "chat_canvas")
    assert hasattr(window, "input_pill")
    assert hasattr(window, "status_pill")
    assert "Siap" in window.status_pill.text()

    # Close cleanly
    window.close()


def test_minimal_main_window_submit_flow(qapp):
    """Verifies user submit initiates processing flow without freezing."""
    orch = Orchestrator()
    orch.state.is_muted = True  # Avoid Piper model loading in unit test
    window = JarvisMainWindow(orchestrator=orch)

    with patch.object(window.orchestrator, "process_input_stream") as mock_stream:
        mock_route = MagicMock()
        mock_route.name = "FAST_COMMAND"
        mock_stream.return_value = (mock_route, iter(["Membuka ", "Chrome, ", "bos."]))

        window._submit_prompt("Buka Chrome")
        assert window.current_worker is not None
        window.current_worker.wait(3000)
        qapp.processEvents()

        assert window.current_bubble is not None
        assert "Chrome" in window.current_bubble.lbl_text.text()

    window.close()


def test_desktop_shortcut_creation():
    """Verifies create_desktop_shortcut produces a valid .lnk file on Desktop."""
    shortcut_path = create_desktop_shortcut()
    assert shortcut_path.exists()
    assert shortcut_path.suffix.lower() == ".lnk"
    assert shortcut_path.stat().st_size > 0
