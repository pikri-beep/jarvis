"""In-memory session state and conversation context tracking for JARVIS."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Message:
    """Represents a conversation message."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class PendingAction:
    """Represents a pending action requiring user confirmation."""
    action: str
    target: str
    display_name: str
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionState:
    """Tracks active conversation state, history, and action context."""

    history: List[Message] = field(default_factory=list)
    system_prompt: str = ""
    is_running: bool = True
    conversation_language: str = "id"
    language_override: Any = None  # Optional[str]: None, "id", or "en"
    max_history_messages: int = 12  # Sliding window of 6 full conversational turns
    last_action_context: Dict[str, Any] = field(default_factory=dict)
    last_search_context: Dict[str, Any] = field(default_factory=dict)
    last_screen_context: Dict[str, Any] = field(default_factory=dict)
    pending_action: Optional[PendingAction] = None
    pending_vision_task: Optional[Any] = None
    last_observation: Optional[Any] = None
    last_focused_element: Optional[Any] = None
    current_task: Optional[Any] = None
    is_muted: bool = False

    def add_message(self, role: str, content: str) -> None:
        """Appends a message to conversation history with sliding window pruning."""
        self.history.append(Message(role=role, content=content))
        # Maintain sliding window to prevent unbounded context growth on CPU
        if len(self.history) > self.max_history_messages:
            self.history = self.history[-self.max_history_messages:]

    def add_turn(self, user_input: str, assistant_reply: str) -> None:
        """Records a completed conversational or command turn."""
        self.add_message("user", user_input)
        self.add_message("assistant", assistant_reply)

    def get_messages_for_llm(self) -> List[Dict[str, str]]:
        """Returns messages formatted for the Ollama chat endpoint."""
        messages: List[Dict[str, str]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        for msg in self.history:
            messages.append({"role": msg.role, "content": msg.content})
        return messages

    def set_last_action(self, action: str, target: str, display_name: str, success: bool) -> None:
        """Records metadata of the last executed command or tool action."""
        self.last_action_context = {
            "action": action,
            "target": target,
            "display_name": display_name,
            "success": success,
        }

    def set_last_search(
        self,
        query: str,
        spoken_answer: str,
        display_answer: str,
        sources: List[Dict[str, str]],
        latency_ms: float = 0.0,
    ) -> None:
        """Records metadata of the last executed search-first query."""
        self.last_search_context = {
            "query": query,
            "spoken_answer": spoken_answer,
            "display_answer": display_answer,
            "sources": sources,
            "latency_ms": latency_ms,
        }

    def get_last_search(self) -> Dict[str, Any]:
        """Returns metadata of the last search-first query."""
        return self.last_search_context

    def set_last_screen(
        self,
        text: str,
        method: str,
        spoken_summary: str = "",
        display_text: str = "",
        window_title: str = "",
        latency_ms: float = 0.0,
    ) -> None:
        """Records metadata of the last on-demand screen reading."""
        self.last_screen_context = {
            "text": text,
            "method": method,
            "spoken_summary": spoken_summary,
            "display_text": display_text,
            "window_title": window_title,
            "latency_ms": latency_ms,
        }

    def get_last_screen(self) -> Dict[str, Any]:
        """Returns metadata of the last screen reading."""
        return self.last_screen_context

    def get_last_action_target(self) -> Optional[str]:
        """Returns the canonical target of the last executed action."""
        return self.last_action_context.get("target")

    def get_last_action_display_name(self) -> Optional[str]:
        """Returns the display name of the last executed action target."""
        return self.last_action_context.get("display_name")

    def get_last_user_message(self) -> Optional[str]:
        """Returns the most recent user message from history."""
        for msg in reversed(self.history):
            if msg.role == "user":
                return msg.content
        return None

    def get_last_assistant_message(self) -> Optional[str]:
        """Returns the most recent assistant message from history."""
        for msg in reversed(self.history):
            if msg.role == "assistant":
                return msg.content
        return None

    def set_last_observation(self, obs: Any) -> None:
        """Stores the most recent multi-layer screen observation."""
        self.last_observation = obs

    def get_last_observation(self) -> Optional[Any]:
        """Retrieves the most recent screen observation."""
        return self.last_observation

    def set_last_focused_element(self, element: Any) -> None:
        """Stores the most recently referenced or focused UI element."""
        self.last_focused_element = element

    def get_last_focused_element(self) -> Optional[Any]:
        """Retrieves the most recently referenced or focused UI element."""
        return self.last_focused_element

    def clear_focused_element(self) -> None:
        """Clears the currently focused UI element."""
        self.last_focused_element = None

    def set_pending_vision_task(self, task: Any) -> None:
        """Stores the active paused vision task state for interactive resumption."""
        self.pending_vision_task = task

    def get_pending_vision_task(self) -> Optional[Any]:
        """Retrieves the active paused vision task state."""
        return self.pending_vision_task

    def clear_pending_vision_task(self) -> None:
        """Clears the active paused vision task."""
        self.pending_vision_task = None

    def clear(self) -> None:
        """Clears conversation history and action context."""
        self.history.clear()
        self.last_action_context.clear()
        self.last_search_context.clear()
        self.last_screen_context.clear()
        self.pending_action = None
        self.pending_vision_task = None
        self.last_observation = None
        self.last_focused_element = None
        self.current_task = None

