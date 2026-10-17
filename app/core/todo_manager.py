"""Todo and Scratchpad manager for JARVIS personal assistant.

Integrates with local SQLite storage and supports natural language task capture.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.logger import setup_logger
from app.memory.database import Database

logger = setup_logger("jarvis.core.todo_manager")


class TodoManager:
    """Manages user todos, tasks, and scratchpad notes with SQLite persistence."""

    def __init__(self, database: Optional[Database] = None):
        self.db = database or Database()

    def add_task(self, raw_input: str, default_category: str = "general") -> Tuple[bool, str, int]:
        """Parses natural text and stores a new todo item.

        Examples:
            - 'kirim email revisi jam 3 sore'
            - 'todo: beli kopi dan susu'
            - 'catat: selesaikan laporan tugas akhir'
        """
        clean = raw_input.strip()
        if not clean:
            return False, "Tugas tidak boleh kosong.", -1

        # Strip common voice/text prefixes
        patterns = [
            r"^(?:tolong\s+)?(?:catat(?:kan)?|ingat(?:kan)?|tambah(?:kan)?)(?:\s+(?:todo|tugas|catatan))?(?:\s*:\s*|\s+)",
            r"^(?:todo|tugas|catatan)\s*:\s*",
            r"^ingatkan\s+(?:saya|aku)\s+(?:untuk\s+)?",
        ]
        task_text = clean
        for p in patterns:
            task_text = re.sub(p, "", task_text, flags=re.IGNORECASE).strip()

        if not task_text:
            task_text = clean

        # Clean and robust due date/time extraction heuristic
        due_date = ""
        # 1. Match time format e.g. 'jam 14.20', 'jam 14:20', 'pukul 14.20', '14:20', '14.20'
        m_time = re.search(
            r"\b(?:jam|pukul)?\s*(\d{1,2})[\.:](\d{2})(?:\s*(pagi|siang|sore|malam|wib|am|pm))?\b",
            task_text,
            flags=re.IGNORECASE,
        )
        if m_time:
            hr = int(m_time.group(1))
            mn = int(m_time.group(2))
            period = (m_time.group(3) or "").lower()
            if period in ("siang", "sore", "malam", "pm") and hr < 12:
                hr += 12
            elif period == "am" and hr == 12:
                hr = 0
            due_date = f"{hr:02d}:{mn:02d}"
            # Strip the time expression from the task text
            task_text = (task_text[:m_time.start()] + " " + task_text[m_time.end():]).strip()
        else:
            # 2. Match relative date/time phrases
            due_patterns = [
                r"\b(besok(?:\s+pagi|\s+siang|\s+sore|\s+malam)?)\b",
                r"\b(nanti\s+malam|nanti\s+sore|nanti\s+siang)\b",
                r"\b(hari\s+ini)\b",
                r"\b(jam\s+\d{1,2}(?:\s*(?:pagi|siang|sore|malam|wib))?)\b",
                r"\b(pukul\s+\d{1,2})\b",
            ]
            for dp in due_patterns:
                m = re.search(dp, task_text, flags=re.IGNORECASE)
                if m:
                    due_date = m.group(1).strip()
                    task_text = (task_text[:m.start()] + " " + task_text[m.end():]).strip()
                    break

        # Clean trailing/leading punctuation from task_text
        task_text = re.sub(r"^[\s,;:\-]+|[\s,;:\-]+$", "", task_text).strip()
        if not task_text:
            task_text = clean

        todo_id = self.db.add_todo(title=task_text, due_date=due_date, category=default_category)
        if todo_id > 0:
            msg = f"Tugas telah dicatat: '{task_text}'"
            if due_date:
                msg += f" (Waktu: {due_date})"
            return True, msg, todo_id
        return False, "Gagal menyimpan tugas ke database.", -1

    def list_tasks(self, include_completed: bool = True) -> List[Dict[str, Any]]:
        """Returns list of tasks."""
        return self.db.get_todos(include_completed=include_completed)

    def toggle_task(self, task_id: int) -> bool:
        """Toggles complete/incomplete state."""
        return self.db.toggle_todo(task_id)

    def delete_task(self, task_id: int) -> bool:
        """Deletes a task by ID."""
        return self.db.delete_todo(task_id)

    def clear_completed(self) -> int:
        """Clears all completed tasks."""
        return self.db.clear_completed_todos()

    def clear_all(self) -> int:
        """Clears all tasks from database and returns number of cleared items."""
        return self.db.clear_all_todos()
