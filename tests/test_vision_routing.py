"""Integration tests for vision presence & gesture routing."""

import pytest

from app.core.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.router import CommandRouter, RouteType


def test_vision_command_routing():
    """Router correctly identifies enable, disable, and status voice commands."""
    router = CommandRouter()

    # Enable vision
    r1 = router.route("aktifkan kamera")
    assert r1.route_type == RouteType.FAST_COMMAND
    assert r1.action == "enable_vision"

    r1_alt = router.route("nyalakan pemantau kamera")
    assert r1_alt.action == "enable_vision"

    # Disable vision
    r2 = router.route("matikan kamera")
    assert r2.route_type == RouteType.FAST_COMMAND
    assert r2.action == "disable_vision"

    r2_alt = router.route("nonaktifkan pemantau kamera")
    assert r2_alt.action == "disable_vision"

    # Vision status
    r3 = router.route("status kamera")
    assert r3.route_type == RouteType.FAST_COMMAND
    assert r3.action == "vision_status"

    r3_alt = router.route("cek kamera")
    assert r3_alt.action == "vision_status"


def test_vision_fast_command_execution():
    """Orchestrator executes vision commands with clean bilingual responses."""
    settings = Settings(llm_enabled=False, voice_enabled=False, tts_enabled=False)
    orch = Orchestrator(settings=settings)

    # 1. Disable vision
    r_off, g_off = orch.process_command("matikan kamera")
    out_off = "".join(list(g_off))
    assert r_off.action == "disable_vision"
    assert "dinonaktifkan" in out_off.lower()

    # 2. Check status
    r_stat, g_stat = orch.process_command("status kamera")
    out_stat = "".join(list(g_stat))
    assert r_stat.action == "vision_status"
    assert any(w in out_stat.lower() for w in ["disabled", "nonaktif", "kamera", "camera"])
