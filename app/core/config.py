"""Configuration management for JARVIS."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

from dotenv import load_dotenv

# Automatically load .env file from the project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"

if _ENV_PATH.exists():
    load_dotenv(dotenv_path=_ENV_PATH)
else:
    load_dotenv()


def _get_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


def _get_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val.strip())
    except ValueError:
        return default


def _get_optional_int(key: str) -> Optional[int]:
    val = os.getenv(key)
    if val is None or not val.strip():
        return None
    try:
        return int(val.strip())
    except ValueError:
        return None


@dataclass(frozen=True)
class Settings:
    """Centralized JARVIS settings."""

    # Project metadata
    project_root: Path = _PROJECT_ROOT

    # Identity
    jarvis_name: str = field(
        default_factory=lambda: os.getenv("JARVIS_NAME", "Jarvis")
    )

    # Local LLM Runtime (Ollama)
    llm_enabled: bool = field(
        default_factory=lambda: _get_bool("JARVIS_LLM_ENABLED", True)
    )
    ollama_url: str = field(
        default_factory=lambda: os.getenv(
            "JARVIS_OLLAMA_URL", "http://localhost:11434"
        ).rstrip("/")
    )
    model: str = field(
        default_factory=lambda: os.getenv("JARVIS_MODEL", "qwen2.5:1.5b")
    )
    keep_alive: str = field(
        default_factory=lambda: os.getenv("JARVIS_KEEP_ALIVE", "15m")
    )
    think_mode: bool = field(
        default_factory=lambda: _get_bool("JARVIS_THINK_MODE", False)
    )
    temperature: float = field(
        default_factory=lambda: _get_float("JARVIS_TEMPERATURE", 0.7)
    )

    # Speech-to-Text (STT) Settings
    stt_model: str = field(
        default_factory=lambda: os.getenv("JARVIS_STT_MODEL", "small")
    )
    stt_device: str = field(
        default_factory=lambda: os.getenv("JARVIS_STT_DEVICE", "cpu")
    )
    stt_compute_type: str = field(
        default_factory=lambda: os.getenv("JARVIS_STT_COMPUTE_TYPE", "int8")
    )
    stt_language: Optional[str] = field(
        default_factory=lambda: os.getenv("JARVIS_STT_LANGUAGE", "en")
    )
    audio_device: Optional[int] = field(
        default_factory=lambda: _get_optional_int("JARVIS_AUDIO_DEVICE")
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.getenv("JARVIS_LOG_LEVEL", "INFO")
    )

    # Feature Flags (Phases 2+)
    voice_enabled: bool = field(
        default_factory=lambda: _get_bool("JARVIS_VOICE_ENABLED", False)
    )
    # Text-to-Speech (TTS) Settings
    tts_enabled: bool = field(
        default_factory=lambda: _get_bool("JARVIS_TTS_ENABLED", False)
    )
    tts_model_en: str = field(
        default_factory=lambda: os.getenv("JARVIS_TTS_MODEL_EN", "en_GB-alan-low")
    )
    tts_model_id: str = field(
        default_factory=lambda: os.getenv("JARVIS_TTS_MODEL_ID", "id_ID-news_tts-medium")
    )
    tts_language_mode: str = field(
        default_factory=lambda: os.getenv("JARVIS_TTS_LANGUAGE_MODE", "auto")
    )
    tts_models_dir: Path = field(
        default_factory=lambda: _PROJECT_ROOT / "data" / "models" / "piper"
    )
    tts_rate: float = field(
        default_factory=lambda: _get_float("JARVIS_TTS_RATE", 1.0)
    )
    tts_engine: str = field(
        default_factory=lambda: os.getenv("JARVIS_TTS_ENGINE", "hybrid")
    )
    tts_voice_id: str = field(
        default_factory=lambda: os.getenv("JARVIS_TTS_VOICE_ID", "id-ID-ArdiNeural")
    )
    tts_pitch: str = field(
        default_factory=lambda: os.getenv("JARVIS_TTS_PITCH", "+0Hz")
    )
    tts_cache_enabled: bool = field(
        default_factory=lambda: _get_bool("JARVIS_TTS_CACHE_ENABLED", True)
    )
    tts_cache_dir: Path = field(
        default_factory=lambda: _PROJECT_ROOT / "data" / "cache" / "tts_cache"
    )

    # Wake Word (Phase 4) Settings
    wake_word_enabled: bool = field(
        default_factory=lambda: _get_bool("JARVIS_WAKE_WORD_ENABLED", False)
    )
    wake_word_model: str = field(
        default_factory=lambda: os.getenv("JARVIS_WAKE_WORD_MODEL", "hey_jarvis_v0.1.onnx")
    )
    wake_word_aliases: List[str] = field(
        default_factory=lambda: [w.strip().lower() for w in os.getenv("JARVIS_WAKE_WORD_ALIASES", "jarvis,jarpis").split(",") if w.strip()]
    )
    wake_word_threshold: float = field(
        default_factory=lambda: _get_float("JARVIS_WAKE_WORD_THRESHOLD", 0.15)
    )
    wake_word_cooldown: float = field(
        default_factory=lambda: _get_float("JARVIS_WAKE_WORD_COOLDOWN", 1.5)
    )
    wake_word_vad_threshold: float = field(
        default_factory=lambda: _get_float("JARVIS_WAKE_WORD_VAD_THRESHOLD", 0.0)
    )
    wake_word_speech_start_grace: float = field(
        default_factory=lambda: _get_float(
            "JARVIS_SPEECH_START_GRACE",
            _get_float("JARVIS_WAKE_WORD_SPEECH_START_GRACE", 3.0),
        )
    )
    wake_word_post_speech_silence: float = field(
        default_factory=lambda: _get_float(
            "JARVIS_POST_SPEECH_SILENCE",
            _get_float("JARVIS_WAKE_WORD_POST_SPEECH_SILENCE", 1.8),
        )
    )
    wake_word_silence_timeout: float = field(
        default_factory=lambda: _get_float("JARVIS_WAKE_WORD_SILENCE_TIMEOUT", 1.8)
    )
    wake_word_max_command_duration: float = field(
        default_factory=lambda: _get_float("JARVIS_WAKE_WORD_MAX_COMMAND_DURATION", 12.0)
    )
    wake_word_models_dir: Path = field(
        default_factory=lambda: _PROJECT_ROOT / "data" / "models" / "wakeword"
    )

    # Search Provider Settings
    search_provider: str = field(
        default_factory=lambda: os.getenv("JARVIS_SEARCH_PROVIDER", "google").lower()
    )
    search_open_browser_tab: bool = field(
        default_factory=lambda: _get_bool("JARVIS_SEARCH_OPEN_BROWSER_TAB", True)
    )

    # Context Interpreter Settings (Layer B/C)
    interpreter_provider: str = field(
        default_factory=lambda: os.getenv("JARVIS_INTERPRETER_PROVIDER", "groq").lower()
    )
    groq_model: str = field(
        default_factory=lambda: os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    )
    interpreter_timeout: float = field(
        default_factory=lambda: _get_float("JARVIS_INTERPRETER_TIMEOUT", 8.0)
    )
    interpreter_temperature: float = field(
        default_factory=lambda: _get_float("JARVIS_INTERPRETER_TEMPERATURE", 0.1)
    )

    # Future Phase Feature Flags
    web_search_enabled: bool = field(
        default_factory=lambda: _get_bool("JARVIS_WEB_SEARCH_ENABLED", False)
    )
    memory_enabled: bool = field(
        default_factory=lambda: _get_bool("JARVIS_MEMORY_ENABLED", True)
    )

    # Proactive Autonomous Agent Settings
    proactive_enabled: bool = field(
        default_factory=lambda: _get_bool("JARVIS_PROACTIVE_ENABLED", True)
    )
    proactive_interval_seconds: float = field(
        default_factory=lambda: _get_float("JARVIS_PROACTIVE_INTERVAL_SECONDS", 900.0)
    )
    proactive_cooldown_seconds: float = field(
        default_factory=lambda: _get_float("JARVIS_PROACTIVE_COOLDOWN_SECONDS", 60.0)
    )

    # Simulated User Agent (Voice E2E Testing)
    groq_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GROQ_API_KEY")
    )


# Cached singleton instance
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Returns the singleton Settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def reload_settings() -> Settings:
    """Reloads settings from environment variables."""
    global _settings_instance
    if _ENV_PATH.exists():
        load_dotenv(dotenv_path=_ENV_PATH, override=False)
    _settings_instance = Settings()
    return _settings_instance
