"""Handlers package modularizing Orchestrator dispatch logic."""

from app.core.handlers.confirmation_handler import handle_pending_confirmation, handle_pending_vision_task, handle_clarification
from app.core.handlers.terminal_handler import handle_terminal_command
from app.core.handlers.fast_command_handler import handle_fast_command, handle_screen_read, handle_web_search, handle_web_dependent
from app.core.handlers.ai_handler import handle_ai_request

__all__ = [
    "handle_pending_confirmation",
    "handle_pending_vision_task",
    "handle_clarification",
    "handle_terminal_command",
    "handle_fast_command",
    "handle_screen_read",
    "handle_web_search",
    "handle_web_dependent",
    "handle_ai_request",
]
