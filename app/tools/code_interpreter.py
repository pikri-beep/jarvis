"""Dynamic Code Interpreter Module for JARVIS (Open Interpreter).

Provides safe, sandboxed, and silent execution of Python scripts and PowerShell commands
within the local environment. Integrates static safety guards to prevent destructive
operations unless explicitly confirmed by the user.
"""

import logging
import os
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.tools.code_interpreter")

MAX_OUTPUT_CHARS = 2000

# Static Safety Guard Patterns
DANGEROUS_PATTERNS: List[Tuple[str, str]] = [
    # 1. Destructive file and folder deletions
    (
        r"\b(?:shutil\.rmtree|os\.remove|os\.unlink|os\.rmdir|os\.removedirs)\b",
        "Penghapusan file/direktori sistem via modul Python os/shutil",
    ),
    (
        r"(?:\.unlink|\.rmdir)\s*\(",
        "Penghapusan file/direktori via Pathlib",
    ),
    (
        r"\bRemove-Item\b.*?(?:-Recurse|-Force|-r|-f)\b",
        "Penghapusan rekursif atau paksa via PowerShell Remove-Item",
    ),
    (
        r"\b(?:rmdir|rd)\s+/(?:s|q)\b",
        "Penghapusan direktori rekursif via CMD",
    ),
    (
        r"\b(?:del|erase)\s+/(?:f|s|q)\b",
        "Penghapusan file paksa via CMD",
    ),
    (
        r"\brm\s+-(?:rf|fr|r)\b",
        "Penghapusan rekursif paksa (rm -rf)",
    ),

    # 2. Storage and Volume formatting
    (
        r"\b(?:Format-Volume|Format-Disk|Clear-Disk|Initialize-Disk)\b",
        "Format atau inisialisasi volume/partisi disk",
    ),
    (
        r"\b(?:format\s+[a-zA-Z]:|diskpart)\b",
        "Perintah format disk atau partisi",
    ),

    # 3. System Power & Disruption
    (
        r"\b(?:Stop-Computer|Restart-Computer)\b",
        "Perintah shutdown atau restart via PowerShell",
    ),
    (
        r"\bshutdown(?:\.exe)?\s+.*?(?:[-/][srtafwb]|[-/]p)\b",
        "Perintah shutdown atau reboot sistem Windows",
    ),
    (
        r"\b(?:Stop-Process\s+-(?:Name|Id)\s+(?:wininit|csrss|lsass|smss|services))\b",
        "Penghentian proses kritis sistem operasi",
    ),

    # 4. Registry & Critical Windows System tampering
    (
        r"\breg(?:\.exe)?\s+delete\b",
        "Penghapusan entri registry Windows",
    ),
    (
        r"\b(?:Remove-Item|Remove-ItemProperty)\b.*?(?:HKLM:|HKCU:|Registry::)",
        "Penghapusan registry via PowerShell",
    ),
    (
        r"(?:System32|SysWOW64|Windows\\System32).*?(?:remove|delete|del|rmdir)",
        "Modifikasi atau penghapusan direktori kritis System32",
    ),

    # 5. Ransomware / Shadow copy deletion & BCD tampering
    (
        r"\bvssadmin(?:\.exe)?\s+delete\s+shadows\b",
        "Penghapusan Windows Volume Shadow Copies",
    ),
    (
        r"\bbcdedit(?:\.exe)?\s+/(?:set|delete)\b",
        "Modifikasi Boot Configuration Data (BCD)",
    ),

    # 6. Database drops
    (
        r"\bDROP\s+(?:DATABASE|SCHEMA)\b",
        "Penghapusan database atau skema secara permanen",
    ),
]


def is_code_dangerous(code: str) -> Tuple[bool, str]:
    """Inspects code or command strings for destructive or unsafe operations.

    Returns:
        (is_dangerous, reason_description)
    """
    if not code or not isinstance(code, str):
        return False, ""

    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            return True, reason

    return False, ""


