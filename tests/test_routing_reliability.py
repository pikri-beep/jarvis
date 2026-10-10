"""Regression tests for Phase 4.1: Command Routing and Tool Execution Reliability."""

from unittest.mock import MagicMock, patch
import pytest

from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, ExecutionStatus, RouteResult, RouteType, ToolExecutionResult
from app.core.state import SessionState


@pytest.fixture
def router():
    return CommandRouter()


@pytest.fixture
def mock_orchestrator():
    mock_llm = MagicMock()
    mock_llm.is_server_available.return_value = True
    mock_llm.is_model_available.return_value = True
    mock_llm.chat_stream.return_value = iter(["Hello", " there, ", "sir."])

    settings = Settings(
        jarvis_name="Jarvis",
        tts_enabled=False,
        voice_enabled=False,
    )
    orch = Orchestrator(settings=settings, llm_client=mock_llm)
    return orch


# ---------------------------------------------------------------------------
# Test 1: Capitalization and Punctuation Variations
# ---------------------------------------------------------------------------
def test_capitalization_and_punctuation(router):
    variations = [
        "Open Chrome",
        "open chrome.",
        "OPEN CHROME!",
        "  open chrome   ",
        '"Open Chrome"',
        "open chrome...",
        "Open Chrome?",
    ]
    for text in variations:
        res = router.route(text)
        assert res.route_type == RouteType.FAST_COMMAND, f"Failed for '{text}': got {res.route_type}"
        assert res.action in ("open_application", "open_browser")
        assert res.args.get("target") == "chrome"
        assert res.route == "DIRECT"


# ---------------------------------------------------------------------------
# Test 2: English and Indonesian Phrasing Variations
# ---------------------------------------------------------------------------
def test_english_and_indonesian_variants(router):
    phrases = [
        ("Please open Chrome", "open_application", "chrome"),
        ("Open Chrome please", "open_application", "chrome"),
        ("Open Chrome now", "open_application", "chrome"),
        ("Buka Chrome", "open_application", "chrome"),
        ("Tolong buka Chrome", "open_application", "chrome"),
        ("Buka Chrome dong", "open_application", "chrome"),
        ("Buka Chrome dong ya", "open_application", "chrome"),
        ("Tolong bukain Chrome", "open_application", "chrome"),
        ("Bisa bukain Chrome dong", "open_application", "chrome"),
        ("Open browser Chrome", "open_application", "chrome"),
        ("Buka browser Chrome", "open_application", "chrome"),
    ]
    for text, expected_action, expected_target in phrases:
        res = router.route(text)
        assert res.route_type == RouteType.FAST_COMMAND, f"Failed for '{text}'"
        assert res.action == expected_action, f"Action mismatch for '{text}': {res.action}"
        assert res.args.get("target") == expected_target, f"Target mismatch for '{text}': {res.args.get('target')}"


# ---------------------------------------------------------------------------
# Test 3: Supported Targets (Chrome, YouTube, Gmail, Calc, WhatsApp)
# ---------------------------------------------------------------------------
def test_supported_targets(router):
    cases = [
        ("Open YouTube", "open_website", "youtube"),
        ("Buka YouTube dong", "open_website", "youtube"),
        ("Open Gmail", "open_website", "gmail"),
        ("Buka Gmail", "open_website", "gmail"),
        ("Open Calculator", "open_application", "calculator"),
        ("Buka kalkulator", "open_application", "calculator"),
        ("Open WhatsApp", "open_application", "whatsapp"),
        ("Buka WhatsApp", "open_application", "whatsapp"),
    ]
    for text, expected_action, expected_target in cases:
        res = router.route(text)
        assert res.route_type == RouteType.FAST_COMMAND, f"Failed for '{text}'"
        assert res.action == expected_action
        assert res.args.get("target") == expected_target


# ---------------------------------------------------------------------------
# Test 4: General Conversation Must Not Trigger Application Launch
# ---------------------------------------------------------------------------
def test_general_conversation_does_not_trigger_tools(router):
    conversations = [
        "Why is the sky blue?",
        "Apa itu YouTube?",
        "Bagaimana cara kerja komputer?",
        "Chrome adalah peramban buatan Google",
        "Jangan buka Chrome",
        "Saya suka menonton video di YouTube",
        "Siapa penemu kalkulator?",
    ]
    for text in conversations:
        res = router.route(text)
        assert res.route_type == RouteType.AI_REQUEST, f"Conversational query '{text}' incorrectly routed to {res.route_type}"
        assert res.route == "LLM"


