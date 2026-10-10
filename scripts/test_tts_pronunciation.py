"""Test Indonesian TTS lexical and phonetic normalization for natural pronunciation."""
import sys
import time
import wave
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
from app.voice.text_to_speech import TextToSpeech

def save_wav(path: Path, audio: np.ndarray, sr: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())

def main():
    tts = TextToSpeech()
    tts.load_model("id")

    test_pairs = [
        ("chrome_raw", "Membuka Chrome, sir.", "Membuka Krom, sir."),
        ("wa_raw", "Membuka WhatsApp sekarang.", "Membuka Watsap sekarang."),
        ("ram_ssd", "RAM dan SSD memiliki fungsi berbeda pada PC Anda.", "Rem dan Es-Es-De memiliki fungsi berbeda pada Pi-Si Anda."),
        ("sys_spec", "Sistem memiliki 16 GB memori dan CPU Intel Core i5.", "Sistem memiliki 16 Giga memori dan Se-Pe-U Intel Kor i5."),
        ("greet_jarvis", "Halo JARVIS, apa kabar?", "Halo Jarvis, apa kabar?"),
    ]

    out_dir = _ROOT / "data" / "tts_evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== Testing Indonesian TTS Pronunciation Normalization ===")
    for tag, raw_text, norm_text in test_pairs:
        t0 = time.time()
        a_raw, sr = tts.synthesize(raw_text, language="id")
        dt_raw = time.time() - t0

        t1 = time.time()
        a_norm, sr = tts.synthesize(norm_text, language="id")
        dt_norm = time.time() - t1

        p_raw = out_dir / f"{tag}_unnormalized.wav"
        p_norm = out_dir / f"{tag}_normalized.wav"
        save_wav(p_raw, a_raw, sr)
        save_wav(p_norm, a_norm, sr)

        print(f"[{tag}]")
        print(f"  Raw:  \"{raw_text}\" -> {len(a_raw)/sr:.2f}s ({dt_raw:.3f}s synth)")
        print(f"  Norm: \"{norm_text}\" -> {len(a_norm)/sr:.2f}s ({dt_norm:.3f}s synth)")
        print(f"  Saved: {p_raw.name} vs {p_norm.name}")

if __name__ == "__main__":
    main()
