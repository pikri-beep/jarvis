"""Settings and system diagnostics tab for JARVIS Dashboard."""

from pathlib import Path
from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
    QSlider,
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
        voice_layout = QGridLayout(voice_group)
        voice_layout.setVerticalSpacing(8)
        voice_layout.setHorizontalSpacing(12)

        self.chk_tts = QCheckBox("Aktifkan Keluaran Suara (Natural AI Voice)")
        self.chk_tts.setChecked(self.orchestrator.settings.tts_enabled)
        self.chk_tts.stateChanged.connect(self._on_tts_toggled)
        voice_layout.addWidget(self.chk_tts, 0, 0, 1, 2)

        self.lbl_voice_info = QLabel(f"STT: {self.orchestrator.settings.stt_model} | Wake: 'Hey Jarvis'")
        self.lbl_voice_info.setStyleSheet("color: #71717a; font-size: 12px;")
        voice_layout.addWidget(self.lbl_voice_info, 0, 2, 1, 2, Qt.AlignmentFlag.AlignRight)

        # Dropdown Model Suara Indonesia
        lbl_model = QLabel("Karakter Suara Indonesia:")
        lbl_model.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        voice_layout.addWidget(lbl_model, 1, 0)

        self.combo_voice = QComboBox()
        self.combo_voice.addItem("Ardi (Pria - Berwibawa)", "id-ID-ArdiNeural")
        self.combo_voice.addItem("Gadis (Wanita - Ramah)", "id-ID-GadisNeural")
        self.combo_voice.addItem("Piper (Offline Lokal)", "piper")

        current_voice = getattr(self.orchestrator.settings, "tts_voice_id", "id-ID-ArdiNeural")
        idx = self.combo_voice.findData(current_voice)
        if idx >= 0:
            self.combo_voice.setCurrentIndex(idx)
        self.combo_voice.currentIndexChanged.connect(self._on_voice_changed)
        voice_layout.addWidget(self.combo_voice, 1, 1)

        # Slider Kecepatan Suara
        lbl_speed = QLabel("Kecepatan Bicara:")
        lbl_speed.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        voice_layout.addWidget(lbl_speed, 1, 2)

        speed_box = QHBoxLayout()
        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(80, 150)
        curr_rate = int(getattr(self.orchestrator.settings, "tts_rate", 1.0) * 100)
        self.slider_speed.setValue(max(80, min(150, curr_rate)))

        self.lbl_speed_val = QLabel(f"{curr_rate / 100.0:.2f}x")
        self.lbl_speed_val.setStyleSheet("color: #e4e4e7; font-weight: 600; min-width: 40px;")

        self.slider_speed.valueChanged.connect(self._on_speed_changed)
        speed_box.addWidget(self.slider_speed)
        speed_box.addWidget(self.lbl_speed_val)
        voice_layout.addLayout(speed_box, 1, 3)

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
        object.__setattr__(self.orchestrator.settings, "tts_enabled", enabled)
        self.orchestrator.get_tts().enabled = enabled

    def _on_voice_changed(self, index: int) -> None:
        voice_id = self.combo_voice.currentData()
        object.__setattr__(self.orchestrator.settings, "tts_voice_id", voice_id)
        if voice_id == "piper":
            object.__setattr__(self.orchestrator.settings, "tts_engine", "piper")
        else:
            object.__setattr__(self.orchestrator.settings, "tts_engine", "hybrid")

    def _on_speed_changed(self, value: int) -> None:
        rate = value / 100.0
        self.lbl_speed_val.setText(f"{rate:.2f}x")
        object.__setattr__(self.orchestrator.settings, "tts_rate", rate)

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
