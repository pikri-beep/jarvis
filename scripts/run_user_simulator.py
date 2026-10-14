"""CLI Runner for Simulated User Agent E2E Voice Testing.

Usage:
    python scripts/run_user_simulator.py --scenario SC-01
    python scripts/run_user_simulator.py --scenario all
    python scripts/run_user_simulator.py --list
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Auto-switch to project virtual environment if invoked with global Python
_venv_python = _PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
if _venv_python.exists():
    try:
        if Path(sys.executable).resolve() != _venv_python.resolve():
            import subprocess
            sys.exit(subprocess.call([str(_venv_python)] + sys.argv))
    except Exception:
        pass

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

from app.core.config import get_settings
from tests.user_simulator.agent import SimulatedUserAgent
from tests.user_simulator.scenarios import get_all_scenarios, get_scenario


def main():
    parser = argparse.ArgumentParser(
        description="JARVIS Simulated User Agent - Autonomous Voice & System Tester",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--scenario",
        "-s",
        type=str,
        default="SC-01",
        help="Scenario ID to execute (e.g. 'SC-01', 'SC-02', ... or 'all'). Default: SC-01",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List all available simulated user test scenarios.",
    )
    parser.add_argument(
        "--fast",
        "-f",
        action="store_true",
        help="Fast mode: skips inter-turn human pauses for rapid validation.",
    )
    parser.add_argument(
        "--groq-key",
        type=str,
        default=None,
        help="Optional Groq API key for autonomous cognitive persona generation.",
    )

    args = parser.parse_args()

    if args.list:
        print("\n=== AVAILABLE SIMULATED USER SCENARIOS ===")
        for sc in get_all_scenarios():
            print(f"[{sc.id}] {sc.name}")
            print(f"  Description: {sc.description}")
            print(f"  Persona:     {sc.persona.name} ({sc.persona.role})")
            print(f"  Voice:       {sc.preferred_voice}\n")
        return

    # Initialize agent
    print("\nInitializing Simulated User Agent...")
    agent = SimulatedUserAgent(
        groq_api_key=args.groq_key,
        fast_mode=args.fast,
    )

    if args.scenario.lower() == "all":
        scenarios = get_all_scenarios()
        all_passed = True
        for sc in scenarios:
            passed = agent.run_scenario(sc)
            if not passed:
                all_passed = False
        sys.exit(0 if all_passed else 1)
    else:
        sc = get_scenario(args.scenario)
        if not sc:
            print(f"[ERROR] Unknown scenario ID '{args.scenario}'. Use --list to view valid scenarios.")
            sys.exit(1)

        passed = agent.run_scenario(sc)
        sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
