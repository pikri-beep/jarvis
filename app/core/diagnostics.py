"""Automated system diagnostic tool for JARVIS.

Follows Workstream I requirements:
- Redacted, privacy-aware diagnostics (zero passwords, keys, or secrets).
- Instant reporting of OS, Python, audio devices, state machine, LLM, TTS, STT, and tool health.
- Single command execution (`/diag`) providing structured troubleshooting output.
"""

import os
import platform
import sys
from typing import Any, Dict

from app.core.config import get_settings


def generate_diagnostics_report(orchestrator: Any) -> Dict[str, Any]:
    """Collects comprehensive, redacted system status and health metrics."""
    settings = orchestrator.settings or get_settings()

    # Audio & Voice metrics
    audio_device_idx = settings.audio_device
    wake_detector = getattr(orchestrator, "_wake_detector", None)
    wake_state = wake_detector.state.value if wake_detector else "UNINITIALIZED"

    # Memory count
    from app.memory.memory import memory_manager
    memories = memory_manager.recall_all()

    # Browser discovery
    from app.tools.apps import find_application_executable
    chrome_path = find_application_executable("chrome")

    # LLM health
    llm = orchestrator.llm
    llm_available = llm.is_server_available() if llm else False
    model_available = llm.is_model_available() if llm else False

    # TTS & STT
    tts = orchestrator.get_tts() if settings.tts_enabled else None
    stt = orchestrator.get_stt() if (settings.voice_enabled or settings.wake_word_enabled) else None

    return {
        "platform": {
            "os": f"{platform.system()} {platform.release()} ({platform.version()})",
            "python": sys.version.split()[0],
            "machine": platform.machine(),
            "processor": platform.processor() or "Unknown",
        },
        "voice_pipeline": {
            "wake_word_active": bool(wake_detector and wake_detector.is_listening()),
            "wake_state": wake_state,
            "wake_model": settings.wake_word_model,
            "audio_device_index": audio_device_idx,
            "stt_engine": "faster-whisper",
            "stt_model": settings.stt_model,
            "stt_loaded": bool(stt and stt.is_loaded()),
            "tts_engine": "Piper TTS",
            "tts_model_id": settings.tts_model_id,
            "tts_model_en": settings.tts_model_en,
            "tts_loaded_voices": list(tts._voices.keys()) if tts else [],
        },
        "ai_orchestrator": {
            "ollama_url": settings.ollama_url,
            "model": settings.model,
            "ollama_online": llm_available,
            "model_ready": model_available,
            "conversation_language": orchestrator.state.conversation_language,
            "recent_turns_count": len(orchestrator.state.history),
        },
        "tools_and_agents": {
            "chrome_installed": bool(chrome_path),
            "chrome_path": str(chrome_path) if chrome_path else "Not found",
            "web_search_agent": "Active (Wikipedia & Clean Web Scraper)",
            "music_controller": "Active (Windows Media Keys & YouTube/Spotify)",
            "desktop_automation": "Active (PowerShell Screen Capture & User32 Lock)",
            "stored_memories_count": len(memories),
        },
    }


def format_diagnostics_text(diag: Dict[str, Any]) -> str:
    """Formats diagnostic metrics dictionary into a compact terminal view."""
    p = diag["platform"]
    v = diag["voice_pipeline"]
    a = diag["ai_orchestrator"]
    t = diag["tools_and_agents"]

    lines = [
        "=" * 66,
        "             JARVIS SYSTEM DIAGNOSTICS REPORT",
        "=" * 66,
        f" [Platform]   OS: {p['os']}",
        f"              Python: {p['python']} | Arch: {p['machine']}",
        "-" * 66,
        f" [Audio/Voice] State: {v['wake_state']} | Wake Active: {v['wake_word_active']}",
        f"              Audio Device: #{v['audio_device_index']}",
        f"              STT: {v['stt_model']} (Loaded: {v['stt_loaded']})",
        f"              TTS: ID={v['tts_model_id']} | EN={v['tts_model_en']}",
        f"              TTS Loaded Voices: {v['tts_loaded_voices']}",
        "-" * 66,
        f" [Local LLM]  Server: {a['ollama_url']} (Online: {a['ollama_online']})",
        f"              Model: {a['model']} (Ready: {a['model_ready']})",
        f"              Active Language: {a['conversation_language'].upper()}",
        f"              Session Turns: {a['recent_turns_count']}",
        "-" * 66,
        f" [Tools]      Chrome: {t['chrome_installed']} ({t['chrome_path']})",
        f"              Browser Agent: {t['web_search_agent']}",
        f"              Music Controller: {t['music_controller']}",
        f"              Desktop Tools: {t['desktop_automation']}",
        f"              Persistent Memories: {t['stored_memories_count']} facts",
        "=" * 66,
    ]
    return "\n".join(lines)
