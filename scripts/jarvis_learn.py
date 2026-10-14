#!/usr/bin/env python
"""JARVIS Interactive Memory Learner CLI.

Allows the user to interactively teach JARVIS their identity, habits,
app preferences, and custom rules via terminal.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.memory.memory import memory_manager
from app.memory.schemas import MemoryItem


def run_interactive_session():
    """Runs a multi-turn interactive profiling session."""
    hon = memory_manager.get_honorific()
    print("=" * 65)
    print("      JARVIS UNIVERSAL MEMORY INGESTION ENGINE (/learn)      ")
    print("=" * 65)
    print(f"Halo {hon}! Silakan ceritakan apa saja tentang diri Anda:")
    print(" • Identitas (Nama, panggilan 'bos/kak/sir', profesi)")
    print(" • Preferensi Alat (Peramban favorit, code editor, musik)")
    print(" • Kebiasaan & Rutinitas (Jam ngoding, preferensi bahasa)")
    print(" • Aturan Khusus (Prioritas kode, cara menjawab, dll.)")
    print("-" * 65)
    print("Ketik 'selesai' atau 'cukup' untuk memproses dan menyimpan memori.")
    print("Ketik 'batal' untuk keluar tanpa menyimpan.")
    print("=" * 65)

    buffer_lines = []
    while True:
        try:
            line = input("\n[Anda] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSesi dibatalkan.")
            return

        if not line:
            continue

        if line.lower() in ("batal", "exit", "quit", "cancel"):
            print("Sesi belajar dibatalkan.")
            return

        if line.lower() in ("selesai", "cukup", "done", "finish"):
            break

        # Process single-turn /learn directly if user prefixed
        buffer_lines.append(line)
        print("  ✓ Dicatat ke sesi. Tambahkan lagi atau ketik 'selesai'.")

    combined_text = " ".join(buffer_lines).strip()
    if not combined_text:
        print("Tidak ada teks yang dimasukkan. Sesi berakhir.")
        return

    print("\n[JARVIS] Sedang memproses dan menyaring memori...")
    res = memory_manager.learn_from_text(combined_text, auto_confirm=False, language="id")

    if res.learned:
        print(f"\nBerhasil mempelajari {len(res.learned)} item:")
        for item in res.learned:
            print(f"  • [{item.category.upper()}] {item.description or item.key} -> {item.value}")

    if res.conflicts:
        print(f"\nDitemukan {len(res.conflicts)} bentrok dengan memori lama:")
        for conf in res.conflicts:
            ans = input(f"  ? {conf.prompt_question} (y/n) > ").strip().lower()
            if ans in ("y", "ya", "yes"):
                memory_manager.apply_conflict_resolution(conf, approved=True, language="id")
                print("    ✓ Diperbarui.")
            else:
                memory_manager.apply_conflict_resolution(conf, approved=False, language="id")
                print("    ✕ Dipertahankan.")

    print("\n" + "=" * 65)
    print(memory_manager.format_profile_card(language="id"))
    print("=" * 65)
    print("\nSesi selesai! Memori telah aktif tersimpan di SQLite.")


if __name__ == "__main__":
    run_interactive_session()
