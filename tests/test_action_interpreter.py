"""Unit tests for Layer B/C Action Interpreter (LLM as context interpreter, not chatbot)."""

from unittest.mock import MagicMock, patch
import pytest

from app.ai.interpreter import (
    ALLOWLISTED_ACTIONS,
    ActionInterpreter,
    InterpreterPlan,
    build_interpreter_context_summary,
    build_interpreter_system_prompt,
)


def test_interpreter_plan_model():
    plan = InterpreterPlan(
        type="action",
        intent="media_control",
        action="pause",
        target="active_media",
    )
    assert plan.is_action is True
    assert plan.action == "pause"
    assert plan.intent == "media_control"


def test_allowlisted_actions_security():
    """Verifies that arbitrary or destructive shell actions are rejected by allowlist."""
    interpreter = ActionInterpreter()
    # Malicious plan trying to execute arbitrary bash/cmd
    raw_payload = '{"type": "action", "intent": "shell", "action": "rm -rf /", "target": "system"}'
    plan = interpreter.parse_and_validate_json(raw_payload, "rm -rf /", 15.0)
    assert plan.type == "unsupported"
    assert plan.is_action is False


def test_context_summary_builder():
    ctx = {
        "active_media": "Bohemian Rhapsody - Queen",
        "last_action": "play_music",
        "last_search_query": "perkembangan AI",
        "last_search_sources": [{"url": "https://example.com/ai"}],
    }
    summary = build_interpreter_context_summary(ctx)
    assert "Bohemian Rhapsody" in summary
    assert "perkembangan AI" in summary
    assert "1 sources" in summary


def test_action_interpretation_parses_clean_json():
    interpreter = ActionInterpreter()
    model_output = """<think>User wants to pause music</think>
```json
{
  "type": "action",
  "intent": "media_control",
  "action": "pause",
  "target": "active_media",
  "parameters": {},
  "requires_confirmation": false
}
```"""
    plan = interpreter.parse_and_validate_json(model_output, "Could you pause the song for a moment?", 850.0)
    assert plan.is_action is True
    assert plan.intent == "media_control"
    assert plan.action == "pause"
    assert plan.target == "active_media"


def test_action_interpretation_handles_conversational_question():
    interpreter = ActionInterpreter()
    model_output = '{"type": "conversation", "response": "Avengers: Doomsday dijadwalkan tayang pada Mei 2026, sir."}'
    plan = interpreter.parse_and_validate_json(model_output, "Kapan rilis film Avengers Doomsday?", 950.0)
    assert plan.is_action is False
    assert plan.type == "conversation"
    assert "Mei 2026" in plan.response


def test_action_interpretation_handles_clarification():
    interpreter = ActionInterpreter()
    model_output = '{"type": "clarify", "response": "Tombol yang mana yang ingin Anda klik, sir?"}'
    plan = interpreter.parse_and_validate_json(model_output, "Klik itu", 400.0)
    assert plan.type == "clarify"
    assert "Tombol yang mana" in plan.response


def test_action_interpretation_network_mock():
    interpreter = ActionInterpreter()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {
            "content": '{"type": "action", "intent": "web_search", "action": "search", "parameters": {"query": "berita AI terbaru"}}'
        }
    }

    with patch("requests.post", return_value=mock_resp):
        plan = interpreter.interpret("Tolong cari info terbaru tentang AI")
        assert plan.is_action is True
        assert plan.intent == "web_search"
        assert plan.action == "search"
        assert plan.parameters.get("query") == "berita AI terbaru"
