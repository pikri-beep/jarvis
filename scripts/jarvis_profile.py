#!/usr/bin/env python
"""JARVIS Profile Viewer & Manager CLI."""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.memory.memory import memory_manager


def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("reset", "--reset"):
        ans = input("Apakah Anda yakin ingin MENGHAPUS SELURUH ingatan profil? (y/n) > ").strip().lower()
        if ans in ("y", "ya", "yes"):
            memory_manager.clear_all()
            print("Seluruh memori profil telah dibersihkan.")
        else:
            print("Reset dibatalkan.")
        return

    card = memory_manager.format_profile_card(language="id")
    print(card)


if __name__ == "__main__":
    main()
