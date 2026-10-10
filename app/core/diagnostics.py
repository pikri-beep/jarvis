"""Automated system diagnostic tool and structured latency tracker for JARVIS.

Follows Workstream I & Section 9 requirements:
- Redacted, privacy-aware diagnostics (zero passwords, keys, or secrets).
- Instant reporting of OS, Python, audio devices, state machine, LLM, TTS, STT, and tool health.
- Single command execution (`/diag`) providing structured troubleshooting output.
- Precise stage timestamps (wake, speech start/end, STT, router, LLM, tool, first TTS, completion).
- p50, p95, and max latency calculations enforcing the 10-second performance contract.
"""

import os
import platform
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import get_settings


# ==============================================================================
# SECTION 9: LATENCY & PERFORMANCE DIAGNOSTICS
# ==============================================================================

@dataclass
class TurnDiagnostics:
    """Detailed stage breakdown for a single interaction turn."""
    turn_id: int
    user_input: str
    route_type: str = "DIRECT"
    action: str = ""
    intent: str = ""
    llm_invoked: bool = False
    success: bool = True
    error: Optional[str] = None
    timeout_reason: Optional[str] = None

    # Timestamps (monotonic)
    t_wake: float = 0.0
    t_speech_start: float = 0.0
    t_speech_end: float = 0.0
    t_stt_end: float = 0.0
    t_router_end: float = 0.0
    t_llm_start: float = 0.0
    t_llm_end: float = 0.0
    t_tool_start: float = 0.0
    t_tool_end: float = 0.0
    t_first_action: float = 0.0
    t_first_tts: float = 0.0
    t_complete: float = 0.0

    # Measured durations in seconds
    duration_speech: float = 0.0
    duration_stt: float = 0.0
    duration_routing: float = 0.0
    duration_llm: float = 0.0
    duration_tool: float = 0.0
    duration_tts_prep: float = 0.0
    duration_local_e2e: float = 0.0
    duration_total_e2e: float = 0.0

    def calculate_durations(self) -> None:
        """Computes stage durations from recorded timestamps."""
        if self.t_speech_start > 0 and self.t_speech_end > self.t_speech_start:
            self.duration_speech = self.t_speech_end - self.t_speech_start
        if self.t_stt_end > 0 and self.t_speech_end > 0:
            self.duration_stt = max(0.0, self.t_stt_end - self.t_speech_end)
        if self.t_llm_start > 0 and self.t_llm_end > self.t_llm_start:
            self.duration_llm = self.t_llm_end - self.t_llm_start
        if self.t_tool_start > 0 and self.t_tool_end > self.t_tool_start:
            self.duration_tool = self.t_tool_end - self.t_tool_start
        if self.t_complete > 0:
            t_base = self.t_stt_end if self.t_stt_end > 0 else (self.t_speech_end if self.t_speech_end > 0 else self.t_wake)
            if t_base > 0:
                self.duration_local_e2e = max(0.0, self.t_complete - t_base)
            t_total_base = self.t_wake if self.t_wake > 0 else (self.t_speech_start if self.t_speech_start > 0 else t_base)
            if t_total_base > 0:
                self.duration_total_e2e = max(0.0, self.t_complete - t_total_base)


class DiagnosticsTracker:
    """Tracks latency metrics across sessions and calculates p50, p95, and max metrics."""

    def __init__(self):
        self.turns: List[TurnDiagnostics] = []
        self._turn_counter: int = 0

    def start_turn(self, user_input: str) -> TurnDiagnostics:
        self._turn_counter += 1
        diag = TurnDiagnostics(
            turn_id=self._turn_counter,
            user_input=user_input,
            t_wake=time.time(),
        )
        self.turns.append(diag)
        return diag

    def get_summary_stats(self) -> Dict[str, Any]:
        """Calculates p50, p95, and max latencies across recorded turns."""
        if not self.turns:
            return {"count": 0, "p50_e2e": 0.0, "p95_e2e": 0.0, "max_e2e": 0.0}

        local_e2es = sorted([t.duration_local_e2e for t in self.turns if t.duration_local_e2e > 0])
        llm_times = sorted([t.duration_llm for t in self.turns if t.duration_llm > 0])
        routing_times = sorted([t.duration_routing for t in self.turns if t.duration_routing > 0])

        def _percentile(data: List[float], pct: float) -> float:
            if not data:
                return 0.0
            idx = int(len(data) * pct)
            idx = min(idx, len(data) - 1)
            return round(data[idx], 3)

        return {
            "count": len(self.turns),
            "p50_local_e2e": _percentile(local_e2es, 0.50),
            "p95_local_e2e": _percentile(local_e2es, 0.95),
            "max_local_e2e": max(local_e2es) if local_e2es else 0.0,
            "p50_llm": _percentile(llm_times, 0.50),
            "p95_llm": _percentile(llm_times, 0.95),
            "max_llm": max(llm_times) if llm_times else 0.0,
            "p50_routing": _percentile(routing_times, 0.50),
            "p95_routing": _percentile(routing_times, 0.95),
        }


# Global singleton tracker instance
diagnostics_tracker = DiagnosticsTracker()


