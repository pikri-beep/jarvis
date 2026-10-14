"""Script to create a native Windows Desktop shortcut for the JARVIS Minimal GUI.

Target: C:\\Users\\<User>\\Desktop\\JARVIS.lnk
Uses pythonw.exe to ensure zero flashing black CMD console window.
"""

import os
import subprocess
import sys
from pathlib import Path


def create_desktop_shortcut() -> Path:
    """Generates the Windows desktop shortcut using WScript.Shell via PowerShell."""
    project_root = Path(__file__).resolve().parent.parent

    # Detect user desktop
    user_profile = os.environ.get("USERPROFILE", "C:\\Users\\user")
    desktop_dir = Path(user_profile) / "Desktop"
    if not desktop_dir.exists():
        # Fallback to OneDrive Desktop if redirected
        onedrive_desktop = Path(user_profile) / "OneDrive" / "Desktop"
        if onedrive_desktop.exists():
            desktop_dir = onedrive_desktop
        else:
            desktop_dir.mkdir(parents=True, exist_ok=True)

    shortcut_file = desktop_dir / "JARVIS.lnk"

    # Virtual environment pythonw.exe
    pythonw_exe = project_root / ".venv" / "Scripts" / "pythonw.exe"
    if not pythonw_exe.exists():
        # Fallback to current sys.executable or system pythonw
        pythonw_exe = Path(sys.executable).parent / "pythonw.exe"
        if not pythonw_exe.exists():
            pythonw_exe = Path(sys.executable)

    run_script = project_root / "run_gui.pyw"
    icon_path = project_root / "app" / "ui" / "assets" / "jarvis.ico"

    powershell_code = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{str(shortcut_file)}')
$Shortcut.TargetPath = '{str(pythonw_exe)}'
$Shortcut.Arguments = '"{str(run_script)}"'
$Shortcut.WorkingDirectory = '{str(project_root)}'
$Shortcut.IconLocation = '{str(icon_path)}, 0'
$Shortcut.Description = 'JARVIS — Local AI Personal Assistant (Claude Minimal Edition)'
$Shortcut.Save()
"""

    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", powershell_code],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Gagal membuat shortcut desktop: {result.stderr}")

    if not shortcut_file.exists():
        raise FileNotFoundError(f"Shortcut tidak ditemukan setelah eksekusi: {shortcut_file}")

    print(f"[SUCCESS] Shortcut berhasil dibuat di: {shortcut_file}")
    print(f"  Target:     {pythonw_exe}")
    print(f"  Script:     {run_script}")
    print(f"  Icon:       {icon_path}")
    print(f"  WorkingDir: {project_root}")
    return shortcut_file


if __name__ == "__main__":
    try:
        create_desktop_shortcut()
    except Exception as err:
        print(f"[ERROR] {err}", file=sys.stderr)
        sys.exit(1)
