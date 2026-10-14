"""SQLite database manager for JARVIS local memory subsystem.

Follows Workstream H requirements:
- Strictly local SQLite database (zero external database server).
- Parameterized queries protecting against SQL injection.
- Atomic transactions with automatic directory creation.
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.logger import setup_logger

logger = setup_logger("jarvis.memory.database")

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "jarvis_memory.db"


class Database:
    """Manages SQLite connection and schemas for persistent assistant memory."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a connection with dictionary-like row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Initializes tables for user facts and preferences with automatic migration."""
        try:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS user_memories (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            key TEXT UNIQUE NOT NULL,
                            value TEXT NOT NULL,
                            category TEXT DEFAULT 'general',
                            description TEXT DEFAULT '',
                            applies_to TEXT DEFAULT 'general',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    )
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS learned_aliases (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            alias TEXT UNIQUE NOT NULL,
                            canonical_target TEXT NOT NULL,
                            target_type TEXT DEFAULT 'app',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    )

                    # Dynamic column migration for existing user_memories tables
                    cursor = conn.execute("PRAGMA table_info(user_memories);")
                    existing_cols = {row["name"] for row in cursor.fetchall()}
                    if "description" not in existing_cols:
                        conn.execute("ALTER TABLE user_memories ADD COLUMN description TEXT DEFAULT '';")
                    if "applies_to" not in existing_cols:
                        conn.execute("ALTER TABLE user_memories ADD COLUMN applies_to TEXT DEFAULT 'general';")

                logger.debug("Initialized memory schema at %s", self.db_path)
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to initialize memory database: %s", e)

    def set_memory(
        self,
        key: str,
        value: str,
        category: str = "general",
        description: str = "",
        applies_to: str = "general",
    ) -> bool:
        """Stores or updates a key-value memory entry with metadata."""
        clean_key = key.strip().lower()
        clean_val = value.strip()
        try:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO user_memories (key, value, category, description, applies_to, updated_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(key) DO UPDATE SET
                            value = excluded.value,
                            category = excluded.category,
                            description = CASE WHEN excluded.description != '' THEN excluded.description ELSE user_memories.description END,
                            applies_to = CASE WHEN excluded.applies_to != 'general' THEN excluded.applies_to ELSE user_memories.applies_to END,
                            updated_at = CURRENT_TIMESTAMP;
                        """,
                        (clean_key, clean_val, category, description, applies_to),
                    )
                logger.info("Saved memory: %r = %r (category=%s, applies_to=%s)", clean_key, clean_val, category, applies_to)
                return True
            finally:
                conn.close()
        except Exception as e:
            logger.error("Error setting memory %s: %s", clean_key, e)
            return False

    def get_memory(self, key: str) -> Optional[str]:
        """Retrieves a memory entry value by key."""
        clean_key = key.strip().lower()
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT value FROM user_memories WHERE key = ?;",
                    (clean_key,),
                )
                row = cursor.fetchone()
                return row["value"] if row else None
            finally:
                conn.close()
        except Exception as e:
            logger.error("Error reading memory %s: %s", clean_key, e)
            return None

    def get_memory_entry(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieves full memory record by key."""
        clean_key = key.strip().lower()
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT key, value, category, description, applies_to, created_at, updated_at FROM user_memories WHERE key = ?;",
                    (clean_key,),
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
            finally:
                conn.close()
        except Exception as e:
            logger.error("Error reading memory entry %s: %s", clean_key, e)
            return None

    def check_conflict(self, key: str, new_value: str) -> Optional[Dict[str, Any]]:
        """Checks if a key already exists with a meaningfully different value.

        Returns the existing memory record if there is a conflict, or None.
        """
        existing = self.get_memory_entry(key)
        if not existing:
            return None
        old_val = (existing.get("value") or "").strip().lower()
        new_val = new_value.strip().lower()
        if old_val != new_val:
            return existing
        return None

    def get_memories_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Retrieves memory records belonging to a specific category."""
        clean_cat = category.strip().lower()
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT key, value, category, description, applies_to, updated_at FROM user_memories WHERE category = ? ORDER BY updated_at DESC;",
                    (clean_cat,),
                )
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()
        except Exception as e:
            logger.error("Error reading memories by category %s: %s", clean_cat, e)
            return []

    def get_all_memory_entries(self) -> List[Dict[str, Any]]:
        """Retrieves all memory records with complete metadata."""
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT key, value, category, description, applies_to, created_at, updated_at FROM user_memories ORDER BY category, key;"
                )
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()
        except Exception as e:
            logger.error("Error reading all memory entries: %s", e)
            return []

    def get_all_memories(self) -> Dict[str, str]:
        """Retrieves all stored user memories as a dictionary."""
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute("SELECT key, value FROM user_memories ORDER BY updated_at DESC;")
                return {row["key"]: row["value"] for row in cursor.fetchall()}
            finally:
                conn.close()
        except Exception as e:
            logger.error("Error reading all memories: %s", e)
            return {}

    def delete_memory(self, key: str) -> bool:
        """Deletes a memory entry by key."""
        clean_key = key.strip().lower()
        try:
            conn = self._get_connection()
            try:
                with conn:
                    cursor = conn.execute(
                        "DELETE FROM user_memories WHERE key = ?;",
                        (clean_key,),
                    )
                    return cursor.rowcount > 0
            finally:
                conn.close()
        except Exception as e:
            logger.error("Error deleting memory %s: %s", clean_key, e)
            return False

    def clear_all_memories(self) -> bool:
        """Purges all user memories."""
        try:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("DELETE FROM user_memories;")
                logger.info("Cleared all user memories.")
                return True
            finally:
                conn.close()
        except Exception as e:
            logger.error("Error clearing all memories: %s", e)
            return False

    def set_learned_alias(self, alias: str, canonical_target: str, target_type: str = "app") -> bool:
        """Stores or updates a learned user alias."""
        clean_alias = alias.strip().lower()
        clean_target = canonical_target.strip().lower()
        try:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO learned_aliases (alias, canonical_target, target_type)
                        VALUES (?, ?, ?)
                        ON CONFLICT(alias) DO UPDATE SET
                            canonical_target = excluded.canonical_target,
                            target_type = excluded.target_type;
                        """,
                        (clean_alias, clean_target, target_type),
                    )
                logger.info("Saved learned alias: %r -> %r (%s)", clean_alias, clean_target, target_type)
                return True
            finally:
                conn.close()
        except Exception as e:
            logger.error("Error saving learned alias %s: %s", clean_alias, e)
            return False

    def get_all_learned_aliases(self) -> List[Dict[str, str]]:
        """Retrieves all learned aliases from database."""
        try:
            conn = self._get_connection()
            try:
                cursor = conn.execute("SELECT alias, canonical_target, target_type FROM learned_aliases;")
                return [
                    {"alias": row["alias"], "canonical_target": row["canonical_target"], "target_type": row["target_type"]}
                    for row in cursor.fetchall()
                ]
            finally:
                conn.close()
        except Exception as e:
            logger.error("Error retrieving learned aliases: %s", e)
            return []

    def delete_learned_alias(self, alias: str) -> bool:
        """Deletes a learned alias."""
        clean_alias = alias.strip().lower()
        try:
            conn = self._get_connection()
            try:
                with conn:
                    cursor = conn.execute("DELETE FROM learned_aliases WHERE alias = ?;", (clean_alias,))
                    return cursor.rowcount > 0
            finally:
                conn.close()
        except Exception as e:
            logger.error("Error deleting learned alias %s: %s", clean_alias, e)
            return False
