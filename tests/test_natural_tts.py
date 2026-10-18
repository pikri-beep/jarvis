"""Tests for Natural AI Voice, Edge-TTS synthesis, SmartTTSCache, and offline fallback."""

import io
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from app.core.config import Settings
from app.voice.text_to_speech import (
    SmartTTSCache,
    TextToSpeech,
    _decode_mp3_to_int16,
)


@pytest.fixture
def temp_cache_dir():
    temp_dir = Path(tempfile.mkdtemp(prefix="jarvis_test_tts_cache_"))
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_smart_tts_cache(temp_cache_dir):
    """Verifies that SmartTTSCache correctly persists and retrieves NumPy audio arrays."""
    cache = SmartTTSCache(temp_cache_dir)
    voice = "id-ID-ArdiNeural"
    modifier = "1.0_+0Hz"
    text = "Membuka Chrome, sir."

    # Initial get should be a miss
    assert cache.get(voice, modifier, text) is None

    # Save audio array
    dummy_audio = np.array([100, 200, 300, -100, -200], dtype=np.int16)
    cache.set(voice, modifier, text, dummy_audio)

    # Retrieval should be a hit and identical
    retrieved = cache.get(voice, modifier, text)
    assert retrieved is not None
    assert np.array_equal(retrieved, dummy_audio)

    # Different text should be a miss
    assert cache.get(voice, modifier, "Kalimat lain") is None


def test_decode_mp3_to_int16():
    """Verifies in-memory decoding logic handles empty or invalid inputs gracefully."""
    # Empty input returns None
    assert _decode_mp3_to_int16(b"") is None
    # Invalid audio stream returns None without raising uncaught exceptions
    assert _decode_mp3_to_int16(b"not_a_valid_mp3_data") is None


def test_natural_tts_edge_synthesis_and_cache(temp_cache_dir):
    """Verifies Edge-TTS synthesis uses cache and produces valid audio."""
    settings = Settings(
        tts_enabled=True,
        tts_engine="hybrid",
        tts_voice_id="id-ID-ArdiNeural",
        tts_cache_enabled=True,
        tts_cache_dir=temp_cache_dir,
    )
    tts = TextToSpeech(settings=settings)

    # Mock _synthesize_edge_tts to simulate Edge-TTS response
    fake_audio = np.array([500, -500, 1000, -1000], dtype=np.int16)
    with patch.object(tts, "_synthesize_edge_tts", return_value=fake_audio) as mock_edge:
        # First call: should call _synthesize_edge_tts and populate cache
        audio1, sr1 = tts.synthesize("Membuka Chrome, sir.", language="id")
        assert mock_edge.call_count == 1
        assert sr1 == 24000
        assert np.array_equal(audio1, fake_audio)

        # Second call with same text: should hit cache and NOT call _synthesize_edge_tts again
        audio2, sr2 = tts.synthesize("Membuka Chrome, sir.", language="id")
        assert mock_edge.call_count == 1  # Still 1 because cache was hit!
        assert sr2 == 24000
        assert np.array_equal(audio2, fake_audio)


def test_natural_tts_fallback_to_piper(temp_cache_dir):
    """Verifies that if Edge-TTS fails, hybrid mode falls back to Piper seamlessly."""
    settings = Settings(
        tts_enabled=True,
        tts_engine="hybrid",
        tts_voice_id="id-ID-ArdiNeural",
        tts_cache_enabled=False,
    )
    tts = TextToSpeech(settings=settings)

    fake_piper_audio = np.array([123, -123], dtype=np.int16)

    # Edge-TTS fails (returns None due to network error/timeout)
    with patch.object(tts, "_synthesize_edge_tts", return_value=None), \
         patch.object(tts, "_synthesize_piper", return_value=(fake_piper_audio, 22050)) as mock_piper:
        audio, sr = tts.synthesize("Halo Jarvis", language="id")
        assert mock_piper.call_count == 1
        assert sr == 22050
        assert np.array_equal(audio, fake_piper_audio)


def test_english_stays_piper():
    """Verifies that English text routes directly to Piper without touching Edge-TTS."""
    settings = Settings(
        tts_enabled=True,
        tts_engine="hybrid",
        tts_voice_id="id-ID-ArdiNeural",
    )
    tts = TextToSpeech(settings=settings)

    fake_piper_audio = np.array([321, -321], dtype=np.int16)

    with patch.object(tts, "_synthesize_edge_tts") as mock_edge, \
         patch.object(tts, "_synthesize_piper", return_value=(fake_piper_audio, 16000)) as mock_piper:
        audio, sr = tts.synthesize("Opening Chrome, sir.", language="en")
        assert mock_edge.call_count == 0  # Did NOT call Edge-TTS
        assert mock_piper.call_count == 1  # Routed to Piper
        assert sr == 16000


def test_settings_tab_voice_controls(qapp):
    """Verifies that SettingsTab dropdown and slider correctly update orchestrator settings."""
    from app.core.orchestrator import Orchestrator
    from app.ui.tabs.settings_tab import SettingsTab

    settings = Settings(
        tts_enabled=True,
        tts_engine="hybrid",
        tts_voice_id="id-ID-ArdiNeural",
        tts_rate=1.0,
    )
    orch = Orchestrator(settings=settings)
    tab = SettingsTab(orchestrator=orch)

    # Verify initial values
    assert tab.combo_voice.currentData() == "id-ID-ArdiNeural"
    assert tab.slider_speed.value() == 100

    # Change voice to Gadis (Wanita)
    idx_gadis = tab.combo_voice.findData("id-ID-GadisNeural")
    tab.combo_voice.setCurrentIndex(idx_gadis)
    assert orch.settings.tts_voice_id == "id-ID-GadisNeural"
    assert orch.settings.tts_engine == "hybrid"

    # Change voice to Piper (Offline)
    idx_piper = tab.combo_voice.findData("piper")
    tab.combo_voice.setCurrentIndex(idx_piper)
    assert orch.settings.tts_voice_id == "piper"
    assert orch.settings.tts_engine == "piper"

    # Change speed slider to 125 (1.25x)
    tab.slider_speed.setValue(125)
    assert orch.settings.tts_rate == 1.25
    assert "1.25x" in tab.lbl_speed_val.text()

