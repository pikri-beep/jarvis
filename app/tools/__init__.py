"""System and automation tools package (Phase 2)."""

from app.tools.apps import close_application, find_application_executable, launch_application, normalize_app_name

__all__ = [
    "launch_application",
    "close_application",
    "normalize_app_name",
    "find_application_executable",
]
