"""Unit tests for JARVIS Dynamic Code Interpreter & Self-Healing ReAct Agent."""

import json
from unittest.mock import MagicMock, patch
import pytest

from app.tools.code_interpreter import (
    execute_powershell,
    execute_python_code,
    is_code_dangerous,
)
from app.core.task_executor import (
    ALLOWED_PLANNER_ACTIONS,
    TOOL_DEFINITIONS,
    AutonomousReActAgent,
    execute_registered_tool,
)


def test_allowed_planner_actions_and_tool_definitions():
    """Verifies execute_python_code and execute_powershell are registered in schemas."""
    assert "execute_python_code" in ALLOWED_PLANNER_ACTIONS
    assert "execute_powershell" in ALLOWED_PLANNER_ACTIONS

    assert "execute_python_code" in TOOL_DEFINITIONS
    assert "execute_powershell" in TOOL_DEFINITIONS
    assert "code" in TOOL_DEFINITIONS["execute_python_code"]["parameters"]
    assert "command" in TOOL_DEFINITIONS["execute_powershell"]["parameters"]


def test_is_code_dangerous_safe_code():
    """Verifies that harmless analysis, calculation, and read operations are considered safe."""
    safe_snippets = [
        "print('Hello JARVIS')",
        "import math\nprint(math.sqrt(144))",
        "import psutil\nprint(psutil.cpu_percent())",
        "with open('report.txt', 'r') as f:\n    print(f.read())",
        "Get-Process | Sort-Object CPU -Descending | Select-Object -First 5",
        "Get-Volume",
    ]
    for snippet in safe_snippets:
        is_dang, reason = is_code_dangerous(snippet)
        assert is_dang is False, f"Expected safe for: {snippet}, got: {reason}"
        assert reason == ""


def test_is_code_dangerous_destructive_patterns():
    """Verifies that destructive, formatting, and system-disrupting commands are blocked."""
    dangerous_snippets = [
        ("import shutil\nshutil.rmtree('C:/Users/user/AppData')", "shutil.rmtree"),
        ("import os\nos.remove('important_doc.pdf')", "os.remove"),
        ("import os\nos.unlink('data.db')", "os.unlink"),
        ("from pathlib import Path\nPath('test.txt').unlink()", "unlink"),
        ("Remove-Item -Path 'D:/backup' -Recurse -Force", "Remove-Item"),
        ("Format-Volume -DriveLetter D", "Format-Volume"),
        ("shutdown /s /t 0", "shutdown"),
        ("Stop-Computer -Force", "Stop-Computer"),
        ("reg delete 'HKCU\\Software\\Bad' /f", "reg delete"),
        ("vssadmin delete shadows /all /quiet", "vssadmin"),
        ("DROP DATABASE production_db", "DROP DATABASE"),
    ]
    for snippet, label in dangerous_snippets:
        is_dang, reason = is_code_dangerous(snippet)
        assert is_dang is True, f"Expected dangerous for {label} snippet: {snippet}"
        assert len(reason) > 0


def test_execute_python_code_safe_execution():
    """Verifies safe Python execution returns stdout and zero returncode."""
    code = "a = 21\nb = 2\nprint(a * b)"
    res = execute_python_code(code=code, timeout=5)

    assert res["success"] is True
    assert res["returncode"] == 0
    assert res["stdout"].strip() == "42"
    assert res["stderr"] == ""
    assert res["requires_confirmation"] is False


def test_execute_python_code_blocks_destructive_without_confirmation():
    """Verifies destructive code is blocked and requires explicit confirmation."""
    dangerous_code = "import shutil\nshutil.rmtree('C:/Windows/Temp')"
    res = execute_python_code(code=dangerous_code, confirmed=False)

    assert res["success"] is False
    assert res["returncode"] == -1
    assert res["requires_confirmation"] is True
    assert "Peringatan Keamanan" in res["stderr"]


def test_execute_python_code_with_confirmed():
    """Verifies that when confirmed=True, execution proceeds."""
    code = "print('Bypassed with confirmation')"
    with patch("subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=0, stdout="Bypassed with confirmation\n", stderr="")
        res = execute_python_code(code=code, confirmed=True)
        assert res["success"] is True
        assert "Bypassed with confirmation" in res["stdout"]


def test_execute_python_code_runtime_error_reporting():
    """Verifies runtime errors and exceptions populate stderr correctly."""
    err_code = "print(100 / 0)"
    res = execute_python_code(code=err_code, timeout=5)

    assert res["success"] is False
    assert res["returncode"] != 0
    assert "ZeroDivisionError" in res["stderr"]


def test_execute_registered_tool_python():
    """Verifies execute_registered_tool dispatches execute_python_code correctly."""
    ok, obs = execute_registered_tool(
        action="execute_python_code",
        args={"code": "print('EXEC_TOOL_SUCCESS')"},
    )
    assert ok is True
    assert "EXEC_TOOL_SUCCESS" in obs


def test_execute_registered_tool_safety_block():
    """Verifies execute_registered_tool halts on unconfirmed dangerous code."""
    ok, obs = execute_registered_tool(
        action="execute_python_code",
        args={"code": "import os\nos.remove('system_file.dll')", "confirmed": False},
    )
    assert ok is False
    assert "Konfirmasi Keamanan Diperlukan" in obs


def test_react_agent_code_interpreter_self_healing():
    """Verifies the Autonomous ReAct Agent inspects execution errors and self-heals code on subsequent iteration."""
    # Iteration 1: LLM generates code with NameError
    step1_llm_response = json.dumps({
        "thought": "Saya akan menghitung nilai kuadrat menggunakan variabel x.",
        "action": "execute_python_code",
        "action_input": {"code": "print(x ** 2)"},
    })

    # Iteration 2: LLM receives Observation with NameError, fixes the code
    step2_llm_response = json.dumps({
        "thought": "Error sebelumnya menunjukkan bahwa variabel x belum didefinisikan. Saya akan mendefinisikan x = 12 lalu mencetak x ** 2.",
        "action": "execute_python_code",
        "action_input": {"code": "x = 12\nprint(x ** 2)"},
    })

    # Iteration 3: LLM sees success and yields final answer
    step3_llm_response = json.dumps({
        "thought": "Kode telah berhasil dieksekusi dengan hasil 144.",
        "final_answer": "Perhitungan berhasil diselesaikan, hasilnya adalah 144, sir.",
    })

    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [
        step1_llm_response,
        step2_llm_response,
        step3_llm_response,
    ]

    agent = AutonomousReActAgent(llm=mock_llm, max_iterations=5)
    result = agent.run("Hitung kuadrat dari 12 menggunakan python")

    assert result.success is True
    assert result.iterations == 3
    assert len(result.steps) == 3

    # Step 1: Failed execution
    assert result.steps[0].action == "execute_python_code"
    assert "Failed" in result.steps[0].observation
    assert "NameError" in result.steps[0].observation

    # Step 2: Successful healed execution
    assert result.steps[1].action == "execute_python_code"
    assert "Success" in result.steps[1].observation
    assert "144" in result.steps[1].observation

    # Step 3: Final answer reached
    assert result.steps[2].final_answer is not None
    assert "144" in result.steps[2].final_answer
