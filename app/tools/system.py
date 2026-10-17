"""System diagnostics, status and screenshot tools (Phase 2)."""

from app.tools.windows import (
    format_battery_status,
    format_system_info,
    get_battery_status,
    get_hardware_specs,
    get_system_specs,
    lock_windows,
    lock_workstation,
    take_screenshot,
)

__all__ = [
    "get_system_specs",
    "get_hardware_specs",
    "format_system_info",
    "get_battery_status",
    "format_battery_status",
    "lock_workstation",
    "lock_windows",
    "take_screenshot",
]
