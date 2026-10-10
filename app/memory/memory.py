"""High-level persistent memory manager and intent handler for JARVIS.

Follows Workstream H requirements:
- Controlled, intentional user fact storage (zero automatic conversation logging of secrets).
- Clear retrieval and forgetting capabilities.
- Natural bilingual response generation.
"""

import re
from typing import Dict, Optional, Tuple

from app.core.logger import setup_logger
from app.memory.database import Database

logger = setup_logger("jarvis.memory.manager")


class MemoryManager:
    """Manages explicit user memories, facts, and preferences."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def store_fact(self, key: str, value: str) -> Tuple[bool, str]:
        """Stores a user preference or fact."""
        success = self.db.set_memory(key, value)
        if success:
            return True, f"Saya akan mengingat bahwa {key} Anda adalah {value}, sir."
        return False, "Maaf sir, gagal menyimpan informasi ke memori."

    def recall_fact(self, key: str) -> Optional[str]:
        """Recalls a single fact by key."""
        return self.db.get_memory(key)

    def recall_all(self) -> Dict[str, str]:
        """Recalls all saved facts."""
        return self.db.get_all_memories()

    def forget_fact(self, key: str) -> Tuple[bool, str]:
        """Removes a stored fact."""
        success = self.db.delete_memory(key)
        if success:
            return True, f"Informasi tentang '{key}' telah dihapus dari memori, sir."
        return False, f"Saya tidak menemukan catatan tentang '{key}' di memori, sir."

    def clear_all(self) -> Tuple[bool, str]:
        """Clears all stored memories."""
        success = self.db.clear_all_memories()
        if success:
            return True, "Seluruh catatan memori telah dibersihkan, sir."
        return False, "Gagal membersihkan memori."

    def format_all_memories(self, language: str = "id") -> str:
        """Formats all stored memories into a natural spoken assistant response."""
        memories = self.recall_all()
        is_id = language.lower().startswith("id")
        if not memories:
            return "Saya belum memiliki catatan memori tentang Anda, sir." if is_id else "I don't have any saved facts about you yet, sir."

        items = [f"{k}: {v}" for k, v in memories.items()]
        joined = ", ".join(items)
        if is_id:
            return f"Berikut hal yang saya ingat tentang Anda, sir: {joined}."
        else:
            return f"Here is what I remember about you, sir: {joined}."


# Singleton instance
memory_manager = MemoryManager()


def save_user_memory(key: str, value: str, user_input: str = "", language: str = "id") -> Tuple[bool, str]:
    """Saves a user fact with natural response generation."""
    is_id = language.lower().startswith("id")
    # If key or value is missing, attempt quick extraction from user input
    if not value and user_input:
        # e.g., "ingat nama saya Alex", "remember my name is Alex", "ingat bahasa favorit saya Python"
        match = re.search(r"(?:bahwa|that|is|adalah|=)\s+(.+)$", user_input, re.IGNORECASE)
        if match:
            value = match.group(1).strip().rstrip(".")

    if not key or not value:
        key = key or "catatan"
        value = value or user_input

    success = memory_manager.db.set_memory(key, value)
    if success:
        if is_id:
            msg = f"Baik sir, saya akan mengingat bahwa {key} Anda adalah {value}."
        else:
            msg = f"Certainly, sir. I will remember that your {key} is {value}."
        return True, msg
    else:
        msg = "Maaf sir, gagal menyimpan informasi ke memori." if is_id else "Failed to store memory, sir."
        return False, msg


def recall_user_memories(query: str = "", language: str = "id") -> str:
    """Recalls stored user facts."""
    is_id = language.lower().startswith("id")
    if query:
        val = memory_manager.recall_fact(query)
        if val:
            return f"{query} Anda adalah {val}, sir." if is_id else f"Your {query} is {val}, sir."
    return memory_manager.format_all_memories(language=language)


def forget_user_memory(key: str, language: str = "id") -> Tuple[bool, str]:
    """Removes a stored fact."""
    is_id = language.lower().startswith("id")
    if key.lower() in ("all", "semua", "semuanya"):
        success = memory_manager.db.clear_all_memories()
        msg = "Seluruh catatan memori telah dibersihkan, sir." if is_id else "All stored memories cleared, sir."
        return success, msg
    success = memory_manager.db.delete_memory(key)
    if success:
        msg = f"Informasi tentang '{key}' telah dihapus dari memori, sir." if is_id else f"Information regarding '{key}' removed from memory, sir."
    else:
        msg = f"Saya tidak menemukan catatan tentang '{key}', sir." if is_id else f"No record found for '{key}', sir."
    return success, msg


def get_relevant_memories_prompt(language: str = "id") -> str:
    """Returns stored memories formatted for LLM system prompt injection."""
    memories = memory_manager.recall_all()
    if not memories:
        return ""
    items = "\n".join([f"- {k}: {v}" for k, v in memories.items()])
    return f"\n\n[Known User Facts & Preferences]:\n{items}"
