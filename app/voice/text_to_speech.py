"""Local Text-to-Speech (TTS) module using Piper.

Provides offline, low-latency, sentence-buffered streaming speech synthesis
outputting to the default Windows audio device without blocking the application.
"""

import os
import queue
import re
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Generator, List, Optional, Tuple, Union
import numpy as np

from app.core.config import Settings, get_settings
from app.core.logger import setup_logger

logger = setup_logger("jarvis.voice.tts")


# Indonesian common stopwords, grammatical markers, and conversational terms
_ID_STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "untuk", "pada", "adalah", "dengan",
    "saya", "kamu", "anda", "apa", "bisa", "tolong", "selamat", "pagi", "siang", "sore",
    "malam", "bagaimana", "mengapa", "kenapa", "baik", "sekarang", "buka", "tutup", "apakah",
    "ingin", "tahu", "mengetahui", "perbedaan", "jadwal", "hari", "terima", "kasih", "halo",
    "hai", "tidak", "bukan", "ada", "sudah", "belum", "akan", "sedang", "tentu", "maaf",
    "mohon", "kami", "kita", "mereka", "ia", "dia", "seperti", "karena", "jika", "kalau",
    "tapi", "tetapi", "juga", "hanya", "semua", "banyak", "sedikit", "saja", "lagi",
    "kembali", "tentang", "sama", "bantu", "membantu", "membuat", "menjelaskan", "penjelasan",
    "singkat", "antara", "berikut", "memori", "sementara", "penyimpanan", "permanen", "membuka",
    "menutup", "pukul", "jam", "siap", "dibutuhkan", "proses", "sistem", "operasi", "kabar",
    "komputer", "layar", "suara", "volume", "tangkapan", "kunci", "matikan", "jalankan",
    "catatan", "berjalan", "berhasil", "gagal", "ditemukan", "cara", "kerja", "dibandingkan",
    "lebih", "cepat", "lambat", "tips", "trik", "efisien", "alat", "hitung", "pengaturan",
    "setelan", "berkas", "folder", "penjelajah", "pesan", "pribadi", "yakin", "melanjutkan",
    "dibatalkan", "menampilkan", "melibatkan", "izin", "akses", "ditolak", "senyap", "daya",
    "mengisi", "menggunakan", "memakai", "dimana", "kapan", "siapa", "mengunci", "mengambil",
    "menaikkan", "menurunkan", "kedua", "ketiga", "pertama", "utama", "dalam", "luar"
}

# English common stopwords, grammatical markers, and assistant response terms
_EN_STOPWORDS = {
    "the", "is", "are", "and", "to", "of", "in", "that", "it", "you", "for", "on", "with",
    "as", "at", "this", "be", "have", "from", "or", "one", "by", "but", "not", "what", "all",
    "were", "we", "when", "your", "can", "said", "there", "use", "an", "each", "which",
    "she", "do", "how", "their", "if", "will", "up", "other", "about", "out", "many", "then",
    "them", "these", "so", "some", "her", "would", "make", "like", "him", "into", "time",
    "has", "look", "two", "more", "write", "go", "see", "number", "no", "way", "could",
    "people", "my", "than", "first", "been", "call", "who", "its", "now", "find",
    "open", "close", "launch", "start", "stop", "exit", "quit", "help", "hello", "hi", "hey",
    "yes", "please", "system", "computer", "screen", "volume", "date", "today", "tomorrow",
    "weather", "news", "difference", "schedule", "sir", "opening", "closing", "taking",
    "screenshot", "increasing", "decreasing", "toggling", "locking", "here", "ready",
    "assist", "sure", "certainly", "storage", "faster", "slower", "volatile", "non-volatile",
    "tips", "productivity", "battery", "charging", "status", "running", "cancelled",
    "proceed", "access", "personal", "messages", "want", "shutting", "down", "good",
    "day", "cleared", "available", "offline", "online", "currently", "normal", "power",
    "percent", "level", "explain", "processor", "memory", "between", "versus", "second"
}


