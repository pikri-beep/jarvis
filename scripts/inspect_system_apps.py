"""Inspects installed applications and protocols on the current Windows 11 system."""

import os
import shutil
import winreg
from pathlib import Path

def check_app_paths():
    apps = {
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ],
        "edge": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "notepad": [
            r"C:\Windows\System32\notepad.exe",
            r"C:\Windows\notepad.exe",
        ],
        "calculator": [
            r"C:\Windows\System32\calc.exe",
            r"C:\Windows\calc.exe",
        ],
        "explorer": [
            r"C:\Windows\explorer.exe",
        ],
        "whatsapp": [
            os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\WhatsApp\WhatsApp.exe"),
        ],
    }

    print("=== Direct Path Checks ===")
    for name, paths in apps.items():
        found = [p for p in paths if os.path.exists(p)]
        print(f"{name:12s}: {found if found else 'Not found via direct path'}")

    print("\n=== Protocol / URI Checks ===")
    protocols = ["ms-settings", "calculator", "whatsapp"]
    for proto in protocols:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, proto) as key:
                print(f"Protocol '{proto}:': Registered in HKEY_CLASSES_ROOT")
        except FileNotFoundError:
            print(f"Protocol '{proto}:': Not registered")

    print("\n=== Windows App Packages Check (%LOCALAPPDATA%\\Packages) ===")
    packages_dir = Path(os.path.expandvars(r"%LOCALAPPDATA%\Packages"))
    if packages_dir.exists():
        wa_dirs = list(packages_dir.glob("*WhatsApp*"))
        print(f"WhatsApp packages found: {wa_dirs}")
        calc_dirs = list(packages_dir.glob("*Calculator*"))
        print(f"Calculator packages found: {calc_dirs}")

    print("\n=== Registry App Paths (HKLM and HKCU) ===")
    for app in ["chrome.exe", "msedge.exe", "notepad.exe", "calc.exe", "WhatsApp.exe"]:
        for root, root_name in [(winreg.HKEY_LOCAL_MACHINE, "HKLM"), (winreg.HKEY_CURRENT_USER, "HKCU")]:
            sub_key = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{app}"
            try:
                with winreg.OpenKey(root, sub_key) as k:
                    val, _ = winreg.QueryValueEx(k, "")
                    print(f"{root_name} App Paths -> {app}: {val} (exists: {os.path.exists(val)})")
            except FileNotFoundError:
                pass

if __name__ == "__main__":
    check_app_paths()
