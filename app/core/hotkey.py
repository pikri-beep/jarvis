"""Native Windows Global Hotkey listener for JARVIS.

Registers system-wide hotkeys (Win+Alt+J and Ctrl+Shift+J) without external third-party
keyboard hooks, running safely inside a dedicated QThread message loop.
"""

import ctypes
import sys
from ctypes import byref, c_int, c_uint, c_void_p, Structure
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from app.core.logger import setup_logger

logger = setup_logger("jarvis.core.hotkey")

# Windows API constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001

VK_J = 0x4A


class POINT(Structure):
    _fields_ = [("x", c_int), ("y", c_int)]


class MSG(Structure):
    _fields_ = [
        ("hwnd", c_void_p),
        ("message", c_uint),
        ("wParam", c_void_p),
        ("lParam", c_void_p),
        ("time", c_uint),
        ("pt", POINT),
    ]


class GlobalHotkeyThread(QThread):
    """Background worker thread listening for Windows system-wide hotkeys."""

    hotkey_triggered = pyqtSignal()

    def __init__(self, parent: Optional[object] = None):
        super().__init__(parent)
        self._running = False

    def run(self) -> None:
        if sys.platform != "win32":
            return

        user32 = ctypes.windll.user32
        self._running = True

        # Hotkey 1: Win + Alt + J
        # Hotkey 2: Ctrl + Shift + J (convenient alternative)
        hk1_ok = user32.RegisterHotKey(0, 101, MOD_WIN | MOD_ALT | MOD_NOREPEAT, VK_J)
        hk2_ok = user32.RegisterHotKey(0, 102, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_J)

        if hk1_ok:
            logger.info("Registered global hotkey Win+Alt+J successfully.")
        else:
            logger.warning("Could not register Win+Alt+J (may be reserved by Windows).")

        if hk2_ok:
            logger.info("Registered global hotkey Ctrl+Shift+J successfully.")

        if not hk1_ok and not hk2_ok:
            logger.warning("Failed to register any global hotkeys.")
            return

        msg = MSG()
        while self._running:
            # Peek message with timeout or blocking GetMessage
            if user32.PeekMessageW(byref(msg), 0, 0, 0, PM_REMOVE):
                if msg.message == WM_HOTKEY:
                    logger.debug("Global hotkey triggered (id=%s)", msg.wParam)
                    self.hotkey_triggered.emit()
            else:
                self.msleep(50)

        # Cleanup on thread exit
        user32.UnregisterHotKey(0, 101)
        user32.UnregisterHotKey(0, 102)
        logger.debug("Unregistered global hotkeys.")

    def stop(self) -> None:
        """Stops the hotkey listener thread."""
        self._running = False
