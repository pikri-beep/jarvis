"""Manual integration test verifying deterministic website launching and measured latency."""

import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.core.orchestrator import Orchestrator
from app.core.router import RouteType
from app.tools.browser import launch_website, normalize_website_target


def main():
    print("=" * 70)
    print("JARVIS Phase 3.9 — Manual Browser & Website Launcher Verification")
    print("=" * 70)

    # 1. URL resolution check
    websites = ["youtube", "google", "gmail", "chatgpt"]
    for site in websites:
        canonical, display, url = normalize_website_target(site)
        print(f"Target: {site:10s} -> Name: {display:10s} | URL: {url}")

    print("\n" + "-" * 70)
    print("Testing Orchestrator end-to-end fast command routing for 'Buka Youtube':")
    orchestrator = Orchestrator()

    t_start = time.perf_counter()
    route, stream = orchestrator.process_input_stream("Buka Youtube")
    reply = "".join(list(stream))
    total_latency_ms = (time.perf_counter() - t_start) * 1000

    print(f"  Input:         'Buka Youtube'")
    print(f"  Route Type:    {route.route_type.name} (Bypassed LLM: {route.route_type == RouteType.FAST_COMMAND})")
    print(f"  Action:        {route.action}")
    print(f"  Target:        {route.args.get('target')}")
    print(f"  JARVIS Reply:  '{reply}'")
    print(f"  Total Latency: {total_latency_ms:.2f} ms")
    print("-" * 70)

    if route.route_type == RouteType.FAST_COMMAND and route.action == "open_website":
        print("[SUCCESS] 'Buka Youtube' successfully intercepted and launched deterministically!")
    else:
        print("[FAILURE] 'Buka Youtube' was not routed to open_website!")


if __name__ == "__main__":
    main()
