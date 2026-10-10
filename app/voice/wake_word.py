"""Always-listening wake word detector using openWakeWord (Phase 4).

Provides real-time, low-latency, fully offline wake-word detection
for "Hey Jarvis" / "Jarvis" with a robust state machine and zero cloud dependencies.
"""

import enum
import queue
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np
import sounddevice as sd

from app.core.config import Settings, get_settings
from app.core.logger import setup_logger
from app.voice.audio_recorder import find_working_input_device

logger = setup_logger("jarvis.voice.wake_word")

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280  # 80ms at 16000Hz (exact openWakeWord frame requirement)


class WakeWordState(enum.Enum):
    """Explicit lifecycle states for the wake-word state machine."""
    STOPPED = "STOPPED"
    STANDBY = "STANDBY"
    LISTENING_COMMAND = "LISTENING_COMMAND"
    PROCESSING_COMMAND = "PROCESSING_COMMAND"
    SPEAKING = "SPEAKING"
    RECOVERING = "RECOVERING"
    PAUSED = "PAUSED"

    # Backward compatibility aliases
    LISTENING_FOR_WAKE_WORD = "STANDBY"
    WAKE_WORD_DETECTED = "LISTENING_COMMAND"
    CAPTURING_COMMAND = "LISTENING_COMMAND"
    SPEAKING_RESPONSE = "SPEAKING"


