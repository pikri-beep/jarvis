"""Unit and integration tests for YouTube Controller and music intelligence."""

from unittest.mock import MagicMock, patch
import pytest

from app.tools.youtube_controller import (
    YouTubeVideoItem,
    execute_youtube_command,
    parse_music_intent,
    search_youtube_videos,
    select_best_youtube_match,
    verify_youtube_playback,
)


def test_parse_music_intent_title_and_artist():
    """Verifies parsing of 'Apalah Arti Menunggu - Raisa'."""
    i1 = parse_music_intent("Putar lagu Apalah Arti Menunggu - Raisa")
    assert i1["type"] == "song_artist"
    assert i1["title"] == "Apalah Arti Menunggu"
    assert i1["artist"] == "Raisa"

    i2 = parse_music_intent("JARVIS, putar lagu Apalah Arti Menunggu oleh Raisa dong")
    assert i2["type"] == "song_artist"
    assert i2["title"] == "Apalah Arti Menunggu"
    assert i2["artist"] == "Raisa"


def test_parse_music_intent_mood():
    """Verifies parsing of mood-based music requests like 'putar lagu santai dong'."""
    i1 = parse_music_intent("JARVIS, putar lagu santai dong")
    assert i1["type"] == "mood"
    assert i1["mood"] == "santai"
    assert "santai" in i1["query"]

    i2 = parse_music_intent("play relaxing music please")
    assert i2["type"] == "mood"
    assert i2["mood"] == "relaxing"

    i3 = parse_music_intent("putar lagu galau")
    assert i3["type"] == "mood"
    assert i3["mood"] == "galau"


def test_select_best_youtube_match_official_video():
    """Verifies that official music video from artist is prioritized over parodies and covers."""
    intent = {
        "type": "song_artist",
        "title": "Apalah Arti Menunggu",
        "artist": "Raisa",
    }
    candidates = [
        YouTubeVideoItem(
            video_id="v1",
            title="Raisa - Apalah Arti Menunggu (Cover Acoustic by Alex)",
            channel="Alex Acoustic",
            url="https://youtube.com/watch?v=v1",
        ),
        YouTubeVideoItem(
            video_id="v2",
            title="RAISA - Apalah (Arti Menunggu) (Official Music Video)",
            channel="raisa6690",
            url="https://youtube.com/watch?v=v2",
        ),
        YouTubeVideoItem(
            video_id="v3",
            title="Apalah Arti Menunggu Reaction Video",
            channel="Reactor Guy",
            url="https://youtube.com/watch?v=v3",
        ),
    ]

    selected = select_best_youtube_match(candidates, intent)
    assert selected is not None
    assert selected.video_id == "v2"
    assert "Official Music Video" in selected.title


def test_select_best_youtube_match_mood_playlist():
    """Verifies that mood-based selection prioritizes playlists and acoustic mixes."""
    intent = {
        "type": "mood",
        "mood": "santai",
        "query": "lagu santai indonesia acoustic mix",
    }
    candidates = [
        YouTubeVideoItem(
            video_id="s1",
            title="Trailer Film Santai",
            channel="Cinema Channel",
            url="https://youtube.com/watch?v=s1",
            is_playlist=False,
        ),
        YouTubeVideoItem(
            video_id="p1",
            title="Lagu Santai Indonesia Terbaik - Playlist Akustik",
            channel="Indie Mix",
            url="https://youtube.com/playlist?list=p1",
            is_playlist=True,
        ),
        YouTubeVideoItem(
            video_id="s2",
            title="Tips Hidup Santai",
            channel="Podcast",
            url="https://youtube.com/watch?v=s2",
            is_playlist=False,
        ),
    ]

    selected = select_best_youtube_match(candidates, intent)
    assert selected is not None
    assert selected.video_id == "p1"
    assert selected.is_playlist is True


def test_execute_youtube_command_end_to_end_mock():
    """Verifies end-to-end execution of a song request with mocked web launch."""
    with patch("app.tools.youtube_controller.search_youtube_videos") as mock_search, \
         patch("app.tools.youtube_controller.launch_website") as mock_launch, \
         patch("app.tools.youtube_controller.verify_youtube_playback") as mock_verify:
        
        mock_search.return_value = [
            YouTubeVideoItem(
                video_id="v_official",
                title="RAISA - Apalah (Arti Menunggu) (Official Video)",
                channel="raisa6690",
                url="https://www.youtube.com/watch?v=v_official",
            )
        ]
        mock_launch.return_value = (True, "YouTube", "https://www.youtube.com/watch?v=v_official", "OK")
        mock_verify.return_value = True

        ok, msg, meta = execute_youtube_command("JARVIS, putar lagu Apalah Arti Menunggu - Raisa", language="id")
        assert ok is True
        assert "Apalah Arti Menunggu" in msg
        assert "Raisa" in msg
        assert meta["video_id"] == "v_official"
        mock_launch.assert_called_once_with("https://www.youtube.com/watch?v=v_official")