def detect_language(text: str, default: str = "en") -> str:
    """Lightweight, offline language detector distinguishing Indonesian ('id') and English ('en')."""
    if not text or not text.strip():
        return default

    cleaned = text.lower()
    words = re.findall(r"\b[a-z]{2,}\b", cleaned)
    if not words:
        return default

    id_count = sum(1 for w in words if w in _ID_STOPWORDS)
    en_count = sum(1 for w in words if w in _EN_STOPWORDS)

    # Check common English contractions
    en_contractions = len(re.findall(r"\b(?:i'm|it's|that's|what's|don't|doesn't|can't|won't|there's|you're)\b", cleaned))
    en_count += en_contractions * 2

    # Check English morphological markers (-ing, -tion, -ment, -ness, -able, -ly)
    en_suffixes = sum(
        1 for w in words
        if len(w) >= 5 and w.endswith(("ing", "tion", "ment", "ness", "able", "ible", "ly"))
        and w not in _ID_STOPWORDS
    )
    en_count += en_suffixes

    # Check Indonesian affixes (me-, ber-, di-, ter-, se-, ke-, -kan, -nya, -lah, -kah)
    id_affixes = sum(
        1 for w in words
        if len(w) >= 4 and (
            w.startswith(("me", "ber", "ter", "se", "di", "pe"))
            or w.endswith(("kan", "nya", "lah", "kah", "pun"))
        )
        and w not in _EN_STOPWORDS
    )
    id_count += id_affixes

    if id_count > en_count:
        return "id"
    elif en_count > id_count:
        return "en"

    return default


def is_explicit_language_switch(text: str) -> Optional[str]:
    """Detects explicit conversational instructions to switch language."""
    lower = text.strip().lower()

    # Explicit switch to English
    if re.search(
        r"\b(?:switch to english|speak in english|speak english|talk in english|use english|in english|ganti (?:ke )?bahasa inggris|bicara bahasa inggris|pakai bahasa inggris|gunakan bahasa inggris)\b",
        lower,
    ):
        return "en"

    # Explicit switch to Indonesian
    if re.search(
        r"\b(?:switch to indonesian|speak in indonesian|speak indonesian|talk in indonesian|use indonesian|in indonesian|ganti (?:ke )?bahasa indonesia|bicara bahasa indonesia|pakai bahasa indonesia|gunakan bahasa indonesia|dalam bahasa indonesia)\b",
        lower,
    ):
        return "id"

    return None


def resolve_conversation_language(user_input: str, current_lang: str) -> str:
    """Maintains consistent conversation language with hysteresis unless the user switches languages."""
    # 1. Check explicit conversational language switch
    explicit = is_explicit_language_switch(user_input)
    if explicit:
        return explicit

    # 2. Extract words
    words = re.findall(r"\b[a-z]{2,}\b", user_input.lower())
    if not words:
        return current_lang

    id_count = sum(1 for w in words if w in _ID_STOPWORDS)
    en_count = sum(1 for w in words if w in _EN_STOPWORDS)

    # Check morphological markers
    id_affixes = sum(
        1 for w in words
        if len(w) >= 4 and (
            w.startswith(("me", "ber", "ter", "se", "di"))
            or w.endswith(("kan", "nya", "lah", "kah"))
        )
    )
    en_suffixes = sum(
        1 for w in words
        if len(w) >= 5 and w.endswith(("ing", "tion", "ment", "ness", "able", "ly"))
    )

    id_total = id_count + id_affixes
    en_total = en_count + en_suffixes

    # If no language markers detected (e.g. single app name "chrome", numbers, "ok"), retain current language
    if id_total == 0 and en_total == 0:
        return current_lang

    # If purely English markers present without Indonesian words:
    if en_total > 0 and id_total == 0:
        return "en"

    # If purely Indonesian markers present without English words:
    if id_total > 0 and en_total == 0:
        return "id"

    # Mixed markers: apply hysteresis favoring current conversation language
    if current_lang.startswith("id"):
        return "en" if en_total > id_total + 1 else "id"
    else:
        return "id" if id_total > en_total + 1 else "en"


