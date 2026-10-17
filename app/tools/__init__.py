"""System and automation tools package (Phase 2)."""

from app.tools.apps import close_application, find_application_executable, launch_application, normalize_app_name
from app.tools.code_interpreter import execute_powershell, execute_python_code, is_code_dangerous
from app.tools.remote_server import get_remote_server_status, start_remote_server, stop_remote_server

__all__ = [
    "launch_application",
    "close_application",
    "normalize_app_name",
    "find_application_executable",
    "execute_python_code",
    "execute_powershell",
    "is_code_dangerous",
    "start_remote_server",
    "stop_remote_server",
    "get_remote_server_status",
]
