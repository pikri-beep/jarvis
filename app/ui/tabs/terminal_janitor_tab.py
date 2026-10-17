"""One-Click Workspace Janitor Tab for JARVIS Modern Hacker HUD.

Allows scanning and organizing cluttered Downloads and Desktop folders with 1 click.
"""

from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.tools.filesystem import open_folder
from app.tools.janitor import clean_workspace, scan_workspace


class TerminalJanitorTab(QWidget):
    """Tab providing workspace file scanning and safe categorization."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(12)

        # 1. Header & Folder Selector Card
        header_card = QFrame()
        header_card.setObjectName("HackerCard")
        hc_layout = QHBoxLayout(header_card)
        hc_layout.setContentsMargins(10, 8, 10, 8)
        hc_layout.setSpacing(12)

        title_lbl = QLabel("🧹 WORKSPACE JANITOR")
        title_lbl.setObjectName("CardHeaderTitle")
        hc_layout.addWidget(title_lbl)

        hc_layout.addStretch()

        lbl_target = QLabel("Target Folder:")
        lbl_target.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        hc_layout.addWidget(lbl_target)

        self.combo_target = QComboBox()
        self.combo_target.addItems(["Downloads", "Desktop"])
        self.combo_target.setStyleSheet(
            "background-color: #181820; color: #00f0ff; border: 1px solid #282834; padding: 4px 10px; border-radius: 4px; font-weight: 600;"
        )
        self.combo_target.currentIndexChanged.connect(self._on_scan)
        hc_layout.addWidget(self.combo_target)

        btn_open = QPushButton("📂 Buka Folder")
        btn_open.setObjectName("HeaderPillButton")
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.clicked.connect(self._on_open_folder)
        hc_layout.addWidget(btn_open)

        layout.addWidget(header_card)

        # 2. Stats & Status Overview Card
        self.stats_card = QFrame()
        self.stats_card.setObjectName("HackerCard")
        sc_layout = QVBoxLayout(self.stats_card)
        sc_layout.setContentsMargins(12, 10, 12, 10)
        sc_layout.setSpacing(6)

        self.lbl_stats_summary = QLabel("📊 Klik 'Scan Folder' untuk menganalisis file yang berantakan.")
        self.lbl_stats_summary.setStyleSheet("color: #e4e4e7; font-size: 13px; font-weight: 600;")
        sc_layout.addWidget(self.lbl_stats_summary)

        self.lbl_categories_breakdown = QLabel("")
        self.lbl_categories_breakdown.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        self.lbl_categories_breakdown.setWordWrap(True)
        sc_layout.addWidget(self.lbl_categories_breakdown)

        layout.addWidget(self.stats_card)

        # 3. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_scan = QPushButton("🔍 SCAN FOLDER")
        self.btn_scan.setObjectName("HeaderPillButton")
        self.btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scan.clicked.connect(self._on_scan)
        btn_layout.addWidget(self.btn_scan)

        self.btn_clean = QPushButton("✨ RAPIKAN SEKARANG")
        self.btn_clean.setObjectName("TerminalActionButton")
        self.btn_clean.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clean.clicked.connect(self._on_clean)
        btn_layout.addWidget(self.btn_clean)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 4. Detailed Activity / File Log
        self.log_browser = QTextBrowser()
        self.log_browser.setObjectName("ConsoleLogArea")
        layout.addWidget(self.log_browser, 1)

        # Initial Auto-Scan
        self._on_scan()

    def _get_current_target(self) -> str:
        return self.combo_target.currentText().lower()

    def _on_scan(self) -> None:
        target = self._get_current_target()
        scan = scan_workspace(target)
        if not scan.get("success"):
            self.lbl_stats_summary.setText(f"⚠️ Gagal menganalisis folder: {scan.get('error')}")
            return

        total_files = scan.get("total_files", 0)
        total_mb = scan.get("total_mb", 0.0)
        categories = scan.get("categories", {})

        if total_files == 0:
            self.lbl_stats_summary.setText(f"✅ Folder {target.capitalize()} sudah rapi! Tidak ada file tercecer di root.")
            self.lbl_categories_breakdown.setText("Kondisi optimal. Tidak ada file yang perlu dipindahkan.")
            self.btn_clean.setEnabled(False)
            self.log_browser.setHtml("<span style='color: #10b981;'>Folder dalam kondisi bersih dan teratur.</span>")
            return

        self.btn_clean.setEnabled(True)
        self.lbl_stats_summary.setText(
            f"⚠️ Ditemukan <span style='color: #00f0ff;'>{total_files} file</span> tercecer ({total_mb} MB) di folder {target.capitalize()}."
        )

        breakdown_text = " • ".join(
            f"{cat}: {len(files)} file" for cat, files in categories.items()
        )
        self.lbl_categories_breakdown.setText(f"Kategori terdeteksi: {breakdown_text}")

        # Render list of files in log browser
        html = "<div style='font-family: monospace; font-size: 11px; color: #a1a1aa;'>"
        html += "<b style='color: #00f0ff;'>DAFTAR FILE SIAP DIRAPIKAN:</b><br><br>"
        for cat, files in categories.items():
            html += f"<span style='color: #10b981; font-weight: bold;'>📂 {cat}/</span><br>"
            for f in files[:8]:
                html += f"&nbsp;&nbsp;• {f['name']} ({f['size_mb']} MB)<br>"
            if len(files) > 8:
                html += f"&nbsp;&nbsp;... dan {len(files) - 8} file lainnya.<br>"
            html += "<br>"
        html += "</div>"
        self.log_browser.setHtml(html)

    def _on_clean(self) -> None:
        target = self._get_current_target()
        self.btn_clean.setEnabled(False)
        self.btn_clean.setText("⏳ Merapikan...")

        result = clean_workspace(target, dry_run=False)
        self.btn_clean.setText("✨ RAPIKAN SEKARANG")

        if result.get("success"):
            moved = result.get("moved_count", 0)
            self.log_browser.append(
                f"<div style='color: #10b981; font-weight: bold; margin-top: 8px;'>"
                f"🎉 {result.get('message', 'Selesai merapikan!')} ({moved} file dipindahkan)."
                f"</div>"
            )
            self._on_scan()
        else:
            self.log_browser.append(
                f"<div style='color: #ef4444; font-weight: bold; margin-top: 8px;'>"
                f"❌ Terjadi kendala saat merapikan file."
                f"</div>"
            )

    def _on_open_folder(self) -> None:
        target = self._get_current_target()
        open_folder(target)
