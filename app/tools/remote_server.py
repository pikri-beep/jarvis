"""PocketDesk Remote server management tool for JARVIS.

Handles starting, stopping, and inspecting the local PocketDesk Remote
FastAPI server running at D:\\Project\\remote.
"""

import os
import socket
import subprocess
import time
from typing import Any, Dict, Optional, Tuple

import psutil

from app.core.logger import setup_logger

logger = setup_logger("jarvis.tools.remote_server")

REMOTE_DIR = r"D:\Project\remote"
REMOTE_PORT = 8000


def get_local_ip() -> str:
    """Retrieves primary LAN/Wi-Fi IPv4 address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def is_remote_server_running(port: int = REMOTE_PORT) -> bool:
    """Checks whether the remote server is actively listening on the port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.6)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def get_remote_server_status(port: int = REMOTE_PORT) -> Dict[str, Any]:
    """Returns status dictionary of PocketDesk Remote server."""
    running = is_remote_server_running(port)
    ip = get_local_ip()
    url = f"http://{ip}:{port}/remote" if running else ""
    return {
        "running": running,
        "port": port,
        "local_ip": ip,
        "url": url,
        "path": REMOTE_DIR,
    }


def start_remote_server(port: int = REMOTE_PORT) -> Tuple[bool, str, str]:
    """Starts the PocketDesk Remote server if not already running.

    Returns:
        (success, url, message)
    """
    ip = get_local_ip()
    url = f"http://{ip}:{port}/remote"

    if is_remote_server_running(port):
        logger.info("PocketDesk Remote server is already active on port %d (%s)", port, url)
        return True, url, f"Server PocketDesk Remote sudah aktif di {url}, sir."

    bat_path = os.path.join(REMOTE_DIR, "start_remote.bat")
    py_path = os.path.join(REMOTE_DIR, "main.py")

    try:
        if os.path.exists(bat_path):
            logger.info("Launching PocketDesk Remote via %s", bat_path)
            subprocess.Popen(
                ["cmd.exe", "/c", bat_path],
                cwd=REMOTE_DIR,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        elif os.path.exists(py_path):
            logger.info("Launching PocketDesk Remote via python %s", py_path)
            subprocess.Popen(
                ["python", "main.py"],
                cwd=REMOTE_DIR,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            return False, "", f"Direktori PocketDesk Remote tidak ditemukan di {REMOTE_DIR}."

        # Wait up to 3 seconds for port to open
        t0 = time.time()
        while time.time() - t0 < 3.5:
            if is_remote_server_running(port):
                break
            time.sleep(0.3)

        if is_remote_server_running(port):
            logger.info("PocketDesk Remote server started successfully at %s", url)
            return True, url, f"Server PocketDesk Remote berhasil diaktifkan di {url}, sir."
        else:
            # Launched process may still be initializing dependencies
            return True, url, f"Server PocketDesk Remote sedang dimulai di {url}, sir."

    except Exception as exc:
        logger.error("Failed to start PocketDesk Remote: %s", exc, exc_info=True)
        return False, "", f"Gagal menyalakan server PocketDesk Remote: {exc}"


def stop_remote_server(port: int = REMOTE_PORT) -> Tuple[bool, str]:
    """Terminates the process currently listening on the PocketDesk Remote port."""
    if not is_remote_server_running(port):
        return True, "Server PocketDesk Remote sedang tidak aktif, sir."

    killed = False
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    logger.info("Terminating remote process PID=%d (%s)", conn.pid, proc.name())
                    proc.terminate()
                    killed = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        time.sleep(0.5)
        if not is_remote_server_running(port) or killed:
            return True, "Server PocketDesk Remote telah dinonaktifkan, sir."
        return False, "Tidak dapat menghentikan server PocketDesk Remote (akses ditolak)."
    except Exception as exc:
        logger.error("Failed to stop remote server: %s", exc)
        return False, f"Terjadi kendala saat mematikan remote server: {exc}"
