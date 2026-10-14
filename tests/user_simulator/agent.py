"""Simulated User Agent Orchestrator for JARVIS E2E Voice Testing.

Drives multi-turn autonomous user persona testing against JARVIS, synthesizing voice,
measuring latency, and verifying real Windows system outcomes.
"""

import time
from typing import Dict, List, Optional

from app.core.config import Settings, get_settings
from app.core.logger import setup_logger
from app.core.orchestrator import Orchestrator
from app.voice.wake_word import WakeWordDetector
from tests.user_simulator.audio_injector import AudioStreamInjector
from tests.user_simulator.dashboard import TestDashboard
from tests.user_simulator.persona_engine import GroqUserPersonaEngine
from tests.user_simulator.scenarios import ScenarioStep, TestScenario
from tests.user_simulator.verifier import SystemStateVerifier, VerificationResult
from tests.user_simulator.voice_synth import EdgeTTSVoiceSynthesizer

logger = setup_logger("jarvis.simulator.agent")


class SimulatedUserAgent:
    """Autonomous agent that uses JARVIS like a real human user."""

    def __init__(
        self,
        orchestrator: Optional[Orchestrator] = None,
        groq_api_key: Optional[str] = None,
        fast_mode: bool = False,
    ):
        self.settings = get_settings()
        self.orchestrator = orchestrator or Orchestrator(settings=self.settings)
        self.fast_mode = fast_mode

        # Core simulator components
        self.synth = EdgeTTSVoiceSynthesizer()
        self.injector = AudioStreamInjector()
        self.verifier = SystemStateVerifier()
        self.dashboard = TestDashboard()

        # Hook TTS to capture spoken output from JARVIS
        self.injector.hook_tts_capture(self.orchestrator)

    def run_scenario(self, scenario: TestScenario) -> bool:
        """Executes a full scenario with the Simulated User persona.

        Args:
            scenario: The TestScenario specification to execute.

        Returns:
            bool: True if all turns and verifications passed.
        """
        # Configure persona engine
        engine = GroqUserPersonaEngine(
            config=scenario.persona,
        )
        engine_label = f"Groq Cloud ({engine.model})" if engine.client else "Smart-Rule Persona Planner"

        self.dashboard.print_scenario_header(
            scenario=scenario,
            engine_name=engine_label,
            voice_name=scenario.preferred_voice,
        )

        dialogue_history: List[Dict[str, str]] = []
        turn_results: List[VerificationResult] = []
        last_jarvis_speech = ""
        system_feedback = "All systems initialized."

        fallback_phrases = [step.spoken_phrase for step in scenario.steps]

        for turn_idx, target_step in enumerate(scenario.steps, 1):
            t_turn_start = time.time()
            latency_metrics: Dict[str, float] = {}

            # 1. Persona decides what to say
            plan = engine.plan_next_turn(
                turn_number=turn_idx,
                dialogue_history=dialogue_history,
                last_jarvis_speech=last_jarvis_speech,
                system_feedback=system_feedback,
                scenario_fallback_steps=fallback_phrases,
            )

            # Use planned phrase or fallback to scenario step phrase
            user_phrase = plan.spoken_text or target_step.spoken_phrase

            # 2. Voice Synthesizer generates human audio PCM
            t_synth_start = time.time()
            pcm_audio = self.synth.synthesize(user_phrase, voice=scenario.preferred_voice)
            synth_duration = time.time() - t_synth_start
            latency_metrics["voice_synth"] = synth_duration * 1000.0

            # 3. Simulate Voice Capture via Orchestrator STT
            t_stt_start = time.time()
            transcription, info = self.orchestrator.transcribe_audio(
                pcm_audio,
                language=scenario.persona.language,
            )
            stt_duration = time.time() - t_stt_start
            latency_metrics["stt"] = stt_duration * 1000.0

            # If STT transcribed empty or hallucinatory short noise, fall back to user_phrase
            cleaned_transcription = (transcription or "").strip()
            if cleaned_transcription and any(c.isalnum() for c in cleaned_transcription):
                effective_input = cleaned_transcription
            else:
                effective_input = user_phrase

            # 4. Execute turn through JARVIS Core
            t_exec_start = time.time()
            route, stream_gen = self.orchestrator.process_input_stream(effective_input)

            # Consume stream tokens & let TTS synthesize
            tokens = []
            for token in stream_gen:
                tokens.append(token)
            jarvis_text_reply = "".join(tokens).strip()

            exec_duration = time.time() - t_exec_start
            latency_metrics["jarvis_router"] = exec_duration * 1000.0

            # 5. Capture spoken output from JARVIS
            jarvis_spoken = self.injector.get_latest_jarvis_speech()
            if not jarvis_spoken:
                jarvis_spoken = jarvis_text_reply

            last_jarvis_speech = jarvis_spoken
            total_turn_ms = (time.time() - t_turn_start) * 1000.0
            latency_metrics["total_turn"] = total_turn_ms

            # 6. Verify Windows OS and conversational state
            verification = self.verifier.verify_turn(
                turn_number=turn_idx,
                intent=plan.intent_type,
                spoken_command=user_phrase,
                jarvis_reply=jarvis_spoken,
                expected_process=target_step.expected_process,
                expected_sandbox_path=target_step.expected_sandbox_path,
                expected_keywords=target_step.expected_keywords,
                is_safety_test=target_step.is_safety_test,
                latency_ms=latency_metrics,
            )

            turn_results.append(verification)

            # 7. Update Live Dashboard
            self.dashboard.print_turn(
                turn_number=turn_idx,
                user_spoken=user_phrase,
                jarvis_reply=jarvis_spoken,
                verification=verification,
            )

            # Update history and feedback for next turn
            dialogue_history.append({"user": user_phrase, "jarvis": jarvis_spoken})
            system_feedback = "; ".join(verification.details)

            # Brief pause between turns for realistic human conversation pacing
            if not self.fast_mode and turn_idx < len(scenario.steps):
                time.sleep(1.0)

        # 8. Print Final Scorecard
        return self.dashboard.print_scorecard(scenario, turn_results)