def normalize_indonesian_phonetics(text: str) -> str:
    """Normalizes technical acronyms and loanwords for Indonesian Piper neural TTS."""
    if not text:
        return ""
    # Software & platforms
    text = re.sub(r"\bchrome\b", "Krom", text, flags=re.IGNORECASE)
    text = re.sub(r"\bgoogle\b", "Gugel", text, flags=re.IGNORECASE)
    text = re.sub(r"\bwhats\s*app\b", "Watsap", text, flags=re.IGNORECASE)
    text = re.sub(r"\bwa\b", "We-A", text, flags=re.IGNORECASE)
    text = re.sub(r"\bwindows\b", "Windos", text, flags=re.IGNORECASE)
    text = re.sub(r"\bedge\b", "Ej", text, flags=re.IGNORECASE)
    text = re.sub(r"\bspotify\b", "Spotifai", text, flags=re.IGNORECASE)
    text = re.sub(r"\byoutube\b", "Yutub", text, flags=re.IGNORECASE)
    text = re.sub(r"\bvs\s*code\b", "Vi-Es Kod", text, flags=re.IGNORECASE)
    text = re.sub(r"\bvscode\b", "Vi-Es Kod", text, flags=re.IGNORECASE)
    text = re.sub(r"\bjarvis\b", "Jarvis", text, flags=re.IGNORECASE)

    # Technical abbreviations & hardware
    text = re.sub(r"\bram\b", "Rem", text, flags=re.IGNORECASE)
    text = re.sub(r"\bssd\b", "Es-Es-De", text, flags=re.IGNORECASE)
    text = re.sub(r"\bpc\b", "Pi-Si", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcpu\b", "Se-Pe-U", text, flags=re.IGNORECASE)
    text = re.sub(r"\bgpu\b", "Ge-Pe-U", text, flags=re.IGNORECASE)
    text = re.sub(r"\bai\b", "A-I", text, flags=re.IGNORECASE)
    text = re.sub(r"\bos\b", "O-Es", text, flags=re.IGNORECASE)
    text = re.sub(r"\burl\b", "U-R-L", text, flags=re.IGNORECASE)
    text = re.sub(r"\bapi\b", "A-P-I", text, flags=re.IGNORECASE)
    text = re.sub(r"\bwifi\b", "Way-Fay", text, flags=re.IGNORECASE)

    # Units and numbers
    text = re.sub(r"\b(\d+)\s*%", r"\1 persen", text)
    text = re.sub(r"\b(\d+)\s*gb\b", r"\1 Giga", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\d+)\s*mb\b", r"\1 Mega", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\d+)\s*tb\b", r"\1 Tera", text, flags=re.IGNORECASE)
    # Time format e.g. 09.30 -> 9 lewat 30
    text = re.sub(r"\b(\d{1,2})\.(\d{2})\b", r"\1 lewat \2", text)

    return text


