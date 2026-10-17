"""Modern Hacker Terminal HUD Main Window for JARVIS.

Features:
- Windows Terminal / PowerShell aesthetic (Cascadia Code / JetBrains Mono dark theme).
- 4 Power Tabs: `>_ CONSOLE`, `📝 TODO & NOTES`, `🧹 JANITOR`, `⚡ PROACTIVE STREAM`.
- Top Telemetry Bar with Live CPU/RAM metrics and Instant Engine Switcher (Groq Turbo <-> Ollama Offline).
- Windows Native Global Hotkey (Win+Alt+J) and System Tray daemon support.
"""

import os
from pathlib import Path
from typing import Optional

import psutil
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QKeyEvent, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.hotkey import GlobalHotkeyThread
from app.core.logger import setup_logger
from app.core.orchestrator import Orchestrator
from app.ui.chat_canvas import ChatCanvas, MessageBubble
from app.ui.dialogs import ProfileDialog
from app.ui.input_pill import InputPill
from app.ui.tabs.terminal_console_tab import TerminalConsoleTab
from app.ui.tabs.terminal_janitor_tab import TerminalJanitorTab
from app.ui.tabs.terminal_proactive_tab import TerminalProactiveTab
from app.ui.tabs.terminal_todo_tab import TerminalTodoTab
from app.ui.terminal_theme import TERMINAL_THEME_QSS
from app.ui.workers import ProcessInputWorker, ProactiveWorker, PttRecordWorker

logger = setup_logger("jarvis.ui.main_window")


