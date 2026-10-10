"""Automated unit and integration tests for Workstream C: Desktop & Mouse Control.

Tests:
1. Cursor centering and coordinate calculations
2. Coordinate bounds clamping and safety
3. Mouse clicks: left, right, double-click
4. Mouse scrolling: up, down, invalid directions
5. Unicode keyboard typing via SendInput
6. Key press handling via SendInput (Enter, Escape, etc.)
7. Shortcut combination sending via SendInput (Ctrl+L, Ctrl+T, etc.)
8. Application focusing via PowerShell AppActivate
"""

from unittest.mock import MagicMock, patch
import pytest

from app.tools.desktop import (
    focus_application,
    get_screen_resolution,
    mouse_click,
    mouse_scroll,
    move_cursor,
    move_cursor_to_center,
    press_single_key,
    send_shortcut,
    type_text,
)


def test_get_screen_resolution():
    """Verifies screen resolution query returns positive width and height."""
    with patch("ctypes.windll.user32.GetSystemMetrics") as mock_metrics:
        mock_metrics.side_effect = lambda code: 1920 if code == 0 else 1080
        w, h = get_screen_resolution()
        assert w == 1920
        assert h == 1080


def test_move_cursor_to_center():
    """Verifies cursor centering computes midpoint and calls SetCursorPos."""
    with patch("ctypes.windll.user32.GetSystemMetrics") as mock_metrics, \
         patch("ctypes.windll.user32.SetCursorPos") as mock_setpos:
        mock_metrics.side_effect = lambda code: 1920 if code == 0 else 1080
        mock_setpos.return_value = 1

        ok, msg = move_cursor_to_center(language="en")
        assert ok is True
        assert "center of screen" in msg
        mock_setpos.assert_called_once_with(960, 540)


def test_move_cursor_clamping():
    """Verifies that coordinates beyond screen limits are clamped safely."""
    with patch("ctypes.windll.user32.GetSystemMetrics") as mock_metrics, \
         patch("ctypes.windll.user32.SetCursorPos") as mock_setpos:
        mock_metrics.side_effect = lambda code: 1000 if code == 0 else 800
        mock_setpos.return_value = 1

        # Coordinates exceeding limits
        ok, msg = move_cursor(2500, -50, language="id")
        assert ok is True
        mock_setpos.assert_called_once_with(999, 0)


def test_mouse_clicks():
    """Verifies left, right, and double-click actions call user32 mouse_event."""
    with patch("ctypes.windll.user32.mouse_event") as mock_event:
        # Left click
        ok_l, msg_l = mouse_click("left", language="id")
        assert ok_l is True
        assert "Klik" in msg_l
        assert mock_event.call_count == 2  # down + up

        # Right click
        mock_event.reset_mock()
        ok_r, msg_r = mouse_click("right", language="en")
        assert ok_r is True
        assert "Right click" in msg_r
        assert mock_event.call_count == 2

        # Double click
        mock_event.reset_mock()
        ok_d, msg_d = mouse_click("double", language="id")
        assert ok_d is True
        assert "Klik" in msg_d
        assert mock_event.call_count == 4


def test_mouse_scroll():
    """Verifies vertical scroll up and down trigger MOUSEEVENTF_WHEEL."""
    with patch("ctypes.windll.user32.mouse_event") as mock_event:
        ok_down, msg_down = mouse_scroll("down", amount=3, language="en")
        assert ok_down is True
        assert "Scrolled down" in msg_down
        # MOUSEEVENTF_WHEEL is 0x0800, dwData is negative for down
        mock_event.assert_called_once()
        args = mock_event.call_args[0]
        assert args[0] == 0x0800
        # dwData: -3 * 120 = -360
        assert args[3] in (-360, ((-360) & 0xFFFFFFFF))

        mock_event.reset_mock()
        ok_up, msg_up = mouse_scroll("up", amount=2, language="id")
        assert ok_up is True
        assert "ke atas" in msg_up
        args_up = mock_event.call_args[0]
        assert args_up[3] == 240


def test_type_text():
    """Verifies text typing uses SendInput with KEYEVENTF_UNICODE."""
    with patch("ctypes.windll.user32.SendInput") as mock_send:
        mock_send.return_value = 22
        ok, msg = type_text("JARVIS 2026", language="en")
        assert ok is True
        assert "Typed" in msg
        mock_send.assert_called_once()
        n_inputs = mock_send.call_args[0][0]
        assert n_inputs == 22  # 11 characters * 2 events each (down + up)


def test_type_empty_text():
    """Verifies typing empty string is safely rejected."""
    ok, msg = type_text("", language="en")
    assert ok is False
    assert "empty" in msg.lower()


def test_press_single_key():
    """Verifies pressing known virtual keys sends proper key codes via SendInput."""
    with patch("ctypes.windll.user32.SendInput") as mock_send:
        mock_send.return_value = 1
        ok, msg = press_single_key("enter", language="id")
        assert ok is True
        assert "Enter" in msg
        # down and up = 2 calls to _send_input
        assert mock_send.call_count == 2

        mock_send.reset_mock()
        ok_esc, msg_esc = press_single_key("escape", language="en")
        assert ok_esc is True
        assert "Escape" in msg_esc
        assert mock_send.call_count == 2


def test_send_shortcut():
    """Verifies sending shortcut combos like Ctrl+L."""
    with patch("ctypes.windll.user32.SendInput") as mock_send:
        mock_send.return_value = 2
        ok, msg = send_shortcut("ctrl+l", language="en")
        assert ok is True
        assert "ctrl+l" in msg.lower()
        # Down array, then up array = 2 calls to _send_input
        assert mock_send.call_count == 2


def test_focus_application():
    """Verifies focus_application uses PowerShell AppActivate."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="True\n", stderr="")
        ok, msg = focus_application("chrome", language="id")
        assert ok is True
        assert "Google Chrome" in msg
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "powershell" in cmd[0]
        assert "AppActivate" in cmd[-1]
