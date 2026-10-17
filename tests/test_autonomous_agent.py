"""Unit and integration tests for Autonomous & Proactive AI Agent Architecture."""

import time
from unittest.mock import MagicMock, patch
import pytest

from app.ai.prompts import DEFAULT_SYSTEM_PROMPT, get_system_prompt
from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.proactive_agent import ProactiveAgent, ProactiveEvent
from app.core.router import CommandRouter, RouteType, is_multi_step_or_implicit_intent
from app.core.task_executor import (
    ALLOWED_PLANNER_ACTIONS,
    AutonomousReActAgent,
    ReActAgentResult,
    ReActStep,
    TOOL_DEFINITIONS,
    execute_registered_tool,
)


def test_loosened_routing_for_complex_and_implicit_intents():
    """Verify that multi-step, complex goals, or implicit situations route to AI_REQUEST."""
    router = CommandRouter()

    # 1. Multi-step instructions with conjunctions
    r_multi1 = router.route("buka tab baru lalu ketik YouTube")
    assert r_multi1.route_type == RouteType.AI_REQUEST
    assert r_multi1.action == "agentic_task"

    r_multi2 = router.route("open chrome and then search for latest AI news")
    assert r_multi2.route_type == RouteType.AI_REQUEST
    assert r_multi2.action == "agentic_task"

    r_multi3 = router.route("buka vscode terus jalankan script main.py")
    assert r_multi3.route_type == RouteType.AI_REQUEST
    assert r_multi3.action == "agentic_task"

    # 2. Implicit user goals
    r_goal1 = router.route("aku mau lanjut ngerjain tugas")
    assert r_goal1.route_type == RouteType.AI_REQUEST
    assert r_goal1.action == "agentic_task"

    r_goal2 = router.route("mau belajar ngoding sekarang")
    assert r_goal2.route_type == RouteType.AI_REQUEST
    assert r_goal2.action == "agentic_task"

    # 3. Implicit screen error statements
    r_err1 = router.route("layarku kok error gini ya")
    assert r_err1.route_type == RouteType.AI_REQUEST
    assert r_err1.action == "agentic_task"

    r_err2 = router.route("ada error di layar laptopku")
    assert r_err2.route_type == RouteType.AI_REQUEST
    assert r_err2.action == "agentic_task"

    # 4. Strict explicit fast commands must NOT be affected
    r_single = router.route("buka chrome")
    assert r_single.route_type == RouteType.FAST_COMMAND
    assert r_single.action == "open_application"

    r_time = router.route("jam berapa sekarang?")
    assert r_time.route_type == RouteType.FAST_COMMAND
    assert r_time.action == "get_time"

    r_fictional = router.route("buka software_fiktif_xyz_999")
    assert r_fictional.route_type == RouteType.FAST_COMMAND
    assert r_fictional.action == "app_not_found"


def test_tool_definitions_and_allowed_actions():
    """Verify tool definitions and allowed safe action registry."""
    assert "open_application" in ALLOWED_PLANNER_ACTIONS
    assert "search_web" in ALLOWED_PLANNER_ACTIONS
    assert "read_screen" in ALLOWED_PLANNER_ACTIONS
    assert "inspect_screen_error" in ALLOWED_PLANNER_ACTIONS
    assert "store_memory" in ALLOWED_PLANNER_ACTIONS
    assert "recall_memory" in ALLOWED_PLANNER_ACTIONS
    assert "get_system_info" in ALLOWED_PLANNER_ACTIONS
    assert "arbitrary_bash" not in ALLOWED_PLANNER_ACTIONS

    assert "open_application" in TOOL_DEFINITIONS
    assert "search_web" in TOOL_DEFINITIONS
    assert "inspect_screen_error" in TOOL_DEFINITIONS


def test_execute_registered_tool_system_info():
    """Verify tool execution for system hardware and specs."""
    ok, info = execute_registered_tool("get_system_info", language="id")
    assert ok is True
    assert "Sistem berjalan pada" in info or "Windows" in info or "RAM" in info


def test_execute_registered_tool_memory():
    """Verify tool execution for persistent memory facts."""
    # Store memory
    ok_store, msg_store = execute_registered_tool(
        "store_memory",
        args={"key": "favorite_subject", "value": "Astrophysics"},
    )
    assert ok_store is True
    assert "favorite_subject" in msg_store or "Astrophysics" in msg_store

    # Recall memory
    ok_rec, msg_rec = execute_registered_tool("recall_memory", args={"key": "favorite_subject"})
    assert ok_rec is True
    assert "Astrophysics" in msg_rec


