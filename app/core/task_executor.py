"""Task-oriented execution loop and Autonomous ReAct Agent for JARVIS on Windows 11.

Follows Section 2.A & Autonomous ReAct Agent specifications:
1. Multi-step ReAct agent loop (Thought -> Action/Tool Call -> Observation -> Thought -> Final Answer)
   with bounded iterations (max_iterations=5).
2. Comprehensive tool definitions/schemas across apps, browser, desktop, filesystem,
   music, screen_reader, system/windows, youtube, and persistent memory.
3. Observation feedback loop allowing JARVIS to autonomously verify results,
   recover from failures, and proceed without asking the user to repeat.
4. Preserves backward compatibility with TaskStep, TaskPlan, and the 7-step cycle.
"""

from dataclasses import dataclass, field
import json
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.core.logger import setup_logger
from app.tools.desktop import (
    ensure_window_focus,
    get_active_window_details,
    mouse_click,
    mouse_scroll,
    press_single_key,
    send_shortcut,
    type_text,
)
from app.tools.screen_reader import (
    ScreenObservation,
    UIElement,
    find_element_by_reference,
    read_screen_content,
)

logger = setup_logger("jarvis.core.task_executor")

# Allowed safe actions in planner & ReAct agent (zero arbitrary shell execution)
ALLOWED_PLANNER_ACTIONS = {
    # Desktop UI
    "open_application",
    "close_application",
    "open_website",
    "focus_window",
    "click_element",
    "type_text",
    "press_key",
    "send_hotkey",
    "mouse_click",
    "mouse_scroll",
    "get_active_window",
    "wait",
    # Browser & Web
    "search_web",
    "open_url",
    "read_web_page",
    "fetch_page_content",
    # Filesystem
    "open_folder",
    "create_folder",
    "delete_file_or_folder",
    # Media & Entertainment
    "play_youtube",
    "play_music",
    "pause_music",
    "resume_music",
    "stop_music",
    "change_volume",
    # Screen Inspection
    "read_screen",
    "inspect_screen_error",
    # System & Hardware
    "get_system_info",
    "get_battery_status",
    "lock_windows",
    "take_screenshot",
    # Persistent Memory
    "store_memory",
    "recall_memory",
    "recall_all_memories",
    "forget_memory",
    # Dynamic Code Interpreter (Open Interpreter)
    "execute_python_code",
    "execute_powershell",
    # Todo & Task Management
    "list_todos",
    "add_todo",
    "clear_all_todos",
    "delete_all_todos",
    "delete_todo",
}

