"""Windowless launcher for JARVIS Minimalist Desktop GUI.

Runs with pythonw.exe without opening a black command prompt / terminal window.
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Change current working directory to project root
os.chdir(PROJECT_ROOT)

from app.ui.app import run_gui

if __name__ == "__main__":
    sys.exit(run_gui())
