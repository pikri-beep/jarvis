"""Terminal and REPL Command handler for JARVIS."""

from typing import Any, Generator, Tuple

from app.core.logger import setup_logger
from app.core.router import RouteResult

logger = setup_logger("jarvis.handlers.terminal")


def handle_terminal_command(
    orchestrator: Any,
    route: RouteResult,
    user_input: str,
    effective_lang: str,
    is_id: bool,
) -> Tuple[RouteResult, Generator[str, None, None]]:
    """Handles terminal REPL built-in commands (/help, /status, /diag, /exit, etc.)."""
    def _terminal_gen():
        if route.action == "help":
            yield (
                "Commands available:\n"
                "  /help, help        - Show this help message\n"
                "  /status, status    - Show system and model status\n"
                "  /diag, /diagnostics- Show detailed system, audio, and performance diagnostics\n"
                "  /reset             - Reset conversation context and state\n"
                "  /lang [id|en|auto] - Set interaction language mode\n"
                "  /vision [task]     - Execute vision computer-use task on screen\n"
                "  /wake, /wakeword   - Toggle Always-Listening Wake-Word mode\n"
                "  /voice, /ptt       - Toggle Push-to-Talk voice mode\n"
                "  /tts, tts          - Toggle spoken Text-to-Speech output\n"
                "  /mic, /devices     - List microphone audio devices\n"
                "  /clear, clear      - Clear conversation history\n"
                "  /exit, quit        - Exit JARVIS"
            )
        elif route.action == "show_diagnostics":
            from app.core.diagnostics import format_diagnostics_text, generate_diagnostics_report
            rep = generate_diagnostics_report(orchestrator)
            yield format_diagnostics_text(rep)
        elif route.action == "reset_context":
            orchestrator.state.clear()
            yield "Session context and conversation history reset, sir."

        elif route.action == "set_language":
            target_l = route.args.get("language", "toggle").lower()
            if target_l in ("id", "indonesia", "indonesian"):
                orchestrator.state.language_override = "id"
                orchestrator.state.conversation_language = "id"
                yield "Bahasa interaksi diatur ke Bahasa Indonesia, sir."
            elif target_l in ("en", "english"):
                orchestrator.state.language_override = "en"
                orchestrator.state.conversation_language = "en"
                yield "Interaction language set to English, sir."
            elif target_l in ("auto", "reset"):
                orchestrator.state.language_override = None
                yield "Language mode set to automatic detection, sir."
            else:
                curr = orchestrator.state.language_override or f"auto ({orchestrator.state.conversation_language})"
                yield f"Current language mode: {curr}. Use '/lang id', '/lang en', or '/lang auto'."
        elif route.action == "clear":
            orchestrator.state.clear()
            yield "Conversation history cleared, sir."
        elif route.action == "status":
            status = orchestrator.get_system_status()
            conn_sym = "ONLINE" if status["ollama_connected"] else "OFFLINE"
            mod_sym = "READY" if status["model_ready"] else "NOT FOUND"
            voice_sym = "ENABLED" if status["voice_enabled"] else "DISABLED"
            tts_sym = "ENABLED" if status["tts_enabled"] else "DISABLED"
            wake_sym = "ACTIVE" if status.get("wake_word_active") else ("ENABLED" if status.get("wake_word_enabled") else "STANDBY")
            lang_status = orchestrator.state.language_override or f"auto ({orchestrator.state.conversation_language})"
            yield (
                f"JARVIS Status:\n"
                f"  Identity:        {status['name']}\n"
                f"  Language Mode:   {lang_status}\n"
                f"  Ollama Server:   {status['ollama_url']} [{conn_sym}]\n"
                f"  Active Model:    {status['model']} [{mod_sym}]\n"
                f"  Wake Word:       {wake_sym} (Model: {status.get('wake_word_model', 'hey_jarvis_v0.1.onnx')})\n"
                f"  Voice (PTT STT): {voice_sym} (Model: {status['stt_model']})\n"
                f"  Speech Out (TTS):{tts_sym} (Model: {status['tts_model']})\n"
                f"  History Length:  {status['history_length']} messages"
            )
        elif route.action == "toggle_wake":
            yield "Wake word mode toggled, sir."
        elif route.action == "toggle_voice":
            yield "Voice mode toggled, sir."
        elif route.action == "toggle_tts":
            tts_eng = orchestrator.get_tts()
            tts_eng.enabled = not tts_eng.enabled
            state = "ENABLED" if tts_eng.enabled else "DISABLED"
            yield f"Speech output (TTS) {state}, sir."
        elif route.action == "list_devices":
            try:
                import sounddevice as sd
                devices = sd.query_devices()
                curr_dev = orchestrator.settings.audio_device
                lines = ["Audio Input Devices:"]
                for idx, d in enumerate(devices):
                    if d["max_input_channels"] > 0:
                        api = sd.query_hostapis(d["hostapi"])["name"]
                        is_sel = " [CONFIGURED]" if curr_dev == idx else ""
                        is_def = " [SYS DEFAULT]" if idx == sd.default.device[0] else ""
                        lines.append(
                            f"  [{idx:2d}] {d['name'][:35]:35s} | API: {api:16s} | in_ch: {d['max_input_channels']}{is_sel}{is_def}"
                        )
                lines.append("\nTip: Set JARVIS_AUDIO_DEVICE=<number> in .env to pin a specific microphone.")
                yield "\n".join(lines)
            except Exception as e:
                yield f"Error querying audio devices: {e}"
        elif route.action == "exit":
            orchestrator.state.is_running = False
            yield "Shutting down. Good day, sir."

    return route, _terminal_gen()