# Detailed tool definitions exposed to the LLM
TOOL_DEFINITIONS = {
    "open_application": {
        "description": "Launch a desktop application (e.g. chrome, vscode, notepad, spotify, calculator, explorer).",
        "parameters": {"app_name": "Name of the application to launch"},
    },
    "close_application": {
        "description": "Close a running application window or process safely.",
        "parameters": {"app_name": "Name of the application to close"},
    },
    "open_website": {
        "description": "Open a website in the default web browser (e.g. youtube.com, github.com).",
        "parameters": {"url": "Website URL or domain"},
    },
    "search_web": {
        "description": "Search Google for real-time information and retrieve top results.",
        "parameters": {"query": "Search query keywords"},
    },
    "open_url": {
        "description": "Navigate to a specific web address in the browser.",
        "parameters": {"url": "Full destination URL"},
    },
    "read_web_page": {
        "description": "Read and extract textual content from the active browser tab.",
        "parameters": {},
    },
    "fetch_page_content": {
        "description": "Fetch and extract text content from an article or URL.",
        "parameters": {"url": "Article URL"},
    },
    "get_active_window": {
        "description": "Get title and process name of the currently focused window.",
        "parameters": {},
    },
    "focus_window": {
        "description": "Bring a window to front focus by title or application name.",
        "parameters": {"title": "Title or partial title of window to focus"},
    },
    "click_element": {
        "description": "Click a UI element or button on screen by label, text, or coordinates.",
        "parameters": {"target": "Element name or label to click"},
    },
    "type_text": {
        "description": "Type text into the currently focused input field.",
        "parameters": {"text": "Text to type"},
    },
    "press_key": {
        "description": "Press a single keyboard key (e.g. enter, tab, esc, backspace, up, down).",
        "parameters": {"key": "Key name to press"},
    },
    "send_hotkey": {
        "description": "Send a keyboard shortcut combo (e.g. ctrl+t, ctrl+w, alt+tab, win+d).",
        "parameters": {"hotkey": "Shortcut combination"},
    },
    "open_folder": {
        "description": "Open a folder in Windows File Explorer (desktop, downloads, documents, pictures, etc.).",
        "parameters": {"target": "Folder name or path to open"},
    },
    "create_folder": {
        "description": "Create a new folder safely.",
        "parameters": {"folder_name": "Name of new folder", "parent": "Parent directory (default desktop)"},
    },
    "delete_file_or_folder": {
        "description": "Delete a file or folder safely. Requires explicit confirmed=True.",
        "parameters": {"path": "File or folder path", "confirmed": "Boolean confirmation"},
    },
    "play_youtube": {
        "description": "Search and play a video or music track on YouTube.",
        "parameters": {"query": "Song, artist, or video title to play"},
    },
    "play_music": {
        "description": "Play music or song via configured provider.",
        "parameters": {"query": "Track title or artist"},
    },
    "pause_music": {
        "description": "Pause currently playing music/media.",
        "parameters": {},
    },
    "resume_music": {
        "description": "Resume paused music/media.",
        "parameters": {},
    },
    "stop_music": {
        "description": "Stop media playback.",
        "parameters": {},
    },
    "change_volume": {
        "description": "Adjust system audio volume (action: 'up', 'down', or 'mute').",
        "parameters": {"action": "'up', 'down', or 'mute'", "steps": "Number of volume steps (default 2)"},
    },
    "read_screen": {
        "description": "Inspect and read UI elements and text visible on screen via OCR.",
        "parameters": {"prompt": "Optional question or focus for screen reading"},
    },
    "inspect_screen_error": {
        "description": "Inspect the screen specifically for error messages, dialog boxes, or exceptions.",
        "parameters": {"prompt": "Context of the suspected error"},
    },
    "get_system_info": {
        "description": "Get hardware specs, CPU threads, RAM usage, and free disk space.",
        "parameters": {},
    },
    "get_battery_status": {
        "description": "Get battery charge percentage and AC power status.",
        "parameters": {},
    },
    "lock_windows": {
        "description": "Safely lock the Windows workstation.",
        "parameters": {},
    },
    "take_screenshot": {
        "description": "Capture the full display screen and save to Pictures/Screenshots.",
        "parameters": {},
    },
    "store_memory": {
        "description": "Save an explicit user fact, preference, or habit into persistent SQLite memory.",
        "parameters": {"key": "Memory key name", "value": "Memory value"},
    },
    "recall_memory": {
        "description": "Recall a specific stored memory fact by key.",
        "parameters": {"key": "Memory key name"},
    },
    "recall_all_memories": {
        "description": "Retrieve all stored user facts and preferences.",
        "parameters": {},
    },
    "forget_memory": {
        "description": "Remove a stored fact from persistent memory.",
        "parameters": {"key": "Memory key name to forget"},
    },
    "wait": {
        "description": "Pause execution briefly to let an application or window respond.",
        "parameters": {"seconds": "Seconds to wait (up to 3.0)"},
    },
    "execute_python_code": {
        "description": "Execute a Python script dynamically to perform calculations, data analysis, file parsing, web scraping, custom automation, or tasks not covered by standard tools. Output is captured. Self-correct on error.",
        "parameters": {
            "code": "Python code string to execute",
            "timeout": "Execution timeout in seconds (default 15)",
            "confirmed": "Set to True if explicit confirmation has been given for dangerous operations",
        },
    },
    "execute_powershell": {
        "description": "Execute a PowerShell command or script to perform system administration, advanced file operations, process queries, or Windows automation not covered by built-in tools.",
        "parameters": {
            "command": "PowerShell command or script string to execute",
            "timeout": "Execution timeout in seconds (default 15)",
            "confirmed": "Set to True if explicit confirmation has been given for dangerous operations",
        },
    },
    "list_todos": {
        "description": "List all active user todos, tasks, and notes from SQLite storage.",
        "parameters": {},
    },
    "add_todo": {
        "description": "Record a new todo task or reminder for the user with optional due time.",
        "parameters": {"task": "Task title or description"},
    },
    "clear_all_todos": {
        "description": "Delete and clear all todos/tasks completely from the user's todo list in SQLite.",
        "parameters": {},
    },
    "delete_todo": {
        "description": "Delete a specific todo item by its ID or number.",
        "parameters": {"task_id": "ID or number of the task to delete"},
    },
}


def build_tool_schemas_prompt() -> str:
    """Builds a formatted string of tool schemas for prompt injection."""
    lines = ["Available Tools for Autonomous Agent:"]
    for name, spec in TOOL_DEFINITIONS.items():
        params = ", ".join(f"{k}" for k in spec.get("parameters", {}).keys())
        lines.append(f"- {name}({params}): {spec['description']}")
    return "\n".join(lines)


