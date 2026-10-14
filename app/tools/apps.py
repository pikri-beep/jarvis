"""Configurable application registry and process control tools for Windows 11.

Follows AGENTS.md security guidelines:
- Strictly explicit function calls (no arbitrary shell=True commands).
- Safe path and protocol resolution for known Windows applications.
- Verifies launch success before reporting.
- Reports honestly if an application is missing or cannot be launched.
- Never sends messages or automated commands through communication apps (e.g. WhatsApp).
"""

import difflib
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

    def register_alias(self, alias: str, canonical_name: str) -> bool:
        """Dynamically registers an alias for an existing canonical application."""
        clean_alias = alias.strip().lower()
        clean_canon = canonical_name.strip().lower()
        if not clean_alias or clean_canon not in self._apps:
            return False
        self._alias_map[clean_alias] = clean_canon
        app = self._apps[clean_canon]
        if clean_alias not in [a.lower() for a in app.aliases]:
            app.aliases.append(clean_alias)
        logger.info("Registered dynamic application alias '%s' -> '%s'", clean_alias, clean_canon)
        return True

    def find_fuzzy_matches(self, query: str, cutoff: float = 0.55) -> List[Tuple[str, str, float]]:
        """Finds closest registered application candidates based on string similarity.

        Returns:
            List of (canonical_name, display_name, score) sorted by score descending.
        """
        if not query:
            return []
        q = query.strip().lower()
        best_per_app: Dict[str, Tuple[str, float]] = {}

        for canonical, app in self._apps.items():
            candidates = [canonical, app.display_name.lower()] + [a.lower() for a in app.aliases]
            max_s = 0.0
            for cand in candidates:
                cand_lower = cand.strip().lower()
                is_sub = False
                if len(cand_lower) >= 4 and cand_lower in q:
                    is_sub = True
                elif len(q) >= 4 and q in cand_lower:
                    is_sub = True
                elif cand_lower in q.split() or q in cand_lower.split():
                    is_sub = True

                if is_sub:
                    sub_ratio = len(min(q, cand_lower, key=len)) / max(len(q), len(cand_lower), 1)
                    s = max(difflib.SequenceMatcher(None, q, cand_lower).ratio(), 0.6 + 0.35 * sub_ratio)
                else:
                    s = difflib.SequenceMatcher(None, q, cand_lower).ratio()
                if s > max_s:
                    max_s = s
            if max_s >= cutoff:
                best_per_app[canonical] = (app.display_name, max_s)

        results = [(can, name, score) for can, (name, score) in best_per_app.items()]
        results.sort(key=lambda x: x[2], reverse=True)
        return results

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

        # 15. Discord
        discord_exes = []
        try:
            import glob
            for d_p in glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-*\Discord.exe")):
                discord_exes.append(Path(d_p))
        except Exception:
            pass
        discord_exes.append(Path(os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe")))

        self.register(
            AppDefinition(
                canonical_name="discord",
                display_name="Discord",
                protocol_uri="discord:",
                known_exes=discord_exes,
                process_names=["Discord.exe"],
                aliases=[
                    "discord", "diskord", "aplikasi discord", "chat discord"
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
    # Dynamic check for Discord versioned path
    if canonical_name == "discord":
        try:
            import glob
            for d_p in glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-*\Discord.exe")):
                if Path(d_p).exists():
                    return Path(d_p)
        except Exception:
            pass

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

    # 4. Check Windows Start Menu shortcuts
    lnk_match = scan_start_menu_apps(canonical_name)
    if lnk_match:
        return lnk_match[1]

    return None


def scan_start_menu_apps(query: str) -> Optional[Tuple[str, Path]]:
    """Scans Windows Start Menu shortcut (.lnk) files for non-registered applications.

    Returns:
        Tuple of (display_name, shortcut_or_exe_path) if found, else None.
    """
    if not query or len(query) < 2:
        return None
    q = query.strip().lower()

    search_roots = [
        Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")),
        Path(os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs")),
    ]

    best_match: Optional[Tuple[str, Path, float]] = None

    for root in search_roots:
        if not root.exists():
            continue
        try:
            for item in root.rglob("*.lnk"):
                stem = item.stem.lower()
                # Exclude uninstallers, help docs, and web links
                if any(bad in stem for bad in ["uninstall", "remove", "help", "readme", "bantuan", "setup"]):
                    continue
                score = difflib.SequenceMatcher(None, q, stem).ratio()
                if q in stem or stem in q:
                    sub_ratio = len(min(q, stem, key=len)) / max(len(q), len(stem), 1)
                    score = max(score, 0.6 + 0.35 * sub_ratio)
                if score >= 0.65:
                    if best_match is None or score > best_match[2]:
                        best_match = (item.stem, item, score)
        except Exception as exc:
            logger.debug("Error scanning Start Menu path %s: %s", root, exc)

    if best_match:
        return best_match[0], best_match[1]
    return None


def find_best_app_or_site_candidate(query: str, cutoff: float = 0.55) -> Optional[Tuple[str, str, str, float]]:
    """Finds the closest application or website candidate for a spoken/typed query.

    Returns:
        Tuple of (target_type, canonical_name, display_name, score) where target_type is 'app' or 'website',
        or None if no candidate exceeds cutoff.
    """
    if not query:
        return None

    # 1. Check Apps
    app_matches = registry.find_fuzzy_matches(query, cutoff=cutoff)
    best_app = app_matches[0] if app_matches else None

    # 2. Check Websites
    from app.tools.browser import website_registry
    site_matches = website_registry.find_fuzzy_matches(query, cutoff=cutoff)
    best_site = site_matches[0] if site_matches else None

    if not best_app and not best_site:
        return None

    if best_app and not best_site:
        return "app", best_app[0], best_app[1], best_app[2]
    if best_site and not best_app:
        return "website", best_site[0], best_site[1], best_site[2]

    # Both found: pick higher score
    if best_app[2] >= best_site[2]:
        return "app", best_app[0], best_app[1], best_app[2]
    else:
        return "website", best_site[0], best_site[1], best_site[2]


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
            if str(exe_path).lower().endswith(".lnk"):
                os.startfile(str(exe_path))
                logger.info("Successfully launched application shortcut '%s' at %s", canonical, exe_path)
                return True, display_name, f"Berhasil membuka {display_name}."

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

    # Step B.5: Fallback to registered web application if applicable (e.g. Gemini, Claude, ChatGPT, YouTube)
    from app.tools.browser import is_known_website, launch_website
    if is_known_website(canonical) or is_known_website(raw_name):
        logger.info("Application '%s' resolved to web application, launching in browser", canonical)
        ok_w, _, d_name, msg_w = launch_website(canonical or raw_name)
        return ok_w, d_name, msg_w

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