def clean_text_for_speech(text: str, language: str = "auto") -> str:

    """Cleans markdown, URLs, code blocks, and emojis for natural speech synthesis."""
    if not text or not text.strip():
        return ""

    # Strip out trailing source citations section completely so TTS never reads it aloud
    cleaned = re.split(r"(?:\r?\n)+(?:sumber(?:\s+terkait)?|sources?|rujukan)\s*:", text, flags=re.IGNORECASE)[0]
    # Strip out trailing UI tips and instructions from speech
    cleaned = re.split(r"(?:\r?\n)+\*?(?:tip|catatan\s+tambahan)\s*:", cleaned, flags=re.IGNORECASE)[0]

    # Remove emojis and miscellaneous non-text unicode symbols
    cleaned = re.sub(r"[\U00010000-\U0010ffff]", "", cleaned)
    cleaned = re.sub(r"[\u2600-\u27bf]", "", cleaned)

    # Remove markdown images ![alt](url)
    cleaned = re.sub(r"!\[[^\]]*\]\([^\)]+\)", " ", cleaned)
    # Filter out pure citation blocks or UI metadata lines so they are not spoken aloud
    low_strip = cleaned.strip().lower()
    if "cheatsheet" in low_strip or "quick cheatsheet" in low_strip or low_strip.startswith("commands available:"):
        return ""
    if low_strip.startswith((
        "sumber:", "sumber :", "source:", "sources:",
        "[screen]", "* active window:", "* local vision model:", "* extracted content:"
    )):
        return ""

    # Remove code blocks ```...```
    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)
    # Remove inline code `...`
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    # Replace markdown links [text](url) -> text
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    # Remove markdown headers (#, ##, etc.)
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    # Remove bold/italic markers (* or _)
    cleaned = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", cleaned)
    # Remove markdown bullet points (- or *)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    # Remove blockquotes >
    cleaned = re.sub(r"^\s*>\s*", "", cleaned, flags=re.MULTILINE)
    # Replace standalone URLs
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    # Remove stray markdown symbols and dashes
    cleaned = re.sub(r"[>#*`~\[\]]", " ", cleaned)
    cleaned = re.sub(r"--+", " ", cleaned)
    # Normalize multiple whitespace/newlines
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if language.startswith("id") or (language == "auto" and detect_language(cleaned) == "id"):
        cleaned = normalize_indonesian_phonetics(cleaned)

    return cleaned


normalize_text_for_speech = clean_text_for_speech


class SentenceBuffer:
    """Buffers streaming LLM tokens into complete, natural spoken sentences."""

    _ABBREVIATIONS = {
        "mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "vs.",
        "etc.", "e.g.", "i.e.", "approx.", "st.", "ai.", "no.", "vol."
    }

    _SENTENCE_TERMINATORS = re.compile(r"([.!?]+(?:\s+|$)|[\n\r]+)")
    _LONG_CLAUSE_TERMINATORS = re.compile(r"([,;:!?.]+(?:\s+|$)|[\n\r]+)")

    def __init__(self, min_chars: int = 14, max_clause_chars: int = 40, early_first_chunk: bool = False):
        self.min_chars = min_chars
        self.max_clause_chars = max_clause_chars
        self.early_first_chunk = early_first_chunk
        self._first_chunk_emitted = False
        self._buffer = ""

    def feed(self, token: str) -> List[str]:
        """Feeds a token and returns any newly completed natural sentences."""
        self._buffer += token
        sentences = []

        # Only use comma/semicolon clause boundary if early_first_chunk is set or buffer is long
        # Default keeps short phrases intact for natural melodic prosody
        if self.early_first_chunk and not self._first_chunk_emitted:
            active_regex = self._LONG_CLAUSE_TERMINATORS
        elif len(self._buffer) >= self.max_clause_chars:
            active_regex = self._LONG_CLAUSE_TERMINATORS
        else:
            active_regex = self._SENTENCE_TERMINATORS

        parts = active_regex.split(self._buffer)
        if len(parts) > 2:
            current = ""
            for i in range(0, len(parts) - 1, 2):
                seg = parts[i]
                term = parts[i + 1]
                current += seg + term

                # Check if this terminator is an abbreviation or decimal number
                words = current.strip().lower().split()
                last_word = words[-1] if words else ""

                if last_word in self._ABBREVIATIONS or re.search(r"\d+\.\d*$", current.strip()):
                    continue

                if len(current.strip()) >= self.min_chars:
                    clean = clean_text_for_speech(current)
                    if clean:
                        sentences.append(clean)
                        self._first_chunk_emitted = True
                    current = ""

            self._buffer = current + parts[-1]

        return sentences

    def flush(self) -> List[str]:
        """Flushes remaining buffered text at end of stream."""
        remaining = clean_text_for_speech(self._buffer)
        self._buffer = ""
        if remaining:
            return [remaining]
        return []


