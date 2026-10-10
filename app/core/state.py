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
    pending_action: Optional[PendingAction] = None

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

    def clear(self) -> None:
        """Clears conversation history and action context."""
        self.history.clear()
        self.last_action_context.clear()
        self.pending_action = None
