import sounddevice as sd
import numpy as np

print("Default device:", sd.default.device)
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0:
        api = sd.query_hostapis(d["hostapi"])["name"]
        print(f"Device {i:2d}: {d['name'][:40]:40s} | API: {api:18s} | in_ch: {d['max_input_channels']} | sr: {d['default_samplerate']}")

# Try WASAPI or DirectSound devices
print("\nTesting which input device can record:")
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0:
        api = sd.query_hostapis(d["hostapi"])["name"]
        for sr in [16000, int(d["default_samplerate"])]:
            for ch in [1, min(2, d["max_input_channels"])]:
                try:
                    rec = sd.rec(int(0.2 * sr), samplerate=sr, channels=ch, dtype="float32", device=i)
                    sd.wait()
                    print(f"  [SUCCESS] Device {i} ({api}) with sr={sr}, ch={ch}! Max amp: {np.max(np.abs(rec)):.4f}")
                    break
                except Exception as e:
                    pass
            else:
                continue
            break
