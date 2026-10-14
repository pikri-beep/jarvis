"""Tests for conversational accuracy, instant greetings, and action execution fixes."""

import pytest
from unittest.mock import MagicMock, patch

from app.core.router import CommandRouter, RouteType, normalize_command_text
from app.core.orchestrator import Orchestrator
from app.ai.interpreter import ActionInterpreter, InterpreterPlan
from app.core.state import SessionState


def test_instant_greetings_bypass_llm():
    """Verify that greetings in all casings return FAST_COMMAND: greeting without LLM."""
    router = CommandRouter()
    
    test_cases = [
        "hALO",
        "halo",
        "Halo",
        "HALO",
        "hello",
        "Hello Jarvis",
        "hi",
        "Hai",
        "selamat pagi",
        "Selamat malam",
        "good morning",
    ]
    
    for case in test_cases:
        res = router.route(case)
        assert res.route_type == RouteType.FAST_COMMAND, f"Failed for {case}"
        assert res.action == "greeting", f"Action was not greeting for {case}"


def test_greeting_status_inquiries():
    """Verify 'apa kabar' or 'how are you' routes to greeting_status."""
    router = CommandRouter()
    
    for case in ["apa kabar", "apa kabar jarvis", "how are you", "How are you doing"]:
        res = router.route(case)
        assert res.route_type == RouteType.FAST_COMMAND
        assert res.action == "greeting_status"


def test_trailing_google_search_routing():
    """Verify queries ending with 'open in google' or 'cari di google' route to WEB_SEARCH."""
    router = CommandRouter()
    
    res = router.route("What AI meaning? open in google")
    assert res.route_type == RouteType.WEB_SEARCH
    assert "what ai meaning" in res.args.get("query", "").lower()
    assert res.args.get("open_browser") is True

    res2 = router.route("apa itu clean state di google")
    assert res2.route_type == RouteType.WEB_SEARCH
    assert "clean state" in res2.args.get("query", "")


def test_contextual_music_followup_routing():
    """Verify follow-up confirmation phrases route to play_contextual_music."""
    router = CommandRouter()
    
    cases = [
        "yes play it for me",
        "yes play it",
        "play it",
        "putar sekarang",
        "iya putarkan",
        "mainkan lagunya",
        "tolong putar",
        "ya putar",
    ]
    for case in cases:
        res = router.route(case)
        assert res.route_type == RouteType.FAST_COMMAND, f"Failed for {case}"
        assert res.action == "play_contextual_music", f"Expected play_contextual_music for {case}"


def test_phonetic_normalization_mishearings():
    """Verify Whisper phonetic mishearings normalize to correct media commands."""
    assert "play creep" in normalize_command_text("play grip")
    assert "play creep" in normalize_command_text("Play, grip.")
    assert "play creep" in normalize_command_text("lay kripp")
    assert "by radiohead" in normalize_command_text("buy radio head")


def test_orchestrator_instant_greeting_execution():
    """Verify Orchestrator replies instantly to greetings without calling LLM."""
    mock_llm = MagicMock()
    orch = Orchestrator(llm_client=mock_llm)
    
    route, gen = orch.process_input_stream("hALO")
    replies = list(gen)
    
    assert route.action == "greeting"
    assert len(replies) == 1
    assert "Halo" in replies[0]
    # Verify LLM was NOT invoked
    mock_llm.chat_stream.assert_not_called()


def test_orchestrator_contextual_music_plays_song():
    """Verify 'yes play it for me' extracts previously discussed song and plays it."""
    mock_llm = MagicMock()
    orch = Orchestrator(llm_client=mock_llm)
    
    # Simulate prior conversation where Creep was discussed
    orch.state.add_turn(
        "Lay, kripp, buy, radio, head.",
        "Sure, let's start with the basics. You want to lay down some 'Creep' music, right? I'll play it for you."
    )
    
    with patch("app.tools.youtube_controller.execute_youtube_command") as mock_yt:
        mock_yt.return_value = (True, "Playing 'Radiohead - Creep' on YouTube, sir.", "https://youtube.com/watch?v=123")
        
        route, gen = orch.process_input_stream("yes play it for me")
        replies = list(gen)
        
        assert route.action == "play_contextual_music"
        mock_yt.assert_called_once()
        # Ensure 'Creep' was the resolved song query
        called_arg = mock_yt.call_args[0][0]
        assert "Creep" in called_arg
        assert "Playing 'Radiohead - Creep'" in replies[0]