def generate_chime_audio(sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Generates a pleasant two-tone digital acknowledgment chime (C6 1046.5Hz + E6 1318.5Hz).

    Uses a cosine amplitude envelope for smooth fading without clicks or pops.
    """
    duration1 = 0.06  # 60ms first tone
    duration2 = 0.08  # 80ms second tone

    t1 = np.linspace(0, duration1, int(sample_rate * duration1), endpoint=False)
    t2 = np.linspace(0, duration2, int(sample_rate * duration2), endpoint=False)

    f1 = 1046.5   # C6
    f2 = 1318.5   # E6

    env1 = np.sin(np.pi * np.linspace(0, 1, len(t1)))
    env2 = np.sin(np.pi * np.linspace(0, 1, len(t2)))

    tone1 = np.sin(2 * np.pi * f1 * t1) * env1 * 0.40
    tone2 = np.sin(2 * np.pi * f2 * t2) * env2 * 0.40

    chime = np.concatenate([tone1, tone2]).astype(np.float32)
    return chime


def play_chime(sample_rate: int = SAMPLE_RATE, blocking: bool = False) -> None:
    """Plays a crisp digital acknowledgment ping when the wake word is detected.

    On Windows, uses native winsound.Beep for instantaneous, non-contending
    hardware audio playback without PortAudio stream initialization overhead.
    Falls back to sounddevice if winsound is unavailable.
    """
    # 1. Primary on Windows: native winsound.Beep (instant, zero stream contention)
    try:
        import winsound
        winsound.Beep(1046, 60)  # C6 (60ms)
        winsound.Beep(1318, 80)  # E6 (80ms)
        return
    except Exception as e:
        logger.debug("winsound ping failed (%s), falling back to sounddevice", e)

    # 2. Fallback: sounddevice
    try:
        chime = generate_chime_audio(sample_rate)
        sd.play(chime, samplerate=sample_rate)
        if blocking:
            sd.wait()
    except Exception as e:
        logger.debug("Failed to play wake word acknowledgment chime: %s", e)


class WakeWordDetector:
    """Offline, continuous wake-word detector with state machine coordination."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        on_wake_word: Optional[Callable[[float], None]] = None,
        on_command_captured: Optional[Callable[[np.ndarray], None]] = None,
        on_silence_timeout: Optional[Callable[[], None]] = None,
        on_state_change: Optional[Callable[[WakeWordState, WakeWordState], None]] = None,
    ):
        self.settings = settings or get_settings()
        self.threshold = self.settings.wake_word_threshold
        self.cooldown = self.settings.wake_word_cooldown
        self.silence_timeout = self.settings.wake_word_silence_timeout
        self.max_command_duration = self.settings.wake_word_max_command_duration
        self.vad_threshold = self.settings.wake_word_vad_threshold

        self.on_wake_word = on_wake_word
        self.on_command_captured = on_command_captured
        self.on_silence_timeout = on_silence_timeout
        self.on_state_change = on_state_change

        self._state = WakeWordState.STOPPED
        self._state_lock = threading.Lock()

        # Model and Audio stream
        self._model = None
        self._model_key: Optional[str] = None
        self._stream: Optional[sd.InputStream] = None
        self._audio_queue: queue.Queue = queue.Queue(maxsize=100)
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Audio device configuration
        self.device_index: Optional[int] = self.settings.audio_device
        self.device_sample_rate = SAMPLE_RATE
        self.device_channels = 1

        # Command capture buffers and tracking
        self._preroll_buffer: List[np.ndarray] = []
        self._preroll_max_chunks = 4  # ~320ms preroll for wake verification
        self._command_chunks: List[np.ndarray] = []
        self._last_detection_time = 0.0
        self._ambient_rms = 30.0

    @property
    def state(self) -> WakeWordState:
        with self._state_lock:
            return self._state

    def set_state(self, new_state: WakeWordState) -> None:
        """Transitions to a new state and notifies state change listeners."""
        with self._state_lock:
            old_state = self._state
            if old_state == new_state:
                return
            self._state = new_state

        logger.info("WakeWordDetector state transition: %s -> %s", old_state.value, new_state.value)
        if self.on_state_change:
            try:
                self.on_state_change(old_state, new_state)
            except Exception as e:
                logger.error("Error in on_state_change callback: %s", e)

    def is_listening(self) -> bool:
        """Returns True if actively listening for the wake word."""
        return self.state == WakeWordState.LISTENING_FOR_WAKE_WORD

    def resolve_model_path(self) -> str:
        """Finds and resolves the wake-word ONNX model path."""
        # 1. Check configured models directory
        candidate_path = self.settings.wake_word_models_dir / self.settings.wake_word_model
        if candidate_path.exists():
            return str(candidate_path)

        # 2. Check if openwakeword has built-in model
        try:
            import openwakeword
            res_dir = Path(openwakeword.__file__).parent / "resources" / "models"
            res_model = res_dir / self.settings.wake_word_model
            if res_model.exists():
                return str(res_model)
        except Exception:
            pass

        # 3. Fallback to model name directly for openwakeword resolution
        return self.settings.wake_word_model

    def initialize(self) -> None:
        """Loads openWakeWord ONNX model and selects operational audio device."""
        if self._model is not None:
            return

        model_path = self.resolve_model_path()
        logger.info("Initializing openWakeWord model from: %s", model_path)

        try:
            from openwakeword.model import Model
            self._model = Model(
                wakeword_models=[model_path],
                inference_framework="onnx",
                vad_threshold=self.vad_threshold,
            )
            model_keys = list(self._model.models.keys())
            if not model_keys:
                raise RuntimeError(f"No wake word models loaded from {model_path}")
            self._model_key = model_keys[0]
            logger.info("openWakeWord loaded model key: '%s'", self._model_key)
        except Exception as e:
            logger.error("Failed to initialize openWakeWord model: %s", e)
            raise

        # Verify operational audio device
        dev_idx, sr, ch = find_working_input_device(self.device_index)
        self.device_index = dev_idx
        self.device_sample_rate = sr
        self.device_channels = ch
        logger.info(
            "WakeWord audio device configured: #%s, sr=%d, ch=%d",
            self.device_index,
            self.device_sample_rate,
            self.device_channels,
        )

    def _audio_callback(self, indata, frames, time_info, status):
        """Audio streaming callback executed by PortAudio."""
        if self._stop_event.is_set():
            return

        # indata has shape (frames, channels) and dtype int16
        if indata.ndim > 1 and indata.shape[1] > 1:
            # Downmix to mono
            mono = indata.mean(axis=1).astype(np.int16)
        else:
            mono = indata.squeeze().astype(np.int16)

        try:
            self._audio_queue.put_nowait(mono)
        except queue.Full:
            # Drop frame if processing lags behind to prevent unbounded latency
            pass

    def _close_stream(self) -> None:
        """Safely stops and closes PortAudio InputStream."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.debug("Error closing wake word audio stream: %s", e)
            finally:
                self._stream = None

    def start(self) -> None:
        """Starts continuous audio capture and background wake-word processing."""
        if self.state == WakeWordState.LISTENING_FOR_WAKE_WORD:
            logger.debug("WakeWordDetector already listening.")
            return

        # If paused and stream/thread are still alive, simply unpause
        if (
            self.state == WakeWordState.PAUSED
            and self._stream is not None
            and self._worker_thread is not None
            and self._worker_thread.is_alive()
        ):
            self.resume()
            return

        # Otherwise ensure any stale stream or thread is cleanly stopped first
        self.stop()
        self.initialize()
        self._stop_event.clear()

        # Clear audio queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        self._preroll_buffer.clear()
        self._command_chunks.clear()

        # Start PortAudio Input stream at 16000Hz mono int16
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=CHUNK_SAMPLES,
                device=self.device_index,
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as e:
            logger.error("Failed to start audio input stream for wake word: %s", e)
            self._close_stream()
            self.set_state(WakeWordState.STOPPED)
            raise

        self._worker_thread = threading.Thread(target=self._run_loop, name="WakeWordWorker", daemon=True)
        self._worker_thread.start()

        self.set_state(WakeWordState.LISTENING_FOR_WAKE_WORD)
        logger.info("WakeWordDetector started. Actively listening for wake word.")

    def pause(self, release_device: bool = False) -> None:
        """Pauses wake-word detection. If release_device=True, releases audio hardware."""
        if self.state in (WakeWordState.STOPPED, WakeWordState.PAUSED):
            if release_device:
                self._close_stream()
            return
        self.set_state(WakeWordState.PAUSED)
        if self._model:
            self._model.reset()
        if release_device:
            self._close_stream()

    def resume(self) -> None:
        """Resumes active wake-word listening after TTS playback or processing."""
        if self.state == WakeWordState.STOPPED or self._stream is None:
            self.start()
            return

        # Atomically transition through RECOVERING to ensure audio frames during recovery are dropped
        self.set_state(WakeWordState.RECOVERING)

        if self._model:
            self._model.reset()

        # Drain audio queue to discard audio captured during processing or speech
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        self._last_detection_time = time.time()
        self._preroll_buffer.clear()
        self._command_chunks.clear()
        self.set_state(WakeWordState.STANDBY)
        logger.info("WakeWordDetector resumed to STANDBY with cooldown enforced.")

    def stop(self) -> None:
        """Stops the audio stream and worker thread, completely releasing PortAudio device."""
        self._stop_event.set()
        self.set_state(WakeWordState.STOPPED)
        self._close_stream()

        if self._worker_thread and self._worker_thread.is_alive():
            if threading.current_thread() != self._worker_thread:
                self._worker_thread.join(timeout=1.0)
            self._worker_thread = None

        logger.info("WakeWordDetector stopped and audio device released.")

    def cleanup(self) -> None:
        """Releases all resources and unloads model."""
        self.stop()
        self._model = None
        self._model_key = None
        logger.info("WakeWordDetector cleaned up.")

    def _run_loop(self) -> None:
        """Background thread continuously processing incoming audio frames."""
        speech_started = False
        consecutive_silence_chunks = 0
        command_start_monotonic = 0.0

        # 1280 samples = 0.08s -> chunks per second = 12.5
        chunks_per_sec = SAMPLE_RATE / CHUNK_SAMPLES

        while not self._stop_event.is_set():
            try:
                chunk = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            current_state = self.state

            # Discard frames when paused, processing command, speaking response, or recovering
            if current_state in (
                WakeWordState.PAUSED,
                WakeWordState.PROCESSING_COMMAND,
                WakeWordState.SPEAKING,
                WakeWordState.RECOVERING,
                WakeWordState.STOPPED,
            ):
                continue

            # State 1: STANDBY (Listening for wake word)
            if current_state in (WakeWordState.STANDBY, WakeWordState.LISTENING_FOR_WAKE_WORD):
                # Update running ambient noise estimate during standby
                chunk_f = chunk.astype(np.float32)
                chunk_rms = float(np.sqrt(np.mean(chunk_f ** 2)))
                self._ambient_rms = 0.95 * self._ambient_rms + 0.05 * chunk_rms

                # Maintain short preroll buffer
                self._preroll_buffer.append(chunk)
                if len(self._preroll_buffer) > self._preroll_max_chunks:
                    self._preroll_buffer.pop(0)

                # Enforce cooldown period after last activation
                now = time.time()
                if now - self._last_detection_time < self.cooldown:
                    continue

                if self._model is None or self._model_key is None:
                    continue

                try:
                    preds = self._model.predict(chunk)
                    score = float(preds.get(self._model_key, 0.0))
                except Exception as e:
                    logger.debug("Inference error in openWakeWord predict: %s", e)
                    score = 0.0

                if score >= self.threshold:
                    self._last_detection_time = time.time()
                    logger.info(
                        "[WAKE] Detected model=%s, confidence=%.3f (threshold=%.2f)",
                        self._model_key,
                        score,
                        self.threshold,
                    )

                    # Atomically transition to LISTENING_COMMAND to prevent duplicate activations
                    self.set_state(WakeWordState.LISTENING_COMMAND)

                    # Trigger visual / notification callback
                    if self.on_wake_word:
                        try:
                            self.on_wake_word(score)
                        except Exception as cb_err:
                            logger.error("Error in on_wake_word callback: %s", cb_err)

                    # Play acknowledgment chime synchronously so it does not bleed into user speech
                    play_chime(blocking=True)
                    time.sleep(0.04)

                    # Purge any residual audio captured while the chime was playing
                    while not self._audio_queue.empty():
                        try:
                            self._audio_queue.get_nowait()
                        except queue.Empty:
                            break

                    # Clear command chunks and wake model internal states
                    self._command_chunks.clear()
                    self._preroll_buffer.clear()
                    if self._model:
                        self._model.reset()

                    # Initialize command capture state
                    speech_started = False
                    consecutive_silence_chunks = 0
                    command_start_monotonic = time.monotonic()
                    logger.info(
                        "[RECORD] Command capture started (ambient_rms=%.1f, no_speech_timeout=%.1fs, max_dur=%.1fs)",
                        self._ambient_rms,
                        max(3.0, self.silence_timeout),
                        self.max_command_duration,
                    )
                    continue

            # State 2: LISTENING_COMMAND (Capturing command speech)
            elif current_state in (WakeWordState.LISTENING_COMMAND, WakeWordState.CAPTURING_COMMAND):
                self._command_chunks.append(chunk)

                # Compute frame energy in 16-bit PCM scale
                chunk_f = chunk.astype(np.float32)
                chunk_rms = float(np.sqrt(np.mean(chunk_f ** 2)))

                # Dynamic VAD thresholds adapted from ambient noise floor
                speech_start_threshold = max(60.0, self._ambient_rms * 1.5)
                silence_threshold = max(35.0, self._ambient_rms * 1.2)

                if not speech_started:
                    if chunk_rms >= speech_start_threshold:
                        speech_started = True
                        consecutive_silence_chunks = 0
                        elapsed_so_far = time.monotonic() - command_start_monotonic
                        logger.info(
                            "[VAD] First speech frame detected (chunk_rms=%.1f, threshold=%.1f, elapsed=%.2fs)",
                            chunk_rms,
                            speech_start_threshold,
                            elapsed_so_far,
                        )
                else:
                    if chunk_rms < silence_threshold:
                        consecutive_silence_chunks += 1
                    else:
                        consecutive_silence_chunks = 0

                elapsed = time.monotonic() - command_start_monotonic
                silence_chunk_limit = int(max(1.2, self.silence_timeout) * chunks_per_sec)

                # Check termination conditions using monotonic timing:
                # 1. No speech began within configured timeout (default 3.0s)
                # 2. User started speaking and then paused for silence_timeout
                # 3. Maximum command duration exceeded
                is_no_speech_timeout = (not speech_started) and (elapsed >= max(3.0, self.silence_timeout))
                is_speech_ended = speech_started and (consecutive_silence_chunks >= silence_chunk_limit)
                is_max_duration = elapsed >= self.max_command_duration

                if is_no_speech_timeout:
                    logger.info(
                        "[RECORD] Recording stopped: reason=silence_timeout (no speech detected within %.2fs). Returning to standby.",
                        elapsed,
                    )
                    self._command_chunks.clear()
                    self._preroll_buffer.clear()
                    if self._model:
                        self._model.reset()
                    self._last_detection_time = time.time()
                    self.set_state(WakeWordState.STANDBY)
                    if self.on_silence_timeout:
                        try:
                            self.on_silence_timeout()
                        except Exception as st_err:
                            logger.error("Error in on_silence_timeout callback: %s", st_err)
                    continue

                if is_speech_ended or is_max_duration:
                    stop_reason = "silence_timeout" if is_speech_ended else "max_duration"

                    # Combine chunks into single normalized float32 array
                    if self._command_chunks:
                        raw_int16 = np.concatenate(self._command_chunks, axis=0)
                        audio_f32 = raw_int16.astype(np.float32) / 32768.0
                    else:
                        audio_f32 = np.zeros(0, dtype=np.float32)

                    audio_dur = len(audio_f32) / float(SAMPLE_RATE) if len(audio_f32) > 0 else 0.0
                    peak = float(np.max(np.abs(audio_f32))) if len(audio_f32) > 0 else 0.0
                    rms = float(np.sqrt(np.mean(audio_f32 ** 2))) if len(audio_f32) > 0 else 0.0

                    logger.info(
                        "[RECORD] Recording stopped: reason=%s, duration=%.2fs, peak=%.4f, rms=%.4f, chunks=%d",
                        stop_reason,
                        audio_dur,
                        peak,
                        rms,
                        len(self._command_chunks),
                    )

                    # Pre-STT energy gate: discard if signal is merely background click or noise
                    if peak < 0.005 or rms < 0.001 or audio_dur < 0.3:
                        logger.info(
                            "[RECORD] Captured audio below human speech threshold (peak=%.4f, rms=%.4f, dur=%.2fs). Discarding noise.",
                            peak,
                            rms,
                            audio_dur,
                        )
                        self._command_chunks.clear()
                        self._preroll_buffer.clear()
                        if self._model:
                            self._model.reset()
                        self._last_detection_time = time.time()
                        self.set_state(WakeWordState.STANDBY)
                        if self.on_silence_timeout:
                            try:
                                self.on_silence_timeout()
                            except Exception as st_err:
                                logger.error("Error in on_silence_timeout callback: %s", st_err)
                        continue

                    # Transition to PROCESSING_COMMAND before invoking consumer callback
                    self.set_state(WakeWordState.PROCESSING_COMMAND)

                    if self.on_command_captured:
                        try:
                            self.on_command_captured(audio_f32)
                        except Exception as cmd_err:
                            logger.error("Error in on_command_captured callback: %s", cmd_err)

                    self._command_chunks.clear()
                    self._preroll_buffer.clear()
