"""Cognitive Persona Engine using Groq Cloud API for Simulated User Agent.

Simulates human user goals, spontaneous dialogue, corrections, and multi-turn reasoning
with sub-second latency and zero CPU/RAM overhead on the local machine.
Includes an intelligent deterministic fallback when no API key is configured.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.logger import setup_logger

logger = setup_logger("jarvis.simulator.persona")


@dataclass
class PersonaConfig:
    """Configuration defining the Simulated User's identity and mission."""
    name: str = "Alex the Developer"
    role: str = "Busy software developer using Windows 11"
    goal: str = "Open Chrome, inspect system RAM usage, and create a project sandbox folder"
    language: str = "en"  # "en" or "id"
    quirks: List[str] = field(default_factory=lambda: ["speaks concisely", "uses 'Hey Jarvis' prefix"])
    max_turns: int = 6


@dataclass
class TurnPlan:
    """The decision made by the Simulated User Agent for the current turn."""
    thought: str
    spoken_text: str
    intent_type: str  # "command", "question", "memory", "confirmation", "barge_in", "done"
    is_goal_achieved: bool = False
    raw_response: Optional[str] = None


class GroqUserPersonaEngine:
    """Drives human conversational decisions using Groq LLM (or deterministic fallback)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[PersonaConfig] = None,
        model: str = "qwen/qwen3.8-27b",
    ):
        from dotenv import load_dotenv
        load_dotenv()
        settings = get_settings()
        self.api_key = api_key or getattr(settings, "groq_api_key", None) or os.getenv("GROQ_API_KEY")
        self.config = config or PersonaConfig()
        self.model = model
        self.client = None

        if self.api_key and self.api_key.strip():
            try:
                import groq
                self.client = groq.Groq(api_key=self.api_key.strip())
                logger.info("Groq client initialized successfully with model '%s'", self.model)
            except Exception as e:
                logger.warning("Failed to initialize Groq client (%s); falling back to rule planner", e)
                self.client = None
        else:
            logger.info("No GROQ_API_KEY detected. Running in deterministic smart-rule mode.")

    def _build_system_prompt(self) -> str:
        lang_instruction = (
            "Speak primarily in Indonesian."
            if self.config.language.startswith("id")
            else "Speak in English."
        )

        return f"""You are simulating a REAL HUMAN USER named {self.config.name}.
Role: {self.config.role}
Main Goal: {self.config.goal}
Language: {lang_instruction}
Quirks: {', '.join(self.config.quirks)}

You are interacting with JARVIS, an AI assistant running on Windows 11 via a voice microphone.
RULES:
1. Always speak naturally as a human talking into a microphone.
2. Most commands to activate the assistant should start with 'Hey Jarvis' or 'Jarvis'.
3. Keep spoken sentences concise and direct (1-2 sentences maximum).
4. Evaluate what JARVIS said in the previous turn and whether your goal is progressing.
5. If JARVIS asked for confirmation (e.g. 'Are you sure?'), reply with 'Yes, proceed' or 'No, cancel'.
6. If the entire goal has been completed, set 'is_goal_achieved' to true.
7. You MUST respond with ONLY valid JSON adhering strictly to this schema:
{{
  "thought": "Internal reasoning about current state and next move",
  "spoken_text": "What you speak into the microphone (e.g. 'Hey Jarvis, open Chrome')",
  "intent_type": "command | question | memory | confirmation | barge_in | done",
  "is_goal_achieved": false
}}"""

    def plan_next_turn(
        self,
        turn_number: int,
        dialogue_history: List[Dict[str, str]],
        last_jarvis_speech: str = "",
        system_feedback: str = "",
        scenario_fallback_steps: Optional[List[str]] = None,
    ) -> TurnPlan:
        """Determines what the simulated user should do and speak next."""
        # 1. Try Groq Cloud LLM if client is available
        if self.client:
            try:
                messages = [{"role": "system", "content": self._build_system_prompt()}]

                for turn in dialogue_history:
                    messages.append({"role": "user", "content": f"User previously said: {turn.get('user', '')}"})
                    if turn.get("jarvis"):
                        messages.append({"role": "assistant", "content": f"JARVIS replied: {turn.get('jarvis', '')}"})

                target_hint = ""
                if scenario_fallback_steps and (turn_number - 1) < len(scenario_fallback_steps):
                    target_hint = f"Target intent for this turn: '{scenario_fallback_steps[turn_number - 1]}'\n"

                current_context = (
                    f"Turn {turn_number}/{self.config.max_turns}.\n"
                    f"Latest JARVIS response: '{last_jarvis_speech}'\n"
                    f"System verification status: '{system_feedback}'\n"
                    f"{target_hint}"
                    f"Decide your next spoken sentence adhering to this target intent."
                )
                messages.append({"role": "user", "content": current_context})

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.4,
                    max_tokens=300,
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content
                data = json.loads(content)

                return TurnPlan(
                    thought=data.get("thought", "Proceeding with goal"),
                    spoken_text=data.get("spoken_text", "Hey Jarvis, help me."),
                    intent_type=data.get("intent_type", "command"),
                    is_goal_achieved=bool(data.get("is_goal_achieved", False)),
                    raw_response=content,
                )

            except Exception as e:
                logger.warning("Groq inference error (%s); falling back to scenario plan", e)

        # 2. Deterministic smart fallback
        return self._plan_fallback_step(
            turn_number=turn_number,
            last_jarvis_speech=last_jarvis_speech,
            scenario_fallback_steps=scenario_fallback_steps,
        )

    def _plan_fallback_step(
        self,
        turn_number: int,
        last_jarvis_speech: str,
        scenario_fallback_steps: Optional[List[str]] = None,
    ) -> TurnPlan:
        """Fallback deterministic planner when offline or without API key."""
        steps = scenario_fallback_steps or [
            "Hey Jarvis, open Chrome",
            "Hey Jarvis, check system status",
            "Hey Jarvis, thank you",
        ]

        # Check confirmation prompt
        lower_jarvis = last_jarvis_speech.lower()
        if any(w in lower_jarvis for w in ["sure", "confirm", "yakin", "lanjutkan", "continue?"]):
            return TurnPlan(
                thought="JARVIS requested confirmation for safety. Confirming action.",
                spoken_text="Yes, please proceed.",
                intent_type="confirmation",
                is_goal_achieved=False,
            )

        step_idx = turn_number - 1
        if step_idx < len(steps):
            spoken = steps[step_idx]
            is_last = (step_idx == len(steps) - 1)
            return TurnPlan(
                thought=f"Executing planned scenario step {step_idx + 1}/{len(steps)}",
                spoken_text=spoken,
                intent_type="command",
                is_goal_achieved=is_last,
            )
        else:
            return TurnPlan(
                thought="All scenario steps completed.",
                spoken_text="Hey Jarvis, that's all for now. Thank you.",
                intent_type="done",
                is_goal_achieved=True,
            )
