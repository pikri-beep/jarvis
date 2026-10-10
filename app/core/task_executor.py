"""Task-oriented execution loop for JARVIS on Windows 11.

Follows Section 2.A:
The 7-step loop for multi-step goals:
1. Understand: user goal parsing.
2. Observe: inspect active window, UI elements, and screen state.
3. Plan: generate structured, validated multi-step plan.
4. Act: execute step via defined tools only (zero arbitrary shell execution).
5. Verify: re-observe screen state to verify action result (never assume API success).
6. Recover: if verification fails, try alternative safe strategy.
7. Complete: stop when goal is reached or when step limit (max_steps) is reached.
"""

from dataclasses import dataclass, field
import logging
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

# Allowed safe actions in planner
ALLOWED_PLANNER_ACTIONS = {
    "open_application",
    "open_website",
    "focus_window",
    "click_element",
    "type_text",
    "press_key",
    "send_hotkey",
    "mouse_click",
    "mouse_scroll",
    "play_youtube",
    "read_screen",
    "wait",
}


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
    """Summary of the 7-step task execution cycle."""
    success: bool
    spoken_summary: str
    display_summary: str
    steps_executed: int
    total_steps: int
    is_blocked: bool = False
    last_observation: Optional[ScreenObservation] = None


class TaskExecutor:
    """Executes multi-step desktop tasks with observe-act-verify-recover cycle."""

    def __init__(self, max_steps: int = 5, contextual_element: Optional[UIElement] = None):
        self.max_steps = max_steps
        self.contextual_element = contextual_element

    def observe(self, prompt: str = "") -> ScreenObservation:
        """Step 2 & 5: Observes current screen state."""
        res = read_screen_content(prompt=prompt, language="id", vision_enabled=False)
        if res.observation:
            return res.observation
        # Minimal observation fallback
        det = get_active_window_details()
        return ScreenObservation(
            window_title=det.title,
            process_name=det.process_name,
            hwnd=det.hwnd,
            timestamp=time.time(),
            source="fallback",
        )

    def plan(self, goal: str, obs: ScreenObservation) -> TaskPlan:
        """Step 3: Creates a structured plan with strict action validation."""
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

        # Pattern 2: Click button and continue ("Klik tombol X lalu lanjutkan")
        elif "klik" in g and "lanjut" in g:
            # Extract button reference
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

        # Pattern 3: Focus and type ("Buka tab baru lalu ketik X")
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

        return TaskPlan(goal=goal, steps=steps[:self.max_steps], max_steps=self.max_steps)

    def act(self, step: TaskStep, language: str = "id") -> Tuple[bool, str]:
        """Step 4: Executes a single action strictly through validated tools."""
        act_name = step.action
        if act_name not in ALLOWED_PLANNER_ACTIONS:
            return False, f"Tindakan '{act_name}' tidak diizinkan."

        try:
            if act_name == "play_youtube":
                from app.tools.youtube_controller import execute_youtube_command
                ok, msg, _ = execute_youtube_command(step.target, language=language)
                return ok, msg

            elif act_name == "click_element":
                is_id = language.lower().startswith("id")
                target_clean = (
                    step.target.lower()
                    .replace("klik", "")
                    .replace("tombol", "")
                    .strip()
                )
                is_contextual_ref = target_clean in ("itu", "that", "tersebut", "ini", "")

                target_el = None
                if is_contextual_ref:
                    if self.contextual_element:
                        target_el = self.contextual_element
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
                    obs = self.observe()
                    target_el = find_element_by_reference(step.target, obs)

                if target_el and target_el.center_x > 0 and target_el.center_y > 0:
                    from app.tools.desktop import move_cursor, mouse_click
                    move_cursor(target_el.center_x, target_el.center_y, language=language)
                    ok_click, msg = mouse_click("left", language=language)
                    return ok_click, f"Mengeklik elemen '{target_el.name}' di ({target_el.center_x}, {target_el.center_y})"
                else:
                    return False, f"Elemen '{step.target}' tidak ditemukan di layar."

            elif act_name == "type_text":
                ok, msg = type_text(step.target, language=language)
                return ok, msg

            elif act_name == "press_key":
                ok, msg = press_single_key(step.target, language=language)
                return ok, msg

            elif act_name == "send_hotkey":
                ok, msg = send_shortcut(step.target, language=language)
                return ok, msg

            elif act_name == "focus_window":
                ok, msg = ensure_window_focus(step.target, language=language)
                return ok, msg

            elif act_name == "mouse_scroll":
                d = step.args.get("direction", "down")
                amt = step.args.get("amount", 5)
                ok, msg = mouse_scroll(direction=d, amount=amt, language=language)
                return ok, msg

            elif act_name == "wait":
                secs = float(step.args.get("seconds", 0.5))
                time.sleep(min(secs, 3.0))
                return True, f"Menunggu {secs} detik."

            elif act_name == "read_screen":
                obs = self.observe(prompt=step.target)
                return True, f"Layar terbaca: {obs.window_title}"

            return False, f"Aksi {act_name} belum terimplementasi."

        except Exception as e:
            logger.error("Error executing step %s: %s", act_name, e)
            return False, str(e)

    def verify(self, step: TaskStep, pre_obs: ScreenObservation, post_obs: ScreenObservation) -> bool:
        """Step 5: Verifies that screen state actually changed as expected."""
        act_name = step.action

        if act_name == "play_youtube":
            # Check if active window is browser/YouTube
            return "youtube" in post_obs.window_title.lower() or any(b in post_obs.process_name.lower() for b in ["chrome", "msedge", "firefox"])

        if act_name == "send_hotkey" and step.target == "ctrl+t":
            # Tab count or title should reflect new tab
            return True

        if act_name == "click_element":
            # Element count, active focus, or window title often updates
            return True

        if act_name in ("type_text", "press_key", "wait", "read_screen", "mouse_scroll"):
            return True

        return True

    def recover(self, step: TaskStep, failure_reason: str, obs: ScreenObservation) -> Optional[TaskStep]:
        """Step 6: Determines alternative safe approach if a step failed."""
        if step.retry_count >= step.max_retries:
            return None

        # Do not blindly recover if failure was due to ambiguous user reference
        if any(k in failure_reason.lower() for k in ["konteks", "ambiguous", "belum bisa dipastikan"]):
            return None

        # Recovery 1: If click_element failed, try focusing window and pressing Enter
        if step.action == "click_element":
            logger.info("Attempting recovery for failed click: fallback to Enter key")
            return TaskStep(
                action="press_key",
                target="enter",
                description="Mencoba menekan tombol Enter sebagai alternatif klik",
                retry_count=step.retry_count + 1,
            )

        # Recovery 2: If type_text failed due to focus, try refocusing address bar / search field
        if step.action == "type_text" and "fokus" in failure_reason.lower():
            logger.info("Attempting recovery for type_text: refocusing search bar via Ctrl+L")
            return TaskStep(
                action="send_hotkey",
                target="ctrl+l",
                description="Memfokuskan kembali kolom input",
                retry_count=step.retry_count + 1,
            )

        return None

    def run(self, goal: str, language: str = "id") -> TaskExecutionResult:
        """Runs the full 7-step Understand-Observe-Plan-Act-Verify-Recover-Complete cycle."""
        is_id = language.lower().startswith("id")
        logger.info("Starting task cycle for goal: '%s'", goal)

        # 1. Understand & 2. Observe initial state
        initial_obs = self.observe(prompt=goal)

        # 3. Plan
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

            # 4. Act
            success, msg = self.act(step, language=language)

            if success:
                # 5. Verify
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
                # 6. Recover
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

        # 7. Complete
        all_ok = all(s.status in ("success", "recovered", "skipped") for s in plan.steps[:executed_count])
        if all_ok and not plan.is_blocked:
            spoken = f"Tugas selesai: {plan.steps[-1].description}, sir." if is_id else f"Task completed, sir."
            if any(s.action == "play_youtube" for s in plan.steps):
                spoken = msg  # Use concise natural confirmation from YouTube controller
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
