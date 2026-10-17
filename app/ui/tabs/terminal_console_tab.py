"""Interactive Terminal Console Tab for JARVIS Modern Hacker HUD.

Features:
- Windows Terminal / PowerShell aesthetic with glowing prompt `JARVIS ❯ _`.
- Smooth streaming markdown/HTML text output.
- Command history buffer accessible via Up/Down arrow keys.
- Push-to-Talk microphone toggle and Quick Action chips.
"""

from typing import List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class CommandLineEdit(QLineEdit):
    """QLineEdit with Up/Down arrow key command history navigation and Escape handling."""

    escape_pressed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.history: List[str] = []
        self.history_index: int = -1

    def add_to_history(self, text: str) -> None:
        clean = text.strip()
        if clean and (not self.history or self.history[-1] != clean):
            self.history.append(clean)
        self.history_index = len(self.history)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
            return
        if event.key() == Qt.Key.Key_Up:
            if self.history and self.history_index > 0:
                self.history_index -= 1
                self.setText(self.history[self.history_index])
                self.setCursorPosition(len(self.text()))
            return
        elif event.key() == Qt.Key.Key_Down:
            if self.history and self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.setText(self.history[self.history_index])
                self.setCursorPosition(len(self.text()))
            elif self.history_index >= len(self.history) - 1:
                self.history_index = len(self.history)
                self.clear()
            return
        super().keyPressEvent(event)


