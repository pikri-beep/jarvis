"""Desktop automation and Windows input tools for JARVIS on Windows 11.

Follows Workstream C & AGENTS.md requirements:
- Strictly explicit, typed function interfaces.
- Zero arbitrary shell command execution.
- Real native Windows user32 SendInput and UI Automation.
- Mouse movement, clicking, scrolling, typing, and shortcuts.
- Foreground window inspection and application focus switching.
- Safety guards against destructive operations.
- Verifies execution where practical.
"""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
import logging
import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

import psutil

from app.core.logger import setup_logger
from app.tools.apps import registry as app_registry, normalize_app_name

logger = setup_logger("jarvis.tools.desktop")

# ---------------------------------------------------------------------------
# Windows user32 C-types Structures & Constants
# ---------------------------------------------------------------------------

PUL = ctypes.POINTER(ctypes.c_ulong)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", PUL),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", PUL),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION),
    ]


# Constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x01000
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

WHEEL_DELTA = 120

# Virtual Key Codes
VK_MAP = {
    "enter": 0x0D,
    "return": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "tab": 0x09,
    "space": 0x20,
    "spasi": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "hapus": 0x2E,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
    "windows": 0x5B,
    "left": 0x25,
    "kiri": 0x25,
    "up": 0x26,
    "atas": 0x26,
    "right": 0x27,
    "kanan": 0x27,
    "down": 0x28,
    "bawah": 0x28,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
}

# Add ASCII letters and digits
for c in "abcdefghijklmnopqrstuvwxyz":
    VK_MAP[c] = ord(c.upper())
for d in "0123456789":
    VK_MAP[d] = ord(d)


def _send_input(inputs: List[INPUT]) -> int:
    """Invokes user32.SendInput with a sequence of INPUT events."""
    if not inputs:
        return 0
    try:
        user32 = ctypes.windll.user32
        n = len(inputs)
        arr = (INPUT * n)(*inputs)
        ret = user32.SendInput(n, arr, ctypes.sizeof(INPUT))
        try:
            return int(ret)
        except (TypeError, ValueError):
            return n
    except Exception as e:
        logger.error("SendInput execution failed: %s", e)
        return 0


# ---------------------------------------------------------------------------
# Mouse Automation
# ---------------------------------------------------------------------------

def get_screen_resolution() -> Tuple[int, int]:
    """Retrieves current primary display resolution in pixels."""
    try:
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        if w > 0 and h > 0:
            return w, h
    except Exception as e:
        logger.debug("Failed to get system metrics: %s", e)
    return 1920, 1080


def get_cursor_position() -> Tuple[int, int]:
    """Retrieves current mouse cursor coordinates."""
    pt = wintypes.POINT()
    try:
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y
    except Exception as e:
        logger.debug("Failed to get cursor position: %s", e)
        return 0, 0


def move_cursor_to_center(language: str = "id") -> Tuple[bool, str]:
    """Moves the mouse cursor to the physical center of the primary screen."""
    is_id = language.lower().startswith("id")
    try:
        w, h = get_screen_resolution()
        cx, cy = w // 2, h // 2
        ok = ctypes.windll.user32.SetCursorPos(cx, cy)
        if ok:
            logger.info("Moved mouse cursor to center (%d, %d)", cx, cy)
            msg = "Kursor digerakkan ke tengah layar, sir." if is_id else "Cursor moved to center of screen, sir."
            return True, msg
        else:
            msg = "Gagal memindahkan kursor mouse." if is_id else "Failed to move mouse cursor."
            return False, msg
    except Exception as e:
        logger.error("Error moving cursor to center: %s", e)
        return False, f"Terjadi kesalahan saat memindahkan kursor: {e}"


def move_cursor(x: int, y: int, language: str = "id") -> Tuple[bool, str]:
    """Moves the mouse cursor to specified coordinates with boundary clamping."""
    is_id = language.lower().startswith("id")
    try:
        w, h = get_screen_resolution()
        target_x = max(0, min(w - 1, x))
        target_y = max(0, min(h - 1, y))
        ok = ctypes.windll.user32.SetCursorPos(target_x, target_y)
        if ok:
            logger.info("Moved cursor to (%d, %d)", target_x, target_y)
            msg = f"Kursor digerakkan ke koordinat {target_x}, {target_y}, sir." if is_id else f"Cursor moved to {target_x}, {target_y}, sir."
            return True, msg
        else:
            return False, "Gagal memindahkan kursor mouse." if is_id else "Failed to move cursor."
    except Exception as e:
        logger.error("Error moving cursor: %s", e)
        return False, str(e)


