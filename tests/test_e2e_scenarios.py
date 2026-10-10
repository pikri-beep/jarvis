"""End-to-end integration tests for the primary user interaction scenarios:
1. Music playback by Title & Artist: 'JARVIS, putar lagu Apalah Arti Menunggu - Raisa'
2. Mood-based music playback: 'JARVIS, putar lagu santai dong'
3. Visual screen element inquiry: 'JARVIS, tombol yang merah di sebelah kanan itu apa?'
4. Contextual follow-up action: 'Klik tombol itu lalu lanjutkan'
"""

from unittest.mock import MagicMock, patch
import pytest

from app.core.orchestrator import Orchestrator
from app.core.router import RouteType
from app.tools.screen_reader import ScreenObservation, ScreenReadResult, UIElement
from app.tools.youtube_controller import YouTubeVideoItem


def test_scenario_1_music_by_title_and_artist():
    """Scenario 1: 'JARVIS, putar lagu Apalah Arti Menunggu - Raisa'."""
    orchestrator = Orchestrator()
    mock_item = YouTubeVideoItem(
        video_id="dQw4w9WgXcQ",
        title="Raisa - Apalah (Arti Menunggu) [Official Music Video]",
        channel="Raisa6690",
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )

    with patch("app.tools.youtube_controller.search_youtube_videos", return_value=[mock_item]), \
         patch("app.tools.browser.launch_website", return_value=(True, "YouTube", mock_item.url, "Success")), \
         patch("app.tools.youtube_controller.verify_youtube_playback", return_value=True):

        route, stream = orchestrator.process_input_stream("JARVIS, putar lagu Apalah Arti Menunggu - Raisa")
        assert route.route_type == RouteType.FAST_COMMAND
        assert route.action == "play_music"
        output = "".join(list(stream))

        # Check response acknowledges the title and artist
        assert "Apalah Arti Menunggu" in output
        assert "Raisa" in output
        assert "YouTube" in output


def test_scenario_2_mood_based_music():
    """Scenario 2: 'JARVIS, putar lagu santai dong'."""
    orchestrator = Orchestrator()
    mock_playlist = YouTubeVideoItem(
        video_id="playlist123",
        title="Lagu Santai Indonesia 2024 - Akustik Terbaik",
        channel="Indie Akustik",
        url="https://www.youtube.com/watch?v=playlist123",
        is_playlist=True,
    )

    with patch("app.tools.youtube_controller.search_youtube_videos", return_value=[mock_playlist]), \
         patch("app.tools.browser.launch_website", return_value=(True, "YouTube", mock_playlist.url, "Success")), \
         patch("app.tools.youtube_controller.verify_youtube_playback", return_value=True):

        route, stream = orchestrator.process_input_stream("JARVIS, putar lagu santai dong")
        assert route.route_type == RouteType.FAST_COMMAND
        assert route.action == "play_music"
        output = "".join(list(stream))

        # Check that it selected a relaxing music track/playlist and confirmed it without asking for title
        assert "santai" in output.lower()
        assert "YouTube" in output


def test_scenario_3_and_4_screen_inquiry_and_contextual_click():
    """Scenario 3: 'JARVIS, tombol yang merah di sebelah kanan itu apa?'
    Followed by:
    Scenario 4: 'Klik tombol itu lalu lanjutkan'.
    """
    orchestrator = Orchestrator()

    # Create mock observation with a Close button at top right
    close_btn = UIElement(
        name="Tutup",
        control_type="Button",
        rect=(1880, 10, 40, 30),
        center_x=1900,
        center_y=25,
        is_enabled=True,
        automation_id="Close",
    )
    obs = ScreenObservation(
        window_title="Google Chrome - YouTube",
        process_name="chrome.exe",
        elements=[close_btn],
        source="UIA",
    )
    sr_res = ScreenReadResult(
        success=True,
        window_title="Google Chrome - YouTube",
        text="Tutup",
        method="UIA",
        spoken_summary="Elemen yang dimaksud adalah Tombol 'Tutup' (tipe: Button), sir.",
        display_text="Elemen yang dimaksud adalah Tombol 'Tutup' (tipe: Button), sir.",
        observation=obs,
    )

    # 1. Ask about red button on the right
    with patch("app.tools.screen_reader.read_screen_content", return_value=sr_res):
        route1, stream1 = orchestrator.process_input_stream("JARVIS, tombol yang merah di sebelah kanan itu apa?")
        assert route1.route_type == RouteType.SCREEN_READ
        out1 = "".join(list(stream1))
        assert "Tutup" in out1 or "Button" in out1

        # Verify state retained the focused element
        focused = orchestrator.state.get_last_focused_element()
        assert focused is not None
        assert focused.name == "Tutup"
        assert focused.center_x == 1900

    # 2. Contextual follow-up: "Klik tombol itu lalu lanjutkan"
    with patch("app.tools.desktop.move_cursor", return_value=(True, "Moved")) as mock_move, \
         patch("app.tools.desktop.mouse_click", return_value=(True, "Clicked")) as mock_click:

        route2, stream2 = orchestrator.process_input_stream("Klik tombol itu lalu lanjutkan")
        assert route2.route_type == RouteType.FAST_COMMAND
        out2 = "".join(list(stream2))

        # Must have moved to the focused element coordinates and clicked
        assert mock_move.called
        assert mock_click.called
        assert mock_move.call_args[0][0] == 1900
        assert mock_move.call_args[0][1] == 25


def test_scenario_4_ambiguous_context_requests_clarification():
    """Scenario 4 edge case: 'Klik tombol itu lalu lanjutkan' when no button was focused."""
    orchestrator = Orchestrator()
    # Reset any state
    orchestrator.state.clear_focused_element()

    with patch("app.tools.desktop.move_cursor") as mock_move, \
         patch("app.tools.desktop.mouse_click") as mock_click:

        route, stream = orchestrator.process_input_stream("Klik tombol itu lalu lanjutkan")
        out = "".join(list(stream))

        # Must not click randomly, must request clarification
        assert not mock_move.called
        assert not mock_click.called
        assert "belum bisa dipastikan" in out or "spesifik" in out
