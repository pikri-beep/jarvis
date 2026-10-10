"""Verify app registry discovery, aliases, and launch methods."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.tools.apps import (
    registry,
    normalize_app_name,
    find_application_executable,
    is_protocol_registered,
    launch_application,
)

def main():
    print("=== Testing App Registry Aliases ===")
    test_aliases = [
        ("chrome", "chrome"),
        ("Google Chrome", "chrome"),
        ("kromya", "chrome"),
        ("browser", "chrome"),
        ("peramban", "chrome"),
        ("edge", "edge"),
        ("Microsoft Edge", "edge"),
        ("notepad", "notepad"),
        ("catatan", "notepad"),
        ("buku catatan", "notepad"),
        ("calculator", "calculator"),
        ("kalkulator", "calculator"),
        ("calc", "calculator"),
        ("explorer", "explorer"),
        ("file explorer", "explorer"),
        ("berkas", "explorer"),
        ("settings", "settings"),
        ("pengaturan", "settings"),
        ("setelan", "settings"),
        ("whatsapp", "whatsapp"),
        ("wa", "whatsapp"),
        ("watsap", "whatsapp"),
    ]

    for raw, expected in test_aliases:
        resolved = normalize_app_name(raw)
        assert resolved == expected, f"Failed for {raw}: got {resolved}, expected {expected}"
        print(f"  [OK] '{raw}' -> '{resolved}'")

    print("\n=== Testing App Discovery on Target System ===")
    target_apps = ["chrome", "edge", "notepad", "calculator", "explorer", "settings", "whatsapp"]
    for app_id in target_apps:
        app_def = registry.get(app_id)
        exe = find_application_executable(app_id)
        has_proto = is_protocol_registered(app_def.protocol_uri) if app_def and app_def.protocol_uri else False
        print(f"  App: {app_def.display_name:15s} | Executable: {str(exe) if exe else 'None':45s} | Protocol: {app_def.protocol_uri or 'None'} (Registered: {has_proto})")
        assert (exe is not None or has_proto), f"App {app_id} neither found as executable nor registered protocol!"

    print("\n=== Testing Honest Failure on Non-existent App ===")
    success, display, msg = launch_application("aplikasi_fiktif_123")
    assert success is False
    assert "tidak ditemukan" in msg
    print(f"  [OK] Non-existent app reported honestly: success={success}, msg='{msg}'")

if __name__ == "__main__":
    main()
