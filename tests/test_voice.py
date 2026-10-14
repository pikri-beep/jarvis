"""Unit tests for Voice / Speech-to-Text (STT) and Push-to-Talk audio recorder."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from app.core.config import Settings
from app.voice.audio_recorder import PushToTalkRecorder, resample_audio
from app.voice.speech_to_text import SpeechToText


def test_resample_audio_same_rate():
    audio = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    res = resample_audio(audio, orig_sr=16000, target_sr=16000)
    assert np.allclose(audio, res)


def test_resample_audio_downsample():
    # 48000 Hz to 16000 Hz should produce 1/3 number of samples
    orig = np.sin(np.linspace(0, 10, 4800)).astype(np.float32)
    res = resample_audio(orig, orig_sr=48000, target_sr=16000)
    assert len(res) == 1600
    assert res.dtype == np.float32


def test_stt_empty_audio():
    stt = SpeechToText()
    text, info = stt.transcribe(np.zeros(0, dtype=np.float32))
    assert text == ""
    assert info["duration"] == 0.0


def test_stt_silence_threshold():
    stt = SpeechToText()
    # 1 second of near-zero noise
    silent_audio = np.random.uniform(-0.001, 0.001, 16000).astype(np.float32)
    text, info = stt.transcribe(silent_audio)
    assert text == ""


def test_stt_mocked_transcription():
    stt = SpeechToText()
    mock_model = MagicMock()
    mock_segment = MagicMock()
    mock_segment.text = "Hello JARVIS"
    mock_info = MagicMock()
    mock_info.language = "en"
    mock_info.language_probability = 0.98

    mock_model.transcribe.return_value = ([mock_segment], mock_info)
    mock_model.detect_language.return_value = ("en", 0.98, [("en", 0.98), ("id", 0.02)])
    stt._model = mock_model

    # 1 second of audible synthetic audio
    audio = np.sin(np.linspace(0, 50, 16000)).astype(np.float32) * 0.5
    text, info = stt.transcribe(audio)

    assert text == "Hello JARVIS"
    assert info["language"] == "en"
    assert info["language_prob"] == 0.98
    assert "transcription_time" in info


def test_push_to_talk_recorder_lifecycle():
    with patch("app.voice.audio_recorder.find_working_input_device", return_value=(29, 16000, 1)):
        with patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream = MagicMock()
            mock_stream_cls.return_value = mock_stream

            recorder = PushToTalkRecorder(device_index=None)
            assert not recorder.is_recording
            assert recorder.device_index == 29
            assert recorder.sample_rate == 16000

            recorder.start_recording()
            assert recorder.is_recording
            mock_stream.start.assert_called_once()

            # Simulate putting a chunk into callback
            chunk = np.zeros((1024, 1), dtype=np.float32)
            recorder._audio_callback(chunk, 1024, None, None)

            audio = recorder.stop_recording()
            assert not recorder.is_recording
            assert len(audio) == 1024

            metrics = recorder.get_last_audio_metrics()
            assert metrics["duration_s"] == 1024 / 16000
            assert metrics["chunks_count"] == 1
            assert "peak" in metrics
            assert "rms" in metrics


def test_stt_model_default_is_small():
    stt = SpeechToText()
    assert stt.model_size == "small"


def test_stt_dc_offset_removal_and_beam_size_2():
    stt = SpeechToText()
    mock_model = MagicMock()
    mock_segment = MagicMock()
    mock_segment.text = "Play Creep Radiohead"
    mock_info = MagicMock()
    mock_info.language = "en"
    mock_info.language_probability = 0.95

    mock_model.transcribe.return_value = ([mock_segment], mock_info)
    stt._model = mock_model

    # Audio with DC bias of +0.30
    biased_audio = (np.sin(np.linspace(0, 50, 16000)).astype(np.float32) * 0.2) + 0.30
    text, info = stt.transcribe(biased_audio)

    assert text == "Play Creep Radiohead"
    # Verify beam_size=2 was passed to model.transcribe
    call_kwargs = mock_model.transcribe.call_args.kwargs
    assert call_kwargs.get("beam_size") == 2
    assert call_kwargs.get("best_of") == 2


def test_stt_load_model_error_handling():
    stt = SpeechToText()
    with patch("faster_whisper.WhisperModel", side_effect=Exception("Model file not found")):
        with pytest.raises(RuntimeError, match="Gagal memuat model STT"):
            stt.load_model()

