"""SQLite database manager for JARVIS local memory subsystem.

Follows Workstream H requirements:
- Strictly local SQLite database (zero external database server).
- Parameterized queries protecting against SQL injection.
- Atomic transactions with automatic directory creation.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
        """Initializes tables for user facts and preferences."""
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
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    )
                logger.debug("Initialized memory schema at %s", self.db_path)
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to initialize memory database: %s", e)

    def set_memory(self, key: str, value: str, category: str = "general") -> bool:
        """Stores or updates a key-value memory entry."""
        clean_key = key.strip().lower()
        clean_val = value.strip()
        try:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO user_memories (key, value, category, updated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(key) DO UPDATE SET
                            value = excluded.value,
                            category = excluded.category,
                            updated_at = CURRENT_TIMESTAMP;
                        """,
                        (clean_key, clean_val, category),
                    )
                logger.info("Saved memory: %r = %r", clean_key, clean_val)
                return True
            finally:
                conn.close()
        except Exception as e:
            logger.error("Error setting memory %s: %s", clean_key, e)
            return False

    def get_memory(self, key: str) -> Optional[str]:
        """Retrieves a memory entry by key."""
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