def test_autonomous_react_loop_multi_step_execution():
    """Verify multi-step ReAct agent loop execution with observation feedback."""
    mock_llm = MagicMock()

    # Step 1: Agent decides to inspect screen
    step1_output = (
        "Thought: The user is asking about an error on screen. I should inspect the screen first.\n"
        "Action: read_screen\n"
        "Action Input: {\"prompt\": \"error on screen\"}"
    )
    # Step 2: Agent observes screen and delivers Final Answer
    step2_output = (
        "Thought: The screen shows a syntax error in main.py. I can now inform the user.\n"
        "Final Answer: Layar Anda menunjukkan SyntaxError pada file main.py, sir. Ada tanda kurung yang belum tertutup."
    )

    mock_llm.chat.side_effect = [step1_output, step2_output]

    agent = AutonomousReActAgent(llm=mock_llm, max_iterations=5)

    with patch("app.core.task_executor.read_screen_content") as mock_screen:
        mock_screen_res = MagicMock()
        mock_screen_res.spoken_summary = "Layar menampilkan VS Code dengan pesan SyntaxError"
        mock_screen_res.display_text = "File main.py line 42: SyntaxError: unexpected EOF"
        mock_screen.return_value = mock_screen_res

        res = agent.run("layarku kok error gini ya", language="id")

        assert res.success is True
        assert len(res.steps) == 2
        # First step performed an action
        assert res.steps[0].action == "read_screen"
        assert "SyntaxError" in res.steps[0].observation
        # Second step produced the final answer
        assert "SyntaxError" in res.final_answer
        assert mock_llm.chat.call_count == 2


def test_autonomous_react_loop_json_parsing():
    """Verify ReAct agent handles structured JSON output format."""
    mock_llm = MagicMock()

    json_step1 = '{"thought": "Opening Chrome", "action": "open_application", "action_input": {"app_name": "chrome"}}'
    json_step2 = '{"thought": "Chrome is opened", "final_answer": "Google Chrome telah dibuka untuk Anda, sir."}'

    mock_llm.chat.side_effect = [json_step1, json_step2]

    agent = AutonomousReActAgent(llm=mock_llm, max_iterations=5)

    with patch("app.tools.apps.launch_application", return_value=(True, "Google Chrome", "Berhasil membuka Google Chrome.")):
        res = agent.run("buka chrome untuk saya", language="id")
        assert res.success is True
        assert len(res.steps) == 2
        assert res.steps[0].action == "open_application"
        assert "telah dibuka" in res.final_answer


def test_autonomous_react_loop_bounded_iterations():
    """Verify ReAct agent respects max_iterations limit and synthesizes completion."""
    mock_llm = MagicMock()
    # LLM that keeps trying to read screen endlessly
    infinite_step = (
        "Thought: Checking screen again.\n"
        "Action: wait\n"
        "Action Input: {\"seconds\": 0.1}"
    )
    mock_llm.chat.return_value = infinite_step

    agent = AutonomousReActAgent(llm=mock_llm, max_iterations=3)
    res = agent.run("tugas tanpa henti", language="id")

    assert res.iterations == 3
    assert len(res.steps) == 3
    assert res.success is True
    assert "Tugas telah diproses" in res.final_answer or "selesai" in res.final_answer


def test_proactive_agent_error_window_trigger():
    """Verify ProactiveAgent triggers intervention when an error window is detected."""
    settings = Settings()
    proactive = ProactiveAgent(settings=settings)

    with patch("app.tools.desktop.get_active_window_details") as mock_det:
        mock_win = MagicMock()
        mock_win.title = "Critical Error - Application Not Responding"
        mock_win.process_name = "program.exe"
        mock_win.hwnd = 12345
        mock_det.return_value = mock_win

        event = proactive.check_context()
        assert event is not None
        assert event.category == "error_assistance"
        assert "kendala" in event.display_message or "error" in event.display_message.lower()


def test_proactive_agent_startup_greeting_trigger():
    """Verify ProactiveAgent initiates welcome greeting on first active window."""
    settings = Settings()
    proactive = ProactiveAgent(settings=settings)
    assert proactive.startup_greeted is False

    with patch("app.tools.desktop.get_active_window_details") as mock_det:
        mock_win = MagicMock()
        mock_win.title = "Visual Studio Code - project"
        mock_win.process_name = "code.exe"
        mock_win.hwnd = 54321
        mock_det.return_value = mock_win

        event = proactive.check_context()
        assert event is not None
        assert event.category == "startup_greeting"
        assert proactive.startup_greeted is True

        # Second consecutive check must be suppressed by cooldown
        event2 = proactive.check_context()
        assert event2 is None


def test_proactive_agent_suppressed_when_voice_busy():
    """Verify ProactiveAgent does not interrupt active speech or processing."""
    settings = Settings()
    orch = Orchestrator(settings=settings)
    orch.state.is_processing = True  # User command in progress

    proactive = ProactiveAgent(settings=settings, orchestrator=orch)
    assert proactive.is_voice_idle() is False
    event = proactive.check_context()
    assert event is None


def test_updated_system_prompt_persona():
    """Verify DEFAULT_SYSTEM_PROMPT includes Autonomous Persona and ReAct capabilities."""
    prompt = get_system_prompt(language="id")
    assert "autonomous" in prompt.lower()
    assert "proactive" in prompt.lower()
    assert "initiative" in prompt.lower()
    assert "screen" in prompt.lower()
    assert "memory" in prompt.lower()