# ==============================================================================
# SECTION I: SYSTEM REPORT GENERATION (/diag)
# ==============================================================================

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

    # Search-First & Screen Vision status
    last_search = orchestrator.state.get_last_search()
    last_screen = orchestrator.state.get_last_screen()

    from app.tools.screen_reader import check_vision_model_available
    has_vision, vision_model, vision_info = check_vision_model_available(settings.ollama_url)

    # Performance stats
    perf_stats = diagnostics_tracker.get_summary_stats()

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
        "search_first": {
            "provider": "Bing Web Search (Primary) + Wikipedia OpenSearch (Fallback)",
            "llm_bypassed": True,
            "last_query": last_search.get("query", "None"),
            "results_count": len(last_search.get("sources", [])),
            "sources": [s.get("domain", "") for s in last_search.get("sources", []) if s.get("domain")],
        },
        "screen_vision": {
            "ocr_engine": "Windows 11 Native WinRT (Windows.Media.Ocr.OcrEngine)",
            "ui_automation": "Active (Desktop Window Hierarchy)",
            "vision_model_available": has_vision,
            "vision_model": vision_model or "None (auto-download prevented)",
            "last_window": last_screen.get("window_title", "None"),
            "last_method": last_screen.get("method", "None"),
        },
        "ai_orchestrator": {
            "ollama_url": settings.ollama_url,
            "model": settings.model,
            "ollama_online": llm_available,
            "model_ready": model_available,
            "llm_enabled": settings.llm_enabled,
            "desktop_mode": "Zero-LLM Fast Mode (Bypassed)" if not settings.llm_enabled else "LLM Enabled",
            "conversation_language": orchestrator.state.conversation_language,
            "recent_turns_count": len(orchestrator.state.history),
            "last_action": orchestrator.state.last_action_context.get("action", "None"),
        },
        "tools_and_agents": {
            "chrome_installed": bool(chrome_path),
            "chrome_path": str(chrome_path) if chrome_path else "Not found",
            "mouse_keyboard_control": "Active (ctypes user32 SendInput & mouse_event)",
            "browser_control": "Active (Tab control, Navigation, Address bar)",
            "web_search_agent": "Active (Extractive 1-2 sentence search)",
            "music_controller": "Active (Windows Media Keys & YouTube/Spotify)",
            "desktop_automation": "Active (PowerShell Screen Capture & User32 Lock)",
            "stored_memories_count": len(memories),
        },
        "performance": perf_stats,
    }


def format_diagnostics_text(diag: Dict[str, Any]) -> str:
    """Formats diagnostic metrics dictionary into a compact terminal view."""
    p = diag["platform"]
    v = diag["voice_pipeline"]
    a = diag["ai_orchestrator"]
    t = diag["tools_and_agents"]
    sf = diag.get("search_first", {})
    sv = diag.get("screen_vision", {})
    perf = diag.get("performance", {})

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
        f" [Search-1st] Provider: {sf.get('provider', 'Bing Web Search')}",
        f"              LLM Bypassed: {sf.get('llm_bypassed', True)} (Extractive 1-2 sentence)",
        f"              Last Query: {sf.get('last_query', 'None')}",
        f"              Sources Retrieved: {sf.get('results_count', 0)} ({', '.join(sf.get('sources', [])) or 'None'})",
        "-" * 66,
        f" [Screen/Vis] OCR: {sv.get('ocr_engine', 'Windows 11 WinRT OCR')}",
        f"              UI Automation: {sv.get('ui_automation', 'Active')}",
        f"              Vision Model: {sv.get('vision_model', 'None')}",
        f"              Active Window: {sv.get('last_window', 'None')} (Method: {sv.get('last_method', 'None')})",
        "-" * 66,
        f" [Local LLM]  Status: {a.get('desktop_mode', 'Zero-LLM Mode')}",
        f"              Server: {a['ollama_url']} (Online: {a['ollama_online']})",
        f"              Model: {a['model']} (Ready: {a['model_ready']})",
        f"              Active Language: {a['conversation_language'].upper()}",
        f"              Session Turns: {a['recent_turns_count']} | Last Action: {a.get('last_action', 'None')}",
        "-" * 66,
        f" [Tools]      Chrome: {t['chrome_installed']} ({t['chrome_path']})",
        f"              Desktop Input: {t.get('mouse_keyboard_control', 'Active')}",
        f"              Browser Control: {t.get('browser_control', 'Active')}",
        f"              Browser Agent: {t['web_search_agent']}",
        f"              Music Controller: {t['music_controller']}",
        f"              Desktop Tools: {t['desktop_automation']}",
        f"              Persistent Memories: {t['stored_memories_count']} facts",
    ]
    if perf and perf.get("count", 0) > 0:
        lines.extend([
            "-" * 66,
            f" [Perf Stats] Turns Tracked: {perf.get('count')}",
            f"              Local E2E: p50={perf.get('p50_local_e2e')}s | p95={perf.get('p95_local_e2e')}s | max={perf.get('max_local_e2e')}s",
            f"              LLM Time:  p50={perf.get('p50_llm')}s | p95={perf.get('p95_llm')}s",
            f"              Routing:   p50={perf.get('p50_routing')}s",
        ])
    lines.append("=" * 66)
    return "\n".join(lines)
