"""Integration test suite for Windows 11 application registry and launcher.

Verifies:
1. Chrome, Edge, Notepad, Calculator, File Explorer, Settings, and WhatsApp discovery.
2. Alias mapping in English and Indonesian.
3. Safe execution mechanisms (binary vs protocol).
4. WhatsApp security guarantees (no messaging / parameters).
5. Honest failure handling when apps are missing.
"""

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
    close_application,
)
from app.core.orchestrator import Orchestrator

def run_integration_tests():
    print("=================================================================")
    print("JARVIS Phase 3.7 - Application Integration & Verification Suite")
    print("=================================================================\n")

    # 1. Verification of all target applications on the system
    target_apps = [
        ("chrome", "Google Chrome"),
        ("edge", "Microsoft Edge"),
        ("notepad", "Notepad"),
        ("calculator", "Calculator"),
        ("explorer", "File Explorer"),
        ("settings", "Settings"),
        ("whatsapp", "WhatsApp"),
    ]

    print("1. Target Applications Verification:")
    print("-" * 65)
    for key, name in target_apps:
        app_def = registry.get(key)
        assert app_def is not None, f"Definition missing for {key}"
        exe_path = find_application_executable(key)
        proto = app_def.protocol_uri
        proto_ok = is_protocol_registered(proto) if proto else False
        
        launch_type = "Binary Executable" if exe_path else ("Protocol URI" if proto_ok else "NOT FOUND")
        location = str(exe_path) if exe_path else (proto if proto_ok else "N/A")
        
        print(f"[{'PASS' if (exe_path or proto_ok) else 'FAIL'}] {name:15s} | Type: {launch_type:18s} | Target: {location}")
        assert exe_path is not None or proto_ok, f"App {name} is neither installed as binary nor registered protocol"

    print("\n2. Alias & Localization Mapping:")
    print("-" * 65)
    aliases_to_test = [
        # English
        ("open Chrome", "chrome"),
        ("open browser", "chrome"),
        ("launch Edge", "edge"),
        ("open Notepad", "notepad"),
        ("start Calculator", "calculator"),
        ("open File Explorer", "explorer"),
        ("open Settings", "settings"),
        ("open WhatsApp", "whatsapp"),
        # Indonesian
        ("buka Chrome", "chrome"),
        ("buka browser", "chrome"),
        ("buka peramban", "chrome"),
        ("buka catatan", "notepad"),
        ("buka kalkulator", "calculator"),
        ("buka berkas", "explorer"),
        ("buka pengaturan", "settings"),
        ("buka setelan", "settings"),
        ("buka wa", "whatsapp"),
        ("buka WhatsApp", "whatsapp"),
        # Whisper STT misrecognitions with conversational verbs
        ("buka kromya", "chrome"),
        ("tolong buka gugel krom", "chrome"),
        ("buka watsap", "whatsapp"),
    ]

    orchestrator = Orchestrator()
    for phrase, expected_canonical in aliases_to_test:
        route = orchestrator.router.route(phrase)
        resolved = route.args.get("target")
        match = resolved == expected_canonical
        print(f"[{'PASS' if match else 'FAIL'}] \"{phrase}\" -> target: '{resolved}' (expected '{expected_canonical}')")
        assert match, f"Routing failed for '{phrase}': got '{resolved}', expected '{expected_canonical}'"

    print("\n3. WhatsApp Security Guarantee:")
    print("-" * 65)
    wa_def = registry.get("whatsapp")
    print(f"  WhatsApp protocol: '{wa_def.protocol_uri}'")
    assert wa_def.protocol_uri == "whatsapp:", "Protocol must strictly be bare 'whatsapp:'"
    assert "?" not in wa_def.protocol_uri, "Security violation: protocol contains query string"
    assert "send" not in wa_def.protocol_uri, "Security violation: protocol contains send command"
    print("  [PASS] Verified: WhatsApp launches without parameters, text, or automated account actions.")

    print("\n4. Honest Failure Handling:")
    print("-" * 65)
    fail_res, name, msg = launch_application("aplikasi_yang_pasti_tidak_ada")
    print(f"  Non-existent app result: success={fail_res}, name='{name}', msg='{msg}'")
    assert fail_res is False
    assert "tidak ditemukan" in msg
    print("  [PASS] Verified: Missing applications are reported honestly without fake success.")

    print("\n=================================================================")
    print("All Phase 3.7 Application Integration Tests PASSED Successfully!")
    print("=================================================================\n")

if __name__ == "__main__":
    run_integration_tests()
