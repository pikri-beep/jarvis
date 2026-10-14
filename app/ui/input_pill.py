"""Floating Input Pill Widget for the Minimalist JARVIS GUI.

Includes multi-line auto-sizing input field, microphone push/toggle button,
audio level indicator, and send action button.
"""

from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtGui import QKeyEvent, QPainter, QColor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class AutoResizingTextEdit(QTextEdit):
    """Clean text edit that emits returnPressed on Enter (unless Shift is pressed)."""

    return_pressed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("InputTextEdit")
        self.setPlaceholderText("Tanyakan apa saja atau ketik perintah...")
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(38)
        self.textChanged.connect(self._adjust_height)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                event.accept()
                self.return_pressed.emit()
                return
        else:
            super().keyPressEvent(event)

    def _adjust_height(self) -> None:
        doc = self.document()
        layout = doc.documentLayout()
        doc_height = int(layout.documentSize().height()) + 8
        new_height = max(38, min(110, doc_height))
        self.setFixedHeight(new_height)


class AudioLevelBar(QProgressBar):
    """Mini audio level meter for real-time microphone feedback."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(False)
        self.setFixedHeight(3)
        self.setStyleSheet(
            "QProgressBar { background-color: #27272a; border: none; border-radius: 1px; } "
            "QProgressBar::chunk { background-color: #38bdf8; border-radius: 1px; }"
        )
        self.hide()


class InputPill(QFrame):
    """Floating rounded input pill container."""

    text_submitted = pyqtSignal(str)
    mic_toggled = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("InputPillContainer")
        self._is_recording = False

        main_vbox = QVBoxLayout(self)
        main_vbox.setContentsMargins(12, 6, 12, 6)
        main_vbox.setSpacing(4)

        # Top row: Mic button, Text edit, Send button
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        # Microphone button
        self.btn_mic = QPushButton("🎙️")
        self.btn_mic.setObjectName("MicButton")
        self.btn_mic.setToolTip("Gunakan Mikrofon (Bicara)")
        self.btn_mic.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mic.setFixedSize(36, 36)
        self.btn_mic.clicked.connect(self._on_mic_clicked)
        row.addWidget(self.btn_mic, 0, Qt.AlignmentFlag.AlignBottom)

        # Text input field
        self.text_edit = AutoResizingTextEdit(self)
        self.text_edit.return_pressed.connect(self._on_submit)
        self.text_edit.textChanged.connect(self._on_text_changed)
        row.addWidget(self.text_edit, 1, Qt.AlignmentFlag.AlignVCenter)

        # Send button
        self.btn_send = QPushButton("➤")
        self.btn_send.setObjectName("SendButton")
        self.btn_send.setToolTip("Kirim Pesan (Enter)")
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.setFixedSize(36, 36)
        self.btn_send.setEnabled(False)
        self.btn_send.clicked.connect(self._on_submit)
        row.addWidget(self.btn_send, 0, Qt.AlignmentFlag.AlignBottom)

        main_vbox.addLayout(row)

        # Real-time audio level bar
        self.audio_bar = AudioLevelBar(self)
        main_vbox.addWidget(self.audio_bar)

    def _on_text_changed(self) -> None:
        has_text = bool(self.text_edit.toPlainText().strip())
        self.btn_send.setEnabled(has_text)

    def _on_submit(self) -> None:
        text = self.text_edit.toPlainText().strip()
        if not text:
            return
        self.text_edit.clear()
        self.text_submitted.emit(text)

    def _on_mic_clicked(self) -> None:
        self.mic_toggled.emit()

    def set_recording(self, recording: bool) -> None:
        """Updates the microphone button visual state."""
        self._is_recording = recording
        if recording:
            self.btn_mic.setProperty("listening", "true")
            self.btn_mic.setText("🔴")
            self.btn_mic.setToolTip("Sedang Merekam... Klik untuk Berhenti")
            self.btn_mic.setStyleSheet(
                "background-color: #dc2626; color: #ffffff; border-radius: 18px;"
            )
            self.audio_bar.show()
            self.audio_bar.setValue(0)
            self.text_edit.setPlaceholderText("Mendengarkan suara Anda...")
        else:
            self.btn_mic.setProperty("listening", "false")
            self.btn_mic.setText("🎙️")
            self.btn_mic.setToolTip("Gunakan Mikrofon (Bicara)")
            self.btn_mic.setStyleSheet("")
            self.audio_bar.hide()
            self.audio_bar.setValue(0)
            self.text_edit.setPlaceholderText("Tanyakan apa saja atau ketik perintah...")

        # Re-apply styles
        self.btn_mic.style().unpolish(self.btn_mic)
        self.btn_mic.style().polish(self.btn_mic)

    def set_audio_level(self, level: float) -> None:
        """Sets mic audio level (0.0 to 1.0)."""
        val = int(min(1.0, max(0.0, level)) * 100)
        self.audio_bar.setValue(val)

    def set_text(self, text: str) -> None:
        """Sets text in the input box and focuses it."""
        self.text_edit.setPlainText(text)
        self.text_edit.setFocus()
        self.btn_send.setEnabled(bool(text.strip()))

    def clear(self) -> None:
        """Clears text."""
        self.text_edit.clear()

    def set_enabled_state(self, enabled: bool) -> None:
        """Enables or disables input elements."""
        self.text_edit.setEnabled(enabled)
        self.btn_send.setEnabled(enabled and bool(self.text_edit.toPlainText().strip()))
