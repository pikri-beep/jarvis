"""Benchmark script for Desktop Assistant Core Rebuild (Workstream I).

Measures:
1. Router latency across bilingual desktop commands (target: < 2ms)
2. Desktop tool latency (mouse move, mouse click, SendInput typing, shortcut)
3. End-to-end turn latency for fast commands without LLM
4. Screen reading latency (WinRT OCR / UI Automation)
"""

import time
from app.core.config import get_settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter
from app.tools.desktop import (
    get_cursor_position,
    get_screen_resolution,
    mouse_click,
    mouse_scroll,
    move_cursor_to_center,
    press_single_key,
    send_shortcut,
    type_text,
)


def run_benchmark():
    router = CommandRouter()
    orch = Orchestrator()

    test_queries = [
        "buka chrome",
        "open notepad",
        "buka youtube",
        "buka tab baru",
        "tutup tab ini",
        "scroll ke bawah",
        "scroll ke atas",
        "klik kanan",
        "double click",
        "gerakkan kursor ke tengah layar",
        "tekan enter",
        "tekan escape",
        "tekan ctrl+l",
        "ketik python tutorial",
        "switch ke Chrome",
        "jam berapa sekarang",
        "tanggal berapa hari ini",
        "ambil screenshot",
        "lihat layar gue",
        "hapus folder documents",
    ]

    print("=" * 68)
    print("       JARVIS DESKTOP ASSISTANT - CORE PERFORMANCE BENCHMARK")
    print("=" * 68)

    # 1. Router Latency Benchmark
    router_times = []
    for q in test_queries:
        t0 = time.perf_counter()
        route = router.route(q)
        t1 = time.perf_counter()
        lat_ms = (t1 - t0) * 1000
        router_times.append(lat_ms)
        print(f" [ROUTER] '{q[:30]:<30}' -> {route.action:<20} ({lat_ms:.3f} ms)")

    avg_router = sum(router_times) / len(router_times)
    p95_router = sorted(router_times)[int(len(router_times) * 0.95)]
    print("-" * 68)
    print(f" Router Latency: Average = {avg_router:.3f} ms | P95 = {p95_router:.3f} ms (Target < 2.0 ms)")
    print("-" * 68)

    # 2. Desktop Native ctypes API Latency
    desktop_timings = {}

    # Screen resolution
    t0 = time.perf_counter()
    w, h = get_screen_resolution()
    desktop_timings["get_screen_res"] = (time.perf_counter() - t0) * 1000

    # Move cursor center
    t0 = time.perf_counter()
    ok, _ = move_cursor_to_center(language="en")
    desktop_timings["move_center"] = (time.perf_counter() - t0) * 1000

    # Mouse scroll
    t0 = time.perf_counter()
    ok, _ = mouse_scroll("down", amount=1, language="en")
    desktop_timings["scroll"] = (time.perf_counter() - t0) * 1000

    # Mouse click
    t0 = time.perf_counter()
    ok, _ = mouse_click("left", language="en")
    desktop_timings["click"] = (time.perf_counter() - t0) * 1000

    # Key press (Escape)
    t0 = time.perf_counter()
    ok, _ = press_single_key("escape", language="en")
    desktop_timings["key_press"] = (time.perf_counter() - t0) * 1000

    # Hotkey (Ctrl+L)
    t0 = time.perf_counter()
    ok, _ = send_shortcut("ctrl+l", language="en")
    desktop_timings["shortcut"] = (time.perf_counter() - t0) * 1000

    print(" Desktop Native user32 ctypes Latencies:")
    for k, v in desktop_timings.items():
        print(f"   - {k:<20}: {v:.2f} ms")
    print("-" * 68)

    # 3. End-to-end Orchestrator turns (Deterministic Zero-LLM)
    e2e_queries = [
        "jam berapa sekarang",
        "tanggal berapa hari ini",
        "scroll ke bawah",
        "tekan enter",
        "buka tab baru",
        "lihat layar gue",
    ]
    print(" End-to-End Orchestrator Turns (Zero-LLM Fast Commands):")
    for q in e2e_queries:
        t0 = time.perf_counter()
        route, stream = orch.process_input_stream(q)
        ans = "".join(list(stream))
        tot_ms = (time.perf_counter() - t0) * 1000
        print(f"   - Turn '{q}' -> [{route.route}] in {tot_ms:.2f} ms | Spoken: '{ans[:40]}...'")

    print("=" * 68)


if __name__ == "__main__":
    run_benchmark()
