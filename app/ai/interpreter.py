"""Performance-first Action Interpreter (Layer B & C).

Translates natural language user instructions into validated, structured action plans
using the local Qwen3 model via Ollama. Ensures actionable requests never silently
fall through into chat conversations, and rejects arbitrary shell code.
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.core.config import Settings, get_settings
from app.core.logger import setup_logger

logger = setup_logger("jarvis.ai.interpreter")

# Allowlisted intents and actions for Layer C plan validation
ALLOWLISTED_ACTIONS: Dict[str, List[str]] = {
    "media_control": ["pause", "resume", "play", "stop", "next", "previous", "volume_up", "volume_down", "mute"],
    "web_search": ["search", "open_search_results", "read_result", "list_sources", "open_source"],
    "page_reader": ["read_page", "summarize_page", "read_source"],
    "open_application": ["open", "close", "focus"],
    "open_website": ["open"],
    "desktop_control": ["click", "double_click", "right_click", "scroll", "type", "press_key", "shortcut"],
    "screen_read": ["inspect_screen", "ask_element", "read_error"],
    "system": ["time", "date", "battery", "lock", "screenshot", "system_info"],
    "task": ["execute_task", "continue", "retry"],
}


@dataclass
class InterpreterPlan:
    """Structured plan returned by the Action Interpreter."""
    type: str  # "action", "conversation", "clarify", "unsupported"
    intent: str = ""
    action: str = ""
    target: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    confidence: float = 1.0
    response: str = ""
    latency_ms: float = 0.0
    raw_output: str = ""

    @property
    def is_action(self) -> bool:
        return self.type == "action" and bool(self.action)


def build_interpreter_system_prompt(language: str = "id") -> str:
    """Builds a compact, instruction-dense system prompt for low-latency JSON classification."""
    is_id = language.lower().startswith("id")
    return (
        "You are JARVIS Action Interpreter on Windows 11.\n"
        "Your task is to classify user intent into a strict, single JSON object.\n"
        "Do NOT output markdown, explanations, or thinking blocks. Output ONLY valid JSON.\n\n"
        "JSON SCHEMA:\n"
        "{\n"
        '  "type": "action" | "conversation" | "clarify",\n'
        '  "intent": "media_control" | "web_search" | "page_reader" | "open_application" | "open_website" | "desktop_control" | "screen_read" | "system",\n'
        '  "action": "<allowlisted_action>",\n'
        '  "target": "<target_app_or_entity>",\n'
        '  "parameters": { ... },\n'
        '  "requires_confirmation": false,\n'
        '  "response": "<concise answer if type is conversation or clarify>"\n'
        "}\n\n"
        "RULES:\n"
        "1. If user wants to do something (open app, search web, control music, click, read page), type MUST be 'action'.\n"
        "2. Resolve pronouns ('it', 'that song', 'the article', 'the first result') using provided context.\n"
        "3. If user is asking a purely conversational or general knowledge question, type MUST be 'conversation'.\n"
        "4. If actionable request is completely ambiguous, type MUST be 'clarify'.\n"
        "5. Output compact JSON only."
    )


def build_interpreter_context_summary(state_context: Optional[Dict[str, Any]]) -> str:
    """Builds a concise summary of active conversation state for pronoun resolution."""
    if not state_context:
        return "Context: No active media or recent actions."

    parts = []
    if state_context.get("active_media"):
        parts.append(f"Active Media: {state_context['active_media']}")
    if state_context.get("last_action"):
        parts.append(f"Last Action: {state_context['last_action']}")
    if state_context.get("last_focused_element"):
        parts.append(f"Last Focused UI: {state_context['last_focused_element']}")
    if state_context.get("last_search_query"):
        parts.append(f"Last Search Query: '{state_context['last_search_query']}'")
    if state_context.get("last_search_sources"):
        sources = state_context["last_search_sources"]
        if isinstance(sources, list) and sources:
            parts.append(f"Search Results Available: {len(sources)} sources")
    if state_context.get("active_window"):
        parts.append(f"Active Window: {state_context['active_window']}")

    return "Context: " + " | ".join(parts) if parts else "Context: Clean state."


class ActionInterpreter:
    """Context and Action Interpreter using local Ollama model."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        ollama_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        temperature: Optional[float] = None,
    ):
        self.settings = settings or get_settings()
        self.ollama_url = ollama_url or self.settings.ollama_url
        self.model = model or self.settings.model
        self.timeout = timeout if timeout is not None else getattr(self.settings, "interpreter_timeout", 3.5)
        self.temperature = temperature if temperature is not None else getattr(self.settings, "interpreter_temperature", 0.1)

    def is_available(self) -> bool:
        """Checks if local Ollama server is responsive."""
        try:
            resp = requests.get(f"{self.ollama_url}/api/version", timeout=1.0)
            return resp.status_code == 200
        except Exception:
            return False

    def interpret(
        self,
        user_input: str,
        state_context: Optional[Dict[str, Any]] = None,
        language: str = "id",
    ) -> InterpreterPlan:
        """Interprets user input into a validated InterpreterPlan.

        Enforces a strict timeout and never executes arbitrary model text.
        """
        t0 = time.time()
        system_prompt = build_interpreter_system_prompt(language=language)
        context_str = build_interpreter_context_summary(state_context)

        prompt = f"{context_str}\nUser Input: \"{user_input}\"\nJSON Output:"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "top_p": 0.9,
                "num_predict": 180,  # Cap output length for latency
            },
            "keep_alive": self.settings.keep_alive,
        }

        try:
            resp = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            elapsed_ms = (time.time() - t0) * 1000.0

            if resp.status_code != 200:
                logger.warning("Ollama interpreter request failed with status %d", resp.status_code)
                return self._fallback_plan(user_input, elapsed_ms, f"HTTP {resp.status_code}")

            res_json = resp.json()
            raw_text = res_json.get("message", {}).get("content", "").strip()
            plan = self.parse_and_validate_json(raw_text, user_input, elapsed_ms)
            logger.info(
                '[INTERPRETER] type="%s" intent="%s" action="%s" target="%s" latency=%.1fms',
                plan.type,
                plan.intent,
                plan.action,
                plan.target,
                elapsed_ms,
            )
            return plan

        except requests.Timeout:
            elapsed_ms = (time.time() - t0) * 1000.0
            logger.warning("[INTERPRETER] Timeout after %.1fms (threshold=%.1fs)", elapsed_ms, self.timeout)
            return self._fallback_plan(user_input, elapsed_ms, "Timeout")

        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000.0
            logger.warning("[INTERPRETER] Error querying model: %s", e)
            return self._fallback_plan(user_input, elapsed_ms, str(e))

    def parse_and_validate_json(self, raw_text: str, user_input: str, latency_ms: float) -> InterpreterPlan:
        """Extracts and validates structured JSON plan from model generation."""
        # 1. Strip think blocks if model produced them
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", raw_text).strip()
        # 2. Extract JSON block if enclosed in markdown
        m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned)
        if m:
            json_str = m.group(1).strip()
        else:
            # Look for outermost braces
            m_brace = re.search(r"\{[\s\S]*\}", cleaned)
            json_str = m_brace.group(0).strip() if m_brace else cleaned

        try:
            data = json.loads(json_str)
            p_type = str(data.get("type", "conversation")).lower()
            intent = str(data.get("intent", "")).lower()
            action = str(data.get("action", "")).lower()
            target = str(data.get("target", "")).strip()
            params = data.get("parameters", {})
            if not isinstance(params, dict):
                params = {}
            conf = float(data.get("confidence", 0.9))
            req_confirm = bool(data.get("requires_confirmation", False))
            response_text = str(data.get("response", "")).strip()

            # Security: Allowlist validation
            if p_type == "action":
                allowed = ALLOWLISTED_ACTIONS.get(intent, [])
                if action not in allowed and not any(action in a for a in allowed):
                    # Reject unknown action
                    logger.warning("Rejected non-allowlisted action: %s for intent: %s", action, intent)
                    return InterpreterPlan(
                        type="unsupported",
                        intent=intent,
                        action=action,
                        target=target,
                        raw_output=raw_text,
                        latency_ms=latency_ms,
                    )

            return InterpreterPlan(
                type=p_type,
                intent=intent,
                action=action,
                target=target,
                parameters=params,
                requires_confirmation=req_confirm,
                confidence=conf,
                response=response_text,
                latency_ms=latency_ms,
                raw_output=raw_text,
            )

        except Exception as e:
            logger.debug("Failed to parse interpreter JSON: %s. Raw: %r", e, raw_text)
            # Default to conversation if model generated direct text
            return InterpreterPlan(
                type="conversation",
                response=cleaned or raw_text,
                latency_ms=latency_ms,
                raw_output=raw_text,
            )

    def _fallback_plan(self, user_input: str, latency_ms: float, reason: str) -> InterpreterPlan:
        """Safe fallback plan when LLM is unavailable or timed out."""
        # Simple heuristic check for obvious action requests
        u = user_input.lower()
        if any(w in u for w in ["pause", "jeda", "stop"]) and any(w in u for w in ["music", "song", "lagu", "it"]):
            return InterpreterPlan(
                type="action",
                intent="media_control",
                action="pause",
                target="active_media",
                latency_ms=latency_ms,
            )
        if any(w in u for w in ["resume", "lanjutkan", "play"]) and any(w in u for w in ["music", "song", "lagu", "it"]):
            return InterpreterPlan(
                type="action",
                intent="media_control",
                action="resume",
                target="active_media",
                latency_ms=latency_ms,
            )

        return InterpreterPlan(
            type="conversation",
            response="",
            latency_ms=latency_ms,
            raw_output=f"Fallback ({reason})",
        )
