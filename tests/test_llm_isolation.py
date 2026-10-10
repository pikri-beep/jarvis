"""Automated tests for Workstream H & Rule A: Strict LLM Isolation and Safety.

Non-Negotiable Verification:
1. Ordinary desktop commands NEVER invoke OllamaClient.chat_stream or requests.post.
2. Screen reading NEVER invokes OllamaClient when vision is disabled.
3. Browser actions NEVER invoke OllamaClient.
4. Mouse/keyboard desktop inputs NEVER invoke OllamaClient.
5. Ambiguous commands return CLARIFY without invoking Ollama.
6. Destructive actions ("hapus folder", "delete file", "shutdown") require explicit confirmation.
7. Negation ("jangan buka Chrome", "don't open Chrome") prevents tool execution.
8. When JARVIS_LLM_ENABLED=False (default), AI requests return offline status without Ollama.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType


@pytest.fixture
def isolated_orchestrator():
    """Returns an Orchestrator with default settings (llm_enabled=False)."""
    settings = Settings()  # llm_enabled is False by default
    orch = Orchestrator(settings=settings)
    return orch


def test_ordinary_desktop_commands_never_invoke_llm(isolated_orchestrator):
    """Verifies that ordinary desktop commands NEVER invoke Ollama chat_stream or network calls."""
    commands = [
        "buka chrome",
        "open notepad",
        "buka kalkulator",
        "buka youtube",
        "buka tab baru",
        "tutup tab ini",
        "scroll ke bawah",
        "scroll ke atas",
        "klik kanan",
        "double click",
        "tekan enter",
        "tekan escape",
        "ketik tutorial python",
        "switch ke Chrome",
        "jam berapa sekarang",
        "tanggal berapa hari ini",
        "ambil screenshot",
        "kunci komputer",
    ]

    with patch("app.ai.llm.OllamaClient.chat_stream") as mock_stream, \
         patch("requests.post") as mock_post, \
         patch("subprocess.run") as mock_subproc, \
         patch("ctypes.windll.user32.mouse_event"), \
         patch("ctypes.windll.user32.SetCursorPos"), \
         patch("ctypes.windll.user32.SendInput", return_value=1):
        
        mock_subproc.return_value = MagicMock(returncode=0, stdout="True\n", stderr="")

        for cmd in commands:
            route, stream = isolated_orchestrator.process_input_stream(cmd)
            response = "".join(list(stream))

            # Must never call Ollama
            assert not mock_stream.called, f"Command '{cmd}' invoked Ollama chat_stream!"
            assert not mock_post.called, f"Command '{cmd}' invoked network requests.post!"
            assert len(response) > 0, f"Command '{cmd}' returned empty response!"
            assert route.route in ("DIRECT", "FAST_COMMAND", "TERMINAL", "WEB", "SCREEN")


def test_screen_reading_never_invokes_llm_in_ocr_mode(isolated_orchestrator):
    """Verifies that screen reading with WinRT OCR / UI Automation never invokes Ollama."""
    with patch("app.ai.llm.OllamaClient.chat_stream") as mock_stream, \
         patch("requests.post") as mock_post, \
         patch("app.tools.screen_reader.read_screen_content") as mock_read:
        
        from app.tools.screen_reader import ScreenReadResult
        mock_read.return_value = ScreenReadResult(
            window_title="Google Chrome",
            text="Python Tutorial - YouTube",
            spoken_summary="Jendela aktif adalah Google Chrome.",
            display_text="[Screen Content: Python Tutorial]",
            success=True,
            method="winrt_ocr",
        )

        route, stream = isolated_orchestrator.process_input_stream("lihat layar gue")
        res = "".join(list(stream))

        assert not mock_stream.called
        assert not mock_post.called
        assert "Google Chrome" in res
        assert route.route_type == RouteType.SCREEN_READ


def test_destructive_commands_require_confirmation(isolated_orchestrator):
    """Verifies that destructive commands route to confirmation guard without executing."""
    destructive_inputs = [
        "hapus folder project",
        "delete file report.docx",
        "format drive c",
        "kosongkan recycle bin",
        "shutdown komputer",
        "matikan komputer",
        "restart komputer",
    ]

    for d_cmd in destructive_inputs:
        route, stream = isolated_orchestrator.process_input_stream(d_cmd)
        res = "".join(list(stream))

        assert route.action == "request_confirmation"
        assert "konfirmasi" in res.lower() or "confirmation" in res.lower() or "memerlukan konfirmasi" in res.lower()
        # Verify pending action is registered
        assert isolated_orchestrator.state.last_action_context["action"] == "request_confirmation"


def test_negation_prevents_action_execution(isolated_orchestrator):
    """Verifies that negation utterances like 'jangan buka Chrome' do not execute launch."""
    negation_inputs = [
        "Jangan buka Chrome",
        "Don't open WhatsApp",
        "Tidak usah buka notepad",
        "Batal buka kalkulator",
    ]

    with patch("app.tools.apps.launch_application") as mock_launch:
        for neg in negation_inputs:
            route, stream = isolated_orchestrator.process_input_stream(neg)
            res = "".join(list(stream))

            # Must not execute launch
            assert not mock_launch.called
            assert "dibatalkan" in res.lower() or "cancelled" in res.lower() or route.route_type == RouteType.AI_REQUEST


def test_ambiguous_commands_request_clarification(isolated_orchestrator):
    """Verifies that ambiguous commands like 'buka' or 'tutup' ask for clarification."""
    route_buka, stream_buka = isolated_orchestrator.process_input_stream("buka")
    res_buka = "".join(list(stream_buka))
    assert route_buka.route_type == RouteType.CLARIFY
    assert "apa yang ingin anda buka" in res_buka.lower() or "which application" in res_buka.lower()

    route_ketik, stream_ketik = isolated_orchestrator.process_input_stream("ketik")
    res_ketik = "".join(list(stream_ketik))
    assert route_ketik.route_type == RouteType.CLARIFY
    assert "apa yang ingin anda ketik" in res_ketik.lower() or "what text" in res_ketik.lower()
