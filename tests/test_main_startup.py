"""Unit tests for JARVIS entry point and startup routines."""

from unittest.mock import MagicMock, patch
from app.core.orchestrator import Orchestrator
from app.main import print_banner


def test_print_banner_runs_cleanly():
    """Verifies print_banner executes without NameError or missing variables."""
    orch = Orchestrator()
    # Test with wake active
    print_banner(orch, wake_active=True, ptt_active=False)
    # Test with ptt active
    print_banner(orch, wake_active=False, ptt_active=True)
    # Test with both inactive
    print_banner(orch, wake_active=False, ptt_active=False)