class AudioPlaybackQueue:
    """Thread-safe background queue for continuous, non-blocking audio playback."""

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._is_playing = threading.Event()
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def _worker_loop(self) -> None:
        import sounddevice as sd

        current_stream = None
        current_sr = None

        while True:
            try:
                # Wait for next audio chunk with an idle timeout
                try:
                    item = self._queue.get(timeout=1.5)
                except queue.Empty:
                    # Release audio device when playback has been idle for 1.5s
                    if current_stream is not None:
                        try:
                            current_stream.stop()
                            current_stream.close()
                        except Exception:
                            pass
                        current_stream = None
                        current_sr = None
                    continue

                if item is None:
                    break

                if self._stop_event.is_set():
                    if current_stream is not None:
                        try:
                            current_stream.stop()
                            current_stream.close()
                        except Exception:
                            pass
                        current_stream = None
                        current_sr = None
                    self._queue.task_done()
                    continue

                audio_data, sample_rate = item
                if audio_data is not None and len(audio_data) > 0 and not self._stop_event.is_set():
                    self._is_playing.set()
                    try:
                        # Seamless continuous stream: avoid closing/re-opening device between chunks
                        if current_stream is None or current_sr != sample_rate:
                            if current_stream is not None:
                                try:
                                    current_stream.stop()
                                    current_stream.close()
                                except Exception:
                                    pass
                            current_stream = sd.OutputStream(
                                samplerate=sample_rate,
                                channels=1,
                                dtype="int16",
                            )
                            current_stream.start()
                            current_sr = sample_rate

                        # Play in 512-sample slices (~32ms per slice) for near-instant, 100% thread-safe stopping
                        chunk_size = 512
                        for offset in range(0, len(audio_data), chunk_size):
                            if self._stop_event.is_set():
                                break
                            chunk = audio_data[offset : offset + chunk_size]
                            current_stream.write(chunk)

                        if self._stop_event.is_set() and current_stream is not None:
                            try:
                                current_stream.stop()
                                current_stream.close()
                            except Exception:
                                pass
                            current_stream = None
                            current_sr = None

                    except Exception as e:
                        if not self._stop_event.is_set():
                            logger.error("Audio playback error: %s", e)
                        if current_stream is not None:
                            try:
                                current_stream.close()
                            except Exception:
                                pass
                            current_stream = None
                            current_sr = None
                    finally:
                        self._is_playing.clear()

                self._queue.task_done()
            except Exception as e:
                logger.error("Unexpected error in AudioPlaybackQueue: %s", e)

    def enqueue(self, audio: np.ndarray, sample_rate: int) -> None:
        """Adds an audio buffer to the playback queue."""
        self._stop_event.clear()
        self._queue.put((audio, sample_rate))

    def stop(self) -> None:
        """Immediately halts current audio playback and empties remaining queue."""
        self._stop_event.set()

        # Drain the queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

        self._is_playing.clear()

    def wait_until_done(self, timeout: Optional[float] = None) -> None:
        """Blocks until all queued audio has finished playing."""
        start = time.time()
        while self.is_playing() and not self._stop_event.is_set():
            if timeout and (time.time() - start) > timeout:
                break
            time.sleep(0.02)

    def is_playing(self) -> bool:
        """Returns True if audio is actively playing or queued."""
        return self._is_playing.is_set() or not self._queue.empty()