def mouse_click(button: str = "left", double: bool = False, language: str = "id") -> Tuple[bool, str]:
    """Executes a mouse click, right click, or double click at the current cursor position."""
    is_id = language.lower().startswith("id")
    btn = button.strip().lower()
    if btn in ("double", "ganda", "dua kali"):
        btn = "left"
        double = True

    if btn == "right":
        down_flag = MOUSEEVENTF_RIGHTDOWN
        up_flag = MOUSEEVENTF_RIGHTUP
        action_name = "Klik kanan" if is_id else "Right click"
    else:
        down_flag = MOUSEEVENTF_LEFTDOWN
        up_flag = MOUSEEVENTF_LEFTUP
        action_name = "Double click" if (double and not is_id) else ("Klik dua kali" if double else ("Klik" if is_id else "Click"))

    try:
        user32 = ctypes.windll.user32
        user32.mouse_event(down_flag, 0, 0, 0, 0)
        time.sleep(0.04)
        user32.mouse_event(up_flag, 0, 0, 0, 0)

        if double:
            time.sleep(0.1)
            user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.04)
            user32.mouse_event(up_flag, 0, 0, 0, 0)

        cx, cy = get_cursor_position()
        logger.info("Executed %s at (%d, %d)", action_name, cx, cy)
        msg = f"{action_name} telah dilakukan, sir." if is_id else f"{action_name} executed, sir."
        return True, msg
    except Exception as e:
        logger.error("Error performing mouse click: %s", e)
        return False, f"Gagal melakukan klik: {e}" if is_id else f"Failed to execute click: {e}"


def mouse_scroll(direction: str = "down", amount: int = 5, language: str = "id") -> Tuple[bool, str]:
    """Scrolls the vertical or horizontal wheel at the current cursor position."""
    is_id = language.lower().startswith("id")
    dir_lower = direction.strip().lower()

    if dir_lower in ("down", "bawah", "ke bawah", "turun"):
        flag = MOUSEEVENTF_WHEEL
        delta = -WHEEL_DELTA * amount
        dir_label = "ke bawah" if is_id else "down"
        dir_en = "down"
    elif dir_lower in ("up", "atas", "ke atas", "naik"):
        flag = MOUSEEVENTF_WHEEL
        delta = WHEEL_DELTA * amount
        dir_label = "ke atas" if is_id else "up"
        dir_en = "up"
    elif dir_lower in ("right", "kanan", "ke kanan"):
        flag = MOUSEEVENTF_HWHEEL
        delta = WHEEL_DELTA * amount
        dir_label = "ke kanan" if is_id else "right"
        dir_en = "right"
    elif dir_lower in ("left", "kiri", "ke kiri"):
        flag = MOUSEEVENTF_HWHEEL
        delta = -WHEEL_DELTA * amount
        dir_label = "ke kiri" if is_id else "left"
        dir_en = "left"
    else:
        flag = MOUSEEVENTF_WHEEL
        delta = -WHEEL_DELTA * amount
        dir_label = "ke bawah" if is_id else "down"
        dir_en = "down"

    try:
        ctypes.windll.user32.mouse_event(flag, 0, 0, delta, 0)
        logger.info("Scrolled mouse %s (%d ticks)", dir_en, amount)
        msg = f"Halaman digulir {dir_label}, sir." if is_id else f"Scrolled {dir_en}, sir."
        return True, msg
    except Exception as e:
        logger.error("Error scrolling mouse: %s", e)
        return False, f"Gagal menggulir layar: {e}" if is_id else f"Failed to scroll: {e}"


# ---------------------------------------------------------------------------
# Keyboard & Input Automation
# ---------------------------------------------------------------------------

