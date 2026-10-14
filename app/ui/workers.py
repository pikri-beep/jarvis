"""Background worker threads for JARVIS GUI to ensure non-blocking UI interactions."""

import time
import threading
from typing import Optional
import psutil
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.core.logger import setup_logger
from app.core.orchestrator import Orchestrator
from app.voice.audio_recorder import PushToTalkRecorder

logger = setup_logger("jarvis.ui.workers")


class ProcessInputWorker(QThread):
    """Executes a user prompt through the Orchestrator pipeline with streaming and voice."""

    token_received = pyqtSignal(str)
    turn_completed = pyqtSignal(str, str, float)  # route_type, full_response, latency_s
    error_occurred = pyqtSignal(str)
    speaking_started = pyqtSignal()
    speaking_finished = pyqtSignal()

    def __init__(self, orchestrator: Orchestrator, user_input: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.user_input = user_input
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        t_start = time.time()
        route_name = "DIRECT"
        full_response = ""
        try:
            route, stream_gen = self.orchestrator.process_input_stream(self.user_input)
            accumulated_tokens = []

            for token in stream_gen:
                if self._is_cancelled:
                    break
                accumulated_tokens.append(token)
                self.token_received.emit(token)

            full_response = "".join(accumulated_tokens)
            latency = time.time() - t_start
            if hasattr(route, "name") and isinstance(route.name, str):
                route_name = str(route.name)
            elif hasattr(route, "route_type") and hasattr(getattr(route, "route_type", None), "name") and isinstance(route.route_type.name, str):
                badge_type = str(route.route_type.name).replace("_", " ")
                act = getattr(route, "action", "")
                route_name = f"{badge_type} • {str(act)}" if isinstance(act, str) and act else badge_type
            elif hasattr(route, "route") and isinstance(route.route, str):
                route_name = str(route.route)
            else:
                route_name = "DIRECT"

            # Trigger spoken TTS playback in background if enabled and not muted
            is_muted = getattr(self.orchestrator.state, "is_muted", False)
            if self.orchestrator.settings.tts_enabled and full_response and not is_muted:
                try:
                    self.speaking_started.emit()
                    tts = self.orchestrator.get_tts()
                    # Blocking speak inside this background QThread gives clean sync with GUI
                    tts.speak(
                        full_response,
                        blocking=True,
                        language=self.orchestrator.state.conversation_language,
                    )
                except Exception as tts_err:
                    logger.warning("TTS playback error in worker: %s", tts_err)
                finally:
                    self.speaking_finished.emit()

            self.turn_completed.emit(route_name, full_response, latency)

        except Exception as e:
            logger.error("Error processing input in worker: %s", e, exc_info=True)
            self.error_occurred.emit(str(e))


class PttRecordWorker(QThread):
    """Handles Push-to-Talk audio recording and transcription asynchronously."""

    recording_started = pyqtSignal()
    recording_finished = pyqtSignal()
    transcription_ready = pyqtSignal(str)
    audio_level = pyqtSignal(float)  # 0.0 to 1.0 normalized
    error_occurred = pyqtSignal(str)

    def __init__(self, orchestrator: Orchestrator, max_duration: float = 7.0, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.max_duration = max_duration
        self.stop_event = threading.Event()
        self.recorder = PushToTalkRecorder(level_callback=self._on_audio_level)

    def _on_audio_level(self, rms: float) -> None:
        normalized = min(1.0, max(0.0, rms * 40.0))
        self.audio_level.emit(normalized)

    def stop_recording(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        try:
            self.recording_started.emit()
            audio = self.recorder.record_timed(
                max_duration=self.max_duration, cancel_event=self.stop_event
            )
            self.recording_finished.emit()

            if len(audio) == 0:
                self.error_occurred.emit("Tidak ada audio yang terdeteksi pada mikrofon.")
                return

            text, info = self.orchestrator.transcribe_audio(audio)
            clean_text = text.strip()
            if clean_text:
                self.transcription_ready.emit(clean_text)
            else:
                self.error_occurred.emit("Tidak ada ucapan yang dapat dikenali.")
        except Exception as e:
            logger.error("PTT Worker error: %s", e, exc_info=True)
            self.error_occurred.emit(str(e))


class SystemMetricsWorker(QThread):
    """Polls system hardware metrics and component statuses every 2 seconds."""

    metrics_updated = pyqtSignal(dict)

    def __init__(self, orchestrator: Orchestrator, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        while self._running:
            try:
                cpu_pct = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory()
                ram_pct = ram.percent
                ram_used_gb = round((ram.total - ram.available) / (1024**3), 1)
                ram_total_gb = round(ram.total / (1024**3), 1)

                status = self.orchestrator.get_system_status()
                payload = {
                    "cpu_percent": cpu_pct,
                    "ram_percent": ram_pct,
                    "ram_used_gb": ram_used_gb,
                    "ram_total_gb": ram_total_gb,
                    "ollama_connected": status.get("ollama_connected", False),
                    "model_ready": status.get("model_ready", False),
                    "model": status.get("model", ""),
                    "tts_enabled": status.get("tts_enabled", False),
                    "wake_word_active": status.get("wake_word_active", False),
                }
                self.metrics_updated.emit(payload)
            except Exception as e:
                logger.debug("Metrics collection warning: %s", e)

            # Sleep 2 seconds before next poll
            for _ in range(20):
                if not self._running:
                    break
                time.sleep(0.1)