# ---------------------------------------------------------------------------
# Test 5: Ambiguous Command Requests Clarification
# ---------------------------------------------------------------------------
def test_ambiguous_command_requests_clarification(router, mock_orchestrator):
    ambiguous_cases = [
        ("Open", "clarify_open"),
        ("open.", "clarify_open"),
        ("Buka", "clarify_open"),
        ("tolong buka dong", "clarify_open"),
        ("Close", "clarify_close"),
        ("tutup", "clarify_close"),
        ("matiin", "clarify_close"),
    ]
    for text, expected_action in ambiguous_cases:
        res = router.route(text)
        assert res.route_type == RouteType.CLARIFY, f"Failed for '{text}': got {res.route_type}"
        assert res.action == expected_action
        assert res.route == "CLARIFY"

    # Verify orchestrator asks for clarification without calling LLM or launching tools
    with patch("app.tools.apps.launch_application") as mock_launch:
        route, gen = mock_orchestrator.process_input_stream("Buka")
        output = "".join(list(gen))
        assert "Aplikasi atau situs apa" in output or "Which application" in output
        mock_launch.assert_not_called()
        mock_orchestrator.llm.chat_stream.assert_not_called()


# ---------------------------------------------------------------------------
# Test 6: Launch Failure Reports Honest Error and Does Not Claim Success
# ---------------------------------------------------------------------------
def test_launch_failure_reports_honest_error(mock_orchestrator):
    with patch("app.tools.apps.launch_application") as mock_launch:
        mock_launch.return_value = (False, "Google Chrome", "Executable not found on system path")

        route, gen = mock_orchestrator.process_input_stream("Open Chrome")
        output = "".join(list(gen))

        assert route.route_type == RouteType.FAST_COMMAND
        assert "tidak dapat membuka" in output.lower() or "couldn't open" in output.lower()
        assert "Executable not found" in output
        # Must not report success
        assert "Opening Google Chrome, sir." not in output
        assert "Membuka Google Chrome, sir." not in output

        assert mock_orchestrator.state.last_action_context.get("success") is False


# ---------------------------------------------------------------------------
# Test 7: Natural-Language LLM Response Never Triggers Tool or State Mutation
# ---------------------------------------------------------------------------
def test_llm_response_mimicking_tool_does_not_execute_tool(mock_orchestrator):
    mock_orchestrator.llm.chat_stream.return_value = iter(["Opening Chrome, sir. Here you go."])

    with patch("app.tools.apps.launch_application") as mock_launch:
        route, gen = mock_orchestrator.process_input_stream("What do you say when opening Chrome?")
        output = "".join(list(gen))

        assert route.route_type == RouteType.AI_REQUEST
        assert "Opening Chrome" in output
        mock_launch.assert_not_called()

        # State must not register a tool action from pure LLM text
        assert mock_orchestrator.state.last_action_context == {}
        assert mock_orchestrator.state.get_last_action_target() is None


# ---------------------------------------------------------------------------
# Test 8: Exceptions During Tool Execution Are Handled Gracefully
# ---------------------------------------------------------------------------
def test_tool_exceptions_handled_gracefully(mock_orchestrator):
    with patch("app.tools.apps.launch_application", side_effect=OSError("Access denied by OS")):
        route, gen = mock_orchestrator.process_input_stream("Open Chrome")
        output = "".join(list(gen))

        assert route.route_type == RouteType.FAST_COMMAND
        assert "Terjadi kesalahan" in output or "error occurred" in output.lower()
        assert "Access denied by OS" in output


# ---------------------------------------------------------------------------
# Test 9: Prevention of Duplicate Tool Execution and LLM Bypassing
# ---------------------------------------------------------------------------
def test_duplicate_execution_prevention(mock_orchestrator):
    with patch("app.tools.apps.launch_application") as mock_launch:
        mock_launch.return_value = (True, "Google Chrome", "Launched successfully")

        route, gen = mock_orchestrator.process_input_stream("Open Chrome")
        output = "".join(list(gen))

        # Tool executed exactly once
        mock_launch.assert_called_once_with("chrome")
        # LLM was never called
        mock_orchestrator.llm.chat_stream.assert_not_called()
        assert "Opening Google Chrome, sir." in output or "Membuka Google Chrome, sir." in output


# ---------------------------------------------------------------------------
# Test 10: Wake-Word Mode and Push-to-Talk Transcription Compatibility
# ---------------------------------------------------------------------------
def test_wake_word_and_ptt_transcription_compatibility(router):
    # Wake word STT typically yields prefix "Hey Jarvis, ..." or trailing punctuation
    wake_transcriptions = [
        ("Hey Jarvis, open Chrome.", "open_application", "chrome"),
        ("jarvis open youtube!", "open_website", "youtube"),
        ("Hey Jarvis, buka Gmail dong.", "open_website", "gmail"),
    ]
    for raw_stt, expected_action, expected_target in wake_transcriptions:
        res = router.route(raw_stt)
        assert res.route_type == RouteType.FAST_COMMAND, f"Wake-word input '{raw_stt}' failed"
        assert res.action == expected_action
        assert res.args.get("target") == expected_target

    # Push-to-talk speech often has Indonesian colloquial speech
    ptt_transcriptions = [
        ("tolong bukain kalkulator ya", "open_application", "calculator"),
        ("buka browser chrome dong", "open_application", "chrome"),
    ]
    for raw_stt, expected_action, expected_target in ptt_transcriptions:
        res = router.route(raw_stt)
        assert res.route_type == RouteType.FAST_COMMAND, f"PTT input '{raw_stt}' failed"
        assert res.action == expected_action
        assert res.args.get("target") == expected_target
