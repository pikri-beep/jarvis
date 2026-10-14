"""Tool Automation hub tab for direct hardware and OS operations."""

import datetime
import time
from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.orchestrator import Orchestrator
from app.ui.dialogs import ask_dangerous_confirmation


class ToolsTab(QWidget):
    """Control hub for direct local tool execution and audit logging."""

    log_entry_added = pyqtSignal(str, str, str, str)

    def __init__(self, orchestrator: Orchestrator, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Quick Control Panel
        controls_group = QGroupBox("Panel Cepat Automasi Komputer")
        grid = QGridLayout(controls_group)
        grid.setSpacing(10)

        # App Actions
        btn_chrome = QPushButton("🌐 Buka Google Chrome")
        btn_chrome.clicked.connect(lambda: self._execute_fast_command("open chrome"))
        grid.addWidget(btn_chrome, 0, 0)

        btn_notepad = QPushButton("📝 Buka Notepad")
        btn_notepad.clicked.connect(lambda: self._execute_fast_command("open notepad"))
        grid.addWidget(btn_notepad, 0, 1)

        btn_spotify = QPushButton("🎵 Buka Spotify")
        btn_spotify.clicked.connect(lambda: self._execute_fast_command("open spotify"))
        grid.addWidget(btn_spotify, 0, 2)

        btn_explorer = QPushButton("📁 Buka File Explorer")
        btn_explorer.clicked.connect(lambda: self._execute_fast_command("open explorer"))
        grid.addWidget(btn_explorer, 0, 3)

        # System & Media
        btn_screenshot = QPushButton("📸 Ambil Screenshot")
        btn_screenshot.clicked.connect(lambda: self._execute_fast_command("take screenshot"))
        grid.addWidget(btn_screenshot, 1, 0)

        btn_vol_up = QPushButton("🔊 Volume Naik (+10%)")
        btn_vol_up.clicked.connect(lambda: self._execute_fast_command("increase volume"))
        grid.addWidget(btn_vol_up, 1, 1)

        btn_vol_down = QPushButton("🔉 Volume Turun (-10%)")
        btn_vol_down.clicked.connect(lambda: self._execute_fast_command("decrease volume"))
        grid.addWidget(btn_vol_down, 1, 2)

        btn_lock = QPushButton("🔒 Kunci Komputer")
        btn_lock.clicked.connect(self._trigger_lock_screen)
        grid.addWidget(btn_lock, 1, 3)

        layout.addWidget(controls_group)

        # Custom Tool Runner Bar
        custom_frame = QFrame()
        custom_frame.setStyleSheet(
            "background-color: #1a1a1e; border: 1px solid #27272a; border-radius: 8px; padding: 6px;"
        )
        custom_layout = QHBoxLayout(custom_frame)
        custom_layout.setContentsMargins(8, 8, 8, 8)

        lbl_custom = QLabel("Eksekusi Cepat:")
        lbl_custom.setStyleSheet("font-weight: 600; color: #38bdf8;")
        custom_layout.addWidget(lbl_custom)

        self.input_tool = QLineEdit()
        self.input_tool.setPlaceholderText("Contoh: 'open youtube', 'create folder Data on Desktop'...")
        self.input_tool.returnPressed.connect(self._run_custom_tool)
        custom_layout.addWidget(self.input_tool, 1)

        btn_run = QPushButton("Jalankan")
        btn_run.setProperty("class", "primary")
        btn_run.clicked.connect(self._run_custom_tool)
        custom_layout.addWidget(btn_run)

        layout.addWidget(custom_frame)

        # Execution History Log Table
        lbl_history = QLabel("Riwayat Eksekusi Tool & Audit Log")
        lbl_history.setStyleSheet("font-weight: 600; color: #e4e4e7; margin-top: 8px;")
        layout.addWidget(lbl_history)

        self.table_history = QTableWidget()
        self.table_history.setColumnCount(4)
        self.table_history.setHorizontalHeaderLabels(["Waktu", "Perintah / Tool", "Hasil Eksekusi", "Durasi"])
        self.table_history.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_history.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_history.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_history.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_history.verticalHeader().setVisible(False)
        layout.addWidget(self.table_history, 1)

    def _execute_fast_command(self, cmd_text: str) -> None:
        """Executes a command through the router or tool system and logs result."""
        t_start = time.time()
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        try:
            route_res, stream_gen = self.orchestrator.process_input_stream(cmd_text)
            tokens = list(stream_gen)
            response = "".join(tokens).strip()
            duration = f"{time.time() - t_start:.2f}s"
            self._add_log_row(time_str, cmd_text, response or "Berhasil dieksekusi", duration)
        except Exception as e:
            duration = f"{time.time() - t_start:.2f}s"
            self._add_log_row(time_str, cmd_text, f"Gagal: {e}", duration, is_error=True)

    def _run_custom_tool(self) -> None:
        cmd = self.input_tool.text().strip()
        if cmd:
            self.input_tool.clear()
            self._execute_fast_command(cmd)

    def _trigger_lock_screen(self) -> None:
        confirmed = ask_dangerous_confirmation(
            self,
            title="Kunci Komputer",
            message="Apakah Anda yakin ingin mengunci layar Windows sekarang?",
            details="Aksi: Rundll32.exe user32.dll,LockWorkStation",
        )
        if confirmed:
            self._execute_fast_command("lock windows")

    def _add_log_row(
        self, timestamp: str, command: str, result: str, duration: str, is_error: bool = False
    ) -> None:
        row = self.table_history.rowCount()
        self.table_history.insertRow(row)

        item_time = QTableWidgetItem(timestamp)
        item_cmd = QTableWidgetItem(command)
        item_res = QTableWidgetItem(result)
        item_dur = QTableWidgetItem(duration)

        if is_error:
            item_res.setForeground(Qt.GlobalColor.red)
        else:
            item_res.setForeground(Qt.GlobalColor.green)

        self.table_history.setItem(row, 0, item_time)
        self.table_history.setItem(row, 1, item_cmd)
        self.table_history.setItem(row, 2, item_res)
        self.table_history.setItem(row, 3, item_dur)

        self.table_history.scrollToBottom()