class TextToSpeech:
    """Local Text-to-Speech synthesis engine using Piper with sentence streaming."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.enabled = self.settings.tts_enabled
        self.models_dir = Path(self.settings.tts_models_dir)
        self.playback_queue = AudioPlaybackQueue()
        self._voices: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def _get_model_path(self, language: str = "en") -> Tuple[Path, Path]:
        """Resolves local model and json config paths for given language."""
        if language.lower().startswith("id"):
            model_name = self.settings.tts_model_id
        else:
            model_name = self.settings.tts_model_en

        if not model_name.endswith(".onnx"):
            model_name += ".onnx"

        onnx_path = self.models_dir / model_name
        json_path = self.models_dir / f"{model_name}.json"
        return onnx_path, json_path

    def load_model(self, language: str = "en") -> bool:
        """Loads the Piper voice model into memory for the requested language."""
        lang_key = "id" if language.lower().startswith("id") else "en"
        with self._lock:
            if lang_key in self._voices and self._voices[lang_key] is not None:
                return True

            onnx_path, json_path = self._get_model_path(lang_key)

            # Auto-download from HuggingFace if not already cached locally
            if not onnx_path.exists() or not json_path.exists():
                logger.info("Piper model '%s' not found locally. Downloading...", onnx_path.name)
                try:
                    from huggingface_hub import hf_hub_download
                    self.models_dir.mkdir(parents=True, exist_ok=True)
                    hf_repo = "rhasspy/piper-voices"
                    
                    if lang_key == "id":
                        src_model = "id/id_ID/news_tts/medium/id_ID-news_tts-medium.onnx"
                    else:
                        src_model = "en/en_GB/alan/low/en_GB-alan-low.onnx"

                    src_json = src_model + ".json"
                    downloaded_onnx = hf_hub_download(hf_repo, src_model)
                    downloaded_json = hf_hub_download(hf_repo, src_json)

                    import shutil
                    shutil.copy2(downloaded_onnx, onnx_path)
                    shutil.copy2(downloaded_json, json_path)
                    logger.info("Piper voice model successfully cached to %s", onnx_path)
                except Exception as e:
                    logger.error("Failed to download Piper model: %s", e)
                    return False

            try:
                from piper import PiperVoice

                t0 = time.time()
                voice = PiperVoice.load(str(onnx_path), config_path=str(json_path))
                self._voices[lang_key] = voice
                logger.info(
                    "Piper voice '%s' loaded in %.2fs (rate: %d Hz)",
                    onnx_path.name,
                    time.time() - t0,
                    voice.config.sample_rate,
                )
                return True
            except Exception as e:
                logger.error("Failed to load Piper voice from %s: %s", onnx_path, e)
                return False

    def is_loaded(self, language: str = "en") -> bool:
        """Returns True if the requested voice model is currently in memory."""
        lang_key = "id" if language.lower().startswith("id") else "en"
        return lang_key in self._voices and self._voices[lang_key] is not None

    def synthesize(self, text: str, language: str = "auto") -> Tuple[Optional[np.ndarray], int]:
        """Synthesizes text into a NumPy int16 audio array and sample rate.

        Args:
            text: Text to synthesize.
            language: Target language ('auto', 'en', or 'id').

        Returns:
            Tuple of (audio_int16_array, sample_rate). Returns (None, 0) if text is empty/silent.
        """
        if language == "auto" or not language:
            target_lang = detect_language(text)
        else:
            target_lang = language

        cleaned = clean_text_for_speech(text, language=target_lang)
        if not cleaned:
            return None, 0

        # Don't synthesize pure punctuation
        if not re.search(r"\w", cleaned):
            return None, 0

        lang_key = "id" if target_lang.lower().startswith("id") else "en"
        if not self.is_loaded(lang_key):
            success = self.load_model(lang_key)
            if not success:
                return None, 0

        voice = self._voices[lang_key]
        sample_rate = voice.config.sample_rate

        try:
            from piper.config import SynthesisConfig
            rate = getattr(self.settings, "tts_rate", 1.0)
            syn_cfg = SynthesisConfig(length_scale=1.0 / max(0.5, min(2.0, rate))) if rate != 1.0 else None
            chunks = list(voice.synthesize(cleaned, syn_config=syn_cfg))
            if not chunks:
                return None, sample_rate

            arrays = [c.audio_int16_array for c in chunks if len(c.audio_int16_array) > 0]
            if not arrays:
                return None, sample_rate

            audio_data = np.concatenate(arrays)
            # Headroom normalization to prevent clipping/distortion
            peak = float(np.max(np.abs(audio_data)))
            if peak > 28000:
                audio_data = (audio_data * (28000.0 / peak)).astype(np.int16)

            return audio_data, sample_rate
        except Exception as e:
            logger.error("Synthesis error for '%s': %s", cleaned[:30], e)
            return None, sample_rate

    def speak(self, text: str, blocking: bool = False, language: str = "auto") -> float:
        """Synthesizes and speaks text out loud through the default audio output.

        Args:
            text: Text to speak.
            blocking: If True, waits until speech finishes playing before returning.
            language: Speech language ('auto', 'en', or 'id').

        Returns:
            Duration of spoken audio in seconds.
        """
        if not self.enabled:
            return 0.0

        if language == "auto" or not language:
            language = detect_language(text)

        audio, sample_rate = self.synthesize(text, language=language)
        if audio is None or len(audio) == 0:
            return 0.0

        duration = len(audio) / sample_rate
        self.playback_queue.enqueue(audio, sample_rate)

        if blocking:
            self.playback_queue.wait_until_done()

        return duration

    def speak_stream(
        self,
        token_generator: Generator[str, None, None],
        language: str = "auto",
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, float]:
        """Consumes a streaming token generator, buffering by sentence for low-latency TTS.

        Plays sentences sequentially through the audio queue as they complete,
        minimizing the time until the user hears the first spoken words.

        Args:
            token_generator: Generator producing response text tokens.
            language: Language code ('auto', 'en', or 'id').
            on_token: Optional callback called as each token arrives (e.g. for terminal printing).

        Returns:
            Dictionary with timing metrics ('ttfa', 'total_speech_s', 'sentences_count').
        """
        t_start = time.time()
        ttfa: Optional[float] = None
        total_audio_samples = 0
        sample_rate = 16000
        sentences_count = 0

        sentence_buffer = SentenceBuffer(min_chars=14, early_first_chunk=True)
        active_lang = language

        for token in token_generator:
            if self.playback_queue._stop_event.is_set():
                break

            if on_token:
                on_token(token)

            if not self.enabled:
                continue

            new_sentences = sentence_buffer.feed(token)
            for sentence in new_sentences:
                sentences_count += 1
                sentence_lang = detect_language(sentence, default=active_lang if active_lang != "auto" else "en")
                audio, sr = self.synthesize(sentence, language=sentence_lang)
                if audio is not None and len(audio) > 0:
                    sample_rate = sr
                    total_audio_samples += len(audio)
                    if ttfa is None:
                        ttfa = time.time() - t_start
                    self.playback_queue.enqueue(audio, sr)

        # Flush any trailing sentence fragment
        if self.enabled:
            remaining = sentence_buffer.flush()
            for sentence in remaining:
                sentences_count += 1
                sentence_lang = detect_language(sentence, default=active_lang if active_lang != "auto" else "en")
                audio, sr = self.synthesize(sentence, language=sentence_lang)
                if audio is not None and len(audio) > 0:
                    sample_rate = sr
                    total_audio_samples += len(audio)
                    if ttfa is None:
                        ttfa = time.time() - t_start
                    self.playback_queue.enqueue(audio, sr)

        total_speech_s = total_audio_samples / sample_rate if sample_rate else 0.0

        return {
            "ttfa": ttfa if ttfa is not None else 0.0,
            "total_speech_s": total_speech_s,
            "sentences_count": sentences_count,
        }

    def stop(self) -> None:
        """Immediately stops all audio playback."""
        self.playback_queue.stop()

    def is_speaking(self) -> bool:
        """Returns True if speech playback is active."""
        return self.playback_queue.is_playing()

    def wait_until_done(self, timeout: Optional[float] = None) -> None:
        """Waits until all queued speech has finished playing."""
        self.playback_queue.wait_until_done(timeout=timeout)