def test_action_interpreter_salvages_truncated_json_without_leak():
    """Verify interpreter never leaks raw JSON text into chat and salvages action."""
    interpreter = ActionInterpreter()
    
    truncated_raw = '''{
  "type": "action",
  "intent": "web_search",
  "action": "search_web",
  "target": "artificial intelligence",
  "parameters": {
    "query": "What is AI"
  },
  "requires_confirmation": false,
  "response": "The meaning of AI is not immediately'''
    
    plan = interpreter.parse_and_validate_json(truncated_raw, "What is AI", 12.0)
    assert plan.type == "action"
    assert plan.intent == "web_search"
    assert plan.action == "search"
    assert plan.parameters.get("query") == "What is AI"
    # Never leak raw JSON in response
    assert not plan.response.startswith("{")


def test_action_interpreter_suppresses_raw_json_leak_on_failure():
    """Verify malformed JSON does not leak into conversational response."""
    interpreter = ActionInterpreter()
    
    malformed = '{"invalid_json": true, "some_field": '
    plan = interpreter.parse_and_validate_json(malformed, "hello", 5.0)
    
    assert plan.type == "conversation"
    assert plan.response == ""


def test_benefactive_particles_open_application():
    """Verify Indonesian and English benefactive particles are cleaned and launch the target app directly."""
    from app.core.router import clean_target_identifier
    router = CommandRouter()

    assert clean_target_identifier("chrome untuk ku") == "chrome"
    assert clean_target_identifier("notepad buat saya") == "notepad"
    assert clean_target_identifier("chrome for me") == "chrome"
    assert clean_target_identifier("calculator untuk aku dong") == "calculator"

    cases = [
        ("Buka chrome untuk ku", "open_application", "chrome"),
        ("bukakan notepad buat saya", "open_application", "notepad"),
        ("Open chrome for me", "open_application", "chrome"),
        ("buka chrome untuk saya please", "open_application", "chrome"),
        ("tolong buka chrome buat aku", "open_application", "chrome"),
    ]
    for text, expected_act, expected_target in cases:
        res = router.route(text)
        assert res.route_type == RouteType.FAST_COMMAND, f"Failed for '{text}': got {res.route_type}"
        assert res.action == expected_act, f"Action mismatch for '{text}': got {res.action}"
        assert res.args.get("target") == expected_target, f"Target mismatch for '{text}': got {res.args.get('target')}"


def test_fuzzy_date_and_time_routing():
    """Verify typos and conversational variations on date/time route deterministically to fast commands."""
    router = CommandRouter()

    date_cases = [
        "what date todaya",
        "what date is today",
        "what date",
        "date today",
        "Tanggal berapa sekarang",
        "tanggal berapa",
        "hari apa sekarang",
    ]
    for text in date_cases:
        res = router.route(text)
        assert res.route_type == RouteType.FAST_COMMAND, f"Failed for '{text}': got {res.route_type}"
        assert res.action == "get_date", f"Action mismatch for '{text}': got {res.action}"

    time_cases = [
        "what time",
        "what time is it now",
        "jam berapa sekarang",
        "sekarang jam berapa",
    ]
    for text in time_cases:
        res = router.route(text)
        assert res.route_type == RouteType.FAST_COMMAND, f"Failed for '{text}': got {res.route_type}"
        assert res.action == "get_time", f"Action mismatch for '{text}': got {res.action}"


def test_system_prompt_temporal_grounding():
    """Verify system prompt dynamically provides current date/time to prevent outdated LLM hallucinations."""
    from app.ai.prompts import get_system_prompt
    import datetime

    prompt = get_system_prompt(language="id")
    now_year = str(datetime.datetime.now().year)
    assert now_year in prompt
    assert "Operating System: Windows 11" in prompt
    assert "CRITICAL LANGUAGE DIRECTIVE" in prompt


def test_misheard_creep_youtube_resolution():
    """Verify 'Play clip.', 'Putar grip by run.', etc. resolve to Radiohead - Creep."""
    from app.tools.youtube_controller import parse_music_intent

    cases = [
        ("Play clip.", "Creep", "Radiohead"),
        ("Putar grip by run.", "Creep", "Radiohead"),
        ("Putar clip by radiohead", "Creep", "Radiohead"),
        ("play grip", "Creep", "Radiohead"),
        ("lay kripp", "Creep", "Radiohead"),
    ]
    for user_input, expected_title, expected_artist in cases:
        intent = parse_music_intent(user_input)
        assert intent.get("title") == expected_title, f"Title mismatch for '{user_input}': got {intent.get('title')}"
        assert intent.get("artist") == expected_artist, f"Artist mismatch for '{user_input}': got {intent.get('artist')}"
        assert "Creep" in intent.get("query")

