"""Orchestrator coordinating input routing, LLM generation, and response delivery."""

import re
import time
from typing import Any, Callable, Dict, Generator, Optional, Tuple

from app.ai.llm import LLMError, OllamaClient, OllamaConnectionError, OllamaModelNotFoundError
from app.ai.prompts import get_system_prompt
from app.core.config import Settings, get_settings
from app.core.logger import setup_logger
from app.core.router import CommandRouter, ExecutionStatus, RouteResult, RouteType, ToolExecutionResult
from app.core.state import SessionState
from app.voice.speech_to_text import SpeechToText
from app.voice.text_to_speech import TextToSpeech

logger = setup_logger("jarvis.orchestrator")


class Orchestrator:
    """Coordinates message processing between Router, LLM, STT, TTS, and State."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[OllamaClient] = None,
        stt_client: Optional[SpeechToText] = None,
        tts_client: Optional[TextToSpeech] = None,
        wake_word_client: Optional[Any] = None,
    ):
        self.settings = settings or get_settings()
        self.llm = llm_client or OllamaClient(
            base_url=self.settings.ollama_url,
            model=self.settings.model,
            keep_alive=self.settings.keep_alive,
            think_mode=self.settings.think_mode,
            temperature=self.settings.temperature,
        )
        self.stt = stt_client
        self.tts = tts_client
        self.wake_word = wake_word_client
        self.router = CommandRouter()
        self.state = SessionState(system_prompt=get_system_prompt())

    def get_stt(self) -> SpeechToText:
        """Returns the active Speech-to-Text instance (lazy-loaded)."""
        if self.stt is None:
            self.stt = SpeechToText(self.settings)
        return self.stt

    def get_tts(self) -> TextToSpeech:
        """Returns the active Text-to-Speech instance (lazy-loaded)."""
        if self.tts is None:
            self.tts = TextToSpeech(self.settings)
        return self.tts

    def get_wake_word(self) -> Any:
        """Returns the active WakeWordDetector instance (lazy-loaded)."""
        if self.wake_word is None:
            from app.voice.wake_word import WakeWordDetector
            self.wake_word = WakeWordDetector(self.settings)
        return self.wake_word

    def get_system_status(self) -> Dict[str, Any]:
        """Returns health and status details of JARVIS components."""
        server_ok = self.llm.is_server_available()
        model_ok = self.llm.is_model_available() if server_ok else False
        stt_loaded = self.stt.is_loaded() if self.stt is not None else False
        tts_loaded = self.tts.is_loaded() if self.tts is not None else False
        wake_active = self.wake_word is not None and self.wake_word.is_listening()
        return {
            "name": self.settings.jarvis_name,
            "model": self.settings.model,
            "ollama_url": self.settings.ollama_url,
            "ollama_connected": server_ok,
            "model_ready": model_ok,
            "history_length": len(self.state.history),
            "voice_enabled": self.settings.voice_enabled,
            "stt_model": self.settings.stt_model,
            "stt_loaded": stt_loaded,
            "tts_enabled": self.settings.tts_enabled,
            "tts_model": self.settings.tts_model_en,
            "tts_loaded": tts_loaded,
            "wake_word_enabled": self.settings.wake_word_enabled,
            "wake_word_model": self.settings.wake_word_model,
            "wake_word_active": wake_active,
        }

    def transcribe_audio(self, audio: Any) -> Tuple[str, dict]:
        """Transcribes raw audio array to text using the STT subsystem."""
        stt_engine = self.get_stt()
        text, info = stt_engine.transcribe(audio)
        if text and not self.state.language_override:
            from app.voice.text_to_speech import resolve_conversation_language
            self.state.conversation_language = resolve_conversation_language(
                text, self.state.conversation_language
            )
        return text, info

    def process_input_stream(
        self, user_input: str
    ) -> Tuple[RouteResult, Generator[str, None, None]]:
        """Processes user input and returns a generator streaming the assistant's reply.

        Returns:
            Tuple of (RouteResult, token_generator).
        """
        start_time = time.time()

        # Determine conversation language with hysteresis:
        # Explicit override takes priority; otherwise use resolve_conversation_language
        if self.state.language_override:
            effective_lang = self.state.language_override
        else:
            from app.voice.text_to_speech import resolve_conversation_language
            effective_lang = resolve_conversation_language(
                user_input, current_lang=self.state.conversation_language
            )
            self.state.conversation_language = effective_lang

        is_id = effective_lang.startswith("id")

        # 0. Check if there is an active pending action requiring confirmation
        if self.state.pending_action:
            pending = self.state.pending_action
            cleaned_lower = user_input.strip().lower()

            _AFFIRMATIVES = {
                "ya", "yes", "y", "buka", "lanjut", "lanjutkan", "oke", "ok",
                "sure", "proceed", "confirm", "silakan", "buka saja", "boleh"
            }
            _NEGATIVES = {
                "tidak", "batal", "batalkan", "jangan", "no", "cancel",
                "stop", "nevermind", "enggak", "gak", "nanti saja"
            }

            words_set = set(re.findall(r"\b[a-z]+\b", cleaned_lower))
            is_confirmed = bool(words_set & _AFFIRMATIVES) or cleaned_lower in _AFFIRMATIVES
            is_cancelled = bool(words_set & _NEGATIVES) or cleaned_lower in _NEGATIVES

            if is_confirmed:
                self.state.pending_action = None
                def _confirm_gen():
                    if pending.action == "open_application":
                        from app.tools.apps import launch_application
                        t_tool_start = time.time()
                        try:
                            success, display_name, msg = launch_application(pending.target)
                            elapsed_ms = (time.time() - t_tool_start) * 1000.0
                            self.state.set_last_action("open_application", pending.target, display_name, success)
                            if success:
                                logger.info('[TOOL] name="open_application" target="%s" status="SUCCESS" latency=%.1fms', pending.target, elapsed_ms)
                                out = f"Membuka {display_name}, sir." if is_id else f"Opening {display_name}, sir."
                            else:
                                logger.warning('[TOOL] name="open_application" target="%s" status="FAILURE" error="%s" latency=%.1fms', pending.target, msg, elapsed_ms)
                                retry_txt = " Silakan periksa kembali atau coba ulangi perintah, sir." if is_id else " Please check if it is installed or try again, sir."
                                out = f"Maaf sir, saya tidak dapat membuka {display_name}. {msg}.{retry_txt}" if is_id else f"I couldn't open {display_name}, sir. {msg}.{retry_txt}"
                        except Exception as exc:
                            elapsed_ms = (time.time() - t_tool_start) * 1000.0
                            logger.exception('[TOOL] name="open_application" target="%s" status="FAILURE" exception="%s"', pending.target, exc)
                            out = f"Terjadi kesalahan saat membuka {pending.display_name}, sir: {exc}" if is_id else f"An error occurred while opening {pending.display_name}, sir: {exc}"
                        self.state.add_turn(user_input, out)
                        yield out

                route = RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action=f"confirm_{pending.action}",
                    args={"target": pending.target, "language": effective_lang},
                    raw_input=user_input,
                    description=f"Confirmed {pending.action} for {pending.target}",
                )
                return route, _confirm_gen()

            elif is_cancelled:
                self.state.pending_action = None
                logger.info('[TOOL] name="%s" target="%s" status="CANCELLED"', pending.action, pending.target)
                def _cancel_gen():
                    out = (
                        f"Baik sir, pembukaan {pending.display_name} dibatalkan."
                        if is_id
                        else f"Understood, sir. {pending.display_name} launch cancelled."
                    )
                    self.state.add_turn(user_input, out)
                    yield out

                route = RouteResult(
                    route_type=RouteType.FAST_COMMAND,
                    action=f"cancel_{pending.action}",
                    args={"target": pending.target, "language": effective_lang},
                    raw_input=user_input,
                    description=f"Cancelled {pending.action} for {pending.target}",
                )
                return route, _cancel_gen()
            else:
                # If neither clear confirmation nor cancellation, cancel pending action and proceed
                self.state.pending_action = None

        route = self.router.route(user_input)
        route.args["language"] = effective_lang

        # Structured Router Log (Task 5)
        if route.route == "LLM":
            logger.info('[ROUTER] input="%s" route="LLM"', user_input)
        else:
            logger.info(
                '[ROUTER] input="%s" normalized="%s" intent="%s" route="%s"',
                user_input,
                route.normalized_input,
                route.intent,
                route.route,
            )

        # 0.5 Handle Clarification requests for ambiguous commands (Task 2)
        if route.route_type == RouteType.CLARIFY:
            def _clarify_gen():
                if route.action == "clarify_open":
                    out = (
                        "Aplikasi atau situs apa yang ingin Anda buka, sir?"
                        if is_id
                        else "Which application or website would you like me to open, sir?"
                    )
                elif route.action == "clarify_close":
                    out = (
                        "Aplikasi apa yang ingin Anda tutup, sir?"
                        if is_id
                        else "Which application would you like me to close, sir?"
                    )
                else:
                    out = (
                        "Mohon jelaskan perintah Anda lebih spesifik, sir."
                        if is_id
                        else "Please specify your request further, sir."
                    )
                self.state.add_turn(user_input, out)
                yield out

            return route, _clarify_gen()

        # 1. Handle Terminal built-in commands
        if route.route_type == RouteType.TERMINAL_COMMAND:
            def _terminal_gen():
                if route.action == "help":
                    yield (
                        "Commands available:\n"
                        "  /help, help        - Show this help message\n"
                        "  /status, status    - Show system and model status\n"
                        "  /diag, /diagnostics- Show detailed system, audio, and performance diagnostics\n"
                        "  /reset             - Reset conversation context and state\n"
                        "  /lang [id|en|auto] - Set interaction language mode\n"
                        "  /wake, /wakeword   - Toggle Always-Listening Wake-Word mode\n"
                        "  /voice, /ptt       - Toggle Push-to-Talk voice mode\n"
                        "  /tts, tts          - Toggle spoken Text-to-Speech output\n"
                        "  /mic, /devices     - List microphone audio devices\n"
                        "  /clear, clear      - Clear conversation history\n"
                        "  /exit, quit        - Exit JARVIS"
                    )
                elif route.action == "show_diagnostics":
                    from app.core.diagnostics import format_diagnostics_text, generate_diagnostics_report
                    rep = generate_diagnostics_report(self)
                    yield format_diagnostics_text(rep)
                elif route.action == "reset_context":
                    self.state.clear()
                    yield "Session context and conversation history reset, sir."

                elif route.action == "set_language":
                    target_l = route.args.get("language", "toggle").lower()
                    if target_l in ("id", "indonesia", "indonesian"):
                        self.state.language_override = "id"
                        self.state.conversation_language = "id"
                        yield "Bahasa interaksi diatur ke Bahasa Indonesia, sir."
                    elif target_l in ("en", "english"):
                        self.state.language_override = "en"
                        self.state.conversation_language = "en"
                        yield "Interaction language set to English, sir."
                    elif target_l in ("auto", "reset"):
                        self.state.language_override = None
                        yield "Language mode set to automatic detection, sir."
                    else:
                        curr = self.state.language_override or f"auto ({self.state.conversation_language})"
                        yield f"Current language mode: {curr}. Use '/lang id', '/lang en', or '/lang auto'."
                elif route.action == "clear":
                    self.state.clear()
                    yield "Conversation history cleared, sir."
                elif route.action == "status":
                    status = self.get_system_status()
                    conn_sym = "ONLINE" if status["ollama_connected"] else "OFFLINE"
                    mod_sym = "READY" if status["model_ready"] else "NOT FOUND"
                    voice_sym = "ENABLED" if status["voice_enabled"] else "DISABLED"
                    tts_sym = "ENABLED" if status["tts_enabled"] else "DISABLED"
                    wake_sym = "ACTIVE" if status.get("wake_word_active") else ("ENABLED" if status.get("wake_word_enabled") else "STANDBY")
                    lang_status = self.state.language_override or f"auto ({self.state.conversation_language})"
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
                    tts_eng = self.get_tts()
                    tts_eng.enabled = not tts_eng.enabled
                    state = "ENABLED" if tts_eng.enabled else "DISABLED"
                    yield f"Speech output (TTS) {state}, sir."
                elif route.action == "list_devices":
                    try:
                        import sounddevice as sd
                        devices = sd.query_devices()
                        curr_dev = self.settings.audio_device
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
                    self.state.is_running = False
                    yield "Shutting down. Good day, sir."

            return route, _terminal_gen()

        # 2. Handle Fast Commands (System / Automation Tools & Instant Local Queries)
        if route.route_type == RouteType.FAST_COMMAND:
            def _fast_command_gen():
                target = route.args.get("target", "")
                reply_chunks = []

                # Contextual pronoun resolution (e.g. "tutup aplikasinya", "close it", "tutup yang tadi")
                if target.lower() in ("it", "aplikasinya", "yang tadi", "programnya", "the app", "aplikasi tadi"):
                    last_target = self.state.get_last_action_target()
                    if last_target:
                        target = last_target

                tool_start = time.time()

                if route.action == "open_application":
                    from app.tools.apps import launch_application
                    # Sensitive applications check: WhatsApp accesses private communications
                    if target.lower() in ("whatsapp",):
                        from app.core.state import PendingAction
                        self.state.pending_action = PendingAction(
                            action="open_application",
                            target=target,
                            display_name="WhatsApp",
                        )
                        logger.info('[TOOL] name="open_application" target="whatsapp" status="CONFIRMATION_REQUIRED"')
                        out = (
                            "Membuka WhatsApp dapat mengakses data pesan pribadi Anda, sir. Apakah Anda yakin ingin melanjutkannya?"
                            if is_id
                            else "Opening WhatsApp will access your personal messages, sir. Are you sure you want to proceed?"
                        )
                        reply_chunks.append(out)
                        self.state.add_turn(user_input, out)
                        yield out
                        return

                    try:
                        success, display_name, msg = launch_application(target)
                        elapsed_ms = (time.time() - tool_start) * 1000.0
                        self.state.set_last_action("open_application", target, display_name, success)
                        if success:
                            logger.info(
                                '[TOOL] name="open_application" target="%s" status="SUCCESS" latency=%.1fms',
                                target,
                                elapsed_ms,
                            )
                            out = f"Membuka {display_name}, sir." if is_id else f"Opening {display_name}, sir."
                        else:
                            logger.warning(
                                '[TOOL] name="open_application" target="%s" status="FAILURE" error="%s" latency=%.1fms',
                                target,
                                msg,
                                elapsed_ms,
                            )
                            retry_txt = " Silakan periksa atau coba ulangi perintah, sir." if is_id else " Please check if it is installed or try again, sir."
                            out = (
                                f"Maaf sir, saya tidak dapat membuka {display_name}. {msg}.{retry_txt}"
                                if is_id
                                else f"I couldn't open {display_name}, sir. {msg}.{retry_txt}"
                            )
                    except Exception as exc:
                        elapsed_ms = (time.time() - tool_start) * 1000.0
                        logger.exception('[TOOL] name="open_application" target="%s" status="FAILURE" exception="%s"', target, exc)
                        out = (
                            f"Terjadi kesalahan saat membuka {target}, sir: {exc}. Silakan coba lagi."
                            if is_id
                            else f"An error occurred while opening {target}, sir: {exc}. Please try again."
                        )
                    reply_chunks.append(out)
                    yield out

                elif route.action == "open_website":
                    from app.tools.browser import launch_website
                    try:
                        success, display_name, url, msg = launch_website(target)
                        elapsed_ms = (time.time() - tool_start) * 1000.0
                        self.state.set_last_action("open_website", "chrome", display_name, success)
                        if success:
                            logger.info(
                                '[TOOL] name="open_website" target="%s" status="SUCCESS" latency=%.1fms',
                                target,
                                elapsed_ms,
                            )
                            out = f"Membuka {display_name}, sir." if is_id else f"Opening {display_name}, sir."
                        else:
                            logger.warning(
                                '[TOOL] name="open_website" target="%s" status="FAILURE" error="%s" latency=%.1fms',
                                target,
                                msg,
                                elapsed_ms,
                            )
                            retry_txt = " Anda dapat mencoba mengulang perintah ini, sir." if is_id else " You can try asking again, sir."
                            out = (
                                f"Maaf sir, saya tidak dapat membuka {display_name}. {msg}.{retry_txt}"
                                if is_id
                                else f"I couldn't open {display_name}, sir. {msg}.{retry_txt}"
                            )
                    except Exception as exc:
                        elapsed_ms = (time.time() - tool_start) * 1000.0
                        logger.exception('[TOOL] name="open_website" target="%s" status="FAILURE" exception="%s"', target, exc)
                        out = (
                            f"Terjadi kesalahan saat membuka situs {target}, sir: {exc}. Silakan coba lagi."
                            if is_id
                            else f"An error occurred while opening website {target}, sir: {exc}. Please try again."
                        )
                    reply_chunks.append(out)
                    yield out

                elif route.action == "close_application":
                    from app.tools.apps import close_application
                    if not target or target.lower() in ("it", "aplikasinya", "yang tadi"):
                        out = "Tidak ada aplikasi yang terlacak dalam sesi ini, sir." if is_id else "No active application was tracked in this session, sir."
                        reply_chunks.append(out)
                        yield out
                    else:
                        try:
                            success, display_name, msg = close_application(target)
                            elapsed_ms = (time.time() - tool_start) * 1000.0
                            self.state.set_last_action("close_application", target, display_name, success)
                            if success:
                                logger.info(
                                    '[TOOL] name="close_application" target="%s" status="SUCCESS" latency=%.1fms',
                                    target,
                                    elapsed_ms,
                                )
                                out = f"Menutup {display_name}, sir." if is_id else f"Closing {display_name}, sir."
                            else:
                                logger.info(
                                    '[TOOL] name="close_application" target="%s" status="FAILURE" error="%s" latency=%.1fms',
                                    target,
                                    msg,
                                    elapsed_ms,
                                )
                                out = f"Maaf sir, {display_name} tidak sedang berjalan." if is_id else f"Application {display_name} is not currently running, sir."
                        except Exception as exc:
                            elapsed_ms = (time.time() - tool_start) * 1000.0
                            logger.exception('[TOOL] name="close_application" target="%s" status="FAILURE" exception="%s"', target, exc)
                            out = (
                                f"Terjadi kesalahan saat menutup {target}, sir: {exc}"
                                if is_id
                                else f"An error occurred while closing {target}, sir: {exc}"
                            )
                        reply_chunks.append(out)
                        yield out

                elif route.action == "get_time":
                    from app.tools.datetime_tool import get_current_time
                    out = get_current_time(lang=effective_lang)
                    self.state.set_last_action("get_time", "time", "Time", True)
                    logger.info('[TOOL] name="get_time" status="SUCCESS"')
                    reply_chunks.append(out)
                    yield out

                elif route.action == "get_date":
                    from app.tools.datetime_tool import get_current_date
                    out = get_current_date(lang=effective_lang)
                    self.state.set_last_action("get_date", "date", "Date", True)
                    logger.info('[TOOL] name="get_date" status="SUCCESS"')
                    reply_chunks.append(out)
                    yield out

                elif route.action == "system_info":
                    from app.tools.windows import get_hardware_specs
                    specs = get_hardware_specs()
                    if is_id:
                        out = (
                            f"Sistem berjalan pada {specs['os']} {specs['os_release']}, "
                            f"prosesor {specs['processor']}, {specs['cpu_count_logical']} threads, "
                            f"penggunaan RAM {specs['ram_percent']}% ({specs['ram_used_gb']} dari {specs['ram_total_gb']} GB), sir."
                        )
                    else:
                        out = (
                            f"System running on {specs['os']} {specs['os_release']}, "
                            f"processor {specs['processor']}, {specs['cpu_count_logical']} threads, "
                            f"RAM usage at {specs['ram_percent']}% ({specs['ram_used_gb']} of {specs['ram_total_gb']} GB), sir."
                        )
                    self.state.set_last_action("system_info", "system", "System", True)
                    logger.info('[TOOL] name="system_info" status="SUCCESS"')
                    reply_chunks.append(out)
                    yield out

                elif route.action == "battery_status":
                    from app.tools.windows import get_battery_status
                    batt = get_battery_status()
                    if batt["has_battery"]:
                        mode = (
                            ("sedang mengisi daya AC" if batt["power_plugged"] else "menggunakan baterai")
                            if is_id
                            else ("charging on AC power" if batt["power_plugged"] else "running on battery")
                        )
                        out = (
                            f"Baterai berada pada level {batt['percent']}%, {mode}, sir."
                            if is_id
                            else f"Battery is at {batt['percent']}%, currently {mode}, sir."
                        )
                    else:
                        out = (
                            "Perangkat terhubung langsung ke daya listrik AC tanpa baterai internal, sir."
                            if is_id
                            else "Device is connected directly to AC power with no internal battery, sir."
                        )
                    self.state.set_last_action("battery_status", "battery", "Battery", True)
                    logger.info('[TOOL] name="battery_status" status="SUCCESS"')
                    reply_chunks.append(out)
                    yield out

                elif route.action == "take_screenshot":
                    from app.tools.windows import take_screenshot
                    success, path, msg = take_screenshot()
                    self.state.set_last_action("take_screenshot", "screen", "Screenshot", success)
                    if success:
                        out = f"Tangkapan layar berhasil disimpan di {path}, sir." if is_id else f"Screenshot saved successfully to {path}, sir."
                    else:
                        out = f"Gagal mengambil tangkapan layar, sir: {msg}" if is_id else f"Failed to take screenshot, sir: {msg}"
                    logger.info('[TOOL] name="take_screenshot" status="%s"', "SUCCESS" if success else "FAILURE")
                    reply_chunks.append(out)
                    yield out

                elif route.action == "lock_screen":
                    from app.tools.windows import lock_windows
                    success, msg = lock_windows()
                    self.state.set_last_action("lock_screen", "windows", "Lock", success)
                    if success:
                        out = "Mengunci workstation Windows, sir." if is_id else "Locking Windows workstation, sir."
                    else:
                        out = f"Gagal mengunci komputer, sir: {msg}" if is_id else f"Failed to lock computer, sir: {msg}"
                    logger.info('[TOOL] name="lock_screen" status="%s"', "SUCCESS" if success else "FAILURE")
                    reply_chunks.append(out)
                    yield out

                elif route.action == "volume_up":
                    from app.tools.music import change_volume
                    change_volume("up")
                    out = "Menaikkan volume suara, sir." if is_id else "Increasing volume, sir."
                    logger.info('[TOOL] name="volume_up" status="SUCCESS"')
                    reply_chunks.append(out)
                    yield out

                elif route.action == "volume_down":
                    from app.tools.music import change_volume
                    change_volume("down")
                    out = "Menurunkan volume suara, sir." if is_id else "Decreasing volume, sir."
                    logger.info('[TOOL] name="volume_down" status="SUCCESS"')
                    reply_chunks.append(out)
                    yield out

                elif route.action == "toggle_mute":
                    from app.tools.music import change_volume
                    change_volume("mute")
                    out = "Mengalihkan status senyap, sir." if is_id else "Toggling mute, sir."
                    logger.info('[TOOL] name="toggle_mute" status="SUCCESS"')
                    reply_chunks.append(out)
                    yield out

                elif route.action in ("media_play_pause", "media_next", "media_previous", "media_stop"):
                    from app.tools.music import media_next, media_play_pause, media_previous, media_stop
                    if route.action == "media_play_pause":
                        media_play_pause()
                        out = "Memutar atau menjeda media, sir." if is_id else "Toggled media playback, sir."
                    elif route.action == "media_next":
                        media_next()
                        out = "Memutar lagu berikutnya, sir." if is_id else "Playing next track, sir."
                    elif route.action == "media_previous":
                        media_previous()
                        out = "Memutar lagu sebelumnya, sir." if is_id else "Playing previous track, sir."
                    elif route.action == "media_stop":
                        media_stop()
                        out = "Menghentikan pemutaran media, sir." if is_id else "Stopped media playback, sir."
                    logger.info('[TOOL] name="%s" status="SUCCESS"', route.action)
                    reply_chunks.append(out)
                    yield out

                elif route.action == "play_music":
                    from app.tools.music import play_music
                    query = route.args.get("query", "")
                    provider = route.args.get("provider", "auto")
                    success, p_used, msg = play_music(query=query, provider=provider)
                    self.state.set_last_action("play_music", query, "Music", success)
                    if success:
                        if query:
                            out = f"Memutar '{query}' melalui {p_used}, sir." if is_id else f"Playing '{query}' via {p_used}, sir."
                        else:
                            out = f"Melanjutkan pemutaran musik melalui {p_used}, sir." if is_id else f"Resuming playback via {p_used}, sir."
                    else:
                        out = f"Maaf sir, tidak dapat memutar musik: {msg}" if is_id else f"Could not play music, sir: {msg}"
                    logger.info('[TOOL] name="play_music" query="%s" provider="%s" status="%s"', query, p_used, "SUCCESS" if success else "FAILURE")
                    reply_chunks.append(out)
                    yield out

                elif route.action == "open_folder":
                    from app.tools.filesystem import open_folder
                    folder_target = route.args.get("target", "") or target
                    success, disp_name, f_path, msg = open_folder(folder_target)
                    self.state.set_last_action("open_folder", folder_target, disp_name, success)
                    if success:
                        out = f"Membuka folder {disp_name}, sir." if is_id else f"Opening {disp_name} folder, sir."
                    else:
                        out = f"Maaf sir, tidak dapat membuka folder {disp_name}: {msg}" if is_id else f"Could not open {disp_name} folder, sir: {msg}"
                    logger.info('[TOOL] name="open_folder" target="%s" status="%s"', folder_target, "SUCCESS" if success else "FAILURE")
                    reply_chunks.append(out)
                    yield out

                elif route.action == "search_web":
                    from app.tools.browser_agent import answer_search_query, open_search_in_browser
                    query = route.args.get("query", "") or target
                    open_b = route.args.get("open_browser", False)
                    if open_b or not query:
                        open_search_in_browser(query or "berita terbaru")
                        out = f"Membuka pencarian '{query}' di Chrome, sir." if is_id else f"Opening search for '{query}' in Chrome, sir."
                    else:
                        ans = answer_search_query(query, language=effective_lang)
                        self.state.set_last_search(
                            query=ans.query,
                            spoken_answer=ans.spoken_answer,
                            display_answer=ans.display_answer,
                            sources=ans.sources,
                        )
                        out = ans.display_answer
                    self.state.set_last_action("search_web", query, "Web Search", True)
                    logger.info('[TOOL] name="search_web" query="%s" status="SUCCESS"', query)
                    reply_chunks.append(out)
                    yield out

                elif route.action == "read_search_result":
                    last_search = self.state.get_last_search()
                    spoken = last_search.get("spoken_answer")
                    if spoken:
                        out = spoken
                    else:
                        out = "Belum ada hasil pencarian sebelumnya untuk dibacakan, sir." if is_id else "There is no previous search result to read, sir."
                    self.state.set_last_action("read_search_result", "search", "Search", bool(spoken))
                    logger.info('[TOOL] name="read_search_result" status="%s"', "SUCCESS" if spoken else "FAILURE")
                    reply_chunks.append(out)
                    yield out

                elif route.action == "list_search_sources":
                    last_search = self.state.get_last_search()
                    sources = last_search.get("sources", [])
                    if sources:
                        domains = [s.get("domain", "") for s in sources if s.get("domain")]
                        dom_str = ", ".join(domains[:3])
                        spoken_lead = f"Sumber pencarian berasal dari {dom_str}, sir." if is_id else f"Search sources are from {dom_str}, sir."
                        lines = [spoken_lead, "", "Sumber:" if is_id else "Sources:"]
                        for i, s in enumerate(sources[:5], 1):
                            lines.append(f"{i}. {s.get('title', 'Result')} - {s.get('url', '')}")
                        out = "\n".join(lines)
                    else:
                        out = "Belum ada sumber pencarian sebelumnya yang tersimpan, sir." if is_id else "No search sources are stored in the current session, sir."
                    self.state.set_last_action("list_search_sources", "search", "Search", bool(sources))
                    logger.info('[TOOL] name="list_search_sources" status="%s"', "SUCCESS" if sources else "FAILURE")
                    reply_chunks.append(out)
                    yield out

                elif route.action == "open_search_source":
                    from app.tools.browser import launch_website
                    last_search = self.state.get_last_search()
                    sources = last_search.get("sources", [])
                    idx = route.args.get("index", 1) - 1
                    if 0 <= idx < len(sources):
                        target_url = sources[idx].get("url") or ""
                        target_title = sources[idx].get("title", f"Sumber #{idx+1}")
                        if target_url:
                            ok, disp, final_url, msg = launch_website(target_url)
                            if ok:
                                out = f"Membuka sumber ke-{idx+1} ({target_title}) di browser, sir." if is_id else f"Opening source #{idx+1} ({target_title}) in your browser, sir."
                            else:
                                out = f"Gagal membuka tautan {target_url}, sir: {msg}" if is_id else f"Failed to open link {target_url}, sir: {msg}"
                        else:
                            out = f"Tautan untuk sumber ke-{idx+1} tidak valid, sir." if is_id else f"Link for source #{idx+1} is invalid, sir."
                    else:
                        out = f"Sumber ke-{idx+1} tidak ditemukan dalam riwayat pencarian terakhir, sir." if is_id else f"Source #{idx+1} not found in last search results, sir."
                    self.state.set_last_action("open_search_source", str(idx+1), "Search Source", 0 <= idx < len(sources))
                    logger.info('[TOOL] name="open_search_source" index=%d status="%s"', idx+1, "SUCCESS" if (0 <= idx < len(sources)) else "FAILURE")
                    reply_chunks.append(out)
                    yield out

                elif route.action == "store_memory":
                    from app.memory.memory import save_user_memory
                    key = route.args.get("key", "catatan")
                    val = route.args.get("value", "")
                    success, msg = save_user_memory(key=key, value=val, user_input=user_input, language=effective_lang)
                    self.state.set_last_action("store_memory", key, "Memory", success)
                    logger.info('[TOOL] name="store_memory" key="%s" status="%s"', key, "SUCCESS" if success else "FAILURE")
                    reply_chunks.append(msg)
                    yield msg

                elif route.action == "recall_memories":
                    from app.memory.memory import recall_user_memories
                    query = route.args.get("query", "")
                    msg = recall_user_memories(query=query, language=effective_lang)
                    self.state.set_last_action("recall_memories", query, "Memory", True)
                    logger.info('[TOOL] name="recall_memories" query="%s" status="SUCCESS"', query)
                    reply_chunks.append(msg)
                    yield msg

                elif route.action == "forget_memory":
                    from app.memory.memory import forget_user_memory
                    key = route.args.get("key", "")
                    success, msg = forget_user_memory(key=key, language=effective_lang)
                    self.state.set_last_action("forget_memory", key, "Memory", success)
                    logger.info('[TOOL] name="forget_memory" key="%s" status="%s"', key, "SUCCESS" if success else "FAILURE")
                    reply_chunks.append(msg)
                    yield msg

                else:
                    out = f"Menjalankan perintah {route.action}, sir." if is_id else f"Executing {route.action}, sir."
                    logger.info('[TOOL] name="%s" status="SUCCESS"', route.action)
                    reply_chunks.append(out)
                    yield out

                # Record the completed fast command turn in session state history
                full_reply = "".join(reply_chunks)
                self.state.add_turn(user_input, full_reply)

            return route, _fast_command_gen()

        # 3. Handle On-Demand Screen Reading
        if route.route_type == RouteType.SCREEN_READ:
            def _screen_read_gen():
                from app.tools.screen_reader import read_screen_content
                pref_vis = route.args.get("prefer_vision", False)
                prompt = route.args.get("prompt", user_input)
                res = read_screen_content(
                    prompt=prompt,
                    language=effective_lang,
                    vision_enabled=pref_vis,
                    ollama_url=self.settings.ollama_url,
                )
                self.state.set_last_screen(
                    window_title=res.window_title,
                    text=res.text,
                    method=res.method,
                    spoken=res.spoken_summary,
                    display=res.display_text,
                )
                self.state.set_last_action("read_screen", res.window_title, "Screen Reader", res.success)
                logger.info(
                    '[TOOL] name="read_screen" method="%s" window="%s" latency=%.1fms status="%s"',
                    res.method,
                    res.window_title,
                    res.latency_ms,
                    "SUCCESS" if res.success else "FAILURE",
                )
                out = f"{res.spoken_summary}\n\n{res.display_text}"
                self.state.add_turn(user_input, out)
                yield out

            return route, _screen_read_gen()

        # 4. Handle Dedicated Search-First Requests (Deterministic, Zero LLM Calls)
        if route.route_type == RouteType.WEB_SEARCH:
            def _search_first_gen():
                from app.tools.browser_agent import answer_search_query, open_search_in_browser
                query = route.args.get("query", "") or user_input
                open_b = route.args.get("open_browser", False) or route.action == "open_search_results"

                if open_b:
                    open_search_in_browser(query)
                    out = (
                        f"Membuka hasil pencarian '{query}' di browser, sir."
                        if is_id
                        else f"Opening search results for '{query}' in your browser, sir."
                    )
                    self.state.set_last_action("open_search_results", query, "Web Browser", True)
                    self.state.add_turn(user_input, out)
                    yield out
                    return

                # Zero-LLM extractive factual search pipeline
                ans = answer_search_query(query, language=effective_lang)
                self.state.set_last_search(
                    query=ans.query,
                    spoken_answer=ans.spoken_answer,
                    display_answer=ans.display_answer,
                    sources=ans.sources,
                )
                self.state.set_last_action("search_web", query, "Search-First", bool(ans.sources))
                logger.info(
                    '[TOOL] name="search_web" query="%s" sources=%d latency=%.1fms status="%s"',
                    query,
                    len(ans.sources),
                    ans.latency_ms,
                    "SUCCESS" if ans.sources else "FAILURE",
                )
                out = ans.display_answer
                self.state.add_turn(user_input, out)
                yield out

            return route, _search_first_gen()

        # 5. Handle Web-dependent requests (e.g. Weather, breaking news, live scores)
        if route.route_type == RouteType.WEB_DEPENDENT:
            def _web_query_gen():
                from app.tools.browser_agent import answer_search_query
                query = route.args.get("query", "") or user_input
                ans = answer_search_query(query, language=effective_lang)
                self.state.set_last_search(
                    query=ans.query,
                    spoken_answer=ans.spoken_answer,
                    display_answer=ans.display_answer,
                    sources=ans.sources,
                )
                self.state.set_last_action("search_web", query, "Web Dependent", bool(ans.sources))
                logger.info(
                    '[TOOL] name="web_dependent" query="%s" sources=%d latency=%.1fms',
                    query,
                    len(ans.sources),
                    ans.latency_ms,
                )
                out = ans.display_answer
                self.state.add_turn(user_input, out)
                yield out

            return route, _web_query_gen()

        # 4. Handle AI reasoning request (routed to local LLM)
        from app.memory.memory import get_relevant_memories_prompt
        mem_prompt = get_relevant_memories_prompt(language=effective_lang)
        self.state.system_prompt = get_system_prompt(language=effective_lang) + mem_prompt
        self.state.add_message("user", user_input)
        messages = self.state.get_messages_for_llm()

        def _llm_gen():
            full_response = []
            try:
                for token in self.llm.chat_stream(messages):
                    full_response.append(token)
                    yield token

                complete_text = "".join(full_response)
                self.state.add_message("assistant", complete_text)
                elapsed = time.time() - start_time
                logger.info("LLM response generated in %.2fs", elapsed)

            except OllamaConnectionError:
                err_msg = (
                    "I am unable to connect to the local Ollama service. "
                    "Please ensure Ollama is running on your machine."
                )
                logger.error("Ollama connection error during chat.")
                yield err_msg
            except OllamaModelNotFoundError:
                err_msg = (
                    f"The configured model '{self.settings.model}' is not available in Ollama. "
                    f"Please run 'ollama pull {self.settings.model}'."
                )
                logger.error("Model '%s' not found.", self.settings.model)
                yield err_msg
            except LLMError as e:
                err_msg = f"I encountered an error while processing your request: {e}"
                logger.error("LLM processing error: %s", e)
                yield err_msg
            except Exception as e:
                err_msg = "An unexpected error occurred while communicating with the assistant."
                logger.exception("Unexpected error in LLM generation: %s", e)
                yield err_msg

        return route, _llm_gen()
