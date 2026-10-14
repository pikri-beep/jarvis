"""Rich Live Terminal Dashboard and Scorecard for Simulated User Agent."""

from typing import Dict, List, Optional
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from tests.user_simulator.scenarios import TestScenario
from tests.user_simulator.verifier import VerificationResult


class TestDashboard:
    """Renders real-time two-way dialogue, telemetry, and final scorecards."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def print_scenario_header(self, scenario: TestScenario, engine_name: str, voice_name: str) -> None:
        """Prints a handsome scenario startup panel."""
        header_text = Text()
        header_text.append(f"SCENARIO: {scenario.id} - {scenario.name}\n", style="bold cyan")
        header_text.append(f"Persona: {scenario.persona.name} ({scenario.persona.role})\n", style="italic white")
        header_text.append(f"Goal: {scenario.persona.goal}\n", style="dim white")
        header_text.append(f"Brain: {engine_name} | Voice: {voice_name}", style="bold yellow")

        panel = Panel(
            header_text,
            title="[bold green]JARVIS - SIMULATED USER VOICE AGENT[/bold green]",
            border_style="bright_blue",
            box=ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def print_turn(
        self,
        turn_number: int,
        user_spoken: str,
        jarvis_reply: str,
        verification: VerificationResult,
    ) -> None:
        """Prints a single conversational turn with live telemetry and checks."""
        table = Table(show_header=False, box=ROUNDED, expand=True, border_style="dim")
        table.add_column("Key", style="bold", width=18)
        table.add_column("Value")

        # Turn Header
        turn_label = f"Turn #{turn_number}"
        table.add_row(turn_label, f"[bold cyan]🎙️ USER:[/bold cyan] \"{user_spoken}\"")

        # JARVIS Spoken Reply
        reply_display = f"\"{jarvis_reply}\"" if jarvis_reply else "[italic red]<No speech returned>[/italic red]"
        table.add_row("", f"[bold green]🤖 JARVIS:[/bold green] {reply_display}")

        # Latency Badges
        latencies = verification.latency_ms
        if latencies:
            lat_text = " | ".join(f"{k.upper()}: {v:.0f}ms" for k, v in latencies.items())
            table.add_row("⏱️ Latency", f"[dim yellow]{lat_text}[/dim yellow]")

        # Verification Checks
        checks_text = []
        for name, passed in verification.checks.items():
            icon = "[bold green]✓ PASS[/bold green]" if passed else "[bold red]✗ FAIL[/bold red]"
            checks_text.append(f"{icon} {name}")

        status_line = "  ".join(checks_text) if checks_text else "No specific checks"
        table.add_row("🔍 Verifications", status_line)

        # Status border color
        box_style = "green" if verification.passed else "red"
        panel = Panel(table, title=f"[bold]{turn_label}[/bold]", border_style=box_style, box=ROUNDED)
        self.console.print(panel)
        self.console.print()

    def print_scorecard(self, scenario: TestScenario, results: List[VerificationResult]) -> bool:
        """Prints the final summary scorecard table and returns whether all turns passed."""
        total_turns = len(results)
        passed_turns = sum(1 for r in results if r.passed)
        all_passed = (passed_turns == total_turns) and (total_turns > 0)

        score_table = Table(
            title=f"SCORECARD - {scenario.id} ({scenario.name})",
            box=ROUNDED,
            header_style="bold magenta",
            expand=True,
        )
        score_table.add_column("Turn", justify="center", width=8)
        score_table.add_column("Spoken Command", style="cyan")
        score_table.add_column("Result", justify="center", width=12)
        score_table.add_column("Key Details", style="dim")

        for r in results:
            result_label = "[bold green]PASSED[/bold green]" if r.passed else "[bold red]FAILED[/bold red]"
            detail_summary = "; ".join(r.details) if r.details else "OK"
            score_table.add_row(f"#{r.turn_number}", r.spoken_command, result_label, detail_summary)

        self.console.print(score_table)

        rate = (passed_turns / total_turns * 100.0) if total_turns > 0 else 0.0
        summary_color = "bold green" if all_passed else "bold red"
        summary_text = (
            f"Result: {passed_turns}/{total_turns} Turns Passed ({rate:.1f}% Reliability)\n"
            f"Overall Status: {'SUCCESSFUL - ALL CRITERIA MET' if all_passed else 'FAILURE - ATTENTION REQUIRED'}"
        )
        summary_panel = Panel(summary_text, style=summary_color, box=ROUNDED)
        self.console.print(summary_panel)
        self.console.print()

        return all_passed
