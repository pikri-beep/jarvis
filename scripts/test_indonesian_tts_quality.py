"""Benchmark and evaluate Indonesian Piper TTS quality, prosody, and latency."""
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import wave
from app.voice.text_to_speech import TextToSpeech, clean_text_for_speech, SentenceBuffer

def save_wav(filepath: Path, audio: np.ndarray, sample_rate: int):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())

def main():
    tts = TextToSpeech()
    tts.load_model("id")

    test_sentences = [
        ("greet", "Selamat pagi, apa kabar?"),
        ("cmd_chrome", "Baik, sekarang buka Chrome."),
        ("ram_ssd", "Saya ingin mengetahui perbedaan RAM dan SSD."),
        ("schedule", "JARVIS, tolong jelaskan jadwal saya hari ini."),
        ("open_wa", "Membuka WhatsApp, sir."),
        ("full_reply", "Tentu, sir. RAM adalah memori berkecepatan tinggi yang menyimpan data sementara saat aplikasi aktif."),
    ]

    out_dir = _ROOT / "data" / "tts_evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== Evaluating Indonesian Piper TTS (id_ID-news_tts-medium) ===")
    print(f"Model: {tts.settings.tts_model_id} | Models dir: {tts.models_dir}")
    print("-" * 65)

    results = []
    for tag, text in test_sentences:
        t0 = time.time()
        audio, sr = tts.synthesize(text, language="id")
        dt = time.time() - t0

        if audio is not None and len(audio) > 0:
            duration = len(audio) / sr
            rtf = dt / duration if duration > 0 else 0.0
            peak = int(np.max(np.abs(audio)))
            wav_path = out_dir / f"id_{tag}.wav"
            save_wav(wav_path, audio, sr)

            print(f"Sentence: \"{text}\"")
            print(f"  -> Synth time: {dt:.3f}s | Duration: {duration:.2f}s | RTF: {rtf:.3f} | SR: {sr}Hz | Peak: {peak}")
            print(f"  -> Saved WAV: {wav_path}")
            print("-" * 65)

            results.append({
                "tag": tag,
                "text": text,
                "synth_time": dt,
                "duration": duration,
                "rtf": rtf,
                "sr": sr,
                "peak": peak,
            })

    # Test SentenceBuffer streaming simulation
    print("\n=== SentenceBuffer Streaming Test (comparing comma split vs sentence split) ===")
    sample_text = "Tentu, sir. RAM adalah memori berkecepatan tinggi yang menyimpan data sementara saat aplikasi aktif."
    
    # Mode A: with comma splitting (legacy)
    buf_a = SentenceBuffer(min_chars=12, early_first_chunk=True)
    tokens = sample_text.split(" ")
    chunks_a = []
    for tok in tokens:
        for s in buf_a.feed(tok + " "):
            chunks_a.append(s)
    chunks_a.extend(buf_a.flush())
    print("Mode A (early comma split chunks):", chunks_a)

    # Mode B: without comma splitting (full sentence boundary)
    buf_b = SentenceBuffer(min_chars=12, early_first_chunk=False)
    chunks_b = []
    for tok in tokens:
        for s in buf_b.feed(tok + " "):
            chunks_b.append(s)
    chunks_b.extend(buf_b.flush())
    print("Mode B (sentence boundary chunks):", chunks_b)

if __name__ == "__main__":
    main()
