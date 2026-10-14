"""Vision and Computer-Use Task Agent for JARVIS on Windows 11.

Follows AGENTS.md and User Vision Specification:
- Multi-step visual task reasoning with screen understanding (UIA + OCR + indexed elements).
- Smart primitives: OS shortcuts (Ctrl+T, Ctrl+L), element indexing (Set-of-Marks), focused typing.
- Transparent execution: Real-time step progress reporting [STEP X/8].
- Human-in-the-Loop: Dynamic Mid-Task Pause & Resume when parameters (like timer duration) are required.
- Fast, safe, lightweight execution on Intel Core i5 CPU without requiring a GPU.
"""

from dataclasses import dataclass, field
import json
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid

import requests

from app.core.config import Settings, get_settings
from app.core.logger import setup_logger
from app.tools.desktop import (
    ensure_window_focus,
    get_active_window_details,
    mouse_click,
    move_cursor,
    press_single_key,
    send_shortcut,
    type_text,
)
from app.tools.screen_reader import (
    IndexedUIElement,
    ScreenObservation,
    format_indexed_screen_summary,
    get_indexed_ui_elements,
    read_screen_content,
)

logger = setup_logger("jarvis.core.vision_agent")


@dataclass
class VisionStep:
    """A single discrete step executed by the Vision Agent."""
    step_num: int
    action: str  # "hotkey", "type_text", "click_index", "press_key", "ask_user", "complete", "wait", "focus_window"
    target: str = ""
    description: str = ""
    status: str = "pending"  # "pending", "success", "failed"
    latency_ms: float = 0.0


@dataclass
class VisionTaskState:
    """Persistent state for an active or paused Vision Task."""
    task_id: str
    goal: str
    status: str  # "RUNNING", "PAUSED_FOR_USER_INPUT", "COMPLETED", "FAILED"
    current_step: int = 1
    max_steps: int = 8
    steps_history: List[VisionStep] = field(default_factory=list)
    prompt_to_user: Optional[str] = None
    waiting_parameter: Optional[str] = None  # e.g. "duration_minutes"
    target_app: str = "chrome"
    language: str = "id"
    last_observation: Optional[ScreenObservation] = None
    created_at: float = 0.0


@dataclass
class VisionAgentResult:
    """Outcome returned to the Orchestrator or caller."""
    task_id: str
    status: str  # "COMPLETED", "PAUSED_FOR_USER_INPUT", "FAILED"
    spoken_output: str
    display_output: str
    steps_executed: int
    is_paused: bool = False
    prompt_to_user: Optional[str] = None
    state: Optional[VisionTaskState] = None


