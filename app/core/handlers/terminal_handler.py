"""Terminal and REPL Command handler for JARVIS."""

from typing import Any, Generator, Tuple

from app.core.logger import setup_logger
from app.core.router import RouteResult

logger = setup_logger("jarvis.handlers.terminal")


def _get_jarvis_cheatsheet() -> str:
    """Returns the comprehensive, beautifully formatted JARVIS command cheatsheet."""
    return (
        "================================================================================\n"
        "                    ⚡ JARVIS // QUICK CHEATSHEET & COMMANDS ⚡\n"
        "================================================================================\n\n"
        "[ 🌐 WEB & BROWSING ]\n"
        "  • search <topik> / cari <topik> di google  -> Buka Google Search di browser & sumber senyap\n"
        "  • buka YouTube / buka GitHub / buka <url>  -> Buka website di browser default\n"
        "  • sumber 1 / tolong ke sumber pertama      -> Buka tautan sumber hasil pencarian\n\n"
        "[ 🎵 MULTIMEDIA & AUDIO ]\n"
        "  • play lagu <judul> / putar <video>        -> Putar audio/video YouTube secara instan\n"
        "  • pause / lanjutkan / stop musik           -> Kendalikan pemutaran media aktif\n"
        "  • volume up / volume down / volume 50%     -> Atur volume suara komputer\n"
        "  • mute / senyap / unmute                   -> Senyapkan / bunyikan audio Windows\n\n"
        "[ 📝 TODO & PROACTIVE REMINDERS ]\n"
        "  • catat todo: jam 14.20 beli makan         -> Catat to-do & otomatis ingatkan saat tiba\n"
        "  • tampilkan todo / daftar tugas            -> Lihat semua daftar tugas aktif\n"
        "  • selesaikan todo #1 / hapus todo #1       -> Tandai tugas selesai atau hapus\n\n"
        "[ 💻 KONTROL APLIKASI & WINDOWS ]\n"
        "  • buka Chrome / buka Spotify / buka VS Code-> Buka aplikasi komputer\n"
        "  • tutup Chrome / tutup Notepad             -> Tutup aplikasi komputer\n"
        "  • rapikan Downloads / rapikan Desktop      -> Janitor merapikan file berdasarkan ekstensi\n"
        "  • cek spesifikasi / info sistem            -> Lihat info CPU, RAM, OS, dan GPU\n"
        "  • kunci komputer / lock Windows            -> Kunci layar Windows 11\n"
        "  • take screenshot / ambil screenshot       -> Tangkap tangkapan layar desktop\n\n"
        "[ 👁️ VISION & INSPEKSI LAYAR ]\n"
        "  • baca layar / ada apa di layar?           -> Baca dan pahami teks pada jendela aktif\n"
        "  • ada error apa di layar?                  -> Diagnosa pesan error yang tampil di layar\n\n"
        "[ ⏹️ KONTROL SUARA & EMERGENCY STOP ]\n"
        "  • Tombol [Esc] atau tombol [⏹️ STOP]       -> Hentikan suara JARVIS seketika (0 ms)\n"
        "  • Kirim perintah baru saat bicara          -> Otomatis potong ucapan sebelumnya\n\n"
        "[ ⚡ TERMINAL & SLASH COMMANDS ]\n"
        "  • /cheat, /cheatsheet                      -> Tampilkan cheatsheet ini (senyap tanpa suara)\n"
        "  • /help                                    -> Ringkasan bantuan perintah sistem\n"
        "  • /status                                  -> Status sistem, model LLM, CPU & RAM\n"
        "  • /diag                                    -> Diagnostik performa latensi & audio\n"
        "  • /tts                                     -> Aktifkan / matikan keluaran suara (Piper TTS)\n"
        "  • /wake                                    -> Aktifkan / matikan deteksi 'Hey Jarvis'\n"
        "  • /clear                                   -> Bersihkan layar terminal console\n"
        "================================================================================"
    )


def handle_terminal_command(
    orchestrator: Any,
    route: RouteResult,
    user_input: str,
    effective_lang: str,
    is_id: bool,
) -> Tuple[RouteResult, Generator[str, None, None]]:
    """Handles terminal REPL built-in commands (/help, /status, /diag, /exit, etc.)."""
    def _terminal_gen():
        if route.action in ("cheatsheet", "cheat"):
            yield _get_jarvis_cheatsheet()
        elif route.action == "help":
            yield (
                "Commands available:\n"
                "  /cheat, /cheatsheet- Show comprehensive JARVIS command cheatsheet\n"
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
