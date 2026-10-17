"""Interactive Todo & Notes Scratchpad Tab for JARVIS Modern Hacker Terminal HUD."""

from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.todo_manager import TodoManager


class TodoItemWidget(QWidget):
    """Custom widget rendered inside QListWidgetItem for a single task."""

    toggled = pyqtSignal(int)
    deleted = pyqtSignal(int)

    def __init__(self, item_data: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.item_id = item_data.get("id", -1)
        self.is_completed = bool(item_data.get("is_completed", 0))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(10)

        # 1. Completion Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.is_completed)
        self.checkbox.stateChanged.connect(lambda: self.toggled.emit(self.item_id))
        layout.addWidget(self.checkbox)

        # 2. Title Label
        title_text = item_data.get("title", "")
        self.lbl_title = QLabel(title_text)
        self._update_title_style()
        layout.addWidget(self.lbl_title, 1)

        # 3. Due Date Badge (if present)
        due_date = item_data.get("due_date", "")
        if due_date:
            lbl_due = QLabel(f"⏱️ {due_date}")
            lbl_due.setStyleSheet("color: #38bdf8; font-size: 11px; background-color: #1e293b; padding: 2px 6px; border-radius: 4px;")
            layout.addWidget(lbl_due)

        # 4. Delete Button
        btn_del = QPushButton("✕")
        btn_del.setFixedSize(22, 22)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet("background-color: transparent; color: #ef4444; border: none; font-weight: bold;")
        btn_del.clicked.connect(lambda: self.deleted.emit(self.item_id))
        layout.addWidget(btn_del)

    def _update_title_style(self) -> None:
        if self.is_completed:
            self.lbl_title.setStyleSheet("color: #71717a; text-decoration: line-through;")
        else:
            self.lbl_title.setStyleSheet("color: #f4f4f5; font-weight: 500;")


class TerminalTodoTab(QWidget):
    """Todo and Scratchpad management tab."""

    def __init__(self, todo_manager: Optional[TodoManager] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.todo_manager = todo_manager or TodoManager()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        # Header Info & Clear Button
        header_layout = QHBoxLayout()
        title_lbl = QLabel("📝 TODO & SCRATCHPAD")
        title_lbl.setObjectName("CardHeaderTitle")
        header_layout.addWidget(title_lbl)

        self.lbl_count = QLabel("0 Tugas")
        self.lbl_count.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        header_layout.addWidget(self.lbl_count)

        header_layout.addStretch()

        btn_clear = QPushButton("Bersihkan Selesai")
        btn_clear.setObjectName("HeaderPillButton")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self._clear_completed)
        header_layout.addWidget(btn_clear)

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setObjectName("HeaderPillButton")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(self.reload_todos)
        header_layout.addWidget(btn_refresh)

        layout.addLayout(header_layout)

        # Input Card to add a new task
        input_card = QFrame()
        input_card.setObjectName("HackerCard")
        ic_layout = QHBoxLayout(input_card)
        ic_layout.setContentsMargins(8, 6, 8, 6)

        self.input_todo = QLineEdit()
        self.input_todo.setObjectName("TerminalLineEdit")
        self.input_todo.setPlaceholderText("Tambah tugas baru... (Contoh: 'Kirim revisi jam 3 sore' atau 'Beli susu')")
        self.input_todo.returnPressed.connect(self._on_add_todo)
        ic_layout.addWidget(self.input_todo, 1)

        btn_add = QPushButton("+ TAMBAH")
        btn_add.setObjectName("TerminalActionButton")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self._on_add_todo)
        ic_layout.addWidget(btn_add)

        layout.addWidget(input_card)

        # List Widget for Tasks
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("TerminalListWidget")
        layout.addWidget(self.list_widget, 1)

        # Initial Load
        self.reload_todos()

    def reload_todos(self) -> None:
        """Reloads all tasks from database and renders list items."""
        self.list_widget.clear()
        items = self.todo_manager.list_tasks(include_completed=True)
        active_count = sum(1 for item in items if not item.get("is_completed"))
        self.lbl_count.setText(f"{active_count} Tugas Aktif ({len(items)} Total)")

        if not items:
            empty_item = QListWidgetItem()
            empty_lbl = QLabel("Belum ada tugas. Tulis tugas di atas atau katakan 'Jarvis, catat todo: ...'")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet("color: #52525b; padding: 20px; font-style: italic;")
            empty_item.setSizeHint(empty_lbl.sizeHint())
            self.list_widget.addItem(empty_item)
            self.list_widget.setItemWidget(empty_item, empty_lbl)
            return

        for item in items:
            list_item = QListWidgetItem(self.list_widget)
            widget = TodoItemWidget(item, self)
            widget.toggled.connect(self._on_item_toggled)
            widget.deleted.connect(self._on_item_deleted)
            list_item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, widget)

    def _on_add_todo(self) -> None:
        text = self.input_todo.text().strip()
        if not text:
            return
        self.todo_manager.add_task(text)
        self.input_todo.clear()
        self.reload_todos()

    def _on_item_toggled(self, item_id: int) -> None:
        self.todo_manager.toggle_task(item_id)
        self.reload_todos()

    def _on_item_deleted(self, item_id: int) -> None:
        self.todo_manager.delete_task(item_id)
        self.reload_todos()

    def _clear_completed(self) -> None:
        self.todo_manager.clear_completed()
        self.reload_todos()
