"""Audio recording utilities for Push-to-Talk input."""

import queue
import threading
import time
from typing import Callable, List, Optional, Tuple
import numpy as np
import sounddevice as sd

from app.core.logger import setup_logger

logger = setup_logger("jarvis.voice.recorder")

TARGET_SAMPLE_RATE = 16000


def resample_audio(audio: np.ndarray, orig_sr: int, target_sr: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    """Resamples 1D audio array to target sampling rate using linear interpolation."""
    if orig_sr == target_sr:
        return audio.astype(np.float32)
    num_samples = int(len(audio) * target_sr / orig_sr)
    if num_samples <= 0:
        return np.zeros(0, dtype=np.float32)
    orig_indices = np.arange(len(audio))
    target_indices = np.linspace(0, len(audio) - 1, num_samples)
    return np.interp(target_indices, orig_indices, audio).astype(np.float32)


_CACHED_INPUT_DEVICE: Optional[Tuple[Optional[int], int, int]] = None
_CACHED_INPUT_DEVICE_KEY: Optional[Optional[int]] = None


def reset_cached_input_device() -> None:
    """Clears the cached audio input device (used in testing or reconfiguration)."""
    global _CACHED_INPUT_DEVICE, _CACHED_INPUT_DEVICE_KEY
    _CACHED_INPUT_DEVICE = None
    _CACHED_INPUT_DEVICE_KEY = None


def find_working_input_device(
    preferred_idx: Optional[int] = None, force_refresh: bool = False
) -> Tuple[Optional[int], int, int]:
    """Finds an operational audio input device index, sample rate, and channels.

    Actively verifies that the candidate device's InputStream callback fires
    and receives non-zero audio frames. Selects the device with the highest
    detected signal sensitivity.

    Returns:
        Tuple of (device_index, sample_rate, channels).
    """
    global _CACHED_INPUT_DEVICE, _CACHED_INPUT_DEVICE_KEY
    if not force_refresh and _CACHED_INPUT_DEVICE is not None and _CACHED_INPUT_DEVICE_KEY == preferred_idx:
        return _CACHED_INPUT_DEVICE

    devices = sd.query_devices()

    # 1. If user explicitly specified a preferred device index, test and verify it
    if preferred_idx is not None and 0 <= preferred_idx < len(devices):
        dev = devices[preferred_idx]
        if dev["max_input_channels"] > 0:
            for sr in [16000, int(dev["default_samplerate"]), 48000, 44100]:
                for ch in [1, min(2, dev["max_input_channels"])]:
                    frames_test: List[np.ndarray] = []

                    def _quick_cb(indata, frames, time_info, status):
                        frames_test.append(indata.copy())

                    try:
                        stream = sd.InputStream(
                            device=preferred_idx,
                            samplerate=sr,
                            channels=ch,
                            dtype="float32",
                            callback=_quick_cb,
                            blocksize=1024,
                        )
                        stream.start()
                        time.sleep(0.12)
                        stream.stop()
                        stream.close()

                        if len(frames_test) >= 2:
                            logger.info(
                                "Using verified configured audio device #%d (%s) sr=%d ch=%d",
                                preferred_idx,
                                dev["name"],
                                sr,
                                ch,
                            )
                            return preferred_idx, sr, ch
                    except Exception as e:
                        logger.debug("Preferred device test error: %s", e)

    # 2. Prioritize devices: WASAPI and MME shared devices first, avoid WDM-KS exclusive streams
    try:
        hostapis = sd.query_hostapis()
    except Exception:
        hostapis = []

    candidates = []
    for idx, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            h_idx = d.get("hostapi", -1)
            h_name = hostapis[h_idx]["name"].lower() if 0 <= h_idx < len(hostapis) else ""
            name_lower = d["name"].lower()
            if any(bad in name_lower for bad in ["stereo mix", "loopback", "steam streaming", "pc speaker"]):
                continue  # Avoid loopback desktop audio and virtual drivers

            # Prefer WASAPI, then WDM-KS (Acer hardware mic), then DirectSound/MME
            if "wasapi" in h_name:
                host_prio = 0
            elif "wdm-ks" in h_name or "kernel streaming" in h_name:
                host_prio = 1
            else:
                host_prio = 2

            if "microphone array" in name_lower:
                dev_prio = 0
            elif "microphone" in name_lower or "mic" in name_lower:
                dev_prio = 1
            else:
                dev_prio = 2

            candidates.append(((host_prio, dev_prio), idx))

    candidates.sort(key=lambda x: x[0])
    valid_devices = []

    for _, idx in candidates:
        d = devices[idx]
        sr_list = [16000, int(d["default_samplerate"]), 48000, 44100]
        device_verified = False

        for sr in sr_list:
            for ch in [1, min(2, d["max_input_channels"])]:
                frames_test = []

                def _cb(indata, frames, time_info, status):
                    frames_test.append(indata.copy())

                try:
                    stream = sd.InputStream(
                        device=idx,
                        samplerate=sr,
                        channels=ch,
                        dtype="float32",
                        callback=_cb,
                        blocksize=1024,
                    )
                    stream.start()
                    time.sleep(0.12)
                    stream.stop()
                    stream.close()

                    if len(frames_test) >= 2:
                        concat = np.concatenate(frames_test, axis=0)
                        peak = float(np.max(np.abs(concat)))
                        rms = float(np.sqrt(np.mean(concat**2)))

                        # Avoid dead or silent interfaces
                        if peak > 0.0001:
                            logger.info(
                                "Verified device #%d (%s) sr=%d ch=%d (peak=%.4f, rms=%.4f)",
                                idx,
                                d["name"],
                                sr,
                                ch,
                                peak,
                                rms,
                            )
                            valid_devices.append((idx, sr, ch, peak, rms, d["name"]))
                            device_verified = True
                            break
                except Exception:
                    pass
            if device_verified:
                break

    if valid_devices:
        # Choose the device with the highest ambient/voice signal sensitivity
        valid_devices.sort(key=lambda item: item[4], reverse=True)
        best = valid_devices[0]
        logger.info(
            "Selected optimal microphone #%d (%s) with sensitivity RMS=%.4f",
            best[0],
            best[5],
            best[4],
        )
        _CACHED_INPUT_DEVICE = (best[0], best[1], best[2])
        _CACHED_INPUT_DEVICE_KEY = preferred_idx
        return best[0], best[1], best[2]

    # Fallback to system default
    logger.warning("Could not auto-verify operational microphone; falling back to default.")
    return None, 16000, 1


class PushToTalkRecorder:
    """Manages push-to-talk audio recording via sounddevice."""

    def __init__(
        self,
        device_index: Optional[int] = None,
        level_callback: Optional[Callable[[float], None]] = None,
    ):
        self.device_index, self.sample_rate, self.channels = find_working_input_device(device_index)
        self.level_callback = level_callback
        self._is_recording = False
        self._queue: queue.Queue = queue.Queue()
        self._stream: Optional[sd.InputStream] = None
        self._chunks: List[np.ndarray] = []
        self._last_metrics = {
            "duration_s": 0.0,
            "peak": 0.0,
            "rms": 0.0,
            "shape": (0,),
            "chunks_count": 0,
        }

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def get_last_audio_metrics(self) -> dict:
        """Returns diagnostic metrics from the most recent recording."""
        return self._last_metrics.copy()

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback invoked by PortAudio for each incoming audio block."""
        if self._is_recording:
            self._queue.put(indata.copy())
            if self.level_callback is not None:
                try:
                    rms = float(np.sqrt(np.mean(indata**2)))
                    self.level_callback(rms)
                except Exception:
                    pass

    def start_recording(self) -> None:
        """Starts recording audio from the microphone."""
        if self._is_recording:
            return

        self._chunks.clear()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        self._is_recording = True

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                device=self.device_index,
                callback=self._audio_callback,
                blocksize=1024,
            )
            self._stream.start()
            logger.info(
                "Push-to-Talk recording started on device #%s (sr=%d, ch=%d)",
                self.device_index,
                self.sample_rate,
                self.channels,
            )
        except Exception as e:
            logger.warning("Push-to-Talk failed on device #%s (%s); refreshing device", self.device_index, e)
            try:
                self.device_index, self.sample_rate, self.channels = find_working_input_device(force_refresh=True)
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype="float32",
                    device=self.device_index,
                    callback=self._audio_callback,
                    blocksize=1024,
                )
                self._stream.start()
                logger.info(
                    "Push-to-Talk recording recovered on device #%s (sr=%d, ch=%d)",
                    self.device_index,
                    self.sample_rate,
                    self.channels,
                )
            except Exception as e2:
                self._is_recording = False
                logger.error("Failed to start audio input stream: %s", e2)
                raise

    def stop_recording(self) -> np.ndarray:
        """Stops recording and returns normalized 16kHz mono audio as float32 numpy array."""
        if not self._is_recording:
            return np.zeros(0, dtype=np.float32)

        self._is_recording = False

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning("Error stopping audio stream: %s", e)
            finally:
                self._stream = None

        # Gather all recorded audio blocks
        while not self._queue.empty():
            try:
                self._chunks.append(self._queue.get_nowait())
            except queue.Empty:
                break

        chunks_count = len(self._chunks)
        if not self._chunks:
            self._last_metrics = {
                "duration_s": 0.0,
                "peak": 0.0,
                "rms": 0.0,
                "shape": (0,),
                "chunks_count": 0,
            }
            logger.warning("Push-to-Talk captured 0 audio chunks.")
            return np.zeros(0, dtype=np.float32)

        raw_audio = np.concatenate(self._chunks, axis=0)

        # Convert to mono if multi-channel
        if raw_audio.ndim > 1 and raw_audio.shape[1] > 1:
            mono_audio = np.mean(raw_audio, axis=1)
        else:
            mono_audio = np.squeeze(raw_audio)

        # Resample to 16000 Hz if recorded at different sample rate
        resampled = resample_audio(mono_audio, self.sample_rate, TARGET_SAMPLE_RATE)
        duration_s = len(resampled) / TARGET_SAMPLE_RATE
        peak = float(np.max(np.abs(resampled))) if len(resampled) > 0 else 0.0
        rms = float(np.sqrt(np.mean(resampled**2))) if len(resampled) > 0 else 0.0

        # Software AGC headroom normalization for laptop microphones
        if peak > 0.0001 and peak < 0.3:
            gain = min(15.0, 0.6 / max(peak, 0.001))
            resampled = resampled * gain
            peak = float(np.max(np.abs(resampled)))
            rms = float(np.sqrt(np.mean(resampled**2)))

        self._last_metrics = {
            "duration_s": duration_s,
            "peak": peak,
            "rms": rms,
            "shape": resampled.shape,
            "chunks_count": chunks_count,
        }

        logger.info(
            "Push-to-Talk recording finished: %.2fs captured (chunks=%d, peak=%.4f, rms=%.4f)",
            duration_s,
            chunks_count,
            peak,
            rms,
        )
        return resampled

    def record_timed(
        self,
        max_duration: float = 6.0,
        cancel_event: Optional[threading.Event] = None,
    ) -> np.ndarray:
        """Records microphone audio up to max_duration seconds with early silence detection."""
        self.start_recording()
        t_start = time.time()
        has_spoken = False
        silence_start = None
        ambient_rms = 0.001

        while time.time() - t_start < max_duration:
            if cancel_event and cancel_event.is_set():
                break
            time.sleep(0.08)

            if not self._queue.empty():
                blocks = []
                while not self._queue.empty():
                    try:
                        blocks.append(self._queue.get_nowait())
                    except queue.Empty:
                        break
                if blocks:
                    self._chunks.extend(blocks)
                    cat = np.concatenate(blocks, axis=0)
                    rms = float(np.sqrt(np.mean(cat ** 2)))
                    if not has_spoken and time.time() - t_start < 0.4:
                        ambient_rms = 0.8 * ambient_rms + 0.2 * rms

                    speech_threshold = max(0.0025, ambient_rms * 1.5)
                    if rms >= speech_threshold:
                        has_spoken = True
                        silence_start = None
                    elif has_spoken:
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start > 1.2:
                            # 1.2s silence after speech -> user done speaking
                            break

        return self.stop_recording()

