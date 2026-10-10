"""Unit and integration tests for website launching, URL mapping, and deterministic browser routing."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType
from app.tools.browser import (
    is_known_website,
    launch_website,
    normalize_website_target,
    website_registry,
)


def test_website_registry_mappings_and_urls():
    # YouTube mapping
    assert is_known_website("youtube")
    assert is_known_website("YouTube")
    assert is_known_website("yutup")
    assert is_known_website("yt")
    assert is_known_website("situs youtube")
    canonical_yt, display_yt, url_yt = normalize_website_target("youtube")
    assert canonical_yt == "youtube"
    assert display_yt == "YouTube"
    assert url_yt == "https://www.youtube.com"

    # Google mapping
    assert is_known_website("google")
    assert is_known_website("gugel")
    canonical_g, display_g, url_g = normalize_website_target("gugel")
    assert canonical_g == "google"
    assert display_g == "Google"
    assert url_g == "https://www.google.com"

    # Gmail mapping
    assert is_known_website("gmail")
    assert is_known_website("email google")
    canonical_gm, display_gm, url_gm = normalize_website_target("gmail")
    assert canonical_gm == "gmail"
    assert display_gm == "Gmail"
    assert url_gm == "https://mail.google.com"

    # ChatGPT mapping
    assert is_known_website("chatgpt")
    assert is_known_website("chat gpt")
    canonical_gpt, display_gpt, url_gpt = normalize_website_target("chatgpt")
    assert canonical_gpt == "chatgpt"
    assert display_gpt == "ChatGPT"
    assert url_gpt == "https://chatgpt.com"

    # Direct URL and domain detection
    assert is_known_website("github.com")
    assert is_known_website("https://news.ycombinator.com")
    assert not is_known_website("non_existent_random_token_xyz")


def test_launch_website_chrome_success():
    """Verify Chrome is prioritized and launched with explicit HTTPS URL."""
    with patch("app.tools.browser.find_application_executable") as mock_find, \
         patch("subprocess.Popen") as mock_popen:
        mock_find.return_value = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        mock_proc = MagicMock()
        mock_proc.pid = 4321
        mock_proc.poll.return_value = None  # Process spawned and running
        mock_popen.return_value = mock_proc

        success, name, url, msg = launch_website("youtube")
        assert success is True
        assert name == "YouTube"
        assert url == "https://www.youtube.com"
        assert "Google Chrome" in msg

        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert str(mock_find.return_value) in args[0]
        assert args[1] == "https://www.youtube.com"
        # Confirm no dangerous shell=True
        assert mock_popen.call_args[1].get("shell") is not True


def test_launch_website_fallback_to_system_browser():
    """Verify clean fallback to system browser when Chrome is not available."""
    with patch("app.tools.browser.find_application_executable", return_value=None), \
         patch("os.startfile") as mock_startfile:
        success, name, url, msg = launch_website("chat gpt")
        assert success is True
        assert name == "ChatGPT"
        assert url == "https://chatgpt.com"
        mock_startfile.assert_called_once_with("https://chatgpt.com")


def test_launch_website_failure_honest_reporting():
    """Verify failure reporting when both Chrome and system browser fail."""
    with patch("app.tools.browser.find_application_executable", return_value=None), \
         patch("os.startfile", side_effect=OSError("System browser protocol failure")), \
         patch("webbrowser.open", return_value=False):
        success, name, url, msg = launch_website("gmail")
        assert success is False
        assert name == "Gmail"
        assert "Gagal membuka" in msg

    # Empty target test
    success_empty, _, _, msg_empty = launch_website("")
    assert success_empty is False
    assert "tidak boleh kosong" in msg_empty


def test_router_website_fast_commands():
    router = CommandRouter()

    # Indonesian website commands
    r_yt_id = router.route("Buka Youtube")
    assert r_yt_id.route_type == RouteType.FAST_COMMAND
    assert r_yt_id.action == "open_website"
    assert r_yt_id.args.get("target") == "youtube"

    r_yt_polite = router.route("Tolong buka YouTube")
    assert r_yt_polite.route_type == RouteType.FAST_COMMAND
    assert r_yt_polite.action == "open_website"
    assert r_yt_polite.args.get("target") == "youtube"

    r_google = router.route("Buka Google")
    assert r_google.route_type == RouteType.FAST_COMMAND
    assert r_google.action == "open_website"
    assert r_google.args.get("target") == "google"

    r_gmail = router.route("Buka Gmail")
    assert r_gmail.route_type == RouteType.FAST_COMMAND
    assert r_gmail.action == "open_website"
    assert r_gmail.args.get("target") == "gmail"

    r_chatgpt = router.route("Buka ChatGPT")
    assert r_chatgpt.route_type == RouteType.FAST_COMMAND
    assert r_chatgpt.action == "open_website"
    assert r_chatgpt.args.get("target") == "chatgpt"

    # English website commands
    r_yt_en = router.route("Open YouTube")
    assert r_yt_en.route_type == RouteType.FAST_COMMAND
    assert r_yt_en.action == "open_website"
    assert r_yt_en.args.get("target") == "youtube"

    r_gmail_en = router.route("Launch Gmail")
    assert r_gmail_en.route_type == RouteType.FAST_COMMAND
    assert r_gmail_en.action == "open_website"
    assert r_gmail_en.args.get("target") == "gmail"


def test_router_preserves_conversational_inquiry_for_websites():
    router = CommandRouter()

    # Questions and definitions must route to AI_REQUEST
    r_q1 = router.route("Apa itu YouTube?")
    assert r_q1.route_type == RouteType.AI_REQUEST

    r_q2 = router.route("What is YouTube?")
    assert r_q2.route_type == RouteType.AI_REQUEST

    r_how = router.route("Bagaimana cara membuka YouTube?")
    assert r_how.route_type == RouteType.AI_REQUEST

    r_neg = router.route("Jangan buka YouTube")
    assert r_neg.route_type == RouteType.AI_REQUEST

    r_why = router.route("Kenapa YouTube lemot?")
    assert r_why.route_type == RouteType.AI_REQUEST


def test_orchestrator_open_website_bilingual_flow():
    orchestrator = Orchestrator()
    with patch("app.tools.browser.launch_website") as mock_launch:
        mock_launch.return_value = (True, "YouTube", "https://www.youtube.com", "Berhasil")

        # Indonesian turn
        route_id, gen_id = orchestrator.process_input_stream("Buka Youtube")
        assert route_id.route_type == RouteType.FAST_COMMAND
        out_id = "".join(list(gen_id))
        assert "Membuka YouTube, sir." in out_id
        mock_launch.assert_called_with("youtube")
        assert orchestrator.state.get_last_action_target() == "chrome"

        # English turn
        route_en, gen_en = orchestrator.process_input_stream("Open YouTube")
        assert route_en.route_type == RouteType.FAST_COMMAND
        out_en = "".join(list(gen_en))
        assert "Opening YouTube, sir." in out_en


def test_orchestrator_open_website_failure_reporting():
    orchestrator = Orchestrator()
    with patch("app.tools.browser.launch_website") as mock_launch:
        mock_launch.return_value = (False, "YouTube", "https://www.youtube.com", "Peramban gagal dibuka.")

        route, gen = orchestrator.process_input_stream("Buka Youtube")
        out = "".join(list(gen))
        assert "tidak dapat membuka YouTube" in out
        assert "Peramban gagal dibuka" in out
