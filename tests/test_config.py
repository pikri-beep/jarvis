"""Unit tests for configuration management."""

import os
from unittest.mock import patch
from app.core.config import Settings, reload_settings, get_settings


def test_default_settings():
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        assert settings.jarvis_name == "Jarvis"
        assert settings.model == "qwen2.5:1.5b"
        assert settings.ollama_url == "http://localhost:11434"
        assert settings.keep_alive == "15m"
        assert settings.think_mode is False
        assert settings.stt_model == "small"
        assert settings.stt_device == "cpu"
        assert settings.stt_compute_type == "int8"
        assert settings.tts_enabled is False


def test_environment_override():
    with patch.dict(os.environ, {
        "JARVIS_NAME": "Friday",
        "JARVIS_MODEL": "qwen2.5:3b",
        "JARVIS_OLLAMA_URL": "http://127.0.0.1:11434/",
        "JARVIS_TEMPERATURE": "0.4",
        "JARVIS_THINK_MODE": "true",
        "JARVIS_VOICE_ENABLED": "true",
    }):
        settings = reload_settings()
        assert settings.jarvis_name == "Friday"
        assert settings.model == "qwen2.5:3b"
        assert settings.ollama_url == "http://127.0.0.1:11434"
        assert settings.temperature == 0.4
        assert settings.think_mode is True
        assert settings.voice_enabled is True

    # Reset back
    reload_settings()
