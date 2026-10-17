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
    "media_control": [
        "pause", "resume", "play", "stop", "next", "previous",
        "volume_up", "volume_down", "mute", "unmute", "toggle_mute",
        "lower_volume", "raise_volume", "reduce_volume", "increase_volume",
    ],
    "web_search": ["search", "search_web", "open_search_results", "read_result", "list_sources", "open_source", "search_google"],
    "web_browser": [
        "open_url", "search_google", "open_new_tab", "close_tab", "switch_tab",
        "click_element", "fill_input", "scroll_page", "read_page", "go_back",
        "observe_page", "open_source", "open"
    ],
    "browser": [
        "open_url", "search_google", "open_new_tab", "close_tab", "switch_tab",
        "click_element", "fill_input", "scroll_page", "read_page", "go_back",
        "observe_page", "open_source", "open"
    ],
    "page_reader": ["read_page", "summarize_page", "read_source"],
    "open_application": ["open", "close", "focus", "launch", "run", "start"],
    "open_website": ["open", "launch", "browse"],
    "desktop_control": ["click", "double_click", "right_click", "scroll", "type", "press_key", "shortcut"],
    "screen_read": ["inspect_screen", "ask_element", "read_error"],
    "system": ["time", "date", "battery", "lock", "screenshot", "system_info"],
    "task": ["execute_task", "continue", "retry", "vision_task", "set_timer"],
    "todo": ["add", "list", "delete", "clear_all", "clear_completed", "toggle", "complete", "add_task", "delete_all", "clear"],
    "filesystem": ["read", "write", "delete", "create_folder", "open_folder", "list_files", "clean_workspace"],
    "code_execution": ["python", "powershell", "execute_python_code", "execute_powershell", "run_script"],
}

# Synonyms mapped to canonical actions
ACTION_SYNONYMS: Dict[str, str] = {
    "clear_all_todos": "clear_all",
    "delete_all_todos": "clear_all",
    "delete_all": "clear_all",
    "clear_todos": "clear_completed",
    "remove_todo": "delete",
    "add_todo": "add",
    "list_todos": "list",
    "run_python": "python",
    "run_powershell": "powershell",
    "set_timer": "vision_task",
    "search_web": "search",
    "web_search": "search",
    "google": "search_google",
    "play_music": "play",
    "reduce_volume": "volume_down",
    "lower_volume": "volume_down",
    "decrease_volume": "volume_down",
    "kecilkan_volume": "volume_down",
    "raise_volume": "volume_up",
    "increase_volume": "volume_up",
    "naikkan_volume": "volume_up",
    "launch": "open",
    "start": "open",
    "run": "open",
    "quit": "close",
    "kill": "close",
    "exit": "close",
    "open_application": "open",
    "open_app": "open",
    "open_website": "open",
    "open_site": "open",
    "open_url": "open",
    "unmute": "unmute",
    "toggle_mute": "toggle_mute",
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
        '  "intent": "todo" | "media_control" | "web_search" | "web_browser" | "browser" | "page_reader" | "open_application" | "open_website" | "desktop_control" | "screen_read" | "system" | "filesystem" | "code_execution",\n'
        '  "action": "<allowlisted_action>",\n'
        '  "target": "<target_app_or_entity>",\n'
        '  "parameters": { ... },\n'
        '  "requires_confirmation": false,\n'
        '  "response": "<concise answer if type is conversation or clarify>"\n'
        "}\n\n"
        "RULES:\n"
        "1. If user wants to do something (open app, search web, control music, click, read page, add/list/delete/clear todos, create/delete files or folders, run code/script), type MUST be 'action'. Never classify an imperative action command as 'conversation'.\n"
        "2. For opening search results/sources (e.g. 'sumber 1', 'tolong ke sumber pertama', 'open first source'), set intent='web_search', action='open_source', target='1' (or the requested index number).\n"
        "3. For todo management (e.g. 'hapus semua todo', 'clear todo', 'daftar tugas', 'catat todo: ...'), set intent='todo', action='clear_all' (or 'add', 'list', 'delete', 'clear_completed').\n"
        "4. Resolve pronouns and references ('it', 'that song', 'the article', 'the first result', 'sumber pertama') using provided context.\n"
        "5. If user is asking a conversational or general knowledge question, type MUST be 'conversation'.\n"
        "6. CRITICAL PERSONA CONSTRAINT: NEVER output third-person meta-analysis (e.g. NEVER output 'The user is looking for...', 'The user wants...'). If type is 'conversation' or 'clarify', 'response' MUST be what JARVIS directly speaks to the user in Bahasa Indonesia, addressing the user as 'sir'.\n"
        "7. If type is 'action', response MUST be empty string \"\". Do not output promises or conversational text for actions.\n"
        "8. Output compact JSON only."
    )


def build_interpreter_context_summary(state_context: Optional[Dict[str, Any]]) -> str:
    """Builds a concise summary of active conversation state for pronoun resolution."""
    if not state_context:
        return "Context: No active media or recent actions."

    parts = []
    if state_context.get("recent_dialog"):
        parts.append(f"Recent Dialog: {state_context['recent_dialog']}")
    if state_context.get("active_media"):
        parts.append(f"Active Media: {state_context['active_media']}")
    if state_context.get("last_action"):
        parts.append(f"Last Action: {state_context['last_action']}")
    if state_context.get("last_target"):
        parts.append(f"Last Target: {state_context['last_target']}")
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

    return "Context: " + " | ".join(parts) if parts else "Context: No active media or recent actions."


