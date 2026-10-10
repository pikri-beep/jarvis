"""Speech-to-text module using faster-whisper.

Provides lightweight, fast local audio transcription on CPU with int8 quantization.
"""

import time
from typing import Optional, Tuple, Union
import numpy as np

from app.core.config import Settings, get_settings
from app.core.logger import setup_logger

logger = setup_logger("jarvis.voice.stt")


DEFAULT_INITIAL_PROMPT = (
    "Halo JARVIS. Tolong buka Chrome, Google Chrome, YouTube, Open YouTube, Buka YouTube, "
    "Instagram, Buka Instagram, WhatsApp, Notepad, Edge, Kalkulator, Pengaturan, Berkas, File Explorer. "
    "Buka tab baru, tutup tab, kembali, refresh halaman, klik kolom pencarian, ketik, tekan enter, "
    "gerakkan kursor ke tengah layar, klik, klik kanan, scroll ke bawah, scroll ke atas, lihat layar gue. "
    "Jam berapa sekarang? Sekarang jam berapa? Pukul berapa sekarang? Tanggal berapa hari ini? Hari apa sekarang? Waktu sekarang. "
    "RAM, SSD, info sistem. Open Chrome, WhatsApp, Settings, What time is it, Take screenshot."
)

WHISPER_HALLUCINATIONS = {
    "terima kasih", "terima kasih.", "terima kasih banyak", "terima kasih banyak.",
    "terima kasih telah menonton", "terima kasih telah menonton.",
    "thank you", "thank you.", "thank you very much", "thank you very much.",
    "thanks for watching", "thanks for watching.",
    "subtitles by", "subtitles by amara.org",
    "you", "you.", "bye", "bye.", "...", "[music]", "(music)",
}


class SpeechToText:
    """Local Speech-to-Text engine using faster-whisper."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.model_size = self.settings.stt_model
        self.device = self.settings.stt_device
        self.compute_type = self.settings.stt_compute_type
        self.language = self.settings.stt_language
        self._model = None

    def load_model(self) -> None:
        """Loads the faster-whisper model into memory."""
        if self._model is not None:
            return

        logger.info(
            "Loading Whisper model '%s' (device=%s, compute_type=%s)...",
            self.model_size,
            self.device,
            self.compute_type,
        )
        t0 = time.time()
        from faster_whisper import WhisperModel

        import os
        num_threads = min(6, os.cpu_count() or 4)

        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            cpu_threads=num_threads,
        )
        elapsed = time.time() - t0
        logger.info(
            "Whisper model '%s' loaded in %.2fs (threads=%d)",
            self.model_size,
            elapsed,
            num_threads,
        )

    def is_loaded(self) -> bool:
        """Returns True if the model is currently loaded in memory."""
        return self._model is not None

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: Optional[str] = None,
        initial_prompt: Optional[str] = None,
    ) -> Tuple[str, dict]:
        """Transcribes raw audio array (float32, 16kHz mono) to text.

        Args:
            audio: 1D numpy array of audio samples (float32, normalized [-1, 1]).
            sample_rate: Audio sampling rate (expected 16000).
            language: Optional language code ('auto', 'id', 'en').
            initial_prompt: Optional vocabulary priming prompt for domain words.

        Returns:
            Tuple of (transcribed_text, info_dict).
        """
        # Resample if audio is not 16kHz
        if sample_rate != 16000:
            from app.voice.audio_recorder import resample_audio
            audio = resample_audio(audio, orig_sr=sample_rate, target_sr=16000)
            sample_rate = 16000

        audio = np.squeeze(audio).astype(np.float32)

        duration = len(audio) / sample_rate
        if duration < 0.2:
            logger.debug("Audio duration too short (%.2fs), skipping transcription.", duration)
            return "", {"language": "", "language_prob": 0.0, "duration": duration, "peak": 0.0, "rms": 0.0, "transcription_time": 0.0}

        max_amp = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0
        rms_amp = float(np.sqrt(np.mean(audio**2))) if len(audio) > 0 else 0.0

        # Pre-STT silence & ambient noise gate: rejects pure noise or silence before neural decoding
        if max_amp < 0.005 or rms_amp < 0.0015:
            logger.debug(
                "Audio energy below threshold (peak=%.4f, rms=%.4f), rejecting as silence.",
                max_amp,
                rms_amp,
            )
            return "", {"language": "", "language_prob": 0.0, "duration": duration, "peak": max_amp, "rms": rms_amp, "transcription_time": 0.0}

        if self._model is None:
            self.load_model()

        eff_lang = language if language is not None else self.language
        is_auto = not eff_lang or eff_lang.lower() == "auto"

        t0 = time.time()
        detected_lang = eff_lang.lower() if not is_auto else None

        # In auto mode, use feature-level detect_language to quickly distinguish id/en without running a 2nd text decoding pass
        if is_auto:
            detected_lang = "id"
            try:
                detect_res = self._model.detect_language(audio)
                if isinstance(detect_res, (list, tuple)) and len(detect_res) == 3:
                    probe_lang, prob, all_probs = detect_res
                    probs_dict = dict(all_probs) if isinstance(all_probs, (list, tuple)) else {}
                    id_score = probs_dict.get("id", 0.0) + probs_dict.get("ms", 0.0)
                    en_score = probs_dict.get("en", 0.0)
                    if id_score >= en_score:
                        detected_lang = "id"
                    elif en_score > 0.4:
                        detected_lang = "en"
                    else:
                        detected_lang = "id" if probe_lang in ("id", "ms") else probe_lang
            except Exception as e:
                logger.debug("Fast language detection error: %s, defaulting to id", e)
                detected_lang = "id"

        prompt = initial_prompt or DEFAULT_INITIAL_PROMPT
        logger.info("[STT] Starting transcription (duration=%.2fs, lang_hint=%s, peak=%.4f, rms=%.4f)", duration, detected_lang, max_amp, rms_amp)

        # 1. Primary transcription pass with VAD filtering and vocabulary priming
        # VAD is trusted strictly: if VAD filters all frames, the audio is silence/noise.
        segments, info = self._model.transcribe(
            audio,
            beam_size=1,
            language=detected_lang,
            initial_prompt=prompt,
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters=dict(threshold=0.3, min_silence_duration_ms=600),
        )

        texts = [s.text.strip() for s in segments if s.text.strip()]
        transcription = " ".join(texts).strip()

        # Filter out known Whisper hallucination phrases produced during near-silence
        clean_cand = transcription.strip().lower()
        if clean_cand in WHISPER_HALLUCINATIONS or clean_cand.rstrip(".") in WHISPER_HALLUCINATIONS:
            logger.info("[STT] Filtered out Whisper silence hallucination: %r", transcription)
            transcription = ""

        elapsed = time.time() - t0
        final_lang = detected_lang or getattr(info, "language", "id")

        logger.info(
            "[STT] Completed in %.2fs: language=%s, transcript=%r (duration=%.2fs, peak=%.4f, rms=%.4f)",
            elapsed,
            final_lang,
            transcription,
            duration,
            max_amp,
            rms_amp,
        )

        return transcription, {
            "language": final_lang,
            "language_prob": getattr(info, "language_probability", 1.0) if 'info' in locals() else 0.0,
            "duration": duration,
            "transcription_time": elapsed,
            "peak": max_amp,
            "rms": rms_amp,
        }