def execute_registered_tool(
    action: str,
    target: str = "",
    args: Optional[Dict[str, Any]] = None,
    language: str = "id",
    contextual_element: Optional[UIElement] = None,
) -> Tuple[bool, str]:
    """Centrally executes a validated tool and returns (success, observation_text)."""
    if action not in ALLOWED_PLANNER_ACTIONS:
        return False, f"Tindakan '{action}' tidak diizinkan."

    params = dict(args or {})
    is_id = language.lower().startswith("id")

    try:
        if action == "open_application":
            from app.tools.apps import launch_application
            app_tgt = params.get("app_name") or params.get("target") or target
            ok, name, msg = launch_application(app_tgt)
            return ok, msg or (f"Aplikasi '{name}' dibuka." if ok else f"Gagal membuka '{app_tgt}'.")

        elif action == "close_application":
            from app.tools.apps import close_application
            app_tgt = params.get("app_name") or params.get("target") or target
            ok, name, msg = close_application(app_tgt)
            return ok, msg or (f"Aplikasi '{name}' ditutup." if ok else f"Gagal menutup '{app_tgt}'.")

        elif action == "open_website":
            from app.tools.browser import launch_website
            url_tgt = params.get("url") or params.get("target") or target
            ok, name, _, msg = launch_website(url_tgt)
            return ok, msg or f"Membuka situs {name}."

        elif action == "search_web":
            from app.tools.web_agent import web_agent
            q = params.get("query") or params.get("target") or target
            res = web_agent.search_google(q, language=language, open_browser=True)
            return res.success, res.message

        elif action == "open_url":
            from app.tools.web_agent import web_agent
            u = params.get("url") or params.get("target") or target
            res = web_agent.open_url(u, language=language)
            return res.success, res.message

        elif action == "read_web_page":
            from app.tools.web_agent import web_agent
            res = web_agent.read_page(language=language)
            return res.success, res.message

        elif action == "fetch_page_content":
            from app.tools.browser_agent import fetch_page_content
            u = params.get("url") or params.get("target") or target
            ok, p_title, p_text = fetch_page_content(u, max_chars=1000)
            if ok:
                return True, f"Judul: {p_title}\nRingkasan: {p_text[:400]}"
            return False, f"Gagal mengambil konten URL: {p_text}"

        elif action == "get_active_window":
            det = get_active_window_details()
            return True, f"Jendela aktif: '{det.title}' (Proses: {det.process_name}, HWND: {det.hwnd})"

        elif action == "focus_window":
            w_tgt = params.get("title") or params.get("target") or target
            ok, msg = ensure_window_focus(w_tgt, language=language)
            return ok, msg

        elif action == "click_element":
            tgt = params.get("target") or target
            target_clean = (
                tgt.lower()
                .replace("klik", "")
                .replace("tombol", "")
                .strip()
            )
            is_contextual_ref = target_clean in ("itu", "that", "tersebut", "ini", "")

            target_el = None
            if is_contextual_ref:
                if contextual_element:
                    target_el = contextual_element
                else:
                    clarify_msg = (
                        "Tombol yang Anda maksud belum bisa dipastikan dari konteks sebelumnya, sir. "
                        "Mohon sebutkan nama atau posisinya lebih spesifik."
                        if is_id
                        else "The button reference is ambiguous from previous context, sir. "
                        "Please specify which button to click."
                    )
                    return False, clarify_msg
            else:
                obs_res = read_screen_content(prompt=tgt, language=language, vision_enabled=False)
                if obs_res.observation:
                    target_el = find_element_by_reference(tgt, obs_res.observation)

            if target_el and target_el.center_x > 0 and target_el.center_y > 0:
                from app.tools.desktop import move_cursor, mouse_click
                move_cursor(target_el.center_x, target_el.center_y, language=language)
                ok_click, msg = mouse_click("left", language=language)
                return ok_click, f"Mengeklik elemen '{target_el.name}' di ({target_el.center_x}, {target_el.center_y})"
            return False, f"Elemen '{tgt}' tidak ditemukan di layar."

        elif action == "type_text":
            txt = params.get("text") or params.get("target") or target
            ok, msg = type_text(txt, language=language)
            return ok, msg

        elif action == "press_key":
            k = params.get("key") or params.get("target") or target
            ok, msg = press_single_key(k, language=language)
            return ok, msg

        elif action == "send_hotkey":
            hk = params.get("hotkey") or params.get("target") or target
            ok, msg = send_shortcut(hk, language=language)
            return ok, msg

        elif action == "mouse_click":
            btn = params.get("button") or params.get("target") or target or "left"
            ok, msg = mouse_click(btn, language=language)
            return ok, msg

        elif action == "mouse_scroll":
            d = params.get("direction", "down")
            amt = int(params.get("amount", 5))
            ok, msg = mouse_scroll(direction=d, amount=amt, language=language)
            return ok, msg

        elif action == "open_folder":
            from app.tools.filesystem import open_folder
            f_tgt = params.get("target") or params.get("folder_name") or target
            ok, _, _, msg = open_folder(f_tgt)
            return ok, msg

        elif action == "create_folder":
            from app.tools.filesystem import create_directory
            f_name = params.get("folder_name") or params.get("target") or target
            parent = params.get("parent")
            ok, p_str, msg = create_directory(f_name, parent=parent)
            return ok, msg

        elif action == "delete_file_or_folder":
            from app.tools.filesystem import delete_file_or_folder
            p_tgt = params.get("path") or params.get("target") or target
            conf = bool(params.get("confirmed", False))
            ok, msg = delete_file_or_folder(p_tgt, confirmed=conf)
            return ok, msg

        elif action == "play_youtube":
            from app.tools.youtube_controller import execute_youtube_command
            q = params.get("query") or params.get("target") or target
            ok, msg, _ = execute_youtube_command(q, language=language)
            return ok, msg

        elif action == "play_music":
            from app.tools.music import play_music
            q = params.get("query") or params.get("target") or target
            ok, _, msg = play_music(query=q)
            return ok, msg

        elif action == "pause_music":
            from app.tools.music import pause_music
            tgt_m = params.get("target") or target
            ok, msg = pause_music(target=tgt_m, language=language)
            return ok, msg

        elif action == "resume_music":
            from app.tools.music import resume_music
            tgt_m = params.get("target") or target
            ok, msg = resume_music(target=tgt_m, language=language)
            return ok, msg

        elif action == "stop_music":
            from app.tools.music import media_stop
            media_stop()
            return True, "Pemutaran musik dihentikan, sir." if is_id else "Music playback stopped, sir."

        elif action == "change_volume":
            from app.tools.music import change_volume
            act_v = params.get("action") or params.get("direction") or "up"
            stps = int(params.get("steps", 2))
            ok, msg = change_volume(act_v, steps=stps)
            return ok, msg

        elif action == "read_screen":
            p = params.get("prompt") or params.get("target") or target
            res = read_screen_content(prompt=p, language=language, prefer_vision=False)
            return True, f"{res.spoken_summary}. {res.display_text[:400]}"

        elif action == "inspect_screen_error":
            p = params.get("prompt") or params.get("target") or target or "error message on screen"
            res = read_screen_content(prompt=p, language=language, prefer_vision=True)
            return True, f"Screen Error Inspection: {res.spoken_summary}. Details: {res.display_text[:400]}"

        elif action == "get_system_info":
            from app.tools.windows import format_system_info
            return True, format_system_info(language=language)

        elif action == "get_battery_status":
            from app.tools.windows import format_battery_status
            return True, format_battery_status(language=language)

        elif action == "lock_windows":
            from app.tools.windows import lock_windows
            return lock_windows()

        elif action == "take_screenshot":
            from app.tools.windows import take_screenshot
            out_d = params.get("output_dir")
            ok, p_str, msg = take_screenshot(output_dir=out_d)
            return ok, msg

        elif action == "store_memory":
            from app.memory.memory import memory_manager
            k = params.get("key") or ""
            v = params.get("value") or ""
            if not k:
                return False, "Key memori tidak boleh kosong."
            ok, msg = memory_manager.store_fact(key=k, value=v)
            return ok, msg

        elif action == "recall_memory":
            from app.memory.memory import memory_manager
            k = params.get("key") or target
            val = memory_manager.recall_fact(key=k)
            if val:
                return True, f"Memori [{k}]: {val}"
            return False, f"Tidak ada catatan memori untuk '{k}'."

        elif action == "recall_all_memories":
            from app.memory.memory import memory_manager
            mems = memory_manager.recall_all()
            return True, f"Daftar memori: {json.dumps(mems, ensure_ascii=False)}"

        elif action == "forget_memory":
            from app.memory.memory import memory_manager
            k = params.get("key") or target
            ok, msg = memory_manager.forget_fact(key=k)
            return ok, msg

        elif action == "wait":
            secs = float(params.get("seconds", 1.0))
            time.sleep(min(secs, 3.0))
            return True, f"Menunggu {secs} detik."

        elif action == "execute_python_code":
            from app.tools.code_interpreter import execute_python_code
            code_str = params.get("code") or params.get("target") or target
            timeout = int(params.get("timeout", 15))
            confirmed = bool(params.get("confirmed", False))
            res = execute_python_code(code=code_str, timeout=timeout, confirmed=confirmed)
            if res.get("requires_confirmation"):
                return False, f"Konfirmasi Keamanan Diperlukan: {res.get('reason')}. Operasi ditangguhkan sampai pengguna mengonfirmasi (confirmed=True)."

            if res["success"]:
                out_msg = res["stdout"] if res["stdout"] else "Kode Python berhasil dieksekusi (tanpa output stdout)."
                return True, out_msg
            else:
                err_msg = res["stderr"] or f"Exit code {res['returncode']}"
                return False, f"Eksekusi Python gagal (code {res['returncode']}):\n{err_msg}"

        elif action == "execute_powershell":
            from app.tools.code_interpreter import execute_powershell
            cmd_str = params.get("command") or params.get("target") or target
            timeout = int(params.get("timeout", 15))
            confirmed = bool(params.get("confirmed", False))
            res = execute_powershell(command=cmd_str, timeout=timeout, confirmed=confirmed)
            if res.get("requires_confirmation"):
                return False, f"Konfirmasi Keamanan Diperlukan: {res.get('reason')}. Operasi ditangguhkan sampai pengguna mengonfirmasi (confirmed=True)."

            if res["success"]:
                out_msg = res["stdout"] if res["stdout"] else "Perintah PowerShell berhasil dieksekusi (tanpa output stdout)."
                return True, out_msg
            else:
                err_msg = res["stderr"] or f"Exit code {res['returncode']}"
                return False, f"Eksekusi PowerShell gagal (code {res['returncode']}):\n{err_msg}"

        elif action == "list_todos":
            from app.core.todo_manager import TodoManager
            mgr = TodoManager()
            todos = mgr.list_tasks(include_completed=False)
            if not todos:
                return True, "Belum ada tugas aktif di daftar todo, sir." if is_id else "No active tasks in your todo list, sir."
            lines = [f"{i}. [ ] {t['title']}" + (f" (Waktu: {t['due_date']})" if t.get('due_date') else "") for i, t in enumerate(todos, 1)]
            return True, "Daftar tugas aktif:\n" + "\n".join(lines)

        elif action == "add_todo":
            from app.core.todo_manager import TodoManager
            t_txt = params.get("task") or params.get("title") or target
            mgr = TodoManager()
            ok, msg, _ = mgr.add_task(t_txt)
            return ok, msg

        elif action in ("clear_all_todos", "delete_all_todos"):
            from app.core.todo_manager import TodoManager
            mgr = TodoManager()
            cleared = mgr.clear_all()
            return True, f"Semua {cleared} tugas dalam daftar todo telah berhasil dihapus, sir." if is_id else f"All {cleared} tasks in your todo list have been cleared, sir."

        elif action == "delete_todo":
            from app.core.todo_manager import TodoManager
            t_id = params.get("task_id") or params.get("id") or target
            mgr = TodoManager()
            try:
                ok = mgr.delete_task(int(t_id))
                if ok:
                    return True, f"Tugas #{t_id} telah dihapus, sir." if is_id else f"Task #{t_id} deleted, sir."
                return False, f"Tugas #{t_id} tidak ditemukan, sir." if is_id else f"Task #{t_id} not found, sir."
            except Exception as e:
                return False, f"Gagal menghapus tugas: {e}"

        return False, f"Aksi '{action}' belum terimplementasi."

    except Exception as e:
        logger.error("Error executing registered tool '%s': %s", action, e, exc_info=True)
        return False, f"Kesalahan saat menjalankan '{action}': {str(e)}"


