"""Unit tests for Multi-Layer Screen Observation, UI Automation, and Screen Q&A Understanding."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.tools.screen_reader import (
    ScreenObservation,
    ScreenReadResult,
    TextRegion,
    UIElement,
    answer_screen_question,
    check_vision_model_available,
    classify_text_regions,
    extract_uia_elements,
    find_element_by_reference,
    query_ollama_vision,
    read_screen_content,
)


def test_ui_element_dataclass():
    """Verifies UIElement creation and center coordinate calculation."""
    el = UIElement(
        name="Play Video",
        control_type="Button",
        rect=(100, 200, 80, 40),
        center_x=140,
        center_y=220,
        is_enabled=True,
        is_focused=False,
    )
    assert el.name == "Play Video"
    assert el.control_type == "Button"
    assert el.center_x == 140
    assert el.center_y == 220
    assert el.is_enabled is True


def test_classify_text_regions():
    """Verifies OCR text segmentation and semantic categorization."""
    ocr_sample = (
        "YouTube - Google Chrome\n"
        "Error: Network connection failed to initialize\n"
        "Play\n"
        "Raisa - Apalah Arti Menunggu Official Music Video\n"
        "Warning: Battery level critical"
    )
    regions = classify_text_regions(ocr_sample)
    assert len(regions) == 5
    
    # Title at line 0
    assert regions[0].category == "title"
    assert "YouTube" in regions[0].text

    # Error lines
    assert regions[1].category == "error"
    assert "Error:" in regions[1].text
    assert regions[4].category == "error"
    assert "Warning:" in regions[4].text

    # Button line
    assert regions[2].category == "button"
    assert regions[2].text == "Play"

    # Main body
    assert regions[3].category == "body"


def test_screen_observation_structure():
    """Verifies normalized ScreenObservation structure combining UIA and OCR."""
    elements = [
        UIElement(name="Search", control_type="Edit", rect=(200, 50, 400, 30), center_x=400, center_y=65),
        UIElement(name="Close", control_type="Button", rect=(1880, 0, 40, 30), center_x=1900, center_y=15),
    ]
    regions = [
        TextRegion(text="YouTube Home", category="title"),
    ]
    obs = ScreenObservation(
        window_title="YouTube - Google Chrome",
        process_name="chrome.exe",
        hwnd=12345,
        browser_page_title="YouTube Home",
        elements=elements,
        text_regions=regions,
        full_text="YouTube Home\nSearch",
        timestamp=time.time(),
        source="hybrid",
    )
    assert obs.window_title == "YouTube - Google Chrome"
    assert obs.process_name == "chrome.exe"
    assert len(obs.elements) == 2
    assert obs.source == "hybrid"


def test_answer_screen_question_what_is_open():
    """Verifies answering 'Apa yang sedang terbuka di layar?'."""
    obs = ScreenObservation(
        window_title="Document1 - Word",
        process_name="WINWORD.EXE",
        full_text="Laporan Keuangan Kuartal 3",
    )
    ans = answer_screen_question("Apa yang sedang terbuka di layar?", obs, language="id")
    assert "Document1 - Word" in ans
    assert "sir" in ans


def test_answer_screen_question_which_button_to_continue():
    """Verifies identifying 'Lanjut' / 'Next' button."""
    obs = ScreenObservation(
        window_title="Installer Wizard",
        elements=[
            UIElement(name="Batal", control_type="Button", rect=(500, 600, 80, 30)),
            UIElement(name="Lanjutkan", control_type="Button", rect=(600, 600, 80, 30)),
        ],
    )
    ans = answer_screen_question("Tombol mana yang harus diklik untuk melanjutkan?", obs, language="id")
    assert "Lanjutkan" in ans


def test_answer_screen_question_is_download_finished():
    """Verifies download progress recognition."""
    obs_done = ScreenObservation(
        window_title="Downloads",
        full_text="installer.exe - 100% Selesai\nUnduhan selesai",
    )
    ans_done = answer_screen_question("Apakah unduhan sudah selesai?", obs_done, language="id")
    assert "selesai" in ans_done.lower()

    obs_in_progress = ScreenObservation(
        window_title="Downloads",
        full_text="setup.zip - 45% Mengunduh 2.4 MB/s",
    )
    ans_prog = answer_screen_question("Apakah unduhan sudah selesai?", obs_in_progress, language="id")
    assert "berjalan" in ans_prog.lower()


def test_answer_screen_question_is_music_playing():
    """Verifies media playback status answering."""
    obs_playing = ScreenObservation(
        window_title="Raisa - Apalah Arti Menunggu - YouTube",
        elements=[
            UIElement(name="Jeda (k)", control_type="Button"),
        ],
        full_text="Raisa - Apalah Arti Menunggu",
    )
    ans = answer_screen_question("Apakah musiknya sudah diputar?", obs_playing, language="id")
    assert "diputar" in ans.lower()


def test_answer_screen_question_why_failed():
    """Verifies failure cause explanation from screen error text."""
    obs_err = ScreenObservation(
        window_title="Login - Portal",
        text_regions=[
            TextRegion(text="Error: Password yang Anda masukkan salah.", category="error"),
        ],
        full_text="Error: Password yang Anda masukkan salah.",
    )
    ans = answer_screen_question("Kenapa langkah tadi gagal?", obs_err, language="id")
    assert "Password yang Anda masukkan salah" in ans


def test_find_element_by_reference_red_button_at_right():
    """Verifies finding button on the right (such as Close button)."""
    elements = [
        UIElement(name="Menu", control_type="Button", center_x=50, center_y=20),
        UIElement(name="Tutup", control_type="Button", center_x=1890, center_y=15, automation_id="Close"),
    ]
    obs = ScreenObservation(window_title="App Window", elements=elements)
    
    el = find_element_by_reference("tombol yang merah di sebelah kanan", obs)
    assert el is not None
    assert el.name == "Tutup"
    assert el.center_x == 1890


def test_find_element_by_reference_play_button():
    """Verifies finding Play button."""
    elements = [
        UIElement(name="Next", control_type="Button", center_x=100, center_y=500),
        UIElement(name="Putar Video", control_type="Button", center_x=500, center_y=500),
    ]
    obs = ScreenObservation(window_title="Player", elements=elements)
    el = find_element_by_reference("klik tombol putar", obs)
    assert el is not None
    assert el.name == "Putar Video"


def test_check_vision_model_available_mock():
    """Verifies Ollama tags inspection for multimodal models."""
    mock_payload = json_bytes = b'{"models": [{"name": "qwen3:8b"}, {"name": "moondream:latest", "details": {"families": ["clip"]}}]}'
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_payload
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp

        has_vis, v_name, msg = check_vision_model_available("http://mock:11434")
        assert has_vis is True
        assert v_name == "moondream:latest"


def test_check_vision_model_available_none():
    """Verifies graceful handling when Ollama only has text models."""
    mock_payload = b'{"models": [{"name": "qwen3:8b"}, {"name": "llama3:latest"}]}'
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_payload
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp

        has_vis, v_name, msg = check_vision_model_available("http://mock:11434")
        assert has_vis is False
        assert v_name is None
        assert "Tidak ada model visi" in msg
