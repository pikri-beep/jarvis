"""Integration tests for the Orchestrator."""

from unittest.mock import MagicMock, patch
from app.core.orchestrator import Orchestrator
from app.core.router import RouteType


def test_orchestrator_terminal_help():
    orchestrator = Orchestrator()
    route, stream = orchestrator.process_input_stream("/help")
    assert route.route_type == RouteType.TERMINAL_COMMAND
    output = "".join(list(stream))
    assert "Commands available" in output


def test_orchestrator_terminal_status():
    mock_llm = MagicMock()
    mock_llm.is_server_available.return_value = True
    mock_llm.is_model_available.return_value = True

    orchestrator = Orchestrator(llm_client=mock_llm)
    route, stream = orchestrator.process_input_stream("/status")
    assert route.route_type == RouteType.TERMINAL_COMMAND
    output = "".join(list(stream))
    assert "ONLINE" in output
    assert "READY" in output


def test_orchestrator_fast_command():
    orchestrator = Orchestrator()
    with patch("app.tools.apps.launch_application", return_value=(True, "Google Chrome", "Berhasil")):
        route, stream = orchestrator.process_input_stream("open chrome")
        assert route.route_type == RouteType.FAST_COMMAND
        output = "".join(list(stream))
        assert "Opening Google Chrome, sir." in output


def test_orchestrator_fast_time_and_date():
    orchestrator = Orchestrator()
    route_time, stream_time = orchestrator.process_input_stream("What time is it?")
    assert route_time.route_type == RouteType.FAST_COMMAND
    out_time = "".join(list(stream_time))
    assert "It is " in out_time and "sir." in out_time

    route_date, stream_date = orchestrator.process_input_stream("Jarvis, what is today's date?")
    assert route_date.route_type == RouteType.FAST_COMMAND
    out_date = "".join(list(stream_date))
    assert "Today is " in out_date and "sir." in out_date


def test_orchestrator_web_query():
    orchestrator = Orchestrator()
    route, stream = orchestrator.process_input_stream("What is the weather today?")
    assert route.route_type == RouteType.WEB_DEPENDENT
    output = "".join(list(stream))
    assert (
        "search results" in output
        or "browser" in output
        or "Source" in output
        or "Sumber" in output
        or "could not find verified online information" in output
    )



def test_orchestrator_llm_flow():
    mock_llm = MagicMock()
    mock_llm.chat_stream.return_value = iter(["Hello, ", "sir. ", "How may I help?"])

    orchestrator = Orchestrator(llm_client=mock_llm)
    route, stream = orchestrator.process_input_stream("Tell me about stars")
    assert route.route_type == RouteType.AI_REQUEST
    output = "".join(list(stream))
    assert output == "Hello, sir. How may I help?"
    assert len(orchestrator.state.history) == 2
    assert orchestrator.state.history[0].role == "user"
    assert orchestrator.state.history[1].role == "assistant"


def test_orchestrator_clarification_follow_up_open():
    orchestrator = Orchestrator()
    # Turn 1: Incomplete command "buka" triggers clarification
    route1, stream1 = orchestrator.process_input_stream("buka")
    assert route1.route_type == RouteType.CLARIFY
    out1 = "".join(list(stream1))
    assert "Aplikasi atau situs apa" in out1
    assert orchestrator.state.pending_action is not None
    assert orchestrator.state.pending_action.action == "clarify_open"

    # Turn 2: Follow-up answer "chrome" resolves cleanly without repeating "buka"
    with patch("app.tools.apps.launch_application", return_value=(True, "Google Chrome", "Berhasil")):
        route2, stream2 = orchestrator.process_input_stream("chrome")
        assert route2.route_type == RouteType.FAST_COMMAND
        out2 = "".join(list(stream2))
        assert "Membuka Google Chrome, sir." in out2
        assert orchestrator.state.pending_action is None


def test_orchestrator_clarification_follow_up_cancellation():
    orchestrator = Orchestrator()
    # Turn 1: Ambiguous close command "tutup"
    route1, stream1 = orchestrator.process_input_stream("tutup")
    assert route1.route_type == RouteType.CLARIFY
    out1 = "".join(list(stream1))
    assert "Aplikasi apa yang ingin Anda tutup" in out1
    assert orchestrator.state.pending_action is not None
    assert orchestrator.state.pending_action.action == "clarify_close"

    # Turn 2: User cancels with "batal"
    route2, stream2 = orchestrator.process_input_stream("batal")
    assert route2.route_type == RouteType.FAST_COMMAND
    out2 = "".join(list(stream2))
    assert "dibatalkan" in out2
    assert orchestrator.state.pending_action is None
