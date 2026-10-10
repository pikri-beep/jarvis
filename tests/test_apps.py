"""Unit tests for application registry, launching, aliases, and process control."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.core.orchestrator import Orchestrator
from app.tools.apps import (
    close_application,
    launch_application,
    normalize_app_name,
    registry,
    is_protocol_registered,
)


def test_normalize_app_name_aliases():
    # Chrome and speech-to-text variants
    assert normalize_app_name("chrome") == "chrome"
    assert normalize_app_name("Chrome") == "chrome"
    assert normalize_app_name("Google Chrome") == "chrome"
    assert normalize_app_name("krom") == "chrome"
    assert normalize_app_name("kromya") == "chrome"
    assert normalize_app_name("kromer") == "chrome"
    assert normalize_app_name("gugel krom") == "chrome"
    assert normalize_app_name("browser") == "chrome"
    assert normalize_app_name("peramban") == "chrome"

    # Edge variants
    assert normalize_app_name("edge") == "edge"
    assert normalize_app_name("ms edge") == "edge"
    assert normalize_app_name("microsoft edge") == "edge"

    # Notepad variants
    assert normalize_app_name("notepad") == "notepad"
    assert normalize_app_name("notpet") == "notepad"
    assert normalize_app_name("catatan") == "notepad"
    assert normalize_app_name("buku catatan") == "notepad"

    # Calculator variants
    assert normalize_app_name("calculator") == "calculator"
    assert normalize_app_name("calc") == "calculator"
    assert normalize_app_name("kalkulator") == "calculator"
    assert normalize_app_name("hitung") == "calculator"

    # File Explorer variants
    assert normalize_app_name("explorer") == "explorer"
    assert normalize_app_name("file explorer") == "explorer"
    assert normalize_app_name("berkas") == "explorer"
    assert normalize_app_name("penjelajah file") == "explorer"

    # Settings variants
    assert normalize_app_name("settings") == "settings"
    assert normalize_app_name("pengaturan") == "settings"
    assert normalize_app_name("setelan") == "settings"

    # WhatsApp variants
    assert normalize_app_name("whatsapp") == "whatsapp"
    assert normalize_app_name("wa") == "whatsapp"
    assert normalize_app_name("watsap") == "whatsapp"
    assert normalize_app_name("whats app") == "whatsapp"

    # Preserves unknown application names
    assert normalize_app_name("custom_tool") == "custom_tool"
    assert normalize_app_name("") == ""


def test_launch_application_executable_success():
    with patch("app.tools.apps.find_application_executable") as mock_find, \
         patch("subprocess.Popen") as mock_popen:
        mock_find.return_value = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.poll.return_value = None  # Process is running
        mock_popen.return_value = mock_proc

        success, name, msg = launch_application("kromya")
        assert success is True
        assert "Chrome" in name
        assert "Berhasil" in msg
        mock_popen.assert_called_once()
        # Verify no shell=True
        call_kwargs = mock_popen.call_args[1]
        assert call_kwargs.get("shell") is not True


def test_launch_application_protocol_success():
    with patch("app.tools.apps.find_application_executable", return_value=None), \
         patch("app.tools.apps.is_protocol_registered", return_value=True), \
         patch("os.startfile") as mock_startfile:

        # Test Windows Settings protocol launch
        success, name, msg = launch_application("pengaturan")
        assert success is True
        assert name == "Settings"
        mock_startfile.assert_called_with("ms-settings:")

        # Test WhatsApp protocol launch
        success_wa, name_wa, msg_wa = launch_application("whatsapp")
        assert success_wa is True
        assert name_wa == "WhatsApp"
        mock_startfile.assert_called_with("whatsapp:")


def test_whatsapp_security_no_unauthorized_actions():
    """Verify WhatsApp is only opened and never sends automated text or messages."""
    with patch("app.tools.apps.find_application_executable", return_value=None), \
         patch("app.tools.apps.is_protocol_registered", return_value=True), \
         patch("os.startfile") as mock_startfile:

        launch_application("whatsapp")
        # Ensure only the bare protocol is used, with no query strings or payload
        called_target = mock_startfile.call_args[0][0]
        assert called_target == "whatsapp:"
        assert "?" not in called_target
        assert "send" not in called_target


def test_launch_application_not_found():
    with patch("app.tools.apps.find_application_executable", return_value=None), \
         patch("app.tools.apps.is_protocol_registered", return_value=False):

        success, name, msg = launch_application("non_existent_app_xyz")
        assert success is False
        assert "tidak ditemukan" in msg


def test_launch_application_process_failure():
    with patch("app.tools.apps.find_application_executable") as mock_find, \
         patch("subprocess.Popen") as mock_popen:
        mock_find.return_value = Path(r"C:\Windows\notepad.exe")
        mock_proc = MagicMock()
        mock_proc.pid = 5678
        mock_proc.poll.return_value = 1  # Process crashed immediately
        mock_proc.returncode = 1
        mock_popen.return_value = mock_proc

        success, name, msg = launch_application("notepad")
        assert success is False
        assert "gagal dimulai" in msg


def test_close_application():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        success, name, msg = close_application("google chrome")
        assert success is True
        assert "Chrome" in name
        assert "Berhasil menutup" in msg

        mock_run.return_value = MagicMock(returncode=1, stderr="ERROR: The process was not found.")
        success2, name2, msg2 = close_application("notepad")
        assert success2 is False
        assert "tidak sedang berjalan" in msg2

        # Explorer protection
        success_exp, name_exp, msg_exp = close_application("explorer")
        assert success_exp is False
        assert "mengganggu" in msg_exp


def test_orchestrator_open_chrome_verified_success():
    orchestrator = Orchestrator()
    with patch("app.tools.apps.launch_application") as mock_launch:
        mock_launch.return_value = (True, "Google Chrome", "Berhasil")

        # Test Indonesian command with STT misspelling "kromya"
        route_id, gen_id = orchestrator.process_input_stream("Tolong buka kromya")
        reply_id = "".join(list(gen_id))
        assert "Membuka Google Chrome, sir." in reply_id
        mock_launch.assert_called_with("chrome")

        # Test English command
        route_en, gen_en = orchestrator.process_input_stream("Open Chrome")
        reply_en = "".join(list(gen_en))
        assert "Opening Google Chrome, sir." in reply_en


def test_orchestrator_open_whatsapp_success():
    orchestrator = Orchestrator()
    with patch("app.tools.apps.launch_application") as mock_launch:
        mock_launch.return_value = (True, "WhatsApp", "Berhasil")

        # Turn 1: Sensitive app triggers confirmation prompt
        route_prompt, gen_prompt = orchestrator.process_input_stream("Tolong buka WhatsApp")
        reply_prompt = "".join(list(gen_prompt))
        assert "Membuka WhatsApp dapat mengakses data pesan pribadi Anda" in reply_prompt
        assert "Apakah Anda yakin" in reply_prompt
        mock_launch.assert_not_called()
        assert orchestrator.state.pending_action is not None
        assert orchestrator.state.pending_action.target == "whatsapp"

        # Turn 2: Affirmative confirmation executes the action
        route_confirm, gen_confirm = orchestrator.process_input_stream("Ya, buka")
        reply_confirm = "".join(list(gen_confirm))
        assert "Membuka WhatsApp, sir." in reply_confirm
        mock_launch.assert_called_with("whatsapp")
        assert orchestrator.state.pending_action is None


def test_orchestrator_open_whatsapp_cancellation():
    orchestrator = Orchestrator()
    with patch("app.tools.apps.launch_application") as mock_launch:
        # Turn 1: Sensitive app triggers confirmation prompt
        route_prompt, gen_prompt = orchestrator.process_input_stream("Open WhatsApp")
        reply_prompt = "".join(list(gen_prompt))
        assert "access your personal messages" in reply_prompt or "Membuka WhatsApp" in reply_prompt
        mock_launch.assert_not_called()

        # Turn 2: User cancels action
        route_cancel, gen_cancel = orchestrator.process_input_stream("No, cancel")
        reply_cancel = "".join(list(gen_cancel))
        assert "cancelled" in reply_cancel.lower() or "dibatalkan" in reply_cancel.lower()
        mock_launch.assert_not_called()
        assert orchestrator.state.pending_action is None


def test_orchestrator_open_chrome_verified_failure():
    orchestrator = Orchestrator()
    with patch("app.tools.apps.launch_application") as mock_launch:
        mock_launch.return_value = (False, "Google Chrome", "Aplikasi tidak ditemukan di sistem.")

        route_id, gen_id = orchestrator.process_input_stream("Tolong buka Chrome")
        reply_id = "".join(list(gen_id))
        assert "tidak dapat membuka Google Chrome" in reply_id
        assert "tidak ditemukan" in reply_id
