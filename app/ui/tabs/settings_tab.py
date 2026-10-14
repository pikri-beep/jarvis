"""Settings and system diagnostics tab for JARVIS Dashboard."""

from pathlib import Path
from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.orchestrator import Orchestrator


class SettingsTab(QWidget):
    """System configuration, resource telemetry, and diagnostic logs."""

    def __init__(self, orchestrator: Orchestrator, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self._init_ui()
        self.refresh_diagnostics()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Telemetry & Hardware Gauges
        hw_group = QGroupBox("Pemantauan Perangkat Keras (Laptop Acer Aspire A514-56P)")
        hw_layout = QGridLayout(hw_group)
        hw_layout.setSpacing(10)

        hw_layout.addWidget(QLabel("Beban CPU (13th Gen Intel Core i5):"), 0, 0)
        self.bar_cpu = QProgressBar()
        self.bar_cpu.setRange(0, 100)
        self.bar_cpu.setValue(0)
        hw_layout.addWidget(self.bar_cpu, 0, 1)

        self.lbl_cpu_val = QLabel("0%")
        self.lbl_cpu_val.setStyleSheet("font-weight: 600; color: #38bdf8;")
        hw_layout.addWidget(self.lbl_cpu_val, 0, 2)

        hw_layout.addWidget(QLabel("Penggunaan Memori RAM (16 GB):"), 1, 0)
        self.bar_ram = QProgressBar()
        self.bar_ram.setRange(0, 100)
        self.bar_ram.setValue(0)
        hw_layout.addWidget(self.bar_ram, 1, 1)

        self.lbl_ram_val = QLabel("0 GB / 16 GB")
        self.lbl_ram_val.setStyleSheet("font-weight: 600; color: #38bdf8;")
        hw_layout.addWidget(self.lbl_ram_val, 1, 2)

        layout.addWidget(hw_group)

        # Ollama Model Configuration
        ollama_group = QGroupBox("Konfigurasi Mesin AI Lokal (Ollama)")
        ollama_layout = QGridLayout(ollama_group)
        ollama_layout.setSpacing(10)

        ollama_layout.addWidget(QLabel("Ollama Server URL:"), 0, 0)
        self.input_url = QLineEdit(self.orchestrator.settings.ollama_url)
        ollama_layout.addWidget(self.input_url, 0, 1)

        self.btn_test_conn = QPushButton("Uji Koneksi")
        self.btn_test_conn.clicked.connect(self._test_ollama_connection)
        ollama_layout.addWidget(self.btn_test_conn, 0, 2)

        ollama_layout.addWidget(QLabel("Model LLM:"), 1, 0)
        self.input_model = QLineEdit(self.orchestrator.settings.model)
        ollama_layout.addWidget(self.input_model, 1, 1)

        self.lbl_ollama_status = QLabel("● Memeriksa...")
        self.lbl_ollama_status.setStyleSheet("color: #a1a1aa; font-weight: 600;")
        ollama_layout.addWidget(self.lbl_ollama_status, 1, 2)

        layout.addWidget(ollama_group)

        # Voice & Speech Controls
        voice_group = QGroupBox("Pengaturan Suara & Audio")
        voice_layout = QHBoxLayout(voice_group)

        self.chk_tts = QCheckBox("Aktifkan Keluaran Suara (TTS Piper)")
        self.chk_tts.setChecked(self.orchestrator.settings.tts_enabled)
        self.chk_tts.stateChanged.connect(self._on_tts_toggled)
        voice_layout.addWidget(self.chk_tts)

        self.lbl_voice_info = QLabel(f"STT: {self.orchestrator.settings.stt_model} | Wake: 'Hey Jarvis'")
        self.lbl_voice_info.setStyleSheet("color: #71717a; font-size: 12px;")
        voice_layout.addStretch()
        voice_layout.addWidget(self.lbl_voice_info)

        layout.addWidget(voice_group)

        # Live Log Viewer
        log_header = QHBoxLayout()
        lbl_log = QLabel("Log Diagnostik Sistem (logs/jarvis.log)")
        lbl_log.setStyleSheet("font-weight: 600; color: #e4e4e7;")
        log_header.addWidget(lbl_log)
        log_header.addStretch()

        self.btn_refresh_log = QPushButton("Muat Ulang Log")
        self.btn_refresh_log.clicked.connect(self._load_log_file)
        log_header.addWidget(self.btn_refresh_log)

        layout.addLayout(log_header)

        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet(
            "background-color: #141416; color: #a1a1aa; font-family: Consolas, monospace; "
            "font-size: 11px; border: 1px solid #27272a; border-radius: 6px;"
        )
        layout.addWidget(self.txt_log, 1)

        self._load_log_file()

    def update_hardware_metrics(self, payload: dict) -> None:
        """Slot called periodically by SystemMetricsWorker."""
        cpu = int(payload.get("cpu_percent", 0))
        ram_pct = int(payload.get("ram_percent", 0))
        ram_used = payload.get("ram_used_gb", 0)
        ram_total = payload.get("ram_total_gb", 16)

        self.bar_cpu.setValue(cpu)
        self.lbl_cpu_val.setText(f"{cpu}%")

        self.bar_ram.setValue(ram_pct)
        self.lbl_ram_val.setText(f"{ram_used} GB / {ram_total} GB ({ram_pct}%)")

        ollama_connected = payload.get("ollama_connected", False)
        model_ready = payload.get("model_ready", False)
        if ollama_connected and model_ready:
            self.lbl_ollama_status.setText("● Terhubung & Tersedia")
            self.lbl_ollama_status.setStyleSheet("color: #10b981; font-weight: 600;")
        elif ollama_connected:
            self.lbl_ollama_status.setText("● Terhubung (Model Belum Terinstall)")
            self.lbl_ollama_status.setStyleSheet("color: #f59e0b; font-weight: 600;")
        else:
            self.lbl_ollama_status.setText("● Offline / Tidak Terdeteksi")
            self.lbl_ollama_status.setStyleSheet("color: #ef4444; font-weight: 600;")

    def refresh_diagnostics(self) -> None:
        status = self.orchestrator.get_system_status()
        self._load_log_file()

    def _test_ollama_connection(self) -> None:
        self.btn_test_conn.setEnabled(False)
        self.btn_test_conn.setText("Menguji...")
        try:
            status = self.orchestrator.get_system_status()
            if status["ollama_connected"]:
                if status["model_ready"]:
                    QMessageBox.information(
                        self,
                        "Koneksi Berhasil",
                        f"Server Ollama terhubung dan model '{status['model']}' siap digunakan!",
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Model Belum Ada",
                        f"Ollama terhubung, namun model '{status['model']}' belum ditemukan.\n"
                        f"Jalankan: ollama pull {status['model']}",
                    )
            else:
                QMessageBox.critical(
                    self,
                    "Koneksi Gagal",
                    f"Tidak dapat terhubung ke Ollama di {status['ollama_url']}.\n"
                    "Pastikan aplikasi Ollama sedang berjalan di latar belakang Windows.",
                )
        finally:
            self.btn_test_conn.setEnabled(True)
            self.btn_test_conn.setText("Uji Koneksi")

    def _on_tts_toggled(self, state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        self.orchestrator.settings.tts_enabled = enabled
        self.orchestrator.get_tts().enabled = enabled

    def _load_log_file(self) -> None:
        log_path = Path(__file__).resolve().parent.parent.parent.parent / "logs" / "jarvis.log"
        if log_path.exists():
            try:
                # Read last 100 lines
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                    recent = lines[-100:]
                    self.txt_log.setPlainText("".join(recent))
                    self.txt_log.verticalScrollBar().setValue(
                        self.txt_log.verticalScrollBar().maximum()
                    )
            except Exception as e:
                self.txt_log.setPlainText(f"Gagal membaca file log: {e}")
        else:
            self.txt_log.setPlainText("File log belum tersedia.")
