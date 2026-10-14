"""Chat and Voice interaction tab for JARVIS Dashboard."""

import datetime
from typing import Optional
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.orchestrator import Orchestrator
from app.ui.workers import PttRecordWorker, ProcessInputWorker


class ChatTab(QWidget):
    """Primary conversational and voice interaction view."""

    action_requested = pyqtSignal(str)
    wake_command_signal = pyqtSignal(str)
    wake_detected_signal = pyqtSignal(float)
    wake_timeout_signal = pyqtSignal()
    wake_state_signal = pyqtSignal(str)

    def __init__(self, orchestrator: Orchestrator, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.current_worker: Optional[ProcessInputWorker] = None
        self.ptt_worker: Optional[PttRecordWorker] = None
        self.is_wake_word_active = False

        # Connect thread-safe background signals
        self.wake_command_signal.connect(self.send_message)
        self.wake_detected_signal.connect(self._on_wake_detected)
        self.wake_timeout_signal.connect(self._on_wake_timeout)
        self.wake_state_signal.connect(self._on_wake_state)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Top Control / Status Bar
        top_bar = QHBoxLayout()

        self.status_badge = QLabel("● Standby")
        self.status_badge.setStyleSheet(
            "background-color: #27272a; color: #a1a1aa; border: 1px solid #3f3f46; "
            "border-radius: 12px; padding: 4px 12px; font-weight: 600; font-size: 12px;"
        )
        top_bar.addWidget(self.status_badge)

        self.lbl_active_model = QLabel(f"Engine: {self.orchestrator.settings.model}")
        self.lbl_active_model.setStyleSheet("color: #71717a; font-size: 12px;")
        top_bar.addWidget(self.lbl_active_model)

        top_bar.addStretch()

        # Wake Word Toggle Button
        self.btn_wake_toggle = QPushButton("Wake Word: OFF")
        self.btn_wake_toggle.setStyleSheet(
            "background-color: #202024; color: #a1a1aa; border: 1px solid #3f3f46; "
            "padding: 5px 12px; border-radius: 6px; font-size: 12px;"
        )
        self.btn_wake_toggle.clicked.connect(self._toggle_wake_word)
        top_bar.addWidget(self.btn_wake_toggle)

        # Clear Chat Button
        self.btn_clear = QPushButton("Bersihkan Chat")
        self.btn_clear.setStyleSheet(
            "background-color: transparent; color: #71717a; border: 1px solid #27272a; "
            "padding: 5px 12px; border-radius: 6px; font-size: 12px;"
        )
        self.btn_clear.clicked.connect(self._clear_chat)
        top_bar.addWidget(self.btn_clear)

        layout.addLayout(top_bar)

        # Chat History Log
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet(
            "background-color: #161618; border: 1px solid #27272a; "
            "border-radius: 8px; padding: 14px; font-size: 13px;"
        )
        layout.addWidget(self.chat_history, 1)

        # Quick Suggestion Chips
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(8)

        chips = [
            ("🌐 Buka Chrome", "buka chrome"),
            ("🎵 Buka Spotify", "buka spotify"),
            ("📸 Ambil Screenshot", "ambil screenshot"),
            ("☁️ Cuaca Besok", "bagaimana cuaca besok?"),
            ("📊 Status Sistem", "bagaimana status sistem kamu?"),
        ]

        for label, prompt in chips:
            btn_chip = QPushButton(label)
            btn_chip.setStyleSheet(
                "background-color: #1e1e24; color: #94a3b8; border: 1px solid #2e2e38; "
                "border-radius: 14px; padding: 4px 10px; font-size: 11px;"
            )
            btn_chip.clicked.connect(lambda checked, p=prompt: self.send_message(p))
            chips_layout.addWidget(btn_chip)

        chips_layout.addStretch()
        layout.addLayout(chips_layout)

        # Bottom Input Area
        input_container = QFrame()
        input_container.setStyleSheet(
            "background-color: #1a1a1e; border: 1px solid #2e2e38; "
            "border-radius: 8px; padding: 4px;"
        )
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(6, 6, 6, 6)
        input_layout.setSpacing(8)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Ketik perintah atau tanyakan apa saja ke JARVIS (tekan Enter untuk kirim)...")
        self.input_edit.setStyleSheet(
            "background-color: transparent; border: none; color: #f4f4f5; "
            "font-size: 13px; padding: 4px 8px;"
        )
        self.input_edit.returnPressed.connect(self._on_send_clicked)
        input_layout.addWidget(self.input_edit, 1)

        # Audio Volume Level Meter (Visible during PTT voice recording)
        self.audio_meter = QProgressBar()
        self.audio_meter.setRange(0, 100)
        self.audio_meter.setValue(0)
        self.audio_meter.setTextVisible(False)
        self.audio_meter.setFixedWidth(70)
        self.audio_meter.setFixedHeight(14)
        self.audio_meter.setStyleSheet(
            "QProgressBar { background-color: #27272a; border-radius: 4px; border: none; } "
            "QProgressBar::chunk { background-color: #10b981; border-radius: 4px; }"
        )
        self.audio_meter.setVisible(False)
        input_layout.addWidget(self.audio_meter)

        # Push to Talk Button
        self.btn_ptt = QPushButton("🎙️ Suara (PTT)")
        self.btn_ptt.setStyleSheet(
            "background-color: #27272a; color: #38bdf8; border: 1px solid #38bdf8; "
            "font-weight: 600; padding: 6px 14px; border-radius: 6px;"
        )
        self.btn_ptt.clicked.connect(self._toggle_ptt)
        input_layout.addWidget(self.btn_ptt)

        # Send Button
        self.btn_send = QPushButton("Kirim")
        self.btn_send.setProperty("class", "primary")
        self.btn_send.clicked.connect(self._on_send_clicked)
        input_layout.addWidget(self.btn_send)

        layout.addWidget(input_container)

        # Welcome message
        self._append_system_banner()

    def _append_system_banner(self) -> None:
        name = self.orchestrator.settings.jarvis_name.upper()
        welcome_html = f"""
        <div style="margin-bottom: 12px; padding: 10px; background-color: #1e1e24; border-radius: 6px; border-left: 3px solid #38bdf8;">
            <b style="color: #38bdf8;">{name} Siap Membantu</b><br/>
            <span style="color: #94a3b8; font-size: 12px;">
                Asisten komputer lokal Anda aktif. Anda dapat mengetik perintah, menekan tombol Suara (PTT), atau mengaktifkan Wake Word ('Hey Jarvis').
            </span>
        </div>
        """
        self.chat_history.append(welcome_html)

    def _set_status(self, text: str, color: str = "#a1a1aa", bg: str = "#27272a") -> None:
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(
            f"background-color: {bg}; color: {color}; border: 1px solid {color}; "
            "border-radius: 12px; padding: 4px 12px; font-weight: 600; font-size: 12px;"
        )

    def _clear_chat(self) -> None:
        self.chat_history.clear()
        self._append_system_banner()

    def _on_send_clicked(self) -> None:
        text = self.input_edit.text().strip()
        if text:
            self.input_edit.clear()
            self.send_message(text)

    def send_message(self, text: str) -> None:
        """Sends a message to the orchestrator pipeline."""
        if not text:
            return

        now_str = datetime.datetime.now().strftime("%H:%M")
        user_html = f"""
        <div style="margin: 8px 0; text-align: right;">
            <span style="font-size: 11px; color: #71717a; margin-right: 6px;">{now_str}</span>
            <span style="display: inline-block; background-color: #27272a; color: #f4f4f5; padding: 8px 14px; border-radius: 12px; max-width: 80%; text-align: left; border: 1px solid #3f3f46;">
                {text}
            </span>
        </div>
        """
        self.chat_history.append(user_html)

        self._set_status("⚙️ Memproses...", color="#f59e0b", bg="#2a2418")
        self.btn_send.setEnabled(False)

        # Response container header
        jarvis_name = self.orchestrator.settings.jarvis_name
        jarvis_header_html = f"""
        <div style="margin-top: 10px; margin-bottom: 2px; text-align: left;">
            <b style="color: #38bdf8; font-size: 12px;">{jarvis_name}</b>
            <span style="font-size: 11px; color: #71717a; margin-left: 6px;">{now_str}</span>
        </div>
        """
        self.chat_history.append(jarvis_header_html)

        # Spawn worker
        self.current_worker = ProcessInputWorker(self.orchestrator, text, parent=self)
        self.current_worker.token_received.connect(self._on_token_received)
        self.current_worker.speaking_started.connect(self._on_speaking_started)
        self.current_worker.speaking_finished.connect(self._on_speaking_finished)
        self.current_worker.turn_completed.connect(self._on_turn_completed)
        self.current_worker.error_occurred.connect(self._on_worker_error)
        self.current_worker.start()

    def _on_token_received(self, token: str) -> None:
        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()

    def _on_speaking_started(self) -> None:
        self._set_status("🔊 JARVIS Berbicara...", color="#10b981", bg="#14291e")
        if self.is_wake_word_active:
            try:
                wake_detector = self.orchestrator.get_wake_word()
                wake_detector.pause(release_device=False)
            except Exception:
                pass

    def _on_speaking_finished(self) -> None:
        if self.is_wake_word_active:
            try:
                wake_detector = self.orchestrator.get_wake_word()
                wake_detector.resume()
                self._set_status("● Standby (Wake Word: ON)", color="#10b981", bg="#14291e")
            except Exception:
                self._set_status("● Standby", color="#a1a1aa", bg="#27272a")
        else:
            self._set_status("● Standby", color="#a1a1aa", bg="#27272a")

    def _on_turn_completed(self, route_name: str, full_response: str, latency: float) -> None:
        metadata_html = f"""
        <div style="margin-top: 4px; margin-bottom: 10px; font-size: 11px; color: #71717a;">
            <span style="background-color: #27272a; padding: 2px 7px; border-radius: 4px; color: #38bdf8; font-weight: 500;">{route_name}</span> &bull; {latency:.2f}s
        </div>
        """
        self.chat_history.append(metadata_html)
        self.btn_send.setEnabled(True)

        if self.is_wake_word_active:
            try:
                wake_detector = self.orchestrator.get_wake_word()
                wake_detector.resume()
                self._set_status("● Standby (Wake Word: ON)", color="#10b981", bg="#14291e")
            except Exception:
                self._set_status("● Standby", color="#a1a1aa", bg="#27272a")
        else:
            self._set_status("● Standby", color="#a1a1aa", bg="#27272a")

    def _on_worker_error(self, err_msg: str) -> None:
        err_html = f"""
        <div style="color: #ef4444; background-color: #2b1818; padding: 8px 12px; border-radius: 6px; margin: 6px 0;">
            ⚠️ Terjadi kesalahan: {err_msg}
        </div>
        """
        self.chat_history.append(err_html)
        self.btn_send.setEnabled(True)

        if self.is_wake_word_active:
            try:
                self.orchestrator.get_wake_word().resume()
                self._set_status("● Standby (Wake Word: ON)", color="#10b981", bg="#14291e")
            except Exception:
                self._set_status("● Standby", color="#a1a1aa", bg="#27272a")
        else:
            self._set_status("● Standby", color="#a1a1aa", bg="#27272a")

    def _toggle_ptt(self) -> None:
        if self.ptt_worker and self.ptt_worker.isRunning():
            self.ptt_worker.stop_recording()
            self._set_status("⚙️ Mentranskripsikan suara...", color="#38bdf8", bg="#182430")
            self.btn_ptt.setText("⏳ Memproses...")
            self.btn_ptt.setStyleSheet(
                "background-color: #27272a; color: #a1a1aa; border: 1px solid #52525b; "
                "font-weight: 600; padding: 6px 14px; border-radius: 6px;"
            )
            self.audio_meter.setVisible(False)
        else:
            # If wake word is active, release microphone hardware first so PTT gets clean access
            if self.is_wake_word_active:
                try:
                    self.orchestrator.get_wake_word().pause(release_device=True)
                except Exception:
                    pass

            self.btn_ptt.setText("🔴 Selesai (Klik)")
            self.btn_ptt.setStyleSheet(
                "background-color: #dc2626; color: white; border: 1px solid #ef4444; "
                "font-weight: 600; padding: 6px 14px; border-radius: 6px;"
            )
            self._set_status("🎙️ Merekam Suara (Silakan Bicara)...", color="#ef4444", bg="#2b1818")
            self.audio_meter.setValue(0)
            self.audio_meter.setVisible(True)

            self.ptt_worker = PttRecordWorker(self.orchestrator, max_duration=8.0, parent=self)
            self.ptt_worker.transcription_ready.connect(self._on_ptt_transcribed)
            self.ptt_worker.audio_level.connect(self._on_ptt_level)
            self.ptt_worker.error_occurred.connect(self._on_ptt_error)
            self.ptt_worker.start()

    def _on_ptt_level(self, level: float) -> None:
        self.audio_meter.setValue(int(level * 100))

    def _on_ptt_transcribed(self, text: str) -> None:
        self.audio_meter.setVisible(False)
        self.btn_ptt.setText("🎙️ Suara (PTT)")
        self.btn_ptt.setStyleSheet(
            "background-color: #27272a; color: #38bdf8; border: 1px solid #38bdf8; "
            "font-weight: 600; padding: 6px 14px; border-radius: 6px;"
        )
        self.send_message(text)

    def _restore_standby_status(self) -> None:
        if self.is_wake_word_active:
            try:
                self.orchestrator.get_wake_word().resume()
                self._set_status("● Standby (Wake Word: ON)", color="#10b981", bg="#14291e")
            except Exception:
                self._set_status("● Standby", color="#a1a1aa", bg="#27272a")
        else:
            self._set_status("● Standby", color="#a1a1aa", bg="#27272a")

    def _on_ptt_error(self, err_msg: str) -> None:
        self.audio_meter.setVisible(False)
        self.btn_ptt.setText("🎙️ Suara (PTT)")
        self.btn_ptt.setStyleSheet(
            "background-color: #27272a; color: #38bdf8; border: 1px solid #38bdf8; "
            "font-weight: 600; padding: 6px 14px; border-radius: 6px;"
        )
        # Display warning on status badge rather than cluttering chat transcript
        self._set_status(f"⚠️ {err_msg}", color="#f59e0b", bg="#262014")
        QTimer.singleShot(3500, self._restore_standby_status)

    def _toggle_wake_word(self) -> None:
        try:
            wake_detector = self.orchestrator.get_wake_word()
            if self.is_wake_word_active:
                wake_detector.stop()
                self.is_wake_word_active = False
                self.btn_wake_toggle.setText("Wake Word: OFF")
                self.btn_wake_toggle.setStyleSheet(
                    "background-color: #202024; color: #a1a1aa; border: 1px solid #3f3f46; "
                    "padding: 5px 12px; border-radius: 6px; font-size: 12px;"
                )
                self._set_status("● Standby", color="#a1a1aa", bg="#27272a")
            else:
                wake_detector.on_wake_word = lambda score: self.wake_detected_signal.emit(score)
                wake_detector.on_command_captured = self._on_wake_command_captured
                wake_detector.on_silence_timeout = lambda: self.wake_timeout_signal.emit()
                wake_detector.on_state_change = lambda old, new: self.wake_state_signal.emit(str(new.value))

                wake_detector.start()
                self.is_wake_word_active = True
                self.btn_wake_toggle.setText("Wake Word: ON (Hey Jarvis)")
                self.btn_wake_toggle.setStyleSheet(
                    "background-color: #059669; color: white; border: 1px solid #10b981; "
                    "font-weight: 600; padding: 5px 12px; border-radius: 6px; font-size: 12px;"
                )
                self._set_status("● Standby (Wake Word: ON)", color="#10b981", bg="#14291e")
        except Exception as e:
            self._on_worker_error(f"Gagal mengaktifkan Wake Word: {e}")

    def _on_wake_detected(self, score: float) -> None:
        self._set_status("🎙️ Mendengarkan 'Hey Jarvis'...", color="#38bdf8", bg="#182430")

    def _on_wake_timeout(self) -> None:
        if self.is_wake_word_active:
            self._set_status("● Standby (Wake Word: ON)", color="#10b981", bg="#14291e")

    def _on_wake_state(self, state_str: str) -> None:
        pass

    def _on_wake_command_captured(self, audio_array) -> None:
        if audio_array is not None and len(audio_array) > 0:
            text, _ = self.orchestrator.transcribe_audio(audio_array)
            if text.strip():
                self.wake_command_signal.emit(text.strip())
            else:
                if self.is_wake_word_active:
                    try:
                        self.orchestrator.get_wake_word().resume()
                        self._set_status("● Standby (Wake Word: ON)", color="#10b981", bg="#14291e")
                    except Exception:
                        pass
