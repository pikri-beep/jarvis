"""Configurable application registry and process control tools for Windows 11.

Follows AGENTS.md security guidelines:
- Strictly explicit function calls (no arbitrary shell=True commands).
- Safe path and protocol resolution for known Windows applications.
- Verifies launch success before reporting.
- Reports honestly if an application is missing or cannot be launched.
- Never sends messages or automated commands through communication apps (e.g. WhatsApp).
"""

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.logger import setup_logger

logger = setup_logger("jarvis.tools.apps")


@dataclass
class AppDefinition:
    """Definition for a registered Windows application."""
    canonical_name: str
    display_name: str
    known_exes: List[Path] = field(default_factory=list)
    reg_app_path_names: List[str] = field(default_factory=list)
    protocol_uri: Optional[str] = None
    process_names: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)


class AppRegistry:
    """Registry managing Windows application discovery, aliases, and safe launches."""

    def __init__(self):
        self._apps: Dict[str, AppDefinition] = {}
        self._alias_map: Dict[str, str] = {}
        self._register_default_apps()

    def register(self, app: AppDefinition) -> None:
        """Registers an application definition and indexes all its aliases."""
        self._apps[app.canonical_name] = app
        self._alias_map[app.canonical_name.lower()] = app.canonical_name
        self._alias_map[app.display_name.lower()] = app.canonical_name

        for alias in app.aliases:
            self._alias_map[alias.strip().lower()] = app.canonical_name

    def get(self, name: str) -> Optional[AppDefinition]:
        """Retrieves an application definition by canonical name or alias."""
        canonical = self.resolve_canonical_name(name)
        return self._apps.get(canonical)

    def resolve_canonical_name(self, raw_name: str) -> str:
        """Resolves raw spoken or typed name to canonical identifier."""
        if not raw_name:
            return ""
        cleaned = raw_name.strip().lower()
        return self._alias_map.get(cleaned, cleaned)

    def _register_default_apps(self) -> None:
        """Initializes standard Windows application definitions."""
        # 1. Google Chrome
        self.register(
            AppDefinition(
                canonical_name="chrome",
                display_name="Google Chrome",
                known_exes=[
                    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
                    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
                    Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")),
                ],
                reg_app_path_names=["chrome.exe"],
                process_names=["chrome.exe"],
                aliases=[
                    "chrome", "google chrome", "google crome", "gugel krom",
                    "gugel chrome", "krom", "kromya", "kromer", "chrom", "crome",
                    "kroma", "browser", "peramban", "web browser"
                ],
            )
        )

        # 2. Microsoft Edge
        self.register(
            AppDefinition(
                canonical_name="edge",
                display_name="Microsoft Edge",
                known_exes=[
                    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
                    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
                ],
                reg_app_path_names=["msedge.exe"],
                protocol_uri="microsoft-edge:",
                process_names=["msedge.exe"],
                aliases=[
                    "edge", "ms edge", "microsoft edge", "msedge", "browser edge"
                ],
            )
        )

        # 3. Notepad
        self.register(
            AppDefinition(
                canonical_name="notepad",
                display_name="Notepad",
                known_exes=[
                    Path(r"C:\Windows\System32\notepad.exe"),
                    Path(r"C:\Windows\notepad.exe"),
                ],
                reg_app_path_names=["notepad.exe"],
                process_names=["notepad.exe", "Notepad.exe"],
                aliases=[
                    "notepad", "notpet", "notped", "catatan", "buku catatan",
                    "text editor", "teks editor", "aplikasi catatan"
                ],
            )
        )

        # 4. Calculator
        self.register(
            AppDefinition(
                canonical_name="calculator",
                display_name="Calculator",
                known_exes=[
                    Path(r"C:\Windows\System32\calc.exe"),
                    Path(r"C:\Windows\calc.exe"),
                ],
                reg_app_path_names=["calc.exe"],
                protocol_uri="calculator:",
                process_names=["CalculatorApp.exe", "calc.exe"],
                aliases=[
                    "calculator", "calc", "kalkulator", "kalku", "hitung", "alat hitung"
                ],
            )
        )

        # 5. File Explorer
        self.register(
            AppDefinition(
                canonical_name="explorer",
                display_name="File Explorer",
                known_exes=[
                    Path(r"C:\Windows\explorer.exe"),
                ],
                reg_app_path_names=["explorer.exe"],
                process_names=["explorer.exe"],
                aliases=[
                    "explorer", "file explorer", "eksplorer", "penjelajah file",
                    "berkas", "folder", "penjelajah berkas", "file manager", "manajer berkas"
                ],
            )
        )

        # 6. Windows Settings
        self.register(
            AppDefinition(
                canonical_name="settings",
                display_name="Settings",
                protocol_uri="ms-settings:",
                process_names=["SystemSettings.exe"],
                aliases=[
                    "settings", "setting", "pengaturan", "setelan", "windows settings",
                    "pengaturan windows", "konfigurasi", "opsi"
                ],
            )
        )

        # 7. WhatsApp
        self.register(
            AppDefinition(
                canonical_name="whatsapp",
                display_name="WhatsApp",
                known_exes=[
                    Path(os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe")),
                    Path(os.path.expandvars(r"%PROGRAMFILES%\WhatsApp\WhatsApp.exe")),
                ],
                reg_app_path_names=["WhatsApp.exe"],
                protocol_uri="whatsapp:",
                process_names=["WhatsApp.exe", "WhatsAppDesktop.exe"],
                aliases=[
                    "whatsapp", "whats app", "wa", "watsap", "whatsap", "watsapp", "pesan wa"
                ],
            )
        )

        # 8. Command Prompt
        self.register(
            AppDefinition(
                canonical_name="cmd",
                display_name="Command Prompt",
                known_exes=[
                    Path(r"C:\Windows\System32\cmd.exe"),
                ],
                process_names=["cmd.exe"],
                aliases=["cmd", "command prompt", "prompt perintah"],
            )
        )

        # 9. PowerShell
        self.register(
            AppDefinition(
                canonical_name="powershell",
                display_name="PowerShell",
                known_exes=[
                    Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"),
                ],
                process_names=["powershell.exe"],
                aliases=["powershell", "terminal", "powersel"],
            )
        )

        # 10. Spotify
        self.register(
            AppDefinition(
                canonical_name="spotify",
                display_name="Spotify",
                known_exes=[
                    Path(os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")),
                ],
                reg_app_path_names=["Spotify.exe"],
                protocol_uri="spotify:",
                process_names=["Spotify.exe"],
                aliases=["spotify", "spotifi", "musik"],
            )
        )

        # 11. Visual Studio Code
        self.register(
            AppDefinition(
                canonical_name="vscode",
                display_name="Visual Studio Code",
                known_exes=[
                    Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe")),
                    Path(r"C:\Program Files\Microsoft VS Code\Code.exe"),
                ],
                reg_app_path_names=["Code.exe"],
                process_names=["Code.exe"],
                aliases=[
                    "vscode", "vs code", "visual studio code", "code editor", "koding", "editor kode"
                ],
            )
        )

        # 12. Task Manager
        self.register(
            AppDefinition(
                canonical_name="taskmgr",
                display_name="Task Manager",
                known_exes=[
                    Path(r"C:\Windows\System32\Taskmgr.exe"),
                ],
                process_names=["Taskmgr.exe"],
                aliases=[
                    "task manager", "taskmgr", "manajer tugas", "pengelola tugas", "manajer proses"
                ],
            )
        )

        # 13. Paint
        self.register(
            AppDefinition(
                canonical_name="paint",
                display_name="Paint",
                known_exes=[
                    Path(r"C:\Windows\System32\mspaint.exe"),
                ],
                reg_app_path_names=["mspaint.exe"],
                process_names=["mspaint.exe", "PaintApp.exe"],
                aliases=[
                    "paint", "mspaint", "menggambar", "gambar", "aplikasi gambar"
                ],
            )
        )

        # 14. Windows Terminal
        self.register(
            AppDefinition(
                canonical_name="terminal",
                display_name="Windows Terminal",
                protocol_uri="windows-terminal:",
                known_exes=[
                    Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe")),
                ],
                process_names=["WindowsTerminal.exe", "wt.exe"],
                aliases=[
                    "terminal", "windows terminal", "wt", "konsol"
                ],
            )
        )


# Global registry singleton
registry = AppRegistry()


def normalize_app_name(raw_name: str) -> str:
    """Normalizes spoken app name variants and STT misrecognitions to a canonical name."""
    return registry.resolve_canonical_name(raw_name)


def is_protocol_registered(protocol_scheme: str) -> bool:
    """Checks if a URI protocol is registered in Windows Registry."""
    proto_name = protocol_scheme.rstrip(":")
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, proto_name) as key:
            val, _ = winreg.QueryValueEx(key, "URL Protocol")
            return True
    except (ImportError, OSError, FileNotFoundError):
        return False


def find_application_executable(canonical_name: str) -> Optional[Path]:
    """Finds the absolute executable path for an application."""
    app = registry.get(canonical_name)

    # 1. Check known explicit paths
    if app:
        for p in app.known_exes:
            if p.exists():
                return p

    # 2. Check system PATH via shutil.which
    which_targets = [canonical_name, f"{canonical_name}.exe"]
    if app and app.reg_app_path_names:
        which_targets.extend(app.reg_app_path_names)

    for target in which_targets:
        hit = shutil.which(target)
        if hit and Path(hit).exists():
            return Path(hit)

    # 3. Check Windows Registry App Paths (HKLM and HKCU)
    reg_names = app.reg_app_path_names if app and app.reg_app_path_names else [f"{canonical_name}.exe"]
    try:
        import winreg
        for reg_name in reg_names:
            for root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                try:
                    sub_key = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{reg_name}"
                    with winreg.OpenKey(root, sub_key) as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val and Path(val).exists():
                            return Path(val)
                except (FileNotFoundError, OSError):
                    continue
    except ImportError:
        pass

    return None


def launch_application(raw_name: str) -> Tuple[bool, str, str]:
    """Safely launches an application on Windows without arbitrary shell execution.

    Args:
        raw_name: Spoken or typed application name (e.g. 'Chrome', 'WhatsApp', 'Pengaturan').

    Returns:
        Tuple of (success_bool, display_name, message).
    """
    canonical = normalize_app_name(raw_name)
    if not canonical:
        return False, "", "Nama aplikasi tidak boleh kosong."

    app = registry.get(canonical)
    display_name = app.display_name if app else canonical.capitalize()

    # Step A: Check for executable path first
    exe_path = find_application_executable(canonical)

    if exe_path is not None:
        try:
            # Special Security Guard for WhatsApp: Ensure bare executable execution only (no parameters)
            cmd_args = [str(exe_path)]

            proc = subprocess.Popen(
                cmd_args,
                close_fds=True,
                creationflags=subprocess.DETACHED_PROCESS if hasattr(subprocess, "DETACHED_PROCESS") else 0,
            )

            # Verification: Check that the process spawned
            if proc.pid and proc.poll() is None:
                logger.info("Successfully launched application '%s' (PID %d) at %s", canonical, proc.pid, exe_path)
                return True, display_name, f"Berhasil membuka {display_name}."
            else:
                logger.error("Process for '%s' exited immediately with code %s", canonical, proc.returncode)
                return False, display_name, f"Aplikasi '{display_name}' gagal dimulai."

        except PermissionError as e:
            logger.error("Permission error launching '%s': %s", canonical, e)
            return False, display_name, f"Izin akses ditolak saat membuka {display_name}."
        except Exception as e:
            logger.error("Unexpected error launching '%s': %s", canonical, e)
            return False, display_name, f"Gagal membuka {display_name}: {e}"

    # Step B: If no executable binary, check registered Windows protocol URI
    if app and app.protocol_uri:
        if is_protocol_registered(app.protocol_uri):
            try:
                # Security Guard: Bare protocol URI only; never attach messages, query strings, or contacts
                safe_uri = app.protocol_uri.split("?")[0]
                os.startfile(safe_uri)
                logger.info("Successfully launched application '%s' via protocol '%s'", canonical, safe_uri)
                return True, display_name, f"Berhasil membuka {display_name}."
            except Exception as e:
                logger.error("Error activating protocol '%s' for '%s': %s", app.protocol_uri, canonical, e)
                return False, display_name, f"Gagal membuka {display_name} melalui protokol sistem: {e}"

    # Step C: Honest reporting when application is absent or unsupported
    logger.warning("Application '%s' (raw: '%s') is not installed or registered", canonical, raw_name)
    return False, display_name, f"Aplikasi '{display_name}' tidak ditemukan di sistem."


def close_application(raw_name: str) -> Tuple[bool, str, str]:
    """Gracefully terminates a running application by registered process names."""
    canonical = normalize_app_name(raw_name)
    app = registry.get(canonical)
    display_name = app.display_name if app else canonical.capitalize()

    # Safety Guard: Don't kill Windows File Explorer shell automatically
    if canonical == "explorer":
        return False, display_name, "Menutup File Explorer secara paksa dapat mengganggu antarmuka Windows, sir."

    process_candidates = app.process_names if app and app.process_names else [f"{canonical}.exe"]

    closed_any = False
    for proc_name in process_candidates:
        try:
            result = subprocess.run(
                ["taskkill", "/IM", proc_name],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                logger.info("Successfully closed process '%s' for app '%s'", proc_name, canonical)
                closed_any = True
        except Exception as e:
            logger.error("Error terminating process '%s': %s", proc_name, e)

    if closed_any:
        return True, display_name, f"Berhasil menutup {display_name}."
    else:
        return False, display_name, f"Aplikasi '{display_name}' tidak sedang berjalan."