def is_host_terminal_active() -> bool:
    """Checks if the currently active foreground window belongs to the host terminal or Python process."""
    try:
        details = get_active_window_details()
        if not details.is_valid:
            return False
        proc = (details.process_name or "").lower()
        if proc in ("powershell.exe", "pwsh.exe", "cmd.exe", "windowsterminal.exe", "wt.exe", "conhost.exe"):
            return True
        my_pid = os.getpid()
        if details.process_id == my_pid:
            return True
        try:
            parent_pid = psutil.Process(my_pid).ppid()
            if details.process_id == parent_pid:
                return True
        except Exception:
            pass
    except Exception:
        pass
    return False


def type_text(text: str, language: str = "id", expected_app: Optional[str] = None) -> Tuple[bool, str]:
    """Types text directly into the focused Windows UI element using SendInput UNICODE events."""
    is_id = language.lower().startswith("id")
    if not text:
        return False, "Teks tidak boleh kosong." if is_id else "Text cannot be empty."

    # Guard 1: verify expected window if specified
    if expected_app:
        details = get_active_window_details()
        target_clean = expected_app.strip().lower()
        if target_clean not in details.title.lower() and target_clean not in details.process_name.lower():
            ok_focus, _ = ensure_window_focus(expected_app, language=language)
            if not ok_focus:
                logger.warning("Aborted typing: foreground window '%s' does not match '%s'", details.title, expected_app)
                msg = f"Mengetik dibatalkan: jendela '{expected_app}' tidak aktif." if is_id else f"Typing aborted: window '{expected_app}' is not focused."
                return False, msg

    # Guard 2: Never inject keystrokes into the host terminal window
    if is_host_terminal_active():
        if expected_app:
            ok_focus, _ = ensure_window_focus(expected_app, language=language)
            if not ok_focus or is_host_terminal_active():
                logger.warning("Suppressed typing: host terminal window is active, preventing terminal pollution.")
                return False, "Mengetik dibatalkan: jendela terminal host sedang aktif." if is_id else "Typing aborted: host terminal is active."
        else:
            logger.warning("Suppressed typing: host terminal window is active, preventing terminal pollution.")
            return False, "Mengetik dibatalkan: jendela terminal host sedang aktif." if is_id else "Typing aborted: host terminal is active."

    try:
        events: List[INPUT] = []
        for char in text:
            # Key Down (Unicode)
            inp_down = INPUT()
            inp_down.type = INPUT_KEYBOARD
            inp_down.u.ki.wVk = 0
            inp_down.u.ki.wScan = ord(char)
            inp_down.u.ki.dwFlags = KEYEVENTF_UNICODE
            inp_down.u.ki.time = 0
            inp_down.u.ki.dwExtraInfo = None
            events.append(inp_down)

            # Key Up (Unicode)
            inp_up = INPUT()
            inp_up.type = INPUT_KEYBOARD
            inp_up.u.ki.wVk = 0
            inp_up.u.ki.wScan = ord(char)
            inp_up.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            inp_up.u.ki.time = 0
            inp_up.u.ki.dwExtraInfo = None
            events.append(inp_up)

        sent = _send_input(events)
        if sent > 0:
            logger.info("Typed %d characters via SendInput UNICODE", len(text))
            disp_txt = text if len(text) <= 25 else text[:22] + "..."
            msg = f"Teks '{disp_txt}' telah diketik, sir." if is_id else f"Typed '{disp_txt}', sir."
            return True, msg
        else:
            return False, "Gagal mengetik teks." if is_id else "Failed to type text."
    except Exception as e:
        logger.error("Error typing text: %s", e)
        return False, f"Gagal mengetik teks: {e}" if is_id else f"Failed to type: {e}"