class TerminalConsoleTab(QWidget):
    """Console tab delivering a rich hacker terminal experience."""

    command_submitted = pyqtSignal(str)
    mic_toggled = pyqtSignal()
    stop_speech_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)

        # 1. Terminal Console Log Browser
        self.log_area = QTextBrowser(self)
        self.log_area.setObjectName("ConsoleLogArea")
        self.log_area.setOpenExternalLinks(True)
        layout.addWidget(self.log_area, 1)

        # Initial ASCII / Welcome Banner
        self._render_welcome_banner()

        # 2. Quick Action Chips
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(8)
        quick_chips = [
            ("⚡ /status", "/status"),
            ("📜 /cheat", "/cheat"),
            ("🧹 Rapikan Downloads", "Rapikan folder downloads"),
            ("📝 Catat Todo", "Catat todo: "),
            ("💻 Info Sistem", "Cek info sistem"),
            ("❓ /help", "/help"),
        ]
        for label, cmd in quick_chips:
            btn = QPushButton(label)
            btn.setObjectName("HeaderPillButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, c=cmd: self._on_chip_clicked(c))
            chips_layout.addWidget(btn)
        chips_layout.addStretch()
        layout.addLayout(chips_layout)

        # 3. Terminal Command Input Bar
        input_frame = QFrame()
        input_frame.setObjectName("TerminalInputFrame")
        h_layout = QHBoxLayout(input_frame)
        h_layout.setContentsMargins(8, 6, 8, 6)
        h_layout.setSpacing(8)

        # Prompt Prefix
        prefix_lbl = QLabel("JARVIS ❯")
        prefix_lbl.setObjectName("TerminalPromptPrefix")
        h_layout.addWidget(prefix_lbl)

        # Command Input Field
        self.input_edit = CommandLineEdit(self)
        self.input_edit.setObjectName("TerminalLineEdit")
        self.input_edit.setPlaceholderText("Ketik perintah PowerShell / AI query, atau tekan tombol mic...")
        self.input_edit.returnPressed.connect(self._on_submit)
        self.input_edit.escape_pressed.connect(self.stop_speech_requested.emit)
        h_layout.addWidget(self.input_edit, 1)

        # Stop Button (allows immediate cancellation with 1 click or Esc)
        self.btn_stop = QPushButton("⏹️ STOP (Esc)")
        self.btn_stop.setObjectName("TerminalStopButton")
        self.btn_stop.setStyleSheet(
            "background-color: #450a0a; color: #f87171; border: 1px solid #dc2626; border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: bold;"
        )
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setToolTip("Hentikan suara / proses (Tekan Esc)")
        self.btn_stop.clicked.connect(self.stop_speech_requested.emit)
        self.btn_stop.hide()
        h_layout.addWidget(self.btn_stop)

        # Mic Push-to-Talk Button
        self.btn_mic = QPushButton("🎙️")
        self.btn_mic.setObjectName("TerminalIconButton")
        self.btn_mic.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mic.setToolTip("Push-to-Talk (Bicara langsung)")
        self.btn_mic.clicked.connect(self.mic_toggled.emit)
        h_layout.addWidget(self.btn_mic)

        # Send Button
        self.btn_send = QPushButton("KIRIM ↵")
        self.btn_send.setObjectName("TerminalActionButton")
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.clicked.connect(self._on_submit)
        h_layout.addWidget(self.btn_send)

        layout.addWidget(input_frame)

    def _render_welcome_banner(self) -> None:
        banner_html = (
            "<div style='font-family: monospace; color: #00f0ff; font-size: 11px; margin-bottom: 8px;'>"
            "░░█ ▄▀█ █▀█ █░█ █ █▀<br>"
            "█▄█ █▀█ █▀▄ ▀▄▀ █ ▄█ — HACKER TERMINAL HUD v2.5 [OMI AMBIENT EDITION]<br>"
            "</div>"
            "<div style='color: #71717a; font-size: 12px; margin-bottom: 12px;'>"
            "System ready. Press <span style='color: #00f0ff; font-weight: bold;'>Win + Alt + J</span> from anywhere in Windows to toggle HUD.<br>"
            "Tipe perintah langsung atau katakan <span style='color: #10b981; font-weight: bold;'>'Hey Jarvis'</span> untuk interaksi suara."
            "</div>"
            "<hr style='border: none; border-top: 1px solid #1f1f28; margin-bottom: 14px;'>"
        )
        self.log_area.setHtml(banner_html)

    def _on_chip_clicked(self, command: str) -> None:
        self.input_edit.setText(command)
        self.input_edit.setFocus()
        if not command.endswith(": "):
            self._on_submit()

    def _on_submit(self) -> None:
        text = self.input_edit.text().strip()
        if not text:
            return
        self.input_edit.add_to_history(text)
        self.input_edit.clear()
        self.command_submitted.emit(text)

    def append_user_message(self, text: str) -> None:
        user_html = (
            f"<div style='margin-top: 10px; margin-bottom: 4px;'>"
            f"<span style='color: #10b981; font-weight: bold;'>YOU ❯</span> "
            f"<span style='color: #f4f4f5;'>{text}</span>"
            f"</div>"
        )
        self.log_area.append(user_html)
        self.scroll_to_bottom()

    def start_assistant_message(self, initial_text: str = "") -> None:
        asst_html = (
            f"<div style='margin-top: 6px; margin-bottom: 8px;'>"
            f"<span style='color: #00f0ff; font-weight: bold;'>JARVIS ❯</span> "
            f"<span style='color: #e4e4e7;'>{initial_text}</span>"
        )
        self.log_area.append(asst_html)
        self.scroll_to_bottom()

    def append_assistant_token(self, token: str) -> None:
        # Move cursor to end and insert plaintext token
        cursor = self.log_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        self.log_area.setTextCursor(cursor)
        self.scroll_to_bottom()

    def end_assistant_message(self) -> None:
        cursor = self.log_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertHtml("</div>")
        self.log_area.setTextCursor(cursor)
        self.scroll_to_bottom()

    def set_recording_state(self, is_recording: bool) -> None:
        if is_recording:
            self.btn_mic.setText("🔴 MEREKAM")
            self.btn_mic.setStyleSheet("background-color: #ef4444; color: #ffffff; font-weight: bold;")
        else:
            self.btn_mic.setText("🎙️")
            self.btn_mic.setStyleSheet("")

    def set_input_enabled(self, enabled: bool) -> None:
        self.input_edit.setEnabled(enabled)
        self.btn_send.setEnabled(enabled)
        if enabled:
            self.input_edit.setFocus()

    def set_speaking_state(self, is_speaking: bool) -> None:
        """Shows/hides the quick Stop button when TTS speech or generation is active."""
        if is_speaking:
            self.btn_stop.show()
        else:
            self.btn_stop.hide()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.stop_speech_requested.emit()
            return
        super().keyPressEvent(event)

    def scroll_to_bottom(self) -> None:
        sb = self.log_area.verticalScrollBar()
        sb.setValue(sb.maximum())
