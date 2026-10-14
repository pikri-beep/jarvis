"""Human Voice Synthesizer for Simulated User Agent using Edge-TTS.

Generates natural human-like voice audio (English and Indonesian) converted to
16000Hz mono 16-bit PCM numpy arrays for injection into JARVIS's wake-word/STT pipeline.
"""

import asyncio
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Dict, Optional
import numpy as np

from app.core.logger import setup_logger

logger = setup_logger("jarvis.simulator.voice")

# Standard High-Fidelity Human Voices
DEFAULT_VOICES = {
    "en_male": "en-US-GuyNeural",
    "en_female": "en-US-JennyNeural",
    "id_male": "id-ID-ArdiNeural",
    "id_female": "id-ID-GadisNeural",
}


class EdgeTTSVoiceSynthesizer:
    """Synthesizes human speech using Microsoft Edge-TTS and converts to 16kHz mono PCM."""

    def __init__(
        self,
        default_voice: str = "en-US-GuyNeural",
        cache_dir: Optional[Path] = None,
    ):
        self.default_voice = default_voice
        self.cache_dir = cache_dir or (Path(__file__).resolve().parent / "audio_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, np.ndarray] = {}
        self._lock = threading.Lock()

    def _get_ffmpeg_path(self) -> str:
        """Resolves ffmpeg executable."""
        return "ffmpeg"

    def _decode_mp3_to_pcm(self, mp3_bytes: bytes) -> np.ndarray:
        """Decodes MP3 byte stream into 16000Hz mono int16 PCM array using ffmpeg."""
        cmd = [
            self._get_ffmpeg_path(),
            "-y",
            "-loglevel", "error",
            "-i", "pipe:0",
            "-f", "s16le",
            "-ar", "16000",
            "-ac", "1",
            "pipe:1",
        ]
        proc = subprocess.run(cmd, input=mp3_bytes, capture_output=True, check=True)
        return np.frombuffer(proc.stdout, dtype=np.int16)

    async def _synthesize_async(self, text: str, voice: str) -> np.ndarray:
        """Asynchronously calls edge_tts to generate speech audio."""
        import edge_tts

        communicate = edge_tts.Communicate(text, voice)
        mp3_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_chunks.append(chunk["data"])

        if not mp3_chunks:
            raise RuntimeError(f"Edge-TTS produced no audio for text: '{text}'")

        mp3_bytes = b"".join(mp3_chunks)
        return self._decode_mp3_to_pcm(mp3_bytes)

    def _synthesize_offline_fallback(self, text: str) -> np.ndarray:
        """Offline fallback using Windows SAPI (System.Speech) if internet/Edge-TTS fails."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                wav_path = tf.name

            ps_script = f"""
Add-Type -AssemblyName System.Speech
$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speak.SetOutputToWaveFile('{wav_path}')
$speak.Speak('{text.replace("'", "''")}')
$speak.Dispose()
"""
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True, capture_output=True)

            cmd = [
                self._get_ffmpeg_path(),
                "-y",
                "-loglevel", "error",
                "-i", wav_path,
                "-f", "s16le",
                "-ar", "16000",
                "-ac", "1",
                "pipe:1",
            ]
            proc = subprocess.run(cmd, capture_output=True, check=True)
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except OSError:
                    pass
            return np.frombuffer(proc.stdout, dtype=np.int16)
        except Exception as e:
            logger.warning("Offline SAPI fallback failed (%s); generating synthetic tone burst", e)
            duration = max(1.0, len(text) * 0.08)
            t = np.linspace(0, duration, int(16000 * duration), endpoint=False)
            sine = (np.sin(2 * np.pi * 440 * t) * 5000).astype(np.int16)
            return sine

    def synthesize(self, text: str, voice: Optional[str] = None) -> np.ndarray:
        """Synthesizes text into 16000Hz mono int16 PCM numpy array.

        Args:
            text: Sentence or phrase to speak (e.g. "Hey Jarvis, open Chrome").
            voice: Voice identifier (defaults to self.default_voice).

        Returns:
            np.ndarray: int16 array of 16kHz audio samples.
        """
        clean_text = text.strip()
        if not clean_text:
            return np.zeros(16000, dtype=np.int16)

        selected_voice = voice or self.default_voice

        # Check memory cache
        cache_key = f"{selected_voice}::{clean_text}"
        with self._lock:
            if cache_key in self._memory_cache:
                return self._memory_cache[cache_key].copy()

        try:
            pcm = asyncio.run(self._synthesize_async(clean_text, selected_voice))
        except Exception as e:
            logger.warning("Edge-TTS synthesis error for '%s' (%s); using offline fallback", clean_text, e)
            pcm = self._synthesize_offline_fallback(clean_text)

        with self._lock:
            self._memory_cache[cache_key] = pcm.copy()

        return pcm
