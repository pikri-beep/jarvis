"""Unit and integration tests for TaskExecutor and the 7-step execution loop."""

from unittest.mock import MagicMock, patch
import pytest

from app.core.task_executor import (
    ALLOWED_PLANNER_ACTIONS,
    TaskExecutionResult,
    TaskExecutor,
    TaskPlan,
    TaskStep,
)
from app.tools.screen_reader import ScreenObservation, UIElement


def test_task_plan_structure():
    """Verifies TaskPlan and TaskStep model integrity."""
    plan = TaskPlan(
        goal="Buka tab baru lalu ketik YouTube",
        steps=[
            TaskStep(action="send_hotkey", target="ctrl+t", description="Buka tab baru"),
            TaskStep(action="type_text", target="https://youtube.com", description="Ketik URL"),
        ],
        max_steps=5,
    )
    assert len(plan.steps) == 2
    assert plan.steps[0].action == "send_hotkey"
    assert plan.max_steps == 5
    assert plan.is_completed is False


def test_allowed_planner_actions_safety():
    """Verifies that arbitrary shell execution or unsafe commands are rejected."""
    executor = TaskExecutor(max_steps=5)
    unsafe_step = TaskStep(action="arbitrary_bash", target="rm -rf /")
    ok, msg = executor.act(unsafe_step)
    assert ok is False
    assert "tidak diizinkan" in msg


def test_task_executor_recovery_on_failed_click():
    """Verifies that if click fails, recovery fallback tries alternative safe action (Enter key)."""
    executor = TaskExecutor(max_steps=5)
    failed_step = TaskStep(
        action="click_element",
        target="tombol submit",
        description="Klik tombol submit",
        retry_count=0,
    )
    obs = ScreenObservation(window_title="Active Form")
    rec_step = executor.recover(failed_step, "Elemen tidak ditemukan di layar.", obs)
    assert rec_step is not None
    assert rec_step.action == "press_key"
    assert rec_step.target == "enter"
    assert rec_step.retry_count == 1


def test_task_executor_max_steps_limit():
    """Verifies that task loop respects max_steps limit and does not run infinitely."""
    executor = TaskExecutor(max_steps=2)
    # Plan with 5 steps
    obs = ScreenObservation(window_title="Test Window")
    with patch.object(executor, "observe", return_value=obs), \
         patch.object(executor, "act", return_value=(True, "OK")), \
         patch.object(executor, "verify", return_value=True):
        
        # Override plan to produce 4 steps
        with patch.object(executor, "plan") as mock_plan:
            mock_plan.return_value = TaskPlan(
                goal="Multi-step test",
                steps=[
                    TaskStep(action="wait", description="Step 1"),
                    TaskStep(action="wait", description="Step 2"),
                    TaskStep(action="wait", description="Step 3"),
                    TaskStep(action="wait", description="Step 4"),
                ],
                max_steps=2,
            )
            res = executor.run("Multi-step test", language="id")
            assert res.steps_executed <= 2


def test_task_executor_contextual_element_success():
    """Verifies that when contextual element is provided, 'Klik tombol itu lalu lanjutkan' uses it."""
    focused_el = UIElement(
        name="Tombol Tutup",
        control_type="Button",
        rect=(1800, 10, 40, 30),
        center_x=1820,
        center_y=25,
    )
    executor = TaskExecutor(max_steps=3, contextual_element=focused_el)
    
    with patch("app.tools.desktop.move_cursor", return_value=(True, "Moved")) as mock_move, \
         patch("app.tools.desktop.mouse_click", return_value=(True, "Clicked")) as mock_click:
        res = executor.run("Klik tombol itu lalu lanjutkan", language="id")
        assert res.success is True
        assert mock_move.called
        assert mock_click.called
        assert mock_move.call_args[0][0] == 1820
        assert mock_move.call_args[0][1] == 25


def test_task_executor_contextual_element_missing_clarification():
    """Verifies that when contextual element is NOT provided, JARVIS does not click randomly and asks for clarification."""
    executor = TaskExecutor(max_steps=3, contextual_element=None)
    
    with patch("app.tools.desktop.move_cursor") as mock_move, \
         patch("app.tools.desktop.mouse_click") as mock_click:
        res = executor.run("Klik tombol itu lalu lanjutkan", language="id")
        assert res.success is False
        assert not mock_move.called
        assert not mock_click.called
        assert "belum bisa dipastikan" in res.spoken_summary or "spesifik" in res.spoken_summary
