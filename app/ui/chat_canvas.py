"""Chat Canvas and Message Bubbles for the Minimalist JARVIS GUI."""

from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QPushButton,
)


class MessageBubble(QFrame):
    """Clean minimalist message card for user or assistant."""

    def __init__(self, sender: str, text: str, is_user: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.is_user = is_user
        self.setObjectName("UserBubble" if is_user else "AssistantBubble")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(4)

        # Sender header
        lbl_sender = QLabel(sender.upper())
        lbl_sender.setObjectName("BubbleSender")
        if is_user:
            lbl_sender.setStyleSheet("color: #94a3b8;")
        else:
            lbl_sender.setStyleSheet("color: #38bdf8;")
        layout.addWidget(lbl_sender)

        # Message body
        self.lbl_text = QLabel(text)
        self.lbl_text.setObjectName("BubbleText")
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.lbl_text)

    def append_text(self, token: str) -> None:
        """Appends streaming token to the message bubble."""
        curr = self.lbl_text.text()
        self.lbl_text.setText(curr + token)

    def set_text(self, text: str) -> None:
        """Sets the complete text."""
        self.lbl_text.setText(text)


class ChatCanvas(QWidget):
    """Scrollable canvas hosting the conversational message stream."""

    suggestion_clicked = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("ChatScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Scroll Content
        self.content_widget = QWidget()
        self.content_widget.setObjectName("ChatScrollContent")
        self.messages_layout = QVBoxLayout(self.content_widget)
        self.messages_layout.setContentsMargins(20, 16, 20, 16)
        self.messages_layout.setSpacing(14)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)

        self.welcome_container: Optional[QWidget] = None
        self._show_welcome_state()

    def _show_welcome_state(self) -> None:
        """Displays an elegant minimalist greeting when chat is empty."""
        self.welcome_container = QWidget()
        layout = QVBoxLayout(self.welcome_container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0, 60, 0, 40)
        layout.setSpacing(16)

        title = QLabel("Apa yang bisa saya bantu hari ini?")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #f4f4f5;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Ketik pertanyaan, jalankan perintah, atau gunakan mikrofon.")
        subtitle.setStyleSheet("font-size: 13px; color: #71717a;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # Quick action suggestions
        suggestions_box = QHBoxLayout()
        suggestions_box.setSpacing(10)
        suggestions_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        quick_prompts = [
            "Buka Chrome",
            "Cari info cuaca hari ini",
            "Siapa aku?",
        ]
        for q in quick_prompts:
            btn = QPushButton(q)
            btn.setStyleSheet(
                "background-color: #18181b; color: #d4d4d8; border: 1px solid #27272a; "
                "border-radius: 14px; padding: 6px 14px; font-size: 12px;"
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, text=q: self.suggestion_clicked.emit(text))
            suggestions_box.addWidget(btn)

        layout.addLayout(suggestions_box)
        self.messages_layout.addWidget(self.welcome_container)

    def add_user_message(self, text: str) -> MessageBubble:
        """Adds a user message bubble."""
        if self.welcome_container:
            self.welcome_container.hide()
            self.welcome_container.deleteLater()
            self.welcome_container = None

        bubble = MessageBubble("Anda", text, is_user=True)
        self.messages_layout.addWidget(bubble)
        self.scroll_to_bottom()
        return bubble

    def add_assistant_message(self, text: str = "", sender: str = "JARVIS") -> MessageBubble:
        """Adds an assistant message bubble (ready for streaming or instant display)."""
        if self.welcome_container:
            self.welcome_container.hide()
            self.welcome_container.deleteLater()
            self.welcome_container = None

        bubble = MessageBubble(sender, text, is_user=False)
        self.messages_layout.addWidget(bubble)
        self.scroll_to_bottom()
        return bubble

    def append_message(self, role_or_sender: str, text: str, **kwargs) -> MessageBubble:
        """Generic append message supporting role ('user', 'assistant') or custom sender."""
        if role_or_sender.lower() in ("user", "anda"):
            return self.add_user_message(text)
        sender = "JARVIS" if role_or_sender.lower() in ("assistant", "jarvis") else role_or_sender
        return self.add_assistant_message(text, sender=sender)

    def clear_chat(self) -> None:
        """Clears all messages and restores the welcome state."""
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._show_welcome_state()

    def scroll_to_bottom(self) -> None:
        """Scrolls the chat canvas to the newest message smoothly."""
        QScrollArea.ensureVisible(
            self.scroll_area,
            0,
            self.content_widget.sizeHint().height() + 500,
            0,
            0,
        )
