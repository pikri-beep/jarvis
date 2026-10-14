"""Dialog components for JARVIS GUI, including dangerous action confirmations."""

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ConfirmationDialog(QDialog):
    """Modal dialog for confirming dangerous operations (Rule 12)."""

    def __init__(
        self,
        title: str,
        message: str,
        details: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Warning Header
        header_layout = QHBoxLayout()
        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 28px;")
        header_layout.addWidget(icon_label)

        title_label = QLabel(f"<b>{title}</b>")
        title_label.setStyleSheet("font-size: 15px; color: #ef4444;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Main message
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet("font-size: 13px; line-height: 1.4;")
        layout.addWidget(msg_label)

        # Optional detail snippet
        if details:
            details_box = QLabel(details)
            details_box.setWordWrap(True)
            details_box.setStyleSheet(
                "background-color: #1a1a1e; color: #f59e0b; padding: 10px; "
                "border: 1px solid #3f3f46; border-radius: 6px; font-family: monospace;"
            )
            layout.addWidget(details_box)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Batalkan")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_confirm = QPushButton("Setujui / Izinkan")
        self.btn_confirm.setProperty("class", "danger")
        self.btn_confirm.setStyleSheet(
            "background-color: #dc2626; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px;"
        )
        self.btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_confirm)

        layout.addLayout(btn_layout)


def ask_dangerous_confirmation(
    parent: Optional[QWidget], title: str, message: str, details: Optional[str] = None
) -> bool:
    """Helper function to show the confirmation modal synchronously."""
    dialog = ConfirmationDialog(title=title, message=message, details=details, parent=parent)
    result = dialog.exec()
    return result == QDialog.DialogCode.Accepted


class ProfileDialog(QDialog):
    """Clean minimalist modal displaying user identity and learned memories."""

    def __init__(self, memories: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Profil & Memori Pengguna")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setStyleSheet(
            "QDialog { background-color: #111114; color: #f4f4f5; font-family: 'Segoe UI', sans-serif; }"
            "QLabel { color: #f4f4f5; font-size: 13px; }"
            "QPushButton { background-color: #27272a; color: #f4f4f5; border: 1px solid #3f3f46; "
            "border-radius: 6px; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #3f3f46; }"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("<b>👤 Profil & Memori Tersimpan</b>")
        title.setStyleSheet("font-size: 16px; color: #38bdf8;")
        layout.addWidget(title)

        subtitle = QLabel("Informasi yang diingat oleh JARVIS secara lokal di SQLite:")
        subtitle.setStyleSheet("color: #71717a; font-size: 12px;")
        layout.addWidget(subtitle)

        # Card container
        card = QWidget()
        card.setStyleSheet(
            "background-color: #18181b; border: 1px solid #27272a; border-radius: 8px; padding: 12px;"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        if not memories:
            empty_lbl = QLabel("Belum ada memori yang tersimpan.\nGunakan perintah seperti: <i>Ingat bahwa namaku Alex</i>.")
            empty_lbl.setStyleSheet("color: #71717a; font-style: italic;")
            card_layout.addWidget(empty_lbl)
        else:
            for k, v in sorted(memories.items()):
                row = QHBoxLayout()
                lbl_k = QLabel(f"<b>{k}:</b>")
                lbl_k.setStyleSheet("color: #94a3b8; min-width: 120px;")
                lbl_v = QLabel(str(v))
                lbl_v.setStyleSheet("color: #f4f4f5;")
                lbl_v.setWordWrap(True)
                row.addWidget(lbl_k)
                row.addWidget(lbl_v, 1)
                card_layout.addLayout(row)

        layout.addWidget(card)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Tutup")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

