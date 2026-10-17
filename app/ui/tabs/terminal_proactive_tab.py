"""Omi-Style Proactive Stream and Ambient Health Tab for JARVIS Modern Hacker HUD."""

import time
from typing import Optional
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.tools.janitor import count_clutter


class TerminalProactiveTab(QWidget):
    """Proactive Stream tracking focus duration, ambient health, clutter alerts, and system events."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.session_start_time = time.time()
        self._init_ui()

        # Update timer: ticks every 30 seconds
        self.health_timer = QTimer(self)
        self.health_timer.timeout.connect(self._update_telemetry)
        self.health_timer.start(30000)

        # Initial evaluation
        self._update_telemetry()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(12)

        # 1. Focus & Health Card
        self.health_card = QFrame()
        self.health_card.setObjectName("HackerCard")
        hc_layout = QVBoxLayout(self.health_card)
        hc_layout.setContentsMargins(12, 10, 12, 10)
        hc_layout.setSpacing(6)

        header_row = QHBoxLayout()
        title_lbl = QLabel("🧘 FOCUS & AMBIENT HEALTH (OMI AWARENESS)")
        title_lbl.setObjectName("CardHeaderTitle")
        header_row.addWidget(title_lbl)

        header_row.addStretch()

        btn_reset = QPushButton("Reset Sesi")
        btn_reset.setObjectName("HeaderPillButton")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.clicked.connect(self._reset_focus_timer)
        header_row.addWidget(btn_reset)
        hc_layout.addLayout(header_row)

        self.lbl_focus_time = QLabel("⏱️ Waktu Fokus Sesi: 0 Menit")
        self.lbl_focus_time.setStyleSheet("color: #e4e4e7; font-size: 13px; font-weight: 600;")
        hc_layout.addWidget(self.lbl_focus_time)

        self.lbl_health_advice = QLabel("🟢 Kondisi Prima: Tubuh dan mata dalam ritme kerja optimal.")
        self.lbl_health_advice.setStyleSheet("color: #10b981; font-size: 11px;")
        self.lbl_health_advice.setWordWrap(True)
        hc_layout.addWidget(self.lbl_health_advice)

        layout.addWidget(self.health_card)

        # 2. Workspace Janitor Health Card
        self.clutter_card = QFrame()
        self.clutter_card.setObjectName("HackerCard")
        cc_layout = QVBoxLayout(self.clutter_card)
        cc_layout.setContentsMargins(12, 10, 12, 10)
        cc_layout.setSpacing(4)

        cc_title = QLabel("🧹 WORKSPACE CLUTTER SENSING")
        cc_title.setObjectName("CardHeaderTitle")
        cc_layout.addWidget(cc_title)

        self.lbl_clutter_status = QLabel("Memeriksa status folder Downloads...")
        self.lbl_clutter_status.setStyleSheet("color: #e4e4e7; font-size: 12px;")
        cc_layout.addWidget(self.lbl_clutter_status)

        layout.addWidget(self.clutter_card)

        # 3. Live Telemetry Event Stream Log
        stream_header = QHBoxLayout()
        stream_lbl = QLabel("⚡ LIVE TELEMETRY & PROACTIVE EVENT FEED")
        stream_lbl.setObjectName("CardHeaderTitle")
        stream_header.addWidget(stream_lbl)

        stream_header.addStretch()

        btn_clear_log = QPushButton("Bersihkan Feed")
        btn_clear_log.setObjectName("HeaderPillButton")
        btn_clear_log.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear_log.clicked.connect(self._clear_event_log)
        stream_header.addWidget(btn_clear_log)

        layout.addLayout(stream_header)

        self.event_browser = QTextBrowser()
        self.event_browser.setObjectName("ConsoleLogArea")
        layout.addWidget(self.event_browser, 1)

        self.log_event("SYSTEM", "Proactive Awareness initialized. Monitoring ambient focus and workspace clutter.")

    def _reset_focus_timer(self) -> None:
        self.session_start_time = time.time()
        self.log_event("HEALTH", "Timer fokus sesi di-reset oleh pengguna.")
        self._update_telemetry()

    def _update_telemetry(self) -> None:
        # 1. Calculate focus duration in minutes
        elapsed_min = int((time.time() - self.session_start_time) / 60)
        self.lbl_focus_time.setText(f"⏱️ Waktu Fokus Sesi: {elapsed_min} Menit")

        if elapsed_min >= 45:
            self.lbl_health_advice.setText(
                "🟡 WAKTU ISTIRAHAT: Anda telah fokus > 45 menit. Disarankan melihat kejauhan 20 detik, regangkan bahu, dan minum air putih."
            )
            self.lbl_health_advice.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_health_advice.setText("🟢 Kondisi Prima: Tubuh dan mata dalam ritme kerja optimal.")
            self.lbl_health_advice.setStyleSheet("color: #10b981; font-size: 11px;")

        # 2. Check Clutter in Downloads
        clutter_count = count_clutter("downloads")
        if clutter_count > 20:
            self.lbl_clutter_status.setText(
                f"⚠️ <span style='color: #f59e0b; font-weight: bold;'>Peringatan:</span> "
                f"Ditemukan <b>{clutter_count} file</b> tercecer di Downloads. Buka tab Janitor untuk merapikan dalam 1 klik."
            )
        else:
            self.lbl_clutter_status.setText(
                f"✅ Folder Downloads teratur ({clutter_count} file di root). Tidak ada penumpukan berlebih."
            )

    def log_event(self, category: str, message: str) -> None:
        """Appends a timestamped proactive event to the feed."""
        timestamp = time.strftime("%H:%M:%S")
        color = "#00f0ff"
        if category == "HEALTH":
            color = "#10b981"
        elif category == "WARNING":
            color = "#f59e0b"
        elif category == "ERROR":
            color = "#ef4444"

        html = (
            f"<div style='font-family: monospace; font-size: 11px; margin-bottom: 4px;'>"
            f"<span style='color: #71717a;'>[{timestamp}]</span> "
            f"<span style='color: {color}; font-weight: bold;'>[{category}]</span> "
            f"<span style='color: #e4e4e7;'>{message}</span>"
            f"</div>"
        )
        self.event_browser.append(html)

    def _clear_event_log(self) -> None:
        self.event_browser.clear()
        self.log_event("SYSTEM", "Event feed dibersihkan.")
