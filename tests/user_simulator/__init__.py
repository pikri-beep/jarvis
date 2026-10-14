"""Simulated User Agent Package for JARVIS E2E Voice Testing."""

from tests.user_simulator.audio_injector import AudioStreamInjector
from tests.user_simulator.persona_engine import GroqUserPersonaEngine, PersonaConfig
from tests.user_simulator.scenarios import get_all_scenarios, get_scenario
from tests.user_simulator.verifier import SystemStateVerifier, VerificationResult
from tests.user_simulator.voice_synth import EdgeTTSVoiceSynthesizer

__all__ = [
    "AudioStreamInjector",
    "GroqUserPersonaEngine",
    "PersonaConfig",
    "EdgeTTSVoiceSynthesizer",
    "SystemStateVerifier",
    "VerificationResult",
    "get_scenario",
    "get_all_scenarios",
]
