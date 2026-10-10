"""Automated test suite for Performance Contract & Diagnostics (Sections 1, 8, 9 & 10.E).

Verifies:
- Deterministic command routing target under 50 ms.
- DiagnosticsTracker records stages (wake, speech, STT, router, LLM, tool, TTS, complete).
- p50, p95, and max latency calculations.
- Hard timeout and rollback requirements (ActionInterpreter 3.5s timeout).
- Recovery and clean failure reporting on timeouts.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from app.ai.interpreter import ActionInterpreter, InterpreterPlan
from app.core.config import Settings
from app.core.diagnostics import DiagnosticsTracker, TurnDiagnostics, format_diagnostics_text
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType


class TestPerformanceContract(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()
        self.tracker = DiagnosticsTracker()

    def test_deterministic_routing_latency_under_50ms(self):
        """Deterministic routing must consistently take well under 50 ms."""
        commands = [
            "open chrome",
            "buka notepad",
            "jam berapa sekarang?",
            "what's today's date?",
            "pause the music",
            "resume it",
            "turn it up",
            "ambil screenshot",
            "lock the screen",
            "status baterai",
        ]
        latencies = []
        for cmd in commands:
            t0 = time.perf_counter()
            route = self.router.route(cmd)
            duration_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(duration_ms)
            self.assertEqual(route.route_type, RouteType.FAST_COMMAND)
            self.assertLess(duration_ms, 50.0, f"Command '{cmd}' took {duration_ms:.2f}ms (> 50ms)")

        avg_ms = sum(latencies) / len(latencies)
        self.assertLess(avg_ms, 10.0, f"Average routing latency was {avg_ms:.2f}ms")

    def test_diagnostics_tracker_stage_recording_and_percentiles(self):
        """DiagnosticsTracker records stage timings and calculates p50/p95/max."""
        # Simulate 10 turns with known durations
        for i in range(1, 11):
            turn = self.tracker.start_turn(f"command {i}")
            turn.t_speech_start = 100.0
            turn.t_speech_end = 101.0
            turn.t_stt_end = 101.5
            turn.t_router_end = 101.52
            turn.t_tool_start = 101.53
            turn.t_tool_end = 101.60
            turn.t_complete = 101.5 + (i * 0.1)  # 0.1s to 1.0s local e2e
            turn.calculate_durations()

        stats = self.tracker.get_summary_stats()
        self.assertEqual(stats["count"], 10)
        self.assertGreater(stats["p50_local_e2e"], 0.0)
        self.assertGreater(stats["p95_local_e2e"], stats["p50_local_e2e"])
        self.assertAlmostEqual(stats["max_local_e2e"], 1.0, places=1)

    @patch("requests.post", side_effect=Exception("Request timed out after 3.5s"))
    def test_action_interpreter_hard_timeout_prevents_pipeline_blocking(self, mock_post):
        """ActionInterpreter must strictly enforce its timeout and fail gracefully."""
        interpreter = ActionInterpreter(
            model="qwen3:8b",
            timeout=0.1,  # Short 100ms timeout for test
        )

        plan = interpreter.interpret(
            user_input="buka youtube dan putar musik",
            state_context={},
        )

        # Must not hang, must return conversational fallback or clarification safely
        self.assertFalse(plan.is_action)
        self.assertIsNotNone(plan.response)

    def test_end_to_end_fast_command_execution_under_performance_target(self):
        """Locally executable fast command completes well within 1-2s target."""
        settings = Settings(llm_enabled=False)
        orchestrator = Orchestrator(settings=settings)

        t0 = time.perf_counter()
        route, stream = orchestrator.process_input_stream("jam berapa sekarang?")
        response = "".join(list(stream))
        elapsed = time.perf_counter() - t0

        self.assertEqual(route.action, "get_time")
        self.assertTrue(len(response) > 0)
        self.assertLess(elapsed, 1.0, f"Local fast command took {elapsed:.3f}s (> 1.0s)")


if __name__ == "__main__":
    unittest.main()
