"""Unit tests for the Text-to-Speech (TTS) subsystem."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from app.core.config import Settings
from app.voice.text_to_speech import AudioPlaybackQueue, SentenceBuffer, TextToSpeech, clean_text_for_speech


def test_clean_text_for_speech():
    # Markdown formatting
    text = "### Header\n**Bold** text, `inline_code()`, [link](http://test.com) > Quote"
    cleaned = clean_text_for_speech(text)
    assert "#" not in cleaned
    assert "*" not in cleaned
    assert "`" not in cleaned
    assert ">" not in cleaned
    assert "Bold text, inline_code(), link Quote" in cleaned

    # Code block removal
    code_text = "Here is code:\n```python\nprint('hello')\n```\nAll done."
    cleaned_code = clean_text_for_speech(code_text)
    assert "print('hello')" not in cleaned_code
    assert "Here is code: All done." in cleaned_code

    # Empty inputs
    assert clean_text_for_speech("") == ""
    assert clean_text_for_speech("   ") == ""


def test_sentence_buffer():
    # 1. Standard mode without early comma clause splitting
    buf = SentenceBuffer(min_chars=10, early_first_chunk=False)

    s1 = buf.feed("Good ")
    assert s1 == []
    s2 = buf.feed("evening, ")
    assert s2 == []
    s3 = buf.feed("sir. ")
    assert s3 == ["Good evening, sir."]

    # Abbreviation protection
    s4 = buf.feed("Dr. Smith is ")
    assert s4 == []
    s5 = buf.feed("available today. ")
    assert s5 == ["Dr. Smith is available today."]

    # 2. Early first chunk mode (splits at first comma to minimize TTFA)
    early_buf = SentenceBuffer(min_chars=10, early_first_chunk=True)
    e1 = early_buf.feed("Good ")
    assert e1 == []
    e2 = early_buf.feed("evening, ")
    assert e2 == ["Good evening,"]
    e3 = early_buf.feed("how are you doing today? ")
    assert e3 == ["how are you doing today?"]

    # Flush remaining fragment without terminator
    early_buf.feed("Have a pleasant day")
    flushed = early_buf.flush()
    assert flushed == ["Have a pleasant day"]


def test_detect_language():
    from app.voice.text_to_speech import detect_language

    # Test the target Indonesian validation utterances
    assert detect_language("Selamat pagi, apa kabar?") == "id"
    assert detect_language("Baik, sekarang buka Chrome.") == "id"
    assert detect_language("Tolong buka Chrome.") == "id"
    assert detect_language("Sekarang buka Google Chrome.") == "id"
    assert detect_language("Saya ingin mengetahui perbedaan RAM dan SSD.") == "id"
    assert detect_language("JARVIS, tolong jelaskan jadwal saya hari ini.") == "id"
    assert detect_language("Jelaskan jadwal saya hari ini.") == "id"
    assert detect_language("Membuka Chrome, sir.") == "id"
    assert detect_language("Menutup Notepad, sir.") == "id"

    # Test English control utterances
    assert detect_language("Good morning, how are you?") == "en"
    assert detect_language("Opening Chrome, sir.") == "en"
    assert detect_language("Explain the architecture of computer memory.") == "en"
    assert detect_language("What time is it?") == "en"
    assert detect_language("Hello, Jarvis.") == "en"

    # Empty / whitespace fallback
    assert detect_language("") == "en"
    assert detect_language("   ") == "en"


def test_tts_empty_and_silent_inputs():
    tts = TextToSpeech()
    for empty in ["", "   ", "...", "---", "!?!", "###"]:
        audio, sr = tts.synthesize(empty)
        assert audio is None
        assert sr == 0


def test_tts_disabled():
    tts = TextToSpeech()
    tts.enabled = False
    dur = tts.speak("Hello, sir.")
    assert dur == 0.0


def test_tts_mocked_synthesis_and_auto_language():
    tts = TextToSpeech(settings=Settings(tts_engine="piper"))
    
    mock_voice_en = MagicMock()
    mock_voice_en.config.sample_rate = 22050
    mock_chunk_en = MagicMock()
    mock_chunk_en.audio_int16_array = np.zeros(2205, dtype=np.int16)
    mock_voice_en.synthesize.return_value = [mock_chunk_en]

    mock_voice_id = MagicMock()
    mock_voice_id.config.sample_rate = 16000
    mock_chunk_id = MagicMock()
    mock_chunk_id.audio_int16_array = np.zeros(1600, dtype=np.int16)
    mock_voice_id.synthesize.return_value = [mock_chunk_id]

    tts._voices["en"] = mock_voice_en
    tts._voices["id"] = mock_voice_id

    # Auto language routing
    audio_en, sr_en = tts.synthesize("System ready.", language="auto")
    assert audio_en is not None
    assert sr_en == 22050
    mock_voice_en.synthesize.assert_called()

    audio_id, sr_id = tts.synthesize("Selamat pagi, apa kabar?", language="auto")
    assert audio_id is not None
    assert sr_id == 16000
    mock_voice_id.synthesize.assert_called()


def test_tts_clipping_prevention():
    tts = TextToSpeech()
    mock_voice = MagicMock()
    mock_voice.config.sample_rate = 16000

    # Create audio with clipped peaks at 32767
    clipped_audio = np.array([32767, -32767, 1000, -1000], dtype=np.int16)
    mock_chunk = MagicMock()
    mock_chunk.audio_int16_array = clipped_audio
    mock_voice.synthesize.return_value = [mock_chunk]
    tts._voices["en"] = mock_voice

    audio, sr = tts.synthesize("Loud speech test.", language="en")
    assert audio is not None
    assert np.max(np.abs(audio)) <= 28000


def test_audio_playback_queue_lifecycle():
    with patch("sounddevice.OutputStream") as mock_stream_cls:
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream

        queue = AudioPlaybackQueue()
        dummy_audio = np.zeros(160, dtype=np.int16)
        queue.enqueue(dummy_audio, 16000)

        # Allow worker thread time to process
        queue.wait_until_done(timeout=0.5)
        assert not queue.is_playing()

        mock_stream.write.assert_called()

        queue.stop()
        assert not queue.is_playing()


def test_indonesian_phonetic_normalization():
    # Indonesian technical acronym and loanword normalization
    id_text = "Membuka Chrome dan WhatsApp di PC dengan 16 GB RAM dan SSD."
    cleaned_id = clean_text_for_speech(id_text, language="id")
    assert "Krom" in cleaned_id
    assert "Watsap" in cleaned_id
    assert "Pi-Si" in cleaned_id
    assert "16 Giga" in cleaned_id
    assert "Rem" in cleaned_id
    assert "Es-Es-De" in cleaned_id

    # English leaves original English terms intact
    en_text = "Opening Chrome and WhatsApp on PC with 16 GB RAM and SSD."
    cleaned_en = clean_text_for_speech(en_text, language="en")
    assert "Chrome" in cleaned_en
    assert "WhatsApp" in cleaned_en
    assert "PC" in cleaned_en
    assert "RAM" in cleaned_en
    assert "SSD" in cleaned_en