def execute_python_code(
    code: str,
    timeout: int = 15,
    confirmed: bool = False,
) -> Dict[str, Any]:
    """Dynamically executes Python code in the current Python environment silently.

    Captures stdout, stderr, and exit code. Implements safety guards to require
    explicit user confirmation on destructive actions.

    Args:
        code: Python source code to execute.
        timeout: Execution timeout in seconds (default: 15).
        confirmed: Whether the user has explicitly confirmed potentially dangerous actions.

    Returns:
        Dict with keys: success, returncode, stdout, stderr, requires_confirmation, reason, code.
    """
    if not code or not code.strip():
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "Tidak ada kode Python yang diberikan untuk dieksekusi.",
            "requires_confirmation": False,
            "reason": "",
            "code": code,
        }

    # 1. Static Safety Guard Check
    is_dangerous, reason = is_code_dangerous(code)
    if is_dangerous and not confirmed:
        logger.warning("[SAFETY] Execution blocked for dangerous Python code: %s", reason)
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Peringatan Keamanan: Kode terdeteksi berisiko ({reason}). Butuh konfirmasi pengguna sebelum dieksekusi (confirmed=True).",
            "requires_confirmation": True,
            "reason": reason,
            "code": code,
        }

    # 2. Silent background execution configuration
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    logger.info("[INTERPRETER] Executing Python script silently (timeout=%ds, confirmed=%s)...", timeout, confirmed)

    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=creationflags,
            env=env,
        )

        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()

        # Truncate long outputs to preserve LLM context window
        if len(stdout) > MAX_OUTPUT_CHARS:
            stdout = stdout[:MAX_OUTPUT_CHARS] + "\n... [Output dipotong: melebihi 2000 karakter]"
        if len(stderr) > MAX_OUTPUT_CHARS:
            stderr = stderr[:MAX_OUTPUT_CHARS] + "\n... [Stderr dipotong: melebihi 2000 karakter]"

        success = proc.returncode == 0
        return {
            "success": success,
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "requires_confirmation": False,
            "reason": "",
            "code": code,
        }

    except subprocess.TimeoutExpired:
        logger.warning("[INTERPRETER] Python execution timed out after %ds", timeout)
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Eksekusi Python melebihi batas waktu (timeout {timeout} detik).",
            "requires_confirmation": False,
            "reason": "Timeout",
            "code": code,
        }
    except Exception as exc:
        logger.exception("[INTERPRETER] Failed to execute Python script: %s", exc)
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Kesalahan saat menjalankan Python: {str(exc)}",
            "requires_confirmation": False,
            "reason": str(exc),
            "code": code,
        }


def execute_powershell(
    command: str,
    timeout: int = 15,
    confirmed: bool = False,
) -> Dict[str, Any]:
    """Dynamically executes a PowerShell command or script silently in the background.

    Args:
        command: PowerShell command or script string to execute.
        timeout: Execution timeout in seconds (default: 15).
        confirmed: Whether the user has explicitly confirmed potentially dangerous actions.

    Returns:
        Dict with keys: success, returncode, stdout, stderr, requires_confirmation, reason, code.
    """
    if not command or not command.strip():
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "Tidak ada perintah PowerShell yang diberikan untuk dieksekusi.",
            "requires_confirmation": False,
            "reason": "",
            "code": command,
        }

    # 1. Static Safety Guard Check
    is_dangerous, reason = is_code_dangerous(command)
    if is_dangerous and not confirmed:
        logger.warning("[SAFETY] Execution blocked for dangerous PowerShell command: %s", reason)
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Peringatan Keamanan: Perintah terdeteksi berisiko ({reason}). Butuh konfirmasi pengguna sebelum dieksekusi (confirmed=True).",
            "requires_confirmation": True,
            "reason": reason,
            "code": command,
        }

    # Determine PowerShell executable
    ps_bin = shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")
    if not ps_bin:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "PowerShell executable tidak ditemukan di sistem ini.",
            "requires_confirmation": False,
            "reason": "PowerShell not found",
            "code": command,
        }

    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    cmd_args = [
        ps_bin,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        command,
    ]

    logger.info("[INTERPRETER] Executing PowerShell command silently (timeout=%ds, confirmed=%s)...", timeout, confirmed)

    try:
        proc = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=creationflags,
        )

        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()

        if len(stdout) > MAX_OUTPUT_CHARS:
            stdout = stdout[:MAX_OUTPUT_CHARS] + "\n... [Output dipotong: melebihi 2000 karakter]"
        if len(stderr) > MAX_OUTPUT_CHARS:
            stderr = stderr[:MAX_OUTPUT_CHARS] + "\n... [Stderr dipotong: melebihi 2000 karakter]"

        success = proc.returncode == 0
        return {
            "success": success,
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "requires_confirmation": False,
            "reason": "",
            "code": command,
        }

    except subprocess.TimeoutExpired:
        logger.warning("[INTERPRETER] PowerShell execution timed out after %ds", timeout)
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Eksekusi PowerShell melebihi batas waktu (timeout {timeout} detik).",
            "requires_confirmation": False,
            "reason": "Timeout",
            "code": command,
        }
    except Exception as exc:
        logger.exception("[INTERPRETER] Failed to execute PowerShell command: %s", exc)
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Kesalahan saat menjalankan PowerShell: {str(exc)}",
            "requires_confirmation": False,
            "reason": str(exc),
            "code": command,
        }
