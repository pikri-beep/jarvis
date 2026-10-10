"""Test recording from Device 20 and transcribing with SpeechToText."""

import sys
import time
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.voice.audio_recorder import PushToTalkRecorder
from app.voice.speech_to_text import SpeechToText

rec = PushToTalkRecorder(device_index=20)
print(f"Device: {rec.device_index}, sr: {rec.sample_rate}, ch: {rec.channels}")
print("Recording 3 seconds of audio...")
rec.start_recording()
time.sleep(3.0)
audio = rec.stop_recording()

print(f"Audio array shape: {audio.shape}")
print(f"Recorded duration: {len(audio)/16000:.2f} s")
if len(audio) > 0:
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio**2)))
    print(f"Peak amplitude:    {peak:.6f}")
    print(f"RMS energy:        {rms:.6f}")
else:
    print("NO AUDIO RECORDED!")

stt = SpeechToText()
text, info = stt.transcribe(audio)
print(f"Transcription: {text!r}")
print(f"Info: {info}")