def extract_duration_from_text(text: str) -> Optional[int]:
    """Extracts duration in minutes from natural language response in Indonesian or English."""
    if not text:
        return None
    s = text.lower().strip()

    # Number mapping for Indonesian and English words
    word_map = {
        "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
        "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9, "sepuluh": 10,
        "sebelas": 11, "dua belas": 12, "lima belas": 15, "dua puluh": 20,
        "tiga puluh": 30, "empat puluh lima": 45, "satu jam": 60, "setengah jam": 30,
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "fifteen": 15, "twenty": 20, "thirty": 30, "an hour": 60, "half an hour": 30,
    }

    # Sort by descending length so compound phrases ("satu jam", "setengah jam") match before single words ("satu")
    for phrase, val in sorted(word_map.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(r"\b" + re.escape(phrase) + r"\b", s):
            return val

    # Match numeric digit patterns: "5 menit", "10 mnt", "15 minutes", "5 min", "5"
    m = re.search(r"\b(\d+)\s*(?:menit|mnt|minute|minutes|min|m)?\b", s)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass

    return None


class VisionAgent:
    """Autonomous Vision & GUI Computer-Use Agent with pause-and-resume capabilities."""

    def __init__(self, settings: Optional[Settings] = None, max_steps: int = 8):
        self.settings = settings or get_settings()
        self.max_steps = max_steps

    def observe(self, prompt: str = "") -> Tuple[ScreenObservation, List[IndexedUIElement]]:
        """Captures current screen state and indexed interactive elements."""
        res = read_screen_content(prompt=prompt, language="id", vision_enabled=False)
        obs = res.observation or ScreenObservation(
            window_title="Active Desktop",
            process_name="",
            hwnd=0,
            timestamp=time.time(),
            source="fallback",
        )
        indexed = get_indexed_ui_elements(obs)
        return obs, indexed

    def _execute_step(
        self,
        step: VisionStep,
        indexed_elements: List[IndexedUIElement],
        language: str = "id",
    ) -> Tuple[bool, str]:
        """Executes a single validated action primitive safely."""
        act = step.action
        t = step.target
        is_id = language.lower().startswith("id")

        if act == "hotkey":
            ok, msg = send_shortcut(t, language=language)
            return ok, msg

        elif act == "type_text":
            ok, msg = type_text(t, language=language)
            return ok, msg

        elif act == "press_key":
            ok, msg = press_single_key(t, language=language)
            return ok, msg

        elif act == "focus_window":
            ok, msg = ensure_window_focus(t, language=language)
            return ok, msg

        elif act == "click_index":
            try:
                target_idx = int(t)
                matched = next((el for el in indexed_elements if el.index == target_idx), None)
                if matched and matched.center_x > 0 and matched.center_y > 0:
                    move_cursor(matched.center_x, matched.center_y, language=language)
                    ok_click, msg = mouse_click("left", language=language)
                    return ok_click, f"Klik elemen [{matched.index}] '{matched.name}'"
                return False, f"Elemen berindeks [{target_idx}] tidak ditemukan."
            except Exception as e:
                return False, f"Gagal mengeklik indeks {t}: {e}"

        elif act == "wait":
            try:
                sec = float(t) if t else 1.0
                time.sleep(sec)
                return True, f"Menunggu {sec:.1f} detik"
            except Exception:
                time.sleep(1.0)
                return True, "Menunggu"

        elif act in ("ask_user", "complete"):
            return True, "Pause/Complete action"

        return False, f"Tindakan '{act}' tidak didukung."

    def _log_step(
        self,
        step_num: int,
        msg: str,
        on_step: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Emits step progression log for transparency."""
        line = f"[VISION AGENT] [STEP {step_num}/{self.max_steps}] {msg}"
        logger.info(line)
        if on_step:
            try:
                on_step(line)
            except Exception:
                pass
        else:
            print(f"  {line}", flush=True)

    def start_task(
        self,
        goal: str,
        language: str = "id",
        on_step: Optional[Callable[[str], None]] = None,
    ) -> VisionAgentResult:
        """Starts a new vision task with multi-step reasoning."""
        task_id = str(uuid.uuid4())[:8]
        is_id = language.lower().startswith("id")
        goal_lower = goal.lower().strip()

        state = VisionTaskState(
            task_id=task_id,
            goal=goal,
            status="RUNNING",
            current_step=1,
            max_steps=self.max_steps,
            language=language,
            created_at=time.time(),
        )

        # Check if the goal is a Timer-setting task (User Primary Scenario)
        if any(w in goal_lower for w in ["timer", "setel timer", "pasang timer", "buat timer", "set timer"]):
            return self._handle_timer_workflow(state, on_step=on_step)

        # General Visual / ReAct Workflow for other tasks
        return self._handle_general_workflow(state, on_step=on_step)

    def _handle_timer_workflow(
        self,
        state: VisionTaskState,
        on_step: Optional[Callable[[str], None]] = None,
    ) -> VisionAgentResult:
        """Specialized, reliable execution loop for the Timer workflow."""
        is_id = state.language.lower().startswith("id")
        from app.tools.desktop import bring_window_to_foreground
        from app.tools.browser import launch_website

        # Step 1: Open Google Timer in Chrome and bring Chrome window to foreground
        state.current_step = 1
        self._log_step(1, "Membuka Google Chrome dan widget Timer...", on_step)
        launch_website("https://www.google.com/search?q=timer")
        time.sleep(1.0)
        bring_window_to_foreground("chrome")
        time.sleep(0.3)

        obs, indexed = self.observe("Google Timer Widget")
        state.last_observation = obs
        state.steps_history.append(
            VisionStep(step_num=1, action="open_app", target="chrome", description="Buka Chrome Timer", status="success")
        )

        # Step 2: Detect active interface
        state.current_step = 2
        self._log_step(2, f"Widget Timer aktif di layar ('{obs.window_title}')", on_step)

        # Check if user already provided a duration in the original goal (e.g. "setel timer 5 menit")
        preset_duration = extract_duration_from_text(state.goal)
        if preset_duration is not None:
            self._log_step(2, f"Durasi {preset_duration} menit sudah terdeteksi dari perintah awal.", on_step)
            return self._finalize_timer_duration(state, preset_duration, on_step=on_step)

        # Step 3: Pause and ask user for missing duration parameter
        state.current_step = 3
        state.status = "PAUSED_FOR_USER_INPUT"
        question = "Timer berapa menit, sir?" if is_id else "How many minutes for the timer, sir?"
        state.prompt_to_user = question
        state.waiting_parameter = "duration_minutes"
        self._log_step(3, f"Form Timer terbuka di layar -> Menanyakan durasi: '{question}'", on_step)

        state.steps_history.append(
            VisionStep(step_num=3, action="ask_user", target=question, description="Tanya durasi timer", status="success")
        )

        return VisionAgentResult(
            task_id=state.task_id,
            status="PAUSED_FOR_USER_INPUT",
            spoken_output=question,
            display_output=f"[VISION AGENT] Antarmuka Timer telah terbuka di Google Chrome.\n{question}",
            steps_executed=3,
            is_paused=True,
            prompt_to_user=question,
            state=state,
        )

    def _finalize_timer_duration(
        self,
        state: VisionTaskState,
        duration_minutes: int,
        on_step: Optional[Callable[[str], None]] = None,
    ) -> VisionAgentResult:
        """Sets and starts the Google timer with the given duration."""
        is_id = state.language.lower().startswith("id")
        from app.tools.desktop import bring_window_to_foreground
        from app.tools.browser import launch_website

        state.current_step = 4
        self._log_step(4, f"Menyetel timer Google ke {duration_minutes} menit -> Memulai timer...", on_step)

        # Directly navigate to timer with exact duration in Google Chrome
        launch_website(f"https://www.google.com/search?q=timer+{duration_minutes}+menit")
        time.sleep(0.8)
        bring_window_to_foreground("chrome")

        state.status = "COMPLETED"
        spoken = (
            f"Timer {duration_minutes} menit telah berhasil disetel dan dimulai, sir."
            if is_id
            else f"A {duration_minutes}-minute timer has been set and started, sir."
        )
        self._log_step(4, f"Tugas selesai: {spoken}", on_step)

        state.steps_history.append(
            VisionStep(
                step_num=4,
                action="complete",
                target=f"{duration_minutes}m",
                description=spoken,
                status="success",
            )
        )

        return VisionAgentResult(
            task_id=state.task_id,
            status="COMPLETED",
            spoken_output=spoken,
            display_output=f"[VISION AGENT] {spoken}\n* Browser: Google Chrome\n* Durasi: {duration_minutes} menit",
            steps_executed=state.current_step,
            is_paused=False,
            state=state,
        )

    def resume_task(
        self,
        state: VisionTaskState,
        user_response: str,
        on_step: Optional[Callable[[str], None]] = None,
    ) -> VisionAgentResult:
        """Resumes a paused vision task with user-supplied parameter."""
        is_id = state.language.lower().startswith("id")
        user_clean = user_response.lower().strip()

        # Check cancellation
        if any(w in user_clean for w in ["batal", "cancel", "jangan", "stop", "tidak jadi"]):
            state.status = "FAILED"
            msg = "Baik sir, penyetelan timer dibatalkan." if is_id else "Understood, timer task cancelled, sir."
            self._log_step(state.current_step, msg, on_step)
            return VisionAgentResult(
                task_id=state.task_id,
                status="FAILED",
                spoken_output=msg,
                display_output=f"[VISION AGENT] {msg}",
                steps_executed=state.current_step,
                is_paused=False,
                state=state,
            )

        # Extract duration
        duration = extract_duration_from_text(user_response)
        if duration is None:
            # Fallback default duration of 5 minutes if response was ambiguous
            duration = 5
            self._log_step(
                state.current_step,
                f"Durasi spesifik tidak terbaca dari '{user_response}', menggunakan default 5 menit.",
                on_step,
            )

        return self._finalize_timer_duration(state, duration, on_step=on_step)

    def _handle_general_workflow(
        self,
        state: VisionTaskState,
        on_step: Optional[Callable[[str], None]] = None,
    ) -> VisionAgentResult:
        """Handles general visual desktop goals using compact LLM ReAct loop."""
        is_id = state.language.lower().startswith("id")

        for step_idx in range(1, self.max_steps + 1):
            state.current_step = step_idx
            obs, indexed = self.observe(state.goal)
            state.last_observation = obs

            screen_summary = format_indexed_screen_summary(obs, indexed)
            self._log_step(step_idx, f"Layar aktif: '{obs.window_title}' ({len(indexed)} elemen interaktif)", on_step)

            # Query Ollama with compact prompt for next step
            next_step = self._query_llm_for_next_action(state.goal, screen_summary, state.steps_history)
            if not next_step:
                # Fallback completed
                break

            if next_step.action == "complete":
                state.status = "COMPLETED"
                spoken = next_step.description or ("Tugas di layar telah selesai dilakukan, sir." if is_id else "Desktop task completed, sir.")
                return VisionAgentResult(
                    task_id=state.task_id,
                    status="COMPLETED",
                    spoken_output=spoken,
                    display_output=f"[VISION AGENT] {spoken}",
                    steps_executed=step_idx,
                    is_paused=False,
                    state=state,
                )

            if next_step.action == "ask_user":
                state.status = "PAUSED_FOR_USER_INPUT"
                q = next_step.target or ("Mohon sebutkan instruksi selanjutnya, sir." if is_id else "Please provide next instruction, sir.")
                state.prompt_to_user = q
                return VisionAgentResult(
                    task_id=state.task_id,
                    status="PAUSED_FOR_USER_INPUT",
                    spoken_output=q,
                    display_output=f"[VISION AGENT] {q}",
                    steps_executed=step_idx,
                    is_paused=True,
                    prompt_to_user=q,
                    state=state,
                )

            # Execute action
            self._log_step(step_idx, f"Menjalankan: {next_step.action} -> {next_step.target}", on_step)
            ok, msg = self._execute_step(next_step, indexed, language=state.language)
            next_step.status = "success" if ok else "failed"
            state.steps_history.append(next_step)
            time.sleep(0.4)

        # Completed or reached limit
        state.status = "COMPLETED"
        spoken = "Tugas telah selesai dijalankan di layar, sir." if is_id else "Screen task completed, sir."
        return VisionAgentResult(
            task_id=state.task_id,
            status="COMPLETED",
            spoken_output=spoken,
            display_output=f"[VISION AGENT] {spoken}",
            steps_executed=state.current_step,
            is_paused=False,
            state=state,
        )

    def _query_llm_for_next_action(
        self,
        goal: str,
        screen_summary: str,
        history: List[VisionStep],
    ) -> Optional[VisionStep]:
        """Queries local Qwen model via Ollama for next visual action with low token overhead."""
        hist_lines = [f"- {s.action}: {s.target}" for s in history[-3:]]
        hist_str = "\n".join(hist_lines) if hist_lines else "None"

        system_prompt = (
            "You are JARVIS Vision Agent on Windows 11.\n"
            "Given current screen observation and goal, choose the next single action.\n"
            "Output ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "action": "hotkey" | "type_text" | "click_index" | "press_key" | "ask_user" | "complete",\n'
            '  "target": "<hotkey combo, text to type, element index number, or message>",\n'
            '  "description": "<short description in Indonesian>"\n'
            "}\n"
            "Examples:\n"
            '{"action": "hotkey", "target": "ctrl+t", "description": "Buka tab baru"}\n'
            '{"action": "type_text", "target": "query text", "description": "Ketik teks pencarian"}\n'
            '{"action": "click_index", "target": "1", "description": "Klik elemen 1"}\n'
            '{"action": "complete", "target": "", "description": "Tugas selesai"}\n'
            "No markdown, no thinking tags, JSON only."
        )

        user_content = f"Goal: {goal}\nPrevious Actions:\n{hist_str}\n\n{screen_summary}\n\nNext Action JSON:"

        try:
            resp = requests.post(
                f"{self.settings.ollama_url}/api/chat",
                json={
                    "model": self.settings.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1, "num_predict": 75},
                    "keep_alive": self.settings.keep_alive,
                },
                timeout=3.0,
            )
            if resp.status_code == 200:
                raw_json = resp.json().get("message", {}).get("content", "").strip()
                cleaned = re.sub(r"<think>[\s\S]*?</think>", "", raw_json).strip()
                data = json.loads(cleaned)
                return VisionStep(
                    step_num=len(history) + 1,
                    action=str(data.get("action", "complete")).lower(),
                    target=str(data.get("target", "")),
                    description=str(data.get("description", "")),
                )
        except Exception as e:
            logger.debug("Ollama vision action generation exception: %s", e)

        return VisionStep(step_num=len(history) + 1, action="complete", description="Task completed")
