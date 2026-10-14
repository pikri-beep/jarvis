"""Unit and integration tests for JARVIS Vision Agent, Set-of-Marks indexing, and Pause & Resume."""

from unittest.mock import MagicMock, patch
import pytest

from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType
from app.core.vision_agent import (
    VisionAgent,
    VisionAgentResult,
    VisionStep,
    VisionTaskState,
    extract_duration_from_text,
)
from app.tools.screen_reader import (
    IndexedUIElement,
    ScreenObservation,
    UIElement,
    format_indexed_screen_summary,
    get_indexed_ui_elements,
)


def test_extract_duration_from_text():
    """Verifies duration extraction for Indonesian and English numeric and word phrases."""
    assert extract_duration_from_text("5 menit") == 5
    assert extract_duration_from_text("sepuluh menit") == 10
    assert extract_duration_from_text("setengah jam") == 30
    assert extract_duration_from_text("satu jam") == 60
    assert extract_duration_from_text("15 minutes") == 15
    assert extract_duration_from_text("lima belas menit") == 15
    assert extract_duration_from_text("tolong setel 20 menit dong") == 20
    assert extract_duration_from_text("7") == 7
    assert extract_duration_from_text("hallo jarvis") is None


def test_indexed_ui_elements_mapping():
    """Verifies that interactive elements are tagged sequentially with 1-based indexing."""
    elements = [
        UIElement(name="Address and search bar", control_type="Edit", center_x=400, center_y=80, is_enabled=True),
        UIElement(name="Google Search", control_type="Button", center_x=500, center_y=300, is_enabled=True),
        UIElement(name="New Tab", control_type="TabItem", center_x=200, center_y=40, is_enabled=True),
        UIElement(name="", control_type="Pane", center_x=100, center_y=100, is_enabled=True),  # Non-interactive pane
    ]
    obs = ScreenObservation(window_title="Google Chrome", elements=elements)
    indexed = get_indexed_ui_elements(obs)

    assert len(indexed) == 3
    assert indexed[0].index == 1
    assert indexed[0].control_type == "Edit"
    assert indexed[1].index == 2
    assert indexed[1].control_type == "Button"
    assert indexed[2].index == 3
    assert indexed[2].control_type == "TabItem"

    summary = format_indexed_screen_summary(obs, indexed)
    assert "[1] Edit:" in summary
    assert "[2] Button:" in summary


def test_router_vision_triggers():
    """Verifies that terminal commands, natural prefixes, and timer intents route to vision_task."""
    router = CommandRouter()

    # 1. Explicit terminal slash command
    r1 = router.route("/vision setel timer")
    assert r1.action == "vision_task"
    assert r1.args["goal"] == "setel timer"

    # 2. Natural language vision prefix
    r2 = router.route("lihat layar dan setel timer")
    assert r2.action == "vision_task"
    assert "setel timer" in r2.args["goal"]

    # 3. Natural intent for timer
    r3 = router.route("setel timer")
    assert r3.action == "vision_task"
    assert "timer" in r3.args["goal"]

    r4 = router.route("pasang timer 10 menit")
    assert r4.action == "vision_task"
    assert "10 menit" in r4.args["goal"]


def test_vision_agent_timer_pause_and_resume():
    """Verifies that timer goal without duration pauses at the timer screen and resumes with user input."""
    agent = VisionAgent(max_steps=8)

    mock_obs = ScreenObservation(
        window_title="Google Chrome - New Tab",
        process_name="chrome.exe",
        elements=[
            UIElement(name="Search", control_type="Edit", center_x=500, center_y=80),
            UIElement(name="Start", control_type="Button", center_x=600, center_y=400),
        ],
    )

    with patch.object(agent, "observe", return_value=(mock_obs, [])):
        with patch("app.core.vision_agent.send_shortcut", return_value=(True, "OK")):
            with patch("app.core.vision_agent.type_text", return_value=(True, "OK")):
                with patch("app.core.vision_agent.press_single_key", return_value=(True, "OK")):
                    # Start task: "setel timer" without duration
                    res = agent.start_task("setel timer", language="id")

                    assert res.status == "PAUSED_FOR_USER_INPUT"
                    assert res.is_paused is True
                    assert "berapa menit" in res.spoken_output.lower()
                    assert res.state is not None
                    assert res.state.waiting_parameter == "duration_minutes"

                    # Resume task with user answer: "5 menit"
                    res_resumed = agent.resume_task(res.state, user_response="5 menit")
                    assert res_resumed.status == "COMPLETED"
                    assert res_resumed.is_paused is False
                    assert "5 menit" in res_resumed.spoken_output


def test_vision_agent_timer_preset_duration_no_pause():
    """Verifies that when duration is already supplied, task finishes directly without pausing."""
    agent = VisionAgent(max_steps=8)

    mock_obs = ScreenObservation(window_title="Google Chrome", process_name="chrome.exe")

    with patch.object(agent, "observe", return_value=(mock_obs, [])):
        with patch("app.core.vision_agent.send_shortcut", return_value=(True, "OK")):
            with patch("app.core.vision_agent.type_text", return_value=(True, "OK")):
                with patch("app.core.vision_agent.press_single_key", return_value=(True, "OK")):
                    res = agent.start_task("setel timer 10 menit", language="id")
                    assert res.status == "COMPLETED"
                    assert res.is_paused is False
                    assert "10 menit" in res.spoken_output


def test_vision_agent_cancellation():
    """Verifies that user can cancel a paused vision task."""
    agent = VisionAgent(max_steps=8)
    state = VisionTaskState(
        task_id="test1",
        goal="setel timer",
        status="PAUSED_FOR_USER_INPUT",
        current_step=3,
        language="id",
    )
    res = agent.resume_task(state, user_response="batal saja")
    assert res.status == "FAILED"
    assert "dibatalkan" in res.spoken_output


def test_orchestrator_vision_task_end_to_end():
    """Verifies orchestrator multi-turn state management for vision tasks."""
    orchestrator = Orchestrator()

    mock_obs = ScreenObservation(window_title="Google Chrome", process_name="chrome.exe")

    with patch("app.core.vision_agent.read_screen_content") as mock_read:
        mock_read.return_value = MagicMock(observation=mock_obs)
        with patch("app.core.vision_agent.send_shortcut", return_value=(True, "OK")), \
             patch("app.core.vision_agent.type_text", return_value=(True, "OK")), \
             patch("app.core.vision_agent.press_single_key", return_value=(True, "OK")):

            # Turn 1: "setel timer"
            route1, gen1 = orchestrator.process_input_stream("setel timer")
            reply1 = "".join(list(gen1))

            assert "berapa menit" in reply1.lower()
            assert orchestrator.state.pending_vision_task is not None

            # Turn 2: User answers "5 menit"
            route2, gen2 = orchestrator.process_input_stream("5 menit")
            reply2 = "".join(list(gen2))

            assert "5 menit" in reply2
            assert orchestrator.state.pending_vision_task is None
