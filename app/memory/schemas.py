"""Data schemas for memory records, extracted items, and conflict resolution."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryItem:
    """A single structured memory fact or user preference."""
    key: str
    value: str
    category: str = "general"  # identity, preference, habit, rule, project, general
    description: str = ""
    applies_to: str = "general"  # prompt, router, tts, general
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "description": self.description,
            "applies_to": self.applies_to,
            "confidence": self.confidence,
        }


@dataclass
class MemoryConflict:
    """Represents a conflict between an existing memory and a new candidate."""
    item: MemoryItem
    existing_value: str
    existing_description: str = ""
    prompt_question: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.item.key,
            "new_value": self.item.value,
            "existing_value": self.existing_value,
            "existing_description": self.existing_description,
            "prompt_question": self.prompt_question,
            "category": self.item.category,
        }


@dataclass
class LearnResult:
    """Outcome of a memory learning / ingestion operation."""
    learned: List[MemoryItem] = field(default_factory=list)
    conflicts: List[MemoryConflict] = field(default_factory=list)
    unchanged: List[MemoryItem] = field(default_factory=list)
    summary_message: str = ""

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0