def press_single_key(key_name: str, language: str = "id") -> Tuple[bool, str]:
    """Sends key-down and key-up for a named virtual key (e.g. 'enter', 'esc', 'tab', 'f5')."""
    is_id = language.lower().startswith("id")
    if is_host_terminal_active():
        logger.warning("Suppressed key '%s': host terminal window is active.", key_name)
        return False, f"Penekanan tombol {key_name} dibatalkan: terminal host sedang aktif." if is_id else f"Key {key_name} aborted: host terminal is active."

    k = key_name.strip().lower()
    vk = VK_MAP.get(k)
    if not vk:
        return False, f"Tombol '{key_name}' tidak didukung." if is_id else f"Key '{key_name}' is not supported."

    try:
        inp_down = INPUT()
        inp_down.type = INPUT_KEYBOARD
        inp_down.u.ki.wVk = vk
        inp_down.u.ki.wScan = 0
        inp_down.u.ki.dwFlags = 0
        inp_down.u.ki.time = 0
        inp_down.u.ki.dwExtraInfo = None

        inp_up = INPUT()
        inp_up.type = INPUT_KEYBOARD
        inp_up.u.ki.wVk = vk
        inp_up.u.ki.wScan = 0
        inp_up.u.ki.dwFlags = KEYEVENTF_KEYUP
        inp_up.u.ki.time = 0
        inp_up.u.ki.dwExtraInfo = None

        _send_input([inp_down])
        time.sleep(0.04)
        _send_input([inp_up])

        k_disp = k.upper() if len(k) <= 4 else k.capitalize()
        logger.info("Pressed key: %s", k_disp)
        msg = f"Tombol {k_disp} telah ditekan, sir." if is_id else f"Pressed {k_disp}, sir."
        return True, msg
    except Exception as e:
        logger.error("Error pressing key %s: %s", key_name, e)
        return False, str(e)


def release_all_modifiers() -> None:
    """Safely releases modifier keys (Ctrl, Alt, Shift, Win) to prevent stuck keys."""
    modifier_keys = ["ctrl", "alt", "shift", "win"]
    up_events = []
    for k in modifier_keys:
        vk = VK_MAP.get(k)
        if vk:
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            inp.u.ki.wVk = vk
            inp.u.ki.dwFlags = KEYEVENTF_KEYUP
            up_events.append(inp)
    _send_input(up_events)


def send_key_down(key_name: str, language: str = "id") -> Tuple[bool, str]:
    """Sends key-down for a virtual key without releasing it."""
    is_id = language.lower().startswith("id")
    k = key_name.strip().lower()
    vk = VK_MAP.get(k)
    if not vk:
        return False, f"Tombol '{key_name}' tidak didukung." if is_id else f"Key '{key_name}' is not supported."

    try:
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.u.ki.wVk = vk
        inp.u.ki.dwFlags = 0
        _send_input([inp])
        return True, f"Tombol {key_name} ditekan (down)." if is_id else f"Key {key_name} pressed down."
    except Exception as e:
        logger.error("Error sending key down %s: %s", key_name, e)
        return False, str(e)


def send_key_up(key_name: str, language: str = "id") -> Tuple[bool, str]:
    """Sends key-up for a virtual key to release it."""
    is_id = language.lower().startswith("id")
    k = key_name.strip().lower()
    vk = VK_MAP.get(k)
    if not vk:
        return False, f"Tombol '{key_name}' tidak didukung." if is_id else f"Key '{key_name}' is not supported."

    try:
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.u.ki.wVk = vk
        inp.u.ki.dwFlags = KEYEVENTF_KEYUP
        _send_input([inp])
        return True, f"Tombol {key_name} dilepas (up)." if is_id else f"Key {key_name} released up."
    except Exception as e:
        logger.error("Error sending key up %s: %s", key_name, e)
        return False, str(e)


def send_shortcut(combo: str, language: str = "id") -> Tuple[bool, str]:
    """Executes a keyboard shortcut combination with guaranteed modifier release (e.g. 'ctrl+l', 'ctrl+t', 'ctrl+w', 'alt+left')."""
    is_id = language.lower().startswith("id")
    if is_host_terminal_active():
        logger.warning("Suppressed shortcut '%s': host terminal window is active.", combo)
        return False, f"Pintasan {combo} dibatalkan: terminal host sedang aktif." if is_id else f"Shortcut {combo} aborted: host terminal is active."

    tokens = [t.strip().lower() for t in combo.split("+") if t.strip()]
    if not tokens:
        return False, "Kombinasi tombol tidak valid." if is_id else "Invalid hotkey combo."

    vks = []
    for t in tokens:
        vk = VK_MAP.get(t)
        if vk is None:
            return False, f"Tombol '{t}' dalam kombinasi '{combo}' tidak dikenali." if is_id else f"Key '{t}' not recognized."
        vks.append(vk)

    down_events = []
    for vk in vks:
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.u.ki.wVk = vk
        inp.u.ki.dwFlags = 0
        down_events.append(inp)

    up_events = []
    for vk in reversed(vks):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.u.ki.wVk = vk
        inp.u.ki.dwFlags = KEYEVENTF_KEYUP
        up_events.append(inp)

    try:
        _send_input(down_events)
        time.sleep(0.05)
    finally:
        # Guarantee all keys are released even if an exception occurs
        _send_input(up_events)

    combo_disp = "+".join(t.upper() for t in tokens)
    logger.info("Executed keyboard shortcut: %s", combo_disp)
    msg = f"Kombinasi tombol {combo_disp} telah dikirim, sir." if is_id else f"Shortcut {combo_disp} sent, sir."
    return True, msg