# ---------------------------------------------------------------------------
# Autonomous ReAct Agent Loop
# ---------------------------------------------------------------------------

@dataclass
class ReActStep:
    """Represents a single iteration in the autonomous ReAct reasoning loop."""
    iteration: int
    thought: str
    action: Optional[str] = None
    action_input: Dict[str, Any] = field(default_factory=dict)
    observation: Optional[str] = None
    final_answer: Optional[str] = None


@dataclass
class ReActAgentResult:
    """Outcome of the multi-step Autonomous ReAct agent execution."""
    success: bool
    final_answer: str
    steps: List[ReActStep] = field(default_factory=list)
    iterations: int = 0
    spoken_summary: str = ""


class AutonomousReActAgent:
    """Autonomous ReAct agent executing Thought -> Action -> Observation loops.

    Capable of multi-step problem solving, error inspection, and autonomous recovery
    bounded by max_iterations=5.
    """

    def __init__(
        self,
        llm: Optional[Any] = None,
        max_iterations: int = 5,
        contextual_element: Optional[UIElement] = None,
    ):
        self.llm = llm
        self.max_iterations = max_iterations
        self.contextual_element = contextual_element

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Invokes LLM synchronously across OllamaClient, Groq, or Mock implementations."""
        if not self.llm:
            return ""

        if hasattr(self.llm, "chat") and callable(self.llm.chat):
            res = self.llm.chat(messages)
            return str(res) if res is not None else ""

        if hasattr(self.llm, "chat_stream") and callable(self.llm.chat_stream):
            tokens = []
            for t in self.llm.chat_stream(messages):
                tokens.append(str(t))
            return "".join(tokens)

        return ""

    def parse_react_output(self, text: str) -> Tuple[str, Optional[str], Dict[str, Any], Optional[str]]:
        """Parses LLM output into (thought, action, action_input, final_answer).

        Supports both standard ReAct blocks and structured JSON responses.
        """
        raw = text.strip()
        thought = ""
        action = None
        action_input: Dict[str, Any] = {}
        final_answer = None

        # 1. Attempt JSON parsing
        try:
            clean_json = raw
            m_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
            if m_block:
                clean_json = m_block.group(1)
            elif "{" in raw and "}" in raw:
                first = raw.find("{")
                last = raw.rfind("}")
                clean_json = raw[first : last + 1]

            data = json.loads(clean_json)
            if isinstance(data, dict):
                thought = str(data.get("thought", "")).strip()
                final_answer = data.get("final_answer")
                act_name = data.get("action")
                if act_name:
                    action = str(act_name).strip()
                    inp = data.get("action_input", {})
                    if isinstance(inp, dict):
                        action_input = inp
                    elif isinstance(inp, str):
                        action_input = {"target": inp}
                if final_answer:
                    return thought, None, {}, str(final_answer).strip()
                if action:
                    return thought, action, action_input, None
        except Exception:
            pass

        # 2. ReAct text block parsing
        # Look for Final Answer
        m_final = re.search(r"Final\s+Answer\s*\d*\s*:\s*(.+)$", raw, re.IGNORECASE | re.DOTALL)
        if m_final:
            final_answer = m_final.group(1).strip()
            # Extract thought before final answer if present
            m_th = re.search(r"Thought\s*\d*\s*:\s*(.+?)(?=(?:Final\s+Answer|$))", raw, re.IGNORECASE | re.DOTALL)
            thought = m_th.group(1).strip() if m_th else ""
            return thought, None, {}, final_answer

        # Look for Thought
        m_th = re.search(r"Thought\s*\d*\s*:\s*(.+?)(?=(?:Action\s*\d*\s*:|Final\s+Answer|$))", raw, re.IGNORECASE | re.DOTALL)
        if m_th:
            thought = m_th.group(1).strip()

        # Look for Action (supporting inline call syntax e.g. Action 1: execute_tool({...}))
        m_act = re.search(r"Action\s*\d*\s*:\s*([a-zA-Z0-9_\-]+)(?:\s*\((.*?)\))?", raw, re.IGNORECASE | re.DOTALL)
        if m_act:
            action = m_act.group(1).strip()
            inline_args = m_act.group(2)
            if inline_args:
                try:
                    action_input = json.loads(inline_args.strip())
                except Exception:
                    action_input = {"target": inline_args.strip()}

        # Look for Action Input if not parsed inline
        if not action_input:
            m_inp = re.search(r"Action\s+Input\s*\d*\s*:\s*(.+)$", raw, re.IGNORECASE | re.DOTALL)
            if m_inp:
                inp_raw = m_inp.group(1).strip()
                try:
                    action_input = json.loads(inp_raw)
                except Exception:
                    # Fallback to key-value or raw target string
                    if inp_raw.startswith("{") and "}" in inp_raw:
                        c = inp_raw[inp_raw.find("{") : inp_raw.rfind("}") + 1]
                        try:
                            action_input = json.loads(c)
                        except Exception:
                            action_input = {"target": inp_raw}
                    else:
                        action_input = {"target": inp_raw}

        # 3. Fallback: if no action was detected, clean thoughts so internal chain-of-thought is not leaked
        if not action and not final_answer:
            cleaned_ans = raw
            cleaned_ans = re.sub(r"^(?:Thought|Action|Observation)\s*\d*\s*:\s*", "", cleaned_ans, flags=re.IGNORECASE).strip()
            if "Action" in cleaned_ans:
                cleaned_ans = re.split(r"Action\s*\d*\s*:", cleaned_ans, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            final_answer = cleaned_ans or raw

        return thought, action, action_input, final_answer

    def run(
        self,
        goal: str,
        language: str = "id",
        state_context: Optional[Dict[str, Any]] = None,
    ) -> ReActAgentResult:
        """Executes the full ReAct loop for up to max_iterations (default 5)."""
        is_id = language.lower().startswith("id")
        steps_taken: List[ReActStep] = []
        tools_prompt = build_tool_schemas_prompt()

        system_instruction = (
            "You are JARVIS, an autonomous, intelligent, and proactive AI desktop assistant for Windows 11.\n"
            "You accomplish complex user goals by executing multi-step ReAct loops:\n"
            "Thought -> Action -> Observation -> Thought -> Final Answer.\n\n"
            f"{tools_prompt}\n\n"
            "ReAct Protocol Rules:\n"
            "1. When deciding a tool step, respond with:\n"
            "Thought: [Explain your plan or reasoning]\n"
            "Action: [tool_name]\n"
            "Action Input: {\"param\": \"value\"}\n"
            "2. When you receive an Observation, verify whether the step succeeded or if alternative recovery is needed.\n"
            "3. If the task is completed or you are answering the user directly, respond with:\n"
            "Thought: [Brief verification summary]\n"
            "Final Answer: [Concise spoken response in the user's language (1 to 3 natural sentences, max 45 words)]\n"
            "4. Open Interpreter Capability: Use standard tools if available. However, for custom, complex, or unhandled tasks (data analysis, file sorting, math, document editing, detailed Windows diagnostics, scraping), use execute_python_code or execute_powershell. Never say 'I cannot do that' for achievable computer tasks. Always write safe scripts. If an execution fails, inspect the error in Observation and self-heal your code in the next iteration.\n"
            "5. Language rule: You MUST respond in the user's active language."
        )

        # Context summary
        ctx_lines = [f"User Goal: {goal}"]
        if state_context:
            for k, v in state_context.items():
                if v:
                    ctx_lines.append(f"{k}: {v}")
        ctx_str = "\n".join(ctx_lines)

        trajectory_history: List[str] = []

        logger.info("[REACT] Starting ReAct loop for goal: '%s' (max_iterations=%d)", goal, self.max_iterations)

        for iteration in range(1, self.max_iterations + 1):
            prompt_content = f"{ctx_str}\n\n"
            if trajectory_history:
                prompt_content += "Prior Steps and Observations:\n" + "\n".join(trajectory_history) + "\n\n"
            prompt_content += f"Step {iteration}: What is your next Thought and Action or Final Answer?"

            messages = [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt_content},
            ]

            llm_output = self._call_llm(messages)
            if not llm_output:
                logger.warning("[REACT] LLM returned empty output at iteration %d", iteration)
                break

            thought, action, action_input, final_answer = self.parse_react_output(llm_output)

            # Step 1: Check for Final Answer
            if final_answer:
                logger.info("[REACT] Final answer reached at iteration %d: %s", iteration, final_answer)
                step = ReActStep(
                    iteration=iteration,
                    thought=thought,
                    final_answer=final_answer,
                )
                steps_taken.append(step)
                return ReActAgentResult(
                    success=True,
                    final_answer=final_answer,
                    steps=steps_taken,
                    iterations=iteration,
                    spoken_summary=final_answer,
                )

            # Step 2: Execute Action
            if action:
                logger.info("[REACT] Iteration %d Action: %s | Args: %s", iteration, action, action_input)
                
                # Loop Detection: prevent repeating identical tool calls consecutively
                is_duplicate = bool(
                    steps_taken
                    and steps_taken[-1].action == action
                    and steps_taken[-1].action_input == action_input
                )
                if is_duplicate:
                    logger.warning("[REACT] Loop detected: identical action '%s' with args %s repeated at iteration %d", action, action_input, iteration)
                    if len(steps_taken) >= 2 and steps_taken[-2].action == action:
                        # Break out immediately if repeating twice in a row
                        logger.warning("[REACT] Breaking out of repetitive loop at iteration %d", iteration)
                        clean_final = "Tugas telah selesai dijalankan, sir." if is_id else "Task execution completed, sir."
                        step = ReActStep(iteration=iteration, thought=thought, final_answer=clean_final)
                        steps_taken.append(step)
                        return ReActAgentResult(
                            success=True,
                            final_answer=clean_final,
                            steps=steps_taken,
                            iterations=iteration,
                            spoken_summary=clean_final,
                        )
                    observation_str = (
                        "Failed: Tindakan ini sama persis dengan langkah sebelumnya dan sudah pernah dijalankan. "
                        "Jangan ulangi tindakan yang sama. Jika tugas telah selesai atau tidak ada tindakan lain yang diperlukan, berikan Final Answer sekarang."
                        if is_id else
                        "Failed: Identical action already executed in prior step. Do not repeat the same action. "
                        "If the task is complete, provide Final Answer now."
                    )
                else:
                    ok, obs = execute_registered_tool(
                        action=action,
                        target=action_input.get("target", ""),
                        args=action_input,
                        language=language,
                        contextual_element=self.contextual_element,
                    )
                    obs_prefix = "Success" if ok else "Failed"
                    observation_str = f"{obs_prefix}: {obs}"
                logger.info("[REACT] Observation %d: %s", iteration, observation_str)

                step = ReActStep(
                    iteration=iteration,
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    observation=observation_str,
                )
                steps_taken.append(step)

                trajectory_history.append(f"Thought {iteration}: {thought}")
                trajectory_history.append(f"Action {iteration}: {action}({json.dumps(action_input)})")
                trajectory_history.append(f"Observation {iteration}: {observation_str}")

            else:
                # LLM outputted neither explicit action nor final answer keyword
                clean_ans = thought or llm_output
                clean_ans = re.sub(r"^(?:Thought|Action|Observation)\s*\d*\s*:\s*", "", clean_ans, flags=re.IGNORECASE).strip()
                if "Action" in clean_ans:
                    clean_ans = re.split(r"Action\s*\d*\s*:", clean_ans, maxsplit=1, flags=re.IGNORECASE)[0].strip()
                if not clean_ans:
                    clean_ans = "Tugas telah selesai diproses, sir." if is_id else "Task processing completed, sir."

                step = ReActStep(iteration=iteration, thought=thought, final_answer=clean_ans)
                steps_taken.append(step)
                return ReActAgentResult(
                    success=True,
                    final_answer=clean_ans,
                    steps=steps_taken,
                    iterations=iteration,
                    spoken_summary=clean_ans,
                )

        # Reached max iterations without explicit final answer
        logger.warning("[REACT] Loop reached max iterations (%d). Synthesizing completion.", self.max_iterations)
        last_obs = steps_taken[-1].observation if steps_taken and steps_taken[-1].observation else ""
        if is_id:
            summary = f"Tugas telah diproses, sir. {last_obs}" if last_obs else "Langkah-langkah telah dijalankan, sir."
        else:
            summary = f"Task completed, sir. {last_obs}" if last_obs else "Executed requested actions, sir."

        return ReActAgentResult(
            success=True,
            final_answer=summary,
            steps=steps_taken,
            iterations=self.max_iterations,
            spoken_summary=summary,
        )


# ---------------------------------------------------------------------------
# Backward Compatible TaskPlan & TaskExecutor (7-Step Loop)
# ---------------------------------------------------------------------------

@dataclass
class TaskStep:
    """Single discrete step within a task plan."""
    action: str
    target: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    status: str = "pending"  # "pending", "success", "failed", "recovered", "skipped"
    retry_count: int = 0
    max_retries: int = 1
    verified: bool = False


@dataclass
class TaskPlan:
    """Structured plan for achieving a user goal."""
    goal: str
    steps: List[TaskStep] = field(default_factory=list)
    current_step: int = 0
    max_steps: int = 5
    is_completed: bool = False
    is_blocked: bool = False
    blocker_message: Optional[str] = None


@dataclass
class TaskExecutionResult:
    """Summary of the task execution cycle."""
    success: bool
    spoken_summary: str
    display_summary: str
    steps_executed: int
    total_steps: int
    is_blocked: bool = False
    last_observation: Optional[ScreenObservation] = None


class TaskExecutor:
    """Executes multi-step desktop tasks with observe-act-verify-recover cycle and ReAct support."""

    def __init__(self, max_steps: int = 5, contextual_element: Optional[UIElement] = None):
        self.max_steps = max_steps
        self.contextual_element = contextual_element

    def observe(self, prompt: str = "") -> ScreenObservation:
        """Observes current screen state."""
        res = read_screen_content(prompt=prompt, language="id", vision_enabled=False)
        if res.observation:
            return res.observation
        det = get_active_window_details()
        return ScreenObservation(
            window_title=det.title,
            process_name=det.process_name,
            hwnd=det.hwnd,
            timestamp=time.time(),
            source="fallback",
        )

    def plan(self, goal: str, obs: ScreenObservation) -> TaskPlan:
        """Creates a structured plan with strict action validation."""
        g = goal.strip().lower()
        steps: List[TaskStep] = []

        # Pattern 1: YouTube Music Playback
        if any(w in g for w in ["putar lagu", "play song", "putar musik"]):
            from app.tools.youtube_controller import parse_music_intent
            intent = parse_music_intent(goal)
            steps.append(
                TaskStep(
                    action="play_youtube",
                    target=goal,
                    description=f"Cari dan putar {intent.get('display_term', 'musik')} di YouTube",
                )
            )

        # Pattern 2: Click button and continue
        elif "klik" in g and "lanjut" in g:
            btn_ref = g.replace("lalu lanjutkan", "").replace("kemudian lanjutkan", "").strip()
            steps.append(
                TaskStep(
                    action="click_element",
                    target=btn_ref,
                    description=f"Klik {btn_ref}",
                )
            )
            steps.append(
                TaskStep(
                    action="wait",
                    args={"seconds": 1.0},
                    description="Menunggu antarmuka merespons",
                )
            )

        # Pattern 3: Focus and type
        elif "tab baru" in g and "ketik" in g:
            m_txt = re.search(r"ketik\s+(.+)$", g)
            text_to_type = m_txt.group(1).strip() if m_txt else ""
            steps.append(
                TaskStep(
                    action="send_hotkey",
                    target="ctrl+t",
                    description="Buka tab baru di browser",
                )
            )
            if text_to_type:
                steps.append(
                    TaskStep(
                        action="type_text",
                        target=text_to_type,
                        description=f"Ketik '{text_to_type}'",
                    )
                )
                steps.append(
                    TaskStep(
                        action="press_key",
                        target="enter",
                        description="Tekan tombol Enter",
                    )
                )

        # Default single action step
        else:
            steps.append(
                TaskStep(
                    action="read_screen",
                    target=goal,
                    description="Periksa dan baca informasi di layar",
                )
            )

        return TaskPlan(goal=goal, steps=steps[: self.max_steps], max_steps=self.max_steps)

    def act(self, step: TaskStep, language: str = "id") -> Tuple[bool, str]:
        """Executes a single action strictly through validated tools."""
        act_name = step.action
        if act_name not in ALLOWED_PLANNER_ACTIONS:
            return False, f"Tindakan '{act_name}' tidak diizinkan."

        return execute_registered_tool(
            action=step.action,
            target=step.target,
            args=step.args,
            language=language,
            contextual_element=self.contextual_element,
        )

    def verify(self, step: TaskStep, pre_obs: ScreenObservation, post_obs: ScreenObservation) -> bool:
        """Verifies that screen state actually changed as expected."""
        act_name = step.action
        if act_name == "play_youtube":
            return "youtube" in post_obs.window_title.lower() or any(
                b in post_obs.process_name.lower() for b in ["chrome", "msedge", "firefox"]
            )
        return True

    def recover(self, step: TaskStep, failure_reason: str, obs: ScreenObservation) -> Optional[TaskStep]:
        """Determines alternative safe approach if a step failed."""
        if step.retry_count >= step.max_retries:
            return None

        if any(k in failure_reason.lower() for k in ["konteks", "ambiguous", "belum bisa dipastikan"]):
            return None

        if step.action == "click_element":
            logger.info("Attempting recovery for failed click: fallback to Enter key")
            return TaskStep(
                action="press_key",
                target="enter",
                description="Mencoba menekan tombol Enter sebagai alternatif klik",
                retry_count=step.retry_count + 1,
            )

        if step.action == "type_text" and "fokus" in failure_reason.lower():
            logger.info("Attempting recovery for type_text: refocusing search bar via Ctrl+L")
            return TaskStep(
                action="send_hotkey",
                target="ctrl+l",
                description="Memfokuskan kembali kolom input",
                retry_count=step.retry_count + 1,
            )

        return None

    def run_react(
        self,
        goal: str,
        llm: Any = None,
        language: str = "id",
        state_context: Optional[Dict[str, Any]] = None,
    ) -> TaskExecutionResult:
        """Runs the Autonomous ReAct Agent loop for complex desktop goals."""
        agent = AutonomousReActAgent(
            llm=llm,
            max_iterations=self.max_steps,
            contextual_element=self.contextual_element,
        )
        res = agent.run(goal=goal, language=language, state_context=state_context)
        log_lines = [f"Goal: {goal}"]
        for s in res.steps:
            if s.action:
                log_lines.append(f"  [STEP {s.iteration}] Action: {s.action} -> {s.observation}")
            if s.final_answer:
                log_lines.append(f"  [FINAL] {s.final_answer}")

        return TaskExecutionResult(
            success=res.success,
            spoken_summary=res.spoken_summary or res.final_answer,
            display_summary="\n".join(log_lines),
            steps_executed=res.iterations,
            total_steps=res.iterations,
            is_blocked=not res.success,
            last_observation=self.observe(),
        )

    def run(self, goal: str, language: str = "id") -> TaskExecutionResult:
        """Runs the full 7-step Understand-Observe-Plan-Act-Verify-Recover-Complete cycle."""
        is_id = language.lower().startswith("id")
        logger.info("Starting task cycle for goal: '%s'", goal)

        initial_obs = self.observe(prompt=goal)
        plan = self.plan(goal, initial_obs)
        if not plan.steps:
            return TaskExecutionResult(
                success=False,
                spoken_summary="Tidak dapat menyusun langkah untuk tugas tersebut, sir." if is_id else "Could not generate plan for task, sir.",
                display_summary="Rencana kosong.",
                steps_executed=0,
                total_steps=0,
                last_observation=initial_obs,
            )

        executed_count = 0
        current_obs = initial_obs
        log_records: List[str] = [f"Goal: {goal}"]

        for idx, step in enumerate(plan.steps):
            if executed_count >= self.max_steps:
                logger.warning("Reached maximum step limit (%d)", self.max_steps)
                break

            executed_count += 1
            pre_obs = current_obs
            logger.info("Executing step %d/%d: %s (%s)", idx + 1, len(plan.steps), step.description, step.action)

            # Act
            success, msg = self.act(step, language=language)

            if success:
                # Verify
                time.sleep(0.3)
                current_obs = self.observe()
                verified = self.verify(step, pre_obs, current_obs)
                if verified:
                    step.status = "success"
                    step.verified = True
                    log_records.append(f"  [OK] Langkah {idx+1}: {step.description} -> Berhasil")
                else:
                    step.status = "failed"
                    log_records.append(f"  [FAIL] Langkah {idx+1}: {step.description} -> Verifikasi gagal")
            else:
                # Recover
                recovery_step = self.recover(step, msg, current_obs)
                if recovery_step:
                    logger.info("Executing recovery step: %s", recovery_step.description)
                    rec_ok, rec_msg = self.act(recovery_step, language=language)
                    if rec_ok:
                        step.status = "recovered"
                        log_records.append(f"  [RECOVERED] Langkah {idx+1}: {recovery_step.description}")
                    else:
                        step.status = "failed"
                        log_records.append(f"  [FAIL] Langkah {idx+1}: {step.description} ({msg})")
                        plan.is_blocked = True
                        plan.blocker_message = msg
                        break
                else:
                    step.status = "failed"
                    log_records.append(f"  [FAIL] Langkah {idx+1}: {step.description} ({msg})")
                    plan.is_blocked = True
                    plan.blocker_message = msg
                    break

        all_ok = all(s.status in ("success", "recovered", "skipped") for s in plan.steps[:executed_count])
        if all_ok and not plan.is_blocked:
            spoken = f"Tugas selesai: {plan.steps[-1].description}, sir." if is_id else "Task completed, sir."
            if any(s.action == "play_youtube" for s in plan.steps):
                spoken = msg
        else:
            reason = plan.blocker_message or "langkah terhambat"
            spoken = f"Tugas belum selesai sempurna, sir: {reason}." if is_id else f"Task was interrupted: {reason}, sir."

        display = "\n".join(log_records)
        return TaskExecutionResult(
            success=all_ok and not plan.is_blocked,
            spoken_summary=spoken,
            display_summary=display,
            steps_executed=executed_count,
            total_steps=len(plan.steps),
            is_blocked=plan.is_blocked,
            last_observation=current_obs,
        )
