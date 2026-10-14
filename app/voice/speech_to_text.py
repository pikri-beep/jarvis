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
    "JARVIS assistant. Percakapan dwibahasa Indonesia dan Inggris. "
    "Music: Play Creep by Radiohead, Putar lagu Creep Radiohead, Bohemian Rhapsody by Queen, "
    "Yellow by Coldplay, Nirvana, Adele, Taylor Swift, YouTube Music, Spotify. "
    "Apps: Buka Chrome, Google Chrome, YouTube, Discord, WhatsApp, Notepad, Calculator, Settings, File Explorer. "
    "Commands: Play it, pause music, resume playback, next track, take screenshot, volume up, volume down, info sistem."
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

        try:
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=num_threads,
            )
        except Exception as e:
            logger.error("Failed to load faster-whisper model '%s': %s", self.model_size, e)
            raise RuntimeError(
                f"Gagal memuat model STT '{self.model_size}': {e}. "
                "Pastikan koneksi internet aktif saat pertama kali mengunduh model, "
                "atau setel JARVIS_STT_MODEL=base di berkas .env."
            ) from e

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

        # Convert to float32 and normalize int16 or unscaled audio to [-1.0, 1.0]
        if np.issubdtype(audio.dtype, np.integer):
            audio = np.squeeze(audio).astype(np.float32) / 32768.0
        else:
            audio = np.squeeze(audio).astype(np.float32)
            if len(audio) > 0 and float(np.max(np.abs(audio))) > 1.5:
                audio = audio / 32768.0

        duration = len(audio) / sample_rate
        if duration < 0.2:
            logger.debug("Audio duration too short (%.2fs), skipping transcription.", duration)
            return "", {"language": "", "language_prob": 0.0, "duration": duration, "peak": 0.0, "rms": 0.0, "transcription_time": 0.0}

        # Step 1: DC-Offset filtering (removes microphone hardware ADC bias)
        if len(audio) > 0:
            audio = audio - float(np.mean(audio))

        max_amp = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0
        rms_amp = float(np.sqrt(np.mean(audio**2))) if len(audio) > 0 else 0.0

        # Pre-STT silence & ambient noise gate: rejects pure noise or silence before neural decoding
        if max_amp < 0.003 or rms_amp < 0.0008:
            logger.debug(
                "Audio energy below threshold (peak=%.4f, rms=%.4f), rejecting as silence.",
                max_amp,
                rms_amp,
            )
            return "", {"language": "", "language_prob": 0.0, "duration": duration, "peak": max_amp, "rms": rms_amp, "transcription_time": 0.0}

        # Step 2: Gentle peak normalization with soft limiter (avoids noise floor explosion)
        if max_amp > 0.0001 and max_amp < 0.50:
            gain = min(8.0, 0.70 / max(max_amp, 0.001))
            audio = np.clip(audio * gain, -1.0, 1.0)
            max_amp = float(np.max(np.abs(audio)))
            rms_amp = float(np.sqrt(np.mean(audio**2)))

        if self._model is None:
            self.load_model()

        eff_lang = language if language is not None else self.language
        is_auto = not eff_lang or eff_lang.lower() == "auto"

        t0 = time.time()
        detected_lang = eff_lang.lower() if not is_auto else None

        # In auto mode, use feature-level detect_language to distinguish pure id vs en,
        # but do not force 'id' clamp on code-switching utterances so English words remain intact!
        if is_auto:
            detected_lang = None
            try:
                detect_res = self._model.detect_language(audio)
                if isinstance(detect_res, (list, tuple)) and len(detect_res) == 3:
                    probe_lang, prob, all_probs = detect_res
                    probs_dict = dict(all_probs) if isinstance(all_probs, (list, tuple)) else {}
                    id_score = probs_dict.get("id", 0.0) + probs_dict.get("ms", 0.0)
                    en_score = probs_dict.get("en", 0.0)
                    if en_score > 0.65 and en_score > id_score:
                        detected_lang = "en"
                    elif id_score > 0.85 and en_score < 0.10:
                        detected_lang = "id"
                    else:
                        # Bilingual code-switching mode: do not clamp language token
                        detected_lang = None
            except Exception as e:
                logger.debug("Fast language detection error: %s", e)
                detected_lang = None

        prompt = initial_prompt or DEFAULT_INITIAL_PROMPT
        logger.info("[STT] Starting transcription (duration=%.2fs, lang_hint=%s, peak=%.4f, rms=%.4f)", duration, detected_lang, max_amp, rms_amp)

        # 1. Primary transcription pass with beam_size=2 and vocabulary priming
        segments, info = self._model.transcribe(
            audio,
            beam_size=2,
            best_of=2,
            temperature=0.0,
            language=detected_lang,
            initial_prompt=prompt,
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters=dict(threshold=0.3, min_silence_duration_ms=600),
        )

        texts = [s.text.strip() for s in segments if s.text.strip()]
        transcription = " ".join(texts).strip()

        # Clean abnormal Whisper comma stutter between words (e.g. 'Play, grip.' -> 'Play grip.')
        if transcription:
            import re
            transcription = re.sub(r'(\b\w+),\s+(\w+\b)', r'\1 \2', transcription)

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
