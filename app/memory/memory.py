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
from app.memory.extractor import MemoryExtractor
from app.memory.schemas import LearnResult, MemoryConflict, MemoryItem

logger = setup_logger("jarvis.memory.manager")


class MemoryManager:
    """Manages explicit user memories, facts, preferences, and deep personalization."""

    def __init__(self, db: Optional[Database] = None, extractor: Optional[MemoryExtractor] = None):
        self.db = db or Database()
        self.extractor = extractor or MemoryExtractor()

    def get_honorific(self, default: str = "sir") -> str:
        """Retrieves user's preferred honorific/panggilan (e.g. 'bos', 'sir', 'kak')."""
        hon = self.db.get_memory("honorific")
        if hon and hon.strip():
            return hon.strip().lower()
        return default

    def get_preferred_tool(self, tool_type: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieves user's preferred tool for a given category (browser, editor, music)."""
        key_map = {
            "browser": "preferred_browser",
            "editor": "preferred_code_editor",
            "code_editor": "preferred_code_editor",
            "music": "preferred_music",
            "music_app": "preferred_music",
        }
        target_key = key_map.get(tool_type.lower(), f"preferred_{tool_type.lower()}")
        val = self.db.get_memory(target_key)
        return val.strip() if val else default

    def store_fact(self, key: str, value: str, category: str = "general", description: str = "", applies_to: str = "general") -> Tuple[bool, str]:
        """Stores a user preference or fact."""
        honorific = self.get_honorific()
        success = self.db.set_memory(key, value, category=category, description=description, applies_to=applies_to)
        if success:
            return True, f"Saya akan mengingat bahwa {key} Anda adalah {value}, {honorific}."
        return False, f"Maaf {honorific}, gagal menyimpan informasi ke memori."

    def recall_fact(self, key: str) -> Optional[str]:
        """Recalls a single fact by key."""
        return self.db.get_memory(key)

    def recall_all(self) -> Dict[str, str]:
        """Recalls all saved facts."""
        return self.db.get_all_memories()

    def forget_fact(self, key: str) -> Tuple[bool, str]:
        """Removes a stored fact."""
        honorific = self.get_honorific()
        success = self.db.delete_memory(key)
        if success:
            return True, f"Informasi tentang '{key}' telah dihapus dari memori, {honorific}."
        return False, f"Saya tidak menemukan catatan tentang '{key}' di memori, {honorific}."

    def clear_all(self) -> Tuple[bool, str]:
        """Clears all stored memories."""
        honorific = self.get_honorific()
        success = self.db.clear_all_memories()
        if success:
            return True, f"Seluruh catatan memori telah dibersihkan, {honorific}."
        return False, "Gagal membersihkan memori."

    def learn_from_text(self, text: str, auto_confirm: bool = False, language: str = "id") -> LearnResult:
        """Extracts facts from natural text, checks for conflicts, and updates memory."""
        is_id = language.lower().startswith("id")
        honorific = self.get_honorific()
        items = self.extractor.extract(text)

        result = LearnResult()
        if not items:
            result.summary_message = (
                f"Saya tidak dapat mendeteksi informasi atau kebiasaan baru dari kalimat tersebut, {honorific}."
                if is_id else f"I couldn't detect any specific facts or habits to learn, {honorific}."
            )
            return result

        for item in items:
            conflict = self.db.check_conflict(item.key, item.value)
            if conflict and not auto_confirm:
                # Require confirmation before overriding
                old_val = conflict.get("value", "")
                old_desc = conflict.get("description", "") or item.description or item.key
                q_text = (
                    f"Sebelumnya {old_desc} Anda adalah '{old_val}'. Apakah Anda ingin memperbaruinya menjadi '{item.value}', {honorific}?"
                    if is_id else
                    f"Previously your {old_desc} was '{old_val}'. Would you like to update it to '{item.value}', {honorific}?"
                )
                conf_obj = MemoryConflict(
                    item=item,
                    existing_value=old_val,
                    existing_description=old_desc,
                    prompt_question=q_text,
                )
                result.conflicts.append(conf_obj)
            else:
                # Save directly
                self.db.set_memory(
                    key=item.key,
                    value=item.value,
                    category=item.category,
                    description=item.description,
                    applies_to=item.applies_to,
                )
                result.learned.append(item)

        # Build response message
        # If honorific was updated in this turn, use the newly updated honorific
        new_hon = self.get_honorific()
        summary_parts = []
        if result.learned:
            learned_points = "; ".join([f"{m.description or m.key}: {m.value}" for m in result.learned])
            summary_parts.append(
                f"Baik {new_hon}, saya telah mempelajari {len(result.learned)} hal baru: {learned_points}."
                if is_id else
                f"Certainly {new_hon}, I have learned {len(result.learned)} item(s): {learned_points}."
            )

        if result.conflicts:
            c = result.conflicts[0]
            summary_parts.append(c.prompt_question)

        result.summary_message = " ".join(summary_parts)
        return result

    def apply_conflict_resolution(self, conflict: MemoryConflict, approved: bool, language: str = "id") -> Tuple[bool, str]:
        """Commits or discards a conflicting memory update based on user confirmation."""
        is_id = language.lower().startswith("id")
        honorific = self.get_honorific()
        item = conflict.item

        if approved:
            self.db.set_memory(
                key=item.key,
                value=item.value,
                category=item.category,
                description=item.description,
                applies_to=item.applies_to,
            )
            # Re-read honorific in case it was updated
            new_hon = self.get_honorific()
            desc = item.description or item.key
            msg = (
                f"Baik {new_hon}, {desc} Anda kini telah diperbarui menjadi '{item.value}'."
                if is_id else
                f"Understood {new_hon}, your {desc} has been updated to '{item.value}'."
            )
            return True, msg
        else:
            desc = conflict.existing_description or item.key
            msg = (
                f"Baik {honorific}, pembaruan dibatalkan. {desc} tetap menggunakan '{conflict.existing_value}'."
                if is_id else
                f"Understood {honorific}, update cancelled. Keeping '{conflict.existing_value}' for {desc}."
            )
            return False, msg

    def format_profile_card(self, language: str = "id") -> str:
        """Formats all known user information into a comprehensive visual profile card."""
        is_id = language.lower().startswith("id")
        entries = self.db.get_all_memory_entries()
        honorific = self.get_honorific()

        if not entries:
            return (
                f"Saya belum memiliki catatan profil tentang Anda, {honorific}. Gunakan command '/learn' untuk mengajari saya!"
                if is_id else
                f"I don't have any profile notes about you yet, {honorific}. Use '/learn' to teach me!"
            )

        by_cat: Dict[str, List[Dict[str, Any]]] = {}
        for e in entries:
            cat = (e.get("category") or "general").lower()
            by_cat.setdefault(cat, []).append(e)

        lines = [
            f"=== PROFIL & KEBIASAAN PENGGUNA ({honorific.upper()}) ===" if is_id else f"=== USER PROFILE & HABITS ({honorific.upper()}) ==="
        ]

        cat_titles = {
            "identity": "👤 Identitas & Panggilan" if is_id else "👤 Identity & Honorific",
            "preference": "🛠️ Preferensi Aplikasi & Tool" if is_id else "🛠️ Tool & App Preferences",
            "habit": "⏰ Kebiasaan & Rutinitas" if is_id else "⏰ Habits & Routines",
            "rule": "📜 Aturan & Instruksi Perilaku" if is_id else "📜 Rules & Custom Instructions",
            "project": "📂 Proyek & Direktori Kerja" if is_id else "📂 Projects & Workspaces",
            "general": "📌 Catatan Lainnya" if is_id else "📌 Other Facts",
        }

        for cat_key, title in cat_titles.items():
            items = by_cat.get(cat_key, [])
            if items:
                lines.append(f"\n{title}:")
                for it in items:
                    desc = it.get("description") or it.get("key")
                    lines.append(f"  • {desc}: {it.get('value')}")

        return "\n".join(lines)

    def format_all_memories(self, language: str = "id") -> str:
        """Formats all stored memories into a natural spoken assistant response."""
        return self.format_profile_card(language=language)


# Singleton instance
memory_manager = MemoryManager()


def save_user_memory(key: str, value: str, user_input: str = "", language: str = "id") -> Tuple[bool, str]:
    """Saves a user fact with natural response generation."""
    is_id = language.lower().startswith("id")
    honorific = memory_manager.get_honorific()
    if not value and user_input:
        match = re.search(r"(?:bahwa|that|is|adalah|=)\s+(.+)$", user_input, re.IGNORECASE)
        if match:
            value = match.group(1).strip().rstrip(".")

    if not key or not value:
        key = key or "catatan"
        value = value or user_input

    success = memory_manager.db.set_memory(key, value)
    if success:
        msg = (
            f"Baik {honorific}, saya akan mengingat bahwa {key} Anda adalah {value}."
            if is_id else
            f"Certainly {honorific}. I will remember that your {key} is {value}."
        )
        return True, msg
    else:
        msg = f"Maaf {honorific}, gagal menyimpan informasi ke memori." if is_id else "Failed to store memory."
        return False, msg


def recall_user_memories(query: str = "", language: str = "id") -> str:
    """Recalls stored user facts or prints full profile card."""
    is_id = language.lower().startswith("id")
    honorific = memory_manager.get_honorific()
    if query:
        val = memory_manager.recall_fact(query)
        if val:
            return f"{query} Anda adalah {val}, {honorific}." if is_id else f"Your {query} is {val}, {honorific}."
    return memory_manager.format_profile_card(language=language)


def forget_user_memory(key: str, language: str = "id") -> Tuple[bool, str]:
    """Removes a stored fact."""
    is_id = language.lower().startswith("id")
    honorific = memory_manager.get_honorific()
    if key.lower() in ("all", "semua", "semuanya"):
        success = memory_manager.db.clear_all_memories()
        msg = f"Seluruh catatan memori telah dibersihkan, {honorific}." if is_id else f"All stored memories cleared, {honorific}."
        return success, msg
    success = memory_manager.db.delete_memory(key)
    if success:
        msg = f"Informasi tentang '{key}' telah dihapus dari memori, {honorific}." if is_id else f"Information regarding '{key}' removed from memory, {honorific}."
    else:
        msg = f"Saya tidak menemukan catatan tentang '{key}', {honorific}." if is_id else f"No record found for '{key}', {honorific}."
    return success, msg


def get_relevant_memories_prompt(language: str = "id") -> str:
    """Returns stored memories formatted for LLM system prompt injection."""
    entries = memory_manager.db.get_all_memory_entries()
    if not entries:
        return ""

    lines = ["\n\n[USER PROFILE, PREFERENCES & RULES]:"]
    honorific = memory_manager.get_honorific()
    lines.append(f"- Preferred Honorific: '{honorific}' (always address the user with this honorific instead of a generic title)")

    for e in entries:
        k = e.get("key", "")
        v = e.get("value", "")
        cat = e.get("category", "")
        desc = e.get("description", "") or k
        lines.append(f"- {desc} [{cat}]: {v}")

    return "\n".join(lines)


def store_learned_alias(alias: str, canonical_target: str, target_type: str = "app") -> bool:
    """Stores a confirmed alias in SQLite and syncs it with runtime app/website registries."""
    success = memory_manager.db.set_learned_alias(alias, canonical_target, target_type=target_type)
    if success:
        if target_type == "website":
            from app.tools.browser import website_registry
            website_registry.register_alias(alias, canonical_target)
        else:
            from app.tools.apps import registry
            registry.register_alias(alias, canonical_target)
    return success


def load_learned_aliases_into_registries() -> int:
    """Loads all learned aliases from SQLite into the runtime application and website registries."""
    aliases = memory_manager.db.get_all_learned_aliases()
    from app.tools.apps import registry
    from app.tools.browser import website_registry

    count = 0
    for item in aliases:
        a = item.get("alias", "")
        tgt = item.get("canonical_target", "")
        t_type = item.get("target_type", "app")
        if a and tgt:
            if t_type == "website":
                website_registry.register_alias(a, tgt)
            else:
                registry.register_alias(a, tgt)
            count += 1
    if count:
        logger.info("Loaded %d learned alias(es) into registries", count)
    return count


# Auto-load any existing learned aliases upon module load
try:
    load_learned_aliases_into_registries()
except Exception as _e:
    logger.debug("Could not auto-load learned aliases on startup: %s", _e)

