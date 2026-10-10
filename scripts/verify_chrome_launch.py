"""Manual integration test verifying real Chrome application launch on Windows 11."""

import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.tools.apps import find_application_executable, launch_application, close_application

def main():
    print("=" * 60)
    print(" VERIFYING ACTUAL CHROME APPLICATION LAUNCH")
    print("=" * 60)

    # 1. Path resolution
    exe_path = find_application_executable("chrome")
    print(f"1. Resolved Chrome executable: {exe_path}")
    assert exe_path is not None and exe_path.exists(), "Chrome executable not found!"
    print("   [PASS] Chrome binary verified on disk.")

    # 2. Launch execution
    print("\n2. Executing launch_application('chrome')...")
    success, display_name, msg = launch_application("chrome")
    print(f"   Launch Success: {success}")
    print(f"   Display Name:   {display_name}")
    print(f"   Status Message: {msg}")
    assert success is True, f"Failed to launch Chrome: {msg}"
    print("   [PASS] Chrome successfully spawned.")

    # Give Chrome 1.5 seconds to show window/process
    time.sleep(1.5)

    print("\nChrome application launch integration test PASSED.")
    print("=" * 60)

if __name__ == "__main__":
    main()