class JarvisMainWindow(QMainWindow):
    """Modern Hacker Terminal HUD desktop interface for JARVIS."""

    wake_detected_signal = pyqtSignal(float)
    wake_command_signal = pyqtSignal(str)
    wake_timeout_signal = pyqtSignal()

    def __init__(self, orchestrator: Optional[Orchestrator] = None):
        super().__init__()
        self.orchestrator = orchestrator or Orchestrator()
        self.setWindowTitle("JARVIS // TERMINAL HUD v2.5")
        self.resize(920, 660)
        self.setMinimumSize(700, 520)

        # Apply Window Icon
        assets_dir = Path(__file__).parent / "assets"
        icon_path = assets_dir / "jarvis.ico"
        self._app_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        if not self._app_icon.isNull():
            self.setWindowIcon(self._app_icon)

        # Apply Terminal Theme
        self.setStyleSheet(TERMINAL_THEME_QSS)

        # State tracking
        self.current_engine_provider = getattr(self.orchestrator.settings, "interpreter_provider", "groq").lower()
        self.current_worker: Optional[ProcessInputWorker] = None
        self.ptt_worker: Optional[PttRecordWorker] = None
        self.proactive_worker: Optional[ProactiveWorker] = None
        self.current_bubble: Optional[MessageBubble] = None
        self.is_wake_word_active = False

        # Connect internal Qt signals
        self.wake_detected_signal.connect(self._on_wake_detected)
        self.wake_command_signal.connect(self._on_wake_command_received)
        self.wake_timeout_signal.connect(self._on_wake_timeout)

        # Compatibility widgets (required by existing test suite and legacy abstractions)
        self.chat_canvas = ChatCanvas(self)
        self.chat_canvas.hide()
        self.input_pill = InputPill(self)
        self.input_pill.hide()

        # Start background Remote IPC Gateway for PocketDesk Remote mobile connection
        try:
            from app.core.remote_gateway import start_remote_gateway
            start_remote_gateway(self.orchestrator)
        except Exception as e:
            logger.warning("Could not start remote gateway: %s", e)

        self._init_ui()
        self._init_system_tray()
        self._init_global_hotkey()
        self._init_telemetry_timer()

    def _init_ui(self) -> None:
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Header Bar
        header = self._create_header_bar()
        root_layout.addWidget(header)

        # 2. Main Tab Widget (Hacker Tabs)
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)

        # Tab 1: Terminal Console
        self.console_tab = TerminalConsoleTab(self)
        self.console_tab.command_submitted.connect(self._submit_prompt)
        self.console_tab.mic_toggled.connect(self._toggle_ptt_recording)
        self.console_tab.stop_speech_requested.connect(self._stop_current_speech_or_generation)
        self.tab_widget.addTab(self.console_tab, ">_ CONSOLE")

        # Tab 2: Todo & Notes
        self.todo_tab = TerminalTodoTab(parent=self)
        self.tab_widget.addTab(self.todo_tab, "📝 TODO & NOTES")

        # Tab 3: Janitor
        self.janitor_tab = TerminalJanitorTab(self)
        self.tab_widget.addTab(self.janitor_tab, "🧹 JANITOR")

        # Tab 4: Proactive Stream (Omi Style)
        self.proactive_tab = TerminalProactiveTab(self)
        self.tab_widget.addTab(self.proactive_tab, "⚡ PROACTIVE STREAM")

        root_layout.addWidget(self.tab_widget, 1)

        # 3. Footer Status Bar
        footer = self._create_footer_bar()
        root_layout.addWidget(footer)

    def _create_header_bar(self) -> QFrame:
        header = QFrame()
        header.setObjectName("TerminalHeader")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 6, 12, 6)
        h_layout.setSpacing(10)

        # Brand / Logo
        lbl_logo = QLabel("⚡")
        lbl_logo.setStyleSheet("font-size: 16px; color: #00f0ff;")
        h_layout.addWidget(lbl_logo)

        # Title block
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        lbl_title = QLabel("JARVIS // TERMINAL HUD")
        lbl_title.setObjectName("TerminalTitle")
        title_box.addWidget(lbl_title)

        lbl_sub = QLabel("Autonomous & Proactive Personal Assistant")
        lbl_sub.setObjectName("TerminalSubtitle")
        title_box.addWidget(lbl_sub)
        h_layout.addLayout(title_box)

        h_layout.addStretch()

        # Telemetry Pill (CPU & RAM)
        self.telemetry_pill = QLabel("💻 CPU: --% | RAM: --%")
        self.telemetry_pill.setObjectName("TelemetryPill")
        h_layout.addWidget(self.telemetry_pill)

        # Engine Switcher Button (Groq Turbo <-> Ollama Offline)
        self.btn_engine = QPushButton("⚡ TURBO: GROQ")
        self.btn_engine.setObjectName("HeaderPillButton")
        self.btn_engine.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_engine.setToolTip("Klik untuk beralih antara Groq Cloud Turbo (<300ms) dan Ollama Offline Lokal")
        self.btn_engine.clicked.connect(self._toggle_engine)
        self._update_engine_button_style()
        h_layout.addWidget(self.btn_engine)

        # Wake Word Toggle Button
        self.btn_wake = QPushButton("🎙️ WAKE: OFF")
        self.btn_wake.setObjectName("HeaderPillButton")
        self.btn_wake.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_wake.setToolTip("Aktifkan pendengaran kontinu 'Hey Jarvis'")
        self.btn_wake.clicked.connect(self._toggle_wake_word)
        h_layout.addWidget(self.btn_wake)

        # Profile / Memory Button
        btn_profile = QPushButton("👤 Profil")
        btn_profile.setObjectName("HeaderPillButton")
        btn_profile.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_profile.setToolTip("Lihat data memori yang diingat JARVIS")
        btn_profile.clicked.connect(self._show_profile_dialog)
        h_layout.addWidget(btn_profile)

        # Minimize to Tray Button
        btn_tray = QPushButton("_ Tray")
        btn_tray.setObjectName("HeaderPillButton")
        btn_tray.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_tray.setToolTip("Sembunyikan ke System Tray (Tetap aktif via Win+Alt+J)")
        btn_tray.clicked.connect(self.hide)
        h_layout.addWidget(btn_tray)

        return header

    def _create_footer_bar(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("TerminalFooter")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(12, 4, 12, 4)

        # Status Pill label
        self.status_pill = QLabel("● Siap")
        self.status_pill.setObjectName("FooterStatusLabel")
        f_layout.addWidget(self.status_pill)

        f_layout.addStretch()

        hint_lbl = QLabel("Shortcut Global: Win + Alt + J (atau Ctrl + Shift + J) • Shift+Enter baris baru")
        hint_lbl.setObjectName("FooterStatusLabel")
        f_layout.addWidget(hint_lbl)

        return footer

    # --- Telemetry & System Vitals ---
    def _init_telemetry_timer(self) -> None:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            self.telemetry_timer = None
            return

        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self._update_telemetry)
        self.telemetry_timer.start(3000)
        self._update_telemetry()

    def _update_telemetry(self) -> None:
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            self.telemetry_pill.setText(f"💻 CPU: {cpu:.0f}% | RAM: {ram:.0f}%")
        except Exception:
            pass

    # --- System Tray Integration ---
    def _init_system_tray(self) -> None:
        if os.environ.get("PYTEST_CURRENT_TEST") or not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = None
            return

        self.tray_icon = QSystemTrayIcon(self)
        if not self._app_icon.isNull():
            self.tray_icon.setIcon(self._app_icon)

        tray_menu = QMenu()
        act_show = QAction("📌 Buka Terminal HUD", self)
        act_show.triggered.connect(self.show_and_activate)
        tray_menu.addAction(act_show)

        act_engine = QAction("⚡ Toggle Engine (Groq/Ollama)", self)
        act_engine.triggered.connect(self._toggle_engine)
        tray_menu.addAction(act_engine)

        act_wake = QAction("🎙️ Toggle Wake Word ('Hey Jarvis')", self)
        act_wake.triggered.connect(self._toggle_wake_word)
        tray_menu.addAction(act_wake)

        act_clean = QAction("🧹 Rapikan Downloads Sekarang", self)
        act_clean.triggered.connect(self._quick_clean_downloads)
        tray_menu.addAction(act_clean)

        tray_menu.addSeparator()
        act_exit = QAction("❌ Keluar Sepenuhnya", self)
        act_exit.triggered.connect(self._quit_application)
        tray_menu.addAction(act_exit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.toggle_visibility()

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.show_and_activate()

    def show_and_activate(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()
        if hasattr(self, "console_tab") and self.console_tab:
            self.console_tab.input_edit.setFocus()

    def _quick_clean_downloads(self) -> None:
        from app.tools.janitor import clean_workspace
        res = clean_workspace("downloads", dry_run=False)
        moved = res.get("moved_count", 0)
        if self.tray_icon:
            self.tray_icon.showMessage(
                "Workspace Janitor",
                f"Berhasil merapikan {moved} file di Downloads.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )

    def _quit_application(self) -> None:
        self._cleanup_workers()
        self.close()
        QApplication.quit()

    # --- Windows Native Global Hotkey ---
    def _init_global_hotkey(self) -> None:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            self.hotkey_thread = None
            return

        self.hotkey_thread = GlobalHotkeyThread(self)
        self.hotkey_thread.hotkey_triggered.connect(self.toggle_visibility)
        self.hotkey_thread.start()

    # --- Engine Switcher (Groq Turbo <-> Ollama Offline) ---
    def _toggle_engine(self) -> None:
        curr_provider = getattr(self, "current_engine_provider", "groq").lower()
        new_provider = "ollama" if curr_provider == "groq" else "groq"
        self.current_engine_provider = new_provider

        if hasattr(self.orchestrator, "action_interpreter") and self.orchestrator.action_interpreter:
            self.orchestrator.action_interpreter.provider = new_provider

        self._update_engine_button_style()
        if hasattr(self, "proactive_tab") and self.proactive_tab:
            self.proactive_tab.log_event("ENGINE", f"Provider beralih ke: {new_provider.upper()}")

    def _update_engine_button_style(self) -> None:
        curr_provider = getattr(self, "current_engine_provider", "groq").lower()
        if curr_provider == "groq":
            self.btn_engine.setText("⚡ TURBO: GROQ")
            self.btn_engine.setStyleSheet(
                "background-color: #0c4a6e; color: #38bdf8; border: 1px solid #0284c7; font-weight: 700;"
            )
        else:
            self.btn_engine.setText("🔒 OFFLINE: OLLAMA")
            self.btn_engine.setStyleSheet(
                "background-color: #27272a; color: #f59e0b; border: 1px solid #78350f; font-weight: 700;"
            )

    # --- Background Proactive Worker ---
    def start_proactive_worker(self) -> None:
        if not self.proactive_worker and getattr(self.orchestrator.settings, "proactive_enabled", True):
            self.proactive_worker = ProactiveWorker(self.orchestrator, self)
            self.proactive_worker.proactive_triggered.connect(self._on_proactive_triggered)
            self.proactive_worker.start()

    def stop_proactive_worker(self) -> None:
        if self.proactive_worker and self.proactive_worker.isRunning():
            self.proactive_worker.stop()
            self.proactive_worker.wait(500)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.start_proactive_worker()

    def _set_status(self, text: str, color: str = "#10b981", bg: str = "#18181b", border: str = "#27272a") -> None:
        self.status_pill.setText(text)
        self.status_pill.setStyleSheet(f"color: {color}; font-weight: 600; font-size: 11px;")

    def _restore_standby_status(self) -> None:
        if self.is_wake_word_active:
            self._set_status("● Standby (Wake: ON)", color="#10b981")
        else:
            self._set_status("● Siap", color="#10b981")

    # --- Submitting User Prompts ---
    def _submit_prompt(self, text: str) -> None:
        clean_text = text.strip()
        if not clean_text:
            return

        if self.current_worker and self.current_worker.isRunning():
            logger.info("New prompt submitted while previous turn was active. Instantly halting previous turn & speech.")
            self._stop_current_speech_or_generation()
            self.current_worker.wait(150)

        # 1. Update Console tab
        self.console_tab.append_user_message(clean_text)
        self.console_tab.start_assistant_message()

        # Update compatibility canvas
        self.chat_canvas.add_user_message(clean_text)
        self.current_bubble = self.chat_canvas.add_assistant_message("", "JARVIS")

        # 2. Update status & disable input
        self._set_status("🧠 Berpikir...", color="#a855f7")
        self.console_tab.set_input_enabled(False)

        # 3. Pause wake word while generating
        if self.is_wake_word_active:
            try:
                self.orchestrator.get_wake_word().pause(release_device=True)
            except Exception as e:
                logger.debug("Wake pause exception: %s", e)

        # 4. Launch processing worker
        self.current_worker = ProcessInputWorker(self.orchestrator, clean_text, self)
        self.current_worker.token_received.connect(self._on_token_received)
        self.current_worker.speaking_started.connect(self._on_speaking_started)
        self.current_worker.speaking_finished.connect(self._on_speaking_finished)
        self.current_worker.turn_completed.connect(self._on_turn_completed)
        self.current_worker.error_occurred.connect(self._on_worker_error)
        self.current_worker.start()

    def _on_token_received(self, token: str) -> None:
        self.console_tab.append_assistant_token(token)
        if self.current_bubble:
            self.current_bubble.append_text(token)

    def _on_speaking_started(self) -> None:
        self._set_status("🔊 Berbicara... (Tekan Esc untuk stop)", color="#f59e0b")
        if hasattr(self, "console_tab") and self.console_tab:
            self.console_tab.set_speaking_state(True)

    def _on_speaking_finished(self) -> None:
        if hasattr(self, "console_tab") and self.console_tab:
            self.console_tab.set_speaking_state(False)
        self._restore_standby_status()

    def _on_turn_completed(self, route_name: str, full_response: str, latency_s: float) -> None:
        if hasattr(self, "console_tab") and self.console_tab:
            self.console_tab.set_speaking_state(False)
            self.console_tab.end_assistant_message()
            self.console_tab.set_input_enabled(True)
        self._restore_standby_status()

        # Reload todos if action might have modified tasks
        if "todo" in full_response.lower() or "tugas" in full_response.lower():
            if hasattr(self, "todo_tab") and self.todo_tab:
                self.todo_tab.reload_todos()

        if self.is_wake_word_active:
            try:
                self.orchestrator.get_wake_word().resume()
            except Exception as e:
                logger.debug("Wake resume exception: %s", e)

    def _stop_current_speech_or_generation(self) -> None:
        """Immediately stops TTS speech and cancels active background generation."""
        logger.info("[UI] Escape / Stop speech triggered by user.")
        try:
            self.orchestrator.stop_speech()
        except Exception as e:
            logger.debug("Error stopping speech: %s", e)

        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()

        if hasattr(self, "console_tab") and self.console_tab:
            self.console_tab.set_speaking_state(False)
            self.console_tab.append_assistant_token("\n[Bicara dihentikan]")
            self.console_tab.end_assistant_message()
            self.console_tab.set_input_enabled(True)
        self._restore_standby_status()

        if self.is_wake_word_active:
            try:
                self.orchestrator.get_wake_word().resume()
            except Exception:
                pass

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._stop_current_speech_or_generation()
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_worker_error(self, error_msg: str) -> None:
        self.console_tab.append_assistant_token(f"\n[Maaf, terjadi kendala: {error_msg}]")
        self.console_tab.end_assistant_message()
        self.console_tab.set_input_enabled(True)
        self._restore_standby_status()

        if self.is_wake_word_active:
            try:
                self.orchestrator.get_wake_word().resume()
            except Exception:
                pass

    # --- PTT Microphone Handling ---
    def _toggle_ptt_recording(self) -> None:
        if self.ptt_worker and self.ptt_worker.isRunning():
            self._set_status("⏳ Mengolah Audio...", color="#38bdf8")
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
        self.ptt_worker.transcription_ready.connect(self._on_ptt_transcribed)
        self.ptt_worker.error_occurred.connect(self._on_ptt_error)
        self.ptt_worker.start()

    def _on_ptt_started(self) -> None:
        self.console_tab.set_recording_state(True)
        self._set_status("🔴 Merekam Suara...", color="#ef4444")

    def _on_ptt_finished(self) -> None:
        self.console_tab.set_recording_state(False)
        self._set_status("⏳ Mengolah Audio...", color="#38bdf8")

    def _on_ptt_transcribed(self, text: str) -> None:
        self._submit_prompt(text)

    def _on_ptt_error(self, error_msg: str) -> None:
        self.console_tab.set_recording_state(False)
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
                self.btn_wake.setText("🎙️ WAKE: OFF")
                self.btn_wake.setStyleSheet("")
                self._restore_standby_status()
            else:
                wake_detector.on_wake_word = lambda score: self.wake_detected_signal.emit(score)
                wake_detector.on_command_captured = self._on_wake_command_captured
                wake_detector.on_silence_timeout = lambda: self.wake_timeout_signal.emit()

                wake_detector.start()
                self.is_wake_word_active = True
                self.btn_wake.setText("🎙️ WAKE: ON")
                self.btn_wake.setStyleSheet(
                    "background-color: #064e3b; color: #34d399; border: 1px solid #10b981; font-weight: 700;"
                )
                self._restore_standby_status()
        except Exception as e:
            logger.error("Failed to toggle wake word: %s", e)
            self._set_status("⚠️ Wake Word Error", color="#ef4444")

    def _on_wake_detected(self, score: float) -> None:
        self._set_status("🎙️ 'Hey Jarvis' Terdeteksi!", color="#38bdf8")
        self.show_and_activate()

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

    def _on_proactive_triggered(self, display_msg: str, spoken_msg: str) -> None:
        """Displays proactive suggestions from JARVIS in the chat stream."""
        if hasattr(self, "console_tab") and self.console_tab:
            self.console_tab.log_area.append(
                f"<div style='color: #00f0ff; font-weight: bold; margin-top: 8px;'>"
                f"💡 [JARVIS PROAKTIF] ❯ <span style='color: #e4e4e7;'>{display_msg}</span>"
                f"</div>"
            )
        if hasattr(self, "proactive_tab") and self.proactive_tab:
            self.proactive_tab.log_event("PROACTIVE", display_msg)

        if "pengingat" in display_msg.lower() or "reminder" in display_msg.lower():
            if hasattr(self, "todo_tab") and self.todo_tab:
                self.todo_tab.reload_todos()

        # Compatibility bubble for legacy tests
        if hasattr(self, "chat_canvas") and self.chat_canvas:
            self.chat_canvas.add_assistant_message(display_msg, sender="JARVIS (Proaktif)")

    def _cleanup_workers(self) -> None:
        if getattr(self, "telemetry_timer", None) is not None:
            try:
                if self.telemetry_timer.isActive():
                    self.telemetry_timer.stop()
            except Exception:
                pass

        if getattr(self, "hotkey_thread", None) is not None:
            try:
                if self.hotkey_thread.isRunning():
                    self.hotkey_thread.stop()
                    self.hotkey_thread.wait(300)
            except Exception:
                pass

        if getattr(self, "current_worker", None) is not None:
            try:
                if self.current_worker.isRunning():
                    self.current_worker.cancel()
                    self.current_worker.wait(300)
            except Exception:
                pass

        if getattr(self, "ptt_worker", None) is not None:
            try:
                if self.ptt_worker.isRunning():
                    self.ptt_worker.stop_recording()
                    self.ptt_worker.wait(300)
            except Exception:
                pass

        if getattr(self, "proactive_worker", None) is not None:
            try:
                if self.proactive_worker.isRunning():
                    self.proactive_worker.stop()
                    self.proactive_worker.wait(300)
            except Exception:
                pass

        if self.is_wake_word_active:
            try:
                wake = self.orchestrator.get_wake_word()
                if wake and wake.is_listening():
                    wake.stop()
            except Exception:
                pass

    def closeEvent(self, event) -> None:
        """Intercepts close to minimize to tray unless in tests or quitting."""
        if os.environ.get("PYTEST_CURRENT_TEST"):
            self._cleanup_workers()
            event.accept()
            return

        if hasattr(self, "tray_icon") and self.tray_icon and self.tray_icon.isVisible() and QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "JARVIS Berjalan di Latar Belakang",
                "JARVIS tetap aktif dan siap merespons. Tekan Win + Alt + J atau klik ikon tray kapan saja.",
                QSystemTrayIcon.MessageIcon.Information,
                1500,
            )
            return

        self._cleanup_workers()
        event.accept()

