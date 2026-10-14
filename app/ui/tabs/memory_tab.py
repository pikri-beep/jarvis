"""Memory management tab for inspecting and modifying SQLite user memories."""

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.orchestrator import Orchestrator
from app.memory.database import Database
from app.ui.dialogs import ask_dangerous_confirmation


class MemoryTab(QWidget):
    """View and editor for persistent assistant facts and user preferences."""

    def __init__(self, orchestrator: Orchestrator, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.db = Database()
        self._init_ui()
        self.refresh_memories()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Header Info
        header_box = QHBoxLayout()
        lbl_title = QLabel("Manajemen Memori Jangka Panjang (SQLite)")
        lbl_title.setStyleSheet("font-weight: 600; font-size: 14px; color: #38bdf8;")
        header_box.addWidget(lbl_title)
        header_box.addStretch()

        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.clicked.connect(self.refresh_memories)
        header_box.addWidget(self.btn_refresh)
        layout.addLayout(header_box)

        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Cari memori tersimpan berdasarkan kunci (key)...")
        self.search_input.textChanged.connect(self._filter_table)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Table View
        self.table_memories = QTableWidget()
        self.table_memories.setColumnCount(3)
        self.table_memories.setHorizontalHeaderLabels(["Kunci (Key)", "Nilai / Fakta (Value)", "Kategori"])
        self.table_memories.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_memories.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_memories.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_memories.verticalHeader().setVisible(False)
        self.table_memories.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table_memories, 1)

        # Add / Edit Memory Form
        form_group = QGroupBox("Tambah atau Perbarui Memori")
        form_layout = QHBoxLayout(form_group)
        form_layout.setSpacing(8)

        self.input_key = QLineEdit()
        self.input_key.setPlaceholderText("Kunci (contoh: preferred_browser, nama)")
        form_layout.addWidget(self.input_key, 1)

        self.input_val = QLineEdit()
        self.input_val.setPlaceholderText("Nilai (contoh: Chrome, Alex)")
        form_layout.addWidget(self.input_val, 2)

        self.btn_save = QPushButton("💾 Simpan")
        self.btn_save.setProperty("class", "primary")
        self.btn_save.clicked.connect(self._save_memory)
        form_layout.addWidget(self.btn_save)

        layout.addWidget(form_group)

        # Actions Row
        actions_layout = QHBoxLayout()

        self.btn_delete = QPushButton("🗑️ Lupakan / Hapus Terpilih")
        self.btn_delete.setProperty("class", "danger")
        self.btn_delete.clicked.connect(self._delete_selected)
        actions_layout.addWidget(self.btn_delete)

        actions_layout.addStretch()

        self.btn_clear_all = QPushButton("⚠️ Kosongkan Semua Memori")
        self.btn_clear_all.setStyleSheet(
            "background-color: transparent; color: #ef4444; border: 1px solid #7f1d1d; "
            "padding: 6px 14px; border-radius: 6px;"
        )
        self.btn_clear_all.clicked.connect(self._clear_all)
        actions_layout.addWidget(self.btn_clear_all)

        layout.addLayout(actions_layout)

    def refresh_memories(self) -> None:
        """Fetches all memories from SQLite and displays them."""
        self.table_memories.setRowCount(0)
        try:
            conn = self.db._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT key, value, category FROM user_memories ORDER BY updated_at DESC;"
                )
                rows = cursor.fetchall()
                for row_idx, r in enumerate(rows):
                    self.table_memories.insertRow(row_idx)
                    self.table_memories.setItem(row_idx, 0, QTableWidgetItem(str(r["key"])))
                    self.table_memories.setItem(row_idx, 1, QTableWidgetItem(str(r["value"])))
                    self.table_memories.setItem(row_idx, 2, QTableWidgetItem(str(r["category"] or "general")))
            finally:
                conn.close()
        except Exception as e:
            QMessageBox.warning(self, "Database Error", f"Gagal membaca memori: {e}")

    def _filter_table(self, query: str) -> None:
        q = query.lower().strip()
        for r in range(self.table_memories.rowCount()):
            key_item = self.table_memories.item(r, 0)
            val_item = self.table_memories.item(r, 1)
            cat_item = self.table_memories.item(r, 2)
            key_text = key_item.text().lower() if key_item else ""
            val_text = val_item.text().lower() if val_item else ""
            cat_text = cat_item.text().lower() if cat_item else ""
            match = q in key_text or q in val_text or q in cat_text
            self.table_memories.setRowHidden(r, not match)

    def _save_memory(self) -> None:
        k = self.input_key.text().strip()
        v = self.input_val.text().strip()
        if not k or not v:
            QMessageBox.information(self, "Input Kurang", "Kunci dan Nilai memori tidak boleh kosong.")
            return

        success = self.db.set_memory(k, v)
        if success:
            self.input_key.clear()
            self.input_val.clear()
            self.refresh_memories()
        else:
            QMessageBox.critical(self, "Error", "Gagal menyimpan memori.")

    def _delete_selected(self) -> None:
        row = self.table_memories.currentRow()
        if row < 0:
            QMessageBox.information(self, "Pilih Baris", "Silakan klik baris memori yang ingin dihapus terlebih dahulu.")
            return

        key_item = self.table_memories.item(row, 0)
        if not key_item:
            return

        key = key_item.text()
        confirmed = ask_dangerous_confirmation(
            self,
            title="Hapus Memori",
            message=f"Apakah Anda yakin ingin menghapus memori '{key}'?",
            details=f"Fakta tentang '{key}' tidak akan diingat lagi oleh JARVIS.",
        )
        if confirmed:
            self.db.delete_memory(key)
            self.refresh_memories()

    def _clear_all(self) -> None:
        confirmed = ask_dangerous_confirmation(
            self,
            title="Kosongkan Semua Memori",
            message="PERINGATAN: Tindakan ini akan menghapus SELURUH data preferensi dan fakta tersimpan!",
            details="Operasi: DELETE FROM user_memories;",
        )
        if confirmed:
            self.db.clear_all_memories()
            self.refresh_memories()
