"""Claude Desktop Ultra-Minimalist Main Window for JARVIS.

Single-window architecture focused entirely on conversational interaction,
clean message streaming, floating input pill, and non-blocking background workers.
"""

from pathlib import Path
from typing import Optional
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.logger import setup_logger
from app.core.orchestrator import Orchestrator
from app.ui.chat_canvas import ChatCanvas, MessageBubble
from app.ui.dialogs import ProfileDialog
from app.ui.input_pill import InputPill
from app.ui.theme import DEEP_OBSIDIAN_THEME_QSS
from app.ui.workers import ProcessInputWorker, PttRecordWorker

logger = setup_logger("jarvis.ui.main_window")


class JarvisMainWindow(QMainWindow):
    """Minimalist single-window desktop interface for JARVIS."""

    # Thread-safe signals for wake word integration
    wake_detected_signal = pyqtSignal(float)
    wake_command_signal = pyqtSignal(str)
    wake_timeout_signal = pyqtSignal()

    def __init__(self, orchestrator: Optional[Orchestrator] = None):
        super().__init__()
        self.orchestrator = orchestrator or Orchestrator()
        self.setWindowTitle(f"{self.orchestrator.settings.jarvis_name.upper()} — Local AI Personal Assistant")
        self.resize(860, 680)
        self.setMinimumSize(640, 500)

        # Apply Window Icon
        assets_dir = Path(__file__).parent / "assets"
        icon_path = assets_dir / "jarvis.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Apply Deep Obsidian theme
        self.setStyleSheet(DEEP_OBSIDIAN_THEME_QSS)

        # State tracking
        self.current_worker: Optional[ProcessInputWorker] = None
        self.ptt_worker: Optional[PttRecordWorker] = None
        self.current_bubble: Optional[MessageBubble] = None
        self.is_wake_word_active = False

        # Connect internal Qt signals
        self.wake_detected_signal.connect(self._on_wake_detected)
        self.wake_command_signal.connect(self._on_wake_command_received)
        self.wake_timeout_signal.connect(self._on_wake_timeout)

        self._init_ui()

    def _init_ui(self) -> None:
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        # 1. Conversational Message Stream Canvas
        self.chat_canvas = ChatCanvas(self)
        self.chat_canvas.suggestion_clicked.connect(self._on_suggestion_clicked)

        # 2. Minimal Header Bar
        header = self._create_header_bar()
        layout.addWidget(header)
        layout.addWidget(self.chat_canvas, 1)

        # 3. Floating Input Pill
        self.input_pill = InputPill(self)
        self.input_pill.text_submitted.connect(self._submit_prompt)
        self.input_pill.mic_toggled.connect(self._toggle_ptt_recording)
        layout.addWidget(self.input_pill)

        # 4. Subtle Keyboard Hint
        hint_label = QLabel("Shift + Enter untuk baris baru • Tekan Enter untuk mengirim")
        hint_label.setObjectName("FooterHint")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint_label)

    def _create_header_bar(self) -> QFrame:
        header = QFrame()
        header.setObjectName("HeaderBar")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(4, 4, 4, 8)
        h_layout.setSpacing(12)

        # Assistant Logo / Brand
        logo_lbl = QLabel()
        png_path = Path(__file__).parent / "assets" / "jarvis.png"
        if png_path.exists():
            pix = QPixmap(str(png_path)).scaled(
                26, 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            logo_lbl.setPixmap(pix)
        else:
            logo_lbl.setText("🤖")
            logo_lbl.setStyleSheet("font-size: 18px;")
        h_layout.addWidget(logo_lbl)

        # Title & Subtitle
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        lbl_title = QLabel(self.orchestrator.settings.jarvis_name.upper())
        lbl_title.setObjectName("HeaderTitle")
        title_box.addWidget(lbl_title)

        lbl_sub = QLabel("Asisten AI Pribadi")
        lbl_sub.setObjectName("HeaderSubtitle")
        title_box.addWidget(lbl_sub)
        h_layout.addLayout(title_box)

        # Center Stretch
        h_layout.addStretch()

        # Status Pill
        self.status_pill = QLabel("● Siap")
        self.status_pill.setObjectName("StatusPill")
        self.status_pill.setStyleSheet(
            "background-color: #18181b; color: #10b981; border: 1px solid #27272a; "
            "border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 600;"
        )
        h_layout.addWidget(self.status_pill)

        # Right Action Buttons
        # Wake Word Toggle
        self.btn_wake = QPushButton("🎙️ Wake Word: OFF")
        self.btn_wake.setObjectName("HeaderIconButton")
        self.btn_wake.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_wake.setToolTip("Aktifkan pendengaran kontinu 'Hey Jarvis'")
        self.btn_wake.clicked.connect(self._toggle_wake_word)
        h_layout.addWidget(self.btn_wake)

        # Profile / Memory Button
        btn_profile = QPushButton("👤 Profil")
        btn_profile.setObjectName("HeaderIconButton")
        btn_profile.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_profile.setToolTip("Lihat identitas dan memori yang diingat JARVIS")
        btn_profile.clicked.connect(self._show_profile_dialog)
        h_layout.addWidget(btn_profile)

        # Clear Chat Button
        btn_clear = QPushButton("🗑️ Bersihkan")
        btn_clear.setObjectName("HeaderIconButton")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setToolTip("Bersihkan riwayat percakapan di layar")
        btn_clear.clicked.connect(self.chat_canvas.clear_chat)
        h_layout.addWidget(btn_clear)

        return header

    def _set_status(self, text: str, color: str = "#10b981", bg: str = "#18181b", border: str = "#27272a") -> None:
        """Sets status text and badge styling."""
        self.status_pill.setText(text)
        self.status_pill.setStyleSheet(
            f"background-color: {bg}; color: {color}; border: 1px solid {border}; "
            "border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 600;"
        )

    def _on_suggestion_clicked(self, text: str) -> None:
        self._submit_prompt(text)

    def _submit_prompt(self, text: str) -> None:
        """Submits user text to the processing pipeline."""
        clean_text = text.strip()
        if not clean_text:
            return

        # If a turn is already processing, avoid collision
        if self.current_worker and self.current_worker.isRunning():
            logger.warning("Submission blocked: previous turn still running.")
            return

        # 1. Add User bubble to canvas
        self.chat_canvas.add_user_message(clean_text)

        # 2. Add Assistant placeholder bubble
        self.current_bubble = self.chat_canvas.add_assistant_message("", "JARVIS")

        # 3. Update status & disable input
        self._set_status("🧠 Berpikir...", color="#a855f7", bg="#1f162b", border="#3b0764")
        self.input_pill.set_enabled_state(False)

        # 4. Pause wake word while generating/speaking
        if self.is_wake_word_active:
            try:
                self.orchestrator.get_wake_word().pause(release_device=True)
            except Exception as e:
                logger.debug("Wake pause exception: %s", e)

        # 5. Launch processing worker
        self.current_worker = ProcessInputWorker(self.orchestrator, clean_text, self)
        self.current_worker.token_received.connect(self._on_token_received)
        self.current_worker.speaking_started.connect(self._on_speaking_started)
        self.current_worker.speaking_finished.connect(self._on_speaking_finished)
        self.current_worker.turn_completed.connect(self._on_turn_completed)
        self.current_worker.error_occurred.connect(self._on_worker_error)
        self.current_worker.start()

    def _on_token_received(self, token: str) -> None:
        if self.current_bubble:
            self.current_bubble.append_text(token)
            self.chat_canvas.scroll_to_bottom()

    def _on_speaking_started(self) -> None:
        self._set_status("🔊 Berbicara...", color="#f59e0b", bg="#2a1f10", border="#78350f")

    def _on_speaking_finished(self) -> None:
        self._restore_standby_status()

    def _on_turn_completed(self, route_name: str, full_response: str, latency_s: float) -> None:
        self.input_pill.set_enabled_state(True)
        self._restore_standby_status()

        # Resume wake word if active
        if self.is_wake_word_active:
            try:
                self.orchestrator.get_wake_word().resume()
            except Exception as e:
                logger.debug("Wake resume exception: %s", e)

    def _on_worker_error(self, error_msg: str) -> None:
        if self.current_bubble:
            self.current_bubble.append_text(f"\n[Maaf, terjadi kesalahan: {error_msg}]")
            self.chat_canvas.scroll_to_bottom()

        self.input_pill.set_enabled_state(True)
        self._restore_standby_status()

        if self.is_wake_word_active:
            try:
                self.orchestrator.get_wake_word().resume()
            except Exception:
                pass

    def _restore_standby_status(self) -> None:
        if self.is_wake_word_active:
            self._set_status("● Standby (Wake: ON)", color="#10b981", bg="#14291e", border="#064e3b")
        else:
            self._set_status("● Siap", color="#10b981", bg="#18181b", border="#27272a")

    # --- PTT (Microphone) Handling ---
    def _toggle_ptt_recording(self) -> None:
        if self.ptt_worker and self.ptt_worker.isRunning():
            self._set_status("⏳ Mengolah Audio...", color="#38bdf8", bg="#132337", border="#0284c7")
            self.ptt_worker.stop_recording()
            return

        if self.is_wake_word_active:
            try:
                self.orchestrator.get_wake_word().pause(release_device=True)
            except Exception:
                pass

        self.ptt_worker = PttRecordWorker(self.orchestrator, max_duration=10.0, parent=self)
        self.ptt_worker.recording_started.connect(self._on_ptt_started)
        self.ptt_worker.recording_finished.connect(self._on_ptt_finished)
        self.ptt_worker.audio_level.connect(self._on_ptt_audio_level)
        self.ptt_worker.transcription_ready.connect(self._on_ptt_transcribed)
        self.ptt_worker.error_occurred.connect(self._on_ptt_error)
        self.ptt_worker.start()

    def _on_ptt_started(self) -> None:
        self.input_pill.set_recording(True)
        self._set_status("🔴 Merekam Suara...", color="#ef4444", bg="#2c1517", border="#991b1b")

    def _on_ptt_finished(self) -> None:
        self.input_pill.set_recording(False)
        self._set_status("⏳ Mengolah Audio...", color="#38bdf8", bg="#132337", border="#0284c7")

    def _on_ptt_audio_level(self, level: float) -> None:
        self.input_pill.set_audio_level(level)

    def _on_ptt_transcribed(self, text: str) -> None:
        self._submit_prompt(text)

    def _on_ptt_error(self, error_msg: str) -> None:
        self.input_pill.set_recording(False)
        self._restore_standby_status()
        if self.is_wake_word_active:
            try:
                self.orchestrator.get_wake_word().resume()
            except Exception:
                pass

    # --- Wake Word Handling ---
    def _toggle_wake_word(self) -> None:
        try:
            wake_detector = self.orchestrator.get_wake_word()
            if self.is_wake_word_active:
                wake_detector.stop()
                self.is_wake_word_active = False
                self.btn_wake.setText("🎙️ Wake Word: OFF")
                self.btn_wake.setStyleSheet("")
                self._restore_standby_status()
            else:
                wake_detector.on_wake_word = lambda score: self.wake_detected_signal.emit(score)
                wake_detector.on_command_captured = self._on_wake_command_captured
                wake_detector.on_silence_timeout = lambda: self.wake_timeout_signal.emit()

                wake_detector.start()
                self.is_wake_word_active = True
                self.btn_wake.setText("🎙️ Wake Word: ON")
                self.btn_wake.setStyleSheet(
                    "background-color: #064e3b; color: #34d399; border: 1px solid #10b981; font-weight: 600;"
                )
                self._restore_standby_status()
        except Exception as e:
            logger.error("Failed to toggle wake word: %s", e)
            self._set_status("⚠️ Wake Word Error", color="#ef4444", bg="#2c1517", border="#991b1b")

    def _on_wake_detected(self, score: float) -> None:
        self._set_status("🎙️ 'Hey Jarvis' Terdeteksi!", color="#38bdf8", bg="#132337", border="#0284c7")

    def _on_wake_timeout(self) -> None:
        self._restore_standby_status()

    def _on_wake_command_captured(self, audio_array) -> None:
        if audio_array is not None and len(audio_array) > 0:
            text, _ = self.orchestrator.transcribe_audio(audio_array)
            if text.strip():
                self.wake_command_signal.emit(text.strip())
            else:
                if self.is_wake_word_active:
                    try:
                        self.orchestrator.get_wake_word().resume()
                        self._restore_standby_status()
                    except Exception:
                        pass

    def _on_wake_command_received(self, text: str) -> None:
        self._submit_prompt(text)

    # --- Profile & Memory Dialog ---
    def _show_profile_dialog(self) -> None:
        memories = {}
        try:
            memories = self.orchestrator.memory.recall_all()
        except Exception as e:
            logger.warning("Could not recall memories: %s", e)

        dlg = ProfileDialog(memories=memories, parent=self)
        dlg.exec()

    # --- Close & Cleanup ---
    def closeEvent(self, event) -> None:
        """Ensures all background threads terminate cleanly upon closing."""
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.current_worker.wait(500)

        if self.ptt_worker and self.ptt_worker.isRunning():
            self.ptt_worker.stop_recording()
            self.ptt_worker.wait(500)

        if self.is_wake_word_active:
            try:
                wake = self.orchestrator.get_wake_word()
                if wake and wake.is_listening():
                    wake.stop()
            except Exception:
                pass

        event.accept()
