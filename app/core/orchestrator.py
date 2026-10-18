"""Orchestrator coordinating input routing, LLM generation, and response delivery.

Follows Section 3.2 & AGENTS.md modular architecture by delegating domain logic
to clean handler modules in app.core.handlers.
"""

import time
from typing import Any, Dict, Generator, Optional, Tuple

from app.ai.llm import OllamaClient
from app.ai.prompts import get_system_prompt
from app.core.config import Settings, get_settings
from app.core.handlers import (
    handle_ai_request,
    handle_clarification,
    handle_fast_command,
    handle_pending_confirmation,
    handle_pending_vision_task,
    handle_screen_read,
    handle_terminal_command,
    handle_web_dependent,
    handle_web_search,
)
from app.core.logger import setup_logger
from app.core.router import CommandRouter, RouteResult, RouteType
from app.core.state import SessionState
from app.voice.speech_to_text import SpeechToText
from app.voice.text_to_speech import TextToSpeech

logger = setup_logger("jarvis.orchestrator")


class Orchestrator:
    """Coordinates message processing between Router, LLM, STT, TTS, State, and Handlers."""

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
        self._explicit_llm = llm_client is not None
        from app.ai.interpreter import ActionInterpreter
        self.interpreter = ActionInterpreter(settings=self.settings)
        from app.core.proactive_agent import ProactiveAgent
        self.proactive_agent = ProactiveAgent(settings=self.settings, orchestrator=self)

    def is_voice_idle(self) -> bool:
        """Returns True if the assistant is not actively speaking, recording, or processing."""
        if getattr(self.state, "is_processing", False):
            return False
        if getattr(self.state, "pending_action", None) is not None:
            return False
        try:
            if self.wake_word and hasattr(self.wake_word, "is_busy") and callable(self.wake_word.is_busy) and self.wake_word.is_busy():
                return False
        except Exception:
            pass
        try:
            if self.tts and hasattr(self.tts, "is_speaking") and callable(self.tts.is_speaking) and self.tts.is_speaking():
                return False
        except Exception:
            pass
        return True

    def check_proactive_initiative(self) -> Optional[Any]:
        """Queries the proactive agent for any context-driven initiative."""
        if hasattr(self, "proactive_agent") and self.proactive_agent:
            return self.proactive_agent.check_context()
        return None

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

    def stop_speech(self) -> None:
        """Immediately halts TTS audio playback and sets speech state to idle."""
        try:
            if self.settings.tts_enabled and self.tts is not None:
                self.tts.stop()
        except Exception as e:
            logger.warning("Error stopping TTS speech: %s", e)


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

    def transcribe_audio(self, audio: Any, language: Optional[str] = None) -> Tuple[str, dict]:
        """Transcribes raw audio array to text using the STT subsystem."""
        stt_engine = self.get_stt()
        text, info = stt_engine.transcribe(audio, language=language)
        if text and not self.state.language_override:
            from app.voice.text_to_speech import resolve_conversation_language
            self.state.conversation_language = resolve_conversation_language(
                text, self.state.conversation_language
            )
        return text, info

    def process_command(
        self, user_input: str
    ) -> Tuple[RouteResult, Generator[str, None, None]]:
        """Processes user command string. Alias for process_input_stream for external IPC callers."""
        return self.process_input_stream(user_input)

    def process_input_stream(
        self, user_input: str
    ) -> Tuple[RouteResult, Generator[str, None, None]]:
        """Processes user input and returns a generator streaming the assistant's reply.

        Coordinates language resolution, confirmations, command routing, and handler dispatch.
        """
        # Determine conversation language with hysteresis
        if self.state.language_override:
            effective_lang = self.state.language_override
        else:
            from app.voice.text_to_speech import resolve_conversation_language
            effective_lang = resolve_conversation_language(
                user_input, current_lang=self.state.conversation_language
            )
            self.state.conversation_language = effective_lang

        is_id = effective_lang.startswith("id")

        # 0. Check pending action requiring confirmation
        pending_res = handle_pending_confirmation(self, user_input, effective_lang, is_id)
        if pending_res is not None:
            return pending_res

        # 0.1 Check active paused vision task awaiting user parameter
        vision_res = handle_pending_vision_task(self, user_input, effective_lang, is_id)
        if vision_res is not None:
            return vision_res

        # Route user command
        route = self.router.route(user_input)
        route.args["language"] = effective_lang

        # Structured Router Log
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

        # 0.5 Handle clarification requests for ambiguous commands
        if route.route_type == RouteType.CLARIFY:
            return handle_clarification(self, route, user_input, effective_lang, is_id)

        # 1. Handle Terminal built-in commands
        if route.route_type == RouteType.TERMINAL_COMMAND:
            return handle_terminal_command(self, route, user_input, effective_lang, is_id)

        # 2. Handle Fast Commands (System / Automation Tools)
        if route.route_type == RouteType.FAST_COMMAND:
            return handle_fast_command(self, route, user_input, effective_lang, is_id)

        # 3. Handle On-Demand Screen Reading
        if route.route_type == RouteType.SCREEN_READ:
            return handle_screen_read(self, route, user_input, effective_lang, is_id)

        # 4. Handle Dedicated Search-First Requests (Deterministic, Zero LLM Calls)
        if route.route_type == RouteType.WEB_SEARCH:
            return handle_web_search(self, route, user_input, effective_lang, is_id)

        # 5. Handle Web-dependent requests (Weather, breaking news, etc.)
        if route.route_type == RouteType.WEB_DEPENDENT:
            return handle_web_dependent(self, route, user_input, effective_lang, is_id)

        # 6. Handle AI reasoning request (Action Interpreter / Local LLM)
        return handle_ai_request(self, route, user_input, effective_lang, is_id)
