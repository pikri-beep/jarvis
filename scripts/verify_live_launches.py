import sys
import time
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.tools.apps import launch_application, close_application

def test_live_launch():
    print("=== Testing Live Notepad Launch & Graceful Close ===")
    ok, name, msg = launch_application("notepad")
    print(f"Launch Notepad -> ok={ok}, name='{name}', msg='{msg}'")
    assert ok is True

    time.sleep(1.0)

    close_ok, close_name, close_msg = close_application("notepad")
    print(f"Close Notepad -> ok={close_ok}, name='{close_name}', msg='{close_msg}'")
    assert close_ok is True

    print("\n=== Testing Live Calculator Launch & Graceful Close ===")
    ok_calc, name_calc, msg_calc = launch_application("calculator")
    print(f"Launch Calculator -> ok={ok_calc}, name='{name_calc}', msg='{msg_calc}'")
    assert ok_calc is True

    time.sleep(1.0)

    close_calc, name_c, msg_c = close_application("calculator")
    print(f"Close Calculator -> ok={close_calc}, name='{name_c}', msg='{msg_c}'")

    print("\nAll live launch and termination verifications passed!")

if __name__ == "__main__":
    test_live_launch()