class ActionInterpreter:
    """Context and Action Interpreter using Groq Cloud API with local Ollama fallback."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        ollama_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        temperature: Optional[float] = None,
        provider: Optional[str] = None,
    ):
        self.settings = settings or get_settings()
        self.ollama_url = ollama_url or self.settings.ollama_url
        self.model = model or self.settings.model
        self.timeout = timeout if timeout is not None else getattr(self.settings, "interpreter_timeout", 3.5)
        self.temperature = temperature if temperature is not None else getattr(self.settings, "interpreter_temperature", 0.1)

        # Provider configuration (groq vs ollama)
        self.groq_model = getattr(self.settings, "groq_model", "qwen/qwen3.8-27b")
        if provider is not None:
            self.provider = provider.lower()
        elif model is not None and model != self.groq_model:
            self.provider = "ollama"
        else:
            self.provider = getattr(self.settings, "interpreter_provider", "groq").lower()

        self.groq_api_key = getattr(self.settings, "groq_api_key", None) or os.getenv("GROQ_API_KEY")
        self._groq_client = None

        if self.provider == "groq" and self.groq_api_key and self.groq_api_key.strip():
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=self.groq_api_key.strip())
                logger.info("Groq Action Interpreter initialized with model '%s'", self.groq_model)
            except Exception as e:
                logger.warning("Failed to initialize Groq client (%s); falling back to Ollama", e)
                self._groq_client = None

    def is_available(self) -> bool:
        """Checks if active interpreter provider is responsive."""
        if self._groq_client is not None:
            return True
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

        Uses Groq Cloud for sub-second parsing with automatic Ollama fallback if offline.
        """
        t0 = time.time()
        system_prompt = build_interpreter_system_prompt(language=language)
        context_str = build_interpreter_context_summary(state_context)
        prompt = f"{context_str}\nUser Input: \"{user_input}\"\nJSON Output:"

        # 1. Primary: Groq Cloud API (< 300ms latency)
        if self._groq_client is not None:
            try:
                resp = self._groq_client.chat.completions.create(
                    model=self.groq_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=self.temperature,
                    max_tokens=300,
                    timeout=self.timeout,
                )
                elapsed_ms = (time.time() - t0) * 1000.0
                raw_text = resp.choices[0].message.content or ""
                plan = self.parse_and_validate_json(raw_text, user_input, elapsed_ms)
                logger.info(
                    '[INTERPRETER-GROQ] type="%s" intent="%s" action="%s" target="%s" latency=%.1fms',
                    plan.type,
                    plan.intent,
                    plan.action,
                    plan.target,
                    elapsed_ms,
                )
                return plan
            except Exception as e:
                logger.warning("Groq interpreter failed (%s); falling back to local Ollama", e)

        # 2. Secondary / Offline Fallback: Local Ollama
        return self._interpret_ollama(user_input, system_prompt, prompt, t0)

    def _interpret_ollama(
        self,
        user_input: str,
        system_prompt: str,
        prompt: str,
        t0: float,
    ) -> InterpreterPlan:
        """Interprets via local Ollama instance."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.temperature,
                "top_p": 0.9,
                "num_predict": 200,
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
                '[INTERPRETER-OLLAMA] type="%s" intent="%s" action="%s" target="%s" latency=%.1fms',
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
            action = ACTION_SYNONYMS.get(action, action)
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
            # 1. Try to salvage structured action fields from raw_text even if truncated
            m_type = re.search(r'"type"\s*:\s*"([^"]+)"', raw_text)
            m_intent = re.search(r'"intent"\s*:\s*"([^"]+)"', raw_text)
            m_act = re.search(r'"action"\s*:\s*"([^"]+)"', raw_text)
            m_tgt = re.search(r'"target"\s*:\s*"([^"]+)"', raw_text)
            m_q = re.search(r'"query"\s*:\s*"([^"]+)"', raw_text)

            if (m_type and m_type.group(1).lower() == "action") or m_act:
                p_intent = m_intent.group(1).lower() if m_intent else "web_search"
                p_action = ACTION_SYNONYMS.get(m_act.group(1).lower(), m_act.group(1).lower()) if m_act else "search"
                p_target = m_tgt.group(1) if m_tgt else ""
                p_params = {"query": m_q.group(1)} if m_q else {}
                logger.info("[INTERPRETER] Salvaged action from truncated JSON: intent=%s, action=%s, target=%s", p_intent, p_action, p_target)
                return InterpreterPlan(
                    type="action",
                    intent=p_intent,
                    action=p_action,
                    target=p_target,
                    parameters=p_params,
                    latency_ms=latency_ms,
                    raw_output=raw_text,
                )

            # 2. Never leak raw JSON structures into conversation responses
            safe_resp = cleaned or raw_text
            if safe_resp.strip().startswith("{") or '"type":' in safe_resp:
                safe_resp = ""

            return InterpreterPlan(
                type="conversation",
                response=safe_resp,
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
