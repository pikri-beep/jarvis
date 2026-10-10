import sounddevice as sd
import numpy as np
import time

def find_verified_input_device(preferred_idx=None):
    devices = sd.query_devices()
    
    if preferred_idx is not None and 0 <= preferred_idx < len(devices):
        candidates = [preferred_idx]
    else:
        candidates = []
        for idx, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                name_l = d['name'].lower()
                if 'microphone array' in name_l:
                    candidates.append((0, idx))
                elif 'microphone' in name_l:
                    candidates.append((1, idx))
                else:
                    candidates.append((2, idx))
        candidates.sort(key=lambda x: x[0])
        candidates = [idx for _, idx in candidates]

    for idx in candidates:
        d = devices[idx]
        sr_list = [16000, int(d['default_samplerate']), 48000, 44100]
        for sr in sr_list:
            for ch in [1, min(2, d['max_input_channels'])]:
                frames_received = []
                def _cb(indata, frames, time_info, status):
                    frames_received.append(indata.copy())
                try:
                    stream = sd.InputStream(device=idx, samplerate=sr, channels=ch, callback=_cb, blocksize=1024)
                    stream.start()
                    time.sleep(0.15)
                    stream.stop()
                    stream.close()
                    if len(frames_received) >= 2:
                        arr = np.concatenate(frames_received, axis=0)
                        peak = float(np.max(np.abs(arr)))
                        d_name = d['name'][:35]
                        print(f"Candidate #{idx:2d} ({d_name:35s}) sr={sr} ch={ch} -> {len(frames_received)} chunks, peak={peak:.4f}")
                        if peak > 0.0001:
                            return idx, sr, ch
                except Exception:
                    pass
    return None, 16000, 1

dev, sr, ch = find_verified_input_device()
print(f"Selected verified device: {dev}, sr: {sr}, ch: {ch}")