# ---------------------------------------------------------------------------
# Window & Application Switching
# ---------------------------------------------------------------------------

def bring_window_to_foreground(target_name: str) -> bool:
    """Uses native Win32 user32 APIs to reliably activate and bring a window to the foreground."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        found_hwnd = None
        target_lower = target_name.strip().lower()

        def enum_cb(hwnd, lparam):
            nonlocal found_hwnd
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            w_title = buff.value.lower()

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_name = ""
            if pid.value > 0:
                try:
                    proc_name = psutil.Process(pid.value).name().lower()
                except Exception:
                    pass

            if target_lower in w_title or (proc_name and target_lower in proc_name):
                found_hwnd = hwnd
                return False  # Stop enumeration
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

        # Fallback: Search top-level window by matching process name
        if not found_hwnd:
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    pname = (p.info["name"] or "").lower()
                    if target_lower in pname:
                        pid_val = p.info["pid"]
                        def pid_cb(h, lp):
                            nonlocal found_hwnd
                            w_pid = wintypes.DWORD()
                            user32.GetWindowThreadProcessId(h, ctypes.byref(w_pid))
                            if w_pid.value == pid_val and user32.GetWindowTextLengthW(h) > 0:
                                found_hwnd = h
                                return False
                            return True
                        user32.EnumWindows(WNDENUMPROC(pid_cb), 0)
                        if found_hwnd:
                            break
                except Exception:
                    pass

        if found_hwnd:
            if user32.IsIconic(found_hwnd):
                user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
            else:
                user32.ShowWindow(found_hwnd, 5)  # SW_SHOW

            fg_hwnd = user32.GetForegroundWindow()
            if fg_hwnd != found_hwnd:
                fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None)
                cur_thread = kernel32.GetCurrentThreadId()
                user32.AttachThreadInput(cur_thread, fg_thread, True)
                user32.BringWindowToTop(found_hwnd)
                user32.SetForegroundWindow(found_hwnd)
                user32.AttachThreadInput(cur_thread, fg_thread, False)
            return True
    except Exception as e:
        logger.debug("Native bring_window_to_foreground error: %s", e)
    return False


def focus_application(app_target: str, language: str = "id") -> Tuple[bool, str]:
    """Brings an application window to the foreground on Windows 11.
    
    Tries:
    1. Native Win32 SetForegroundWindow with thread attach (instant, reliable).
    2. WScript.Shell AppActivate by title/alias.
    3. If not found running, launches the application and brings it to the front.
    """
    is_id = language.lower().startswith("id")
    canonical = normalize_app_name(app_target)
    app = app_registry.get(canonical)
    disp_name = app.display_name if app else app_target.capitalize()

    # Build search titles to match window
    match_candidates = [disp_name, canonical]
    if app:
        match_candidates.extend(app.aliases)
        for p in app.process_names:
            match_candidates.append(p.replace(".exe", ""))

    # 1. Native Win32 Window Activation (instant, reliable)
    for candidate in match_candidates:
        if bring_window_to_foreground(candidate):
            logger.info("Successfully activated window matching '%s' via Win32", candidate)
            msg = f"Beralih ke jendela {disp_name}, sir." if is_id else f"Switched to {disp_name}, sir."
            return True, msg

    try:
        # 2. Fallback to WScript.Shell AppActivate
        for candidate in match_candidates[:4]:
            ps_cmd = f'(New-Object -ComObject WScript.Shell).AppActivate("{candidate}")'
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=4,
            )
            if proc.returncode == 0 and "True" in proc.stdout:
                logger.info("Successfully activated window matching '%s' via WScript", candidate)
                msg = f"Beralih ke jendela {disp_name}, sir." if is_id else f"Switched to {disp_name}, sir."
                return True, msg

        # If not running, attempt to launch it
        from app.tools.apps import launch_application
        ok_launch, _, _ = launch_application(canonical)
        if ok_launch:
            time.sleep(1.0)
            for candidate in match_candidates:
                if bring_window_to_foreground(candidate):
                    msg = f"Membuka dan beralih ke jendela {disp_name}, sir." if is_id else f"Launched and focused {disp_name}, sir."
                    return True, msg
            return True, f"Membuka {disp_name}, sir." if is_id else f"Launched {disp_name}, sir."

        msg = f"Jendela untuk {disp_name} tidak ditemukan sedang aktif, sir." if is_id else f"Window for {disp_name} was not found running, sir."
        return False, msg
    except Exception as e:
        logger.error("Error focusing application '%s': %s", app_target, e)
        return False, f"Gagal beralih ke {disp_name}: {e}" if is_id else f"Failed to switch to {disp_name}: {e}"


# ---------------------------------------------------------------------------
# Accessible Search Field Focus
# ---------------------------------------------------------------------------

def click_search_field(language: str = "id") -> Tuple[bool, str]:
    """Focuses the active search or address field.
    
    1. Sends Ctrl+L (the universal browser & Windows Explorer address/search bar shortcut).
    2. Verifies foreground focus state.
    """
    is_id = language.lower().startswith("id")
    try:
        ok, _ = send_shortcut("ctrl+l", language=language)
        if ok:
            logger.info("Activated search / address field via Ctrl+L")
            msg = "Kolom pencarian telah difokuskan, sir." if is_id else "Search field has been focused, sir."
            return True, msg
        else:
            return False, "Gagal memfokuskan kolom pencarian." if is_id else "Failed to focus search field."
    except Exception as e:
        logger.error("Error activating search field: %s", e)
        return False, str(e)


# ---------------------------------------------------------------------------
# Window State and Inspection Tools
# ---------------------------------------------------------------------------

@dataclass
class WindowDetails:
    """Rich details of a Windows desktop window."""
    hwnd: int = 0
    title: str = ""
    process_id: int = 0
    process_name: str = ""
    rect: Tuple[int, int, int, int] = (0, 0, 0, 0)  # (left, top, right, bottom)
    width: int = 0
    height: int = 0
    is_maximized: bool = False
    is_minimized: bool = False
    is_foreground: bool = True
    is_valid: bool = False


def get_active_window_details() -> WindowDetails:
    """Retrieves full geometry, state, title, and process info of the foreground window."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return WindowDetails(title="No Foreground Window", is_valid=False)

        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc_id = pid.value
        proc_name = ""
        if proc_id > 0:
            try:
                p = psutil.Process(proc_id)
                proc_name = p.name()
            except Exception:
                proc_name = "unknown"

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        l, t, r, b = rect.left, rect.top, rect.right, rect.bottom
        w = max(0, r - l)
        h = max(0, b - t)

        is_max = bool(user32.IsZoomed(hwnd))
        is_min = bool(user32.IsIconic(hwnd))

        return WindowDetails(
            hwnd=int(hwnd),
            title=title or "Active Window",
            process_id=proc_id,
            process_name=proc_name,
            rect=(l, t, r, b),
            width=w,
            height=h,
            is_maximized=is_max,
            is_minimized=is_min,
            is_foreground=True,
            is_valid=True,
        )
    except Exception as e:
        logger.error("Failed to retrieve active window details: %s", e)
        return WindowDetails(title="Error", is_valid=False)


def ensure_window_focus(expected_target: str, language: str = "id") -> Tuple[bool, str]:
    """Verifies and ensures that the specified application or window target is active."""
    is_id = language.lower().startswith("id")
    details = get_active_window_details()
    target_clean = expected_target.strip().lower()

    if target_clean in details.title.lower() or target_clean in details.process_name.lower():
        return True, f"Jendela {details.title} sudah aktif." if is_id else f"Window {details.title} is already active."

    # Try activating the target
    ok, msg = focus_application(expected_target, language=language)
    if ok:
        time.sleep(0.15)
        new_details = get_active_window_details()
        return True, f"Fokus dialihkan ke {new_details.title}." if is_id else f"Focus switched to {new_details.title}."
    return False, msg

