"""In-Memory Real-Time Audio Stream Injection for Simulated User Agent.

Simulates real-time microphone audio input directly into JARVIS's WakeWordDetector
and STT pipeline without requiring physical microphones or 3rd-party virtual audio cables.
"""

import queue
import threading
import time
from typing import Callable, Generator, List, Optional, Union
import numpy as np

from app.core.logger import setup_logger
from app.voice.wake_word import CHUNK_SAMPLES, SAMPLE_RATE, WakeWordDetector, WakeWordState

logger = setup_logger("jarvis.simulator.audio")


class AudioStreamInjector:
    """Injects synthesized PCM audio chunks into JARVIS's audio queue in real-time."""

    def __init__(
        self,
        wake_detector: Optional[WakeWordDetector] = None,
        sample_rate: int = SAMPLE_RATE,
        chunk_samples: int = CHUNK_SAMPLES,
    ):
        self.detector = wake_detector
        self.sample_rate = sample_rate
        self.chunk_samples = chunk_samples
        self.chunk_duration = chunk_samples / sample_rate  # 80ms for 1280 / 16000

        self._is_injecting = False
        self._abort_event = threading.Event()
        self._captured_jarvis_speech: List[str] = []
        self._lock = threading.Lock()

    def attach_detector(self, detector: WakeWordDetector) -> None:
        """Attaches or updates the target WakeWordDetector instance."""
        self.detector = detector

    def hook_tts_capture(self, orchestrator) -> None:
        """Hooks into JARVIS's TTS and process stream to capture JARVIS's replies."""
        try:
            tts = orchestrator.get_tts()
            orig_speak = tts.speak
            orig_speak_stream = tts.speak_stream

            def hooked_speak(text: str, *args, **kwargs):
                with self._lock:
                    self._captured_jarvis_speech.append(text)
                return orig_speak(text, *args, **kwargs)

            def hooked_speak_stream(sentence_generator, *args, **kwargs):
                collected = []
                for s in sentence_generator:
                    collected.append(s)
                    with self._lock:
                        self._captured_jarvis_speech.append(s)
                return orig_speak_stream(iter(collected), *args, **kwargs)

            tts.speak = hooked_speak
            tts.speak_stream = hooked_speak_stream
            logger.info("TTS capture hook installed successfully.")
        except Exception as e:
            logger.debug("Failed to attach TTS capture hook: %s", e)

    def get_latest_jarvis_speech(self) -> str:
        """Returns and clears the accumulated speech from JARVIS."""
        with self._lock:
            speech = " ".join(self._captured_jarvis_speech).strip()
            self._captured_jarvis_speech.clear()
            return speech

    def inject_pcm(
        self,
        pcm_audio: np.ndarray,
        real_time: bool = True,
        pace_multiplier: float = 1.0,
        on_chunk_sent: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """Streams a PCM audio array into the wake detector's audio queue.

        Args:
            pcm_audio: 1D numpy array of 16kHz mono audio (int16 or float32 in [-1.0, 1.0]).
            real_time: If True, paces chunk injection at 1x real-time speed (80ms per chunk).
            pace_multiplier: Speed multiplier for real-time pacing (e.g. 1.5x faster or 1.0x normal).
            on_chunk_sent: Optional callback(current_chunk_idx, total_chunks).

        Returns:
            bool: True if completed successfully, False if aborted.
        """
        if self.detector is None:
            raise RuntimeError("No WakeWordDetector attached to AudioStreamInjector.")

        # Ensure int16 format
        if pcm_audio.dtype == np.float32 or pcm_audio.dtype == np.float64:
            pcm_audio = np.clip(pcm_audio * 32767.0, -32768, 32767).astype(np.int16)
        elif pcm_audio.dtype != np.int16:
            pcm_audio = pcm_audio.astype(np.int16)

        total_samples = len(pcm_audio)
        total_chunks = (total_samples + self.chunk_samples - 1) // self.chunk_samples

        self._abort_event.clear()
        self._is_injecting = True

        sleep_interval = (self.chunk_duration / max(0.1, pace_multiplier)) if real_time else 0.002

        try:
            for idx in range(total_chunks):
                if self._abort_event.is_set():
                    logger.info("Audio injection aborted at chunk %d/%d", idx, total_chunks)
                    return False

                start_idx = idx * self.chunk_samples
                end_idx = min(start_idx + self.chunk_samples, total_samples)
                chunk = pcm_audio[start_idx:end_idx]

                # Pad last chunk with silence if necessary
                if len(chunk) < self.chunk_samples:
                    padded = np.zeros(self.chunk_samples, dtype=np.int16)
                    padded[: len(chunk)] = chunk
                    chunk = padded

                # Push chunk to WakeWordDetector internal queue
                try:
                    self.detector._audio_queue.put(chunk, timeout=0.5)
                except queue.Full:
                    logger.debug("Audio queue full; dropped injected chunk %d", idx)

                if on_chunk_sent:
                    on_chunk_sent(idx + 1, total_chunks)

                if sleep_interval > 0:
                    time.sleep(sleep_interval)

            return True

        finally:
            self._is_injecting = False

    def inject_silence(self, duration_sec: float = 1.0, real_time: bool = True) -> None:
        """Injects silence to allow VAD to detect end of speech."""
        samples = int(duration_sec * self.sample_rate)
        silence = np.zeros(samples, dtype=np.int16)
        self.inject_pcm(silence, real_time=real_time)

    def abort(self) -> None:
        """Signals current audio injection to halt immediately."""
        self._abort_event.set()
